"""P2 — WhatsApp şablon registry şemaları.

CRUD + Preview endpoint'leri için Pydantic modeller. Variables her zaman
metadata'lı liste: [{key, label_tr, example}].
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CategoryLiteral = Literal[
    "veli", "ogrenci", "kurum_ogretmen", "kurum_veli", "kurum_ogrenci",
    "admin_yonetici", "admin_sistem",
]

TargetRoleLiteral = Literal[
    "teacher", "institution_admin", "super_admin", "any",
]


class WhatsAppTemplateVar(BaseModel):
    """Tek bir şablon değişkeni — UI etiketi + örnek değer."""
    key: str = Field(min_length=1, max_length=40)
    label_tr: str = Field(min_length=1, max_length=120)
    example: str = Field(default="", max_length=200)


class WhatsAppTemplateItem(BaseModel):
    """Şablon liste/detay öğesi — tüm alanlar."""
    id: int
    key: str
    category: CategoryLiteral | str
    category_label_tr: str
    target_role: TargetRoleLiteral | str
    target_role_label_tr: str
    name_tr: str
    description: str
    content_template: str
    variables: list[WhatsAppTemplateVar]
    requires_date: bool
    allow_bulk: bool
    allow_freeform_note: bool
    sort_order: int
    is_active: bool
    updated_at: datetime
    updated_by_name: str | None = None


class WhatsAppTemplateListResponse(BaseModel):
    """GET /admin/whatsapp-templates yanıtı."""
    items: list[WhatsAppTemplateItem]
    total: int
    categories: dict[str, str]   # key → label_tr
    target_roles: dict[str, str]


class WhatsAppTemplateCreateBody(BaseModel):
    """POST /admin/whatsapp-templates body — yeni şablon."""
    key: str = Field(min_length=2, max_length=80)
    category: CategoryLiteral | str
    target_role: TargetRoleLiteral | str = "any"
    name_tr: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=600)
    content_template: str = Field(min_length=2, max_length=4000)
    variables: list[WhatsAppTemplateVar] = []
    requires_date: bool = False
    allow_bulk: bool = False
    allow_freeform_note: bool = False
    sort_order: int = 100
    is_active: bool = True


class WhatsAppTemplateUpdateBody(BaseModel):
    """POST /admin/whatsapp-templates/{id} body — key haricinde her şey."""
    category: CategoryLiteral | str
    target_role: TargetRoleLiteral | str
    name_tr: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=600)
    content_template: str = Field(min_length=2, max_length=4000)
    variables: list[WhatsAppTemplateVar] = []
    requires_date: bool
    allow_bulk: bool
    allow_freeform_note: bool
    sort_order: int
    is_active: bool


class WhatsAppTemplatePreviewBody(BaseModel):
    """POST /admin/whatsapp-templates/preview body — render örnek değerlerle."""
    content_template: str
    variables: dict[str, str] = {}  # key → value (boş ise template'deki default)
    variable_defs: list[WhatsAppTemplateVar] = []  # example fallback


class WhatsAppTemplatePreviewResult(BaseModel):
    """Render edilmiş metin + sözdizimi uyarıları."""
    rendered: str
    warnings: list[str] = []
    used_keys: list[str] = []      # şablonda bulunan değişken anahtarları
    missing_keys: list[str] = []   # variable_defs'te tanımlı ama template'de yok
    unknown_keys: list[str] = []   # template'de geçen ama defs'te yok


class WhatsAppTemplateToggleResult(BaseModel):
    message: str
    is_active: bool


class WhatsAppTemplateDeleteResult(BaseModel):
    message: str
