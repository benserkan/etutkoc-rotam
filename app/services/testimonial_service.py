"""Testimonial servis — sosyal kanıt iş mantığı (TEK MERKEZ).

Public yayınlanmış liste + uygulama-içi gönderim + süper admin moderasyon/CRUD.
Anasayfa (landing) yalnız `published` kayıtları çeker; uygulama-içi gönderimler
`pending` olarak gelir, süper admin yayınlar.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    TESTIMONIAL_KIND_LABELS_TR,
    TESTIMONIAL_KIND_REVIEW,
    TESTIMONIAL_SOURCE_IN_APP,
    TESTIMONIAL_SOURCE_MANUAL,
    TESTIMONIAL_STATUS_HIDDEN,
    TESTIMONIAL_STATUS_PENDING,
    TESTIMONIAL_STATUS_PUBLISHED,
    Testimonial,
    User,
)

VALID_KINDS = set(TESTIMONIAL_KIND_LABELS_TR.keys())
VALID_STATUSES = {
    TESTIMONIAL_STATUS_PENDING,
    TESTIMONIAL_STATUS_PUBLISHED,
    TESTIMONIAL_STATUS_HIDDEN,
}

# Uygulama-içi yorum bırakabilen roller (kurum yöneticisi dahil; süper admin
# elle panelden girer, öğrenci-dışı rol kısıtı backend'de değil — herkes kendi
# deneyimini paylaşabilir, moderasyon süper adminde).
IN_APP_ALLOWED_ROLES = {"student", "parent", "teacher", "institution_admin"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- public (anasayfa)

def list_published(db: Session, *, kind: str | None = None, limit: int = 24) -> list[Testimonial]:
    """Anasayfada gösterilecek yayınlanmış kayıtlar (öne çıkanlar üstte)."""
    q = db.query(Testimonial).filter(
        Testimonial.status == TESTIMONIAL_STATUS_PUBLISHED
    )
    if kind and kind in VALID_KINDS:
        q = q.filter(Testimonial.kind == kind)
    q = q.order_by(
        Testimonial.featured.desc(),
        Testimonial.sort_order.asc(),
        Testimonial.published_at.desc().nullslast(),
        Testimonial.id.desc(),
    )
    return q.limit(max(1, min(limit, 100))).all()


def published_counts(db: Session) -> dict[str, int]:
    """Yayınlanmış kayıt sayıları (anasayfa 'N gerçek yorum' rozeti için)."""
    rows = (
        db.query(Testimonial.kind, func.count(Testimonial.id))
        .filter(Testimonial.status == TESTIMONIAL_STATUS_PUBLISHED)
        .group_by(Testimonial.kind)
        .all()
    )
    counts = {k: 0 for k in VALID_KINDS}
    for kind, n in rows:
        counts[kind] = int(n)
    counts["total"] = sum(counts[k] for k in VALID_KINDS)
    return counts


# ---------------------------------------------------------------- uygulama-içi gönderim

def has_open_pending(db: Session, user_id: int) -> bool:
    """Kullanıcının zaten incelenmeyi bekleyen bir gönderimi var mı (tekrar engelle)."""
    return (
        db.query(Testimonial.id)
        .filter(
            Testimonial.submitted_by_id == user_id,
            Testimonial.status == TESTIMONIAL_STATUS_PENDING,
        )
        .first()
        is not None
    )


def has_any_submission(db: Session, user_id: int) -> bool:
    """Kullanıcının (durumdan bağımsız) herhangi bir gönderimi var mı."""
    return (
        db.query(Testimonial.id)
        .filter(Testimonial.submitted_by_id == user_id)
        .first()
        is not None
    )


# Uygulama-içi "deneyimini paylaş" istemi yalnız bir süredir aktif kullanıcıya
# çıkar (yeni kullanıcıyı rahatsız etme).
PROMPT_MIN_ACCOUNT_AGE_DAYS = 7


def prompt_eligible(db: Session, user: User) -> bool:
    """'Deneyimini paylaş' kartı bu kullanıcıya gösterilsin mi?

    Kurallar: rol uygun + hesap yeterince eski (≥7 gün) + daha önce gönderim yapmamış.
    """
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role not in IN_APP_ALLOWED_ROLES:
        return False
    created = getattr(user, "created_at", None)
    if created is not None:
        ref = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
        if (_now() - ref).days < PROMPT_MIN_ACCOUNT_AGE_DAYS:
            return False
    if has_any_submission(db, user.id):
        return False
    return True


def submit_in_app(
    db: Session,
    *,
    user: User,
    content: str,
    rating: int | None,
    author_name: str,
    consent_public: bool,
) -> Testimonial:
    """Kullanıcı kendi deneyimini gönderir → pending (moderasyon bekler)."""
    t = Testimonial(
        kind=TESTIMONIAL_KIND_REVIEW,
        author_name=author_name.strip()[:160] or "Kullanıcı",
        author_role=user.role.value if hasattr(user.role, "value") else str(user.role),
        author_title=None,
        rating=rating if (rating and 1 <= rating <= 5) else None,
        content=content.strip(),
        status=TESTIMONIAL_STATUS_PENDING,
        source=TESTIMONIAL_SOURCE_IN_APP,
        submitted_by_id=user.id,
        consent_public=bool(consent_public),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ---------------------------------------------------------------- süper admin

def admin_list(
    db: Session, *, status: str | None = None, kind: str | None = None
) -> list[Testimonial]:
    q = db.query(Testimonial)
    if status and status in VALID_STATUSES:
        q = q.filter(Testimonial.status == status)
    if kind and kind in VALID_KINDS:
        q = q.filter(Testimonial.kind == kind)
    return q.order_by(
        # bekleyenler üstte (moderasyon kuyruğu), sonra en yeni
        (Testimonial.status == TESTIMONIAL_STATUS_PENDING).desc(),
        Testimonial.created_at.desc(),
    ).all()


def admin_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(Testimonial.status, func.count(Testimonial.id))
        .group_by(Testimonial.status)
        .all()
    )
    out = {s: 0 for s in VALID_STATUSES}
    for st, n in rows:
        out[st] = int(n)
    out["total"] = sum(out.values())
    return out


def create_manual(
    db: Session,
    *,
    admin: User,
    kind: str,
    author_name: str,
    author_role: str | None,
    author_title: str | None,
    institution_name: str | None,
    rating: int | None,
    content: str,
    status: str,
    consent_public: bool,
    featured: bool,
    sort_order: int,
) -> Testimonial:
    kind = kind if kind in VALID_KINDS else TESTIMONIAL_KIND_REVIEW
    status = status if status in VALID_STATUSES else TESTIMONIAL_STATUS_PENDING
    t = Testimonial(
        kind=kind,
        author_name=author_name.strip()[:160],
        author_role=(author_role or None),
        author_title=(author_title or None),
        institution_name=(institution_name or None),
        rating=rating if (rating and 1 <= rating <= 5) else None,
        content=content.strip(),
        status=status,
        source=TESTIMONIAL_SOURCE_MANUAL,
        reviewed_by_id=admin.id,
        consent_public=bool(consent_public),
        featured=bool(featured),
        sort_order=int(sort_order or 0),
        published_at=_now() if status == TESTIMONIAL_STATUS_PUBLISHED else None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def get(db: Session, testimonial_id: int) -> Testimonial | None:
    return db.query(Testimonial).filter(Testimonial.id == testimonial_id).first()


def update_fields(
    db: Session,
    *,
    t: Testimonial,
    admin: User,
    kind: str | None = None,
    author_name: str | None = None,
    author_role: str | None = None,
    author_title: str | None = None,
    institution_name: str | None = None,
    rating: int | None = None,
    content: str | None = None,
    consent_public: bool | None = None,
    featured: bool | None = None,
    sort_order: int | None = None,
) -> Testimonial:
    if kind is not None and kind in VALID_KINDS:
        t.kind = kind
    if author_name is not None:
        t.author_name = author_name.strip()[:160]
    if author_role is not None:
        t.author_role = author_role or None
    if author_title is not None:
        t.author_title = author_title or None
    if institution_name is not None:
        t.institution_name = institution_name or None
    if rating is not None:
        t.rating = rating if (rating and 1 <= rating <= 5) else None
    if content is not None:
        t.content = content.strip()
    if consent_public is not None:
        t.consent_public = bool(consent_public)
    if featured is not None:
        t.featured = bool(featured)
    if sort_order is not None:
        t.sort_order = int(sort_order)
    t.reviewed_by_id = admin.id
    db.commit()
    db.refresh(t)
    return t


def set_status(db: Session, *, t: Testimonial, status: str, admin: User) -> Testimonial:
    """Moderasyon: yayınla / gizle / beklemeye al."""
    if status not in VALID_STATUSES:
        raise ValueError("invalid_status")
    was_published = t.status == TESTIMONIAL_STATUS_PUBLISHED
    t.status = status
    t.reviewed_by_id = admin.id
    if status == TESTIMONIAL_STATUS_PUBLISHED and not was_published:
        t.published_at = _now()
    db.commit()
    db.refresh(t)
    return t


def delete(db: Session, *, t: Testimonial) -> None:
    db.delete(t)
    db.commit()
