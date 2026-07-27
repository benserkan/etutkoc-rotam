"""Randevu servisi (TEK MERKEZ) — online görüşme planlama/organizasyon.

Tüm randevu yazımları buradan geçer: koç ataması, haftalık seri üretimi,
self-servis istek/onay/red, iptal/güncelleme, slot hesabı, hatırlatma cron'u.

Saat modeli: Date + "HH:MM" TÜRKİYE duvar saati. TR sabit UTC+3 (2016'dan beri
yaz saati yok) → `now_tr()` = UTC now + 3 saat. DB'ye tz dönüşümü yazılmaz;
koçun girdiği saat ekranda aynen görünür.

Bildirim İLKESİ: oluştur/güncelle/iptal olayları router'da BackgroundTasks ile
gönderilir (yanıt bloklanmaz); hatırlatmalar cron'dan (appointment_maintenance,
10 dk'da bir). Hepsi best-effort — randevu akışı bildirim hatasıyla ASLA bozulmaz.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import (
    APPT_ACTIVE_STATUSES,
    APPT_SOURCE_COACH,
    APPT_STATUS_CANCELLED,
    APPT_STATUS_DONE,
    APPT_STATUS_NO_SHOW,
    APPT_STATUS_PENDING,
    APPT_STATUS_REJECTED,
    APPT_STATUS_SCHEDULED,
    CoachAvailabilityWindow,
    CoachGoogleAccount,
    CoachingAppointment,
    CoachingAppointmentSeries,
    ParentNotificationPref,
    ParentStudentLink,
    User,
)

logger = logging.getLogger(__name__)

# Türkiye sabit UTC+3 (yaz saati uygulaması 2016'da kalktı).
TR_UTC_OFFSET = timedelta(hours=3)

# Seri occurrence'ları bu kadar gün ileriye üretilir (cron her tick tamamlar).
SERIES_HORIZON_DAYS = 28

# Self-servis istekte slot en az bu kadar dakika sonrasında olmalı.
MIN_LEAD_MINUTES = 60

# Slot listesi en fazla bu kadar gün ileriye bakar.
SLOT_LOOKAHEAD_DAYS = 14

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class AppointmentError(Exception):
    """Servis hatası — router HTTP'ye çevirir."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ---------------------------------------------------------------------------
# Zaman yardımcıları
# ---------------------------------------------------------------------------


def now_tr(now_utc: datetime | None = None) -> datetime:
    """Türkiye duvar saati (naive) — DB'deki date+HH:MM ile karşılaştırılır."""
    base = now_utc or datetime.now(timezone.utc)
    if base.tzinfo is not None:
        base = base.astimezone(timezone.utc).replace(tzinfo=None)
    return base + TR_UTC_OFFSET


def parse_hhmm(value: str) -> time:
    m = _TIME_RE.match((value or "").strip())
    if not m:
        raise AppointmentError(
            "invalid_time", "Saat SS:DD biçiminde olmalı (örn. 17:00)."
        )
    return time(int(m.group(1)), int(m.group(2)))


def appt_start_dt(appt: CoachingAppointment) -> datetime:
    t = parse_hhmm(appt.start_time)
    return datetime.combine(appt.date, t)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _overlaps(a_start: int, a_dur: int, b_start: int, b_dur: int) -> bool:
    return a_start < b_start + b_dur and b_start < a_start + a_dur


# ---------------------------------------------------------------------------
# Çakışma kontrolü
# ---------------------------------------------------------------------------


def _conflicting_appointment(
    db: Session,
    *,
    coach_id: int,
    d: date,
    start: time,
    duration_min: int,
    exclude_id: int | None = None,
) -> CoachingAppointment | None:
    """Koçun aynı gün AKTİF (pending/scheduled) çakışan randevusu var mı?"""
    q = (
        db.query(CoachingAppointment)
        .filter(
            CoachingAppointment.coach_id == coach_id,
            CoachingAppointment.date == d,
            CoachingAppointment.status.in_(APPT_ACTIVE_STATUSES),
        )
    )
    if exclude_id:
        q = q.filter(CoachingAppointment.id != exclude_id)
    smin = _minutes(start)
    for row in q.all():
        try:
            other = _minutes(parse_hhmm(row.start_time))
        except AppointmentError:
            continue
        if _overlaps(smin, duration_min, other, row.duration_min or 40):
            return row
    return None


def _validate_slot_basics(d: date, start: time, *, allow_past: bool = False) -> None:
    if not allow_past:
        start_dt = datetime.combine(d, start)
        if start_dt <= now_tr():
            raise AppointmentError(
                "past_datetime", "Geçmiş bir tarihe randevu oluşturulamaz."
            )


# ---------------------------------------------------------------------------
# Koç ataması + seri
# ---------------------------------------------------------------------------


def create_by_coach(
    db: Session,
    *,
    coach: User,
    student: User,
    d: date,
    start_time: str,
    duration_min: int = 40,
    meeting_link: str | None = None,
    note: str | None = None,
    weekly: bool = False,
) -> tuple[CoachingAppointment, CoachingAppointmentSeries | None]:
    """Koç randevu atar; weekly=True → seri kuralı + ilk occurrence'lar.

    Dönen ilk eleman İLK randevu (weekly'de ilk occurrence). Meet linki
    üretimi ROUTER'da (google bağlıysa best-effort) — burada yalnız kayıt.
    """
    start = parse_hhmm(start_time)
    duration_min = max(10, min(240, int(duration_min or 40)))
    _validate_slot_basics(d, start)
    conflict = _conflicting_appointment(
        db, coach_id=coach.id, d=d, start=start, duration_min=duration_min
    )
    if conflict:
        raise AppointmentError(
            "time_conflict",
            f"Bu saatte başka bir görüşmen var ({conflict.start_time}).",
        )

    series: CoachingAppointmentSeries | None = None
    link = (meeting_link or "").strip() or None
    if weekly:
        series = CoachingAppointmentSeries(
            coach_id=coach.id,
            student_id=student.id,
            weekday=d.weekday(),
            start_time=start.strftime("%H:%M"),
            duration_min=duration_min,
            meeting_link=link,
            link_source="manual" if link else None,
            note=note,
        )
        db.add(series)
        db.flush()

    appt = CoachingAppointment(
        coach_id=coach.id,
        student_id=student.id,
        series_id=series.id if series else None,
        date=d,
        start_time=start.strftime("%H:%M"),
        duration_min=duration_min,
        status=APPT_STATUS_SCHEDULED,
        source=APPT_SOURCE_COACH,
        requested_by_id=coach.id,
        meeting_link=link,
        link_source="manual" if link else None,
        note=note,
    )
    db.add(appt)
    db.flush()

    if series:
        materialize_series(db, series)

    return appt, series


def materialize_series(
    db: Session,
    series: CoachingAppointmentSeries,
    *,
    horizon_days: int = SERIES_HORIZON_DAYS,
) -> int:
    """Serinin ileriye dönük occurrence'larını üret (idempotent).

    [bugün, bugün+horizon] aralığındaki her seri gününe, o tarihte seri kaydı
    YOKSA scheduled randevu ekler. Tek occurrence iptal edilmişse (satır var)
    yeniden ÜRETİLMEZ. Koçun başka randevusuyla çakışan gün ATLANIR (koç
    takvimde görür, elle çözer).
    """
    if not series.active:
        return 0
    today = now_tr().date()
    start = parse_hhmm(series.start_time)
    existing_dates = {
        row[0]
        for row in db.query(CoachingAppointment.date)
        .filter(CoachingAppointment.series_id == series.id)
        .all()
    }
    created = 0
    for i in range(horizon_days + 1):
        d = today + timedelta(days=i)
        if d.weekday() != series.weekday:
            continue
        if d in existing_dates:
            continue
        if datetime.combine(d, start) <= now_tr():
            continue
        if _conflicting_appointment(
            db, coach_id=series.coach_id, d=d, start=start,
            duration_min=series.duration_min,
        ):
            continue
        db.add(CoachingAppointment(
            coach_id=series.coach_id,
            student_id=series.student_id,
            series_id=series.id,
            date=d,
            start_time=series.start_time,
            duration_min=series.duration_min,
            status=APPT_STATUS_SCHEDULED,
            source=APPT_SOURCE_COACH,
            requested_by_id=series.coach_id,
            meeting_link=series.meeting_link,
            link_source=series.link_source,
            google_event_id=series.google_event_id,
            note=series.note,
        ))
        created += 1
    if created:
        db.flush()
    return created


def update_series(
    db: Session,
    series: CoachingAppointmentSeries,
    *,
    weekday: int | None = None,
    start_time: str | None = None,
    duration_min: int | None = None,
    meeting_link: str | None = None,
    active: bool | None = None,
) -> dict:
    """Seri kuralını güncelle; GELECEK scheduled occurrence'lara yansıt.

    Pasifleştirme → gelecekteki scheduled occurrence'lar iptal edilir
    (geçmiş/işaretli kayıtlar korunur). Saat/gün değişimi → gelecekteki
    scheduled occurrence'lar silinip yeniden üretilir (temiz yol).
    """
    changed_rule = False
    if weekday is not None and weekday != series.weekday:
        if not 0 <= weekday <= 6:
            raise AppointmentError("invalid_weekday", "Gün 0-6 aralığında olmalı.")
        series.weekday = weekday
        changed_rule = True
    if start_time is not None:
        t = parse_hhmm(start_time)
        if t.strftime("%H:%M") != series.start_time:
            series.start_time = t.strftime("%H:%M")
            changed_rule = True
    if duration_min is not None and duration_min != series.duration_min:
        series.duration_min = max(10, min(240, int(duration_min)))
        changed_rule = True

    link_changed = False
    if meeting_link is not None:
        link = meeting_link.strip() or None
        if link != series.meeting_link:
            series.meeting_link = link
            series.link_source = "manual" if link else None
            link_changed = True

    deactivated = False
    if active is not None and active != series.active:
        series.active = active
        deactivated = not active

    today = now_tr().date()
    future_q = db.query(CoachingAppointment).filter(
        CoachingAppointment.series_id == series.id,
        CoachingAppointment.date >= today,
        CoachingAppointment.status == APPT_STATUS_SCHEDULED,
    )

    cancelled = 0
    regenerated = 0
    if deactivated:
        for appt in future_q.all():
            appt.status = APPT_STATUS_CANCELLED
            appt.cancel_reason = "Haftalık görüşme planı kapatıldı."
            cancelled += 1
    elif changed_rule:
        # Gelecek scheduled occurrence'ları sil + yeniden üret
        for appt in future_q.all():
            db.delete(appt)
            cancelled += 1
        db.flush()
        regenerated = materialize_series(db, series)
    elif link_changed:
        for appt in future_q.all():
            appt.meeting_link = series.meeting_link
            appt.link_source = series.link_source
    # Yeniden aktifleştirme → occurrence'ları tamamla
    if active is True and not changed_rule:
        regenerated = materialize_series(db, series)
    db.flush()
    return {"cancelled": cancelled, "regenerated": regenerated}


# ---------------------------------------------------------------------------
# Güncelleme / durum geçişleri
# ---------------------------------------------------------------------------


def update_appointment(
    db: Session,
    appt: CoachingAppointment,
    *,
    d: date | None = None,
    start_time: str | None = None,
    duration_min: int | None = None,
    meeting_link: str | None = None,
    note: str | None = None,
) -> dict:
    """Randevu alanlarını güncelle (yalnız pending/scheduled)."""
    if appt.status not in APPT_ACTIVE_STATUSES:
        raise AppointmentError(
            "not_editable", "Sonuçlanmış randevu düzenlenemez."
        )
    time_changed = False
    new_date = d or appt.date
    new_start = parse_hhmm(start_time) if start_time else parse_hhmm(appt.start_time)
    new_dur = max(10, min(240, int(duration_min))) if duration_min else appt.duration_min

    if (
        new_date != appt.date
        or new_start.strftime("%H:%M") != appt.start_time
        or new_dur != appt.duration_min
    ):
        _validate_slot_basics(new_date, new_start)
        conflict = _conflicting_appointment(
            db, coach_id=appt.coach_id, d=new_date, start=new_start,
            duration_min=new_dur, exclude_id=appt.id,
        )
        if conflict:
            raise AppointmentError(
                "time_conflict",
                f"Bu saatte başka bir görüşmen var ({conflict.start_time}).",
            )
        appt.date = new_date
        appt.start_time = new_start.strftime("%H:%M")
        appt.duration_min = new_dur
        # Saat değişti → eski hatırlatma damgaları sıfırlanır (yeni saate göre gider)
        appt.reminder_d1_sent_at = None
        appt.reminder_h1_sent_at = None
        time_changed = True

    if meeting_link is not None:
        link = meeting_link.strip() or None
        if link != appt.meeting_link:
            appt.meeting_link = link
            appt.link_source = "manual" if link else None
    if note is not None:
        appt.note = note.strip() or None
    db.flush()
    return {"time_changed": time_changed}


def set_status(
    db: Session,
    appt: CoachingAppointment,
    *,
    status: str,
    reason: str | None = None,
) -> None:
    """Koç durum işaretler: cancelled / done / no_show (+ geri alma scheduled)."""
    allowed = {
        APPT_STATUS_CANCELLED, APPT_STATUS_DONE,
        APPT_STATUS_NO_SHOW, APPT_STATUS_SCHEDULED,
    }
    if status not in allowed:
        raise AppointmentError("invalid_status", "Geçersiz durum.")
    if appt.status == APPT_STATUS_PENDING and status != APPT_STATUS_CANCELLED:
        raise AppointmentError(
            "pending_needs_review",
            "Bekleyen istek önce onaylanmalı ya da reddedilmeli.",
        )
    if status == APPT_STATUS_CANCELLED:
        appt.cancel_reason = (reason or "").strip() or None
    appt.status = status
    db.flush()


def approve_request(db: Session, appt: CoachingAppointment) -> None:
    if appt.status != APPT_STATUS_PENDING:
        raise AppointmentError("not_pending", "Bu istek zaten sonuçlanmış.")
    start = parse_hhmm(appt.start_time)
    conflict = _conflicting_appointment(
        db, coach_id=appt.coach_id, d=appt.date, start=start,
        duration_min=appt.duration_min, exclude_id=appt.id,
    )
    if conflict and conflict.status == APPT_STATUS_SCHEDULED:
        raise AppointmentError(
            "time_conflict",
            f"Bu saat artık dolu ({conflict.start_time}) — isteği reddet ya da diğer görüşmeyi taşı.",
        )
    appt.status = APPT_STATUS_SCHEDULED
    db.flush()


def reject_request(
    db: Session, appt: CoachingAppointment, *, reason: str | None = None
) -> None:
    if appt.status != APPT_STATUS_PENDING:
        raise AppointmentError("not_pending", "Bu istek zaten sonuçlanmış.")
    appt.status = APPT_STATUS_REJECTED
    appt.cancel_reason = (reason or "").strip() or None
    db.flush()


# ---------------------------------------------------------------------------
# Self-servis: uygunluk + slot + istek
# ---------------------------------------------------------------------------


def replace_availability(
    db: Session, coach: User, windows: list[dict]
) -> list[CoachAvailabilityWindow]:
    """Koçun uygunluk pencerelerini topluca değiştir (replace-all)."""
    if len(windows) > 40:
        raise AppointmentError("too_many_windows", "En fazla 40 pencere tanımlanabilir.")
    parsed: list[tuple[int, time, time, int]] = []
    for w in windows:
        wd = int(w.get("weekday", -1))
        if not 0 <= wd <= 6:
            raise AppointmentError("invalid_weekday", "Gün 0-6 aralığında olmalı.")
        start = parse_hhmm(str(w.get("start_time", "")))
        end = parse_hhmm(str(w.get("end_time", "")))
        if _minutes(end) <= _minutes(start):
            raise AppointmentError(
                "invalid_window", "Bitiş saati başlangıçtan sonra olmalı."
            )
        slot = max(10, min(240, int(w.get("slot_minutes", 40) or 40)))
        parsed.append((wd, start, end, slot))
    db.query(CoachAvailabilityWindow).filter(
        CoachAvailabilityWindow.coach_id == coach.id
    ).delete(synchronize_session=False)
    rows: list[CoachAvailabilityWindow] = []
    for wd, start, end, slot in parsed:
        row = CoachAvailabilityWindow(
            coach_id=coach.id,
            weekday=wd,
            start_time=start.strftime("%H:%M"),
            end_time=end.strftime("%H:%M"),
            slot_minutes=slot,
        )
        db.add(row)
        rows.append(row)
    db.flush()
    return rows


def available_slots(
    db: Session,
    *,
    coach_id: int,
    days: int = SLOT_LOOKAHEAD_DAYS,
) -> list[dict]:
    """Öğrenci/veli slot seçici için boş slot listesi (gün → saatler).

    Pencerelerden slot üretir; koçun AKTİF randevularıyla (pending dahil)
    çakışanları ve çok yakın (MIN_LEAD_MINUTES) olanları eler.
    """
    days = max(1, min(30, days))
    windows = (
        db.query(CoachAvailabilityWindow)
        .filter(
            CoachAvailabilityWindow.coach_id == coach_id,
            CoachAvailabilityWindow.active.is_(True),
        )
        .all()
    )
    if not windows:
        return []
    by_weekday: dict[int, list[CoachAvailabilityWindow]] = {}
    for w in windows:
        by_weekday.setdefault(w.weekday, []).append(w)

    today = now_tr().date()
    lead_cutoff = now_tr() + timedelta(minutes=MIN_LEAD_MINUTES)

    # Aktif randevuları tek sorguda çek (tarih aralığı)
    end_date = today + timedelta(days=days)
    appts = (
        db.query(CoachingAppointment)
        .filter(
            CoachingAppointment.coach_id == coach_id,
            CoachingAppointment.date >= today,
            CoachingAppointment.date <= end_date,
            CoachingAppointment.status.in_(APPT_ACTIVE_STATUSES),
        )
        .all()
    )
    busy: dict[date, list[tuple[int, int]]] = {}
    for a in appts:
        try:
            busy.setdefault(a.date, []).append(
                (_minutes(parse_hhmm(a.start_time)), a.duration_min or 40)
            )
        except AppointmentError:
            continue

    out: list[dict] = []
    for i in range(days + 1):
        d = today + timedelta(days=i)
        wins = by_weekday.get(d.weekday())
        if not wins:
            continue
        slots: list[dict] = []
        for w in wins:
            step = w.slot_minutes or 40
            cur = _minutes(parse_hhmm(w.start_time))
            end_min = _minutes(parse_hhmm(w.end_time))
            while cur + step <= end_min:
                slot_time = time(cur // 60, cur % 60)
                slot_dt = datetime.combine(d, slot_time)
                ok = slot_dt > lead_cutoff and not any(
                    _overlaps(cur, step, b_start, b_dur)
                    for b_start, b_dur in busy.get(d, [])
                )
                if ok:
                    slots.append({
                        "start_time": slot_time.strftime("%H:%M"),
                        "duration_min": step,
                    })
                cur += step
        if slots:
            out.append({"date": d.isoformat(), "slots": slots})
    return out


def create_request(
    db: Session,
    *,
    student: User,
    coach: User,
    d: date,
    start_time: str,
    note: str | None = None,
    requested_by: User,
    source: str,
) -> CoachingAppointment:
    """Öğrenci/veli self-servis randevu isteği (pending — koç onaylar).

    İstenen slot, koçun uygunluk pencerelerinden üretilen GEÇERLİ bir slot
    olmalı (uydurma saat kabul edilmez) + hâlâ boş olmalı.
    """
    start = parse_hhmm(start_time)
    _validate_slot_basics(d, start)

    # Öğrencinin aynı koçta bekleyen isteği varsa ikincisi açılmaz
    existing = (
        db.query(CoachingAppointment)
        .filter(
            CoachingAppointment.student_id == student.id,
            CoachingAppointment.status == APPT_STATUS_PENDING,
        )
        .first()
    )
    if existing:
        raise AppointmentError(
            "pending_exists",
            "Bekleyen bir görüşme isteğin zaten var — koçun yanıtlamasını bekle ya da geri çek.",
        )

    slot_days = available_slots(db, coach_id=coach.id)
    wanted = start.strftime("%H:%M")
    slot = None
    for day in slot_days:
        if day["date"] != d.isoformat():
            continue
        for s in day["slots"]:
            if s["start_time"] == wanted:
                slot = s
                break
    if slot is None:
        raise AppointmentError(
            "slot_unavailable",
            "Bu saat artık uygun değil — listeden boş bir saat seç.",
        )

    appt = CoachingAppointment(
        coach_id=coach.id,
        student_id=student.id,
        date=d,
        start_time=wanted,
        duration_min=slot["duration_min"],
        status=APPT_STATUS_PENDING,
        source=source,
        requested_by_id=requested_by.id,
        request_note=(note or "").strip() or None,
    )
    db.add(appt)
    db.flush()
    return appt


# ---------------------------------------------------------------------------
# Listeleme
# ---------------------------------------------------------------------------


def list_for_coach(
    db: Session, coach_id: int, *, start: date, end: date
) -> list[CoachingAppointment]:
    return (
        db.query(CoachingAppointment)
        .options(joinedload(CoachingAppointment.student))
        .filter(
            CoachingAppointment.coach_id == coach_id,
            CoachingAppointment.date >= start,
            CoachingAppointment.date <= end,
        )
        .order_by(CoachingAppointment.date, CoachingAppointment.start_time)
        .all()
    )


def pending_for_coach(db: Session, coach_id: int) -> list[CoachingAppointment]:
    return (
        db.query(CoachingAppointment)
        .options(joinedload(CoachingAppointment.student))
        .filter(
            CoachingAppointment.coach_id == coach_id,
            CoachingAppointment.status == APPT_STATUS_PENDING,
        )
        .order_by(CoachingAppointment.date, CoachingAppointment.start_time)
        .all()
    )


def upcoming_for_student(
    db: Session, student_id: int, *, limit: int = 10
) -> list[CoachingAppointment]:
    today = now_tr().date()
    rows = (
        db.query(CoachingAppointment)
        .options(joinedload(CoachingAppointment.coach))
        .filter(
            CoachingAppointment.student_id == student_id,
            CoachingAppointment.date >= today,
            CoachingAppointment.status.in_(APPT_ACTIVE_STATUSES),
        )
        .order_by(CoachingAppointment.date, CoachingAppointment.start_time)
        .limit(limit)
        .all()
    )
    # Bugünün saati geçmiş randevularını düş (görüşme bitti sayılır)
    now = now_tr()
    out = []
    for a in rows:
        try:
            end_dt = appt_start_dt(a) + timedelta(minutes=a.duration_min or 40)
        except AppointmentError:
            continue
        if end_dt >= now:
            out.append(a)
    return out


def recent_past_for_student(
    db: Session, student_id: int, *, limit: int = 5
) -> list[CoachingAppointment]:
    today = now_tr().date()
    return (
        db.query(CoachingAppointment)
        .options(joinedload(CoachingAppointment.coach))
        .filter(
            CoachingAppointment.student_id == student_id,
            CoachingAppointment.date < today,
            CoachingAppointment.status.in_(
                (APPT_STATUS_DONE, APPT_STATUS_NO_SHOW, APPT_STATUS_SCHEDULED)
            ),
        )
        .order_by(
            CoachingAppointment.date.desc(), CoachingAppointment.start_time.desc()
        )
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Bildirim yardımcıları (best-effort; router BackgroundTasks + cron kullanır)
# ---------------------------------------------------------------------------


def _fmt_dt_tr(appt: CoachingAppointment) -> str:
    days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
    d = appt.date
    return f"{d.day:02d}.{d.month:02d} {days[d.weekday()]} {appt.start_time}"


def _parent_targets(db: Session, student_id: int) -> list[int]:
    """Bildirim alacak veliler: muted DEĞİL + appointment_enabled pref açık."""
    links = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.student_id == student_id,
            ParentStudentLink.muted.is_(False),
        )
        .all()
    )
    out: list[int] = []
    for link in links:
        pref = (
            db.query(ParentNotificationPref)
            .filter(ParentNotificationPref.parent_id == link.parent_id)
            .first()
        )
        if pref is not None and not pref.appointment_enabled:
            continue
        if pref is not None and pref.unsubscribed_at is not None:
            continue
        out.append(link.parent_id)
    return out


def notify_appointment_event(
    db: Session,
    appt_id: int,
    event: str,  # scheduled | updated | cancelled | request_approved | request_rejected
) -> None:
    """Randevu yaşam döngüsü bildirimi — öğrenci + veli push & e-posta.

    Best-effort: hata yutar (loglar). BackgroundTasks hedefi taze session ile
    `notify_appointment_event_bg` üzerinden çağrılır.
    """
    from app.config import settings
    from app.services.email_service import send_email
    from app.services.push_notifications import safe_push

    appt = (
        db.query(CoachingAppointment)
        .options(
            joinedload(CoachingAppointment.student),
            joinedload(CoachingAppointment.coach),
        )
        .filter(CoachingAppointment.id == appt_id)
        .first()
    )
    if appt is None or appt.student is None:
        return
    student = appt.student
    coach_name = appt.coach.full_name if appt.coach else "Koçun"
    when = _fmt_dt_tr(appt)

    titles = {
        "scheduled": "Yeni koçluk görüşmesi",
        "updated": "Görüşme saati güncellendi",
        "cancelled": "Görüşme iptal edildi",
        "request_approved": "Görüşme isteğin onaylandı",
        "request_rejected": "Görüşme isteğin reddedildi",
    }
    bodies = {
        "scheduled": f"{coach_name} seninle görüşme planladı: {when}.",
        "updated": f"Görüşmen güncellendi: {when}.",
        "cancelled": f"{when} görüşmesi iptal edildi."
        + (f" Sebep: {appt.cancel_reason}" if appt.cancel_reason else ""),
        "request_approved": f"Görüşme isteğin onaylandı: {when}.",
        "request_rejected": "Görüşme isteğin uygun olmadı"
        + (f": {appt.cancel_reason}" if appt.cancel_reason else ".")
        + " İstersen başka bir saat seç.",
    }
    title = titles.get(event, "Koçluk görüşmesi")
    body = bodies.get(event, when)

    try:
        safe_push(
            db, user_id=student.id, title=title, body=body,
            data={"type": "student", "screen": "appointments"},
        )
        if student.email:
            template = (
                "appointment_cancelled"
                if event in ("cancelled", "request_rejected")
                else "appointment_scheduled"
            )
            send_email(student.email, template, {
                "recipient_name": student.full_name,
                "student_name": student.full_name,
                "coach_name": coach_name,
                "when_label": when,
                "duration_min": appt.duration_min,
                "meeting_link": appt.meeting_link,
                "event": event,
                "event_title": title,
                "event_body": body,
                "cancel_reason": appt.cancel_reason,
                "for_parent": False,
            })
    except Exception as e:  # noqa: BLE001
        logger.warning("appointment student notify failed (non-fatal): %s", e)

    # Veliler (pref + mute süzgeçli)
    if event == "request_rejected":
        # Reddi yalnız isteği yapan taraf görür (veli istediyse veli de bilir)
        parent_ids = (
            [appt.requested_by_id]
            if appt.requested_by_id and appt.requested_by_id != student.id
            and appt.source == "parent"
            else []
        )
    else:
        parent_ids = _parent_targets(db, student.id)
    for pid in parent_ids:
        try:
            parent = db.get(User, pid)
            if parent is None:
                continue
            safe_push(
                db, user_id=pid, title=title,
                body=f"{student.full_name} — {body}",
                data={
                    "type": "parent_notification", "kind": "appointment",
                    "student_id": student.id,
                },
            )
            if parent.email:
                template = (
                    "appointment_cancelled"
                    if event in ("cancelled", "request_rejected")
                    else "appointment_scheduled"
                )
                send_email(parent.email, template, {
                    "recipient_name": parent.full_name,
                    "student_name": student.full_name,
                    "coach_name": coach_name,
                    "when_label": when,
                    "duration_min": appt.duration_min,
                    "meeting_link": appt.meeting_link,
                    "event": event,
                    "event_title": title,
                    "event_body": f"{student.full_name} — {body}",
                    "cancel_reason": appt.cancel_reason,
                        "for_parent": True,
                })
        except Exception as e:  # noqa: BLE001
            logger.warning("appointment parent notify failed (non-fatal): %s", e)


def notify_appointment_event_bg(appt_id: int, event: str) -> None:
    """BackgroundTasks hedefi — taze session, yanıtı bloklamaz."""
    try:
        from app.database import SessionLocal

        with SessionLocal() as s:
            notify_appointment_event(s, appt_id, event)
            s.commit()
    except Exception:  # noqa: BLE001
        logger.exception("appointment bg notify failed appt=%s", appt_id)


# ---------------------------------------------------------------------------
# Cron: seri roll-forward + hatırlatmalar
# ---------------------------------------------------------------------------


def run_maintenance(db: Session, *, now_utc: datetime) -> dict:
    """appointment_maintenance cron gövdesi (10 dk'da bir).

    1) Aktif serilerin occurrence'larını ileriye üret (horizon).
    2) D-1 hatırlatması: başlamaya 24 saatten az kalmış + damgasız.
    3) 1 saat hatırlatması: başlamaya 60 dakikadan az kalmış + damgasız.
    Hatırlatmalar scheduled durumundaki randevulara gider (pending değil).

    KİLİT HİJYENİ (dev SQLite dersi): damgalar ÖNCE yazılıp COMMIT edilir,
    push/e-posta İŞLEM DIŞINDA gönderilir — comm_log'un kendi oturumu ana
    işlemin kilidinde beklemez; damga-önce yaklaşımı mükerrer gönderimi de
    yapısal olarak engeller (at-most-once).
    """
    from app.config import settings
    from app.services.email_service import send_email
    from app.services.push_notifications import safe_push

    now_local = now_tr(now_utc)
    today = now_local.date()

    generated = 0
    for series in (
        db.query(CoachingAppointmentSeries)
        .filter(CoachingAppointmentSeries.active.is_(True))
        .all()
    ):
        try:
            generated += materialize_series(db, series)
        except Exception as e:  # noqa: BLE001
            logger.warning("series materialize failed id=%s: %s", series.id, e)
    db.commit()  # seri üretimi kapansın — gönderim aşaması işlem tutmaz

    horizon_end = today + timedelta(days=2)
    candidates = (
        db.query(CoachingAppointment)
        .options(
            joinedload(CoachingAppointment.student),
            joinedload(CoachingAppointment.coach),
        )
        .filter(
            CoachingAppointment.status == APPT_STATUS_SCHEDULED,
            CoachingAppointment.date >= today,
            CoachingAppointment.date <= horizon_end,
        )
        .all()
    )

    # 1. faz — gönderilecekleri seç + DAMGALA + COMMIT (kısa atomik yazım)
    stamp = datetime.now(timezone.utc)
    to_send: list[tuple[CoachingAppointment, str]] = []
    for appt in candidates:
        try:
            start_dt = appt_start_dt(appt)
        except AppointmentError:
            continue
        delta = start_dt - now_local
        if delta.total_seconds() <= 0:
            continue

        kind: str | None = None
        if delta <= timedelta(hours=1) and appt.reminder_h1_sent_at is None:
            kind = "h1"
        elif (
            delta <= timedelta(hours=24)
            and delta > timedelta(hours=1)
            and appt.reminder_d1_sent_at is None
        ):
            kind = "d1"
        if kind is None or appt.student is None:
            continue

        if kind == "h1":
            appt.reminder_h1_sent_at = stamp
            # H-1 gönderiliyorsa D-1 penceresi kaçmıştır — damgala (mükerrer önleme)
            if appt.reminder_d1_sent_at is None:
                appt.reminder_d1_sent_at = stamp
        else:
            appt.reminder_d1_sent_at = stamp
        to_send.append((appt, kind))
    db.commit()

    # 2. faz — gönderim (açık işlem YOK; best-effort)
    d1_sent = 0
    h1_sent = 0
    for appt, kind in to_send:
        student = appt.student
        coach_name = appt.coach.full_name if appt.coach else "Koçun"
        when = _fmt_dt_tr(appt)
        if kind == "h1":
            title = "Görüşmen 1 saatten az kaldı"
            body = f"{coach_name} ile görüşmen {appt.start_time}'te başlıyor."
        else:
            title = "Yarınki görüşmeni unutma"
            body = f"{coach_name} ile görüşmen: {when}."

        try:
            safe_push(
                db, user_id=student.id, title=title, body=body,
                data={"type": "student", "screen": "appointments"},
            )
            if student.email:
                send_email(student.email, "appointment_reminder", {
                    "recipient_name": student.full_name,
                    "student_name": student.full_name,
                    "coach_name": coach_name,
                    "when_label": when,
                    "duration_min": appt.duration_min,
                    "meeting_link": appt.meeting_link,
                    "reminder_kind": kind,
                        "for_parent": False,
                })
            for pid in _parent_targets(db, student.id):
                parent = db.get(User, pid)
                if parent is None:
                    continue
                safe_push(
                    db, user_id=pid, title=title,
                    body=f"{student.full_name} — {body}",
                    data={
                        "type": "parent_notification", "kind": "appointment",
                        "student_id": student.id,
                    },
                )
                if parent.email:
                    send_email(parent.email, "appointment_reminder", {
                        "recipient_name": parent.full_name,
                        "student_name": student.full_name,
                        "coach_name": coach_name,
                        "when_label": when,
                        "duration_min": appt.duration_min,
                        "meeting_link": appt.meeting_link,
                        "reminder_kind": kind,
                                "for_parent": True,
                    })
        except Exception as e:  # noqa: BLE001
            logger.warning("appointment reminder failed appt=%s: %s", appt.id, e)

        if kind == "h1":
            h1_sent += 1
        else:
            d1_sent += 1

    return {"series_generated": generated, "d1_sent": d1_sent, "h1_sent": h1_sent}


# ---------------------------------------------------------------------------
# Google durumu (router özet kartı için)
# ---------------------------------------------------------------------------


def google_status(db: Session, coach: User) -> dict:
    from app.services import google_meet

    account = (
        db.query(CoachGoogleAccount)
        .filter(CoachGoogleAccount.coach_id == coach.id)
        .first()
    )
    return {
        "configured": google_meet.is_configured(),
        "connected": account is not None,
        "email": account.google_email if account else None,
        "last_error": account.last_error if account else None,
    }
