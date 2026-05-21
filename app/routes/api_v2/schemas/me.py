"""GET /api/v2/me + KVKK self-serve şemaları.

Referans: API_CONTRACTS_DRAFT.md §2.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# UserRole enum.value: "super_admin", "institution_admin", "teacher", "student", "parent"
RoleLiteral = Literal[
    "super_admin", "institution_admin", "teacher", "student", "parent"
]

# ParentRelation enum.value: Türkçe lowercase
ParentRelationLiteral = Literal["anne", "baba", "vasi", "diger"]

# DataRequestKind enum.value
DataRequestKindLiteral = Literal["export", "delete", "rectify"]

# DataRequestStatus enum.value
DataRequestStatusLiteral = Literal[
    "pending", "processing", "completed", "cancelled", "rejected"
]


class UserPublic(BaseModel):
    """Kullanıcı kamuya açık alanları — password REDACTED."""
    id: int
    email: str
    full_name: str
    role: RoleLiteral
    institution_id: int | None = None
    is_active: bool
    must_change_password: bool
    email_verified: bool = True
    last_login_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def from_user(cls, user) -> "UserPublic":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            institution_id=user.institution_id,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            email_verified=getattr(user, "email_verified_at", None) is not None,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )


class InstitutionRef(BaseModel):
    """Kurum özet referansı — /me yanıtında istisnasız."""
    id: int
    name: str
    slug: str | None = None


class ParentLinkRef(BaseModel):
    """Veli ↔ öğrenci eşleşmesi (yön role'a göre).

    Veli ise counterpart = öğrenci; öğrenci ise counterpart = veli.
    """
    link_id: int
    counterpart_id: int
    counterpart_name: str
    relation: ParentRelationLiteral
    relation_label_tr: str           # "Anne", "Baba", "Vasi", "Diğer"
    is_primary: bool


class DataRequestSummary(BaseModel):
    """KVKK talep özeti — son 20 talep listesinde + detayda."""
    id: int
    kind: DataRequestKindLiteral
    kind_label_tr: str
    status: DataRequestStatusLiteral
    status_label_tr: str
    reason: str | None = None
    created_at: datetime
    process_after: datetime | None = None
    processed_at: datetime | None = None
    can_cancel: bool                 # frontend butonu gizlemek için


class KvkkStatus(BaseModel):
    """Hesap KVKK durum özeti — pending delete varsa hangi tarih."""
    has_pending_delete: bool
    pending_delete_request_id: int | None = None
    pending_delete_scheduled_at: datetime | None = None
    can_export: bool = True          # ileride feature flag ile kapatılabilir


class MyAccountResponse(BaseModel):
    """GET /api/v2/me — sayfanın tek istekte ihtiyacı olan her şey."""
    user: UserPublic
    institution: InstitutionRef | None = None
    parent_links: list[ParentLinkRef] = []
    kvkk_status: KvkkStatus
    recent_requests: list[DataRequestSummary] = []


class DataDeleteRequestBody(BaseModel):
    """POST /api/v2/me/data-delete body."""
    reason: str | None = None
    confirm: bool                    # eski Form alanı 'confirm' — bool oldu


class DataDeleteResponse(BaseModel):
    """POST /api/v2/me/data-delete data alanı."""
    request_id: int
    scheduled_at: datetime           # = process_after
    can_cancel_until: datetime       # = process_after (kullanıcı kolaylığı)


# =============================================================================
# Paket 3.5d.2 — Şifre değiştirme
# =============================================================================


class PasswordChangeBody(BaseModel):
    """POST /api/v2/me/password-change body.

    current_password: must_change_password=False ise zorunlu (servise göre kontrol)
    new_password: politika + breach check
    confirm_password: new_password ile eşleşmeli
    """
    current_password: str | None = None
    new_password: str
    confirm_password: str


class PasswordChangeResult(BaseModel):
    must_change_password: bool        # always False after success
    password_changed_at: datetime


# ---------------------------- 2FA / TOTP (Dalga 7 P4) ----------------------------


class TwoFactorStatus(BaseModel):
    """GET /api/v2/me/2fa/status."""
    available: bool          # rol 2FA kullanabilir mi (super_admin / institution_admin)
    enabled: bool            # 2FA aktif mi
    pending_setup: bool      # secret üretildi ama henüz enable edilmedi
    remaining_backup_codes: int = 0


class TwoFactorSetupResult(BaseModel):
    """POST /api/v2/me/2fa/setup — secret + QR + yedek kodlar (bir kez gösterilir)."""
    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class TwoFactorCodeBody(BaseModel):
    code: str


class TwoFactorMutationResult(BaseModel):
    message: str
    enabled: bool


# ---------------------------- Aktif oturumlar (Dalga 7 P5) ----------------------------


class ActiveSessionItem(BaseModel):
    """GET /api/v2/me/sessions satırı — kullanıcının kendi cihazları."""
    session_token: str               # revoke için (kısmi maskeleme frontend)
    ip: str | None = None
    user_agent: str | None = None
    login_at: datetime | None = None
    last_seen_at: datetime | None = None
    idle_seconds: int
    is_current: bool                 # bu istek bu oturumdan mı geldi


class SessionsResponse(BaseModel):
    sessions: list[ActiveSessionItem]


class SessionRevokeResult(BaseModel):
    message: str
