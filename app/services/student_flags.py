"""Öğrenci bayrak motoru — koç uyarı sisteminin TEK kaynağı (2026-09-29 revizyonu).

Koç: "uyarılar çoğu zaman bizi yanıltıyor". Boran: programı 26 Eyl'de bitmiş,
son programında 4 gün üst üste hiçbir şey yapmamış — ekranda kırmızı yoktu, beş
sarı ders kartı vardı. Kök neden değil belirtiler gösteriliyordu.

Katmanlar (üstten alta; üst katmandaki kırmızı alttaki belirtileri EK SİNYALE indirir):
  A. Program durumu (aksiyon koçta)      program_none · program_ending · draft_only · subjects_unprogrammed
  B. Uygulama / katılım (öğrenci)         empty_streak · completion_low · completion_drop · no_login · today_no_tick
  C. Ders dengesi                         subject_avoid_{id} · subject_stale_{id} · subject_untouched_{id}
  D. Deneme ve akademik sonuç             deneme_skipped (koça özel) · exam_drop
  E. Sınav hedefi                         projection_* (sınava yetişme)
  F. Veri güvenilirliği (bilgi, koça özel) bulk_marking · dy_missing
  G. İyi gidenler                         good_*

Pencereler: "son 7 gün" = son 7 BİTMİŞ gün (bugün hariç). Bugün yalnız
kişisel başlama saatinden sonra değerlendirilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Book, Task, TaskBookItem, TaskStatus, User
from app.models.exam_result import ExamResult
from app.services import gorev_stats

LEVEL_RANK = {"red": 0, "amber": 1, "green": 2}
LAYER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}

# Eşikler (koç onaylı, 2026-09-29)
EMPTY_STREAK_AMBER = 2
EMPTY_STREAK_RED = 3
COMPLETION_AMBER = 70
COMPLETION_RED = 40
COMPLETION_MIN_TASKS = 3
DROP_POINTS = 30
NO_LOGIN_AMBER = 3
NO_LOGIN_RED = 5
AVOID_MIN_TASKS = 4
AVOID_GAP_POINTS = 30
BULK_MIN_TASKS = 5
BULK_MAX_MINUTES = 10
BULK_MIN_DAYS = 3
GOOD_STREAK_DAYS = 5

# Veliye gitmeyen bayraklar (koç kararı: toplu işaretleme + deneme aksatma koça özel)
COACH_ONLY_PREFIXES = ("bulk_marking", "dy_missing", "deneme_skipped")


@dataclass
class FlagReport:
    primary: list = field(default_factory=list)     # ana kartlar (kırmızı/sarı)
    secondary: list = field(default_factory=list)   # ek sinyaller + bilgi
    good: list = field(default_factory=list)        # iyi gidenler
    headline: str = ""
    level: str = "green"
    parent_level: str = "green"


def _aw(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _tick(t: Task) -> bool:
    return t.status == TaskStatus.COMPLETED or any(
        (it.completed_count or 0) > 0 for it in t.book_items)


def _subject_of(t: Task):
    for it in t.book_items:
        if it.book is not None and it.book.subject is not None:
            return it.book.subject
    return None


def evaluate_flags(db: Session, student: User, today: date, projection=None,
                   *, include_goal: bool = True) -> FlagReport:
    from app.services.analytics import Warning, _d, legacy_warnings

    rep = FlagReport()
    if getattr(student, "is_paused", False) or not student.is_active:
        rep.headline = "Takip duraklatıldı" if getattr(student, "is_paused", False) else ""
        return rep

    now = datetime.now(timezone.utc)
    created = _aw(student.created_at)
    age = max(0, (now - created).days) if created else None

    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject))
        .filter(Task.student_id == student.id, Task.date >= today - timedelta(days=28))
        .all()
    )
    pub = [t for t in tasks if not t.is_draft]
    past = [t for t in pub if t.date < today]
    today_pub = [t for t in pub if t.date == today]
    after = [t for t in pub if t.date > today]
    drafts_ahead = [t for t in tasks if t.is_draft and t.date >= today]
    flags: list = []

    def add(layer, level, code, title, detail, evidence, **kw):
        w = Warning(level=level, code=code, title=title, detail=detail, evidence=evidence)
        w.layer = layer
        w.coach_only = code.startswith(COACH_ONLY_PREFIXES)
        flags.append(w)
        return w

    # Eski üreticiden yalnız hazır parçalar; sınav tahmini artık exam_readiness'ta.
    legacy = legacy_warnings(db, student, today, None)
    legacy_by = {w.code: w for w in legacy}

    # ---------------------------------------------------------------- A. Program
    last_prog = max((t.date for t in past), default=None)
    if last_prog is None:
        last_prog = (db.query(func.max(Task.date))
                     .filter(Task.student_id == student.id, Task.is_draft.is_(False),
                             Task.date < today).scalar())
    if not today_pub and not after:
        if drafts_ahead:
            first = min(t.date for t in drafts_ahead)
            add("A", "amber", "draft_only", "Program taslakta — öğrenci göremiyor",
                f"{len(drafts_ahead)} görev hazır ama yayınlanmamış; öğrenci programını göremiyor.",
                [("Taslak görev", f"{len(drafts_ahead)} görev · ilk gün {_d(first)}"),
                 ("Yayınlanmış görev (bugün ve sonrası)", "0")])
        elif age is None or age >= 3:
            if last_prog:
                gap = (today - last_prog).days
                add("A", "red", "program_none", "Programı yok",
                    f"Son programı {_d(last_prog)} tarihinde bitti; {gap} gündür görevi yok.",
                    [("Son görev günü", _d(last_prog)),
                     ("Bugün ve sonrası", "yayınlanmış görev yok"),
                     ("Taslak", "yok")])
            else:
                add("A", "red", "program_none", "Programı yok",
                    "Bu öğrenciye henüz hiç program verilmemiş.",
                    [("Yayınlanmış görev", "hiç yok")])
    elif today_pub and not after:
        add("A", "amber", "program_ending", "Program bugün bitiyor",
            "Yarından sonrası için görev yok; yeni haftanın programını hazırla.",
            [("Son görev günü", _d(today)), ("Yarın ve sonrası", "yayınlanmış görev yok")])
    if "subjects_unprogrammed" in legacy_by:
        w = legacy_by["subjects_unprogrammed"]
        add("A", "green", w.code, w.title, w.detail, w.evidence)

    # ---------------------------------------------------------------- B. Katılım
    by_day: dict[date, list] = {}
    for t in past:
        by_day.setdefault(t.date, []).append(t)
    # Başlangıç muafiyeti: hesabı 3 günden genç öğrenci katılım bayrağı almaz;
    # hesap açılışından önceki günler (geriye tarihli görevler) sayılmaz.
    grace = age is not None and age < 3
    created_day = (created + timedelta(hours=3)).date() if created else None
    today_ticked = any(_tick(t) for t in today_pub)
    streak: list[date] = []
    if not today_ticked:
        for d in sorted(by_day, reverse=True):
            if d < today - timedelta(days=14) or (created_day and d < created_day):
                break
            if any(_tick(t) for t in by_day[d]):
                break
            streak.append(d)
    last_seen = _aw(getattr(student, "last_active_at", None))
    if len(streak) >= EMPTY_STREAK_AMBER and not grace:
        n_tasks = sum(len(by_day[d]) for d in streak)
        lo, hi = min(streak), max(streak)
        ev = [("Günler", f"{_d(lo)} – {_d(hi)} ({len(streak)} programlı gün)"),
              ("Verilen görev", f"{n_tasks} görev · 0 tamamlandı")]
        if last_seen is not None:
            ls_day = (last_seen + timedelta(hours=3)).date()
            opened = lo <= ls_day <= hi
            ev.append(("Son görülme", f"{_d(ls_day)}" + (" — uygulamayı açtı ama işaretleme yapmadı" if opened else "")))
        add("B", "red" if len(streak) >= EMPTY_STREAK_RED else "amber", "empty_streak",
            f"Son {len(streak)} programlı günde hiç görev yapmadı",
            f"{_d(lo)} – {_d(hi)} arasında verilen {n_tasks} görevin hiçbiri yapılmadı.", ev)

    # "Son 7 gün" TEK TANIM (pano/liste/Durum Özeti ile aynı): bugün dahil son 7 gün,
    # bugünün henüz yapılmamış görevleri sayılmaz (gorev_stats.settled_tasks).
    cur = gorev_stats.settled_tasks(
        [t for t in pub if today - timedelta(days=6) <= t.date <= today], today)
    prev = [t for t in past if today - timedelta(days=13) <= t.date <= today - timedelta(days=7)]
    cs, ps = gorev_stats.summarize(cur), gorev_stats.summarize(prev)
    if cs.gorev_total >= COMPLETION_MIN_TASKS and cs.gorev_pct < COMPLETION_AMBER and not grace:
        add("B", "red" if cs.gorev_pct < COMPLETION_RED else "amber", "completion_low",
            f"Son 7 günde tamamlama %{cs.gorev_pct}",
            f"Verilen {cs.gorev_total} görevin {cs.gorev_done} tanesi tamamlandı.",
            [("Dönem", f"{_d(today - timedelta(days=6))} – {_d(today)} (bugünün yapılmamış görevleri sayılmaz)"),
             ("Görev", f"{cs.gorev_done}/{cs.gorev_total} (%{cs.gorev_pct})"),
             ("Test", f"{cs.test_completed}/{cs.test_planned} çözüldü"),
             ("Eşik", f"%{COMPLETION_AMBER} altı sarı · %{COMPLETION_RED} altı kırmızı")])
    if (not grace and cs.gorev_total >= COMPLETION_MIN_TASKS and ps.gorev_total >= COMPLETION_MIN_TASKS
            and ps.gorev_pct - cs.gorev_pct >= DROP_POINTS):
        add("B", "amber", "completion_drop", f"Tamamlama %{ps.gorev_pct} → %{cs.gorev_pct} düştü",
            f"Önceki 7 güne göre {ps.gorev_pct - cs.gorev_pct} puan düşüş.",
            [("Önceki 7 gün", f"{ps.gorev_done}/{ps.gorev_total} görev (%{ps.gorev_pct})"),
             ("Son 7 gün", f"{cs.gorev_done}/{cs.gorev_total} görev (%{cs.gorev_pct})")])

    if age is None or age >= NO_LOGIN_AMBER:
        seen_days = (now - last_seen).days if last_seen else age
        if seen_days is not None and seen_days >= NO_LOGIN_AMBER:
            add("B", "red" if seen_days >= NO_LOGIN_RED else "amber", "no_login",
                f"{seen_days} gündür uygulamayı açmadı",
                "Web ya da mobil uygulamada hiç görülmedi.",
                [("Son görülme", _d((last_seen + timedelta(hours=3)).date()) if last_seen else "hiç")])
    if "today_no_tick" in legacy_by:
        w = legacy_by["today_no_tick"]
        add("B", w.level, w.code, w.title, w.detail, w.evidence)

    # ---------------------------------------------------------------- C. Ders dengesi
    tests28 = [t for t in past if gorev_stats.classify_gorev(t) == "test"]
    per: dict[int, list] = {}
    names: dict[int, str] = {}
    for t in tests28:
        sub = _subject_of(t)
        if sub is None:
            continue
        per.setdefault(sub.id, []).append(t)
        names[sub.id] = sub.name
    all_done = sum(1 for t in tests28 if gorev_stats.gorev_done(t))
    overall = round(100 * all_done / len(tests28)) if tests28 else 0
    avoided: set[int] = set()
    for sid_, ts in per.items():
        if len(ts) < AVOID_MIN_TASKS:
            continue
        done = sum(1 for t in ts if gorev_stats.gorev_done(t))
        pct = round(100 * done / len(ts))
        others = [t for t in tests28 if t not in ts]
        o_pct = round(100 * sum(1 for t in others if gorev_stats.gorev_done(t)) / len(others)) if others else overall
        if pct == 0 or o_pct - pct >= AVOID_GAP_POINTS:
            avoided.add(sid_)
            _w = add("C", "red" if pct == 0 else "amber", f"subject_avoid_{sid_}",
                f"{names[sid_]} dersinden kaçınıyor",
                f"Son 4 haftada bu dersteki {len(ts)} görevin {done} tanesi yapıldı (%{pct}); "
                f"diğer derslerde %{o_pct}.",
                [("Dönem", f"{_d(today - timedelta(days=28))} – {_d(today - timedelta(days=1))}"),
                 (names[sid_], f"{done}/{len(ts)} görev (%{pct})"),
                 ("Diğer dersler", f"%{o_pct}"),
                 ("Kural", f"en az {AVOID_MIN_TASKS} görev · {AVOID_GAP_POINTS}+ puan geride ya da %0")])
            _w.others_pct = o_pct
    for w in legacy:
        if w.code.startswith(("subject_stale_", "subject_untouched_")):
            if int(w.code.rsplit("_", 1)[1]) in avoided:
                continue
            add("C", w.level, w.code, w.title, w.detail, w.evidence)

    # ---------------------------------------------------------------- D. Deneme
    den = [t for t in cur if gorev_stats.classify_gorev(t) in ("deneme", "tam_deneme")]
    if den:
        dd = sum(1 for t in den if gorev_stats.gorev_done(t))
        if dd < len(den):
            add("D", "red" if (dd == 0 and len(den) >= 2) else "amber", "deneme_skipped",
                "Deneme görevlerini aksatıyor",
                f"Son 7 günde programdaki {len(den)} deneme görevinin {len(den) - dd} tanesi yapılmadı.",
                [("Deneme görevi", f"{dd}/{len(den)} yapıldı"),
                 ("Yapılmayanlar", ", ".join(f"{_d(t.date)} {t.title}" for t in den if not gorev_stats.gorev_done(t))[:300]),
                 ("Görünürlük", "yalnız koç — veliye gitmez")])
    exams = (db.query(ExamResult).filter(ExamResult.student_id == student.id)
             .order_by(ExamResult.exam_date.desc(), ExamResult.created_at.desc()).limit(12).all())
    if exams and exams[0].exam_date and (today - exams[0].exam_date).days <= 30:
        from app.services import exam_scope
        _k = exam_scope.series_key(exams[0])
        same = [e for e in exams if exam_scope.series_key(e) == _k]
        if len(same) >= 2 and same[1].net is not None and same[0].net is not None:
            diff = float(same[0].net) - float(same[1].net)
            thr = max(2.0, abs(float(same[1].net)) * 0.1)
            if diff <= -thr:
                add("D", "amber", "exam_drop", "Deneme netinde düşüş",
                    f"Son denemede net {float(same[1].net):.2f} → {float(same[0].net):.2f}.",
                    [("Önceki", f"{_d(same[1].exam_date)} · {same[1].title} · {float(same[1].net):.2f}"),
                     ("Son", f"{_d(same[0].exam_date)} · {same[0].title} · {float(same[0].net):.2f}"),
                     ("Kıyas", "aynı sınav türü ve kapsamı (genel/branş) içinde")])
            elif diff >= thr:
                add("G", "green", "good_net_up", "Deneme neti yükseliyor",
                    f"Net {float(same[1].net):.2f} → {float(same[0].net):.2f} (+{diff:.2f}).",
                    [("Önceki", f"{_d(same[1].exam_date)} · {float(same[1].net):.2f}"),
                     ("Son", f"{_d(same[0].exam_date)} · {float(same[0].net):.2f}")])

    # ---------------------------------------------------------------- E. Sınav hedefi
    def _dy(d):
        """Yıllı tarih — sınav tahmininde bitiş ile hedef farklı yıllarda olabilir."""
        return f"{_d(d)} {d.year}" if d else "—"

    if include_goal:
        from app.services.exam_readiness import compute_readiness
        rd = compute_readiness(db, student, today)
        days_to_exam = (rd.exam_date - today).days if rd.exam_date else None
        c_subjects = {int(w.code.rsplit("_", 1)[1]) for w in flags
                      if w.code.startswith(("subject_avoid_", "subject_stale_", "subject_untouched_"))}
        for sr in rd.subjects:
            src = " · ".join(f"{b['name']} (kalan {b['remaining']})" for b in sr.active_books)
            base_ev = [("Hedef kaynak", sr.goal), ("Aktif kaynak", src or "—")]
            if sr.dropped_books:
                base_ev.append(("Bırakılan (21+ gündür görev yok)", ", ".join(sr.dropped_books)))
            if sr.finished_books:
                base_ev.append(("Biten", ", ".join(sr.finished_books)))
            base_ev += [
                ("Kalan", f"{sr.remaining_tests} test" + (f" · {sr.remaining_topics} konu" if sr.remaining_topics else "")),
                ("Hız", f"{sr.pace:.1f} test/gün (son {sr.pace_days} günde {sr.solved_window} test)"),
                ("Hedef", f"{_dy(sr.target_date)} (sınav {_dy(rd.exam_date)} · son 6 hafta deneme/tekrar)"),
            ]
            if sr.status == "late":
                need = sr.remaining_tests / max(1, (sr.target_date - today).days)
                add("E", "red" if (days_to_exam is not None and days_to_exam <= 60) else "amber",
                    f"exam_behind_{sr.subject_id}", f"{sr.subject_name} sınav takvimine yetişmiyor",
                    f"Bu hızla aktif kaynaklar {_dy(sr.finish_date)} tarihinde biter; hedef {_dy(sr.target_date)} "
                    f"— {sr.days_late} gün geride. Gereken: günde {need:.1f} test.",
                    base_ev + [("Tahmini bitiş", _dy(sr.finish_date)), ("Gereken hız", f"{need:.1f} test/gün")])
            elif sr.status == "stalled" and sr.subject_id not in c_subjects:
                add("E", "amber", f"exam_stalled_{sr.subject_id}", f"{sr.subject_name} ilerlemiyor",
                    f"Aktif kaynaklarda {sr.remaining_tests} test kaldı ama son {sr.pace_days} günde çözüm yok.",
                    base_ev)

    # ---------------------------------------------------------------- F. Veri güvenilirliği
    recent = [t for t in past if t.date >= today - timedelta(days=14)]
    stamps: dict[date, list] = {}
    for t in recent:
        if t.completed_at is not None:
            stamps.setdefault(t.date, []).append(_aw(t.completed_at))
    bulk_days = [d for d, ss in stamps.items()
                 if len(ss) >= BULK_MIN_TASKS and (max(ss) - min(ss)) < timedelta(minutes=BULK_MAX_MINUTES)]
    if len(bulk_days) >= BULK_MIN_DAYS:
        add("F", "green", "bulk_marking", "Görevleri topluca işaretliyor",
            f"Son 14 günün {len(bulk_days)} gününde o günün tüm görevleri birkaç dakika içinde işaretlendi; "
            "işaretlemeler gün içinde değil, sonradan yapılıyor olabilir.",
            [("Günler", ", ".join(_d(d) for d in sorted(bulk_days))),
             ("Kural", f"günde {BULK_MIN_TASKS}+ görev {BULK_MAX_MINUTES} dk içinde"),
             ("Görünürlük", "yalnız koç — veliye gitmez")])
    items = [it for t in recent if gorev_stats.classify_gorev(t) == "test"
             for it in t.book_items if (it.completed_count or 0) > 0]
    if len(items) >= 5:
        miss = sum(1 for it in items if not (it.correct_count or 0) and not (it.wrong_count or 0))
        if miss / len(items) >= 0.7:
            add("F", "green", "dy_missing", "Doğru/yanlış girilmiyor",
                f"Son 14 günde çözülen {len(items)} test kaleminin {miss} tanesinde D/Y boş; doğruluk ölçülemiyor.",
                [("D/Y boş", f"{miss}/{len(items)} kalem")])

    # ---------------------------------------------------------------- G. İyi gidenler
    good_streak = 0
    for d in sorted(by_day, reverse=True):
        if all(gorev_stats.gorev_done(t) for t in by_day[d]):
            good_streak += 1
        else:
            break
    if good_streak >= GOOD_STREAK_DAYS:
        add("G", "green", "good_streak", f"{good_streak} programlı gündür görevlerinin tamamını yaptı",
            "Arka arkaya her programlı gün eksiksiz.", [("Seri", f"{good_streak} gün")])
    if cs.gorev_total >= 5 and cs.gorev_pct >= 90:
        add("G", "green", "good_completion", f"Son 7 günde tamamlama %{cs.gorev_pct}",
            f"{cs.gorev_done}/{cs.gorev_total} görev · {cs.test_completed}/{cs.test_planned} test.",
            [("Görev", f"{cs.gorev_done}/{cs.gorev_total}")])
    if den and all(gorev_stats.gorev_done(t) for t in den):
        add("G", "green", "good_deneme", "Programdaki denemelerin hepsini çözdü",
            f"Son 7 günde {len(den)} deneme görevi eksiksiz.", [("Deneme", f"{len(den)}/{len(den)}")])

    # ---------------------------------------------------------------- Hiyerarşi
    reds_ab = [w for w in flags if w.layer in ("A", "B") and w.level == "red"]
    codes = {w.code for w in flags}
    for w in flags:
        if w.layer == "G":
            rep.good.append(w)
            continue
        demote = w.level == "green"
        if w.code == "completion_low" and "empty_streak" in codes and \
                next(x for x in flags if x.code == "empty_streak").level == "red":
            demote = True
        if w.code == "completion_drop" and any(x.code in ("empty_streak", "completion_low") for x in flags):
            demote = True
        if w.code == "no_login" and "empty_streak" in codes:
            demote = True
        if reds_ab and w.code.startswith(("subject_stale_", "subject_untouched_")):
            demote = True
        if reds_ab and w.code == "deneme_skipped":
            demote = True
        # Öğrenci programı bırakmışken sınav takvimi kartları aynı olgunun sonucu.
        if reds_ab and w.layer == "E":
            demote = True
        # Kaçınma, diğer derslerde de iş yapılmıyorsa anlamsız (genel bırakma —
        # B katmanı zaten söylüyor). Ölçüt DİĞER derslerin oranı: genel oran,
        # kaçınılan dersin kendisiyle aşağı çekilir (Taha: Kimya 0/14).
        if w.code.startswith("subject_avoid_") and getattr(w, "others_pct", 100) < COMPLETION_RED:
            demote = True
        (rep.secondary if demote else rep.primary).append(w)

    key = lambda w: (LEVEL_RANK.get(w.level, 9), LAYER_ORDER.get(w.layer, 9))
    rep.primary.sort(key=key)
    rep.secondary.sort(key=key)
    if rep.primary:
        rep.level = rep.primary[0].level
        parent = [w for w in rep.primary if not w.coach_only]
        rep.parent_level = parent[0].level if parent else "green"
        rep.headline = " · ".join(w.title for w in rep.primary[:2])
    else:
        rep.headline = rep.good[0].title if rep.good else "Program yolunda"
    return rep
