"""Haftalık İskelet — hayalet hücreler + bilgili konu çipleri (F1, 2026-09-25).

Koç bir kez "hangi gün hangi ders" iskeletini kurar. Program açılınca her gün
için iskeletteki dersin görevi yoksa HAYALET hücre çıkar. Hayalet görev değildir,
rezerv tutmaz, tabloda saklanmaz — burada o anki veriden hesaplanır.

ÇİPLER (ölçülen İPLİK MODELİ — scripts/backtest_threads.py, prod %75/%79):
  · İplik = o derste son 7 günde çalışılan bölüm; en yeni önde.
    Bölümde test kaldıysa aynı bölüm ("dünün devamı"), bittiyse / konu
    kapatıldıysa aynı kitabın sıradaki konulu bölümü ("kitapta sıradaki").
  · "Yeni konu": dersin kitaplarında sıradaki hiç başlanmamış konu bölümü.
  · "Tekrar": iplik dışında kalmış, denemede ≥2 yanlış yapılan konu.
Çipler CANLI hesaplanır: koç Pazartesi'yi onaylayınca Salı'nın çipleri değişir
(hafta başında dondurmak isabeti %75 → %58'e düşürüyordu).

BİLGİ (kullanıcı şartı: "çip körü körüne değil, bilgiyle seçilsin"): her çip
gerekçe cümlesi + öncelik sıralı rozetler taşır (denemede yanlış · arşivde açık
yanlış · unutuluyor · görev doğruluğu · kalan kapasite · kapatmaya hazır).
Rozet verisi Müfredat panosuyla AYNI kaynaklardan gelir (topic_board
yardımcıları) → iki yüzey farklı sayı gösteremez. ROZETLER SIRAYI DEĞİŞTİRMEZ
(F1 bilinçli kararı — ölçülen isabet korunur; ileride backtest ile denenir).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    Topic,
    User,
)
from app.models.weekly_skeleton import (
    SkeletonGhostAction,
    WeeklySkeleton,
    WeeklySkeletonSlot,
)
from app.services import topic_closure
from app.services.gorev_stats import is_test_book

log = logging.getLogger(__name__)

THREAD_WINDOW_DAYS = 7
MAX_RANGE_DAYS = 14
# "Bu haftayı iskelet yap": aynı kaynak (kitap ya da serbest metin başlığı)
# haftanın en az bu kadar gününde varsa satır RUTİN işaretlenir.
ROUTINE_MIN_DAYS = 4
WEAK_MIN_EXAM_WRONG = 2
# Ders başına en çok kaç 'yeni konu' çipi (her biri FARKLI kitaptan). F1c
# backtest'iyle seçilir (scripts/backtest_skeleton_chips.py --new-chips N).
NEW_TOPIC_CHIPS = 2  # 1→2: tüm çiplerde %74→%77 (prod, 852 kalem); 3 ek kazanç yok
MAX_BADGES_SHOWN = 3  # arayüz ilk 3'ü çipte gösterir, gerisi "ayrıntı"da
GUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
PERIOD_ORDER = {"morning": 0, "noon": 1, "evening": 2, None: 3}


# ---------------------------------------------------------------- veri kabı


@dataclass
class _Sec:
    id: int
    book_id: int
    book_name: str
    subject_id: int
    label: str
    order: int
    topic_id: int | None
    total: int
    completed: int
    reserved: int

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.completed - self.reserved)


@dataclass
class _Ctx:
    student: User
    coach_id: int
    secs: dict[int, _Sec]
    by_book: dict[int, list[_Sec]]
    books_by_subject: dict[int, list[int]]
    closed: set[int]
    topic_names: dict[int, str]
    subject_names: dict[int, str]
    # iplik geçmişi: ders → [(tarih, task_id, section_id, planned)]
    history: dict[int, list[tuple[date, int, int, int]]]
    # o güne konmuş görevler: tarih → ders → [period]
    day_tasks: dict[date, dict[int, list[str | None]]]
    # o güne konmuş bölümler: tarih → ders → {section_id}
    day_sections: dict[date, dict[int, set[int]]]
    exam_wrong: dict[int, int]
    open_wrong: dict[int, int]
    forgotten: set[int]
    perf: dict[int, dict]
    quantity_cache: dict[int, int] = field(default_factory=dict)
    # F2-1: o günün görevleri KAYNAKLARIYLA (iskelet satırı eşleştirme + çıkarım):
    # tarih → [{task_id, subjects, period, book_ids, label, planned, sections}]
    day_items: dict[date, list[dict]] = field(default_factory=dict)

    def open_(self, s: _Sec) -> bool:
        return s.remaining > 0 and not (s.topic_id and s.topic_id in self.closed)

    def advance(self, s: _Sec) -> tuple[_Sec | None, str]:
        """Bölümde test kaldıysa kendisi ('thread'); yoksa kitapta sıradaki açık
        konulu bölüm ('next')."""
        if self.open_(s):
            return s, "thread"
        for c in self.by_book.get(s.book_id, []):
            if c.order > s.order and c.topic_id and self.open_(c):
                return c, "next"
        return None, ""


# ---------------------------------------------------------------- yükleme


def _load_sections(db: Session, student_id: int) -> dict[int, _Sec]:
    rows = (
        db.query(
            BookSection.id, BookSection.book_id, BookSection.label,
            BookSection.order, BookSection.topic_id, BookSection.test_count,
            Book, func.coalesce(SectionProgress.completed_count, 0),
            func.coalesce(SectionProgress.reserved_count, 0),
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(StudentBook.student_id == student_id, StudentBook.archived_at.is_(None))
        .all()
    )
    out: dict[int, _Sec] = {}
    for sid, bid, label, order, tid, tc, book, comp, res in rows:
        if not is_test_book(book):
            continue
        out[sid] = _Sec(
            id=sid, book_id=bid, book_name=book.name, subject_id=book.subject_id,
            label=label or "", order=order or 0, topic_id=tid,
            total=int(tc or 0), completed=int(comp or 0), reserved=int(res or 0),
        )
    return out


def _subject_name_index(db: Session, student: User, coach_id: int) -> dict[int, str]:
    rows = db.query(Subject.id, Subject.name).all()
    return {int(i): n for i, n in rows}


def _task_subjects(t: Task, secs: dict[int, _Sec], book_subj: dict[int, int],
                   topic_subj: dict[int, int], name_to_ids: dict[str, list[int]]) -> set[int]:
    out: set[int] = set()
    for it in t.book_items:
        if it.book_section_id and it.book_section_id in secs:
            out.add(secs[it.book_section_id].subject_id)
        elif it.book_id and it.book_id in book_subj:
            out.add(book_subj[it.book_id])
        elif it.topic_id and it.topic_id in topic_subj:
            out.add(topic_subj[it.topic_id])
    if not out and t.title and " · " in t.title:
        head = t.title.split(" · ", 1)[0].strip().lower()
        out.update(name_to_ids.get(head, []))
    return out


def _activity_label(t: Task) -> str | None:
    """Kitapsız (serbest metinli) görevin koça görünen adı: başlığın "Ders · "
    öneki atılmış hâli ("345 Sıfır Risk Paragraf 2 Test")."""
    if any(it.book_id for it in t.book_items):
        return None
    title = (t.title or "").strip()
    if " · " in title:
        title = title.split(" · ", 1)[1].strip()
    return title[:160] or None


def _norm_label(v: str | None) -> str:
    return " ".join((v or "").lower().split())


def _load_ctx(db: Session, *, student: User, coach_id: int, start: date, end: date) -> _Ctx:
    secs = _load_sections(db, student.id)
    by_book: dict[int, list[_Sec]] = defaultdict(list)
    books_by_subject: dict[int, list[int]] = defaultdict(list)
    for s in secs.values():
        by_book[s.book_id].append(s)
    for bid, lst in by_book.items():
        lst.sort(key=lambda x: (x.order, x.id))
        books_by_subject[lst[0].subject_id].append(bid)

    subject_names = _subject_name_index(db, student, coach_id)
    # Başlıktan ("TYT Matematik · …") ders çözümü: aynı adda BİRDEN ÇOK ders
    # kaydı olabilir (canlıda 5 ayrı "TYT Matematik": sistem + başka koçlarınki).
    # Ad başına TEK ders seçilir: öğrencinin kitaplarındaki ders > sistem dersi >
    # bu koçun dersi. Başka koçun dersi asla seçilmez (iskelete sızmasın).
    own_subjects = set(books_by_subject)
    meta = {
        int(i): (tid, cm)
        for i, tid, cm in db.query(Subject.id, Subject.teacher_id, Subject.curriculum_model)
    }
    best: dict[str, tuple[int, int]] = {}
    for i, n in subject_names.items():
        tid, _cm = meta.get(i, (None, None))
        if i in own_subjects:
            rank = 0
        elif tid is None:
            rank = 1
        elif tid == coach_id:
            rank = 2
        else:
            continue
        key = (n or "").strip().lower()
        if key not in best or rank < best[key][0]:
            best[key] = (rank, i)
    name_to_ids: dict[str, list[int]] = {k: [v[1]] for k, v in best.items()}

    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(
            Task.student_id == student.id,
            Task.date >= start - timedelta(days=THREAD_WINDOW_DAYS),
            Task.date <= end,
        )
        .all()
    )
    book_ids = {it.book_id for t in tasks for it in t.book_items if it.book_id}
    topic_ids = {it.topic_id for t in tasks for it in t.book_items if it.topic_id}
    book_subj = (
        {int(i): int(s) for i, s in db.query(Book.id, Book.subject_id).filter(Book.id.in_(book_ids))}
        if book_ids else {}
    )
    topic_subj = (
        {int(i): int(s) for i, s in db.query(Topic.id, Topic.subject_id).filter(Topic.id.in_(topic_ids))}
        if topic_ids else {}
    )

    history: dict[int, list] = defaultdict(list)
    day_tasks: dict[date, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    day_sections: dict[date, dict[int, set]] = defaultdict(lambda: defaultdict(set))
    day_items: dict[date, list[dict]] = defaultdict(list)
    for t in sorted(tasks, key=lambda x: (x.date, x.id)):
        subs = _task_subjects(t, secs, book_subj, topic_subj, name_to_ids)
        for s in subs:
            day_tasks[t.date][s].append(t.period)
        tsecs = [
            (it.book_section_id, int(it.planned_count or 0))
            for it in sorted(t.book_items, key=lambda x: x.id)
            if it.book_section_id and it.book_section_id in secs
        ]
        day_items[t.date].append({
            "task_id": t.id,
            "subjects": subs,
            "period": t.period,
            "book_ids": [secs[sid].book_id for sid, _n in tsecs],
            "label": _activity_label(t),
            "planned": sum(n for _sid, n in tsecs),
            "sections": tsecs,
        })
        for it in t.book_items:
            if it.book_section_id and it.book_section_id in secs:
                sec = secs[it.book_section_id]
                history[sec.subject_id].append(
                    (t.date, t.id, sec.id, int(it.planned_count or 0))
                )
                day_sections[t.date][sec.subject_id].add(sec.id)

    topic_names = {
        int(i): n for i, n in db.query(Topic.id, Topic.name).filter(
            Topic.id.in_({s.topic_id for s in secs.values() if s.topic_id} or {0})
        )
    }

    # --- bilgi rozetleri (Müfredat panosuyla AYNI kaynaklar)
    from app.services.topic_board import _exam_wrong_counts, _open_wrong_counts

    exam_wrong = _exam_wrong_counts(db, student.id)
    open_wrong = _open_wrong_counts(db, student.id)
    forgotten: set[int] = set()
    try:
        from app.services.exam_topic_analysis import build_exam_topic_analysis

        forgotten = {int(t["topic_id"]) for t in build_exam_topic_analysis(db, student)["forgotten"]}
    except Exception:  # noqa: BLE001 — rozet yan bilgi; çipleri asla düşürmez
        log.warning("skeleton: unutulan konu analizi alınamadı", exc_info=True)
    perf: dict[int, dict] = {}
    try:
        from app.services.topic_performance import compute_topic_performance

        for sp in compute_topic_performance(db, student.id):
            for tp in sp.topics:
                if tp.topic_id:
                    perf[tp.topic_id] = {
                        "tests": tp.tests_solved, "correct": tp.correct,
                        "wrong": tp.wrong, "accuracy": tp.accuracy_pct,
                    }
    except Exception:  # noqa: BLE001
        log.warning("skeleton: konu performansı alınamadı", exc_info=True)

    return _Ctx(
        student=student, coach_id=coach_id, secs=secs, by_book=dict(by_book),
        books_by_subject=dict(books_by_subject),
        closed=topic_closure.closed_topic_ids(db, student.id),
        topic_names=topic_names, subject_names=subject_names,
        history=dict(history), day_tasks=day_tasks, day_sections=day_sections,
        exam_wrong=exam_wrong, open_wrong=open_wrong, forgotten=forgotten, perf=perf,
        day_items=dict(day_items),
    )


# ---------------------------------------------------------------- rozet + çip


def _badges(ctx: _Ctx, sec: _Sec, count: int) -> list[dict]:
    """Öncelik sıralı bilgi rozetleri. Tonlar arayüzde DOLGULU gösterilir."""
    out: list[dict] = []
    tid = sec.topic_id
    if tid:
        ew = ctx.exam_wrong.get(tid, 0)
        if ew:
            out.append({"code": "exam_wrong", "label": f"denemede {ew} yanlış", "tone": "rose"})
        ow = ctx.open_wrong.get(tid, 0)
        if ow:
            out.append({"code": "open_wrong", "label": f"arşivde {ow} açık yanlış", "tone": "amber"})
        if tid in ctx.forgotten:
            out.append({"code": "forgotten", "label": "unutuluyor", "tone": "rose"})
        p = ctx.perf.get(tid) or {}
        acc = p.get("accuracy")
        if acc is not None and int(p.get("tests") or 0) >= 2:
            tone = "rose" if acc < 60 else "amber" if acc < 80 else "emerald"
            out.append({"code": "accuracy", "label": f"görevde %{acc} doğru", "tone": tone})
    rem = sec.remaining
    if rem <= 1:
        out.append({"code": "capacity", "label": "son 1 test", "tone": "amber"})
    elif rem < count:
        out.append({"code": "capacity", "label": f"bölümde {rem} test kaldı", "tone": "amber"})
    if tid:
        from app.services.topic_board import _readiness

        p = ctx.perf.get(tid) or {}
        r, _note = _readiness(
            closed=False, tests=int(p.get("tests") or 0),
            correct=int(p.get("correct") or 0), wrong=int(p.get("wrong") or 0),
            exam_wrong=ctx.exam_wrong.get(tid, 0), open_wrongs=ctx.open_wrong.get(tid, 0),
        )
        if r == "ready":
            out.append({"code": "ready", "label": "kapatmaya hazır", "tone": "emerald"})
    return out


def _default_quantity(db: Session, ctx: _Ctx, subject_id: int) -> int:
    if subject_id not in ctx.quantity_cache:
        from app.services.task_quantity import learned_quantity

        q = learned_quantity(
            db, coach_id=ctx.coach_id, subject_id=subject_id, student_id=ctx.student.id,
        )
        ctx.quantity_cache[subject_id] = int(q.quantity or 3)
    return ctx.quantity_cache[subject_id]


def _chip(ctx: _Ctx, sec: _Sec, kind: str, reason: str, count: int) -> dict:
    count = max(1, min(count, sec.remaining)) if sec.remaining > 0 else max(1, count)
    badges = _badges(ctx, sec, count)
    return {
        "kind": kind,
        "section_id": sec.id,
        "book_id": sec.book_id,
        "book_name": sec.book_name,
        "section_label": sec.label,
        "topic_id": sec.topic_id,
        "topic_name": ctx.topic_names.get(sec.topic_id) if sec.topic_id else None,
        "count": count,
        "remaining": sec.remaining,
        "total": sec.total,
        "reason": reason,
        "badges": badges,
    }


def _continuation_reason(d: date, last: date, rem: int) -> str:
    gap = (d - last).days
    if gap <= 0:
        head = "bugünün devamı"
    elif gap == 1:
        head = "dünün devamı"
    else:
        head = f"{GUN[last.weekday()]} gününün devamı"
    return f"{head} · {rem} test kaldı"


def build_chips(
    db: Session, ctx: _Ctx, *, subject_id: int, d: date, rotate: int = 0,
    default_count: int | None = None, prefer_book: int | None = None,
) -> list[dict]:
    """Bir hayalet hücrenin çipleri (sıra = ölçülen iplik modeli)."""
    taken_secs = set(ctx.day_sections.get(d, {}).get(subject_id, set()))
    taken_topics = {ctx.secs[s].topic_id for s in taken_secs if s in ctx.secs and ctx.secs[s].topic_id}

    hist = [
        h for h in ctx.history.get(subject_id, [])
        if 0 <= (d - h[0]).days <= THREAD_WINDOW_DAYS
    ]
    hist.sort(key=lambda h: (h[0], h[1]), reverse=True)
    seen_threads: set[int] = set()
    last_count: dict[int, int] = {}
    for _dd, _tid, sid, planned in sorted(hist, key=lambda h: (h[0], h[1])):
        last_count[sid] = planned

    thread_chips: list[dict] = []
    used_secs: set[int] = set(taken_secs)
    used_topics: set[int] = set(taken_topics)
    fallback_q = default_count or _default_quantity(db, ctx, subject_id)
    for dd, _tid, sid, _planned in hist:
        if sid in seen_threads or sid in taken_secs:
            continue
        seen_threads.add(sid)
        src = ctx.secs.get(sid)
        if src is None:
            continue
        cur, kind = ctx.advance(src)
        if cur is None or cur.id in used_secs or (cur.topic_id and cur.topic_id in used_topics):
            continue
        q = default_count or last_count.get(sid) or fallback_q
        if kind == "thread":
            reason = _continuation_reason(d, dd, cur.remaining)
        else:
            reason = f"kitapta sıradaki konu ({src.label} bitti)"
        thread_chips.append(_chip(ctx, cur, kind, reason, q))
        used_secs.add(cur.id)
        if cur.topic_id:
            used_topics.add(cur.topic_id)

    if rotate and len(thread_chips) > 1:
        k = rotate % len(thread_chips)
        thread_chips = thread_chips[k:] + thread_chips[:k]
    chips = list(thread_chips)

    # --- yeni konu: dersin kitaplarında sıradaki hiç başlanmamış konu
    recent_books: list[int] = []
    for _dd, _tid, sid, _p in hist:
        b = ctx.secs[sid].book_id if sid in ctx.secs else None
        if b and b not in recent_books:
            recent_books.append(b)
    others = sorted(
        (b for b in ctx.books_by_subject.get(subject_id, []) if b not in recent_books),
        key=lambda b: ctx.by_book[b][0].book_name if ctx.by_book.get(b) else "",
    )
    new_added = 0
    book_order = recent_books + others
    if prefer_book in book_order:
        book_order = [prefer_book] + [b for b in book_order if b != prefer_book]
    for b in book_order:
        cand = next(
            (
                c for c in ctx.by_book.get(b, [])
                if c.topic_id and c.completed == 0 and c.reserved == 0
                and ctx.open_(c) and c.id not in used_secs
                and c.topic_id not in used_topics
            ),
            None,
        )
        if cand is not None:
            chips.append(_chip(
                ctx, cand, "new", f"yeni konu — {cand.book_name}'ta sıradaki başlanmamış konu",
                fallback_q,
            ))
            used_secs.add(cand.id)
            used_topics.add(cand.topic_id)
            new_added += 1
            if new_added >= NEW_TOPIC_CHIPS:
                break

    # --- tekrar: iplik dışında kalmış, denemede yanlış yapılan konu
    weak = sorted(
        (
            (n, tid) for tid, n in ctx.exam_wrong.items()
            if n >= WEAK_MIN_EXAM_WRONG and tid not in used_topics and tid not in ctx.closed
        ),
        reverse=True,
    )
    for n, tid in weak:
        srcs = [
            s for s in ctx.secs.values()
            if s.topic_id == tid and s.subject_id == subject_id and s.remaining > 0
        ]
        if not srcs:
            continue
        srcs.sort(key=lambda s: (s.completed == 0, -s.remaining, s.book_name))
        chips.append(_chip(ctx, srcs[0], "weak", f"tekrar — denemede {n} yanlış", fallback_q))
        break

    if prefer_book is not None:
        # Satırın kaynağı olan kitabın çipleri öne (sıra içi korunur).
        chips.sort(key=lambda c: c["book_id"] != prefer_book)
    for i, c in enumerate(chips, start=1):
        c["rank"] = i
    return chips


def _last_used_in_book(ctx: _Ctx, book_id: int, d: date) -> _Sec | None:
    """Rutin kitabında en son hangi bölümde kalındı (d günü dahil, iplik penceresi).
    En yeni görevin o kitaptaki SON kalemi (kalem sırasıyla) — karışık rutin
    başa sardığında (…4 · 5 · 1) doğru yer 1'dir, en büyük sıra numarası değil."""
    best = None
    for dd, items in ctx.day_items.items():
        if dd > d:
            continue
        for it in items:
            last = None
            for sid, _n in it["sections"]:
                sec = ctx.secs.get(sid)
                if sec is not None and sec.book_id == book_id:
                    last = sec
            if last is not None and (best is None or (dd, it["task_id"]) > best[0]):
                best = ((dd, it["task_id"]), last)
    return best[1] if best else None


def routine_items(
    ctx: _Ctx, *, book_id: int, mode: str | None, count: int, d: date,
) -> list[tuple[_Sec, int]]:
    """Kitaba bağlı rutinin o günkü kalemleri.

    sirali: kalınan bölümden (testi varsa) başlayıp sırayla doldurur, bölüm
            biterse sıradakine taşar.
    karma:  kalınan bölümün SONRAKİNDEN başlayıp her bölümden birer test alır,
            bölümler arasında döner (paragraf: Sözcükte Anlam 1 · Cümlede
            Anlam 1 · …). Kapatılmış konu ve testi bitmiş bölüm atlanır; o gün
            zaten verilmiş bölüm tekrar verilmez.
    """
    taken = {
        sid for subj in ctx.day_sections.get(d, {}).values() for sid in subj
    }
    book = ctx.by_book.get(book_id, [])
    opens = [s for s in book if ctx.open_(s) and s.id not in taken]
    if not opens or count <= 0:
        return []
    last = _last_used_in_book(ctx, book_id, d)
    if mode == "karma":
        start = 0
        if last is not None:
            start = next((i for i, s in enumerate(opens) if s.order > last.order), 0)
        ring = opens[start:] + opens[:start]
        left = {s.id: s.remaining for s in ring}
        got: dict[int, int] = {}
        need = count
        while need > 0 and any(left[s.id] > 0 for s in ring):
            for s in ring:
                if need == 0:
                    break
                if left[s.id] > 0:
                    got[s.id] = got.get(s.id, 0) + 1
                    left[s.id] -= 1
                    need -= 1
        return [(s, got[s.id]) for s in ring if s.id in got]
    # sirali
    start = 0
    if last is not None:
        start = next((i for i, s in enumerate(opens) if s.order >= last.order), 0)
    out: list[tuple[_Sec, int]] = []
    need = count
    for s in opens[start:] + opens[:start]:
        if need == 0:
            break
        n = min(s.remaining, need)
        if n > 0:
            out.append((s, n))
            need -= n
    return out


def _routine_chip(ctx: _Ctx, slot: WeeklySkeletonSlot, d: date, fallback_q: int) -> dict | None:
    items = routine_items(
        ctx, book_id=slot.book_id, mode=slot.routine_mode,
        count=slot.default_count or fallback_q, d=d,
    )
    if not items:
        return None
    first = items[0][0]
    total = sum(n for _s, n in items)
    reason = (
        f"rutin · karışık: {len(items)} farklı bölüm"
        if slot.routine_mode == "karma"
        else "rutin · kitapta sırayla"
        + (f" ({first.label} bitince {items[-1][0].label})" if len(items) > 1 else "")
    )
    chip = _chip(ctx, first, "routine", reason, total)
    chip["count"] = total
    chip["badges"] = []
    chip["items"] = [
        {"section_id": s.id, "section_label": s.label, "count": n} for s, n in items
    ]
    chip["rank"] = 1
    return chip


# ---------------------------------------------------------------- hayaletler


def get_skeleton(db: Session, student_id: int) -> WeeklySkeleton | None:
    return (
        db.query(WeeklySkeleton)
        .options(joinedload(WeeklySkeleton.slots))
        .filter(WeeklySkeleton.student_id == student_id)
        .first()
    )


def _match_by_source(
    slots: list[WeeklySkeletonSlot], items: list[dict],
) -> tuple[list[WeeklySkeletonSlot], list[dict]]:
    """Kaynaklı satır (kitap/etiket) önce KENDİ kaynağının göreviyle eşleşir —
    aynı derste üç satırdan hangisinin dolu olduğu doğru bilinsin (rutin
    problemler satırı, konu satırının göreviyle 'dolmuş' sayılmasın)."""
    pool = list(items)
    rest: list[WeeklySkeletonSlot] = []
    for s in slots:
        hit = None
        if s.book_id:
            hit = next((it for it in pool if s.book_id in it["book_ids"]), None)
        elif s.label:
            key = _norm_label(s.label)
            hit = next((it for it in pool if _norm_label(it["label"]) == key), None)
        if hit is not None:
            pool.remove(hit)
        else:
            rest.append(s)
    return rest, pool


def _unfilled_slots(
    slots: list[WeeklySkeletonSlot], periods: list[str | None],
) -> list[WeeklySkeletonSlot]:
    """O gün o derse konmuş görevlerle iskelet satırlarını eşleştir; boş kalanlar
    hayalettir. Periyotlu satır önce aynı periyottaki görevi alır, periyotsuz
    satır herhangi birini, periyotlu satır son çare olarak periyotsuz görevi."""
    left = list(periods)
    unmatched: list[WeeklySkeletonSlot] = []
    pending: list[WeeklySkeletonSlot] = []
    for s in slots:
        if s.period and s.period in left:
            left.remove(s.period)
        else:
            pending.append(s)
    later: list[WeeklySkeletonSlot] = []
    for s in pending:
        if s.period is None and left:
            left.pop(0)
        else:
            later.append(s)
    for s in later:
        if None in left:
            left.remove(None)
        else:
            unmatched.append(s)
    return unmatched


def build_ghosts(
    db: Session, *, student: User, coach_id: int, start: date, end: date,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    sk = get_skeleton(db, student.id)
    if sk is None or not sk.slots:
        return {"has_skeleton": sk is not None, "days": []}
    start = max(start, today)
    if end < start:
        return {"has_skeleton": True, "days": []}
    end = min(end, start + timedelta(days=MAX_RANGE_DAYS - 1))

    ctx = _load_ctx(db, student=student, coach_id=coach_id, start=start, end=end)
    dismissed = {
        (a.slot_id, a.date)
        for a in db.query(SkeletonGhostAction).filter(
            SkeletonGhostAction.student_id == student.id,
            SkeletonGhostAction.action == "dismissed",
            SkeletonGhostAction.date >= start,
            SkeletonGhostAction.date <= end,
        )
    }

    slot_books = {s.book_id for s in sk.slots if s.book_id}
    book_names = (
        {int(i): n for i, n in db.query(Book.id, Book.name).filter(Book.id.in_(slot_books))}
        if slot_books else {}
    )
    days = []
    d = start
    while d <= end:
        wd = [s for s in sk.slots if s.weekday == d.weekday()]
        by_subj: dict[int, list[WeeklySkeletonSlot]] = defaultdict(list)
        for s in sorted(wd, key=lambda x: (x.position, x.id)):
            by_subj[s.subject_id].append(s)
        ghosts = []
        for subj, slots in by_subj.items():
            items = [it for it in ctx.day_items.get(d, []) if subj in it["subjects"]]
            # 1) kaynaklı satırlar kendi kaynağıyla; 2) kalan satırlar kalan
            #    görevlerle periyot kuralına göre (kaynaksız satırlar önce).
            rest, pool = _match_by_source(slots, items)
            rest.sort(key=lambda s: (bool(s.book_id or s.label), s.position, s.id))
            unfilled = [
                s for s in _unfilled_slots(rest, [it["period"] for it in pool])
                if (s.id, d) not in dismissed
            ]
            unfilled.sort(key=lambda s: (s.position, s.id))
            k = 0
            for s in unfilled:
                fallback_q = s.default_count or _default_quantity(db, ctx, subj)
                chips: list[dict] = []
                if s.is_routine and s.book_id:
                    rc = _routine_chip(ctx, s, d, fallback_q)
                    chips = [rc] if rc else []
                if not chips and not (s.is_routine and s.label and not s.book_id):
                    chips = build_chips(
                        db, ctx, subject_id=subj, d=d, rotate=0 if s.book_id else k,
                        default_count=s.default_count, prefer_book=s.book_id,
                    )
                    if not s.book_id:
                        k += 1
                ghosts.append({
                    "slot_id": s.id,
                    "date": d.isoformat(),
                    "subject_id": subj,
                    "subject_name": ctx.subject_names.get(subj, "?"),
                    "period": s.period,
                    "position": s.position,
                    "is_routine": bool(s.is_routine),
                    "book_id": s.book_id,
                    "book_name": book_names.get(s.book_id) if s.book_id else None,
                    "label": s.label,
                    "routine_mode": s.routine_mode,
                    "chips": chips,
                })
        ghosts.sort(key=lambda g: (PERIOD_ORDER.get(g["period"], 3), g["position"]))
        days.append({"date": d.isoformat(), "ghosts": ghosts})
        d += timedelta(days=1)
    return {"has_skeleton": True, "days": days}


def find_ghost(db: Session, *, student: User, coach_id: int, slot_id: int, d: date) -> dict | None:
    data = build_ghosts(db, student=student, coach_id=coach_id, start=d, end=d)
    for day in data["days"]:
        for g in day["ghosts"]:
            if g["slot_id"] == slot_id:
                return g
    return None


# ---------------------------------------------------------------- iskelet kurma


def _is_drill_book(ctx: _Ctx, book_id: int) -> bool:
    """Alıştırma (rutin) kitabı mı: bölümlerinin çoğu müfredat konusuna BAĞLI
    DEĞİL (paragraf / karma test / deneme tarzı). Konu sıralı soru bankası değil."""
    secs = ctx.by_book.get(book_id, [])
    if not secs:
        return False
    return sum(1 for x in secs if not x.topic_id) * 2 >= len(secs)


def slots_from_tasks(
    db: Session, *, student: User, coach_id: int, start: date, end: date,
) -> list[dict]:
    """Bir haftanın görevlerinden iskelet satırları.

    Her görev bir satır (gün + periyot + ders) ve KAYNAĞINI taşır: kitaba bağlı
    görevde kitap, serbest metinli görevde başlık (label). Aynı kaynak haftanın
    en az ROUTINE_MIN_DAYS gününde varsa satır RUTİN işaretlenir (kitapta
    yalnız alıştırma kitabıysa — konu kitabı her gün kullanılsa da konu
    ipliğidir); adet o kaynağın en sık günlük adedi. Kitaba bağlı rutinde bir günde aynı kitabın
    ≥2 bölümünden birer test verildiyse biçim 'karma', yoksa 'sirali'.
    Aralık 7 günü aşarsa her hafta günü için İLK tarih esas alınır."""
    from collections import Counter

    end = min(end, start + timedelta(days=MAX_RANGE_DAYS - 1))
    ctx = _load_ctx(db, student=student, coach_id=coach_id, start=start, end=end)

    def src(it: dict) -> tuple:
        if it["book_ids"]:
            return ("b", it["book_ids"][0])
        if it["label"]:
            return ("l", _norm_label(it["label"]))
        return ("s", None)

    days_of: dict[tuple, set] = defaultdict(set)
    counts: dict[tuple, Counter] = defaultdict(Counter)
    karma_votes: dict[tuple, list[bool]] = defaultdict(list)
    d = start
    while d <= end:
        for it in ctx.day_items.get(d, []):
            for subj in it["subjects"]:
                key = (subj, src(it))
                days_of[key].add(d)
                if it["planned"]:
                    counts[key][it["planned"]] += 1
                if key[1][0] == "b":
                    karma_votes[key].append(
                        len(it["sections"]) >= 2 and all(n == 1 for _s, n in it["sections"])
                    )
        d += timedelta(days=1)

    seen_weekdays: set[int] = set()
    out: list[dict] = []
    d = start
    while d <= end:
        wd = d.weekday()
        items = ctx.day_items.get(d, [])
        if wd not in seen_weekdays and items:
            seen_weekdays.add(wd)
            rows = []
            for it in items:
                for subj in it["subjects"]:
                    key = (subj, src(it))
                    routine = key[1][0] != "s" and len(days_of[key]) >= ROUTINE_MIN_DAYS
                    if routine and key[1][0] == "b" and not _is_drill_book(ctx, key[1][1]):
                        # Konu kitabı her gün kullanılsa da RUTİN değil, konu ipliğidir
                        # (Orijinal Mat: Temel Kavramlar → Oran-Orantı → …); rutin
                        # işaretlenirse bilgili konu çiplerini kaybeder. Koç isterse
                        # düzenleyicide elle rutin yapar.
                        routine = False
                    book_id = it["book_ids"][0] if it["book_ids"] else None
                    mode = None
                    if routine and book_id:
                        votes = karma_votes[key]
                        mode = "karma" if votes and sum(votes) * 2 > len(votes) else "sirali"
                    dc = counts[key].most_common(1)[0][0] if routine and counts[key] else None
                    rows.append((
                        PERIOD_ORDER.get(it["period"], 3),
                        ctx.subject_names.get(subj, ""), it["task_id"],
                        {"weekday": wd, "period": it["period"], "subject_id": subj,
                         "is_routine": routine, "default_count": dc,
                         "book_id": book_id, "label": None if book_id else it["label"],
                         "routine_mode": mode},
                    ))
            for pos, (_po, _n, _t, row) in enumerate(sorted(rows, key=lambda r: r[:3])):
                row["position"] = pos
                out.append(row)
        d += timedelta(days=1)
    return out


def replace_slots(
    db: Session, *, student: User, coach_id: int, slots: list[dict],
    name: str | None = None, source: str = "manual",
) -> WeeklySkeleton:
    sk = get_skeleton(db, student.id)
    if sk is None:
        sk = WeeklySkeleton(student_id=student.id, coach_id=coach_id)
        db.add(sk)
        db.flush()
    sk.coach_id = coach_id
    sk.source = source
    if name:
        sk.name = name.strip()[:120]
    for s in list(sk.slots):
        sk.slots.remove(s)
    db.flush()
    for i, s in enumerate(slots):
        sk.slots.append(WeeklySkeletonSlot(
            weekday=int(s["weekday"]), period=s.get("period"),
            subject_id=int(s["subject_id"]), position=int(s.get("position", i)),
            is_routine=bool(s.get("is_routine")), default_count=s.get("default_count"),
            book_id=s.get("book_id"), label=(s.get("label") or None),
            routine_mode=s.get("routine_mode"),
        ))
    db.flush()
    return sk


def acceptance_report(db: Session, *, coach_id: int | None = None, days: int = 30) -> dict:
    """F1 başarı ölçüsü — koçun hayaletlerde ne yaptığı."""
    since = date.today() - timedelta(days=days)
    q = db.query(SkeletonGhostAction).filter(SkeletonGhostAction.date >= since)
    if coach_id is not None:
        q = q.filter(SkeletonGhostAction.coach_id == coach_id)
    rows = q.all()
    total = len(rows)
    acc = [r for r in rows if r.action == "accepted"]
    by_rank: dict[int, int] = defaultdict(int)
    by_kind: dict[str, int] = defaultdict(int)
    for r in acc:
        by_rank[r.chip_rank or 0] += 1
        by_kind[r.chip_kind or "?"] += 1
    return {
        "actions": total,
        "accepted": len(acc),
        "other": sum(1 for r in rows if r.action == "other"),
        "dismissed": sum(1 for r in rows if r.action == "dismissed"),
        "acceptance_pct": round(100 * len(acc) / total) if total else None,
        "by_rank": dict(sorted(by_rank.items())),
        "by_kind": dict(by_kind),
    }
