"""API v2 — Public iletişim talebi (login gerektirmez).

Kurumlar için /pricing sayfasında fiyat gösterilmez; kurumsal bölümden form
doldurulur. Talep:
  1. `contact_requests` tablosuna kaydedilir,
  2. satış kutusuna e-posta gönderilir (email_service; EMAIL_ENABLED=false → log-only),
  3. süper admin panel → İletişim Talepleri'nde görünür.

Anti-spam: IP başına sliding-window (enforce_login_rate_limit yeniden kullanılır).
KVKK: ad/e-posta/telefon yalnız iletişime geçmek için; satış + yönetim erişir.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models.contact_request import (
    CONTACT_SOURCE_LABELS_TR,
    CONTACT_SUPPORT_SOURCES,
    ContactRequest,
)
from app.services import turnstile
from app.services.rate_limit import enforce_login_rate_limit


router = APIRouter(prefix="/contact", tags=["v2-contact-public"])


class ContactRequestIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    email: str = Field(..., min_length=3, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    institution_name: str | None = Field(default=None, max_length=200)
    coach_count: int | None = Field(default=None, ge=0, le=100000)
    message: str | None = Field(default=None, max_length=2000)
    source: str = Field(default="pricing_institution", max_length=40)
    # Cloudflare Turnstile token — yalnız CAPTCHA aktifse doğrulanır (bot/spam
    # koruması: public form → contact_requests + satışa e-posta).
    turnstile_token: str = Field(default="", max_length=4096)


class ContactRequestOut(BaseModel):
    ok: bool = True
    message: str


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("", response_model=ContactRequestOut)
def submit_contact(
    payload: ContactRequestIn,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """İletişim talebini kaydet + satışa e-posta + süper admin panele düşür."""
    # Turnstile CAPTCHA — yalnız aktifse (bot/spam talep + e-posta bombardımanı koruması)
    if turnstile.is_enabled():
        ip_raw = _client_ip(request)
        if not turnstile.verify_token(
            payload.turnstile_token,
            ip=(ip_raw if ip_raw and ip_raw != "unknown" else None),
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthenticated", "code": "captcha_failed",
                        "message": "Bot doğrulaması başarısız. Sayfayı yenile ve tekrar dene."},
            )
    # Basit email biçim doğrulaması (email-validator/EmailStr projede kullanılmıyor)
    email_clean = str(payload.email).strip().lower()
    if "@" not in email_clean or len(email_clean.split("@")) != 2 or "." not in email_clean.split("@")[1]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_email",
                    "message": "Geçerli bir e-posta gir."},
        )
    source = payload.source if payload.source in CONTACT_SOURCE_LABELS_TR else "other"
    cr = ContactRequest(
        name=payload.name.strip(),
        email=email_clean,
        phone=(payload.phone or "").strip() or None,
        institution_name=(payload.institution_name or "").strip() or None,
        coach_count=payload.coach_count,
        message=(payload.message or "").strip() or None,
        source=source,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)

    # İlgili kutuya bildir (destek konusu → destek; diğerleri → satış).
    # Best-effort; e-posta kapalıysa log-only.
    try:
        from app.services import email_service, pricing

        contact_cfg = pricing.get_pricing_catalog().get("contact") or {}
        if cr.source in CONTACT_SUPPORT_SOURCES:
            inbox = contact_cfg.get("support_email") or contact_cfg.get("sales_email")
        else:
            inbox = contact_cfg.get("sales_email") or contact_cfg.get("support_email")
        if inbox:
            email_service.send_email(
                to=inbox,
                template="contact_request_admin",
                ctx={
                    "name": cr.name,
                    "email": cr.email,
                    "phone": cr.phone,
                    "institution_name": cr.institution_name,
                    "coach_count": cr.coach_count,
                    "message": cr.message,
                    "source_label": CONTACT_SOURCE_LABELS_TR.get(cr.source, cr.source),
                },
            )
    except Exception:
        # Bildirim hatası talebi düşürmez — kayıt zaten alındı.
        pass

    return ContactRequestOut(
        ok=True,
        message="Talebiniz alındı. Ekibimiz en kısa sürede sizinle iletişime geçecek.",
    )
