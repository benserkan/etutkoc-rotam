"""Ödeme şemaları (Ödeme Paket Ö1)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PaymentInitBody(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=50)
    cycle: str = Field(..., pattern="^(monthly|annual)$")


class PaymentInitResponse(BaseModel):
    transaction_id: int
    payment_page_url: str
    iyzico_token: str
    amount: float
    currency: str
    plan_code: str
    cycle: str


class PaymentResultResponse(BaseModel):
    transaction_id: int
    status: str  # pending | 3ds_pending | succeeded | failed | expired | refunded
    status_label: str
    status_reason: str | None = None
    plan_code: str
    cycle: str
    amount: float
    currency: str
    created_at: datetime
    completed_at: datetime | None = None


class PaymentHistoryItem(BaseModel):
    id: int
    provider: str
    plan_code: str
    cycle: str
    amount: float
    currency: str
    status: str
    status_label: str
    created_at: datetime
    completed_at: datetime | None = None


class PaymentHistoryResponse(BaseModel):
    items: list[PaymentHistoryItem]
    total: int


class PaymentProviderStatus(BaseModel):
    """Frontend "Öde ve devam et" butonunu göstermeden önce check eder."""
    available: bool
    sandbox: bool  # True ise dev test modunda


# ====================================================================
# PaymentLink (Paket Ö2a) — süper admin oluşturur, kurum/koç linkten öder
# ====================================================================


class PaymentLinkCreateBody(BaseModel):
    target_owner_type: str = Field(..., pattern="^(institution|user)$")
    target_owner_id: int = Field(..., gt=0)
    plan_code: str = Field(..., min_length=1, max_length=50)
    cycle: str = Field(..., pattern="^(monthly|annual)$")
    amount: float = Field(..., gt=0)
    description: str | None = Field(None, max_length=500)
    expires_in_days: int | None = Field(14, ge=1, le=365)


class PaymentLinkItem(BaseModel):
    id: int
    token: str
    public_url: str  # tam URL — admin'in kopyalaması için
    target_owner_type: str
    target_owner_id: int
    target_owner_name: str | None = None  # kurum adı veya user adı
    plan_code: str
    cycle: str
    amount: float
    currency: str
    description: str | None = None
    status: str
    status_label: str
    expires_at: datetime | None = None
    consumed_at: datetime | None = None
    consumed_by_user_id: int | None = None
    consumed_by_user_name: str | None = None
    consumed_transaction_id: int | None = None
    created_by_admin_id: int | None = None
    created_at: datetime


class PaymentLinkListResponse(BaseModel):
    items: list[PaymentLinkItem]
    total: int


class PaymentLinkPublicInfo(BaseModel):
    """Public/auth'lı sayfa için — kurumun göreceği link özeti."""
    token: str
    target_owner_type: str
    target_owner_name: str
    plan_code: str
    plan_label: str  # sade Türkçe (örn. "Etüt Standart")
    cycle: str
    cycle_label: str  # "Aylık" / "Yıllık (10 ay peşin)"
    amount: float
    currency: str
    description: str | None = None
    status: str
    status_label: str
    expires_at: datetime | None = None
    is_usable: bool
    can_pay: bool  # giriş yapan kullanıcı bu linki ödeyebilir mi
    requires_login: bool  # link kullanıcı login gerektirir

