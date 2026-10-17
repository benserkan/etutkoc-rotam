"""Süper admin — Kişiler (kullanıcılar) sayfası: rol sekmeleri + aktivite kümeleri.

2026-10-17 (kullanıcı): tüm kullanıcıları tek karışık listede göstermek pratik
değildi; veli bağlantısı görünmüyordu. Bu uç rol sekmesi başına sayılar, aktivite
kümeleri (bugün / bu hafta / 7+ gün sessiz / hiç girmedi), sayfalama ve role
özgü sütunlar (öğrenci → koç + sınıf + son 7 gün görev %; koç → öğrenci sayısı +
paket durumu; veli → çocuklar) döndürür. Eski GET /admin/users geriye uyum için
duruyor (detay sayfası + diğer ekranlar).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import Institution, User, UserRole
from app.models.parent import ParentStudentLink
from app.models.task import Task
from app.routes.api_v2.admin import _require_super_admin, _users_invalidate
from app.routes.api_v2.schemas.common import MutationResponse
from app.services import gorev_stats
from app.services.audit import log_action
from app.models.audit_log import AuditAction

router = APIRouter(prefix="/admin", tags=["v2-admin-people"])

TR = timezone(timedelta(hours=3))
ROLE_KEYS = ("teacher", "student", "parent", "institution_admin", "super_admin")
ROLE_LABELS = {
    "teacher": "Koç", "student": "Öğrenci", "parent": "Veli",
    "institution_admin": "Kurum yöneticisi", "super_admin": "Süper admin",
}
Activity = Literal["all", "today", "week", "silent", "never"]
PlanFilter = Literal["all", "trial", "active", "payment_pending", "past_due", "free"]


class PersonRef(BaseModel):
    id: int
    name: str
    institution_name: str | None = None
    coach_name: str | None = None
    grade_label: str | None = None


class PersonRow(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    role_label: str
    is_active: bool
    locked_now: bool = False
    must_change_password: bool = False
    is_demo: bool = False
    demo_label: str | None = None
    last_active_at: datetime | None = None
    created_at: datetime | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    # öğrenci
    grade_label: str | None = None
    coach: PersonRef | None = None
    gorev_7d_done: int | None = None
    gorev_7d_total: int | None = None
    program_mode: str | None = None
    # koç
    student_count: int | None = None
    plan_label: str | None = None
    plan_state: str | None = None   # trial | active | past_due | payment_pending | free | institution
    plan_note: str | None = None
    # veli
    children: list[PersonRef] = []


class PeopleResponse(BaseModel):
    role: str
    activity: str
    role_counts: dict[str, int]
    activity_counts: dict[str, int]
    total: int
    page: int
    page_size: int
    items: list[PersonRow]
    institutions: list[dict]
    plan_counts: dict[str, int] = {}


class SetActiveBody(BaseModel):
    is_active: bool


def _last_active_expr():
    """Son aktiflik = last_seen_at ile last_login_at'in büyüğü (User.last_active_at aynası)."""
    return func.coalesce(
        case((User.last_seen_at >= User.last_login_at, User.last_seen_at), else_=User.last_login_at),
        User.last_seen_at, User.last_login_at,
    )


def _bounds(now: datetime) -> tuple[datetime, datetime]:
    today_tr = now.astimezone(TR).date()
    today_start = datetime.combine(today_tr, time.min, tzinfo=TR).astimezone(timezone.utc)
    return today_start, now - timedelta(days=7)


def _activity_filter(q, activity: str, la, today_start: datetime, week_ago: datetime):
    if activity == "today":
        return q.filter(la >= today_start)
    if activity == "week":
        return q.filter(la < today_start, la >= week_ago)
    if activity == "silent":
        return q.filter(la < week_ago)
    if activity == "never":
        return q.filter(la.is_(None))
    return q


def _base_query(db: Session, q: str | None, institution_id: int | None):
    query = db.query(User)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if institution_id:
        child_parents = (
            db.query(ParentStudentLink.parent_id)
            .join(User, User.id == ParentStudentLink.student_id)
            .filter(User.institution_id == institution_id)
        )
        query = query.filter(or_(User.institution_id == institution_id, User.id.in_(child_parents)))
    return query


def _plan_filter(q, plan: str, now: datetime):
    """_plan_info ile aynı öncelik sırası, SQL'de: deneme > gecikti > aktif > ödeme bekliyor > ücretsiz."""
    from app.services.pricing import is_paid_plan_code
    from app.services.plans import PLAN_CATALOG

    paid = [c for c in PLAN_CATALOG if is_paid_plan_code(c)]
    trial = (User.trial_ends_at.isnot(None)) & (User.trial_ends_at > now)
    past_due = User.subscription_status == "past_due"
    active = User.subscription_status.in_(["active", "canceled"])
    pending = User.post_trial_plan.in_(paid)
    if plan == "trial":
        return q.filter(trial)
    if plan == "past_due":
        return q.filter(~trial, past_due)
    if plan == "active":
        return q.filter(~trial, active)
    if plan == "payment_pending":
        return q.filter(~trial, or_(User.subscription_status.is_(None), ~(past_due | active)), pending)
    if plan == "free":
        return q.filter(~trial, or_(User.subscription_status.is_(None), ~(past_due | active)),
                        or_(User.post_trial_plan.is_(None), ~pending))
    return q


def _plan_info(u: User, now: datetime) -> tuple[str | None, str | None, str | None]:
    from app.services.plans import PLAN_CATALOG, is_trial_active
    from app.services.pricing import is_paid_plan_code

    if u.institution_id:
        return (None, "institution", None)
    label = (PLAN_CATALOG.get(u.plan or "") or None)
    label = label.label if label else (u.plan or None)
    if is_trial_active(u) and u.trial_ends_at:
        end = u.trial_ends_at if u.trial_ends_at.tzinfo else u.trial_ends_at.replace(tzinfo=timezone.utc)
        days = max(0, (end - now).days)
        return (label, "trial", f"{days} gün kaldı")
    if u.subscription_status == "past_due":
        return (label, "past_due", "yenileme gecikti")
    if u.subscription_status in ("active", "canceled"):
        note = None
        if u.subscription_period_end:
            note = f"{'bitiş' if u.subscription_status == 'canceled' else 'yenileme'} {u.subscription_period_end:%d.%m}"
        return (label, "active", note)
    if u.post_trial_plan and is_paid_plan_code(u.post_trial_plan):
        target = PLAN_CATALOG.get(u.post_trial_plan)
        return (label, "payment_pending", f"ödeme bekleniyor · {target.label if target else u.post_trial_plan}")
    if is_paid_plan_code(u.plan):
        # Bütünlük taramasının "ödeme kaydı olmayan ücretli plan" vakası (test/demo hesapları)
        return (label, "free", "ödeme kaydı yok")
    return (label, "free", None)


@router.get("/people", response_model=PeopleResponse)
def admin_people_v2(
    role: str = Query("student"),
    activity: Activity = Query("all"),
    q: str | None = Query(None, max_length=120),
    institution_id: int | None = Query(None),
    sort: Literal["activity", "name", "created"] = Query("activity"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    independent: bool = Query(False, description="Yalnız bağımsız koçlar (kurumsuz öğretmen)"),
    plan: PlanFilter = Query("all"),
    _: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    if role not in ROLE_KEYS:
        raise HTTPException(status_code=422, detail="invalid_role")
    now = datetime.now(timezone.utc)
    today_start, week_ago = _bounds(now)
    la = _last_active_expr()

    base = _base_query(db, q, institution_id)
    role_counts = {
        r.value: int(c) for r, c in
        base.with_entities(User.role, func.count(User.id)).group_by(User.role).all()
    }
    role_counts = {k: role_counts.get(k, 0) for k in ROLE_KEYS}

    in_role = base.filter(User.role == UserRole(role))
    plan_counts: dict[str, int] = {}
    if independent:
        in_role = in_role.filter(User.role == UserRole.TEACHER, User.institution_id.is_(None))
        for key in ("all", "trial", "active", "payment_pending", "past_due", "free"):
            plan_counts[key] = _plan_filter(in_role, key, now).count()
        in_role = _plan_filter(in_role, plan, now)
    activity_counts = {"all": in_role.count()}
    for key in ("today", "week", "silent", "never"):
        activity_counts[key] = _activity_filter(in_role, key, la, today_start, week_ago).count()

    rows_q = _activity_filter(in_role, activity, la, today_start, week_ago)
    total = rows_q.count()
    if sort == "name":
        rows_q = rows_q.order_by(User.full_name.asc())
    elif sort == "created":
        rows_q = rows_q.order_by(User.created_at.desc())
    else:
        rows_q = rows_q.order_by(la.is_(None), la.desc(), User.id.desc())
    users = (
        rows_q.options(joinedload(User.institution))
        .offset((page - 1) * page_size).limit(page_size).all()
    )

    items = [_row(u, now) for u in users]
    _enrich(db, users, items, now)
    insts = [{"id": i.id, "name": i.name, "slug": i.slug} for i in db.query(Institution).order_by(Institution.name).all()]
    return PeopleResponse(
        role=role, activity=activity, role_counts=role_counts, activity_counts=activity_counts,
        total=total, page=page, page_size=page_size, items=items, institutions=insts,
        plan_counts=plan_counts,
    )


def _row(u: User, now: datetime) -> PersonRow:
    from app.services.auth_security import is_locked

    r = PersonRow(
        id=u.id, full_name=u.full_name, email=u.email, role=u.role.value,
        role_label=ROLE_LABELS.get(u.role.value, u.role.value),
        is_active=u.is_active, locked_now=is_locked(u),
        must_change_password=bool(u.must_change_password),
        is_demo=bool(getattr(u, "is_demo", False)), demo_label=getattr(u, "demo_label", None),
        last_active_at=u.last_active_at, created_at=u.created_at,
        institution_id=u.institution_id,
        institution_name=u.institution.name if u.institution_id and u.institution else None,
    )
    if u.role == UserRole.STUDENT:
        r.grade_label = u.display_grade_label
        r.program_mode = getattr(u, "program_mode", None)
    if u.role == UserRole.TEACHER:
        r.plan_label, r.plan_state, r.plan_note = _plan_info(u, now)
    return r


def _enrich(db: Session, users: list[User], items: list[PersonRow], now: datetime) -> None:
    """Sayfadaki satırlar için toplu ek bilgi — N+1 yok."""
    by_id = {it.id: it for it in items}
    students = [u for u in users if u.role == UserRole.STUDENT]
    teachers = [u for u in users if u.role == UserRole.TEACHER]
    parents = [u for u in users if u.role == UserRole.PARENT]

    # Veli → çocuklar
    links = (
        db.query(ParentStudentLink.parent_id, ParentStudentLink.student_id)
        .filter(ParentStudentLink.parent_id.in_([p.id for p in parents])).all()
        if parents else []
    )
    kid_ids = {sid for _, sid in links}
    kids = (
        {k.id: k for k in db.query(User).options(joinedload(User.institution))
         .filter(User.id.in_(kid_ids)).all()} if kid_ids else {}
    )
    coach_ids = {s.teacher_id for s in students if s.teacher_id} | {k.teacher_id for k in kids.values() if k.teacher_id}
    coaches = {c.id: c for c in db.query(User).filter(User.id.in_(coach_ids)).all()} if coach_ids else {}

    for pid, sid in links:
        k = kids.get(sid)
        if k is None:
            continue
        c = coaches.get(k.teacher_id) if k.teacher_id else None
        by_id[pid].children.append(PersonRef(
            id=k.id, name=k.full_name,
            institution_name=k.institution.name if k.institution_id and k.institution else None,
            coach_name=c.full_name if c else None, grade_label=k.display_grade_label,
        ))
    for p in parents:
        it = by_id[p.id]
        if not it.institution_name:
            insts = sorted({c.institution_name for c in it.children if c.institution_name})
            it.institution_name = ", ".join(insts) or None

    # Öğrenci → koç + son 7 gün görev
    for s in students:
        c = coaches.get(s.teacher_id) if s.teacher_id else None
        if c:
            by_id[s.id].coach = PersonRef(id=c.id, name=c.full_name)
    if students:
        today = now.astimezone(TR).date()
        start = today - timedelta(days=6)
        tasks = (
            db.query(Task).options(joinedload(Task.book_items))
            .filter(Task.student_id.in_([s.id for s in students]),
                    Task.date >= start, Task.date <= today, Task.is_draft.is_(False))
            .all()
        )
        per: dict[int, list[Task]] = {}
        for t in tasks:
            per.setdefault(t.student_id, []).append(t)
        for s in students:
            g = gorev_stats.summarize(gorev_stats.settled_tasks(per.get(s.id, []), today))
            by_id[s.id].gorev_7d_done = g.gorev_done
            by_id[s.id].gorev_7d_total = g.gorev_total

    # Koç → aktif öğrenci sayısı
    if teachers:
        counts = dict(
            db.query(User.teacher_id, func.count(User.id))
            .filter(User.teacher_id.in_([t.id for t in teachers]),
                    User.role == UserRole.STUDENT, User.is_active.is_(True))
            .group_by(User.teacher_id).all()
        )
        for t in teachers:
            by_id[t.id].student_count = int(counts.get(t.id, 0))


@router.post("/users/{user_id}/set-active", response_model=MutationResponse[dict])
def admin_set_user_active_v2(
    user_id: int,
    body: SetActiveBody,
    admin: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Yalnız aktifliği değiştir (listeden hızlı işlem). Kendi hesabı / süper admin yasak."""
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    if u.id == admin.id or u.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="cannot_modify_admin")
    before = u.is_active
    u.is_active = bool(body.is_active)
    log_action(
        db, action=AuditAction.USER_DEACTIVATE if not u.is_active else AuditAction.USER_UPDATE,
        actor_id=admin.id, target_type="user", target_id=u.id,
        details={"op": "set_active", "before": before, "after": u.is_active}, autocommit=False,
    )
    db.commit()
    return MutationResponse(
        data={"id": u.id, "is_active": u.is_active,
              "message": "Hesap aktif edildi" if u.is_active else "Hesap pasife alındı"},
        invalidate=_users_invalidate(),
    )


@router.get("/audit/feed")
def admin_audit_feed_v2(
    days: int = Query(7, ge=1, le=90),
    category: Literal["all", "security", "admin", "coaching", "student", "commercial", "system"] = Query("all"),
    severity: Literal["all", "critical", "warn"] = Query("all"),
    actor_id: int | None = Query(None),
    q: str | None = Query(None, max_length=120),
    role: Literal["teacher", "student", "parent", "institution_admin", "super_admin"] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    _: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Denetim akışı — audit_logs + alan olayları (deneme, öğrenci, program, görev…) Türkçe cümleyle."""
    from app.services.admin_activity_log import build_feed

    return build_feed(db, days=days, category=category, severity=severity, actor_id=actor_id,
                      q=q, role=role, page=page, page_size=page_size)
