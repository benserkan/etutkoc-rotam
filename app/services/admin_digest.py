"""Admin haftalık özet — veri toplama + gönderim servisi.

Cron her Pazartesi 09:00 UTC çalışır ve her aktif kurum için
build_weekly_digest_payload() ile özeti üretip e-posta gönderir.
İdempotency: aynı (institution, week_start) zaten varsa atlanır.

Snapshot UI'da arşiv olarak da gösterilir.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AdminWeeklyDigest,
    Institution,
    User,
    UserRole,
)
from app.services.cohort_analysis import (
    cohort_by_grade,
    cohort_by_track,
    institution_week_over_week,
)
from app.services.email_service import send_email
from app.services.risk_analysis import (
    bulk_risk_assessment,
    filter_at_risk,
)
from app.services.teacher_activity import inactive_teachers


logger = logging.getLogger(__name__)


# ---------------------------- Tarih yardımcıları ----------------------------


def _monday_of_week(d: date) -> date:
    """Verilen günün haftasının Pazartesi başlangıcı (0=Mon, 6=Sun)."""
    return d - timedelta(days=d.weekday())


def previous_week_start(today: date | None = None) -> date:
    """Geçen haftanın Pazartesi günü — rapor bu hafta için 'geçen hafta'."""
    if today is None:
        today = date.today()
    this_monday = _monday_of_week(today)
    return this_monday - timedelta(days=7)


# ---------------------------- Payload üretici ----------------------------


def build_weekly_digest_payload(
    db: Session,
    *,
    institution: Institution,
    week_end: date | None = None,
) -> dict[str, Any]:
    """Verilen kurum için haftalık özet payload'ı üret.

    week_end: hesaplama günü (default bugün). Hafta = son 7 gün (week_end dahil).
    Cron çağırırken week_end = today (Pazartesi sabahı önceki haftayı görür).
    """
    if week_end is None:
        week_end = date.today()
    week_start = week_end - timedelta(days=6)

    # 1) Kurum geneli kohort özeti — sınıf ve alan
    grade_cohorts = cohort_by_grade(db, institution_id=institution.id, today=week_end)
    track_cohorts = cohort_by_track(db, institution_id=institution.id, today=week_end)

    # 2) Week-over-week
    wow = institution_week_over_week(
        db, institution_id=institution.id, today=week_end,
    )

    # 3) Risk altındaki öğrenciler (özet sayım)
    teacher_ids_q = (
        db.query(User.id).filter(
            User.role == UserRole.TEACHER,
            User.institution_id == institution.id,
        )
    )
    teacher_ids = [t[0] for t in teacher_ids_q.all()]
    students = []
    if teacher_ids:
        students = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id.in_(teacher_ids),
                User.is_active.is_(True),
                User.is_paused.is_(False),   # pasif öğrenci digest sayımına dahil değil
            )
            .all()
        )
    student_total = len(students)
    risk_critical = risk_high = risk_medium = 0
    if students:
        assessments = bulk_risk_assessment(db, students=students, today=week_end)
        at_risk = filter_at_risk(assessments, min_level="medium")
        for a in at_risk:
            if a.level == "critical":
                risk_critical += 1
            elif a.level == "high":
                risk_high += 1
            elif a.level == "medium":
                risk_medium += 1

    # 4) Pasif öğretmenler (son 7 gün hiç login yok)
    inactives = inactive_teachers(
        db, institution_id=institution.id, days=7, today=week_end,
    )

    # 5) Toplam sayımlar
    teacher_total = len(teacher_ids)

    # En zor / en başarılı sınıf — bu hafta plan oranıyla
    best_grade = None
    worst_grade = None
    plan_having_grades = [c for c in grade_cohorts if c.weekly_rate_pct is not None]
    if plan_having_grades:
        best_grade = max(plan_having_grades, key=lambda c: c.weekly_rate_pct)
        worst_grade = min(plan_having_grades, key=lambda c: c.weekly_rate_pct)

    return {
        "institution_id": institution.id,
        "institution_name": institution.name,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "totals": {
            "student_count": student_total,
            "teacher_count": teacher_total,
            "inactive_teacher_count": len(inactives),
        },
        "completion": {
            "this_week_rate": wow.this_week_rate,
            "last_week_rate": wow.last_week_rate,
            "delta_pct": wow.delta_pct,
            "direction": wow.direction,
        },
        "at_risk": {
            "critical": risk_critical,
            "high": risk_high,
            "medium": risk_medium,
            "total": risk_critical + risk_high + risk_medium,
        },
        "highlight": {
            "best_grade_label": best_grade.cohort_label if best_grade else None,
            "best_grade_rate": best_grade.weekly_rate_pct if best_grade else None,
            "worst_grade_label": worst_grade.cohort_label if worst_grade else None,
            "worst_grade_rate": worst_grade.weekly_rate_pct if worst_grade else None,
        },
        "inactive_teachers": [
            {"id": t.id, "name": t.full_name, "email": t.email}
            for t in inactives[:5]   # ilk 5 — özet için yeter
        ],
        "grade_cohorts": [
            {
                "label": c.cohort_label,
                "n": c.student_count,
                "rate": c.weekly_rate_pct,
                "color": c.rate_color,
            }
            for c in grade_cohorts
        ],
        "track_cohorts": [
            {
                "label": c.cohort_label,
                "n": c.student_count,
                "rate": c.weekly_rate_pct,
                "color": c.rate_color,
            }
            for c in track_cohorts
        ],
    }


# ---------------------------- Gönderim ----------------------------


def send_admin_weekly_digest(
    db: Session,
    *,
    institution: Institution,
    week_end: date | None = None,
    force: bool = False,
) -> AdminWeeklyDigest:
    """Bir kurum için haftalık özet üret + e-posta gönder + DB'ye kaydet.

    - Idempotency: aynı (institution, week_start) için zaten satır varsa,
      force=False ise mevcut satırı döner (göndermez).
    - force=True: yeniden gönder (manuel "şimdi gönder" butonu için)

    Returns: AdminWeeklyDigest satırı (mevcut veya yeni oluşturulmuş).
    """
    if week_end is None:
        week_end = date.today()
    week_start = week_end - timedelta(days=6)

    existing = (
        db.query(AdminWeeklyDigest)
        .filter(
            AdminWeeklyDigest.institution_id == institution.id,
            AdminWeeklyDigest.week_start_date == week_start,
        )
        .first()
    )
    if existing and not force:
        logger.info(
            "admin_digest: skip — institution=%s, week=%s already sent (id=%s)",
            institution.id, week_start, existing.id,
        )
        return existing

    # Veriyi topla
    payload = build_weekly_digest_payload(
        db, institution=institution, week_end=week_end,
    )

    # Alıcı kurum admin'leri — aktif, e-posta sahibi (pasifler haftalık özet almaz)
    admins = (
        db.query(User)
        .filter(
            User.institution_id == institution.id,
            User.role == UserRole.INSTITUTION_ADMIN,
            User.is_active.is_(True),
            User.is_paused.is_(False),
        )
        .all()
    )
    admin_emails = [a.email for a in admins if a.email]

    # Kayıt güncelleme veya yeni oluşturma
    if existing:
        digest = existing
    else:
        digest = AdminWeeklyDigest(
            institution_id=institution.id,
            week_start_date=week_start,
            week_end_date=week_end,
        )
        db.add(digest)

    digest.payload_json = json.dumps(payload, ensure_ascii=False)
    digest.recipient_emails = "\n".join(admin_emails) if admin_emails else None
    digest.recipient_count = len(admin_emails)

    if not admin_emails:
        digest.send_status = "skipped_no_admin"
        digest.error_message = "Aktif institution_admin yok"
        db.commit()
        return digest

    # E-postaları gönder + Stage 6 kredi tüketimi (sadece gerçekten gönderilen)
    from app.models import UsageKind
    from app.services.credits import CreditOwner, record_usage
    owner = CreditOwner.for_institution(institution)
    sent_any = False
    failed_emails: list[str] = []
    for email in admin_emails:
        ctx = {
            "payload": payload,
            "institution": institution,
            "admin_email": email,
        }
        try:
            ok = send_email(
                to=email, template="admin_weekly_summary", ctx=ctx,
            )
            if ok:
                sent_any = True
                # Kredi düş — log_only'da tüketmeyiz (gerçek maliyet yok)
                try:
                    record_usage(
                        db, owner=owner, kind=UsageKind.EMAIL_SEND,
                        metadata={"template": "admin_weekly_summary", "to": email},
                        autocommit=False,
                    )
                except Exception as ce:
                    logger.warning("credit record_usage failed (non-fatal): %s", ce)
            else:
                # log_only mode: send_email False döner, hata yok
                pass
        except Exception as e:
            logger.exception("admin_digest send failed: %s", e)
            failed_emails.append(email)

    # Status set
    if failed_emails:
        digest.send_status = "failed"
        digest.error_message = "Failed for: " + ", ".join(failed_emails)
    elif sent_any:
        digest.send_status = "sent"
        digest.error_message = None
    else:
        # send_email log_only mode'da False döner — bunu hata sayma
        digest.send_status = "log_only"
        digest.error_message = None

    digest.sent_at = datetime.now(timezone.utc)
    db.commit()
    return digest
