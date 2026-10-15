"""Havuz modu erken uyarı katmanları — K40–K51 (Adım 4, 2026-10-12).

Gün-gün bayrak motoru (`student_flags`) program/katılım katmanlarında görev
TARİHİNİ varsayar; havuz öğrencisinde bu yanlış alarm üretir. Bu modül havuz
öğrencisi için AYNI `FlagReport` sözleşmesini döndürür → pano uyarı akışı, Durum
Özeti, öğrenci listesi rengi, risk puanı ve Gördüm/Ertele mekanizması değişmeden
çalışır. Gün-gün öğrencisine hiç dokunmaz (giriş kapısı `student_flags`).

Katmanlar (üstten alta; K48: öğrenci başına 1 ANA kart + katlanan ek sinyaller):
  P  dönem / havuz (rehber aksiyonu, veliye gitmez)
       pool_no_period · pool_empty · pool_session_overdue (K57) · pool_session_late (K54)
  K  katılım kademeleri (K43): giriş → kap → işaret → D/Y/B
       pool_idle_streak (2 gün sarı / 3 gün kırmızı) · pool_no_cup · pool_no_tick ·
       pool_dy_missing (bilgi)
  T  tempo (K42, TEK başarı kriteri): kalan birim ÷ kalan gün > son 3 dönem günlük
       ortalaması × 1,5 → pool_behind (ilk 2 dönem susar)
  D  doğruluk (K46): ders başına <%50 (≥2 test) → pool_accuracy_{sid}
  E  deneme çaprazı (K47): bu dönem çalışılan konuda denemede yanlış → pool_exam_cross
  A  kaçınma (K44): pool_avoided
  Z  desen (K45, yalnız bilgi): pool_late_{sid} — ders hep sona kalıyor
  G  iyi gidenler: pool_good_done · pool_good_pace
Kağıt öğrencisi (K40/K51): hiç kayıt girmeyen öğrenci kendiliğinden tanınır; K/T/D
susar, yalnız seans işaretlerinden eğilim çizgisi (pool_paper, bilgi).
Veli (K52): havuz öğrencisinde veli uyarısı YOK → parent_level daima green.
Öğrenci (K48): kırmızı gitmez → `student_hints` yalnız yönlendirme cümleleri.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models import PanelVisitEvent, PoolItem, StudyPeriod, Subject, Task, TaskBookItem, TaskStatus, User
from app.models.pool import (
    PERIOD_BREAK, PERIOD_NO_SESSION_RED_DAYS, PERIOD_OPEN, SOURCE_CARRY, UNIT_ETKINLIK, UNIT_TEST,
)
from app.services import pool_mode as pm
from app.services.student_flags import LEVEL_RANK, FlagReport

LAYER_ORDER = {"P": 0, "K": 1, "T": 2, "D": 3, "E": 4, "F": 5, "A": 6, "Z": 7, "G": 8}

# Eşikler (K42–K57, 2026-10-12 kilitli kararlar)
PACE_SILENT_PERIODS = 2      # K42: ilk 2 dönem susar
PACE_HISTORY_PERIODS = 3     # K42: son 3 dönem günlük ortalaması
PACE_FACTOR = 1.5            # K42: ×1,5
IDLE_AMBER_DAYS = 2          # K43
IDLE_RED_DAYS = 3            # K43
IDLE_LOOKBACK_DAYS = 14
GUIDE_DAYS = 2               # K43: eksik kademe 2 gün sürerse yönlendirme
DY_MIN_ITEMS = 3             # K43 D/Y/B kademesi: ≥3 işaretli test kaleminde
DY_MISSING_RATIO = 0.7
ACCURACY_MIN_ITEMS = 2       # K46: ≥2 test
ACCURACY_LOW_PCT = 50        # K46
SESSION_LATE_DAYS = 3        # K54: beklenen gün 3+ geçti
PAPER_TREND_PERIODS = 4      # K51: son 4 dönem
LATE_TAIL_DAYS = 2           # K45: dönemin son 2 günü
LATE_SHARE = 0.7             # K45: birimlerin %70'i sona kaldı/yapılmadı
LATE_MIN_PERIODS = 2         # K45: son 3 dönemin 2'sinde
ONBOARDING_GRACE_DAYS = 3
# F. dürüstlük (2026-10-13): kaba çok alıp toplu "yaptım" işaretleme — havuzu eritme kuşkusu.
# Engel DEĞİL, rehbere sinyal (seansta kaynağa bakıp sorar). Öğrenciye gösterilmez.
BULK_WINDOW_MIN = 10         # bu süre içinde
BULK_MIN_TASKS = 3           # en az bu kadar kap görevi tamamlandı
BULK_MIN_UNITS = 12          # ve toplam en az bu kadar test
DAY_HEAVY_MIN_UNITS = 20     # bir günde işaretlenen test: en az bu kadar VE
DAY_HEAVY_FACTOR = 3.0       # alışkanlığın 3 katı (alışkanlık yoksa 25)
DAY_HEAVY_NO_BASELINE = 25

COACH_ONLY_CODES = ("pool_no_period", "pool_empty", "pool_session_overdue", "pool_session_late",
                    "pool_dy_missing", "pool_avoided", "pool_exam_cross", "pool_bulk_mark")


def _aw(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _tr_day(dt: datetime) -> date:
    return (_aw(dt) + timedelta(hours=3)).date()


def _dstr(d: date) -> str:
    from app.services.analytics import _d
    return _d(d)


def _student_units(item: PoolItem) -> tuple[int, int]:
    """(toplam, ÖĞRENCİNİN kaydettiği) birim — K42 erken uyarı yalnız `completed`e bakar."""
    if item.unit == UNIT_ETKINLIK:
        return 1, (1 if int(item.completed or 0) >= int(item.quantity or 1) else 0)
    return int(item.quantity or 0), min(int(item.quantity or 0), int(item.completed or 0))


def _period_days(p: StudyPeriod, today: date) -> int:
    end = p.closed_on or today
    return max(1, (end - p.opened_on).days)


def _counts_filter():
    """SQL karşılığı: `PoolItem.counts_toward_pool` (öğrenci kalemi yalnız onaylıysa)."""
    return or_(PoolItem.source != pm.SOURCE_STUDENT, PoolItem.approval == pm.APPROVAL_APPROVED)


def _closed_periods(db: Session, student_id: int, *, before: StudyPeriod | None, limit: int) -> list[StudyPeriod]:
    """Kapanmış dönemler (en yeni önce); 'ara' (tatil) tempo/eğilim hesabına girmez."""
    q = (db.query(StudyPeriod).options(joinedload(StudyPeriod.items))
         .filter(StudyPeriod.student_id == student_id, StudyPeriod.status != PERIOD_OPEN,
                 StudyPeriod.status != PERIOD_BREAK))
    if before is not None:
        q = q.filter(StudyPeriod.opened_on <= before.opened_on, StudyPeriod.id != before.id)
    # Boş dönem (yüzdeye giren kalemi yok) tempo/eğilim bilgisi taşımaz: 0 birim/gün olarak girerse
    # öğrenci hep "geride" görünürdü (2026-10-14, #414: 3 boş dönem → "son 3 dönemde günde 0.0").
    q = q.filter(StudyPeriod.items.any(and_(PoolItem.removed_at.is_(None), _counts_filter())))
    return q.order_by(StudyPeriod.opened_on.desc(), StudyPeriod.id.desc()).limit(limit).all()


def _cup_tasks_for(db: Session, item_ids: list[int]) -> list[Task]:
    if not item_ids:
        return []
    return (db.query(Task).options(joinedload(Task.book_items))
            .filter(Task.pool_item_id.in_(item_ids)).all())


def _task_done(t: Task) -> bool:
    return t.status == TaskStatus.COMPLETED or any((bi.completed_count or 0) > 0 for bi in t.book_items)


def _task_units_done(t: Task) -> int:
    if t.book_items:
        return sum(int(bi.completed_count or 0) for bi in t.book_items)
    return pm._units_from_title(t) if t.status == TaskStatus.COMPLETED else 0


def is_paper_student(db: Session, student: User, period: StudyPeriod | None) -> bool:
    """K40: hiç kayıt girmeyen öğrenci. Uygulamaya hiç girmemişse hemen; girmişse en az
    bir kapanmış dönem olup hiçbir dönemde öğrenci kaydı (completed) yoksa."""
    if student.last_active_at is None:
        return True
    any_done = (db.query(PoolItem.id)
                .filter(PoolItem.student_id == student.id, PoolItem.completed > 0).first())
    if any_done is not None:
        return False
    closed = (db.query(StudyPeriod.id)
              .filter(StudyPeriod.student_id == student.id, StudyPeriod.status != PERIOD_OPEN,
                      StudyPeriod.items.any(and_(PoolItem.removed_at.is_(None), _counts_filter())))
              .first())
    return closed is not None


def pace_baseline(db: Session, student_id: int, period: StudyPeriod, today: date) -> tuple[float | None, int]:
    """K42: son 3 (tatil dışı) kapanmış dönemde öğrencinin günlük ortalama birimi.
    (ortalama, dönem sayısı); ilk 2 dönem → (None, n)."""
    hist = _closed_periods(db, student_id, before=period, limit=PACE_HISTORY_PERIODS)
    if len(hist) < PACE_SILENT_PERIODS:
        return None, len(hist)
    rates = []
    for p in hist:
        done = sum(_student_units(it)[1] for it in p.items if it.counts_toward_pool)
        rates.append(done / _period_days(p, today))
    return (sum(rates) / len(rates)) if rates else None, len(hist)


def _participation_days(db: Session, student: User, period: StudyPeriod, today: date,
                        cup_tasks: list[Task]) -> dict[date, dict]:
    """K43 kademeleri gün gün: giriş / kap / işaret / D-Y-B (dönem içi, bugün hariç, en çok 14 gün)."""
    start = max(period.opened_on + timedelta(days=1), today - timedelta(days=IDLE_LOOKBACK_DAYS))
    days = {start + timedelta(days=i): {"login": False, "cup": False, "tick": False, "dyb": False}
            for i in range((today - start).days)}
    if not days:
        return days
    lo = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(hours=3)
    visits = (db.query(PanelVisitEvent.created_at)
              .filter(PanelVisitEvent.user_id == student.id, PanelVisitEvent.created_at >= lo).all())
    for (ts,) in visits:
        d = _tr_day(ts)
        if d in days:
            days[d]["login"] = True
    la = student.last_active_at
    if la is not None and _tr_day(la) in days:
        days[_tr_day(la)]["login"] = True
    for t in cup_tasks:
        if t.date not in days:
            continue
        rec = days[t.date]
        rec["cup"] = True
        if _task_done(t):
            rec["tick"] = True
        if any((bi.correct_count is not None or bi.wrong_count is not None) and (bi.completed_count or 0) > 0
               for bi in t.book_items):
            rec["dyb"] = True
    return days


def _accuracy_by_subject(cup_tasks: list[Task], items_by_id: dict[int, PoolItem]) -> dict[int, tuple[int, int, int]]:
    """ders → (kalem sayısı, doğru, yanlış) — yalnız D/Y girilmiş TEST kalemleri."""
    out: dict[int, list[int]] = {}
    for t in cup_tasks:
        it = items_by_id.get(t.pool_item_id)
        if it is None or it.unit != UNIT_TEST or it.subject_id is None:
            continue
        for bi in t.book_items:
            if (bi.completed_count or 0) <= 0 or (bi.correct_count is None and bi.wrong_count is None):
                continue
            acc = out.setdefault(it.subject_id, [0, 0, 0])
            acc[0] += 1
            acc[1] += int(bi.correct_count or 0)
            acc[2] += int(bi.wrong_count or 0)
    return {k: (v[0], v[1], v[2]) for k, v in out.items()}


def late_pattern(db: Session, student_id: int, period: StudyPeriod | None, today: date) -> dict[int, int]:
    """K45: son 3 kapanmış dönemde dersin birimleri dönemin son 2 gününe kaldı ya da hiç
    yapılmadı (≥%70) → ders → kaç dönemde. Yalnız bilgi."""
    hist = _closed_periods(db, student_id, before=period, limit=PACE_HISTORY_PERIODS)
    counts: dict[int, int] = {}
    for p in hist:
        items = [it for it in p.items if it.counts_toward_pool and it.subject_id]
        if not items:
            continue
        tasks = _cup_tasks_for(db, [it.id for it in items])
        by_item: dict[int, list[Task]] = {}
        for t in tasks:
            by_item.setdefault(t.pool_item_id, []).append(t)
        end = p.closed_on or today
        per_sub: dict[int, list[int]] = {}
        for it in items:
            total, _done = _student_units(it)
            if total <= 0:
                continue
            early = 0
            for t in by_item.get(it.id, []):
                if t.date < end - timedelta(days=LATE_TAIL_DAYS - 1):
                    early += min(total, _task_units_done(t))
            s = per_sub.setdefault(it.subject_id, [0, 0])
            s[0] += total
            s[1] += min(total, early)
        for sid, (total, early) in per_sub.items():
            if total >= 2 and (total - early) / total >= LATE_SHARE:
                counts[sid] = counts.get(sid, 0) + 1
    return {sid: n for sid, n in counts.items() if n >= LATE_MIN_PERIODS}


def paper_trend(db: Session, student_id: int, period: StudyPeriod | None, today: date) -> list[tuple[date, int]]:
    """K51: son 4 kapanmış dönemin yüzdesi (öğrenci kaydı + seans işareti), eskiden yeniye."""
    hist = _closed_periods(db, student_id, before=period, limit=PAPER_TREND_PERIODS)
    out = []
    for p in reversed(hist):
        total = done = 0
        for it in p.items:
            if not it.counts_toward_pool:
                continue
            t, d = pm._units(it)
            total += t
            done += d
        out.append((p.opened_on, int(round(100 * done / total)) if total else 0))
    return out


# ---------------------------------------------------------------- ana giriş

def evaluate_pool_flags(db: Session, student: User, today: date) -> FlagReport:
    from app.services.analytics import Warning

    rep = FlagReport(parent_level="green")  # K52: veliye havuz uyarısı gitmez
    flags: list = []

    def add(layer, level, code, title, detail, evidence, **kw):
        w = Warning(level=level, code=code, title=title, detail=detail, evidence=evidence)
        w.layer = layer
        w.coach_only = code.startswith(COACH_ONLY_CODES)
        for k, v in kw.items():
            setattr(w, k, v)
        flags.append(w)
        return w

    now = datetime.now(timezone.utc)
    created = _aw(student.created_at)
    age = max(0, (now - created).days) if created else None
    period = pm.get_open_period(db, student.id)

    # ---------------------------------------------------------------- P. dönem
    if period is None:
        last = pm.list_periods(db, student.id, limit=1)
        if last and last[0].status == PERIOD_BREAK:
            rep.headline = "Ara (tatil) — takip duraklatıldı"
            return rep
        if age is None or age >= ONBOARDING_GRACE_DAYS:
            if last:
                gap = (today - (last[0].closed_on or last[0].opened_on)).days
                add("P", "red", "pool_no_period", "Açık dönem yok",
                    f"Son dönem {_dstr(last[0].closed_on or last[0].opened_on)} tarihinde kapandı; {gap} gündür "
                    "öğrencinin havuzu yok. Seansta yeni dönemi aç.",
                    [("Son dönem", _dstr(last[0].opened_on) + " – " + (_dstr(last[0].closed_on) if last[0].closed_on else "?")),
                     ("Açık dönem", "yok")])
            else:
                add("P", "red", "pool_no_period", "Havuz henüz yazılmadı",
                    "Öğrenci haftalık havuz modunda ama hiç dönem açılmamış. İlk seansta havuzu yaz.",
                    [("Dönem", "hiç açılmadı")])
        _finish(rep, flags, None, None)
        return rep

    live = [it for it in period.items if it.removed_at is None]
    counting = [it for it in live if it.counts_toward_pool]
    summary = pm.period_summary(db, period, today)
    days_open = (today - period.opened_on).days
    if not counting and days_open >= 1:
        add("P", "amber", "pool_empty", "Havuz boş",
            f"Dönem {_dstr(period.opened_on)} tarihinde açıldı ama havuzda sayılan kalem yok; "
            "öğrencinin bu dönem için işi görünmüyor.",
            [("Dönem", f"{_dstr(period.opened_on)} ({days_open} gün önce)"), ("Kalem", "0")])
    if days_open >= PERIOD_NO_SESSION_RED_DAYS:
        add("P", "red", "pool_session_overdue", f"{days_open} gündür seans yok",
            "Dönem 14 günü aştı; seans yap ya da dönemi 'görüşmesiz kapat'.",
            [("Dönem başı", _dstr(period.opened_on)),
             ("Beklenen seans", _dstr(period.expected_next_on) if period.expected_next_on else "girilmedi")])
    elif period.expected_next_on and (today - period.expected_next_on).days >= SESSION_LATE_DAYS:
        late = (today - period.expected_next_on).days
        add("P", "amber", "pool_session_late", f"Seans {late} gün gecikti",
            f"Beklenen seans günü {_dstr(period.expected_next_on)} idi; dönem hâlâ açık, tempo kalan 1 güne göre ölçülüyor.",
            [("Beklenen", _dstr(period.expected_next_on)), ("Gecikme", f"{late} gün")])

    paper = is_paper_student(db, student, period)
    items_by_id = {it.id: it for it in live}
    cup_tasks = _cup_tasks_for(db, list(items_by_id))

    if paper:
        # K40/K51: dönem içi susar; eğilim yalnız seans işaretinden
        trend = paper_trend(db, student.id, period, today)
        if trend:
            arrow = " → ".join(f"%{p}" for _, p in trend)
            add("Z", "green", "pool_paper", f"Kağıt öğrencisi · son {len(trend)} dönem {arrow}",
                "Öğrenci uygulamaya kayıt girmiyor; yüzde rehberin seans işaretinden. Dönem içi uyarı üretilmez.",
                [(_dstr(d), f"%{p}") for d, p in trend] + [("Kural", "K40/K51 — yalnız eğilim")])
        else:
            add("Z", "green", "pool_paper", "Kağıt öğrencisi",
                "Öğrenci uygulamaya kayıt girmiyor; dönem içi uyarı üretilmez, seansta işaretle.",
                [("Kural", "K40/K51")])
    else:
        # ---------------------------------------------------------------- K. katılım
        days = _participation_days(db, student, period, today, cup_tasks)
        today_tick = any(t.date == today and _task_done(t) for t in cup_tasks)
        streak = 0
        if not today_tick:
            for d in sorted(days, reverse=True):
                r = days[d]
                if r["login"] or r["cup"] or r["tick"]:
                    break
                streak += 1
        if streak >= IDLE_AMBER_DAYS and not (age is not None and age < ONBOARDING_GRACE_DAYS):
            lo = today - timedelta(days=streak)
            add("K", "red" if streak >= IDLE_RED_DAYS else "amber", "pool_idle_streak",
                f"{streak} gündür havuza dokunmadı",
                f"{_dstr(lo)} – {_dstr(today - timedelta(days=1))} arasında ne uygulamaya girdi, ne kap kurdu, ne işaretledi.",
                [("Günler", f"{streak} gün"), ("Kademe", "giriş yok · kap yok · işaret yok"),
                 ("Havuzda kalan", f"{summary.total_units - summary.done_units} birim")])
        else:
            recent = [days[d] for d in sorted(days, reverse=True)[:GUIDE_DAYS]]
            if len(recent) >= GUIDE_DAYS and all(r["login"] for r in recent) and not any(r["cup"] for r in recent):
                add("K", "amber", "pool_no_cup", "Uygulamayı açıyor ama kap kurmuyor",
                    f"Son {GUIDE_DAYS} gün giriş yaptı, havuzdan kalem almadı.",
                    [("Kademe", "giriş var · kap yok"), ("Yönlendirme", "öğrenciye 'bugün havuzdan ne alıyorsun' bildirimi")])
            elif len(recent) >= GUIDE_DAYS and all(r["cup"] for r in recent) and not any(r["tick"] for r in recent):
                add("K", "amber", "pool_no_tick", "Kap kuruyor ama işaretlemiyor",
                    f"Son {GUIDE_DAYS} gün kabına kalem aldı, hiçbirini işaretlemedi.",
                    [("Kademe", "kap var · işaret yok"), ("Yönlendirme", "akşam 'kabındaki kalemleri işaretledin mi' bildirimi")])
        ticked_items = [bi for t in cup_tasks for bi in t.book_items
                        if (bi.completed_count or 0) > 0 and items_by_id.get(t.pool_item_id)
                        and items_by_id[t.pool_item_id].unit == UNIT_TEST]
        if len(ticked_items) >= DY_MIN_ITEMS:
            miss = sum(1 for bi in ticked_items if bi.correct_count is None and bi.wrong_count is None)
            if miss / len(ticked_items) >= DY_MISSING_RATIO:
                add("K", "green", "pool_dy_missing", "Doğru/yanlış girmiyor",
                    f"Bu dönem işaretlediği {len(ticked_items)} test kaleminin {miss} tanesinde D/Y boş; doğruluk ölçülemiyor.",
                    [("D/Y boş", f"{miss}/{len(ticked_items)} kalem"), ("Kademe", "işaret var · D/Y/B yok")])

        # ---------------------------------------------------------------- T. tempo (K42)
        baseline, n_hist = pace_baseline(db, student.id, period, today)
        remaining = sum(max(0, t - d) for t, d in (_student_units(it) for it in counting))
        need = remaining / max(1, summary.days_left)
        if baseline is not None and remaining > 0 and need > baseline * PACE_FACTOR:
            add("T", "amber", "pool_behind", "Tempo geride",
                f"Kalan {remaining} birim için günde {need:.1f} birim gerekiyor; son {n_hist} dönemde günde "
                f"ortalama {baseline:.1f} birim yaptı.",
                [("Kalan", f"{remaining} birim · {summary.days_left} gün"),
                 ("Gereken", f"{need:.1f} birim/gün"),
                 ("Alışkanlık", f"{baseline:.1f} birim/gün (son {n_hist} dönem)"),
                 ("Kural", f"gereken > alışkanlık × {PACE_FACTOR}")],
                remaining_units=remaining, need_per_day=round(need, 1), baseline_per_day=round(baseline, 1))
        elif baseline is None:
            pass  # K42: ilk 2 dönem susar
        elif remaining > 0 and need <= baseline * 0.5 and summary.pct >= 50:
            add("G", "green", "pool_good_pace", "Tempo önde",
                f"Kalan {remaining} birim için günde {need:.1f} birim yeter; alışkanlığı {baseline:.1f}.",
                [("Kalan", f"{remaining} birim · {summary.days_left} gün")])

        # ---------------------------------------------------------------- D. doğruluk (K46)
        acc = _accuracy_by_subject(cup_tasks, items_by_id)
        sids = [s for s, (n, c, w) in acc.items() if n >= ACCURACY_MIN_ITEMS and (c + w) > 0]
        names = {s.id: s.name for s in db.query(Subject).filter(Subject.id.in_(sids)).all()} if sids else {}
        for sid in sids:
            n, c, w = acc[sid]
            pct = int(round(100 * c / (c + w)))
            if pct < ACCURACY_LOW_PCT:
                add("D", "amber", f"pool_accuracy_{sid}", f"{names.get(sid, 'Ders')} doğruluk %{pct}",
                    f"Bu dönem {n} test kaleminde {c} doğru / {w} yanlış; konu öğrenilmemiş olabilir.",
                    [("Doğruluk", f"%{pct} ({c}D / {w}Y)"), ("Kalem", f"{n} test"),
                     ("Kural", f"≥{ACCURACY_MIN_ITEMS} test · <%{ACCURACY_LOW_PCT}")],
                    subject_id=sid, accuracy_pct=pct)

        # ---------------------------------------------------------------- F. dürüstlük (toplu işaretleme)
        bulk = bulk_marking(cup_tasks, items_by_id, baseline)
        if bulk:
            add("F", "amber", "pool_bulk_mark", "Toplu işaretleme — seansta kaynağa bak",
                bulk["detail"], bulk["evidence"])

    # ---------------------------------------------------------------- E. deneme çaprazı (K47)
    strip = pm.exam_strip(db, student=student, period=period)
    if strip and strip.get("in_period") and strip.get("studied_but_wrong"):
        sbw = strip["studied_but_wrong"]
        add("E", "amber", "pool_exam_cross", f"Çalıştığı {len(sbw)} konuda denemede yanlış",
            f"{strip['title']} ({_dstr(date.fromisoformat(strip['exam_date']))}): bu dönem havuzda çalışılan "
            + ", ".join(t["name"] for t in sbw[:4]) + " konularında yanlış var. Seans gündemine alındı.",
            [(t["name"], f"{t['wrong']} yanlış") for t in sbw[:6]] + [("Deneme", strip["title"])],
            exam_id=strip["exam_id"])

    # ---------------------------------------------------------------- A. kaçınma (K44)
    reasons = pm.avoid_reasons(period, today, db) if not paper else {}  # K40: kağıt öğrencisi kaba almaz
    if reasons:
        av = list(reasons)
        names_av = _item_names(db, av)
        add("A", "amber", "pool_avoided", f"{len(av)} kalemden kaçınıyor",
            "Kaba girip geri dönen, 3. kez devredilen ya da hiç alınmayan kalemler: " + "; ".join(names_av[:4]) + ".",
            [(n, reasons[it]) for n, it in zip(names_av[:6], av[:6])])

    # ---------------------------------------------------------------- Z. desen (K45, bilgi)
    late = late_pattern(db, student.id, period, today)
    if late:
        lnames = {s.id: s.name for s in db.query(Subject).filter(Subject.id.in_(late.keys())).all()}
        for sid, n in late.items():
            add("Z", "green", f"pool_late_{sid}", f"{lnames.get(sid, 'Ders')} hep sona kalıyor",
                f"Son dönemlerin {n} tanesinde bu dersin kalemleri dönemin son günlerine kaldı ya da yapılmadı.",
                [("Dönem", f"{n}/{PACE_HISTORY_PERIODS}"), ("Kural", "K45 — yalnız bilgi, seansta konuş")])

    # ---------------------------------------------------------------- G. iyi
    if summary.total_units > 0 and summary.pct >= 100:
        add("G", "green", "pool_good_done", "Havuzu bitirdi",
            f"{summary.done_units}/{summary.total_units} birim tamamlandı.", [("Yüzde", "%100")])

    _finish(rep, flags, period, summary)
    return rep


def bulk_marking(cup_tasks: list[Task], items_by_id: dict[int, PoolItem], baseline: float | None) -> dict | None:
    """Havuzu "eritme" kuşkusu: (1) BULK_WINDOW_MIN dakikada ≥BULK_MIN_TASKS kap görevi ve ≥BULK_MIN_UNITS test
    tamamlandı ya da (2) bir günde işaretlenen test alışkanlığın DAY_HEAVY_FACTOR katını (ve DAY_HEAVY_MIN_UNITS'i) aştı.
    Kaba ALMAK sinyal değildir (yapılmayan kap gün sonu havuza döner); sinyal yalnız İŞARETLEMEDİR."""
    done = []
    for t in cup_tasks:
        it = items_by_id.get(t.pool_item_id)
        if it is None or it.unit not in (UNIT_TEST,) or t.completed_at is None:
            continue
        u = sum(int(bi.completed_count or 0) for bi in t.book_items)
        if u > 0:
            done.append((_aw(t.completed_at), u, t.date))
    if not done:
        return None
    done.sort()
    best = None
    j = 0
    for i in range(len(done)):
        while done[i][0] - done[j][0] > timedelta(minutes=BULK_WINDOW_MIN):
            j += 1
        n = i - j + 1
        units = sum(x[1] for x in done[j:i + 1])
        if n >= BULK_MIN_TASKS and units >= BULK_MIN_UNITS and (best is None or units > best[1]):
            mins = max(1, int((done[i][0] - done[j][0]).total_seconds() // 60))
            best = (n, units, mins, done[i][2])
    per_day: dict[date, int] = {}
    for _ts, u, d in done:
        per_day[d] = per_day.get(d, 0) + u
    limit = max(DAY_HEAVY_MIN_UNITS, baseline * DAY_HEAVY_FACTOR) if baseline else DAY_HEAVY_NO_BASELINE
    heavy = [(d, u) for d, u in per_day.items() if u >= limit]
    if not best and not heavy:
        return None
    ev = []
    parts = []
    if best:
        n, units, mins, d = best
        parts.append(f"{_dstr(d)} günü {mins} dakika içinde {n} görev / {units} test 'yaptım' olarak işaretlendi")
        ev.append(("Toplu işaret", f"{_dstr(d)} · {n} görev · {units} test · {mins} dk"))
    if heavy:
        d, u = max(heavy, key=lambda x: x[1])
        parts.append(f"{_dstr(d)} günü toplam {u} test işaretlendi")
        ev.append(("Yoğun gün", f"{_dstr(d)} · {u} test"))
        ev.append(("Alışkanlık", f"{baseline:.1f} birim/gün" if baseline else "henüz yok"))
    ev.append(("Kural", f"{BULK_WINDOW_MIN} dk'da ≥{BULK_MIN_TASKS} görev+≥{BULK_MIN_UNITS} test ya da günde ≥{int(limit)} test"))
    ev.append(("Not", "Engel değil — kitaba bakıp seans ekranında işaretle; kaba almak sinyal değildir"))
    return {"detail": "; ".join(parts) + ". Gerçekten çözüldü mü, seansta kitabından kontrol et.", "evidence": ev}


def _item_names(db: Session, items: list[PoolItem]) -> list[str]:
    out = []
    for it in items:
        if it.book_section_id and it.section is not None:
            out.append(it.section.label)
        elif it.topic_id and it.topic is not None:
            out.append(it.topic.name)
        else:
            out.append(it.label or (it.subject.name if it.subject is not None else "kalem"))
    return out


def _finish(rep: FlagReport, flags: list, period: StudyPeriod | None, summary) -> None:
    key = lambda w: (LEVEL_RANK.get(w.level, 9), LAYER_ORDER.get(w.layer, 9))
    signal = sorted([w for w in flags if w.layer != "G" and w.level != "green"], key=key)
    info = sorted([w for w in flags if w.layer != "G" and w.level == "green"], key=key)
    rep.good = [w for w in flags if w.layer == "G"]
    # K48: öğrenci başına 1 ANA kart; gerisi katlanan ek sinyal
    rep.primary = signal[:1]
    rep.secondary = signal[1:] + info
    rep.parent_level = "green"
    if rep.primary:
        rep.level = rep.primary[0].level
        rep.headline = rep.primary[0].title
    elif period is not None and summary is not None:
        rep.level = "green"
        rep.headline = (rep.good[0].title if rep.good else f"Havuz yolunda · %{summary.pct}")
    else:
        rep.headline = "Haftalık görev havuzu"


# ---------------------------------------------------------------- öğrenci (K41/K46/K48)

def student_hints(rep: FlagReport) -> list[dict]:
    """Öğrenciye yönlendirme cümleleri — kırmızı yok, yargı yok (K41/K48)."""
    out = []
    for w in rep.primary + rep.secondary:
        if w.code.startswith("pool_accuracy_"):
            out.append({"code": w.code, "title": "Bu derste doğruluk düşük",
                        "note": f"{w.title}. Yanlışlarının çözümlerine bak, konuyu kısa tekrar edip aynı testten birkaç soru daha çöz."})
        elif w.code == "pool_dy_missing":
            out.append({"code": w.code, "title": "Doğru/yanlış gir",
                        "note": "İşaretlerken doğru-yanlış-boş sayısını da yaz; hangi konuda zorlandığın böyle görünür."})
        elif w.code == "pool_no_cup":
            out.append({"code": w.code, "title": "Bugün havuzdan ne alıyorsun?",
                        "note": "Güne başlarken havuzdan 1-2 kalem seç; kap boş kalınca gün kayıt dışı kalıyor."})
        elif w.code == "pool_no_tick":
            out.append({"code": w.code, "title": "Kabındakileri işaretle",
                        "note": "Yaptıklarını akşam işaretle; işaretlenmeyen kalem yapılmamış sayılıp havuza dönüyor."})
        elif w.code == "pool_behind":
            out.append({"code": w.code, "title": "Tempo biraz geride",
                        "note": f"Kalan {getattr(w, 'remaining_units', '?')} birim için günde {getattr(w, 'need_per_day', '?')} birim gerekiyor; bugün bir fazla yapmak haftayı rahatlatır."})
    return out


# ---------------------------------------------------------------- K47 anında: deneme kaydedilince

def exam_cross_check(db: Session, *, student: User, exam_id: int, actor: User) -> dict:
    """Yeni deneme kaydedilince (havuz öğrencisi): bu dönem çalışılan konularda yanlış varsa
    'Seansa ekle' kuyruğuna ZORUNLU ekler + rehbere anında push. İdempotent (anahtar)."""
    from app.models import Topic
    from app.models.exam_result import EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion
    from app.services import exam_progress
    from app.services.push_notifications import safe_push
    from sqlalchemy import func

    if not pm.is_havuz(student):
        return {"skipped": "not_havuz"}
    period = pm.get_open_period(db, student.id)
    exam = db.get(ExamResult, exam_id)
    if period is None or exam is None or exam.student_id != student.id:
        return {"skipped": "no_period"}
    studied = {it.topic_id for it in period.items
               if it.topic_id and it.removed_at is None and it.done_units > 0}
    if not studied:
        return {"added": 0}
    rows = (db.query(ExamResultQuestion.topic_id, func.count(ExamResultQuestion.id))
            .filter(ExamResultQuestion.exam_result_id == exam.id,
                    ExamResultQuestion.result == EQ_RESULT_YANLIS,
                    ExamResultQuestion.topic_id.in_(studied))
            .group_by(ExamResultQuestion.topic_id).all())
    if not rows:
        return {"added": 0}
    tnames = {t.id: t.name for t in db.query(Topic).filter(Topic.id.in_([r[0] for r in rows])).all()}
    items = [{"key": f"pool_cross:{exam.id}:{tid}", "source": "pool",
              "text": f"Denemede yanlış: {tnames.get(tid, 'konu')} ({n} yanlış) — bu dönem havuzda çalışıldı ({exam.title})",
              "exam_id": exam.id} for tid, n in rows]
    _q, added = exam_progress.add_to_queue(db, student.id, items, actor=actor)
    db.flush()
    if added and student.teacher_id:
        names = ", ".join(tnames.get(tid, "konu") for tid, _ in rows[:3])
        safe_push(db, user_id=student.teacher_id, title=f"{student.full_name}: deneme çaprazı",
                  body=f"Bu dönem çalışılan {names} konularında denemede yanlış var; seans gündemine eklendi.",
                  data={"type": "coach_student", "student_id": student.id, "screen": "pool"})
    return {"added": added, "topics": [tnames.get(tid) for tid, _ in rows]}


__all__ = ["evaluate_pool_flags", "student_hints", "exam_cross_check", "is_paper_student",
           "pace_baseline", "late_pattern", "paper_trend"]
