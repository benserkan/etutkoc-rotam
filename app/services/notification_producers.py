"""Yüksek seviye bildirim üreticileri — bildirim türü başına tek fonksiyon.

`notification_producer.enqueue_notification()` kuyruğa yazma katmanı (low-level);
bu modül "X olayı oldu, ilgili veliye bildirim gönder" katmanı (high-level).

Her produce_*() fonksiyonu:
1. Veriyi (öğrenci adı, sayılar, tarih...) parametre olarak alır — kendi sorgu yapmaz
   ki cron + event tetikleyici aynı yerden çağırsın.
2. Email payload + (opsiyonel) WhatsApp components dict'ini hazırlar.
3. Kanal matrisi:
   - DAILY_SUMMARY, EMPTY_DAY → sadece email
   - WEEKLY_REPORT, NEW_PROGRAM, DROP_ALERT, TEACHER_NOTE → email + WA (link)
4. Her aktif kanal için `enqueue_notification` çağırır.
5. Yazılan NotificationLog satır listesini döner (test/audit için).

Pref kontrolleri (whatsapp_enabled, kind toggle, unsubscribed) zaten low-level
producer'da uygulanıyor; burada sadece kanal listesi belirleniyor.

Tetikleyici noktalar:
- Cron job'lar → daily_summary, weekly_backstop, drop_alert (Sprint 5'te yazıldı)
- Event'ler → mark_task_completed (döngü-son weekly_report), öğretmen yayınla
  (new_program), öğretmen "veliye not" butonu (teacher_note) — Sprint 8'de
  bağlanacak; producer arayüzü zaten hazır.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    ParentNotificationPref,
    User,
)
from app.services.notification_producer import enqueue_notification


logger = logging.getLogger(__name__)


# ---------------------------- Yardımcılar ----------------------------


def _unsub_token(db: Session, parent_id: int) -> str | None:
    p = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == parent_id)
        .first()
    )
    return p.unsubscribe_token if p else None


def _wa_eligible(db: Session, parent_id: int) -> bool:
    """Bu veli WA bildirim alabilir mi? (toggle on + telefon doğrulanmış)

    Pref yoksa veya WA kapalıysa False; düşük seviye producer da bu durumda
    SUPPRESSED yazar ama burada channel listesinden çıkararak gereksiz
    SUPPRESSED satırlarını engelliyoruz (cleaner audit log).
    """
    p = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == parent_id)
        .first()
    )
    if not p:
        return False
    return bool(
        p.whatsapp_enabled
        and p.whatsapp_phone
        and p.whatsapp_phone_verified_at
    )


def _student_url_path(student_id: int) -> str:
    return f"/parent/students/{student_id}"


# ---------------------------- DAILY_SUMMARY (email-only) ----------------------------


def produce_daily_summary(
    db: Session,
    *,
    parent: User,
    student: User,
    completed: int,
    planned: int,
    subject_breakdown: list[dict[str, Any]] | None = None,
) -> list[NotificationLog]:
    payload = {
        "__template": "parent_daily_summary",
        "student_id": student.id,
        "student_name": student.full_name,
        "completed": completed,
        "planned": planned,
        "subject_breakdown": subject_breakdown or [],
        "unsubscribe_token": _unsub_token(db, parent.id),
    }
    log = enqueue_notification(
        db,
        parent_id=parent.id,
        student_id=student.id,
        kind=NotificationKind.DAILY_SUMMARY,
        channel=NotificationChannel.EMAIL,
        subject=f"{student.full_name} bugünün özeti",
        payload=payload,
    )
    return [log]


# ---------------------------- EMPTY_DAY (email-only) ----------------------------


def produce_empty_day(
    db: Session,
    *,
    parent: User,
    student: User,
    planned: int,
    consecutive_empty_days: int,
) -> list[NotificationLog]:
    payload = {
        "__template": "parent_empty_day_alert",
        "student_id": student.id,
        "student_name": student.full_name,
        "planned": planned,
        "consecutive_empty_days": consecutive_empty_days,
        "unsubscribe_token": _unsub_token(db, parent.id),
    }
    log = enqueue_notification(
        db,
        parent_id=parent.id,
        student_id=student.id,
        kind=NotificationKind.EMPTY_DAY,
        channel=NotificationChannel.EMAIL,
        subject=f"{student.full_name} bugün hiç görev tamamlamadı",
        payload=payload,
    )
    return [log]


# ---------------------------- WEEKLY_REPORT (email + WA) ----------------------------


def produce_weekly_report(
    db: Session,
    *,
    parent: User,
    student: User,
    week_start: date,
    week_end: date,
    completed: int,
    planned: int,
    rate_pct: int | None,
) -> list[NotificationLog]:
    student_path = _student_url_path(student.id)
    base_payload: dict[str, Any] = {
        "__template": "parent_weekly_report",
        "student_id": student.id,
        "student_name": student.full_name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "completed": completed,
        "planned": planned,
        "rate_pct": rate_pct,
        "unsubscribe_token": _unsub_token(db, parent.id),
    }

    logs: list[NotificationLog] = []
    logs.append(
        enqueue_notification(
            db,
            parent_id=parent.id,
            student_id=student.id,
            kind=NotificationKind.WEEKLY_REPORT,
            channel=NotificationChannel.EMAIL,
            subject=f"{student.full_name} haftalık raporu",
            payload=base_payload,
        )
    )

    if _wa_eligible(db, parent.id):
        wa_payload = dict(base_payload)
        wa_payload["__wa_template"] = "veli_haftalik_rapor"
        wa_payload["__wa_components"] = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": student.full_name},
                {"type": "text", "text": str(completed)},
                {"type": "text", "text": str(planned)},
                {"type": "text", "text": str(rate_pct if rate_pct is not None else "—")},
                {"type": "text", "text": student_path},
            ],
        }]
        logs.append(
            enqueue_notification(
                db,
                parent_id=parent.id,
                student_id=student.id,
                kind=NotificationKind.WEEKLY_REPORT,
                channel=NotificationChannel.WHATSAPP,
                subject=f"{student.full_name} haftalık (WA)",
                payload=wa_payload,
            )
        )
    return logs


# ---------------------------- DROP_ALERT (email + WA) ----------------------------


def produce_drop_alert(
    db: Session,
    *,
    parent: User,
    student: User,
    last_rate_pct: int,
    prev_rate_pct: int,
    drop_pct: int,
    last_week_label: str,
    prev_week_label: str,
) -> list[NotificationLog]:
    student_path = _student_url_path(student.id)
    base_payload: dict[str, Any] = {
        "__template": "parent_drop_alert",
        "student_id": student.id,
        "student_name": student.full_name,
        "last_rate_pct": last_rate_pct,
        "prev_rate_pct": prev_rate_pct,
        "drop_pct": drop_pct,
        "last_week_label": last_week_label,
        "prev_week_label": prev_week_label,
        "unsubscribe_token": _unsub_token(db, parent.id),
    }

    logs: list[NotificationLog] = []
    logs.append(
        enqueue_notification(
            db,
            parent_id=parent.id,
            student_id=student.id,
            kind=NotificationKind.DROP_ALERT,
            channel=NotificationChannel.EMAIL,
            subject=f"{student.full_name} — geçen haftaya göre düşüş",
            payload=base_payload,
        )
    )

    if _wa_eligible(db, parent.id):
        wa_payload = dict(base_payload)
        wa_payload["__wa_template"] = "veli_dusus_alarmi"
        wa_payload["__wa_components"] = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": student.full_name},
                {"type": "text", "text": str(drop_pct)},
                {"type": "text", "text": student_path},
            ],
        }]
        logs.append(
            enqueue_notification(
                db,
                parent_id=parent.id,
                student_id=student.id,
                kind=NotificationKind.DROP_ALERT,
                channel=NotificationChannel.WHATSAPP,
                subject=f"{student.full_name} düşüş (WA)",
                payload=wa_payload,
            )
        )
    return logs


# ---------------------------- NEW_PROGRAM (email + WA) ----------------------------


def produce_new_program(
    db: Session,
    *,
    parent: User,
    student: User,
    week_start: date,
    week_end: date,
    total_tasks: int,
    daily_breakdown: list[dict[str, Any]] | None = None,
) -> list[NotificationLog]:
    """Öğretmen yeni haftalık program yayınladı.

    daily_breakdown: [{"date": "2026-05-06", "label": "Salı", "task_count": 5}, ...]
    Sadece önümüzdeki 7 güne bakar (geçmiş özet vermez — locked design).
    """
    student_path = _student_url_path(student.id)
    base_payload: dict[str, Any] = {
        "__template": "parent_new_program",
        "student_id": student.id,
        "student_name": student.full_name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_tasks": total_tasks,
        "daily_breakdown": daily_breakdown or [],
        "unsubscribe_token": _unsub_token(db, parent.id),
    }

    logs: list[NotificationLog] = []
    logs.append(
        enqueue_notification(
            db,
            parent_id=parent.id,
            student_id=student.id,
            kind=NotificationKind.NEW_PROGRAM,
            channel=NotificationChannel.EMAIL,
            subject=f"{student.full_name} için yeni haftalık program",
            payload=base_payload,
        )
    )

    if _wa_eligible(db, parent.id):
        wa_payload = dict(base_payload)
        wa_payload["__wa_template"] = "veli_yeni_program"
        wa_payload["__wa_components"] = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": student.full_name},
                {"type": "text", "text": str(total_tasks)},
                {"type": "text", "text": student_path},
            ],
        }]
        logs.append(
            enqueue_notification(
                db,
                parent_id=parent.id,
                student_id=student.id,
                kind=NotificationKind.NEW_PROGRAM,
                channel=NotificationChannel.WHATSAPP,
                subject=f"{student.full_name} yeni program (WA)",
                payload=wa_payload,
            )
        )
    return logs


# ---------------------------- EXAM_APPROACHING (email-only, MVP) ----------------------------


def produce_exam_approaching(
    db: Session,
    *,
    parent: User,
    student: User,
    days_left: int,
    threshold: int,
    exam_label: str,
    exam_date: date,
) -> list[NotificationLog]:
    """Sınav yaklaşıyor bildirimi (email + opsiyonel WA).

    threshold: hangi eşikte tetiklendi (30/7/1) — subject'e gömülü, idempotency
    için cron tarafında "[D-{threshold}]" prefix'i ile sorgulanır.

    exam_label: 'LGS' veya 'YKS' — student.effective_exam_label'dan gelir.

    WhatsApp gönderimi yalnızca veli pref WA enabled + telefon doğrulanmışsa.
    Meta Business'ta `veli_sinav_yaklasiyor` template'i 5 parametreyle (öğrenci
    adı, hedef sınav etiketi, kalan gün, sınav tarihi, link) provision edilmiş
    olmalı; aksi halde dispatch hata verir ama email yine gider.
    """
    exam_date_label = exam_date.strftime("%d.%m.%Y")
    student_path = _student_url_path(student.id)
    base_payload: dict[str, Any] = {
        "__template": "parent_exam_approaching",
        "student_id": student.id,
        "student_name": student.full_name,
        "days_left": days_left,
        "threshold": threshold,
        "exam_label": exam_label,
        "exam_date": exam_date.isoformat(),
        "exam_date_label": exam_date_label,
        "unsubscribe_token": _unsub_token(db, parent.id),
    }
    # Subject'in başındaki [D-{threshold}/Y{year}] etiketi cron idempotency
    # sorgusunda LIKE ile aranır — değiştirilirse cron sorgusu da güncellenmeli.
    # Year suffix sayesinde aynı öğrenci ardışık 2 yıl mezun YKS'ye kalırsa
    # ikinci yıl da bildirim alır (önceki yıl için kayıt prefix'i farklıdır).
    exam_year = exam_date.year
    subject_text = (
        f"[D-{threshold}/Y{exam_year}] {student.full_name} — "
        f"{exam_label} sınavına {days_left} gün"
    )

    logs: list[NotificationLog] = []
    logs.append(
        enqueue_notification(
            db,
            parent_id=parent.id,
            student_id=student.id,
            kind=NotificationKind.EXAM_APPROACHING,
            channel=NotificationChannel.EMAIL,
            subject=subject_text,
            payload=base_payload,
        )
    )

    if _wa_eligible(db, parent.id):
        wa_payload = dict(base_payload)
        wa_payload["__wa_template"] = "veli_sinav_yaklasiyor"
        wa_payload["__wa_components"] = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": student.full_name},
                {"type": "text", "text": exam_label},
                {"type": "text", "text": str(days_left)},
                {"type": "text", "text": exam_date_label},
                {"type": "text", "text": student_path},
            ],
        }]
        logs.append(
            enqueue_notification(
                db,
                parent_id=parent.id,
                student_id=student.id,
                kind=NotificationKind.EXAM_APPROACHING,
                channel=NotificationChannel.WHATSAPP,
                subject=subject_text,
                payload=wa_payload,
            )
        )
    return logs


# ---------------------------- TEACHER_NOTE (email + WA) ----------------------------


def produce_teacher_note(
    db: Session,
    *,
    parent: User,
    student: User,
    teacher: User,
    body: str,
    note_id: int | None = None,
) -> list[NotificationLog]:
    """Öğretmenin veliye gönderdiği özel not — manuel tetikleyici (Sprint 8'de buton).

    body: notun ham metni (max 2000 char). Email'de tam, WA'da kısaltılır + link.
    """
    student_path = _student_url_path(student.id)
    base_payload: dict[str, Any] = {
        "__template": "parent_teacher_note",
        "student_id": student.id,
        "student_name": student.full_name,
        "teacher_name": teacher.full_name,
        "body": body,
        "note_id": note_id,
        "unsubscribe_token": _unsub_token(db, parent.id),
    }

    logs: list[NotificationLog] = []
    logs.append(
        enqueue_notification(
            db,
            parent_id=parent.id,
            student_id=student.id,
            kind=NotificationKind.TEACHER_NOTE,
            channel=NotificationChannel.EMAIL,
            subject=f"{student.full_name} — öğretmenden not",
            payload=base_payload,
        )
    )

    if _wa_eligible(db, parent.id):
        wa_payload = dict(base_payload)
        wa_payload["__wa_template"] = "veli_ogretmen_notu"
        wa_payload["__wa_components"] = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": student.full_name},
                {"type": "text", "text": student_path},
            ],
        }]
        logs.append(
            enqueue_notification(
                db,
                parent_id=parent.id,
                student_id=student.id,
                kind=NotificationKind.TEACHER_NOTE,
                channel=NotificationChannel.WHATSAPP,
                subject=f"{student.full_name} öğretmen notu (WA)",
                payload=wa_payload,
            )
        )
    return logs
