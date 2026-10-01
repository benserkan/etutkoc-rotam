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
    # F2-4: rutin kapsamı 'book' | 'problems' · konu satırının 2. ana kaynağı
    routine_scope: str | None = None
    second_book_id: int | None = None


class SkeletonSlotOut(SkeletonSlotIn):
    id: int
    subject_name: str
    book_name: str | None = None
    second_book_name: str | None = None


class SkeletonSubjectOption(BaseModel):
    id: int
    name: str


class SkeletonBookOption(BaseModel):
    id: int
    name: str
    subject_id: int
    # F2-4: yalnız soru bankası ana kaynak / 2. kaynak / problem kaynağı olabilir
    book_type: str | None = None
    is_bank: bool = False
    has_problems: bool = False
    # Deneme kitabı: öneri 'sıradaki deneme' (kaldığı yerden sırayla)
    is_deneme: bool = False


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
    book_id: int | None = None
    book_name: str | None = None


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
    # F2-4: 1. kaynakta konu bitti — koçun seçmesi gereken çiplerden biri
    source_choice: bool = False


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
    routine_scope: str | None = None
    second_book_id: int | None = None
    second_book_name: str | None = None
    source_choice: bool = False
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
    # True → hiçbir şey yazılmaz; yazılacak görevler gün gün döner (önizleme).
    # Gerçek yazma döngüsü aynen çalışıp işlem geri alındığı için önizleme ile
    # yazılan birebir aynıdır.
    dry_run: bool = False


class RoutinePreviewItem(BaseModel):
    book_name: str | None = None
    section_label: str | None = None
    count: int = 0


class RoutinePreviewTask(BaseModel):
    date: str
    subject_name: str
    title: str
    planned: int = 0
    is_activity: bool = False
    too_many: bool = False                    # günlük rutin adedi olağandışı
    items: list[RoutinePreviewItem] = []


class GhostAcceptResult(BaseModel):
    task_ids: list[int] = []
    created: int = 0
    preview: list[RoutinePreviewTask] = []


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



# --- İskeleti başka öğrencilere kopyala (2026-09-27) ---------------------------


class SkeletonCopyBookRef(BaseModel):
    id: int
    name: str


class SkeletonCopyCandidate(BaseModel):
    student_id: int
    full_name: str
    grade_label: str
    class_group: str | None = None
    period_count: int
    period_starts: list[str | None]          # hedefin dönem başlangıçları (ISO)
    current_period_name: str | None = None   # bugün geçerli dönem (replace modunda değişir)
    current_slot_count: int = 0
    missing_books: list[SkeletonCopyBookRef]  # kaynaktaki kitaplardan öğrencide olmayanlar


class SkeletonCopyCandidatesResponse(BaseModel):
    source_skeleton_id: int
    source_name: str
    source_valid_from: str | None = None
    source_slot_count: int
    source_books: list[SkeletonCopyBookRef]
    candidates: list[SkeletonCopyCandidate]


class SkeletonCopyBody(BaseModel):
    skeleton_id: int
    target_ids: list[int] = Field(min_length=1, max_length=200)
    mode: str = "new"                        # new | replace
    valid_from: str | None = None            # new modunda zorunlu
    name: str | None = Field(default=None, max_length=120)
    assign_missing_books: bool = True


class SkeletonCopyStudentResult(BaseModel):
    student_id: int
    full_name: str
    skeleton_id: int
    slot_count: int
    books_assigned: int
    slots_without_book: int


class SkeletonCopyResult(BaseModel):
    students: list[SkeletonCopyStudentResult]
    skipped_invalid_ids: list[int]
