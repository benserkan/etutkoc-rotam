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

log = logging.getLogger(__name__)

THREAD_WINDOW_DAYS = 7
MAX_RANGE_DAYS = 14
# "Bu haftayı iskelet yap": aynı kaynak (kitap ya da serbest metin başlığı)
# haftanın en az bu kadar gününde varsa satır RUTİN işaretlenir.
ROUTINE_MIN_DAYS = 4
# Rutinin GÜNLÜK toplam adedi boşsa kullanılan değer. Koçun kalem-başı alışkanlığı
# (P3) burada KULLANILMAZ: karışık paragraf rutininde her bölümden 1'er test
# verildiği için alışkanlık 1 çıkıyor, oysa rutinin günlük toplamı 3'tür.
ROUTINE_DEFAULT_COUNT = 3
# Bu adedin üstündeki günlük rutin olağandışı sayılır (düzenleyici + önizleme uyarır).
ROUTINE_WARN_COUNT = 6
# Deneme kitabı rutininde adet boşsa günde 1 deneme (3 değil).
DENEME_BOOK_TYPES = ("brans_denemesi", "genel_deneme")
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
    book_type: str = ""

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
    # F2-4: problem bölümleri (rutin 'problems' kapsamı) + soru bankası kitapları
    problem_secs: set[int] = field(default_factory=set)
    bank_books: set[int] = field(default_factory=set)

    def open_(self, s: _Sec) -> bool:
        return s.remaining > 0 and not (s.topic_id and s.topic_id in self.closed)

    def advance(self, s: _Sec, exclude: set[int] | frozenset = frozenset()) -> tuple[_Sec | None, str]:
        """Bölümde test kaldıysa kendisi ('thread'); yoksa kitapta sıradaki açık
        konulu bölüm ('next'). exclude: atlanacak bölümler (konu satırında
        problem rutininin bölümleri)."""
        if self.open_(s):
            return s, "thread"
        for c in self.by_book.get(s.book_id, []):
            if c.order > s.order and c.topic_id and self.open_(c) and c.id not in exclude:
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
        # Deneme kitapları da yüklenir (2026-10-01): satırın kaynağı olabilir
        # (her gün sırayla N deneme). Konu önerisi ipliklerine KARIŞMAZ (build_chips).
        out[sid] = _Sec(
            id=sid, book_id=bid, book_name=book.name, subject_id=book.subject_id,
            label=label or "", order=order or 0, topic_id=tid,
            total=int(tc or 0), completed=int(comp or 0), reserved=int(res or 0),
            book_type=getattr(book.type, "value", str(book.type or "")),
        )
    return out


# ---------------------------------------------------------------- problem bölümleri (F2-4)

BANK_TYPE = "soru_bankasi"


def _tr_low(v: str | None) -> str:
    return (v or "").replace("İ", "i").replace("I", "ı").lower()


def _is_osym_block(label: str) -> bool:
    low = _tr_low(label)
    return "ösym" in low or "osym" in low


def _problemish(sec: "_Sec", topic_names: dict[int, str]) -> bool:
    """Bölüm problem konusu mu: etiketinde ya da konusunda 'problem' / 'orantı'."""
    texts = [_tr_low(sec.label)]
    if sec.topic_id:
        texts.append(_tr_low(topic_names.get(sec.topic_id)))
    return any("problem" in t or "orantı" in t or "oranti" in t for t in texts)


def problem_section_ids(by_book: dict[int, list["_Sec"]], topic_names: dict[int, str]) -> set[int]:
    """Kitapların PROBLEM bloğu (rutin 'problems' kapsamı).

    Blok = kitapta Oran-Orantı (yoksa etiketinde 'problem' geçen ilk bölüm) ile son
    problem bölümü arası. Blok içinde: problem konulu ya da konusu olmayan bölümler
    (Problem Denemeleri); ÖSYM çıkmış blokları ve blok içine düşen konu bölümleri
    (Birinci Dereceden Denklemler) hariç. Bloktan önceki 'problem' konulu bölüm
    (Özel Sayı Tanımlama → Sayısal Yetenek) konu hattına aittir, alınmaz."""
    out: set[int] = set()
    for secs in by_book.values():
        cand = [
            i for i, x in enumerate(secs)
            if not _is_osym_block(x.label) and _problemish(x, topic_names)
        ]
        if not cand:
            continue
        start = next(
            (i for i in cand if "oran" in _tr_low(secs[i].label)
             or (secs[i].topic_id and "oran" in _tr_low(topic_names.get(secs[i].topic_id)))),
            None,
        )
        if start is None:
            start = next((i for i in cand if "problem" in _tr_low(secs[i].label)), cand[0])
        end = cand[-1]
        for i in range(start, end + 1):
            x = secs[i]
            if _is_osym_block(x.label):
                continue
            if x.topic_id is None or _problemish(x, topic_names):
                out.add(x.id)
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

    problem_secs = problem_section_ids(by_book, topic_names)
    bank_books = {s.book_id for s in secs.values() if s.book_type == BANK_TYPE}
    return _Ctx(
        problem_secs=problem_secs, bank_books=bank_books,
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
    exclude: set[int] | frozenset = frozenset(), second_book: int | None = None,
) -> list[dict]:
    """Bir hayalet hücrenin çipleri (sıra = ölçülen iplik modeli).

    exclude: bu satırda önerilmeyecek bölümler — o derste problem rutini varsa
    problem bölümleri konu satırına sızmaz (F2-4).
    second_book: satırın 2. ana kaynağı. 1. kaynakta konu biterse aynı konu
    2. kaynakta İLK öneri olur (2026-09-30: koç seçmez, otomatik); 2. kaynakta konu
    bitince ana kaynakta (prefer_book) o konudan sonraki konuya dönülür."""
    taken_secs = set(ctx.day_sections.get(d, {}).get(subject_id, set()))
    taken_topics = {ctx.secs[s].topic_id for s in taken_secs if s in ctx.secs and ctx.secs[s].topic_id}

    hist = [
        h for h in ctx.history.get(subject_id, [])
        if 0 <= (d - h[0]).days <= THREAD_WINDOW_DAYS and h[2] not in exclude
        and not _is_deneme_sec(ctx, h[2])
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
        cur, kind = ctx.advance(src, exclude)
        back_reason = None
        if (
            second_book and prefer_book and src.book_id == second_book
            and kind != "thread" and src.topic_id
        ):
            # 2. kaynakta bölüm bitti: aynı konunun 2. kaynakta açık bölümü varsa o,
            # yoksa ana kaynakta konudan sonraki konu (2. kaynağın kendi sırasına kayma).
            same = next(
                (c for c in ctx.by_book.get(second_book, [])
                 if c.topic_id == src.topic_id and ctx.open_(c) and c.id not in exclude),
                None,
            )
            if same is not None:
                cur, kind = same, "next"
                back_reason = f"aynı konu 2. kaynakta sürüyor ({src.label} bitti)"
            else:
                cur = _primary_after_topic(ctx, prefer_book, src.topic_id, exclude)
                kind = "next" if cur is not None else ""
                back_reason = (f"konu iki kaynakta da bitti — ana kaynakta sıradaki konu"
                               if cur is not None else None)
        q = default_count or last_count.get(sid) or fallback_q
        # F2-4: konu 1. kaynakta bitti → 2. kaynaktan AYNI konu da seçenek.
        alt = None
        if (
            second_book and kind != "thread" and src.topic_id
            and src.book_id != second_book and src.topic_id not in used_topics
        ):
            alt = next(
                (c for c in ctx.by_book.get(second_book, [])
                 if c.topic_id == src.topic_id and ctx.open_(c)
                 and c.id not in used_secs and c.id not in exclude),
                None,
            )
        if alt is not None:
            ch = _chip(
                ctx, alt, "second",
                f"{src.book_name}'da {src.label} bitti — konu 2. kaynakta bitiriliyor", q,
            )
            thread_chips.append(ch)
            used_secs.add(alt.id)
        if cur is None or cur.id in used_secs or (cur.topic_id and cur.topic_id in used_topics):
            if alt is not None:
                used_topics.add(alt.topic_id)
            continue
        if kind == "thread":
            reason = _continuation_reason(d, dd, cur.remaining)
        elif back_reason:
            reason = back_reason
        else:
            reason = f"kitapta sıradaki konu ({src.label} bitti)"
        ch = _chip(ctx, cur, kind, reason, q)
        thread_chips.append(ch)
        used_secs.add(cur.id)
        if cur.topic_id:
            used_topics.add(cur.topic_id)
        if alt is not None:
            used_topics.add(alt.topic_id)

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
                and ctx.open_(c) and c.id not in used_secs and c.id not in exclude
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
            and s.id not in exclude
        ]
        if not srcs:
            continue
        srcs.sort(key=lambda s: (s.completed == 0, -s.remaining, s.book_name))
        chips.append(_chip(ctx, srcs[0], "weak", f"tekrar — denemede {n} yanlış", fallback_q))
        break

    if prefer_book is not None:
        # Satırın kaynağı olan kitabın çipleri öne (sıra içi korunur). 2. kaynakta
        # süren/bitirilen konu (iplik çipi) en önde kalır: konu iki kaynakta bitmeden
        # ana kaynakta yeni konuya geçilmez.
        # Yalnız ANA kaynakta bitmiş (açık bölümü kalmamış) bir konunun 2. kaynaktaki
        # devamı öne çıkar; 2. kaynağın konudan bağımsız iplikleri öne atlamaz.
        prim = ctx.by_book.get(prefer_book, [])
        prim_topics = {c.topic_id for c in prim if c.topic_id}
        prim_open = {c.topic_id for c in prim if c.topic_id and ctx.open_(c)}
        second_first = {
            id(c) for c in thread_chips
            if second_book and c["book_id"] == second_book and c.get("topic_id")
            and c["topic_id"] in prim_topics and c["topic_id"] not in prim_open
        }
        chips.sort(key=lambda c: (id(c) not in second_first, c["book_id"] != prefer_book))
    for i, c in enumerate(chips, start=1):
        c["rank"] = i
    return chips


def _is_deneme_sec(ctx: _Ctx, sid: int) -> bool:
    sec = ctx.secs.get(sid)
    return sec is not None and sec.book_type in DENEME_BOOK_TYPES


def _is_deneme_book(ctx: _Ctx, book_id: int | None) -> bool:
    return bool(
        book_id and ctx.by_book.get(book_id)
        and ctx.by_book[book_id][0].book_type in DENEME_BOOK_TYPES
    )


def _last_used(ctx: _Ctx, d: date, pred) -> _Sec | None:
    """pred(bölüm) sağlayan bölümlerde en son nerede kalındı (d günü dahil).
    En yeni görevin SON uygun kalemi (kalem sırasıyla) — karışık rutin başa
    sardığında (…4 · 5 · 1) doğru yer 1'dir, en büyük sıra numarası değil."""
    best = None
    for dd, items in ctx.day_items.items():
        if dd > d:
            continue
        for it in items:
            last = None
            for sid, _n in it["sections"]:
                sec = ctx.secs.get(sid)
                if sec is not None and pred(sec):
                    last = sec
            if last is not None and (best is None or (dd, it["task_id"]) > best[0]):
                best = ((dd, it["task_id"]), last)
    return best[1] if best else None


def _last_used_in_book(ctx: _Ctx, book_id: int, d: date) -> _Sec | None:
    return _last_used(ctx, d, lambda s: s.book_id == book_id)


def problem_queue(ctx: _Ctx, *, subject_id: int, book_id: int | None) -> list[int]:
    """Problem rutininin KAYNAK SIRASI: yalnız SORU BANKALARI (konu anlatımlı /
    video destekli defter ana kaynak değildir). Satırın kitabı önde, sonra
    problemlerine başlanmış olanlar, sonra başlanmamışlar (ada göre)."""
    books = [
        b for b in ctx.books_by_subject.get(subject_id, [])
        if b in ctx.bank_books and any(x.id in ctx.problem_secs for x in ctx.by_book.get(b, []))
    ]

    def started(b: int) -> bool:
        return any(
            x.id in ctx.problem_secs and (x.completed or x.reserved)
            for x in ctx.by_book.get(b, [])
        )

    books.sort(key=lambda b: (
        b != book_id, not started(b),
        ctx.by_book[b][0].book_name if ctx.by_book.get(b) else "",
    ))
    return books


def _two_source_chain(ctx: _Ctx, primary: int, second: int) -> list[_Sec]:
    """İki kaynaklı konu zinciri: ana kaynak sırası; her konunun ana kaynaktaki SON
    bölümünün hemen ardından 2. kaynakta AYNI müfredat konusuna bağlı bölümler
    (2. kaynağın kendi sırasıyla). Konusu olmayan / ana kaynakta karşılığı olmayan
    2. kaynak bölümleri zincire girmez."""
    prim = ctx.by_book.get(primary, [])
    sec_by_topic: dict[int, list[_Sec]] = defaultdict(list)
    for c in ctx.by_book.get(second, []):
        if c.topic_id:
            sec_by_topic[c.topic_id].append(c)
    last_idx = {c.topic_id: i for i, c in enumerate(prim) if c.topic_id}
    chain: list[_Sec] = []
    for i, c in enumerate(prim):
        chain.append(c)
        if c.topic_id and last_idx.get(c.topic_id) == i:
            chain.extend(sec_by_topic.get(c.topic_id, []))
    return chain


def _primary_after_topic(
    ctx: _Ctx, primary: int, topic_id: int, exclude: set[int] | frozenset = frozenset(),
) -> _Sec | None:
    """Ana kaynakta, verilen konunun SON bölümünden sonraki ilk açık konulu bölüm."""
    prim = ctx.by_book.get(primary, [])
    orders = [c.order for c in prim if c.topic_id == topic_id]
    if not orders:
        return None
    mx = max(orders)
    return next(
        (c for c in prim if c.order > mx and c.topic_id and ctx.open_(c) and c.id not in exclude),
        None,
    )


def routine_items(
    ctx: _Ctx, *, book_id: int, mode: str | None, count: int, d: date,
    scope: str | None = None, subject_id: int | None = None,
    second_book: int | None = None,
) -> list[tuple[_Sec, int]]:
    """Kitaba bağlı rutinin o günkü kalemleri.

    sirali: kalınan bölümden (testi varsa) başlayıp sırayla doldurur, bölüm
            biterse sıradakine taşar.
    karma:  kalınan bölümün SONRAKİNDEN başlayıp her bölümden birer test alır,
            bölümler arasında döner (paragraf: Sözcükte Anlam 1 · Cümlede
            Anlam 1 · …). Kapatılmış konu ve testi bitmiş bölüm atlanır; o gün
            zaten verilmiş bölüm tekrar verilmez.
    scope='problems' (F2-4): yalnız problem bölümleri. Kalınan kaynağın
            problemleri bitince sıradaki SORU BANKASININ problemlerinden baştan
            (Oran-Orantı) devam eder — konu hattına (Fonksiyon, Polinomlar)
            asla kaymaz.
    """
    taken = {
        sid for subj in ctx.day_sections.get(d, {}).values() for sid in subj
    }
    if count <= 0:
        return []
    if scope == "problems":
        if subject_id is None and ctx.by_book.get(book_id):
            subject_id = ctx.by_book[book_id][0].subject_id
        return _problem_routine_items(
            ctx, book_id=book_id, mode=mode, count=count, d=d, taken=taken,
            subject_id=subject_id,
        )
    if mode == "iki_kaynak" and second_book and second_book != book_id:
        # Konu ana kaynakta bitince aynı konu 2. kaynakta SINIRSIZ bitirilir, sonra
        # ana kaynakta sıradaki konu. Kalınan yer iki kitabın en yeni kalemi.
        chain = _two_source_chain(ctx, book_id, second_book)
        ids = [c.id for c in chain]
        last = _last_used(ctx, d, lambda s: s.book_id in (book_id, second_book) and s.id in ids)
        start = ids.index(last.id) if last is not None else 0
        seq = [
            c for c in chain[start:] + chain[:start]
            if ctx.open_(c) and c.id not in taken
        ]
        return _fill(seq, count)
    book = ctx.by_book.get(book_id, [])
    opens = [s for s in book if ctx.open_(s) and s.id not in taken]
    if not opens:
        return []
    last = _last_used_in_book(ctx, book_id, d)
    if mode == "karma":
        return _karma(opens, last, count)
    # sirali
    start = 0
    if last is not None:
        start = next((i for i, s in enumerate(opens) if s.order >= last.order), 0)
    return _fill(opens[start:] + opens[:start], count)


def _fill(seq: list[_Sec], count: int) -> list[tuple[_Sec, int]]:
    out: list[tuple[_Sec, int]] = []
    need = count
    for s in seq:
        if need == 0:
            break
        n = min(s.remaining, need)
        if n > 0:
            out.append((s, n))
            need -= n
    return out


def _karma(opens: list[_Sec], last: _Sec | None, count: int) -> list[tuple[_Sec, int]]:
    start = 0
    if last is not None and last.book_id == opens[0].book_id:
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


def _problem_routine_items(
    ctx: _Ctx, *, book_id: int, mode: str | None, count: int, d: date,
    taken: set[int], subject_id: int | None,
) -> list[tuple[_Sec, int]]:
    queue = problem_queue(ctx, subject_id=subject_id, book_id=book_id) if subject_id else []
    if not queue:
        return []
    last = _last_used(ctx, d, lambda s: s.id in ctx.problem_secs and s.book_id in queue)
    cur = last.book_id if last is not None else queue[0]
    k = queue.index(cur)
    order = queue[k:] + queue[:k]

    def opens_of(b: int) -> list[_Sec]:
        return [
            x for x in ctx.by_book.get(b, [])
            if x.id in ctx.problem_secs and ctx.open_(x) and x.id not in taken
        ]

    if mode == "karma":
        for b in order:
            ops = opens_of(b)
            if ops:
                return _karma(ops, last if b == cur else None, count)
        return []
    # sirali: kalınan yerden ileri → sıradaki kaynakların problemleri baştan →
    # en son kalınan kaynağın atlanmış (önceki) bölümleri.
    first = opens_of(cur)
    head, tail = first, []
    if last is not None:
        head = [x for x in first if x.order >= last.order]
        tail = [x for x in first if x.order < last.order]
    seq = head + [x for b in order[1:] for x in opens_of(b)] + tail
    return _fill(seq, count)


def _routine_reason(ctx: _Ctx, slot: WeeklySkeletonSlot, items: list[tuple[_Sec, int]]) -> str:
    first = items[0][0]
    scope = getattr(slot, "routine_scope", None)
    if scope == "problems":
        head = "rutin · problemler " + ("karışık" if slot.routine_mode == "karma" else "sırayla")
        other = next((s for s, _n in items if s.book_id != first.book_id), None)
        if first.book_id != slot.book_id and ctx.by_book.get(slot.book_id):
            src_name = ctx.by_book[slot.book_id][0].book_name
            return f"{head} · {src_name} problemleri bitti → {first.book_name} · {first.label}"
        if other is not None:
            return (f"{head} · {first.book_name} problemleri bu gün bitiyor → "
                    f"{other.book_name} · {other.label}")
        return f"{head} · {first.book_name}" + (
            f" ({first.label} bitince {items[-1][0].label})" if len(items) > 1 else ""
        )
    if first.book_type in DENEME_BOOK_TYPES:
        return "sıradaki deneme (kaldığı yerden sırayla)"
    if slot.routine_mode == "karma":
        return f"rutin · karışık: {len(items)} farklı bölüm"
    if slot.routine_mode == "iki_kaynak":
        other = next((s for s, _n in items if s.book_id != first.book_id), None)
        if other is not None:
            return (f"rutin · konu iki kaynakta: {first.book_name} · {first.label} → "
                    f"{other.book_name} · {other.label}")
        if first.book_id != slot.book_id:
            return f"rutin · konu 2. kaynakta bitiriliyor ({first.book_name} · {first.label})"
        return "rutin · kitapta sırayla; konu bitince 2. kaynakta bitirilir"
    return "rutin · kitapta sırayla" + (
        f" ({first.label} bitince {items[-1][0].label})" if len(items) > 1 else ""
    )


def _routine_chip(ctx: _Ctx, slot: WeeklySkeletonSlot, d: date, fallback_q: int) -> dict | None:
    items = routine_items(
        ctx, book_id=slot.book_id, mode=slot.routine_mode,
        count=slot.default_count or fallback_q, d=d,
        scope=getattr(slot, "routine_scope", None), subject_id=slot.subject_id,
        second_book=getattr(slot, "second_book_id", None),
    )
    if not items:
        return None
    first = items[0][0]
    total = sum(n for _s, n in items)
    chip = _chip(ctx, first, "routine", _routine_reason(ctx, slot, items), total)
    chip["count"] = total
    chip["badges"] = []
    chip["items"] = [
        {"section_id": s.id, "section_label": s.label, "count": n,
         "book_id": s.book_id, "book_name": s.book_name}
        for s, n in items
    ]
    chip["rank"] = 1
    return chip


# ---------------------------------------------------------------- hayaletler


def list_skeletons(db: Session, student_id: int) -> list[WeeklySkeleton]:
    """Öğrencinin dönem iskeletleri, başlangıca göre eskiden yeniye (NULL = en baş)."""
    rows = (
        db.query(WeeklySkeleton)
        .options(joinedload(WeeklySkeleton.slots))
        .filter(WeeklySkeleton.student_id == student_id)
        .all()
    )
    return sorted(rows, key=lambda x: (x.valid_from or date.min, x.id))


def skeleton_for_date(skels: list[WeeklySkeleton], d: date) -> WeeklySkeleton | None:
    """O gün geçerli dönem: valid_from ≤ d olanların en yenisi."""
    cur = None
    for sk_ in skels:
        if (sk_.valid_from or date.min) <= d:
            cur = sk_
    return cur


def valid_until(skels: list[WeeklySkeleton], sk_: WeeklySkeleton) -> date | None:
    """Dönemin son günü = bir sonraki dönemin başlangıcından bir gün önce."""
    nxt = [x for x in skels if (x.valid_from or date.min) > (sk_.valid_from or date.min)]
    if not nxt:
        return None
    return min(x.valid_from for x in nxt) - timedelta(days=1)


def get_skeleton(
    db: Session, student_id: int, at: date | None = None, skeleton_id: int | None = None,
) -> WeeklySkeleton | None:
    """skeleton_id verilirse o dönem (öğrenciye aitse); yoksa `at` (varsayılan
    bugün) günü geçerli dönem. Hiç geçerli yoksa (hepsi ileride başlıyorsa) ilki."""
    skels = list_skeletons(db, student_id)
    if skeleton_id is not None:
        return next((x for x in skels if x.id == skeleton_id), None)
    if not skels:
        return None
    return skeleton_for_date(skels, at or date.today()) or skels[0]


def _is_problems_slot(s: WeeklySkeletonSlot) -> bool:
    return bool(s.is_routine and s.book_id and getattr(s, "routine_scope", None) == "problems")


def _match_by_source(
    slots: list[WeeklySkeletonSlot], items: list[dict],
    problem_secs: set[int] | frozenset = frozenset(),
    problem_books: list[int] | None = None,
) -> tuple[list[WeeklySkeletonSlot], list[dict]]:
    """Kaynaklı satır (kitap/etiket) önce KENDİ kaynağının göreviyle eşleşir —
    aynı derste üç satırdan hangisinin dolu olduğu doğru bilinsin (rutin
    problemler satırı, konu satırının göreviyle 'dolmuş' sayılmasın).

    F2-4: problem rutini satırı ÖNCE eşleşir ve yalnız problem bölümlü görevi
    alır (kaynak sırasındaki herhangi bir soru bankasından — Orijinal bitince
    sıradaki kaynak da onu doldurur). O derste problem rutini varsa kitaplı
    konu satırı yalnız problem-dışı görevle dolar."""
    pool = list(items)
    rest: list[WeeklySkeletonSlot] = []
    has_prob = any(_is_problems_slot(s) for s in slots)

    def only_problems(it: dict) -> bool:
        return bool(it["sections"]) and all(sid in problem_secs for sid, _n in it["sections"])

    ordered = sorted(slots, key=lambda s: not _is_problems_slot(s))
    for s in ordered:
        hit = None
        if _is_problems_slot(s):
            books = set(problem_books or []) | {s.book_id}
            hits = [it for it in pool if only_problems(it) and set(it["book_ids"]) & books]
            # Kaynak değişen gün rutin kitap başına iki görev yazar — ikisi de bu satırın.
            for it in hits[1:]:
                pool.remove(it)
            hit = hits[0] if hits else None
        elif s.book_id:
            hit = next(
                (it for it in pool if s.book_id in it["book_ids"]
                 and not (has_prob and only_problems(it))),
                None,
            )
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
    skels = list_skeletons(db, student.id)
    if not skels or not any(x.slots for x in skels):
        return {"has_skeleton": bool(skels), "days": []}
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

    slot_books = {s.book_id for x in skels for s in x.slots if s.book_id} | {
        s.second_book_id for x in skels for s in x.slots if getattr(s, "second_book_id", None)
    }
    book_names = (
        {int(i): n for i, n in db.query(Book.id, Book.name).filter(Book.id.in_(slot_books))}
        if slot_books else {}
    )
    days = []
    d = start
    while d <= end:
        # F2-2: her gün O GÜN geçerli dönemin iskeletinden (dönem değişen hafta bölünür)
        cur = skeleton_for_date(skels, d)
        wd = [s for s in (cur.slots if cur else []) if s.weekday == d.weekday()]
        by_subj: dict[int, list[WeeklySkeletonSlot]] = defaultdict(list)
        for s in sorted(wd, key=lambda x: (x.position, x.id)):
            by_subj[s.subject_id].append(s)
        ghosts = []
        for subj, slots in by_subj.items():
            if any(s.is_routine for s in slots):
                # Dershane konusu aynı zamanda rutinin konusu: o gün TEK görev (rutin).
                slots = [s for s in slots if not s.is_anchor]
            items = [it for it in ctx.day_items.get(d, []) if subj in it["subjects"]]
            # 1) kaynaklı satırlar kendi kaynağıyla; 2) kalan satırlar kalan
            #    görevlerle periyot kuralına göre (kaynaksız satırlar önce).
            prob_slots = [s for s in slots if _is_problems_slot(s)]
            prob_books = (
                problem_queue(ctx, subject_id=subj, book_id=prob_slots[0].book_id)
                if prob_slots else []
            )
            # O derste problem rutini varsa problem bölümleri konu satırına önerilmez.
            exclude = frozenset(ctx.problem_secs) if prob_slots else frozenset()
            rest, pool = _match_by_source(slots, items, ctx.problem_secs, prob_books)
            rest.sort(key=lambda s: (bool(s.book_id or s.label), s.position, s.id))
            unfilled = [
                s for s in _unfilled_slots(rest, [it["period"] for it in pool])
                if (s.id, d) not in dismissed
            ]
            unfilled.sort(key=lambda s: (s.position, s.id))
            k = 0
            # Aynı gün aynı derste önceki hayaletlerin İLK çipleri: sonraki
            # hayalette sona atılır (aynı kitaptan iki satır aynı konuyu önermesin).
            shown_first: set[int] = set()
            for s in unfilled:
                is_deneme_book = _is_deneme_book(ctx, s.book_id)
                fallback_q = s.default_count or (
                    1 if is_deneme_book
                    else ROUTINE_DEFAULT_COUNT if s.is_routine
                    else _default_quantity(db, ctx, subj)
                )
                chips: list[dict] = []
                if (s.is_routine or is_deneme_book) and s.book_id:
                    rc = _routine_chip(ctx, s, d, fallback_q)
                    chips = [rc] if rc else []
                if not chips and not (s.is_routine and s.label and not s.book_id):
                    chips = build_chips(
                        db, ctx, subject_id=subj, d=d, rotate=0 if s.book_id else k,
                        default_count=s.default_count, prefer_book=s.book_id,
                        exclude=exclude if not s.is_routine else frozenset(),
                        second_book=getattr(s, "second_book_id", None),
                    )
                    if not s.book_id:
                        k += 1
                    if shown_first and len(chips) > 1:
                        chips.sort(key=lambda c: c["section_id"] in shown_first)
                        for i, c in enumerate(chips, start=1):
                            c["rank"] = i
                    if chips:
                        shown_first.add(chips[0]["section_id"])
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
                    "routine_scope": getattr(s, "routine_scope", None),
                    "second_book_id": getattr(s, "second_book_id", None),
                    "second_book_name": (
                        book_names.get(s.second_book_id) if getattr(s, "second_book_id", None) else None
                    ),
                    # 1. kaynakta konu bitti: koç 2. kaynak / sıradaki konu arasında seçer
                    "source_choice": any(c.get("source_choice") for c in chips),
                    "is_anchor": bool(s.is_anchor),
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


# Kitap adı ↔ serbest metin eşleştirmesinde AYIRT EDİCİ sayılmayan kelimeler.
_GENERIC_WORDS = {
    "test", "testi", "testler", "soru", "sorular", "bankası", "bankasi", "kitabı", "kitap",
    "yayınları", "yayinlari", "yayınevi", "tyt", "ayt", "lgs", "paragraf", "paragrafı",
    "karma", "konu", "konulu", "deneme", "denemesi", "tüm", "her", "gün", "sınıf", "ve",
}


def _distinct_words(text: str | None) -> set[str]:
    out = set()
    for w in _norm_label(text).replace("-", " ").replace("·", " ").split():
        w = w.strip(".,:;()'’\"")
        if not w or w in _GENERIC_WORDS:
            continue
        if w.isdigit() and len(w) < 2:
            continue
        out.add(w)
    return out


def _label_points_to_book(label: str | None, book_name: str | None) -> bool:
    """Serbest metinli görev ("Mor Yayınları 3 Test Paragraf") o kitabı mı işaret
    ediyor ("Paraf Konsept TYT Mor Paragraf …")? Ayırt edici bir kelime ortaksa evet.
    '345 Sıfır Risk Paragraf' ile 'Mor Paragraf' ortak yalnız 'paragraf' → hayır."""
    return bool(_distinct_words(label) & _distinct_words(book_name))


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
    Aralık 7 günü aşarsa her hafta günü için İLK tarih esas alınır.

    Geçen haftayı BİREBİR kopyalamaz (2026-09-30): rutin = kaynak + sıra + günlük
    adet. Serbest metinli rutin, adı aynı dersteki kitaplı rutinin kitabını işaret
    ediyorsa o kitaplı rutine dönüşür (o gün aynı rutin zaten varsa tekrar
    eklenmez); işaret etmiyorsa kitapsız kalır (düzenleyici "kaynak seç" uyarır).
    Günlük adet haftanın en sık değeri; ROUTINE_WARN_COUNT'u aşarsa
    ROUTINE_DEFAULT_COUNT (tek bir yoğun gün rutini bozmaz)."""
    from collections import Counter

    end = min(end, start + timedelta(days=MAX_RANGE_DAYS - 1))
    ctx = _load_ctx(db, student=student, coach_id=coach_id, start=start, end=end)

    def src(it: dict) -> tuple:
        if it["book_ids"]:
            # F2-4: yalnız problem bölümlü görev ayrı kaynak sayılır — aynı kitabın
            # konu hattıyla karışmasın (Orijinal Mat: konu satırı + problem rutini).
            if all(sid in ctx.problem_secs for sid, _n in it["sections"]):
                return ("p", it["book_ids"][0])
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
                if key[1][0] in ("b", "p"):
                    karma_votes[key].append(
                        len(it["sections"]) >= 2 and all(n == 1 for _s, n in it["sections"])
                    )
        d += timedelta(days=1)

    def routine_of(key: tuple) -> bool:
        if key[1][0] == "s" or len(days_of[key]) < ROUTINE_MIN_DAYS:
            return False
        if key[1][0] == "b" and not _is_drill_book(ctx, key[1][1]):
            return False
        return True

    def daily_count(key: tuple) -> int | None:
        if not counts[key]:
            return None
        n = counts[key].most_common(1)[0][0]
        return n if 1 <= n <= ROUTINE_WARN_COUNT else ROUTINE_DEFAULT_COUNT

    # Serbest metinli görev → aynı dersteki kitaplı rutinin kitabını işaret ediyorsa
    # ona bağlanır. Etiket rutin sayılmasa bile (ör. yalnız 1 gün elle yazılmış)
    # kitaplı rutinin günü olarak değerlendirilir.
    book_routines: dict[int, list[tuple]] = defaultdict(list)
    for key in days_of:
        if key[1][0] in ("b", "p") and routine_of(key):
            book_routines[key[0]].append(key)
    label_target: dict[tuple, tuple] = {}
    for key in days_of:
        if key[1][0] != "l":
            continue
        for bkey in book_routines.get(key[0], []):
            name = ctx.by_book[bkey[1][1]][0].book_name if ctx.by_book.get(bkey[1][1]) else ""
            if _label_points_to_book(key[1][1], name):
                label_target[key] = bkey
                break

    # Konu satırının 2. kaynağı: aynı derste haftada kullanılan DİĞER soru bankası
    # (problem dışı görevlerden; en sık kullanılan). Yalnız SORU BANKASI.
    bank_use: dict[int, Counter] = defaultdict(Counter)
    for (subj, key), days in days_of.items():
        if key[0] == "b" and key[1] in ctx.bank_books:
            bank_use[subj][key[1]] += len(days)

    def second_for(subj: int, own: int | None) -> int | None:
        for b, _n in bank_use.get(subj, Counter()).most_common():
            if b != own:
                return b
        return None

    seen_weekdays: set[int] = set()
    out: list[dict] = []
    d = start
    while d <= end:
        wd = d.weekday()
        items = ctx.day_items.get(d, [])
        if wd not in seen_weekdays and items:
            seen_weekdays.add(wd)
            rows = []
            day_keys = {(subj, src(it)) for it in items for subj in it["subjects"]}
            for it in items:
                for subj in it["subjects"]:
                    key = (subj, src(it))
                    label = None if it["book_ids"] else it["label"]
                    if key in label_target:
                        # Elle yazılmış etkinlik kitaplı rutinin kitabını işaret ediyor →
                        # o rutinin satırı olur; o gün kitaplı rutin zaten varsa atlanır.
                        key = label_target[key]
                        if key in day_keys:
                            continue
                        day_keys.add(key)
                        label = None
                    # Konu kitabı her gün kullanılsa da RUTİN değil, konu ipliğidir
                    # (Orijinal Mat: Temel Kavramlar → Oran-Orantı → …); rutin
                    # işaretlenirse bilgili konu çiplerini kaybeder. Koç isterse
                    # düzenleyicide elle rutin yapar.
                    routine = routine_of(key)
                    scope = "problems" if (routine and key[1][0] == "p") else None
                    book_id = key[1][1] if key[1][0] in ("b", "p") else (
                        it["book_ids"][0] if it["book_ids"] else None
                    )
                    mode = None
                    if routine and book_id:
                        votes = karma_votes[key]
                        mode = "karma" if votes and sum(votes) * 2 > len(votes) else "sirali"
                    dc = daily_count(key) if routine else None
                    second = (
                        second_for(subj, book_id)
                        if book_id and not routine and book_id in ctx.bank_books else None
                    )
                    rows.append((
                        PERIOD_ORDER.get(it["period"], 3),
                        ctx.subject_names.get(subj, ""), it["task_id"],
                        {"weekday": wd, "period": it["period"], "subject_id": subj,
                         "is_routine": routine, "default_count": dc,
                         "book_id": book_id, "label": None if book_id else label,
                         "routine_mode": mode, "routine_scope": scope,
                         "second_book_id": second},
                    ))
            for pos, (_po, _n, _t, row) in enumerate(sorted(rows, key=lambda r: r[:3])):
                row["position"] = pos
                out.append(row)
        d += timedelta(days=1)
    return out


class PeriodConflict(Exception):
    """Aynı başlangıç tarihli ikinci dönem."""


def _check_start_free(skels: list[WeeklySkeleton], valid_from: date | None, except_id: int | None):
    for x in skels:
        if x.id != except_id and (x.valid_from or date.min) == (valid_from or date.min):
            raise PeriodConflict(
                f"Bu tarihte başlayan bir dönem zaten var ({x.name})."
            )


def create_period(
    db: Session, *, student: User, coach_id: int, valid_from: date, name: str | None = None,
    source: str = "manual", copy_from: WeeklySkeleton | None = None,
) -> WeeklySkeleton:
    """Yeni dönem iskeleti (boş ya da başka bir dönemin kopyası)."""
    _check_start_free(list_skeletons(db, student.id), valid_from, None)
    sk_ = WeeklySkeleton(
        student_id=student.id, coach_id=coach_id, valid_from=valid_from, source=source,
        name=(name or f"{valid_from.strftime('%d.%m.%Y')} dönemi").strip()[:120],
    )
    db.add(sk_)
    db.flush()
    if copy_from is not None:
        for s in copy_from.slots:
            sk_.slots.append(WeeklySkeletonSlot(
                weekday=s.weekday, period=s.period, subject_id=s.subject_id, position=s.position,
                is_routine=s.is_routine, default_count=s.default_count, book_id=s.book_id,
                label=s.label, routine_mode=s.routine_mode, is_anchor=s.is_anchor,
                routine_scope=s.routine_scope, second_book_id=s.second_book_id,
            ))
        db.flush()
    if copy_from is not None and copy_from.day_capacity:
        sk_.day_capacity = copy_from.day_capacity
    return sk_


def update_period(
    db: Session, *, student: User, skeleton: WeeklySkeleton, name: str | None = None,
    valid_from: date | None = None, clear_start: bool = False,
) -> WeeklySkeleton:
    if name is not None and name.strip():
        skeleton.name = name.strip()[:120]
    if valid_from is not None or clear_start:
        new_start = None if clear_start else valid_from
        _check_start_free(list_skeletons(db, student.id), new_start, skeleton.id)
        skeleton.valid_from = new_start
    db.flush()
    return skeleton


def replace_slots(
    db: Session, *, student: User, coach_id: int, slots: list[dict],
    name: str | None = None, source: str = "manual",
    skeleton: WeeklySkeleton | None = None,
) -> WeeklySkeleton:
    """Bir dönemin satırlarını değiştir. skeleton verilmezse BUGÜN geçerli dönem
    (hiç yoksa başlangıçsız ilk dönem açılır)."""
    sk = skeleton or get_skeleton(db, student.id)
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
    # Yüklenmemiş kalıntı satır bırakma (yeni oluşturulan dönemin koleksiyonu
    # DB'den okunmaz; dev SQLite id yeniden kullanımında yetim satırlar gelirdi).
    db.query(WeeklySkeletonSlot).filter(
        WeeklySkeletonSlot.skeleton_id == sk.id
    ).delete(synchronize_session=False)
    for i, s in enumerate(slots):
        sk.slots.append(WeeklySkeletonSlot(
            weekday=int(s["weekday"]), period=s.get("period"),
            subject_id=int(s["subject_id"]), position=int(s.get("position", i)),
            is_routine=bool(s.get("is_routine")), default_count=s.get("default_count"),
            book_id=s.get("book_id"), label=(s.get("label") or None),
            routine_mode=s.get("routine_mode"), is_anchor=bool(s.get("is_anchor")),
            routine_scope=s.get("routine_scope"), second_book_id=s.get("second_book_id"),
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
