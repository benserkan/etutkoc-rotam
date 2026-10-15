"""Havuz modu — zamanlı işler (Adım 3, 2026-10-12).

  · daily_close  (günlük 03:15 TR): dünün kaplarını kapatır — yapılmayan kalem havuza
                  döner (K34). Yalnız havuz modundaki, açık dönemi olan öğrenciler.
  · reminders    (30 dk'da bir): K37 iki hatırlatma —
        sabah: kap boşsa, öğrencinin olağan başlama saatinden (usual_first_tick) sonra,
               günde bir kez; şube ders programı biliniyorsa "bugün biyoloji vardı,
               biyoloji kalemin var" cümlesiyle.
        akşam: 21:00'den sonra kapta işaretlenmemiş kalem varsa, günde bir kez.
    Dedup `moment_events` (user + anahtar + gün tekil) ile; push best-effort.
Gün-gün öğrencisi bu işlerden hiç etkilenmez (mod süzgeci).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import StudyPeriod, Subject, Task, TaskStatus, User
from app.models.moment_event import MomentEvent
from app.models.pool import PERIOD_OPEN, PROGRAM_MODE_HAVUZ
from app.services import pool_mode as pm

logger = logging.getLogger(__name__)

MORNING_LATEST_MIN = 21 * 60      # sabah hatırlatması en geç 21:00
EVENING_MIN = 21 * 60             # akşam hatırlatması 21:00'den sonra
MOMENT_MORNING = "pool_morning"
MOMENT_EVENING = "pool_evening"
MOMENT_GUIDE = "pool_guide"       # K43: eksik kademe yönlendirmesi (günde en çok bir kez)


def _tr(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now + timedelta(hours=3)


def _havuz_students_with_open_period(db: Session) -> list[tuple[User, StudyPeriod]]:
    rows = (db.query(User, StudyPeriod)
            .join(StudyPeriod, StudyPeriod.student_id == User.id)
            .filter(User.program_mode == PROGRAM_MODE_HAVUZ, User.is_active.is_(True),
                    User.is_paused.is_(False), StudyPeriod.status == PERIOD_OPEN)
            .all())
    return [(u, p) for u, p in rows]


def daily_close(db: Session, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    yesterday = _tr(now).date() - timedelta(days=1)
    n_students = removed = shrunk = 0
    for student, _p in _havuz_students_with_open_period(db):
        try:
            res = pm.close_day(db, student=student, day=yesterday)
            db.commit()
            n_students += 1
            removed += res["removed"]
            shrunk += res["shrunk"]
        except Exception:  # noqa: BLE001 — bir öğrenci diğerini durdurmasın
            db.rollback()
            logger.warning("pool daily_close failed for student %s", student.id, exc_info=True)
    out = {"day": yesterday.isoformat(), "students": n_students, "removed": removed, "shrunk": shrunk}
    logger.info("pool daily_close: %s", out)
    return out


def _already(db: Session, user_id: int, key: str, day: date) -> bool:
    return (db.query(MomentEvent.id)
            .filter(MomentEvent.user_id == user_id, MomentEvent.moment_key == key,
                    MomentEvent.day == day.isoformat()).first() is not None)


def _stamp(db: Session, user_id: int, key: str, day: date, now: datetime) -> None:
    db.add(MomentEvent(user_id=user_id, moment_key=key, day=day.isoformat(), occurred_at=now))


def morning_message(db: Session, *, student: User, coach_id: int | None, period: StudyPeriod,
                    day: date) -> tuple[str, str]:
    """K37 ek: şube ders programı varsa o günün dersiyle konuşur."""
    title = "Bugün havuzdan ne alıyorsun?"
    body = "Kabın boş. Havuzdan bugün yapacağın kalemleri seç."
    if coach_id:
        coach = db.get(User, coach_id)
        cg = pm.class_group_of(db, student=student, coach=coach) if coach else None
        taught = pm.subjects_taught_on(cg, day)
        if taught:
            remaining = {it.subject_id for it in period.items
                         if it.removed_at is None and it.remaining > 0 and it.subject_id in taught}
            if remaining:
                names = [s.name for s in db.query(Subject).filter(Subject.id.in_(remaining)).all()]
                if names:
                    n = ", ".join(sorted(names))
                    body = (f"Bugün dershanede {n} vardı ve havuzunda {n} kalemin var. "
                            f"Bir kısmını bugün yapmak ister misin?")
    return title, body


GUIDE_CODES = ("pool_idle_streak", "pool_dy_missing", "pool_accuracy_")


def guidance_message(db: Session, *, student: User, day: date) -> tuple[str, str] | None:
    """K43: eksik kademeye göre tek yönlendirme cümlesi. Giriş yok → 'havuzuna bak';
    D/Y yok → 'doğru/yanlış gir'; düşük doğruluk (K46) → 'çözümlere bak'. Kap/işaret
    kademeleri sabah/akşam hatırlatmalarında zaten var; kağıt öğrencisi (K40) susar."""
    from app.services import pool_flags as pf
    rep = pf.evaluate_pool_flags(db, student, day)
    codes = {w.code for w in rep.primary + rep.secondary}
    if "pool_paper" in codes:
        return None
    if "pool_idle_streak" in codes:
        return ("Havuzun seni bekliyor", "Birkaç gündür havuzuna bakmadın. Bugün küçük bir kalemle başla; "
                                           "kalanı seansa kadar bölüştürürüz.")
    acc = next((w for w in rep.primary + rep.secondary if w.code.startswith("pool_accuracy_")), None)
    if acc is not None:
        return ("Bir derste doğruluk düşük", f"{acc.title}. Yanlışlarının çözümlerine bakıp konuyu kısa "
                                             "tekrar et; sonra aynı testten birkaç soru daha çöz.")
    if "pool_dy_missing" in codes:
        return ("Doğru/yanlış da gir", "İşaretlerken doğru-yanlış-boş sayısını yaz; hangi konuda "
                                        "zorlandığın ancak böyle görünür.")
    return None


def reminders(db: Session, *, now: datetime | None = None) -> dict:
    from app.services.analytics import usual_first_tick
    from app.services.push_notifications import safe_push

    now = now or datetime.now(timezone.utc)
    tr = _tr(now)
    day = tr.date()
    minutes = tr.hour * 60 + tr.minute
    sent_m = sent_e = sent_g = 0
    for student, period in _havuz_students_with_open_period(db):
        cup = (db.query(Task).filter(Task.student_id == student.id, Task.date == day,
                                     Task.pool_item_id.isnot(None)).all())
        # --- sabah: kap boş, olağan başlama saati geçti, 21:00'den önce
        if not cup and minutes < MORNING_LATEST_MIN and not _already(db, student.id, MOMENT_MORNING, day):
            due, _n = usual_first_tick(db, student.id, day)
            if minutes >= due:
                has_items = any(it.removed_at is None and it.remaining > 0 for it in period.items)
                if has_items:
                    title, body = morning_message(db, student=student, coach_id=student.teacher_id,
                                                  period=period, day=day)
                    safe_push(db, user_id=student.id, title=title, body=body,
                              data={"type": "student", "screen": "pool"})
                    _stamp(db, student.id, MOMENT_MORNING, day, now)
                    sent_m += 1
        # --- K43 yönlendirme: eksik kademede öğrenciye bildirim (günde bir kez, sabah
        # penceresinde; kırmızı GİTMEZ — yalnız "şunu yapmayı dene" cümlesi)
        if minutes < MORNING_LATEST_MIN and not _already(db, student.id, MOMENT_GUIDE, day):
            due, _n = usual_first_tick(db, student.id, day)
            if minutes >= due:
                g = guidance_message(db, student=student, day=day)
                if g:
                    safe_push(db, user_id=student.id, title=g[0], body=g[1],
                              data={"type": "student", "screen": "pool"})
                    sent_g += 1
                _stamp(db, student.id, MOMENT_GUIDE, day, now)
        # --- akşam: kapta işaretlenmemiş kalem var
        if cup and minutes >= EVENING_MIN and not _already(db, student.id, MOMENT_EVENING, day):
            open_tasks = [t for t in cup if t.status != TaskStatus.COMPLETED]
            if open_tasks:
                safe_push(db, user_id=student.id, title="Kabındaki kalemleri işaretledin mi?",
                          body=f"Bugün kabına aldığın {len(open_tasks)} kalem işaretlenmedi. "
                               "Çözdüysen doğru/yanlış/boş gir; kalan havuza döner.",
                          data={"type": "student", "screen": "pool"})
                _stamp(db, student.id, MOMENT_EVENING, day, now)
                sent_e += 1
    db.commit()
    out = {"day": day.isoformat(), "morning": sent_m, "evening": sent_e, "guide": sent_g}
    if sent_m or sent_e or sent_g:
        logger.info("pool reminders: %s", out)
    return out
