"""Public yasal/bilgi sayfaları — auth gerektirmez.

KVKK + gizlilik + mesafeli satış + iade/iptal + kullanım şartları. Footer,
login ve signup sayfalarından erişilir. Tümü tek kaynak `legal_info.COMPANY`'den
beslenir (şirket bilgisi tek yerde düzenlenir).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.deps import get_current_user
from app.legal_info import COMPANY, is_complete
from app.models import User
from app.templating import templates


router = APIRouter()


def _ctx(request: Request, user: User | None) -> dict:
    """Tüm yasal sayfalar için ortak şablon bağlamı."""
    return {
        "request": request,
        "user": user,
        "company": COMPANY,
        "company_complete": is_complete(),
    }


@router.get("/kvkk")
def kvkk_info(request: Request, user: User | None = Depends(get_current_user)):
    """KVKK madde 11 hakları ve aydınlatma metni — Türkçe, public."""
    return templates.TemplateResponse("kvkk/info.html", _ctx(request, user))


@router.get("/privacy")
def privacy_policy(request: Request, user: User | None = Depends(get_current_user)):
    """Gizlilik politikası — public."""
    return templates.TemplateResponse("kvkk/privacy.html", _ctx(request, user))


@router.get("/mesafeli-satis")
def mesafeli_satis(request: Request, user: User | None = Depends(get_current_user)):
    """Mesafeli Satış Sözleşmesi — public (iyzico + 6502 sayılı Kanun)."""
    return templates.TemplateResponse("kvkk/mesafeli.html", _ctx(request, user))


@router.get("/iade-iptal")
def iade_iptal(request: Request, user: User | None = Depends(get_current_user)):
    """İade, İptal ve Cayma Koşulları — public."""
    return templates.TemplateResponse("kvkk/iade.html", _ctx(request, user))


@router.get("/kullanim-sartlari")
def kullanim_sartlari(request: Request, user: User | None = Depends(get_current_user)):
    """Kullanım Şartları ve Üyelik Sözleşmesi — public."""
    return templates.TemplateResponse("kvkk/kullanim.html", _ctx(request, user))
