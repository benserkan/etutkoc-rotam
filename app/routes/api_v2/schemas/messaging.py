"""P3-P4 — Mesajlaşma API şemaları (Click-to-WhatsApp)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class WaLinkRequestBody(BaseModel):
    """POST /api/v2/messaging/wa-link body."""
    template_id: int = Field(gt=0)
    target_user_id: int = Field(gt=0)
    variables: dict[str, str] = Field(default_factory=dict)
    freeform_note: str | None = Field(default=None, max_length=1000)


class WaLinkResult(BaseModel):
    """POST /api/v2/messaging/wa-link yanıtı."""
    wa_url: str
    rendered_text: str
    target_name: str
    target_phone_masked: str
    character_count: int
    long_text: bool
    warnings: list[str] = Field(default_factory=list)
    log_id: int | None = None


# ============================================================================
# P4 — Koç/yön./admin için aktif şablon listesi (admin CRUD'dan farklı)
# ============================================================================


class WaTemplateVarBrief(BaseModel):
    key: str
    label_tr: str
    example: str = ""


class WaTemplateBrief(BaseModel):
    """Liste öğesi — gönderim dialog'unda picker için kompakt model."""
    id: int
    key: str
    category: str
    category_label_tr: str
    name_tr: str
    description: str
    content_template: str
    variables: list[WaTemplateVarBrief]
    requires_date: bool
    allow_bulk: bool
    allow_freeform_note: bool


class WaTemplatesListResponse(BaseModel):
    """GET /api/v2/messaging/templates yanıtı."""
    items: list[WaTemplateBrief]
    total: int
    categories: dict[str, str]   # key → label_tr (UI filter chip için)


class WaTargetBrief(BaseModel):
    """Hedef kullanıcı özeti — dialog header'ında gösterilir."""
    user_id: int
    full_name: str
    role: str
    phone_masked: str  # "+90 532 *** ** 67" veya "Telefon doğrulanmamış"
    phone_verified: bool


# ============================================================================
# P5 — Toplu gönderim
# ============================================================================


class BulkTargetCandidateModel(BaseModel):
    user_id: int
    full_name: str
    role: str
    phone_masked: str
    phone_verified: bool


class BulkGroupOption(BaseModel):
    """Sender rolüne göre seçilebilir hedef grubu."""
    key: str
    label_tr: str


class BulkTargetsResponse(BaseModel):
    """GET /messaging/bulk-targets?group=... yanıtı."""
    group_key: str
    group_label_tr: str
    eligible: list[BulkTargetCandidateModel]
    no_phone: list[BulkTargetCandidateModel]
    total: int
    # UI'ın hangi grupları gösterebileceği (frontend tüm group filter chip'leri)
    available_groups: list[BulkGroupOption] = Field(default_factory=list)


class BulkSendBody(BaseModel):
    """POST /messaging/bulk-link body."""
    template_id: int = Field(gt=0)
    target_user_ids: list[int] = Field(min_length=1, max_length=200)
    variables: dict[str, str] = Field(default_factory=dict)
    mode: str = Field(default="sequential")  # "sequential" | "broadcast"
    freeform_note: str | None = Field(default=None, max_length=1000)


class BulkDispatchItemModel(BaseModel):
    target_user_id: int
    target_name: str
    wa_url: str
    phone_masked: str


class BulkSkippedItemModel(BaseModel):
    target_user_id: int
    target_name: str
    reason: str


class BulkSendResponse(BaseModel):
    """POST /messaging/bulk-link yanıtı."""
    mode: str
    rendered_text: str
    items: list[BulkDispatchItemModel] = Field(default_factory=list)
    skipped: list[BulkSkippedItemModel] = Field(default_factory=list)
    total_dispatched: int
    total_skipped: int
    long_text: bool
    warnings: list[str] = Field(default_factory=list)


# ============================================================================
# P6 — Audit + Spam Guard
# ============================================================================


class DispatchStatsResponse(BaseModel):
    """GET /messaging/dispatch-stats yanıtı — koç görür.

    warning_level eşikleri (P6 spam guard):
      - "ok"        : <50 mesaj/gün
      - "yogun"     : 50-99 mesaj/gün → amber banner
      - "cok_yogun" : 100+ mesaj/gün → rose banner
    """
    today_count: int
    week_count: int
    week_start_iso: str  # YYYY-MM-DD
    warning_level: str   # "ok" | "yogun" | "cok_yogun"
    warning_message: str | None = None


# --- Admin dispatch log listesi ---


class DispatchLogItem(BaseModel):
    id: int
    sender_user_id: int
    sender_name: str
    sender_role: str
    target_user_id: int | None
    target_name: str             # "(silindi)" if None
    target_role: str | None      # None if silindi
    template_key: str
    template_name_tr: str | None  # None if şablon silinmiş
    character_count: int
    created_at: str  # ISO


class TopSenderItem(BaseModel):
    sender_user_id: int
    sender_name: str
    sender_role: str
    count: int


class DispatchLogSummary(BaseModel):
    total_today: int
    total_week: int
    total_period: int  # filter days içindeki toplam
    top_senders: list[TopSenderItem] = Field(default_factory=list)


class DispatchLogResponse(BaseModel):
    """GET /admin/whatsapp-dispatch-log yanıtı."""
    items: list[DispatchLogItem]
    total: int                          # filter sonrası toplam
    summary: DispatchLogSummary
    days: int                           # filter window (1-90)
    sender_filter_id: int | None = None
