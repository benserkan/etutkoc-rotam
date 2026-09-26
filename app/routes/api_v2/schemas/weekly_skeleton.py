"""Haftalık İskelet şemaları (F1, 2026-09-25)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SkeletonSlotIn(BaseModel):
    weekday: int = Field(ge=0, le=6)          # 0=Pazartesi … 6=Pazar
    period: str | None = None                 # morning|noon|evening|None
    subject_id: int
    position: int = 0
    is_routine: bool = False
    default_count: int | None = Field(default=None, ge=1, le=100)
    # F2-1 kaynak: kitap (rutin kitabı / konu satırında öncelikli kitap) ya da
    # kitapsız görevin başlığı (label). routine_mode: sirali | karma
    book_id: int | None = None
    label: str | None = Field(default=None, max_length=160)
    routine_mode: str | None = None
    # F2-3 çapa: okulda/dershanede işlenen ders (sabit gün)
    is_anchor: bool = False


class SkeletonSlotOut(SkeletonSlotIn):
    id: int
    subject_name: str
    book_name: str | None = None


class SkeletonSubjectOption(BaseModel):
    id: int
    name: str


class SkeletonBookOption(BaseModel):
    id: int
    name: str
    subject_id: int


class SkeletonPeriodItem(BaseModel):
    """F2-2 dönem: yalnız başlangıç tarihi taşır, bir sonraki dönem başlayana kadar geçerli."""
    id: int
    name: str
    valid_from: str | None = None   # None = en baştan beri
    valid_until: str | None = None  # None = açık uçlu (güncel ya da ileride)
    slot_count: int
    is_current: bool                # bugün geçerli dönem
    source: str | None = None


class CapacityItem(BaseModel):
    weekday: int
    learned: int | None = None     # geçmişten öğrenilen tipik test sayısı
    override: int | None = None    # koçun elle düzeltmesi
    effective: int | None = None   # kullanılan (düzeltme > öğrenilen)


class SkeletonResponse(BaseModel):
    exists: bool
    id: int | None = None
    name: str | None = None
    source: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    periods: list[SkeletonPeriodItem] = []
    capacity: list[CapacityItem] = []
    slots: list[SkeletonSlotOut] = []
    subjects: list[SkeletonSubjectOption] = []
    books: list[SkeletonBookOption] = []


class SkeletonSaveBody(BaseModel):
    skeleton_id: int | None = None   # None = bugün geçerli dönem
    name: str | None = None
    # Hafta günü → test kapasitesi düzeltmesi (None = öğrenilen değere dön)
    day_capacity: dict[int, int | None] | None = None
    slots: list[SkeletonSlotIn] = Field(default_factory=list, max_length=120)


class SkeletonFromWeekBody(BaseModel):
    start: str
    end: str
    # replace: seçili (ya da bugün geçerli) dönemin satırlarını değiştir ·
    # new: bu haftanın başından YENİ DÖNEM başlat (eski dönem silinmez)
    mode: str = "replace"
    skeleton_id: int | None = None
    name: str | None = Field(default=None, max_length=120)


class SkeletonDeleteBody(BaseModel):
    skeleton_id: int | None = None


class PeriodCreateBody(BaseModel):
    valid_from: str
    name: str | None = Field(default=None, max_length=120)
    copy_from_id: int | None = None   # verilirse o dönemin satırları kopyalanır


class PeriodUpdateBody(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    valid_from: str | None = None
    clear_start: bool = False         # başlangıcı kaldır ("en baştan beri")


class ChipBadge(BaseModel):
    code: str
    label: str
    tone: str


class ChipItem(BaseModel):
    section_id: int
    section_label: str
    count: int


class GhostChip(BaseModel):
    rank: int
    kind: str                                 # thread|next|new|weak
    section_id: int
    book_id: int
    book_name: str
    section_label: str
    topic_id: int | None = None
    topic_name: str | None = None
    count: int
    remaining: int
    total: int
    reason: str
    badges: list[ChipBadge] = []
    # Kitaba bağlı rutin çipi birden çok bölümü kapsayabilir (karışık/sıralı taşma)
    items: list[ChipItem] | None = None


class GhostCell(BaseModel):
    slot_id: int
    date: str
    subject_id: int
    subject_name: str
    period: str | None = None
    position: int
    is_routine: bool
    book_id: int | None = None
    book_name: str | None = None
    label: str | None = None
    routine_mode: str | None = None
    is_anchor: bool = False
    chips: list[GhostChip] = []


class GhostDay(BaseModel):
    date: str
    ghosts: list[GhostCell] = []


class GhostsResponse(BaseModel):
    has_skeleton: bool
    days: list[GhostDay] = []


class AcceptItem(BaseModel):
    section_id: int
    count: int = Field(ge=1, le=100)


class GhostAcceptBody(BaseModel):
    slot_id: int
    date: str
    section_id: int | None = None
    count: int = Field(default=1, ge=1, le=100)
    # Çok kalemli (rutin) çip — verilirse section_id/count yok sayılır
    items: list[AcceptItem] | None = Field(default=None, max_length=12)
    # Kitapsız satır: etiketiyle ETKİNLİK görevi yaz ("345 Sıfır Risk Paragraf 2 Test")
    as_activity: bool = False
    chip_rank: int | None = None              # None = çip dışı seçim ("başka konu")
    chip_kind: str | None = None
    chip_count: int | None = None


class GhostActionBody(BaseModel):
    slot_id: int
    date: str
    action: str                               # dismissed|restore


class GhostRoutineBody(BaseModel):
    date: str
    # Verilirse date..end arası tüm günlerin rutinleri sırayla yazılır (≤14 gün)
    end: str | None = None


class GhostAcceptResult(BaseModel):
    task_ids: list[int] = []
    created: int = 0


class GhostAcceptanceReport(BaseModel):
    actions: int
    accepted: int
    other: int
    dismissed: int
    acceptance_pct: int | None = None
    by_rank: dict[int, int] = {}
    by_kind: dict[str, int] = {}


# ---------------------------------------------------------------- konuyu yay (F2-3)


class SpreadItem(BaseModel):
    section_id: int
    section_label: str
    book_id: int
    book_name: str
    count: int


class SpreadDay(BaseModel):
    date: str
    capacity: int | None = None
    planned: int = 0
    anchor_reserve: int = 0
    free: int | None = None
    items: list[SpreadItem] = []


class SpreadSkip(BaseModel):
    date: str
    capacity: int | None = None
    planned: int = 0
    anchor_reserve: int = 0
    reason: str


class SpreadPreview(BaseModel):
    topic_id: int | None = None
    section_id: int | None = None
    subject_id: int | None = None
    per_day: int
    start: str
    window_end: str | None = None
    stop_reason: str | None = None
    total_remaining: int = 0
    leftover: int = 0
    days: list[SpreadDay] = []
    skipped: list[SpreadSkip] = []


class SpreadApplyItem(BaseModel):
    section_id: int
    count: int = Field(ge=1, le=100)


class SpreadApplyDay(BaseModel):
    date: str
    items: list[SpreadApplyItem] = Field(default_factory=list, max_length=12)


class SpreadApplyBody(BaseModel):
    days: list[SpreadApplyDay] = Field(default_factory=list, max_length=14)
