"""Cron job fonksiyonları — kuyruğa bildirim atan scheduled aksiyonlar.

Her job: `def job(db: Session, *, now: datetime) -> dict`. Bildirim üretmez,
`enqueue_notification` çağırır. Asıl gönderim dispatcher'a aittir.

Kayıt: `JOB_REGISTRY` dict'ine `job_key → callable` eşlenir; cron_runner
tick'i `CronSchedule.job_key`'e bakıp bu sözlükten fonksiyonu bulur.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session, joinedload

from app.models import (
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentNotificationPref,
    ParentStudentLink,
    Task,
    TaskBookItem,
    User,
    UserRole,
)
from app.services.analytics import (
    daily_stats_for,
    week_stats_for,
    subject_breakdown,
)
from app.services.notification_producers import (
    produce_daily_summary,
    produce_drop_alert,
    produce_empty_day,
    produce_exam_approaching,
    produce_weekly_report,
)


# Faz 8: sınav yaklaşıyor eşikleri (gün cinsinden, sıralı). Cron her gün
# çalışır, days_left bu sette ise bir defaya mahsus bildirim gönderir.
EXAM_APPROACHING_THRESHOLDS: tuple[int, ...] = (30, 7, 1)


logger = logging.getLogger(__name__)


# ---------------------------- Yardımcılar ----------------------------


def _today_utc(now: datetime) -> date:
    return now.astimezone(timezone.utc).date()


def _has_recent_notification(
    db: Session, *, parent_id: int, student_id: int, kind: NotificationKind, within: timedelta
) -> bool:
    """Aynı veliye/öğrenciye/türe son N saatte/günde bildirim gitti mi?
    Spam koruması — örn günlük özetin aynı gün ikinci kez atılmasını engeller.
    """
    cutoff = datetime.now(timezone.utc) - within
    return (
        db.query(NotificationLog)
        .filter(
            NotificationLog.parent_id == parent_id,
            NotificationLog.student_id == student_id,
            NotificationLog.kind == kind,
            NotificationLog.status.in_([
                NotificationStatus.SENT, NotificationStatus.QUEUED,
            ]),
            NotificationLog.queued_at >= cutoff,
        )
        .first()
        is not None
    )


def _consecutive_empty_days(db: Session, student_id: int, today_date: date, lookback: int = 5) -> int:
    """Bugün dahil son N günde planlı ama tamamlanmamış (boş) gün sayısı (üst üste).

    "Üst üste boş gün uyarısı 3'ten sonra atma" mantığı için.
    """
    count = 0
    for i in range(lookback):
        d = today_date - timedelta(days=i)
        stats = daily_stats_for(db, student_id, d)
        if stats.planned > 0 and stats.completed == 0:
            count += 1
        else:
            break
    return count


def _parent_prefs_map(db: Session) -> dict[int, ParentNotificationPref]:
    rows = db.query(ParentNotificationPref).all()
    return {p.parent_id: p for p in rows}


def _all_parent_student_pairs(db: Session) -> list[tuple[User, User, ParentStudentLink]]:
    """Aktif (parent, student, link) üçlüleri."""
    links = (
        db.query(ParentStudentLink)
        .options(
            joinedload(ParentStudentLink.parent),
            joinedload(ParentStudentLink.student),
        )
        .all()
    )
    out = []
    for link in links:
        if not link.parent or not link.student:
            continue
        if not link.parent.is_active or not link.student.is_active:
            continue
        # is_paused: pasif öğrencinin velisine bildirim gitmez,
        # pasif velinin kendisi de bildirim almaz. Tek noktada
        # filtre — bu sayede tüm veli cron'ları (daily/empty/weekly/
        # drop/exam-approaching/new-program) otomatik susar.
        if link.parent.is_paused or link.student.is_paused:
            continue
        if link.parent.role != UserRole.PARENT or link.student.role != UserRole.STUDENT:
            continue
        out.append((link.parent, link.student, link))
    return out


# ---------------------------- Job: günlük özet + boş gün ----------------------------


def daily_summary(db: Session, *, now: datetime) -> dict:
    """Her aktif veli/öğrenci çifti için günlük özet bildirimi üret.

    İçerik:
      - planned > 0 ve completed > 0 → DAILY_SUMMARY (tamamlama yüzdesi)
      - planned > 0 ve completed = 0 → EMPTY_DAY (3 günden fazla üst üste ise atla)
      - planned = 0 → atla (gürültü)
    """
    today = _today_utc(now)
    pairs = _all_parent_student_pairs(db)
    counts = {"daily": 0, "empty": 0, "skipped_recent": 0, "skipped_streak": 0, "skipped_zero": 0}

    for parent, student, link in pairs:
        stats = daily_stats_for(db, student.id, today)

        if stats.planned == 0:
            counts["skipped_zero"] += 1
            continue

        if stats.completed > 0:
            # Aynı gün ikinci özet atma
            if _has_recent_notification(
                db, parent_id=parent.id, student_id=student.id,
                kind=NotificationKind.DAILY_SUMMARY, within=timedelta(hours=18),
            ):
                counts["skipped_recent"] += 1
                continue

            subjects = subject_breakdown(db, student.id)
            sb = [
                {
                    "subject": s["name"],
                    "completed": s["completed"],
                    "planned": s["completed"] + s["remaining"] + s["reserved"],
                    "unit": "test",
                }
                for s in subjects[:6]
            ]
            produce_daily_summary(
                db, parent=parent, student=student,
                completed=stats.completed, planned=stats.planned,
                subject_breakdown=sb,
            )
            counts["daily"] += 1
        else:
            # Boş gün uyarısı — ama 3 günden fazla üst üste ise sus
            streak = _consecutive_empty_days(db, student.id, today)
            if streak > 3:
                counts["skipped_streak"] += 1
                continue
            if _has_recent_notification(
                db, parent_id=parent.id, student_id=student.id,
                kind=NotificationKind.EMPTY_DAY, within=timedelta(hours=18),
            ):
                counts["skipped_recent"] += 1
                continue
            produce_empty_day(
                db, parent=parent, student=student,
                planned=stats.planned, consecutive_empty_days=streak,
            )
            counts["empty"] += 1

    db.flush()
    logger.info("daily_summary cron: %s", counts)
    return counts


# ---------------------------- Job: haftalık döngü-son backstop ----------------------------


def weekly_backstop(db: Session, *, now: datetime) -> dict:
    """Her gün gece 23:55 — son 7 günde haftalık rapor gönderilmemiş öğrenci varsa
    bunlar için weekly_report üret.

    Asıl trigger Sprint 8'de olay tabanlı: öğrencinin döngü-son gününde son
    görev işaretlendiği an. Bu cron backstop — düşmüş tetikleyicileri yakalar.

    Tek kural: bir öğrenciye 7 gün içinde 1 weekly_report yeterli.
    """
    today = _today_utc(now)
    pairs = _all_parent_student_pairs(db)
    counts = {"sent": 0, "skipped_recent": 0, "skipped_no_tasks": 0}

    for parent, student, link in pairs:
        if _has_recent_notification(
            db, parent_id=parent.id, student_id=student.id,
            kind=NotificationKind.WEEKLY_REPORT, within=timedelta(days=6),
        ):
            counts["skipped_recent"] += 1
            continue

        # Son 7 günde hiç görev yoksa hafta raporu da boş; atla
        week_start = today - timedelta(days=6)
        any_task = (
            db.query(Task.id)
            .filter(
                Task.student_id == student.id,
                Task.date >= week_start,
                Task.date <= today,
            )
            .first()
        )
        if not any_task:
            counts["skipped_no_tasks"] += 1
            continue

        wstats = week_stats_for(db, student.id, today)
        rate = (
            int(round(100 * wstats.completed / wstats.planned)) if wstats.planned > 0 else None
        )
        produce_weekly_report(
            db, parent=parent, student=student,
            week_start=week_start, week_end=today,
            completed=wstats.completed, planned=wstats.planned, rate_pct=rate,
        )
        counts["sent"] += 1

    db.flush()
    logger.info("weekly_backstop cron: %s", counts)
    return counts


# ---------------------------- Job: düşüş alarmı ----------------------------


def drop_alert(db: Session, *, now: datetime) -> dict:
    """Pazartesi 06:00 — geçen hafta vs önceki hafta tamamlama oranı kıyas.

    %30+ düşüş varsa DROP_ALERT enqueue. Veli pref'i kapalıysa producer suppresses.
    """
    today = _today_utc(now)
    last_week_end = today - timedelta(days=1)
    last_week_start = last_week_end - timedelta(days=6)
    prev_week_end = last_week_start - timedelta(days=1)
    prev_week_start = prev_week_end - timedelta(days=6)

    pairs = _all_parent_student_pairs(db)
    counts = {"sent": 0, "skipped_no_drop": 0, "skipped_no_data": 0, "skipped_recent": 0}

    for parent, student, link in pairs:
        if _has_recent_notification(
            db, parent_id=parent.id, student_id=student.id,
            kind=NotificationKind.DROP_ALERT, within=timedelta(days=6),
        ):
            counts["skipped_recent"] += 1
            continue

        last_w = week_stats_for(db, student.id, last_week_end)
        prev_w = week_stats_for(db, student.id, prev_week_end)

        # Veri yetersiz
        if last_w.planned == 0 or prev_w.planned == 0:
            counts["skipped_no_data"] += 1
            continue

        last_rate = last_w.completed / last_w.planned
        prev_rate = prev_w.completed / prev_w.planned
        drop = prev_rate - last_rate

        if prev_rate < 0.10 or drop < 0.30:
            counts["skipped_no_drop"] += 1
            continue

        produce_drop_alert(
            db, parent=parent, student=student,
            last_rate_pct=int(round(last_rate * 100)),
            prev_rate_pct=int(round(prev_rate * 100)),
            drop_pct=int(round(drop * 100)),
            last_week_label=f"{last_week_start.isoformat()} – {last_week_end.isoformat()}",
            prev_week_label=f"{prev_week_start.isoformat()} – {prev_week_end.isoformat()}",
        )
        counts["sent"] += 1

    db.flush()
    logger.info("drop_alert cron: %s", counts)
    return counts


# ---------------------------- Job: sınav yaklaşıyor (Faz 8) ----------------------------


def _exam_threshold_already_sent(
    db: Session,
    *,
    parent_id: int,
    student_id: int,
    threshold: int,
    exam_year: int,
) -> bool:
    """Bu (parent, student, threshold, exam_year) için EXAM_APPROACHING zaten
    gönderildi mi?

    Subject prefix `[D-{threshold}/Y{year}]` üzerinden LIKE ile sorgulanır. Bu
    işaret `produce_exam_approaching` tarafından konuyor; iki yer beraber
    değişmeli. Year suffix: aynı öğrenci 2 yıl üst üste mezun/12. sınıf
    kalırsa her yıl için ayrı kayıt — önceki yılın bildirimi yeni yılı
    bastırmaz.
    """
    marker = f"[D-{threshold}/Y{exam_year}]%"
    return (
        db.query(NotificationLog)
        .filter(
            NotificationLog.parent_id == parent_id,
            NotificationLog.student_id == student_id,
            NotificationLog.kind == NotificationKind.EXAM_APPROACHING,
            NotificationLog.subject.like(marker),
            NotificationLog.status.in_([
                NotificationStatus.SENT, NotificationStatus.QUEUED,
            ]),
        )
        .first()
        is not None
    )


def exam_approaching(db: Session, *, now: datetime) -> dict:
    """Her gün — efektif sınav tarihi {30, 7, 1} gün uzağa düşen öğrenciler için
    EXAM_APPROACHING bildirimi.

    İdempotency: aynı (parent, student, threshold) için bir kez. Yıl döndüğünde
    yeniden hak kazanır mı? — Hayır; aynı subject prefix'iyle önceden satır varsa
    geçilir. Pratikte: bir sınav cycle'ı bittikten sonra öğrenci bir sonraki
    yıla aynı target ile kalırsa farklı `student_id` veya farklı threshold
    eşleşmesiyle yeni satır üretir; aynı student_id+aynı threshold yıllar
    sonra bile gönderilmiş kalır. Mevcut kullanım için bu kabul edilebilir
    (üst üste 2 yıl YKS kalan mezun için yeniden bildirim istenirse subject
    suffix'ine year ekleyip filtreyi sıkılaştırmak gerekir).

    Hedef sınavı olmayan (5-7, 9-11) öğrenciler atlanır.
    """
    today = _today_utc(now)
    pairs = _all_parent_student_pairs(db)
    counts = {
        "sent": 0,
        "skipped_no_target": 0,
        "skipped_no_date": 0,
        "skipped_past": 0,
        "skipped_far": 0,
        "skipped_already": 0,
    }

    for parent, student, link in pairs:
        target = student.effective_exam_target  # 'LGS' / 'YKS' / None
        if target is None:
            counts["skipped_no_target"] += 1
            continue
        exam_date = student.effective_exam_date
        if exam_date is None:
            counts["skipped_no_date"] += 1
            continue
        days_left = (exam_date - today).days
        if days_left < 0:
            counts["skipped_past"] += 1
            continue
        if days_left not in EXAM_APPROACHING_THRESHOLDS:
            counts["skipped_far"] += 1
            continue
        if _exam_threshold_already_sent(
            db,
            parent_id=parent.id,
            student_id=student.id,
            threshold=days_left,
            exam_year=exam_date.year,
        ):
            counts["skipped_already"] += 1
            continue
        produce_exam_approaching(
            db,
            parent=parent,
            student=student,
            days_left=days_left,
            threshold=days_left,
            exam_label=student.effective_exam_label,
            exam_date=exam_date,
        )
        counts["sent"] += 1

    db.flush()
    logger.info("exam_approaching cron: %s", counts)
    return counts


# ---------------------------- Admin haftalık özet ----------------------------


def admin_weekly_digest(db: Session, *, now: datetime) -> dict:
    """Her aktif kurum için haftalık yönetici özeti gönder.

    Idempotency: aynı (institution, week_start) için 2. kez gönderilmez.
    Cron Pazartesi 09:00 UTC'de çalışır → "geçen hafta" özeti hazır.
    Stage 7: weekly_admin_digest flag KAPALIYSA hiç çalışmaz; per-kurum
    override KAPALIYSA o kurum atlanır.
    """
    from app.models import Institution
    from app.services.admin_digest import send_admin_weekly_digest
    from app.services.feature_flags import is_enabled

    today = now.astimezone(timezone.utc).date()

    # Stage 7 — global flag kontrolü
    if not is_enabled(db, "weekly_admin_digest"):
        logger.info("admin_weekly_digest cron: global flag KAPALI, atlandı")
        return {"skipped": "feature_flag_global_disabled", "total_institutions": 0}

    institutions = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .all()
    )
    counts = {"sent": 0, "skipped_duplicate": 0, "skipped_no_admin": 0,
              "log_only": 0, "failed": 0, "skipped_flag": 0,
              "total_institutions": len(institutions)}
    for inst in institutions:
        # Stage 7 — per-kurum override kontrolü
        if not is_enabled(db, "weekly_admin_digest", institution=inst):
            counts["skipped_flag"] += 1
            continue
        try:
            digest = send_admin_weekly_digest(
                db, institution=inst, week_end=today, force=False,
            )
            status = digest.send_status
            if status == "sent":
                counts["sent"] += 1
            elif status == "log_only":
                counts["log_only"] += 1
            elif status == "skipped_no_admin":
                counts["skipped_no_admin"] += 1
            elif status == "failed":
                counts["failed"] += 1
            else:
                # 'pending' (yeni satır ama gönderim henüz başlamadı) — burada olmamalı
                pass
        except Exception as e:
            logger.exception(
                "admin_weekly_digest cron: institution=%s hata: %s",
                inst.id, e,
            )
            counts["failed"] += 1
    logger.info("admin_weekly_digest cron: %s", counts)
    return counts


# ---------------------------- Audit log retention ----------------------------


# Audit log saklama süresi — bu yaştan eski kayıtlar silinir.
# Forensic değer + DB boyutu dengesi: 6 ay ortalama.
AUDIT_LOG_RETENTION_DAYS = 180


def audit_cleanup(db: Session, *, now: datetime) -> dict:
    """AUDIT_LOG_RETENTION_DAYS'dan eski audit kayıtlarını sil.

    Bu job kalıcı veriyi silen TEK cron job — geri alınamaz. retention
    suresinden önce çalışırsa veri kaybı. Bu yüzden:
    - retention sabiti açıkça tanımlı (üstte)
    - silinen sayıyı log'a yaz (operatöre güven için)
    - DELETE öncesi count() ile doğrula

    Çalışma sıklığı: Günde 1 kez (gece 03:00 UTC) yeterli — audit log INSERT
    yoğun değil, hourly cron overkill.
    """
    from app.models import AuditLog
    cutoff = now - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
    # Önce kaç kayıt etkilenecek say (operatör gözle kontrol için)
    n_to_delete = (
        db.query(AuditLog).filter(AuditLog.created_at < cutoff).count()
    )
    if n_to_delete == 0:
        logger.info("audit_cleanup: silinecek kayıt yok (cutoff=%s)", cutoff.isoformat())
        return {"deleted": 0, "cutoff": cutoff.isoformat(), "retention_days": AUDIT_LOG_RETENTION_DAYS}

    deleted = (
        db.query(AuditLog)
        .filter(AuditLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.flush()
    logger.info(
        "audit_cleanup: %d kayıt silindi (cutoff=%s, retention=%dgün)",
        deleted, cutoff.isoformat(), AUDIT_LOG_RETENTION_DAYS,
    )
    return {
        "deleted": deleted,
        "cutoff": cutoff.isoformat(),
        "retention_days": AUDIT_LOG_RETENTION_DAYS,
    }


# ---------------------------- Job registry ----------------------------


# ---------------------------- Stage 6 — kredi aylık refill ----------------------------


# ---------------------------- Stage 9 (Faz 2) — Plan trial expire ----------------------------


def trial_expire(db: Session, *, now: datetime) -> dict:
    """Süresi dolmuş trial'ları otomatik post_trial_plan'a düşür + trial bildirimleri.

    Günlük çalışır (00:15 UTC). Hem bağımsız öğretmen (14g) hem kurum (30g)
    trial'larını izler. İdempotent: zaten geçmişse no-op.

    Ek (2026-05-22): son 3 gün hatırlatma (e-posta + otomatik teklif) + bitiş
    e-postası. Yeni cron/migration yok — bu mevcut job'a bağlandı.
    """
    from app.services.plans import expire_trials
    from app.services import trial_notifications as tn

    reminders = 0
    try:
        reminders = tn.send_trial_reminders(db, now=now)
    except Exception:
        logger.exception("trial_expire: reminders fail")

    result = expire_trials(db, now=now)

    expired_emails = 0
    try:
        expired_emails = tn.notify_trial_expired(
            db, user_ids=result.get("expired_user_ids", []),
        )
    except Exception:
        logger.exception("trial_expire: expired emails fail")

    renewals = {"reminded": 0, "past_due": 0}
    try:
        renewals = tn.process_renewals(db, now=now)
    except Exception:
        logger.exception("trial_expire: renewals fail")

    result["reminders_sent"] = reminders
    result["expired_emails"] = expired_emails
    result["renewals_reminded"] = renewals["reminded"]
    result["renewals_past_due"] = renewals["past_due"]
    return result


def dunning_send_reminders(db: Session, *, now: datetime) -> dict:
    """Cron: tüm uygun faturalar için ödeme hatırlatma aşaması tetikle.

    Günlük 09:00 UTC (TR 12:00). Her aşama bir kez gönderilir.
    """
    from app.services.dunning import run_dunning_for_all
    return run_dunning_for_all(db, autocommit=True)


def health_snapshot_daily(db: Session, *, now: datetime) -> dict:
    """Cron: tüm aktif kurumlar için günlük sağlık skoru snapshot'ı kaydet.

    Günlük 03:00 UTC. Sprint F.1 — Sağlık Skoru 2.0. "7 gün düşüş" + "öğretmen
    kaybı" tetikleyicilerinin geçmiş karşılaştırması bu snapshot'lardan yapılır.
    İdempotent — aynı (institution, date) için UPDATE eder.
    """
    from app.services.health_score_v2 import record_daily_snapshots
    return record_daily_snapshots(db, snapshot_date=now.date(), autocommit=True)


def invoices_mark_overdue(db: Session, *, now: datetime) -> dict:
    """Cron: vadesi geçmiş PENDING faturaları OVERDUE'ya geçir.

    Günlük 02:30 UTC. Sprint A.2 — ödeme takvimi banner ve drill için
    bucket sınıflandırmasının doğru olması için PENDING + due_at < now
    olan kayıtları OVERDUE'ye taşır. İdempotent.
    """
    from app.services.revenue_panel import mark_overdue
    changed = mark_overdue(db, autocommit=True)
    return {"marked_overdue": changed}


def kvkk_apply_expired_deletions(db: Session, *, now: datetime) -> dict:
    """Cron: 30g grace period'u dolmuş silme taleplerini uygular.

    Günlük 02:00 UTC. PROCESSING durumundaki delete talepleri için
    process_after <= now ise apply_deletion çağrılır (kullanıcı anonimleştirilir).
    İdempotent — bir kez uygulanan kayıt COMPLETED'a geçer.
    """
    from app.services.kvkk import cron_apply_expired_deletions
    return cron_apply_expired_deletions(db, now=now)


def subscription_resume(db: Session, *, now: datetime) -> dict:
    """Cron: pause_until'i geçmiş kurumları otomatik akademik yıla resume eder.

    Her gün 01:00 UTC. İdempotent — hâlâ pause süresi devam eden kurumlar
    atlanır. Yaz pause'dan Eylül'de otomatik dönüş için.
    """
    from app.services.subscription import cron_resume_paused_subscriptions
    return cron_resume_paused_subscriptions(db, now=now)


def subscription_guarantee_eval(db: Session, *, now: datetime) -> dict:
    """Cron: 60g performans garantisi olan kurumları haftalık değerlendir.

    Pazartesi 06:00 UTC. 60 gün geçen kurumlarda tamamlama oranı eşiğin
    altındaysa 1 ay uzatma uygulanır (tek seferlik). İdempotent.
    """
    from app.services.subscription import cron_evaluate_guarantees
    today = now.astimezone(timezone.utc).date()
    if today.weekday() != 0:    # 0=Pazartesi
        return {"skipped": "not_monday", "today": today.isoformat()}
    return cron_evaluate_guarantees(db, now=now)


def addons_monthly_renewal(db: Session, *, now: datetime) -> dict:
    """Cron: dönemi biten auto_renew=True add-on'ları yeni aya yenile.

    Cron her gün 00:30 UTC çalışır; sadece ayın 1'inde efektif iş yapar
    (credits_monthly_refill ile paralel pattern). İdempotent: aynı (owner,
    kind, period_start) için satır varsa atlanır. AI_PLUS yenilenirken
    CreditAccount.bonus_credits +1000 eklenir.
    """
    from app.services.addons import monthly_addon_renewal
    today = now.astimezone(timezone.utc).date()
    if today.day != 1:
        logger.debug(
            "addons_monthly_renewal skipped (day=%s, only runs on day 1)",
            today.day,
        )
        return {"skipped": "not_first_of_month", "today": today.isoformat()}
    return monthly_addon_renewal(db, now=now)


def credits_monthly_refill(db: Session, *, now: datetime) -> dict:
    """Her ayın 1'inde tüm aktif kurum + bağımsız öğretmene yeni period satırı.

    Cron her gün 00:30 UTC çalışır; sadece ayın 1. gününde efektif iş yapar
    (cron_schedules tablosunda day_of_month yok, bu yüzden "günlük çalış,
    kendin filtre uygula" yaklaşımı). İdempotent: aynı period için satır
    varsa atlanır.

    İlk satırlar zaten lazy-create ediliyor (get_or_create_account on demand);
    bu cron sadece "henüz hiç kullanım yapmamış" sahipler için yeni period
    satırını açar — UI'da "0 / 50 kredi" görmek için.
    """
    from app.services.credits import monthly_refill
    today = now.astimezone(timezone.utc).date()
    if today.day != 1:
        logger.debug("credits_monthly_refill skipped (day=%s, only runs on day 1)", today.day)
        return {"skipped": "not_first_of_month", "today": today.isoformat()}
    return monthly_refill(db, now=now)


def auto_pause_inactive_users(db: Session, *, now: datetime) -> dict:
    """Sessizleşen öğrenci/öğretmenleri otonom pasifleştir.

    Eşik: öğrenci 21 gün, öğretmen 30 gün canlı sinyalsizse pasif.
    Sinyaller: last_login_at + son tamamlanan görev + son oluşturulan görev.
    Yeni hesap 14 gün, manuel resume sonrası 7 gün cooldown.
    Panik koruyucu: aktif kullanıcının %5'inden fazlasını tek seferde pause etmez.

    İlgili kayıtları audit log'a (USER_AUTO_PAUSE, actor=NULL) düşürür.
    """
    from app.models import AuditAction, UserRole
    from app.services.audit import log_action
    from app.services.pause import (
        DAILY_AUTO_PAUSE_RATIO_LIMIT,
        find_auto_pause_candidates,
        pause_user,
        REASON_AUTO_INACTIVITY,
    )

    candidates = find_auto_pause_candidates(db, now=now)
    if not candidates:
        return {"candidates": 0, "paused": 0}

    active_total = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            User.is_paused.is_(False),
            User.role.in_([UserRole.STUDENT, UserRole.TEACHER]),
        )
        .count()
    )
    # %5 panik koruyucu — en az 1 izin ver (küçük setlerde de çalışsın)
    daily_limit = max(1, int(active_total * DAILY_AUTO_PAUSE_RATIO_LIMIT))
    to_pause = candidates[:daily_limit]
    over_limit = len(candidates) - len(to_pause)

    paused_count = 0
    errors: list[str] = []
    for user, last_signal in to_pause:
        try:
            pause_user(db, user, actor=None, reason=REASON_AUTO_INACTIVITY)
            log_action(
                db,
                action=AuditAction.USER_AUTO_PAUSE,
                actor_id=None,
                target_type="user",
                target_id=user.id,
                details={
                    "role": user.role.value,
                    "reason": REASON_AUTO_INACTIVITY,
                    "last_signal_at": last_signal.isoformat() if last_signal else None,
                },
            )
            paused_count += 1
        except Exception as e:  # noqa: BLE001 - cron üst seviye
            errors.append(f"user={user.id}: {e}")
            logger.warning("auto_pause failed for user %s: %s", user.id, e)

    return {
        "candidates": len(candidates),
        "paused": paused_count,
        "over_limit_skipped": over_limit,
        "daily_limit": daily_limit,
        "errors": errors,
    }


# ---------------------------- Katman 11.J — Güvenlik Kamerası cron'ları ----------------------------


def security_alarm_evaluate(db: Session, *, now: datetime) -> dict:
    """5 dakikada bir alarm motorunu çalıştır.

    Tüm enabled AlarmRule'lar değerlendirilir; eşik aşılırsa AlarmEvent +
    email süper adminlere. Cooldown alarm_engine içinde uygulanır.
    """
    from app.services.alarm_engine import evaluate_all
    results = evaluate_all(db)
    triggered = sum(1 for r in results if r.triggered)
    return {
        "rules_evaluated": len(results),
        "triggered": triggered,
        "skipped_cooldown": sum(1 for r in results if r.skipped_reason == "cooldown"),
        "skipped_disabled": sum(1 for r in results if r.skipped_reason == "disabled"),
    }


def abuse_scan(db: Session, *, now: datetime) -> dict:
    """Saatlik abuse tespiti taraması.

    4 dedektör (mass_invitation, mass_notification, multi_account, unsubscribe_spike)
    çalıştırır; eşik aşılan kayıtlar AbuseSignal'a upsert edilir (24h dedup).
    """
    from app.services.abuse_detection import run_all
    summary = run_all(db)
    return {"detector_hits": summary, "total_hits": sum(summary.values())}


# Retention sabitleri
ERROR_EVENT_RETENTION_DAYS = 30
SLOW_REQUEST_RETENTION_DAYS = 7


def error_event_retention(db: Session, *, now: datetime) -> dict:
    """30 günden eski resolved hata gruplarını sil. DB şişmesini önler.

    Sadece resolved kayıtlar silinir — open hatalar korunur (henüz tetiklenirler).
    """
    from app.models import ErrorEvent
    cutoff = now - timedelta(days=ERROR_EVENT_RETENTION_DAYS)
    n_to_delete = (
        db.query(ErrorEvent)
        .filter(
            ErrorEvent.resolved_at.isnot(None),
            ErrorEvent.last_seen_at < cutoff,
        )
        .count()
    )
    deleted = (
        db.query(ErrorEvent)
        .filter(
            ErrorEvent.resolved_at.isnot(None),
            ErrorEvent.last_seen_at < cutoff,
        )
        .delete(synchronize_session=False)
    )
    db.flush()
    logger.info(
        "error_event_retention: %d resolved kayıt silindi (cutoff=%s)",
        deleted, cutoff.isoformat(),
    )
    return {
        "deleted": deleted,
        "found": n_to_delete,
        "cutoff": cutoff.isoformat(),
        "retention_days": ERROR_EVENT_RETENTION_DAYS,
    }


def slow_request_retention(db: Session, *, now: datetime) -> dict:
    """7 günden eski yavaş request log'larını sil (append-only tablo, hızla büyür)."""
    from app.models import SlowRequestLog
    cutoff = now - timedelta(days=SLOW_REQUEST_RETENTION_DAYS)
    n_to_delete = (
        db.query(SlowRequestLog)
        .filter(SlowRequestLog.recorded_at < cutoff)
        .count()
    )
    deleted = (
        db.query(SlowRequestLog)
        .filter(SlowRequestLog.recorded_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.flush()
    logger.info(
        "slow_request_retention: %d kayıt silindi (cutoff=%s)",
        deleted, cutoff.isoformat(),
    )
    return {
        "deleted": deleted,
        "found": n_to_delete,
        "cutoff": cutoff.isoformat(),
        "retention_days": SLOW_REQUEST_RETENTION_DAYS,
    }


def security_integrity_scan(db: Session, *, now: datetime) -> dict:
    """Günlük veri bütünlüğü taraması (orphan + KVKK SLA + cron drift özeti).

    Sadece tespit yapar, otomatik düzeltme yok. Bulgu varsa
    `last_error` field'ına özet yazılır (cron sağlık panosunda görülür).
    """
    from app.services.data_integrity import (
        kvkk_sla_check,
        orphan_scan,
    )
    orph = orphan_scan(db, limit=10)
    sla = kvkk_sla_check(db)
    summary = {
        "orphan_findings": orph["total_findings"],
        "kvkk_overdue": sla["overdue_count"],
        "kvkk_open": sla["open_total"],
    }
    # Bulgular varsa hatayı işaretle (cron_runner success/fail mantığını
    # bozmaz — exception fırlatmıyoruz; sadece dönen dict'te raporluyoruz).
    return summary


def offers_expire(db: Session, *, now: datetime) -> dict:
    """Günlük: süresi dolmuş SENT teklifleri EXPIRED'a çek (toplu süpürme).

    Teklif görüntülenince zaten lazy expire oluyordu (offers.describe_offer); ama
    hiç açılmamış süresi-geçmiş teklifler SENT kalıp admin gelir/funnel sayımını
    şişiriyordu. Bu cron o boşluğu kapatır."""
    from app.services.offers import expire_old_offers
    return expire_old_offers(db, autocommit=True)


def feature_discovery_scan(db: Session, *, now: datetime) -> dict:
    """Haftalık Vitrin Kartları otomatik keşfi — son migration + commit'leri tarar,
    yeni özellikler için DRAFT keşif kartı açar (idempotent). Süper admin keşif
    kuyruğunda inceleyip yayınlar. Manuel 'Şimdi tara' butonuyla aynı servisi
    paylaşır (feature_discovery.run_scan)."""
    from app.services import feature_discovery as fd
    counts = fd.run_scan(db, actor_id=None, days=120)
    logger.info("feature_discovery_scan: %s", counts)
    return {
        "created": counts.get("created", 0),
        "skipped": counts.get("skipped", 0),
        "candidates": counts.get("candidates", 0),
    }


JOB_REGISTRY: dict[str, Callable[[Session], dict]] = {
    "daily_summary": daily_summary,
    "weekly_backstop": weekly_backstop,
    "drop_alert": drop_alert,
    "exam_approaching": exam_approaching,
    "audit_cleanup": audit_cleanup,
    "admin_weekly_digest": admin_weekly_digest,
    "credits_monthly_refill": credits_monthly_refill,
    "trial_expire": trial_expire,
    "invoices_mark_overdue": invoices_mark_overdue,  # Sprint A.2 — ödeme takvimi
    "dunning_send_reminders": dunning_send_reminders,  # Sprint C — dunning zinciri
    "health_snapshot_daily": health_snapshot_daily,  # Sprint F.1 — sağlık snapshot
    "addons_monthly_renewal": addons_monthly_renewal,
    "subscription_resume": subscription_resume,
    "subscription_guarantee_eval": subscription_guarantee_eval,
    "kvkk_apply_expired_deletions": kvkk_apply_expired_deletions,
    "auto_pause_inactive_users": auto_pause_inactive_users,
    # Katman 11.J — Güvenlik Kamerası
    "security_alarm_evaluate": security_alarm_evaluate,
    "abuse_scan": abuse_scan,
    "error_event_retention": error_event_retention,
    "slow_request_retention": slow_request_retention,
    "security_integrity_scan": security_integrity_scan,
    # Vitrin Kartları otomatik keşfi (haftalık)
    "feature_discovery_scan": feature_discovery_scan,
    # Kopuk-cron düzeltmeleri (2026-05-24): schedule'ı eksik olanlar
    "offers_expire": offers_expire,
}
