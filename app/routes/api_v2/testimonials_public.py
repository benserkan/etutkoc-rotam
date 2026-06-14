"""API v2 — Testimonial (sosyal kanıt).

İki yüzey:
  - GET /api/v2/testimonials  → public (login'siz): anasayfada yayınlanmış kayıtlar
    + sayımlar. kind filtresi opsiyonel.
  - POST /api/v2/testimonials/submit → authed (öğrenci/veli/koç/kurum yöneticisi):
    kendi deneyimini gönderir → pending (süper admin yayınlar).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import TESTIMONIAL_ROLE_LABELS_TR, Testimonial, User
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.testimonial import (
    TestimonialPromptOut,
    TestimonialPublicItem,
    TestimonialPublicResponse,
    TestimonialSubmitBody,
    TestimonialSubmitOut,
)
from app.services import testimonial_service as svc

router = APIRouter(prefix="/testimonials", tags=["v2-testimonials"])


def _to_public(t: Testimonial) -> TestimonialPublicItem:
    return TestimonialPublicItem(
        id=t.id,
        kind=t.kind,
        author_name=t.author_name,
        author_role=t.author_role,
        author_role_label=TESTIMONIAL_ROLE_LABELS_TR.get(t.author_role or "", None),
        author_title=t.author_title,
        institution_name=t.institution_name,
        rating=t.rating,
        content=t.content,
        featured=t.featured,
    )


@router.get("", response_model=TestimonialPublicResponse)
def public_testimonials(
    kind: str | None = Query(None, max_length=30),
    limit: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Anasayfada gösterilecek yayınlanmış sosyal kanıt + sayımlar."""
    rows = svc.list_published(db, kind=kind, limit=limit)
    return TestimonialPublicResponse(
        items=[_to_public(t) for t in rows],
        counts=svc.published_counts(db),
    )


@router.get("/prompt", response_model=TestimonialPromptOut)
def testimonial_prompt(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """'Deneyimini paylaş' kartı bu kullanıcıya gösterilsin mi (rol+yaş+gönderim)."""
    return TestimonialPromptOut(
        eligible=svc.prompt_eligible(db, user),
        default_name=(user.full_name or "").strip() or None,
    )


@router.post("/submit", response_model=TestimonialSubmitOut)
def submit_testimonial(
    body: TestimonialSubmitBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Kullanıcı kendi deneyimini paylaşır → moderasyon kuyruğuna (pending)."""
    role = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role not in svc.IN_APP_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "role_not_allowed",
                    "message": "Bu roldan yorum gönderilemez."},
        )
    if svc.has_open_pending(db, user.id):
        return TestimonialSubmitOut(
            ok=True,
            already_pending=True,
            message="Daha önce gönderdiğin yorum inceleniyor. Teşekkürler!",
        )
    svc.submit_in_app(
        db,
        user=user,
        content=body.content,
        rating=body.rating,
        author_name=body.author_name,
        consent_public=body.consent_public,
    )
    return TestimonialSubmitOut(
        ok=True,
        message="Yorumun alındı. İncelendikten sonra yayınlanabilir. Teşekkürler!",
    )
