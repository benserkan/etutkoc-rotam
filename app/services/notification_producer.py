"""Bildirim üreticisi — kuyruğa yazma API'si.

Tek fonksiyon: `enqueue_notification(...)`. Üretici (cron, olay tetikleyici, manuel
buton) bu fonksiyonu çağırır; satır `notification_logs`'a `status=QUEUED` olarak
yazılır. Asıl gönderim notification_dispatcher tarafından asenkron yapılır.

Sessiz saat / pref kontrolü:
- Veli o tür bildirimi kapattıysa → status=SUPPRESSED yazılır (göndermeden)
- Veli unsubscribed_at SET ise → status=SUPPRESSED yazılır
- Veli sessiz saatte ise → scheduled_at sessiz saat sonuna ayarlanır
- Aksi halde scheduled_at=now → dispatcher hemen alır

Producer ÖZELLİKLE GÖNDERMEZ — bu önemli. Ham API çağrıları yapan tek nokta
dispatcher; producer sadece kayıt atar. Bu sayede:
- Test edilebilir (veritabanına ne yazıldığı denetlenir)
- Crash-safe (üretici crash'lerse mesaj kaybolmaz, kuyrukta kalır)
- Multi-worker-safe (üretici her yerde çalışabilir, dispatcher tek yerde)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentNotificationPref,
    ParentStudentLink,
)


logger = logging.getLogger(__name__)


# Hangi bildirim türü hangi pref alanını kontrol eder
_KIND_TO_PREF_FIELD: dict[NotificationKind, str] = {
    NotificationKind.DAILY_SUMMARY: "daily_summary_enabled",
    NotificationKind.EMPTY_DAY: "empty_day_alert_enabled",
    NotificationKind.WEEKLY_REPORT: "weekly_report_enabled",
    NotificationKind.NEW_PROGRAM: "new_program_alert_enabled",
    NotificationKind.DROP_ALERT: "drop_alert_enabled",
    NotificationKind.TEACHER_NOTE: "teacher_note_enabled",
    NotificationKind.EXAM_APPROACHING: "exam_approaching_enabled",
    # INVITATION ve OTP her zaman gönderilir — pref kontrolü yok
}

# WhatsApp olmasa da gönderilen tip (INVITATION/OTP gibi sistem mesajları)
_BYPASS_PREF_KINDS: set[NotificationKind] = {
    NotificationKind.INVITATION,
    NotificationKind.OTP,
}


def _safe_json(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        if is_dataclass(payload):
            payload = asdict(payload)
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning("payload_json serialize hatası: %s", e)
        return None


def _quiet_hours_active(pref: ParentNotificationPref, now: datetime) -> bool:
    """Veli sessiz saatte mi?

    Sessiz saatler aynı gün içinde (08:00-22:00) veya gün-aşırı (22:00-07:00) olabilir.
    """
    if not pref.quiet_hours_start or not pref.quiet_hours_end:
        return False
    s, e = pref.quiet_hours_start, pref.quiet_hours_end
    cur = now.time()
    if s == e:
        return False
    if s < e:
        # Aynı gün penceresi (örn 12:00-14:00)
        return s <= cur < e
    # Gün aşırı (örn 22:00-07:00)
    return cur >= s or cur < e


def _next_active_time(pref: ParentNotificationPref, now: datetime) -> datetime:
    """Sessiz saat içindeysek, sessiz saat bitişine kadar ertele."""
    if not _quiet_hours_active(pref, now):
        return now
    end = pref.quiet_hours_end
    target = now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return target


def enqueue_notification(
    db: Session,
    *,
    parent_id: int,
    student_id: int | None,
    kind: NotificationKind,
    channel: NotificationChannel,
    subject: str | None = None,
    payload: Any = None,
    bypass_quiet_hours: bool = False,
) -> NotificationLog:
    """Bildirim kaydını kuyruğa yaz.

    payload: dispatcher'ın email render'ı için context (dict; Jinja şablonuna verilir).

    Returns: yazılan NotificationLog satırı (status=QUEUED ya da SUPPRESSED).
    """
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == parent_id)
        .first()
    )

    now = datetime.now(timezone.utc)

    # 0) Çocuk-bazlı sustur (parent_student_link.muted) — INVITATION/OTP hariç
    #    sistem mesajları zaten student_id'siz gönderiliyor, bu kontrol noop olur.
    if student_id is not None and kind not in _BYPASS_PREF_KINDS:
        link = (
            db.query(ParentStudentLink)
            .filter(
                ParentStudentLink.parent_id == parent_id,
                ParentStudentLink.student_id == student_id,
            )
            .first()
        )
        if link and link.muted:
            log = NotificationLog(
                parent_id=parent_id, student_id=student_id, kind=kind, channel=channel,
                status=NotificationStatus.SUPPRESSED,
                subject=subject, payload_json=_safe_json(payload),
                error="child_muted",
            )
            db.add(log)
            db.flush()
            return log

    # 1) Genel unsubscribe? → SUPPRESSED (INVITATION/OTP hariç)
    if (
        pref and pref.unsubscribed_at is not None
        and kind not in _BYPASS_PREF_KINDS
    ):
        log = NotificationLog(
            parent_id=parent_id, student_id=student_id, kind=kind, channel=channel,
            status=NotificationStatus.SUPPRESSED,
            subject=subject, payload_json=_safe_json(payload),
            error="unsubscribed",
        )
        db.add(log)
        db.flush()
        return log

    # 2) Tür bazlı pref kapalı → SUPPRESSED
    if pref and kind not in _BYPASS_PREF_KINDS:
        field = _KIND_TO_PREF_FIELD.get(kind)
        if field is not None and not getattr(pref, field, True):
            log = NotificationLog(
                parent_id=parent_id, student_id=student_id, kind=kind, channel=channel,
                status=NotificationStatus.SUPPRESSED,
                subject=subject, payload_json=_safe_json(payload),
                error=f"pref:{field}=False",
            )
            db.add(log)
            db.flush()
            return log

    # 3) WhatsApp kanalı için pref + telefon doğrulama kontrolü
    if channel == NotificationChannel.WHATSAPP and kind not in _BYPASS_PREF_KINDS:
        if not pref or not pref.whatsapp_enabled or not pref.whatsapp_phone:
            log = NotificationLog(
                parent_id=parent_id, student_id=student_id, kind=kind, channel=channel,
                status=NotificationStatus.SUPPRESSED,
                subject=subject, payload_json=_safe_json(payload),
                error="whatsapp_not_enabled",
            )
            db.add(log)
            db.flush()
            return log

    # 4) Sessiz saat → scheduled_at ileriye al
    scheduled = now
    if pref and not bypass_quiet_hours and kind not in _BYPASS_PREF_KINDS:
        scheduled = _next_active_time(pref, now)

    log = NotificationLog(
        parent_id=parent_id, student_id=student_id, kind=kind, channel=channel,
        status=NotificationStatus.QUEUED,
        subject=subject, payload_json=_safe_json(payload),
        scheduled_at=scheduled,
        next_attempt_at=scheduled,
    )
    db.add(log)
    db.flush()
    return log
