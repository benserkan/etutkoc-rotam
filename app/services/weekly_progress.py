"""Öğrenci detay sayfası — haftalık ilerleme ve öğrencinin kendi normaline göre kıyas (TEK MERKEZ).

Salt okuma, yapay zekâ yok, kredi yok. Kararlar (kullanıcı, 2026-10-20):
  · Hafta = öğrencinin PROGRAM haftası (WeeklyProgram; Perşembe–Çarşamba olabilir).
  · Kıyas, geçmiş haftaların AYNI GÜNÜNE KADAR yapılır; bugün sürdüğü için sayılmaz.
  · "Genelde" (normal aralık) = taban haftaların çeyrekler arası bandı — ortalama DEĞİL.
    Taban: bu sınıf dönemindeki geçmiş program haftaları; öğrencinin ilk 2 alışma haftası
    ve 4 günden kısa haftalar girmez; 4 haftadan az taban → durum yok ("veri az").
  · Normalin altı = dikkat; geçmiş haftaların en kötüsünün de altı = kritik.
  · 3 hafta üst üste kötüleşme = EĞİLİM bilgisi (alarm değil).
  · Önlemler ölçüme dayanır; düğmeler mevcut sayfalara gider (hatırlatma sistemi ayrı iş).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from statistics import median

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Book, Task, TaskBookItem, User, WeeklyProgram
from app.models.task import TaskStatus
from app.services import gorev_stats

MIN_BASELINE = 4
MIN_WEEK_DAYS = 4
ONBOARDING_WEEKS = 2
CHART_WEEKS = 8
TREND_RUN = 3
ONTIME_GRACE_H = 5        # 00:00–05:00 arası atılan tik önceki günün sayılır
NIGHT_START_H, NIGHT_END_H = 0, 5
AVOID_GAP = 30            # ders, diğerlerinin bu kadar puan gerisindeyse "kaçınılan"
AVOID_MIN_TASKS = 4
TR = timedelta(hours=3)

DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
MONTH_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _d(d: date) -> str:
    return f"{d.day} {MONTH_SHORT[d.month - 1]}"


def _range_label(a: date, b: date) -> str:
    if a.month == b.month:
        return f"{a.day}–{b.day} {MONTH_SHORT[b.month - 1]}"
    return f"{_d(a)}–{_d(b)}"


def _tr(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt + TR


def _quartiles(vals: list[float]) -> tuple[float, float]:
    s = sorted(vals)
    n = len(s)
    return float(median(s[: n // 2])), float(median(s[(n + 1) // 2:]))


def _num(v: float) -> str:
    """12.5 → '12,5'; 61.0 → '61'."""
    return (f"{v:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


def _pct(a: float, b: float) -> float | None:
    return round(100.0 * a / b, 1) if b else None


# ---------------------------------------------------------------- haftalar

@dataclass
class Week:
    program_id: int  # program id; takvim/dönem haftasında negatif anahtar
    start: date
    end: date
    kind: str = "program"  # program | takvim (programsız görev günleri) | donem (havuz)
    cut: bool = False  # mod geçişiyle kırpılmış program haftası (eğilim dizisine girmez)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def label(self) -> str:
        return _range_label(self.start, self.end)


def _program_weeks(db: Session, student_id: int) -> list[Week]:
    """Program haftaları (çakışan programlardan ilk açılan kalır), başlangıca göre."""
    progs = (db.query(WeeklyProgram).filter(WeeklyProgram.student_id == student_id)
             .order_by(WeeklyProgram.start_date.asc(), WeeklyProgram.created_at.asc()).all())
    out: list[Week] = []
    for p in progs:
        if out and p.start_date <= out[-1].end:
            # Çakışma: daha sonra açılan program bugünü taşıyorsa onun yerine geçer.
            if p.end_date > out[-1].end and p.start_date > out[-1].start:
                out[-1] = Week(out[-1].program_id, out[-1].start, p.start_date - timedelta(days=1))
                if out[-1].end < out[-1].start:
                    out.pop()
            else:
                continue
        out.append(Week(p.id, p.start_date, p.end_date))
    return out


def _calendar_fill(db: Session, student_id: int, weeks: list[Week]) -> list[Week]:
    """Programa düşmeyen görev günleri → Pzt–Paz takvim haftası (program haftasıyla
    çakışan kısım kırpılır). Koç program açmadan görev eklediyse sayfa boş kalmasın."""
    dates = {d for (d,) in db.query(Task.date).filter(
        Task.student_id == student_id, Task.is_draft.is_(False)).distinct()}
    uncovered = sorted(d for d in dates if not any(w.start <= d <= w.end for w in weeks))
    added: dict[date, Week] = {}
    for d in uncovered:
        mon = d - timedelta(days=d.weekday())
        if mon in added:
            continue
        lo, hi = mon, mon + timedelta(days=6)
        for w in weeks:  # komşu program haftalarına göre kırp (görev gününü kapsayan parça)
            if w.end < d and w.end >= lo:
                lo = w.end + timedelta(days=1)
            if w.start > d and w.start <= hi:
                hi = w.start - timedelta(days=1)
        added[mon] = Week(-(mon.toordinal()), lo, hi, kind="takvim")
    return sorted(weeks + list(added.values()), key=lambda w: w.start)


def _period_weeks(db: Session, student_id: int, today: date) -> list[Week]:
    """Havuz öğrencisi: her çalışma dönemi bir 'hafta' (seans günü yeni döneme ait)."""
    from app.models.pool import StudyPeriod
    periods = (db.query(StudyPeriod).filter(StudyPeriod.student_id == student_id)
               .order_by(StudyPeriod.opened_on.asc(), StudyPeriod.id.asc()).all())
    out: list[Week] = []
    for i, p in enumerate(periods):
        if p.closed_on is not None:
            # Seans günü yalnız o gün yeni dönem açıldıysa yeni döneme aittir; açılmadıysa
            # (gün güne geçiş, ara, görüşmesiz kapanış) kapanış günü bu dönemde kalır.
            nxt = periods[i + 1].opened_on if i + 1 < len(periods) else None
            end = p.closed_on - timedelta(days=1) if nxt == p.closed_on else p.closed_on
        else:
            exp = (p.expected_next_on - timedelta(days=1)) if p.expected_next_on else p.opened_on
            end = max(exp, today)
        if i + 1 < len(periods) and periods[i + 1].opened_on <= end:
            end = periods[i + 1].opened_on - timedelta(days=1)
        if end < p.opened_on:
            continue
        out.append(Week(-1_000_000 - p.id, p.opened_on, end, kind="donem"))
    return out


def _merge_program_and_period_weeks(programs: list[Week], periods: list[Week]) -> list[Week]:
    """Havuz dönemleri önceliklidir; program haftası dönemle çakışan kısımdan kırpılır.

    Mod geçişinde (gün gün → havuz ya da tersi) yarıda kalan program haftası kaybolmaz:
    dönemden önceki (ya da sonraki) parçası kendi haftası olarak kalır ve `cut` işaretlenir.
    """
    out = list(periods)
    for w in programs:
        segs = [(w.start, w.end)]
        for p in periods:
            nxt = []
            for a, b in segs:
                if p.end < a or p.start > b:
                    nxt.append((a, b))
                    continue
                if a < p.start:
                    nxt.append((a, p.start - timedelta(days=1)))
                if b > p.end:
                    nxt.append((p.end + timedelta(days=1), b))
            segs = nxt
        for a, b in segs:
            cut = (a, b) != (w.start, w.end)
            out.append(Week(w.program_id if (a, b) == segs[0] else -(a.toordinal()) - 2_000_000,
                            a, b, kind="program", cut=cut))
    return sorted(out, key=lambda x: x.start)


def _weeks(db: Session, student: User, today: date) -> list[Week]:
    # Gün gün program haftaları + havuz dönemleri birlikte: mod değişse de geçmiş haftalar
    # kendi yapısıyla görünür (havuza geçen öğrencinin eski program haftaları takvime dağılmaz).
    periods = _period_weeks(db, student.id, today)
    programs = _program_weeks(db, student.id)
    weeks = _merge_program_and_period_weeks(programs, periods) if periods else programs
    return _calendar_fill(db, student.id, weeks)


# ---------------------------------------------------------------- ölçüler

def _is_done(t: Task) -> bool:
    return gorev_stats.gorev_done(t)


def _ontime(t: Task) -> bool | None:
    if not _is_done(t):
        return None
    ct = _tr(t.completed_at)
    if ct is None:
        return None
    return ct <= datetime.combine(t.date + timedelta(days=1), time(ONTIME_GRACE_H))


def _metrics(tasks: list[Task], dates: list[date]) -> dict:
    s = gorev_stats.summarize(tasks)
    done = [t for t in tasks if _is_done(t)]
    ont = [o for o in (_ontime(t) for t in tasks) if o is not None]
    night = [t for t in done if t.completed_at and NIGHT_START_H <= _tr(t.completed_at).hour < NIGHT_END_H]
    timed = [t for t in done if t.completed_at]
    c = w = b = 0
    tests_done = tests_with_result = 0
    for t in tasks:
        for it in t.book_items:
            if not gorev_stats.item_is_test(it):
                continue
            if int(it.completed_count or 0) > 0:
                tests_done += 1
                if it.correct_count is not None or it.wrong_count is not None:
                    tests_with_result += 1
            c += int(it.correct_count or 0)
            w += int(it.wrong_count or 0)
            b += int(it.blank_count or 0)
    by_day: dict[date, list[Task]] = defaultdict(list)
    for t in tasks:
        by_day[t.date].append(t)
    empty = 0
    for d in dates:
        ts = by_day.get(d) or []
        if ts and not any(_is_done(t) or any(int(i.completed_count or 0) > 0 for i in t.book_items) for t in ts):
            empty += 1
    return {
        "gorev_done": s.gorev_done, "gorev_total": s.gorev_total,
        "gorev_pct": _pct(s.gorev_done, s.gorev_total),
        "test_done": s.test_completed, "test_planned": s.test_planned,
        "ontime_pct": _pct(sum(1 for o in ont if o), len(ont)),
        "night_pct": _pct(len(night), len(timed)),
        "accuracy_pct": _pct(c, c + w),
        "result_coverage": (tests_with_result, tests_done),
        "blank_pct": _pct(b, c + w + b),
        "empty_days": empty,
        "subjects": [(sg.subject_name, sg.gorev_done, sg.gorev_total) for sg in s.subjects],
    }


# ---------------------------------------------------------------- tanımlar

# key, ad, açıklama, grup, yön (+1 yüksek iyi, -1 düşük iyi, 0 nötr), birim
METRICS = [
    ("test_done", "Çözülen test", "Soru bankası ve konulu kaynaksız testler (deneme hariç), bugüne kadar.",
     "gelisim", 1, "test"),
    ("accuracy_pct", "Doğruluk", "Doğru ÷ (doğru + yanlış), sonuç girilen testlerden.", "gelisim", 1, "%"),
    ("new_topics", "Yeni işlenen konu", "Müfredatta bu hafta ilk kez çalışılan konu sayısı.", "ilerleme", 1, "konu"),
    ("load", "Verilen yük", "Bu hafta öğrenciye verdiğin görev sayısı. Uyum düştüyse sebep yük mü, buradan anlaşılır.",
     "ilerleme", 0, "görev"),
    ("gorev_pct", "Görev uyumu", "Yapılan ÷ verilen görev, bugüne kadarki günler.", "risk", 1, "%"),
    ("ontime_pct", "Gününde tamamlama", "Görevini kendi gününde işaretleme oranı; sonradan toplu işaretleme bunu düşürür.",
     "risk", 1, "%"),
    ("night_pct", "Gece çalışma payı", "Gece 00:00–05:00 arası tamamlanan görevlerin payı (uyku ve yük riski).",
     "risk", -1, "%"),
    ("empty_days", "Boş gün", "Programlı olduğu hâlde hiç görev yapılmayan gün.", "risk", -1, "gün"),
    ("blank_pct", "Boş bırakılan soru", "Testlerde boş bırakılan soru oranı; konuya giremediğini gösterir.",
     "risk", -1, "%"),
]

GROUPS = [
    ("gelisim", "Gelişim", "Öğrenme artıyor mu? Çözülen iş, doğruluk ve deneme sonucu."),
    ("ilerleme", "İlerleme", "Müfredatta ilerliyor mu, koçun verdiği yük ne düzeyde?"),
    ("risk", "Risk", "Programdan kopma, kaçınma ve düzensiz çalışma işaretleri."),
]


def _fmt(v: float | None, unit: str) -> str:
    if v is None:
        return "—"
    if unit == "%":
        return f"%{round(v)}"
    return f"{round(v)} {unit}"


def _status(cur, base: list[float], direction: int) -> tuple[str, float | None, float | None]:
    """(status, lo, hi). status: insufficient|normal|below|critical|above|high|low."""
    if cur is None or len(base) < MIN_BASELINE:
        return "insufficient", None, None
    if max(base + [cur]) == 0:      # hiç kayıt yok (ör. test görevi verilmeyen öğrenci)
        return "insufficient", None, None
    lo, hi = _quartiles(base)
    if direction == 0:
        return ("high" if cur > hi else "low" if cur < lo else "normal"), lo, hi
    worse_than_all = cur < min(base) if direction > 0 else cur > max(base)
    worse = cur < lo if direction > 0 else cur > hi
    better = cur > hi if direction > 0 else cur < lo
    if worse_than_all:
        return "critical", lo, hi
    if worse:
        return "below", lo, hi
    if better:
        return "above", lo, hi
    return "normal", lo, hi


def _decline_run(series: list[float], direction: int) -> int:
    run = 0
    for i in range(len(series) - 1, 0, -1):
        a, b = series[i - 1], series[i]
        if (b < a if direction > 0 else b > a):
            run += 1
        else:
            break
    return run


def _verdict(key: str, cur, lo, hi, prev, status: str, unit: str) -> str:
    c = _fmt(cur, unit)
    if cur is None:
        return {
            "accuracy_pct": "Bu hafta sonucu (doğru/yanlış) girilmiş test yok.",
            "blank_pct": "Bu hafta sonucu girilmiş test yok.",
            "ontime_pct": "Bu hafta henüz tamamlanan görev yok.",
            "night_pct": "Bu hafta henüz tamamlanan görev yok.",
            "gorev_pct": "Bu hafta henüz geçen gün yok.",
        }.get(key, "Bu hafta kayıt yok.")
    if status == "insufficient":
        if lo is None and cur == 0 and key in ("test_done", "new_topics", "empty_days", "night_pct", "blank_pct"):
            return f"Bu hafta {c}."
        return f"Bu hafta {c}. Kıyas için en az {MIN_BASELINE} geçmiş program haftası gerekiyor."
    if round(lo) == round(hi):
        rng = f"%{round(lo)}" if unit == "%" else f"{round(lo)} {unit}"
    else:
        rng = f"%{round(lo)}–{round(hi)}" if unit == "%" else f"{round(lo)}–{round(hi)} {unit}"
    if key == "load":
        tail = {"high": "her zamankinden fazla", "low": "her zamankinden az", "normal": "her zamanki düzeyde"}[status]
        return f"Ona genelde haftada {rng} veriyorsun; bu hafta {c} ile {tail}."
    if status == "normal":
        return f"Genelde {rng}; bu hafta {c} ile her zamanki yerinde."
    if unit == "%":
        diff = abs(round(cur - (lo if cur < lo else hi)))
        word = f"{diff} puan"
    else:
        diff = abs(round(cur - (lo if cur < lo else hi)))
        word = f"{diff} {unit}"
    dir_word = "aşağıda" if cur < lo else "yukarıda"
    lead = "Geçmiş haftaların en kötüsünden de kötü. " if status == "critical" else ""
    return f"{lead}Genelde {rng}; bu hafta {c}, her zamankinden {word} {dir_word}."


# ---------------------------------------------------------------- ana

def build_weekly_progress(db: Session, student: User, *, today: date | None = None) -> dict:
    from app.services import grade_period_service
    from app.services.analytics import usual_first_tick

    today = today or date.today()
    weeks = _weeks(db, student, today)
    cur = next((w for w in reversed(weeks) if w.start <= today <= w.end), None)
    ended = False
    if cur is None:
        past = [w for w in weeks if w.end < today]
        cur = past[-1] if past else None
        ended = True
    if cur is None:
        return {"has_program": False}

    # Aynı noktaya kadar: geçen gün sayısı (bugün sayılmaz)
    k = cur.days if ended else (today - cur.start).days
    period = grade_period_service.current_period(db, student.id)
    period_start = period.started_on if period is not None else None
    first_ids = {w.program_id for w in weeks[:ONBOARDING_WEEKS]}
    # Geçmiş = güncel sınıf dönemindeki haftalar (önceki sınıfın haftaları kıyasa/grafiğe karışmaz)
    history = [w for w in weeks if w.end < cur.start and (period_start is None or w.start >= period_start)]
    baseline = [w for w in history
                if w.days >= MIN_WEEK_DAYS and not w.cut and w.program_id not in first_ids
                and (period_start is None or w.start >= period_start)]

    lo_date = min([w.start for w in history[-12:]] + [cur.start])
    tasks = (db.query(Task)
             .options(selectinload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
                      selectinload(Task.book_items).joinedload(TaskBookItem.section),
                      selectinload(Task.book_items).joinedload(TaskBookItem.topic))
             .filter(Task.student_id == student.id, Task.is_draft.is_(False),
                     Task.date >= lo_date, Task.date <= cur.end).all())

    def tasks_in(a: date, b: date) -> list[Task]:
        return [t for t in tasks if a <= t.date <= b]

    def slice_metrics(w: Week, n: int) -> dict:
        n = max(0, min(n, w.days))
        end = w.start + timedelta(days=n - 1)
        dates = [w.start + timedelta(days=i) for i in range(n)]
        m = _metrics(tasks_in(w.start, end) if n > 0 else [], dates)
        m["load"] = len(tasks_in(w.start, w.end))
        return m

    # Yeni konu: konunun ilk çalışıldığı gün (tüm geçmiş)
    first_seen: dict[int, date] = {}
    rows = (db.query(Task.date, TaskBookItem)
            .join(TaskBookItem, TaskBookItem.task_id == Task.id)
            .options(joinedload(TaskBookItem.section))
            .filter(Task.student_id == student.id, Task.is_draft.is_(False),
                    TaskBookItem.completed_count > 0).all())
    for d, it in rows:
        tid = it.topic_id or (it.section.topic_id if it.section is not None else None)
        if tid and (tid not in first_seen or d < first_seen[tid]):
            first_seen[tid] = d

    def new_topics(a: date, b: date) -> int:
        return sum(1 for d in first_seen.values() if a <= d <= b)

    cur_m = slice_metrics(cur, k)
    cur_m["new_topics"] = new_topics(cur.start, cur.start + timedelta(days=max(k, 0) - 1)) if k > 0 else 0
    base_ms = []
    for w in baseline:
        m = slice_metrics(w, k if k > 0 else w.days)
        m["new_topics"] = new_topics(w.start, w.start + timedelta(days=min(k if k > 0 else w.days, w.days) - 1))
        base_ms.append(m)
    full_ms = []
    for w in history[-12:]:
        m = slice_metrics(w, w.days)
        m["new_topics"] = new_topics(w.start, w.end)
        full_ms.append((w, m))
    # "Geçen hafta" ancak gerçekten bitişik (≤7 gün boşluk) bir hafta varsa; aylar önceki hafta değil.
    prev_w = history[-1] if history and (cur.start - history[-1].end).days <= 7 else None
    prev_m = slice_metrics(prev_w, k if k > 0 else prev_w.days) if prev_w else None
    if prev_m is not None:
        prev_m["new_topics"] = new_topics(prev_w.start, prev_w.start + timedelta(
            days=min(k if k > 0 else prev_w.days, prev_w.days) - 1))

    # ----- kartlar
    cards: list[dict] = []
    for key, name, hint, group, direction, unit in METRICS:
        cv = cur_m.get(key)
        base = [m[key] for m in base_ms if m.get(key) is not None]
        status, lo, hi = _status(cv, base, direction)
        # Kırpılmış (mod geçişi) ya da kısa haftalar eğilim dizisine girmez: 3 günlük parça tam
        # haftayla kıyaslanınca sahte "kötüleşme" üretir.
        full_series = [m[key] for w, m in full_ms
                       if m.get(key) is not None and not w.cut and w.days >= MIN_WEEK_DAYS]
        run = _decline_run(full_series, direction) if direction != 0 else 0
        pv = prev_m.get(key) if prev_m else None
        card = {
            "key": key, "name": name, "hint": hint, "group": group, "unit": unit, "direction": direction,
            "value": cv, "value_label": _fmt(cv, unit), "prev": pv, "prev_label": _fmt(pv, unit),
            "status": status, "low": lo, "high": hi, "baseline": base,
            "trend_run": run, "trend": run >= TREND_RUN,
            "verdict": _verdict(key, cv, lo, hi, pv, status, unit),
        }
        if key == "accuracy_pct":
            wr, td = cur_m["result_coverage"]
            card["hint"] = f"Doğru ÷ (doğru + yanlış). Sonuç girilen {wr} / {td} testten."
        if key == "load":
            card["hint"] = hint
            card["value_label"] = f"{cv} görev"
        if run >= TREND_RUN and status in ("normal", "above", "insufficient"):
            tail = full_series[-(run + 1):]
            card["verdict"] += " " + f"Son {run} haftadır her hafta kötüleşiyor (" + \
                " → ".join(_fmt(v, unit) for v in tail) + ")."
        cards.append(card)

    # Ders dengesi (son 3 tam hafta + bu hafta)
    recent = [w for w in history if w.end >= cur.start - timedelta(days=28)][-3:]
    subj_tot: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for w in recent:
        for nm, d_, t_ in _metrics(tasks_in(w.start, w.end), [])["subjects"]:
            subj_tot[nm][0] += d_
            subj_tot[nm][1] += t_
    for nm, d_, t_ in cur_m["subjects"]:
        subj_tot[nm][0] += d_
        subj_tot[nm][1] += t_
    balance = None
    elig = {nm: v for nm, v in subj_tot.items() if v[1] >= AVOID_MIN_TASKS and nm != "Diğer"}
    if len(elig) >= 2:
        worst = min(elig, key=lambda nm: elig[nm][0] / elig[nm][1])
        wd, wt = elig[worst]
        od = sum(v[0] for nm, v in elig.items() if nm != worst)
        ot = sum(v[1] for nm, v in elig.items() if nm != worst)
        wp, op = round(100 * wd / wt), round(100 * od / ot) if ot else 0
        avoided = wp <= op - AVOID_GAP or wd == 0
        balance = {"subject": worst, "subject_pct": wp, "others_pct": op, "avoided": avoided}
    cards.append({
        "key": "balance", "name": "Ders dengesi", "group": "risk", "unit": "%", "direction": 1,
        "hint": "Son 3 hafta ve bu hafta en çok bırakılan dersin tamamlanma oranı.",
        "value": balance["subject_pct"] if balance else None,
        "value_label": f"{balance['subject']} %{balance['subject_pct']}" if balance else "—",
        "prev": None, "prev_label": "—", "status": ("below" if balance and balance["avoided"] else
                                                     "info" if balance else "insufficient"),
        "low": None, "high": None, "baseline": [], "trend_run": 0, "trend": False,
        "verdict": (f"Diğer derslerde %{balance['others_pct']} tamamlıyor; {balance['subject']} %{balance['subject_pct']} ile en geride."
                    if balance else "Kıyas için yeterli ders görevi yok."),
    })

    # Deneme neti (karne/elle genel deneme, aynı seri) + yanlış arşivi + talep/devir
    cards += _extra_cards(db, student, cur, k, ended, prev_w)

    order = {g[0]: i for i, g in enumerate(GROUPS)}
    cards.sort(key=lambda c: order[c["group"]])

    # ----- haftalar grafiği (tam haftalar) + dönem özeti
    def _range_note(w: Week) -> str:
        if w.cut:
            return f"{w.label} · mod geçişiyle kısaldı"
        return f"{w.label} · havuz dönemi" if w.kind == "donem" else w.label

    chart = []
    for w, m in full_ms[-(CHART_WEEKS - 1):]:
        chart.append({"label": _d(w.start), "range": _range_note(w), "value": m["gorev_pct"],
                      "current": False, "in_baseline": w in baseline})
    chart.append({"label": _d(cur.start), "range": _range_note(cur), "value": cur_m["gorev_pct"],
                  "current": True, "in_baseline": False})
    base_full = [(w, m["gorev_pct"]) for w, m in full_ms if w in baseline and m["gorev_pct"] is not None]
    full_vals = [v for _, v in base_full]
    full_band = _quartiles(full_vals) if len(full_vals) >= MIN_BASELINE else (None, None)
    best = max(base_full, key=lambda x: x[1]) if base_full else None
    worst = min(base_full, key=lambda x: x[1]) if base_full else None
    full_series = [v for _, v in base_full]
    fall_run = _decline_run(full_series, 1)
    summary = {
        "weeks": len(baseline),
        "median": round(median(full_vals), 1) if full_vals else None,
        "best": {"value": best[1], "label": _d(best[0].start)} if best else None,
        "worst": {"value": worst[1], "label": _d(worst[0].start)} if worst else None,
        "band_low": full_band[0], "band_high": full_band[1],
        "decline_run": fall_run,
    }
    # son 4 tam haftanın eğilimi
    last4 = full_series[-4:]
    slope = None
    if len(last4) >= 3:
        n = len(last4)
        mx = (n - 1) / 2
        my = sum(last4) / n
        den = sum((i - mx) ** 2 for i in range(n))
        slope = round(sum((i - mx) * (y - my) for i, y in enumerate(last4)) / den, 1) if den else 0.0
    projection = {
        "same_point_pct": cur_m["gorev_pct"], "projected_pct": cur_m["gorev_pct"] if k > 0 else None,
        "band_low": full_band[0], "band_high": full_band[1],
        "position": (None if cur_m["gorev_pct"] is None or full_band[0] is None or k == 0 else
                     "below" if cur_m["gorev_pct"] < full_band[0] else
                     "above" if cur_m["gorev_pct"] > full_band[1] else "within"),
        "last4": last4, "slope_per_week": slope,
        "load": cur_m["load"],
    }

    # ----- gün gün
    usual_min, _n = usual_first_tick(db, student.id, today)
    days = []
    for i in range(cur.days):
        d = cur.start + timedelta(days=i)
        ts = sorted(tasks_in(d, d), key=lambda t: (t.order or 0, t.id))
        done = [t for t in ts if _is_done(t)]
        missing = [{"title": t.title, "tests": max(0, gorev_stats._planned(t) - gorev_stats._completed(t)) or None}
                   for t in ts if not _is_done(t)]
        if d > today:
            state = "future"
        elif d == today and not ended:
            state = "today"
        elif not ts:
            state = "none"
        elif len(done) == len(ts):
            state = "done"
        elif done:
            state = "partial"
        else:
            state = "missed"
        first = min((_tr(t.completed_at) for t in done if t.completed_at), default=None)
        days.append({
            "date": d.isoformat(), "day": DAY_SHORT[d.weekday()], "label": _d(d), "state": state,
            "total": len(ts), "done": len(done), "missing": missing,
            "first_tick": first.strftime("%H:%M") if first else None,
        })

    week_info = {
        "program_id": cur.program_id, "kind": cur.kind, "start": cur.start.isoformat(), "end": cur.end.isoformat(),
        "label": cur.label, "day_index": min(k + 1, cur.days) if not ended else cur.days,
        "days": cur.days, "ended": ended, "today_label": DAY_SHORT[today.weekday()],
        "compare_days": k, "usual_start": f"{usual_min // 60:02d}:{usual_min % 60:02d}",
    }

    from app.services.deneme_analysis import build_deneme_analysis
    deneme = build_deneme_analysis(db, student, today=today)
    actions = _actions(student, cards, days, balance, projection, week_info, deneme)
    if ended or cur.kind == "donem":
        _reword(cards, actions, ended=ended, period=cur.kind == "donem")
    groups = [{"key": g, "name": n, "desc": d} for g, n, d in GROUPS]
    headline = {c["key"]: c for c in cards if c["key"] in ("gorev_pct", "test_done")}
    return {
        "has_program": True, "week": week_info, "headline": headline, "projection": projection,
        "days": days, "chart": chart, "period_summary": summary, "groups": groups,
        "cards": cards, "actions": actions, "deneme": deneme,
    }


def _reword(cards: list[dict], actions: list[dict], *, ended: bool, period: bool) -> None:
    """Biten haftada "bu hafta" → "o hafta"; havuz döneminde "hafta" → "dönem" (yalnız cümle başı kalıpları)."""
    unit = "dönem" if period else "hafta"
    pre = "O" if ended else "Bu"
    pairs = [("Bu hafta henüz", f"{pre} {unit}") if ended else ("", ""), ("Bu hafta", f"{pre} {unit}"), ("bu hafta", f"{pre.lower()} {unit}")]
    pairs = [p for p in pairs if p[0]]
    for c in cards:
        for fld in ("verdict",):
            v = c.get(fld)
            if isinstance(v, str):
                for x, y in pairs:
                    v = v.replace(x, y)
                c[fld] = v
    for a in actions:
        v = a.get("why")
        if isinstance(v, str):
            for x, y in pairs:
                v = v.replace(x, y)
            a["why"] = v


def _extra_cards(db: Session, student: User, cur: Week, k: int, ended: bool, prev_w: Week | None) -> list[dict]:
    from app.models.exam_result import ExamResult, analysis_exam_filter
    from app.models.task_request import TaskRequest
    from app.models.wrong_question import WrongQuestion
    from app.services import exam_scope

    out = []
    exams = (db.query(ExamResult).filter(ExamResult.student_id == student.id, analysis_exam_filter())
             .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc()).limit(40).all())
    genel = [e for e in exams if exam_scope.classify(e) == "genel"]
    last = genel[0] if genel else None
    prev = next((e for e in genel[1:] if exam_scope.series_key(e) == exam_scope.series_key(last)), None) if last else None
    if last:
        diff = round(last.net - prev.net, 2) if prev else None
        status = ("insufficient" if prev is None else "above" if diff > 0 else "below" if diff < 0 else "normal")
        if prev is None:
            verdict = "Aynı seride önceki deneme yok."
        elif diff == 0:
            verdict = f"Önceki deneme de {_num(prev.net)} net idi: değişmedi."
        else:
            verdict = f"Önceki deneme {_num(prev.net)} net idi: {_num(abs(diff))} net {'yükseldi' if diff > 0 else 'düştü'}."
        out.append({
            "key": "exam_net", "name": "Deneme neti", "group": "gelisim", "unit": "net", "direction": 1,
            "hint": f"{exam_scope.exam_scope(last).series_label}, son deneme {_d(last.exam_date)}; yalnız aynı seri kıyaslanır.",
            "value": last.net, "value_label": f"{_num(last.net)} net",
            "prev": prev.net if prev else None, "prev_label": f"{_num(prev.net)} net" if prev else "—",
            "status": status, "low": None, "high": None, "baseline": [],
            "trend_run": 0, "trend": False, "verdict": verdict,
        })

    def rng(w: Week) -> tuple[datetime, datetime]:
        n = w.days if (ended or k == 0) else min(k, w.days)
        a = datetime.combine(w.start, time()) - TR
        return a, a + timedelta(days=n)

    def wq_counts(w: Week) -> tuple[int, int]:
        a, b = rng(w)
        added = db.query(WrongQuestion).filter(WrongQuestion.student_id == student.id,
                                               WrongQuestion.created_at >= a, WrongQuestion.created_at < b).count()
        closed = db.query(WrongQuestion).filter(WrongQuestion.student_id == student.id,
                                                WrongQuestion.closed_at >= a, WrongQuestion.closed_at < b).count()
        return added, closed

    def req_counts(w: Week) -> tuple[int, int]:
        a, b = rng(w)
        reqs = db.query(TaskRequest).filter(TaskRequest.student_id == student.id,
                                            TaskRequest.created_at >= a, TaskRequest.created_at < b).count()
        carried = db.query(Task).filter(Task.student_id == student.id, Task.carried_at.isnot(None),
                                        Task.date >= w.start, Task.date <= w.end).count()
        return reqs, carried

    a1, c1 = wq_counts(cur)
    pa = wq_counts(prev_w) if prev_w else None
    out.append({
        "key": "wrong_archive", "name": "Yanlış arşivi", "group": "gelisim", "unit": "", "direction": 0,
        "hint": "Bu hafta arşive eklenen ve aralıklı tekrarla kapanan soru.",
        "value": a1, "value_label": f"{a1} eklendi · {c1} kapandı", "prev": None,
        "prev_label": f"{pa[0]} · {pa[1]}" if pa else "—", "status": "info", "low": None, "high": None,
        "baseline": [], "trend_run": 0, "trend": False,
        "verdict": f"Geçen hafta {pa[0]} eklenmiş, {pa[1]} kapanmıştı." if pa else "Geçen hafta kaydı yok.",
    })
    r1, d1 = req_counts(cur)
    pr = req_counts(prev_w) if prev_w else None
    out.append({
        "key": "requests", "name": "Talep ve devir", "group": "risk", "unit": "", "direction": -1,
        "hint": "Görev değişiklik talebi ve sonraki haftaya devredilen görev.",
        "value": r1 + d1, "value_label": f"{r1} talep · {d1} devir", "prev": None,
        "prev_label": f"{pr[0]} · {pr[1]}" if pr else "—", "status": "info", "low": None, "high": None,
        "baseline": [], "trend_run": 0, "trend": False,
        "verdict": f"Geçen hafta {pr[0]} talep, {pr[1]} devir vardı." if pr else "Geçen hafta kaydı yok.",
    })
    return out


def _actions(student: User, cards: list[dict], days: list[dict], balance: dict | None,
             projection: dict, week: dict, deneme: dict | None = None) -> list[dict]:
    by = {c["key"]: c for c in cards}
    sid = student.id
    week_href = f"/teacher/students/{sid}/week?start={week['start']}"
    out: list[dict] = []
    # 1. Geçmiş günlerde kalan görevler
    left = [d for d in days if d["state"] in ("partial", "missed")]
    if left:
        n = sum(len(d["missing"]) for d in left)
        titles = [m["title"] for d in left for m in d["missing"]]
        short = [(t if len(t) <= 42 else t[:40].rstrip() + "…") for t in titles[:3]]
        names = ", ".join(short) + (f" ve {len(titles) - 3} görev daha" if len(titles) > 3 else "")
        last = left[-1]
        out.append({
            "key": "carry", "title": f"Kalan {n} görevi hafta içine dağıt",
            "why": (f"{last['label']} günü {n} görev yapılmadı ({names})." if len(left) == 1 else
                    f"Bu hafta {len(left)} günde {n} görev yapılmadı ({names})."
                    )
                   + (" Yük zaten normalin üst sınırında." if by.get("load", {}).get("status") == "high" else ""),
            "cta_label": "Haftalık programı aç", "cta_href": week_href,
            "agenda": f"Yapılmayan {n} görevi konuş, hafta içine dağıt.",
        })
    # 2. Kaçınılan ders
    if balance and balance["avoided"]:
        out.append({
            "key": "avoid", "title": f"{balance['subject']} için seansta konuş, yükü ayarla",
            "why": f"Son haftalarda en çok bırakılan ders: %{balance['subject_pct']} (diğer dersler %{balance['others_pct']}).",
            "cta_label": f"{balance['subject']} görevlerini aç", "cta_href": week_href,
            "agenda": f"{balance['subject']}: neden bırakılıyor? Yükü/kaynağı konuş.",
        })
    # 3. Gününde işaretleme / gece payı
    ont, night = by.get("ontime_pct"), by.get("night_pct")
    if (ont and (ont["trend"] or ont["status"] in ("below", "critical"))) or \
            (night and night["status"] in ("below", "critical")):
        bits = []
        if ont and (ont["trend"] or ont["status"] in ("below", "critical")):
            bits.append(f"gününde tamamlama {ont['value_label']}")
        if night and night["status"] in ("below", "critical"):
            bits.append(f"gece payı {night['value_label']}")
        out.append({
            "key": "rhythm", "title": "Görevleri gününde yapmasını konuş",
            "why": "Bu hafta " + " ve ".join(bits) + " — öğrencinin genel ritminin dışında.",
            "cta_label": "Seans kaydına geç", "cta_href": f"/teacher/students/{sid}#sessions",
            "agenda": "Çalışma ritmi: görevleri gününde yapma, gece çalışmasını azaltma.",
        })
    # 4. Yük yüksek + uyum düşük
    load, gp = by.get("load"), by.get("gorev_pct")
    if load and gp and load["status"] == "high" and gp["status"] in ("below", "critical"):
        out.append({
            "key": "load", "title": "Haftalık yükü bir miktar azalt",
            "why": f"Bu hafta {load['value_label']} verildi (genelde {round(load['low'])}–{round(load['high'])}); "
                   f"uyum {gp['value_label']} ile normalin altında.",
            "cta_label": "Haftalık programı aç", "cta_href": week_href,
            "agenda": "Yük fazla mı geldi? Görev sayısını birlikte ayarla.",
        })
    # 5. Doğruluk düştü
    acc = by.get("accuracy_pct")
    if acc and acc["status"] in ("below", "critical"):
        out.append({
            "key": "accuracy", "title": "Doğruluğu düşen konulara tekrar koy",
            "why": f"Doğruluk bu hafta {acc['value_label']} (genelde %{round(acc['low'])}–{round(acc['high'])}).",
            "cta_label": "Konu performansını aç", "cta_href": f"/teacher/students/{sid}#topics",
            "agenda": "Doğruluk düştü: hangi konularda zorlanıyor?",
        })
    # 6. Program denemesi işaretleri (D4): üst üste düşüş / test–deneme farkı
    series = {s_["key"]: s_ for s_ in (deneme or {}).get("series", [])}
    seen: set[str] = set()
    for f in (deneme or {}).get("flags", []):
        if f["code"] not in ("decline", "test_gap") or f["series"] in seen:
            continue
        sr = series.get(f["series"])
        if not sr:
            continue
        seen.add(f["series"])
        gap = (sr.get("test_accuracy_pct") is not None and sr.get("accuracy_pct") is not None)
        why = f["text"]
        if f["code"] == "decline" and gap:
            why += f" Testlerde %{sr['test_accuracy_pct']}, denemede %{sr['accuracy_pct']} doğru."
        out.append({
            "key": f"deneme:{sr['key']}", "title": f"{sr['label']} denemesine süre hedefi koy",
            "why": why, "cta_label": "Denemeler sekmesi", "cta_href": f"/teacher/students/{sid}#exams",
            "agenda": f"{sr['label']}: denemede düşüş — süre yönetimi ve karma soru pratiği.",
        })
    return out
