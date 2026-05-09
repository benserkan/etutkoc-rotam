"""Bildirim dispatcher — kuyruktaki QUEUED satırları işleyip gönderir.

Tek public fonksiyon: `dispatch_pending(db, batch_size)`. Sırasıyla:
1. Hazır (next_attempt_at <= now veya null) ve QUEUED olan satırları çeker
2. Her birine günlük tavan kontrolü uygular (per-veli/gün max DAILY_CAP)
3. Kanala göre transport çağırır (email_service.send_email / whatsapp.send_template)
4. Sonuca göre satırı SENT veya FAILED olarak işaretler; FAILED ise next_attempt_at
   exponential backoff ile ilerletir, MAX_ATTEMPTS aşılırsa kalıcı FAILED

Multi-worker güvenliği: her satır tek bir worker tarafından alınmalı. Şu an
SQLite'da row-level lock yok; pratik çözüm: dispatcher tek instance'da çalışır
(prod'da ayrı process: `python -m app.dispatcher`). Postgres'e geçildiğinde
`SELECT ... FOR UPDATE SKIP LOCKED` ile multi-worker'a açılır.

Çağırma yolları:
- Dev: `app/main.py` lifespan'inde periyodik task (60sn)
- Prod: `python -m app.dispatcher` standalone (Render Background Worker)
- Test: `dispatch_pending(db)` doğrudan
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import (
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentNotificationPref,
    User,
)
from app.services import email_service, whatsapp


logger = logging.getLogger(__name__)


# Yapılandırma sabitleri — config.py'a taşınabilir, şimdilik burada.
MAX_ATTEMPTS = 3
DAILY_CAP_PER_PARENT = 4  # email + WA toplam, INVITATION/OTP hariç
BACKOFF_SECONDS = [60, 300, 1800]  # 1dk, 5dk, 30dk
DEFAULT_BATCH_SIZE = 50

# Tavanın dışında kalan (sistem) bildirim türleri
_BYPASS_CAP_KINDS: set[NotificationKind] = {
    NotificationKind.INVITATION,
    NotificationKind.OTP,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_for(attempt: int) -> int:
    """attempt=1 → 60s, 2 → 300s, 3+ → 1800s"""
    idx = max(0, min(attempt - 1, len(BACKOFF_SECONDS) - 1))
    return BACKOFF_SECONDS[idx]


def _decode_payload(log: NotificationLog) -> dict[str, Any]:
    if not log.payload_json:
        return {}
    try:
        return json.loads(log.payload_json)
    except Exception:
        logger.warning("payload_json decode hatası, log id=%s", log.id)
        return {}


def _is_over_daily_cap(
    db: Session,
    parent_id: int,
    kind: NotificationKind,
    in_run_counter: dict[int, int] | None = None,
) -> bool:
    """Bu veli için bugün gönderilen sayım tavanı geçti mi? INVITATION/OTP hariç.

    in_run_counter: aynı dispatch_pending() içinde gönderilen rakam — autoflush=False
    olduğu için DB count() henüz commit'lenmemiş satırları görmüyor; bu sözlük
    tek-run boyunca per-veli SENT sayısı ekler.
    """
    if kind in _BYPASS_CAP_KINDS:
        return False
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    sent_count = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.parent_id == parent_id,
            NotificationLog.status == NotificationStatus.SENT,
            NotificationLog.sent_at >= today_start,
            NotificationLog.sent_at < today_end,
            NotificationLog.kind.notin_(list(_BYPASS_CAP_KINDS)),
        )
        .count()
    )
    if in_run_counter is not None:
        sent_count += in_run_counter.get(parent_id, 0)
    return sent_count >= DAILY_CAP_PER_PARENT


def _send_email(parent: User, log: NotificationLog) -> tuple[bool, str | None, str | None]:
    """Mevcut email_service'i kullan. Return: (ok, external_id, error).

    Akış:
    1. Önce şablon render edilebiliyor mu? Edilemiyorsa FAILED (retry için).
    2. EMAIL_ENABLED=false / smtp_host yok ise → stub-sent (log mode).
    3. Aksi → SMTP gönderim, sonuca göre.
    """
    from app.config import settings as app_settings

    payload = _decode_payload(log)
    template = payload.get("__template") or f"parent_{log.kind.value}"

    # 1) Şablon hazır mı?
    rendered = email_service.render_template_safe(template, payload)
    if rendered is None:
        return False, None, f"template_render_failed:{template}"

    # 2) Dev/log-only mod: gerçek SMTP yok ama şablon OK → stub-sent
    if not app_settings.email_enabled or not app_settings.smtp_host:
        # send_email zaten log-only modda log atar; biz de "sent" olarak işle
        try:
            email_service.send_email(to=parent.email, template=template, ctx=payload)
        except Exception:
            pass
        return True, "stub:email_log_only", None

    # 3) Gerçek SMTP gönderim
    try:
        ok = email_service.send_email(to=parent.email, template=template, ctx=payload)
        if ok:
            return True, None, None
        return False, None, "smtp_failed"
    except Exception as e:
        logger.exception("Email gönderim istisnası: %s", e)
        return False, None, str(e)[:500]


def _send_whatsapp(
    pref: ParentNotificationPref, log: NotificationLog
) -> tuple[bool, str | None, str | None]:
    """WhatsApp Cloud API çağrısı (Sprint 4'te stub, Sprint 6'da gerçek)."""
    if not pref or not pref.whatsapp_phone:
        return False, None, "no_whatsapp_phone"
    payload = _decode_payload(log)
    template = payload.get("__wa_template", f"veli_{log.kind.value}")
    components = payload.get("__wa_components", [])
    result = whatsapp.send_template(
        to_phone=pref.whatsapp_phone,
        template_name=template,
        components=components,
    )
    return result.success, result.external_id, result.error


def _dispatch_one(
    db: Session, log: NotificationLog, in_run_counter: dict[int, int] | None = None,
) -> None:
    """Tek satırı işle: tavan kontrolü → kanal gönderim → durum güncelle."""

    # Tavan kontrolü (in-run counter ile aynı runde gönderilen sayıyı ekler)
    if _is_over_daily_cap(db, log.parent_id, log.kind, in_run_counter):
        log.status = NotificationStatus.SUPPRESSED
        log.error = "daily_cap_exceeded"
        log.attempts += 1
        return

    # Veli + pref yükle
    parent = db.get(User, log.parent_id)
    if not parent or not parent.is_active:
        log.status = NotificationStatus.FAILED
        log.error = "parent_inactive"
        log.attempts += 1
        return

    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == log.parent_id)
        .first()
    )

    log.attempts += 1

    # Stage 7 — feature flag kontrolü (kanal bazında)
    from app.services.feature_flags import is_enabled
    institution = None
    if log.student_id:
        student = db.get(User, log.student_id)
        if student and student.teacher_id:
            teacher = db.get(User, student.teacher_id)
            if teacher and teacher.institution:
                institution = teacher.institution

    # Kanal seç
    if log.channel == NotificationChannel.EMAIL:
        if not is_enabled(db, "parent_notifications_email", institution=institution):
            log.status = NotificationStatus.FAILED
            log.error = "feature_flag_disabled"
            log.next_attempt_at = None
            return
        ok, ext_id, err = _send_email(parent, log)
    elif log.channel == NotificationChannel.WHATSAPP:
        if not is_enabled(db, "parent_notifications_whatsapp", institution=institution):
            log.status = NotificationStatus.FAILED
            log.error = "feature_flag_disabled"
            log.next_attempt_at = None
            return
        ok, ext_id, err = _send_whatsapp(pref, log)
    else:
        ok, ext_id, err = False, None, f"unknown_channel:{log.channel}"

    if ok:
        log.status = NotificationStatus.SENT
        log.sent_at = _now()
        log.external_id = ext_id
        log.error = None
        log.next_attempt_at = None
        # Stage 6 — kredi tüket. Sahip = öğretmenin kurumu (varsa) ya da öğretmen.
        # student → teacher_id → owner. Student yoksa parent'tan teacher zinciri yok;
        # bu durumda atla (defansif — fatura tutarsızlığı oluşturmamak için).
        try:
            from app.models import UsageKind, User as _User
            from app.services.credits import CreditOwner, record_usage
            student_id = log.student_id
            if student_id:
                stu = db.get(_User, student_id)
                if stu and stu.teacher_id:
                    teacher = db.get(_User, stu.teacher_id)
                    if teacher:
                        owner = CreditOwner.for_user(teacher)
                        kind = (
                            UsageKind.WHATSAPP_SEND
                            if log.channel == NotificationChannel.WHATSAPP
                            else UsageKind.EMAIL_SEND
                        )
                        record_usage(
                            db, owner=owner, kind=kind,
                            metadata={"notification_id": log.id, "kind": log.kind.value if log.kind else None},
                            autocommit=False,
                        )
        except Exception as ce:
            logger.warning("notification credit record failed (non-fatal): %s", ce)
        return

    # Başarısız — retry kararı
    log.error = (err or "unknown_error")[:500]
    if log.attempts >= MAX_ATTEMPTS:
        log.status = NotificationStatus.FAILED
        log.next_attempt_at = None
    else:
        # QUEUED olarak kal, next_attempt_at'i ileriye al
        log.next_attempt_at = _now() + timedelta(seconds=_backoff_for(log.attempts))
        # status QUEUED kalsın


def dispatch_pending(db: Session, *, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, int]:
    """Hazır QUEUED satırları işle. Tek işlemde max batch_size satır.

    Returns: özet dict {processed, sent, failed, suppressed, retried}.
    """
    now = _now()

    # Hazır satırları çek: QUEUED + (next_attempt_at IS NULL OR next_attempt_at <= now)
    # + (scheduled_at IS NULL OR scheduled_at <= now)
    rows = (
        db.query(NotificationLog)
        .filter(NotificationLog.status == NotificationStatus.QUEUED)
        .filter(
            (NotificationLog.next_attempt_at.is_(None))
            | (NotificationLog.next_attempt_at <= now)
        )
        .filter(
            (NotificationLog.scheduled_at.is_(None))
            | (NotificationLog.scheduled_at <= now)
        )
        .order_by(NotificationLog.queued_at.asc())
        .limit(batch_size)
        .all()
    )

    summary = {"processed": 0, "sent": 0, "failed": 0, "suppressed": 0, "retried": 0}
    in_run_counter: dict[int, int] = {}  # parent_id → bu run'da gönderilen sayı
    for log in rows:
        try:
            _dispatch_one(db, log, in_run_counter)
            summary["processed"] += 1
            if log.status == NotificationStatus.SENT:
                summary["sent"] += 1
                if log.kind not in _BYPASS_CAP_KINDS:
                    in_run_counter[log.parent_id] = in_run_counter.get(log.parent_id, 0) + 1
            elif log.status == NotificationStatus.FAILED:
                summary["failed"] += 1
            elif log.status == NotificationStatus.SUPPRESSED:
                summary["suppressed"] += 1
            else:  # QUEUED — retry kuyrukta kalır
                summary["retried"] += 1
        except Exception as e:
            logger.exception("dispatch_one istisnası, log id=%s: %s", log.id, e)
            log.error = f"dispatch_exception:{str(e)[:400]}"
            log.attempts += 1
            if log.attempts >= MAX_ATTEMPTS:
                log.status = NotificationStatus.FAILED
                log.next_attempt_at = None

    db.commit()
    if summary["processed"]:
        logger.info("Dispatch özet: %s", summary)
    return summary
