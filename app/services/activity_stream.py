"""Üyelik & aktivite akışı — süper admin + kurum yöneticisi için birleşik feed.

Mevcut tabloları (users + invitations + parent_invitations + contact_requests +
plan_change_history) chronological tek akışa birleştirir. `institution_id`
parametresi ile scoped çalışır (None = süper admin tüm sistem, INT = kurum
yöneticisi sadece kendi kurumu).

Kategori sistemi:
  - signup        — yeni kayıt (bağımsız koç / kurum koç / öğrenci / veli)
  - invitation    — kurum→koç davet, öğretmen→veli davet
  - commercial    — paket alımı, abonelik talebi, iletişim talebi (HIGHLIGHT)
  - change        — plan değişimi (yan akış)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session, aliased

from app.models import (
    ContactRequest, Institution, ParentInvitation, User, UserRole,
)
from app.models.invitation import Invitation, InvitationStatus
from app.models.plan_history import PlanChangeHistory, PlanChangeReason, PlanOwnerType


_PLAN_LABELS_TR = {
    "solo_free": "Solo Ücretsiz", "solo_trial": "Solo Deneme (14g)",
    "solo_pro": "Solo Pro", "solo_elite": "Solo Elite",
    "solo_unlimited": "Solo Sınırsız",
    "institution_free": "Kurum Tanıma", "institution_trial": "Kurum Deneme",
    "etut_standart": "Etüt Standart", "dershane_pro": "Dershane Pro",
    "enterprise": "Enterprise",
    "free": "Ücretsiz",
}


def _plan_label(code: str | None) -> str:
    if not code:
        return "—"
    return _PLAN_LABELS_TR.get(code, code)


def _item(
    *,
    src: str, sid: int, occurred_at: datetime, type_: str, category: str,
    is_commercial: bool, title: str, subtitle: str | None = None,
    actor_name: str | None = None, actor_email: str | None = None,
    actor_role: str | None = None,
    target_label: str | None = None, detail_url: str | None = None,
    institution_id: int | None = None, institution_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": f"{src}:{sid}",
        "occurred_at": occurred_at,
        "type": type_, "category": category,
        "is_commercial": is_commercial,
        "title": title, "subtitle": subtitle,
        "actor_name": actor_name, "actor_email": actor_email,
        "actor_role": actor_role,
        "target_label": target_label,
        "detail_url": detail_url,
        "institution_id": institution_id, "institution_name": institution_name,
    }


def fetch_activity(
    db: Session, *,
    institution_id: int | None = None,
    days: int = 30,
    type_filter: str | None = None,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Birleşik aktivite akışı.

    institution_id=None  → süper admin (tüm sistem).
    institution_id=INT   → o kurumun aktiviteleri (öğretmen + öğrenci + davet +
                           plan).

    type_filter:
      'all' / None       — hepsi
      'signup'           — yeni kayıt
      'invitation'       — davet (kurum→koç + öğretmen→veli)
      'commercial'       — iletişim/abonelik talebi + paket alımı (HIGHLIGHT)
      'change'           — plan değişimi
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    items: list[dict[str, Any]] = []

    # ---- 1) Yeni kullanıcı kayıtları (users.created_at) ----
    Teacher = aliased(User)
    u_q = db.query(User, Teacher).outerjoin(
        Teacher, User.teacher_id == Teacher.id
    ).filter(User.created_at >= since)
    if institution_id is not None:
        # Scope: kurum öğretmenleri + onların öğrencileri/velileri
        u_q = u_q.filter(
            (User.institution_id == institution_id)
            | (Teacher.institution_id == institution_id)
        )
    for u, coach in u_q.all():
        if u.role == UserRole.TEACHER and u.institution_id is None:
            # Bağımsız koç — yeni signup (deneme ile)
            title = f"Yeni bağımsız koç: {u.full_name or u.email}"
            subtitle = f"Paket: {_plan_label(u.plan)} · {u.email}"
            t = "signup_teacher_solo"
            inst_name = None
        elif u.role == UserRole.TEACHER:
            inst = db.query(Institution).filter(Institution.id == u.institution_id).first()
            title = f"Kuruma yeni koç: {u.full_name or u.email}"
            subtitle = f"{u.email} · kurum: {inst.name if inst else '—'}"
            t = "signup_teacher_institution"
            inst_name = inst.name if inst else None
        elif u.role == UserRole.STUDENT:
            title = f"Yeni öğrenci: {u.full_name}"
            subtitle = f"Koç: {coach.full_name if coach else '—'}"
            t = "create_student"
            inst_name = coach.institution.name if coach and coach.institution else None
        elif u.role == UserRole.PARENT:
            title = f"Yeni veli: {u.full_name or u.email}"
            subtitle = u.email
            t = "signup_parent"
            inst_name = None
        elif u.role == UserRole.INSTITUTION_ADMIN:
            inst = db.query(Institution).filter(Institution.id == u.institution_id).first()
            title = f"Yeni kurum yöneticisi: {u.full_name or u.email}"
            subtitle = f"Kurum: {inst.name if inst else '—'}"
            t = "signup_institution_admin"
            inst_name = inst.name if inst else None
        else:
            continue
        items.append(_item(
            src="user", sid=u.id, occurred_at=u.created_at,
            type_=t, category="signup", is_commercial=False,
            title=title, subtitle=subtitle,
            actor_name=u.full_name, actor_email=u.email,
            actor_role=u.role.value,
            detail_url=f"/admin/users/{u.id}" if institution_id is None
                       else (f"/institution/teachers/{u.id}" if u.role == UserRole.TEACHER else None),
            institution_id=u.institution_id or (coach.institution_id if coach else None),
            institution_name=inst_name,
        ))

    # ---- 2) Kurum davetleri (invitations — institution_admin'in koça yolladığı) ----
    inv_q = db.query(Invitation, User, Institution).outerjoin(
        User, Invitation.created_by_user_id == User.id
    ).outerjoin(
        Institution, Invitation.institution_id == Institution.id
    ).filter(Invitation.created_at >= since)
    if institution_id is not None:
        inv_q = inv_q.filter(Invitation.institution_id == institution_id)
    for inv, creator, inst in inv_q.all():
        status_label = {
            InvitationStatus.PENDING: "bekliyor",
            InvitationStatus.CONSUMED: "kabul edildi",
            InvitationStatus.EXPIRED: "süresi doldu",
            InvitationStatus.REVOKED: "iptal edildi",
        }.get(inv.status, inv.status.value if hasattr(inv.status, "value") else str(inv.status))
        target = inv.email or inv.full_name or "—"
        items.append(_item(
            src="invitation", sid=inv.id,
            occurred_at=inv.created_at,
            type_="invitation_institution",
            category="invitation", is_commercial=False,
            title=f"Kurum daveti: {target}",
            subtitle=f"Rol: {inv.role.value} · durum: {status_label}",
            actor_name=creator.full_name if creator else None,
            actor_email=creator.email if creator else None,
            actor_role=creator.role.value if creator else None,
            target_label=target,
            detail_url=f"/admin/institutions/{inv.institution_id}" if institution_id is None
                       else "/institution/invitations",
            institution_id=inv.institution_id,
            institution_name=inst.name if inst else None,
        ))

    # ---- 3) Veli davetleri (parent_invitations — öğretmenin) ----
    InvitedBy = aliased(User)
    Student = aliased(User)
    pi_q = db.query(ParentInvitation, InvitedBy, Student).outerjoin(
        InvitedBy, ParentInvitation.invited_by_id == InvitedBy.id
    ).outerjoin(
        Student, ParentInvitation.student_id == Student.id
    ).filter(ParentInvitation.created_at >= since)
    if institution_id is not None:
        pi_q = pi_q.filter(InvitedBy.institution_id == institution_id)
    for pi, teacher, student in pi_q.all():
        status_label = "kabul edildi" if pi.consumed_at else "bekliyor"
        items.append(_item(
            src="parent_inv", sid=pi.id,
            occurred_at=pi.created_at,
            type_="invitation_parent",
            category="invitation", is_commercial=False,
            title=f"Veli daveti: {pi.invited_email}",
            subtitle=f"Öğrenci: {student.full_name if student else '—'} · durum: {status_label}",
            actor_name=teacher.full_name if teacher else None,
            actor_email=teacher.email if teacher else None,
            actor_role="teacher",
            target_label=pi.invited_email,
            detail_url=f"/teacher/students/{pi.student_id}#parents" if pi.student_id else None,
            institution_id=teacher.institution_id if teacher else None,
        ))

    # ---- 4) Contact requests (iletişim + abonelik talepleri) ----
    cr_q = db.query(ContactRequest).filter(ContactRequest.created_at >= since)
    if institution_id is not None:
        # Sadece bu kurum için subscription talepleri (mesajda kurum_id=N geçerse)
        cr_q = cr_q.filter(
            ContactRequest.source == "subscription_request",
            ContactRequest.message.like(f"%kurum_id={institution_id}%"),
        )
    for cr in cr_q.all():
        if cr.source == "subscription_request":
            t = "subscription_request"
            title = f"Abonelik talebi: {cr.name}"
            is_commercial = True
            # mesajdan hedef paket çıkar
            import re
            m = re.search(r"hedef=([^·]+)", cr.message or "")
            target_pkg = m.group(1).strip() if m else "—"
            subtitle = f"Hedef paket: {target_pkg} · {cr.email}"
        else:
            t = "contact_request"
            title = f"İletişim talebi: {cr.name}"
            is_commercial = True
            subtitle = f"{cr.institution_name or '—'} · {cr.coach_count or '?'} koç · {cr.email}"
        items.append(_item(
            src="contact", sid=cr.id,
            occurred_at=cr.created_at,
            type_=t, category="commercial",
            is_commercial=is_commercial,
            title=title, subtitle=subtitle,
            actor_name=cr.name, actor_email=cr.email,
            actor_role=None,
            target_label=cr.institution_name,
            detail_url="/admin/contact-requests" if institution_id is None
                       else "/institution/subscription",
            institution_name=cr.institution_name,
        ))

    # ---- 5) Plan değişimleri (paket alımı/yükseltme öne çıkar) ----
    pch_q = db.query(PlanChangeHistory).filter(PlanChangeHistory.occurred_at >= since)
    if institution_id is not None:
        pch_q = pch_q.filter(
            PlanChangeHistory.owner_type == PlanOwnerType.INSTITUTION,
            PlanChangeHistory.owner_id == institution_id,
        )
    for pch in pch_q.all():
        # Plan UPGRADE = paket satın alma → HIGHLIGHT
        is_upgrade = pch.reason == PlanChangeReason.UPGRADE
        is_downgrade = pch.reason == PlanChangeReason.DOWNGRADE
        if is_upgrade:
            title = "🛒 PAKET SATIN ALMA"
            t = "plan_upgrade"; cat = "commercial"; is_commercial = True
        elif is_downgrade:
            title = "Paket düşürme"
            t = "plan_downgrade"; cat = "change"; is_commercial = False
        else:
            title = "Plan kaydı"
            t = "plan_other"; cat = "change"; is_commercial = False

        # owner adı
        if pch.owner_type == PlanOwnerType.INSTITUTION:
            inst = db.query(Institution).filter(Institution.id == pch.owner_id).first()
            owner_label = inst.name if inst else f"Kurum #{pch.owner_id}"
            inst_name = owner_label
            inst_id = pch.owner_id
            url = f"/admin/institutions/{pch.owner_id}" if institution_id is None else "/institution/subscription"
        else:
            u = db.query(User).filter(User.id == pch.owner_id).first()
            owner_label = u.full_name if u else f"Kullanıcı #{pch.owner_id}"
            inst_name = None
            inst_id = u.institution_id if u else None
            url = f"/admin/users/{pch.owner_id}" if institution_id is None else None

        subtitle = (
            f"{owner_label} · {_plan_label(pch.from_plan)} → {_plan_label(pch.to_plan)}"
        )
        items.append(_item(
            src="plan_change", sid=pch.id,
            occurred_at=pch.occurred_at,
            type_=t, category=cat,
            is_commercial=is_commercial,
            title=title, subtitle=subtitle,
            target_label=owner_label,
            detail_url=url,
            institution_id=inst_id, institution_name=inst_name,
        ))

    # ---- Filter + sort + limit ----
    if type_filter and type_filter != "all":
        items = [i for i in items if i["category"] == type_filter]
    items.sort(key=lambda x: x["occurred_at"], reverse=True)

    # KPI sayım — tüm liste (limit'ten önce)
    counts = {
        "total": len(items),
        "signup": sum(1 for i in items if i["category"] == "signup"),
        "invitation": sum(1 for i in items if i["category"] == "invitation"),
        "commercial": sum(1 for i in items if i["category"] == "commercial"),
        "change": sum(1 for i in items if i["category"] == "change"),
    }
    # Highlight ayrı sayım — paket satın alma
    counts["purchases"] = sum(1 for i in items if i["type"] == "plan_upgrade")

    return items[:limit], counts
