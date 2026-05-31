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
from datetime import date, datetime, timedelta, timezone
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


def _student_url_full(student_id: int) -> str:
    """WhatsApp link variable'ları için: tam URL (app_base_url + path).

    Meta WA mesajlarında body variable olarak gönderilen relative path
    tıklanamaz. Email tarafında relative OK çünkü template_renderer
    base_url ile prefix'liyor.
    """
    from app.config import settings
    base = (settings.app_base_url or "").rstrip("/")
    return f"{base}{_student_url_path(student_id)}"


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


def _build_daily_breakdown(
    db: Session, *, student_id: int, week_start: date, week_end: date,
) -> list[dict]:
    """Günlük görev listesi — her görev: kitap + bölüm + planlanan/tamamlanan soru.

    [{day_iso, day_label, items: [{title, type, book, section, planned, completed}], total_planned, total_completed}]
    """
    from app.models import Task, TaskBookItem
    from sqlalchemy.orm import joinedload

    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book),
                 joinedload(Task.book_items).joinedload(TaskBookItem.section))
        .filter(
            Task.student_id == student_id,
            Task.date >= week_start,
            Task.date <= week_end,
        )
        .order_by(Task.date, Task.id)
        .all()
    )

    by_day: dict[date, list[dict]] = {}
    for t in tasks:
        items_list: list[dict] = []
        total_p = 0
        total_c = 0
        for it in t.book_items:
            planned = int(it.planned_count or 0)
            done = int(it.completed_count or 0)
            total_p += planned
            total_c += done
            book_name = it.label if not it.book else (it.book.name if hasattr(it.book, "name") else "")
            section_name = it.section.name if it.section and hasattr(it.section, "name") else ""
            items_list.append({
                "book": book_name or "—",
                "section": section_name or "",
                "planned": planned,
                "completed": done,
            })
        task_type = (
            t.type.value if hasattr(t.type, "value") else str(t.type)
        ) if t.type else "test"
        task_record = {
            "title": t.title or "",
            "type": task_type,
            # 'items' Jinja2'de dict.items() metoduyla çakışır → 'rows' kullan
            "rows": items_list,
            "total_planned": total_p,
            "total_completed": total_c,
        }
        by_day.setdefault(t.date, []).append(task_record)

    # Tüm hafta günleri (boş günler de listelensin — veli boş gün de görsün)
    day_names_tr = {0: "Pzt", 1: "Sal", 2: "Çar", 3: "Per", 4: "Cum", 5: "Cmt", 6: "Paz"}
    out: list[dict] = []
    cur = week_start
    while cur <= week_end:
        day_tasks = by_day.get(cur, [])
        day_total_p = sum(t["total_planned"] for t in day_tasks)
        day_total_c = sum(t["total_completed"] for t in day_tasks)
        out.append({
            "day_iso": cur.isoformat(),
            "day_label": cur.strftime("%d %b").replace("Jan","Oca").replace("Feb","Şub")
                .replace("Mar","Mar").replace("Apr","Nis").replace("May","May")
                .replace("Jun","Haz").replace("Jul","Tem").replace("Aug","Ağu")
                .replace("Sep","Eyl").replace("Oct","Eki").replace("Nov","Kas").replace("Dec","Ara"),
            "day_name": day_names_tr.get(cur.weekday(), ""),
            "tasks": day_tasks,
            "total_planned": day_total_p,
            "total_completed": day_total_c,
            "has_tasks": len(day_tasks) > 0,
        })
        cur += timedelta(days=1)
    return out


def _get_latest_exam(db: Session, *, student_id: int, since_days: int = 7) -> dict | None:
    """Son deneme — yalnız son N gün içinde girilmiş olan ExamResult varsa."""
    from app.models.exam_result import ExamResult
    from sqlalchemy import desc as _desc

    cutoff = date.today() - timedelta(days=since_days)
    latest = (
        db.query(ExamResult)
        .filter(
            ExamResult.student_id == student_id,
            ExamResult.exam_date >= cutoff,
        )
        .order_by(_desc(ExamResult.exam_date), _desc(ExamResult.created_at))
        .first()
    )
    if latest is None:
        return None
    section_str = latest.section.value if hasattr(latest.section, "value") else (str(latest.section) if latest.section else None)
    return {
        "title": latest.title,
        "date_iso": latest.exam_date.isoformat() if latest.exam_date else None,
        "net": float(latest.net) if latest.net is not None else None,
        "correct": int(latest.total_correct or 0),
        "wrong": int(latest.total_wrong or 0),
        "blank": int(latest.total_blank or 0),
        "section": section_str,
    }


def _get_recent_exams(
    db: Session, *, student_id: int, since_days: int = 90, limit: int = 20,
) -> list[dict]:
    """Son N gün denemeleri — güncel tarih → geriye doğru sıralı.

    M3 için `parent_new_program` mail'ine eklenir: veli yeni programı görürken
    son 3 ayın deneme performansını da görür (bilgi amaçlı, klinik teşhis değil).
    `limit` mail boyutunu kontrol eder (default 20).
    """
    from app.models.exam_result import ExamResult
    from sqlalchemy import desc as _desc

    cutoff = date.today() - timedelta(days=since_days)
    rows = (
        db.query(ExamResult)
        .filter(
            ExamResult.student_id == student_id,
            ExamResult.exam_date >= cutoff,
        )
        .order_by(_desc(ExamResult.exam_date), _desc(ExamResult.created_at))
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for r in rows:
        section_str = (
            r.section.value if hasattr(r.section, "value")
            else (str(r.section) if r.section else None)
        )
        out.append({
            "title": r.title,
            "date_iso": r.exam_date.isoformat() if r.exam_date else None,
            "net": float(r.net) if r.net is not None else None,
            "correct": int(r.total_correct or 0),
            "wrong": int(r.total_wrong or 0),
            "blank": int(r.total_blank or 0),
            "section": section_str,
        })
    return out


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
    base_payload: dict[str, Any] = {
        "__template": "parent_weekly_report",
        "student_id": student.id,
        "student_name": student.full_name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "completed": completed,
        "planned": planned,
        "rate_pct": rate_pct,
        # Günlük detay + son deneme — template'in zenginleştirilmesi için
        "daily_breakdown": _build_daily_breakdown(
            db, student_id=student.id, week_start=week_start, week_end=week_end,
        ),
        "latest_exam": _get_latest_exam(db, student_id=student.id, since_days=7),
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
                {"type": "text", "text": _student_url_full(student.id)},
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
                {"type": "text", "text": _student_url_full(student.id)},
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

    `daily_breakdown` parametresi `event_triggers.on_program_published`'dan
    gelir (basit "gün → task_count" özeti). Producer bunu yok sayar ve
    `_build_daily_breakdown` ile **gün × görev kalemleri detaylı** veri
    çeker (ders + konu + planlanan soru sayısı). Eski callsite imzası
    bozulmasın diye parametre kaldırılmadı, sadece kullanılmıyor.

    M3 (yeniden tasarım): mail her gün için → kitap + bölüm + planlanan soru
    sayısı listesini gösterir. Altında son 90g denemeler tablosu (veya
    "deneme yok" notu) bulunur.
    """
    # _build_daily_breakdown weekly_report ile aynı kalıbı kullanır; bu mail
    # için "completed" alanı her zaman 0 (yeni program), şablonda gizlenir.
    detailed_breakdown = _build_daily_breakdown(
        db, student_id=student.id, week_start=week_start, week_end=week_end,
    )
    # daily_breakdown parametresi (event_triggers'tan eski format) artık atıl —
    # log için sayım amaçlı kullanılabilir ama mail içeriği detailed_breakdown'dan.
    _ = daily_breakdown

    base_payload: dict[str, Any] = {
        "__template": "parent_new_program",
        "student_id": student.id,
        "student_name": student.full_name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_tasks": total_tasks,
        # Detaylı gün-gün liste — şablon yeniden tasarımı bu formatla çalışır
        "daily_breakdown": detailed_breakdown,
        "recent_exams": _get_recent_exams(
            db, student_id=student.id, since_days=90, limit=20,
        ),
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
                {"type": "text", "text": _student_url_full(student.id)},
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
                {"type": "text", "text": _student_url_full(student.id)},
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
                {"type": "text", "text": _student_url_full(student.id)},
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
