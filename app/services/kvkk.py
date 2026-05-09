"""Stage 10 — KVKK servis katmanı.

KVKK madde 11 hakları:
- Kişisel verisinin işlenip işlenmediğini öğrenme
- Hangi amaçlarla kullanıldığını bilme
- Yurt içi/dışı aktarılan üçüncü kişileri bilme
- Eksik/yanlış işlenmişse düzeltilmesini isteme
- KVKK madde 7'deki şartlar çerçevesinde silinmesini/yok edilmesini isteme
- (Yukarıdakilerin) üçüncü kişilere bildirilmesini isteme
- Otomatize sistemler aracılığıyla aleyhe çıkan sonuçlara itiraz etme
- Kanuna aykırı işleme nedeniyle zarar uğranması hâlinde tazminat talep etme

Bu modül 3 ana akışı yönetir:
1. **Veri ihracı (export)** — `generate_user_export(user)` JSON-serializable dict
   üretir; kullanıcı kendi verisini indirir
2. **Silme talebi (RTBF)** — `request_deletion(user)` 30g grace period'lu kayıt
   açar; `apply_deletion(request)` anonimleştirir; cron expired'leri uygular
3. **Düzeltme** — şu an yalnız manuel akış (admin paneli)

Anonimleştirme stratejisi (silme):
- full_name="(Silinen Kullanıcı)", email="anonymized-{request_id}@kvkk.local"
- password_hash null'lanır → hesap login edemez
- is_active=False
- profil alanları (telefon, vs.) clear
- AuditLog/Tasks/Notifications gibi etkinlik kayıtları KORUNUR (anonimize
  edilmiş kullanıcıya bağlı kalır — istatistik bütünlüğü için, ad alanı
  zaten silindi)
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AuditAction,
    AuditLog,
    DELETE_GRACE_PERIOD_DAYS,
    DataRequestKind,
    DataRequestStatus,
    DataSubjectRequest,
    Institution,
    NotificationLog,
    ParentNotificationPref,
    ParentSessionLog,
    ParentStudentLink,
    PlanChangeHistory,
    Task,
    TeacherNoteToParent,
    User,
    UserRole,
)
from app.services.audit import log_action


logger = logging.getLogger(__name__)


# ============================ Veri ihracı ============================


def _user_to_dict(user: User) -> dict[str, Any]:
    """Kullanıcı satırının dış dünyaya dönecek hâli — password REDACTED."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if user.role else None,
        "institution_id": user.institution_id,
        "teacher_id": user.teacher_id,
        "is_active": user.is_active,
        "must_change_password": user.must_change_password,
        "password_changed_at": user.password_changed_at.isoformat() if user.password_changed_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "plan": getattr(user, "plan", None),
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
        "post_trial_plan": user.post_trial_plan,
        # Hassas alanlar
        "password_hash": "REDACTED",
    }


def generate_user_export(
    db: Session, *, user: User, requester: User | None = None,
) -> dict[str, Any]:
    """Bir kullanıcının kişisel verisinin tam ihracı — JSON-serializable dict.

    Kapsam (rolüne göre):
    - profile (her zaman)
    - audit_logs (kendisi aktör veya target — last 1 year)
    - login_history (kendi LOGIN_SUCCESS/FAILED kayıtları)
    - tasks (öğrenci ise kendi tasks)
    - notifications (parent/student ise ilgili NotificationLog)
    - parent_links (parent ise children, student ise parents)
    - plan_history (teacher ise kendi plan değişimleri)
    """
    payload: dict[str, Any] = {
        "schema_version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": requester.id if requester else user.id,
        "data_subject": _user_to_dict(user),
    }

    # Audit logs — kendisi aktör veya target
    audit_rows = (
        db.query(AuditLog)
        .filter(
            (AuditLog.actor_id == user.id)
            | ((AuditLog.target_type == "user") & (AuditLog.target_id == user.id))
        )
        .order_by(AuditLog.created_at.desc())
        .limit(500)
        .all()
    )
    payload["audit_logs"] = [
        {
            "id": a.id,
            "action": a.action.value,
            "actor_id": a.actor_id,
            "target_type": a.target_type,
            "target_id": a.target_id,
            "ip_address": a.ip_address,
            "user_agent": a.user_agent,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "details": json.loads(a.details_json) if a.details_json else None,
        }
        for a in audit_rows
    ]

    # Plan geçmişi (kendi teacher kaydı için)
    if user.role == UserRole.TEACHER:
        from app.models import PlanOwnerType
        plan_rows = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_type == PlanOwnerType.USER,
                PlanChangeHistory.owner_id == user.id,
            )
            .order_by(PlanChangeHistory.occurred_at.desc())
            .all()
        )
        payload["plan_history"] = [
            {
                "id": p.id,
                "from_plan": p.from_plan,
                "to_plan": p.to_plan,
                "reason": p.reason.value,
                "actor_user_id": p.actor_user_id,
                "note": p.note,
                "occurred_at": p.occurred_at.isoformat() if p.occurred_at else None,
            }
            for p in plan_rows
        ]
    else:
        payload["plan_history"] = []

    # Öğrenci ise kendi task'leri (son 6 ay)
    if user.role == UserRole.STUDENT:
        cutoff = datetime.now(timezone.utc) - timedelta(days=180)
        tasks = (
            db.query(Task)
            .filter(
                Task.student_id == user.id,
                Task.created_at >= cutoff,
            )
            .order_by(Task.created_at.desc())
            .limit(2000)
            .all()
        )
        payload["tasks"] = [
            {
                "id": t.id,
                "type": t.type.value if t.type else None,
                "title": t.title,
                "date": t.date.isoformat() if t.date else None,
                "status": t.status.value if t.status else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]
    else:
        payload["tasks"] = []

    # Veli/öğrenci linkleri
    if user.role == UserRole.PARENT:
        links = (
            db.query(ParentStudentLink)
            .filter(ParentStudentLink.parent_id == user.id)
            .all()
        )
    elif user.role == UserRole.STUDENT:
        links = (
            db.query(ParentStudentLink)
            .filter(ParentStudentLink.student_id == user.id)
            .all()
        )
    else:
        links = []
    payload["parent_student_links"] = [
        {
            "id": l.id,
            "parent_id": l.parent_id,
            "student_id": l.student_id,
            "relation": l.relation.value if l.relation else None,
            "is_primary": l.is_primary,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in links
    ]

    # Veli bildirim tercihleri
    if user.role == UserRole.PARENT:
        pref = (
            db.query(ParentNotificationPref)
            .filter(ParentNotificationPref.parent_id == user.id)
            .first()
        )
        payload["notification_preferences"] = (
            {
                "daily_summary_enabled": pref.daily_summary_enabled,
                "weekly_report_enabled": pref.weekly_report_enabled,
                "empty_day_alert_enabled": pref.empty_day_alert_enabled,
                "drop_alert_enabled": pref.drop_alert_enabled,
                "new_program_alert_enabled": pref.new_program_alert_enabled,
                "teacher_note_enabled": pref.teacher_note_enabled,
                "exam_approaching_enabled": pref.exam_approaching_enabled,
                "whatsapp_enabled": pref.whatsapp_enabled,
                "whatsapp_phone": pref.whatsapp_phone,
                "whatsapp_phone_verified_at": (
                    pref.whatsapp_phone_verified_at.isoformat()
                    if pref.whatsapp_phone_verified_at else None
                ),
                "quiet_hours_start": str(pref.quiet_hours_start) if pref.quiet_hours_start else None,
                "quiet_hours_end": str(pref.quiet_hours_end) if pref.quiet_hours_end else None,
                "unsubscribed_at": pref.unsubscribed_at.isoformat() if pref.unsubscribed_at else None,
                "updated_at": pref.updated_at.isoformat() if pref.updated_at else None,
            }
            if pref else None
        )

        # Bildirim logları (parent_id eşleşen)
        notif_rows = (
            db.query(NotificationLog)
            .filter(NotificationLog.parent_id == user.id)
            .order_by(NotificationLog.queued_at.desc())
            .limit(500)
            .all()
        )
        payload["notification_logs"] = [
            {
                "id": n.id,
                "kind": n.kind.value if n.kind else None,
                "channel": n.channel.value if n.channel else None,
                "status": n.status.value if n.status else None,
                "subject": n.subject,
                "queued_at": n.queued_at.isoformat() if n.queued_at else None,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "delivered_at": n.delivered_at.isoformat() if n.delivered_at else None,
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in notif_rows
        ]
    else:
        payload["notification_preferences"] = None
        payload["notification_logs"] = []

    # Kurum bilgisi (varsa, public alanlar)
    if user.institution_id:
        inst = db.get(Institution, user.institution_id)
        if inst:
            payload["institution"] = {
                "id": inst.id,
                "name": inst.name,
                "slug": inst.slug,
            }

    return payload


def export_to_json(payload: dict[str, Any], indent: int = 2) -> str:
    """JSON-serialize wrapper."""
    return json.dumps(payload, ensure_ascii=False, indent=indent, default=str)


# ============================ Talep akışı ============================


def request_export(
    db: Session, *, target: User, requester: User | None = None,
    reason: str | None = None, autocommit: bool = True,
) -> DataSubjectRequest:
    """Yeni veri ihracı talebi oluştur.

    Export anlık üretilebildiği için bu talep aynı transaction'da
    'completed' edilebilir; payload_json snapshot olarak yazılır.
    İleride büyük tenant'lar için async hâle getirilebilir.
    """
    if requester is None:
        requester = target

    payload = generate_user_export(db, user=target, requester=requester)
    req = DataSubjectRequest(
        kind=DataRequestKind.EXPORT,
        status=DataRequestStatus.COMPLETED,
        requester_user_id=requester.id,
        target_user_id=target.id,
        institution_id=target.institution_id,
        reason=reason,
        processed_by_user_id=requester.id,
        processed_at=datetime.now(timezone.utc),
        payload_json=export_to_json(payload),
    )
    db.add(req)
    db.flush()

    if autocommit:
        db.commit()
    logger.info(
        "request_export: target=%s requester=%s req_id=%s",
        target.id, requester.id, req.id,
    )
    return req


def request_deletion(
    db: Session, *, target: User, requester: User | None = None,
    reason: str | None = None, autocommit: bool = True,
) -> DataSubjectRequest:
    """Silme (RTBF) talebi aç — 30g grace period'lu.

    Talep DataRequestStatus.PROCESSING ile başlar; process_after = now + 30g.
    Bu süre içinde kullanıcı `cancel_request` ile iptal edebilir. Süre
    dolduğunda `apply_deletion` (cron veya manuel admin tarafından) çağrılır.

    Aynı target için bekleyen talep varsa idempotent (mevcut kaydı döner).
    """
    if requester is None:
        requester = target

    # Idempotency: bekleyen aktif silme talebi varsa onu döndür
    existing = (
        db.query(DataSubjectRequest)
        .filter(
            DataSubjectRequest.target_user_id == target.id,
            DataSubjectRequest.kind == DataRequestKind.DELETE,
            DataSubjectRequest.status.in_([
                DataRequestStatus.PENDING, DataRequestStatus.PROCESSING,
            ]),
        )
        .first()
    )
    if existing is not None:
        return existing

    now = datetime.now(timezone.utc)
    req = DataSubjectRequest(
        kind=DataRequestKind.DELETE,
        status=DataRequestStatus.PROCESSING,
        requester_user_id=requester.id,
        target_user_id=target.id,
        institution_id=target.institution_id,
        reason=reason,
        process_after=now + timedelta(days=DELETE_GRACE_PERIOD_DAYS),
    )
    db.add(req)
    db.flush()

    if autocommit:
        db.commit()
    logger.info(
        "request_deletion: target=%s req_id=%s process_after=%s",
        target.id, req.id, req.process_after.isoformat(),
    )
    return req


def cancel_request(
    db: Session, *, request_id: int, by_user: User,
    note: str | None = None, autocommit: bool = True,
) -> DataSubjectRequest | None:
    """Talebi iptal et. Yetki:
    - target_user_id == by_user.id: kendi talebini iptal edebilir
    - SUPER_ADMIN: her talebi iptal edebilir
    - INSTITUTION_ADMIN: kendi kurumundaki talepleri iptal edebilir
    """
    req = db.get(DataSubjectRequest, request_id)
    if req is None:
        return None
    if req.status not in (
        DataRequestStatus.PENDING, DataRequestStatus.PROCESSING,
    ):
        return req   # zaten kapalı — idempotent

    # Yetki
    is_target = req.target_user_id == by_user.id
    is_super = by_user.role == UserRole.SUPER_ADMIN
    is_inst_admin = (
        by_user.role == UserRole.INSTITUTION_ADMIN
        and req.institution_id == by_user.institution_id
    )
    if not (is_target or is_super or is_inst_admin):
        raise PermissionError("Bu talebi iptal etme yetkiniz yok")

    req.status = DataRequestStatus.CANCELLED
    req.processed_by_user_id = by_user.id
    req.processed_at = datetime.now(timezone.utc)
    if note:
        req.admin_note = ((req.admin_note or "") + "\n" + note).strip()

    if autocommit:
        db.commit()
    return req


def apply_deletion(
    db: Session, *, request: DataSubjectRequest,
    by_user: User | None = None, autocommit: bool = True,
) -> DataSubjectRequest:
    """Silme talebini fiilen uygula — kullanıcıyı anonimleştir.

    Adımlar:
    1. User satırına anonimleştirilmiş değerler yaz
    2. password_hash temizle (login imkânsız)
    3. is_active=False
    4. AuditLog satırı (USER_DELETE)
    5. Talep status=COMPLETED + processed_*

    İlişkili veriler (Task, NotificationLog, AuditLog) KORUNUR — istatistiki
    bütünlük + adli iz için. Anonimleştirilmiş kullanıcıya bağlı kalırlar
    (full_name "(Silinen Kullanıcı)" olur).
    """
    target = db.get(User, request.target_user_id) if request.target_user_id else None
    if target is None:
        # Kullanıcı zaten silinmiş — talebi cancel et
        request.status = DataRequestStatus.CANCELLED
        request.processed_by_user_id = by_user.id if by_user else None
        request.processed_at = datetime.now(timezone.utc)
        request.admin_note = (
            (request.admin_note or "")
            + "\nKullanıcı bulunamadı, talep iptal edildi."
        ).strip()
        if autocommit:
            db.commit()
        return request

    # Anonimleştir
    anonym_email = f"anonymized-{request.id}@kvkk.local"
    target.full_name = "(Silinen Kullanıcı)"
    target.email = anonym_email
    target.password_hash = ""    # login imkânsız
    target.is_active = False
    target.must_change_password = False
    # Telefon ve diğer profil alanları varsa temizle (Sprint'te eklenirse buraya)
    # Şu an User modelinde telefon yok; ParentNotificationPref.phone_e164 ayrı.

    # Veli telefonu varsa anonimleştir
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == target.id)
        .first()
    )
    if pref:
        pref.whatsapp_phone = None
        pref.whatsapp_enabled = False
        pref.whatsapp_phone_verified_at = None
        pref.daily_summary_enabled = False
        pref.weekly_report_enabled = False
        pref.empty_day_alert_enabled = False
        pref.drop_alert_enabled = False
        pref.new_program_alert_enabled = False
        pref.teacher_note_enabled = False
        pref.exam_approaching_enabled = False
        pref.unsubscribed_at = datetime.now(timezone.utc)

    # Audit
    audit = AuditLog(
        actor_id=by_user.id if by_user else None,
        action=AuditAction.USER_DELETE,
        target_type="user",
        target_id=target.id,
        details_json=json.dumps({
            "data_subject_request_id": request.id,
            "reason": "kvkk_rtbf_anonymization",
            "request_reason": request.reason or "",
        }, ensure_ascii=False),
    )
    db.add(audit)

    # Talep durumu
    request.status = DataRequestStatus.COMPLETED
    request.processed_by_user_id = by_user.id if by_user else None
    request.processed_at = datetime.now(timezone.utc)
    if not request.admin_note:
        request.admin_note = (
            "Kullanıcı KVKK madde 11 kapsamında anonimleştirildi"
        )

    if autocommit:
        db.commit()
    logger.info(
        "apply_deletion: req_id=%s target=%s anonymized email=%s",
        request.id, target.id, anonym_email,
    )
    return request


# ============================ Cron ============================


def cron_apply_expired_deletions(
    db: Session, *, now: datetime | None = None,
) -> dict:
    """Cron: process_after geçmiş PROCESSING DataSubjectRequest.delete'leri uygula.

    Günlük 02:00 UTC. İdempotent — bir kez uygulanan kayıt COMPLETED'a geçer.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    counts = {"processed": 0, "skipped_user_missing": 0, "skipped_not_due": 0}

    candidates = (
        db.query(DataSubjectRequest)
        .filter(
            DataSubjectRequest.kind == DataRequestKind.DELETE,
            DataSubjectRequest.status == DataRequestStatus.PROCESSING,
            DataSubjectRequest.process_after.isnot(None),
        )
        .all()
    )
    for req in candidates:
        pa = req.process_after
        if pa is not None and pa.tzinfo is None:
            pa = pa.replace(tzinfo=timezone.utc)
        if pa is None or pa > now:
            counts["skipped_not_due"] += 1
            continue
        target = db.get(User, req.target_user_id) if req.target_user_id else None
        if target is None:
            req.status = DataRequestStatus.CANCELLED
            req.processed_at = now
            req.admin_note = (
                (req.admin_note or "")
                + "\nKullanıcı bulunamadı (cron sırasında)."
            ).strip()
            counts["skipped_user_missing"] += 1
            continue
        apply_deletion(db, request=req, by_user=None, autocommit=False)
        counts["processed"] += 1

    db.commit()
    logger.info("cron_apply_expired_deletions: %s", counts)
    return counts


# ============================ Veri envanteri ============================


@dataclass(frozen=True)
class DataInventoryItem:
    """KVKK denetim raporu için bir veri kategorisi."""
    table_name: str
    label: str
    contains_pii: bool
    retention_days: int | None       # None = süresiz
    legal_basis: str
    purpose: str


# Sistem geneli kişisel veri envanteri (KVKK madde 10 aydınlatma metni
# kaynağı). Yeni tablo eklendikçe burası güncellenmeli.
DATA_INVENTORY: tuple[DataInventoryItem, ...] = (
    DataInventoryItem(
        table_name="users", label="Kullanıcı hesapları",
        contains_pii=True, retention_days=None,
        legal_basis="Sözleşme: ETÜTKOÇ Rotam hizmetinin sağlanması",
        purpose="Kimlik doğrulama, rol bazlı erişim, hesap yönetimi",
    ),
    DataInventoryItem(
        table_name="audit_logs", label="Güvenlik denetim kayıtları",
        contains_pii=True, retention_days=180,
        legal_basis="Hukuki yükümlülük: KVKK madde 12 — veri güvenliği",
        purpose="Yetkisiz erişim tespiti, ihlal soruşturması",
    ),
    DataInventoryItem(
        table_name="tasks", label="Öğrenci görevleri ve programları",
        contains_pii=True, retention_days=None,
        legal_basis="Sözleşme: koçluk hizmeti sağlanması",
        purpose="Çalışma takibi, performans analizi",
    ),
    DataInventoryItem(
        table_name="notification_logs", label="Veli bildirim logları",
        contains_pii=True, retention_days=180,
        legal_basis="Sözleşme + açık rıza (veli bildirim onayı)",
        purpose="Bildirim teslim takibi, başarısızlık raporu",
    ),
    DataInventoryItem(
        table_name="parent_student_links", label="Veli-öğrenci eşleşmeleri",
        contains_pii=True, retention_days=None,
        legal_basis="Açık rıza (veli kayıt akışı)",
        purpose="Veliyi çocuğun raporlarına yetkilendirme",
    ),
    DataInventoryItem(
        table_name="parent_notification_prefs",
        label="Veli iletişim tercihleri",
        contains_pii=True, retention_days=None,
        legal_basis="Açık rıza (telefon, e-posta tercihleri)",
        purpose="Bildirim kanalı seçimi, opt-out",
    ),
    DataInventoryItem(
        table_name="notification_logs", label="Veli oturum kayıtları",
        contains_pii=True, retention_days=180,
        legal_basis="Hukuki yükümlülük: erişim güvenliği",
        purpose="Magic link doğrulama, anormal erişim tespiti",
    ),
    DataInventoryItem(
        table_name="usage_events", label="Sistem kullanım olayları",
        contains_pii=False, retention_days=365,
        legal_basis="Meşru menfaat: kapasite planlama, faturalandırma",
        purpose="Kredi tüketimi, plan uyum, KPI",
    ),
    DataInventoryItem(
        table_name="data_subject_requests",
        label="Veri sahibi talep kayıtları",
        contains_pii=True, retention_days=730,
        legal_basis="Hukuki yükümlülük: KVKK madde 13 talep cevap iz",
        purpose="Talep takibi, denetim",
    ),
)


def list_pending_requests(
    db: Session, *, institution_id: int | None = None,
) -> list[DataSubjectRequest]:
    """Bekleyen tüm talepleri listele — admin paneli için."""
    q = db.query(DataSubjectRequest).filter(
        DataSubjectRequest.status.in_([
            DataRequestStatus.PENDING, DataRequestStatus.PROCESSING,
        ])
    )
    if institution_id is not None:
        q = q.filter(DataSubjectRequest.institution_id == institution_id)
    return q.order_by(DataSubjectRequest.created_at.desc()).all()


def request_summary(db: Session, *, institution_id: int | None = None) -> dict[str, int]:
    """Talep durum sayım özeti — admin dashboard için."""
    q = db.query(DataSubjectRequest)
    if institution_id is not None:
        q = q.filter(DataSubjectRequest.institution_id == institution_id)
    rows = q.all()
    counts = {s.value: 0 for s in DataRequestStatus}
    counts["total"] = len(rows)
    for r in rows:
        counts[r.status.value] = counts.get(r.status.value, 0) + 1
    return counts
