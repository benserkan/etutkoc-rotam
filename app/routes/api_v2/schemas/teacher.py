"""API v2 — Öğretmen paneli Pydantic şemaları (Dalga 3 Paket 1).

İlk paket okuma sözleşmesi:
  - Dashboard (filo özeti + risk + bekleyen talep + hafta KPI)
  - Öğrenci listesi (search + filter + pagination)
  - Öğrenci detayı (360 paneli)
  - Polling rozeti
  - Öğretmenin kendi özeti

Mutation (program CRUD, request approve/reject, students CRUD) Paket 2-4'te gelir.
Bu dosya yalnız okuma şemalarını içerir.

Referans:
  - app/services/analytics.py (StudentSnapshot)
  - app/services/risk_analysis.py (RiskAssessment, warning levels)
  - app/services/request_service.py (pending_count_for_teacher)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# =============================================================================
# Ortak tipler
# =============================================================================

# Warning seviyeleri — risk_analysis.py / analytics.py ile birebir
WarningLevelLiteral = Literal["green", "amber", "red"]

# Risk seviyeleri — risk_analysis.py: RiskAssessment.level
RiskLevelLiteral = Literal["ok", "medium", "high", "critical"]


class RiskRow(BaseModel):
    """Risk panosunda tek öğrenci satırı."""
    student_id: int
    full_name: str
    level: RiskLevelLiteral
    reasons: list[str]               # kısa Türkçe açıklamalar (en fazla 3)


class DashboardRequest(BaseModel):
    """Dashboard'da öğrencinin son bekleyen talebi (özet)."""
    id: int
    student_id: int
    student_name: str
    type: Literal["change", "replace", "remove", "question", "add"]
    task_id: int | None
    task_title: str | None
    created_at: datetime


# =============================================================================
# Dashboard
# =============================================================================


class TeacherDashboardResponse(BaseModel):
    """GET /api/v2/teacher/dashboard"""
    student_count: int
    active_student_count: int
    at_risk_count: int                  # medium+ risk
    at_risk_critical: int

    pending_requests_count: int

    today_planned: int
    today_completed: int
    week_planned: int
    week_completed: int
    week_completion_rate: float         # 0..1

    fleet_red: int                      # worst_warning_level sayım
    fleet_amber: int
    fleet_green: int

    top_5_at_risk: list[RiskRow]
    recent_requests: list[DashboardRequest]


# =============================================================================
# Öğrenci listesi
# =============================================================================


class TeacherStudentListItem(BaseModel):
    """Liste satırı — filtrelenebilir."""
    id: int
    full_name: str
    email: str
    grade_level: int | None
    is_active: bool
    last_login_at: datetime | None

    # Hızlı durum göstergeleri (StudentSnapshot'tan üretilir)
    worst_warning_level: WarningLevelLiteral
    today_planned: int
    today_completed: int
    week_pct: float                     # 0..1

    has_pending_request: bool


class TeacherStudentListResponse(BaseModel):
    """GET /api/v2/teacher/students"""
    items: list[TeacherStudentListItem]
    total: int
    page: int
    page_size: int
    has_next: bool


# =============================================================================
# Öğrenci detayı (360 paneli)
# =============================================================================


class StudentBriefProfile(BaseModel):
    id: int
    full_name: str
    email: str
    grade_level: int | None
    is_active: bool
    is_graduate: bool
    institution_id: int | None
    teacher_id: int | None
    last_login_at: datetime | None
    created_at: datetime | None
    # Paket 3.5b — öğrenci detay header'ı için zenginleştirme
    # (Jinja student_detail.html:5-75 parite)
    display_grade_label: str | None = None  # "8. sınıf" / "Mezun" / vb.
    track: str | None = None                 # "sayisal" | "ea" | "sozel" | "dil"
    track_label: str | None = None           # "Sayısal" / "Eşit Ağırlık" / vb.
    track_required: bool = False
    track_missing: bool = False
    curriculum_model: str | None = None      # "lgs" | "klasik_lise" | "maarif_lise"
    curriculum_label: str | None = None      # "LGS Müfredatı" / vb.
    exam_target: str | None = None
    exam_label: str | None = None
    exam_date: str | None = None             # "YYYY-MM-DD"
    graduate_mode: str | None = None         # "full_time" | "dershane"
    academic_year_name: str | None = None


class StudentProgramSummary(BaseModel):
    """360 paneli için hızlı plan özeti."""
    today_planned: int
    today_completed: int
    today_pct: float
    week_planned: int
    week_completed: int
    week_pct: float
    consistency_7d: float               # 0..1
    hit_rate_7d: float                  # 0..1
    rate_7d: float = 0.0                # test/gün (7 günlük ortalama hız)


class StudentActivePhase(BaseModel):
    """Öğrencinin academic_year'ında bugüne denk gelen aktif dönem.

    Jinja student_detail.html:59-73 parite — winter_break/summer_camp/exam_prep
    için renkli rozet.
    """
    kind: str                           # "regular" | "winter_break" | "summer_camp" | "exam_prep"
    kind_label: str
    kind_badge: str                     # Jinja'daki kısa görsel rozet metni
    name: str                           # öğretmen tarafından adlandırılmış faz
    start_date: str                     # "YYYY-MM-DD"
    end_date: str


class TeacherStudentDetailResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}"""
    student: StudentBriefProfile
    program_summary: StudentProgramSummary
    worst_warning_level: WarningLevelLiteral
    warnings: list[str]                 # detail/title metinleri
    pending_request_count: int          # bu öğrencinin bekleyen talepleri
    # Paket 3.5b — header için aktif dönem rozeti
    active_phase: StudentActivePhase | None = None
    # Paket 3.5b — anchor edit kartı için
    week_anchor: str | None = None      # "YYYY-MM-DD" | None
    anchor_is_manual: bool = False


class SetWeekAnchorBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/set-week-anchor"""
    # "clear" stringi gönderilirse manuel anchor silinir; ISO date stringi
    # gönderilirse program_anchor_date set edilir.
    anchor: str


# =============================================================================
# Polling badge + öğretmenin kendi özeti
# =============================================================================


class TeacherBadgesResponse(BaseModel):
    """GET /api/v2/teacher/badges — 60s polling."""
    pending_request_count: int
    at_risk_count: int
    checked_at: datetime


class TeacherMeResponse(BaseModel):
    """GET /api/v2/teacher/me — hızlı kimlik + öğrenci sayısı kestirme."""
    id: int
    full_name: str
    email: str
    institution_id: int | None
    plan: str | None
    student_count: int
    active_student_count: int


# =============================================================================
# Paket 2 — Program CRUD (öğretmen perspektifi)
# =============================================================================

TaskTypeLiteral = Literal["test", "video", "ozet", "tekrar", "other"]
TaskStatusLiteral = Literal["pending", "partial", "completed", "cancelled"]


class TeacherTaskItem(BaseModel):
    """Öğretmen perspektifi — kalem detayı + rezerv/tamam exposure'ı."""
    id: int
    book_id: int
    book_name: str
    subject_id: int | None
    subject_name: str | None
    section_id: int
    section_label: str | None
    topic_name: str | None
    planned_count: int
    completed_count: int
    # Section'daki anlık rezerv/tamam durumu (öğretmen kapasiteyi anında görsün)
    section_total_tests: int
    section_reserved_count: int
    section_completed_count: int
    section_remaining: int


class TeacherTask(BaseModel):
    """Öğretmen perspektifi — bir görev tam görünüm."""
    id: int
    student_id: int
    date: str                       # "YYYY-MM-DD"
    type: TaskTypeLiteral
    status: TaskStatusLiteral
    title: str
    scheduled_hour: str | None      # "HH:00" veya None
    order: int
    is_draft: bool
    notes: str | None
    items: list[TeacherTaskItem]
    planned_count: int              # sum(items.planned_count)
    completed_count: int            # sum(items.completed_count)
    pct: float                      # 0..1
    has_pending_request: bool


class TeacherWeekNote(BaseModel):
    id: int
    body: str
    order: int
    is_done: bool


class TeacherStudentDayResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/day"""
    student_id: int
    date: str
    is_today: bool
    is_future: bool
    is_past: bool
    prev_date: str
    next_date: str
    tasks: list[TeacherTask]
    today_planned: int
    today_completed: int
    today_pct: float


class TeacherDaySubjectSummary(BaseModel):
    """Bir günün ders bazında özet rozeti — UI'da renk şeridi için."""
    subject_id: int
    subject_name: str
    task_count: int
    tests: int                       # type=test sayısı
    denemeler: int                   # type in {brans_denemesi, genel_deneme}


class TeacherSuggestionInline(BaseModel):
    """Haftalık plan içinde inline öneri — student_insights ile aynı kontrat."""
    book_id: int
    book_name: str
    book_type: str
    section_id: int
    section_label: str
    subject_id: int
    subject_name: str
    topic_name: str | None
    planned_count: int
    remaining: int
    confidence: float
    confidence_label: str
    score: float
    reasons: list[str]


class TeacherActivePhase(BaseModel):
    """Aktif akademik faz — kapasite çarpanı UI'da gösterilir."""
    kind: str                        # regular|winter_break|summer_camp|exam_prep
    kind_label: str
    kind_badge: str
    capacity_multiplier: float
    is_no_school: bool


class TeacherStudentWeekDay(BaseModel):
    date: str
    dow_label: str
    is_today: bool
    is_future: bool
    is_past: bool
    tasks_count: int
    planned: int
    completed: int
    pct: float
    tasks: list[TeacherTask]
    # Paket 3.5a — Jinja parity zenginleştirmesi (geriye uyumlu, varsayılan None/empty)
    draft_count: int = 0
    subject_summary: list[TeacherDaySubjectSummary] = []
    suggestions: list[TeacherSuggestionInline] = []


class TeacherStudentWeekResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/week"""
    student_id: int
    start_date: str
    end_date: str
    prev_start: str
    next_start: str
    week_start_anchor: str           # _student_week_start çıktısı
    days: list[TeacherStudentWeekDay]
    total_planned: int
    total_completed: int
    total_pct: float
    notes: list[TeacherWeekNote]
    # Paket 3.5a — Jinja parity zenginleştirmesi (geriye uyumlu)
    week_anchor: str | None = None
    anchor_is_manual: bool = False
    week_draft_total: int = 0
    maturity_value: float = 0.0
    maturity_label: str = ""
    weeks_observed: int = 0
    days_observed: int = 0
    active_phase: TeacherActivePhase | None = None
    track_required: bool = False
    track_missing: bool = False
    track_label: str | None = None


# =============================================================================
# Paket 3.5a — Haftalık plan ek şemaları
# =============================================================================


class WeekNoteAddBody(BaseModel):
    week_start: str                   # ISO YYYY-MM-DD
    body: str                         # >= 1 karakter (server trim eder)


class WeekNoteToggleResult(BaseModel):
    id: int
    is_done: bool


class PublishDayBody(BaseModel):
    task_date: str                    # ISO


class PublishWeekBody(BaseModel):
    week_start: str                   # ISO


class PublishResult(BaseModel):
    published_count: int
    week_draft_total: int             # sonra kalan taslak (UI banner için)


class TasksReorderBody(BaseModel):
    task_date: str                    # ISO
    task_ids: list[int]               # yeni sıra


class TasksReorderResult(BaseModel):
    reordered_count: int


class NotifyParentsBody(BaseModel):
    week_start: str                   # ISO


class NotifyParentsResult(BaseModel):
    fired: int
    skipped_recent: int
    no_tasks: bool
    message: str                      # insancıl özet


# ---- Sidebar (3 seviyeli) ----


class SidebarSection(BaseModel):
    id: int
    label: str
    topic_name: str | None
    total: int
    completed: int
    reserved: int
    remaining: int


class SidebarBook(BaseModel):
    id: int
    name: str
    type: str                         # book.type.value (test/deneme türü için unit_word)
    total: int                        # sum(sections.test_count)
    completed: int
    reserved: int
    remaining: int
    sections: list[SidebarSection]


class SidebarSubjectSummary(BaseModel):
    total: int
    completed: int
    reserved: int
    remaining: int
    books_count: int


class SidebarSubject(BaseModel):
    id: int
    name: str
    summary: SidebarSubjectSummary
    books: list[SidebarBook]


class SidebarResponse(BaseModel):
    subjects: list[SidebarSubject]
    focused_subject_id: int | None    # form'dan ders seçilince filtrelenmiş bool
    grand_total: int
    grand_completed: int
    grand_reserved: int
    grand_remaining: int


# ---- Cascade form yardımcıları ----


class BookOption(BaseModel):
    id: int
    name: str


class BookOptionsResponse(BaseModel):
    items: list[BookOption]
    subject_id: int | None


class SectionOption(BaseModel):
    id: int
    label: str
    topic_name: str | None
    remaining: int
    total: int


class SectionOptionsResponse(BaseModel):
    items: list[SectionOption]
    is_deneme: bool


class SectionStatsResponse(BaseModel):
    section_id: int
    section_label: str
    book_name: str
    topic_name: str | None
    total: int
    completed: int
    reserved: int
    remaining: int


# ---- FSRS Tekrar önerisi chip'leri ----


class ReviewStruggleChip(BaseModel):
    card_id: int
    topic_name: str
    state: str                        # "relearning" | "review" | "new" | ...
    lapse_count: int
    score: int                        # 0..100
    reasons: list[str]


class ReviewStruggleResponse(BaseModel):
    items: list[ReviewStruggleChip]
    target_date: str
    subject_id: int


# ----------------------- Mutation bodyleri -----------------------


class TaskItemBody(BaseModel):
    """POST /tasks ve POST /tasks/{id}/items için kalem."""
    book_id: int
    section_id: int
    planned_count: int               # ≥1 — service ek olarak kontrol eder


class TaskCreateBody(BaseModel):
    """POST /api/v2/teacher/students/{student_id}/tasks

    `is_draft=None` (default): smart varsayılan — gelecek tarihler taslak, bugün/geçmiş canlı.
    `is_draft=True/False`: açık değer, smart varsayılan'ı override eder.
    """
    date: str                        # "YYYY-MM-DD"
    type: TaskTypeLiteral = "test"
    title: str
    scheduled_hour: int | None = None  # 0..23
    is_draft: bool | None = None
    notes: str | None = None
    items: list[TaskItemBody]        # ≥1


class TaskPatchBody(BaseModel):
    """PATCH /api/v2/teacher/tasks/{task_id}

    None geçilen alanlar değişmez. items burada YOK — kalem değişikliği için
    dedicated endpoint'ler kullanılır (rezerv invariant'ı güvenli).
    """
    title: str | None = None
    type: TaskTypeLiteral | None = None
    scheduled_hour: int | None = None
    order: int | None = None
    is_draft: bool | None = None
    notes: str | None = None


class TaskItemPatchBody(BaseModel):
    """PATCH /api/v2/teacher/tasks/{task_id}/items/{item_id}"""
    planned_count: int


class TaskSingleItemEditBody(BaseModel):
    """PATCH /api/v2/teacher/tasks/{task_id}/single-item

    Tek kalemli görev için atomik düzenleme. Kullanıcı kaynak (book/section),
    sayıyı, tarihi ve diğer meta alanları aynı form'dan değiştirir; backend
    rezerv'i otomatik dengeler ve başlığı yeniden üretir.

    Kalem sayısı ≠ 1 ise 422 (multi_item_task).
    `book_id`/`section_id` değişti AMA `completed_count > 0` ise 422
    (source_change_with_completed).
    Yeni `planned_count < completed_count` ise 422 (planned_below_completed).
    """
    date: str                          # "YYYY-MM-DD"
    scheduled_hour: int | None = None  # 0..23 veya None = saatsiz
    type: TaskTypeLiteral
    book_id: int
    section_id: int
    planned_count: int
    notes: str | None = None
    link_url: str | None = None


class BulkTaskItem(BaseModel):
    date: str
    type: TaskTypeLiteral = "test"
    title: str
    scheduled_hour: int | None = None
    is_draft: bool = False
    notes: str | None = None
    items: list[TaskItemBody]


class BulkTasksBody(BaseModel):
    """POST /api/v2/teacher/students/{student_id}/bulk-tasks

    Atomik — hepsi geçer ya da hiçbiri. Max 20 görev. İlk hatada rollback.
    """
    tasks: list[BulkTaskItem]


class BulkResult(BaseModel):
    created_count: int
    task_ids: list[int]              # başarıyla oluşturulanlar (atomik commit sonrası)


# =============================================================================
# Paket 3 — Talep Yanıtlama (öğretmen perspektifi)
# =============================================================================

RequestTypeLiteral = Literal["change", "replace", "remove", "question", "add"]
RequestStatusLiteral = Literal["pending", "approved", "rejected", "withdrawn", "resolved"]


class TeacherRequestListItem(BaseModel):
    """Öğretmen liste satırı — kompakt, sayfalanır."""
    id: int
    student_id: int
    student_name: str
    type: RequestTypeLiteral
    status: RequestStatusLiteral
    task_id: int | None
    task_title: str | None
    task_date: str | None                  # "YYYY-MM-DD"
    message: str | None
    proposed_count: int | None
    proposed_date: str | None              # "YYYY-MM-DD"
    teacher_response: str | None
    created_at: datetime
    responded_at: datetime | None


class TeacherRequestListResponse(BaseModel):
    """GET /api/v2/teacher/requests — filtre + sayfa + bekleyen sayım."""
    items: list[TeacherRequestListItem]
    total: int
    page: int
    page_size: int
    has_next: bool
    pending_count: int                     # öğretmenin tüm bekleyen talepleri


class TeacherRequestDetail(BaseModel):
    """GET /api/v2/teacher/requests/{id} — tam detay + öneri snapshot."""
    id: int
    student_id: int
    student_name: str
    student_email: str
    type: RequestTypeLiteral
    status: RequestStatusLiteral

    # Mevcut göreve referans (varsa)
    task_id: int | None
    task_title: str | None
    task_date: str | None                  # "YYYY-MM-DD"

    message: str | None
    teacher_response: str | None

    # Önerilen değerler (CHANGE/REPLACE/ADD için)
    proposed_book_id: int | None
    proposed_book_name: str | None
    proposed_section_id: int | None
    proposed_section_label: str | None
    proposed_count: int | None
    proposed_date: str | None              # "YYYY-MM-DD"

    # Mevcut görev snapshot'ı (varsa) — diff için
    current_items: list[TeacherTaskItem] = []

    created_at: datetime
    updated_at: datetime
    responded_at: datetime | None


class RequestApproveBody(BaseModel):
    """POST /api/v2/teacher/requests/{id}/approve — opsiyonel kısa not."""
    response: str | None = None


class RequestRejectBody(BaseModel):
    """POST /api/v2/teacher/requests/{id}/reject — gerekçe zorunlu."""
    reason: str                            # boş ≠ valid (route 422 döner)


class RequestRespondBody(BaseModel):
    """POST /api/v2/teacher/requests/{id}/respond — soru cevabı."""
    response: str                          # boş ≠ valid


# =============================================================================
# Paket 4 — Students CRUD (öğrenci yönetimi)
# =============================================================================

TrackLiteral = Literal["sayisal", "ea", "sozel", "dil"]
GraduateModeLiteral = Literal["full_time", "dershane"]
ParentRelationLiteral = Literal["anne", "baba", "vasi", "diger"]


class StudentCreateBody(BaseModel):
    """POST /api/v2/teacher/students — yeni öğrenci.

    Şifre üretimi server-side; cevapta `temp_password` döner (UI bir kez gösterir).
    grade_level: 5–12 ya da None (None + is_graduate=True → mezun).
    11+ veya is_graduate=True ise `track` zorunlu (yoksa 422 track_required).
    is_graduate=True ise `graduate_mode` zorunlu (yoksa 422 graduate_mode_required).
    """
    full_name: str
    email: str
    grade_level: int | None = 8
    is_graduate: bool = False
    track: TrackLiteral | None = None
    graduate_mode: GraduateModeLiteral | None = None
    academic_year_id: int | None = None


class StudentPatchBody(BaseModel):
    """PATCH /api/v2/teacher/students/{id} — profil alanları, None geçilirse değişmez."""
    full_name: str | None = None
    grade_level: int | None = None
    is_graduate: bool | None = None
    track: TrackLiteral | None = None
    graduate_mode: GraduateModeLiteral | None = None
    academic_year_id: int | None = None


class StudentCreateResult(BaseModel):
    """Yeni öğrenci sonucu — temp_password yalnız bir kez döner."""
    id: int
    full_name: str
    email: str
    grade_level: int | None
    is_graduate: bool
    is_active: bool
    temp_password: str


class StudentBookSectionProgressRow(BaseModel):
    """Bir kitabın tek ünite/bölüm satırı — Jinja `<details>` kırılım paritesi."""
    section_id: int
    label: str
    order: int
    topic_id: int | None
    topic_name: str | None
    test_count: int
    completed_count: int
    reserved_count: int


class StudentBookListItem(BaseModel):
    """Öğrenciye atanmış kitap özet satırı.

    Ders bazlı gruplama + Jinja kart parite için ekstra alanlar (subject/publisher
    + section breakdown) doludur — geri uyumlu (eski tüketici alanları görmez).
    """
    student_book_id: int
    book_id: int
    book_name: str
    book_type: str                          # BookType.value
    book_type_label_tr: str                 # Türkçe etiket (UI'da doğrudan)
    publisher: str | None
    subject_id: int
    subject_name: str
    section_count: int
    section_total_tests: int
    section_reserved_total: int
    section_completed_total: int
    has_reservations: bool                  # silme bloklanır mı?
    sections: list[StudentBookSectionProgressRow]


class StudentBookListResponse(BaseModel):
    items: list[StudentBookListItem]
    total: int


class StudentBookAssignBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/books — kitap ata."""
    book_id: int


class StudentBookBulkAssignBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/books/bulk — birden fazla kitabı tek seferde ata.

    `book_ids` listesindeki:
      - öğretmenin sahibi olmadığı id'ler `skipped_invalid_ids`'a düşer
      - zaten atanmış olanlar `skipped_already_ids`'a düşer
      - kalanlar oluşturulur ve `assigned` listesinde döner
    """
    book_ids: list[int]


class StudentBookBulkAssignResult(BaseModel):
    assigned: list[StudentBookListItem]
    assigned_count: int
    skipped_already_ids: list[int]
    skipped_invalid_ids: list[int]


class ParentLinkItem(BaseModel):
    link_id: int
    parent_id: int
    parent_email: str
    parent_full_name: str
    relation: ParentRelationLiteral
    is_primary: bool
    muted: bool
    created_at: datetime


class PendingParentInvitation(BaseModel):
    invitation_id: int
    invited_email: str
    relation: ParentRelationLiteral
    is_primary: bool
    expires_at: datetime
    created_at: datetime


class StudentParentsResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/parents — aktif + bekleyen."""
    links: list[ParentLinkItem]
    pending_invitations: list[PendingParentInvitation]


class ParentInviteBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/parents — veli daveti."""
    parent_email: str
    relation: ParentRelationLiteral = "diger"
    is_primary: bool = False


class ParentInviteResult(BaseModel):
    invitation_id: int
    invited_email: str
    expires_at: datetime


class TeacherBookListItem(BaseModel):
    """Öğretmenin sahip olduğu bir kitabın özet bilgisi — kitap atama UI'sı için."""
    id: int
    name: str
    type: str                                # BookType.value
    subject_id: int
    subject_name: str | None
    section_count: int


class TeacherBookListResponse(BaseModel):
    items: list[TeacherBookListItem]
    total: int


# =============================================================================
# Paket 3.5c — Sınıf Yükselt / Hedefler / Tekrar / DNA / Odak
# =============================================================================

# --- Sınıf Yükselt (Promote) ---

GradeChoiceLiteral = Literal["5", "6", "7", "8", "9", "10", "11", "12", "graduate"]
TrackChoiceLiteral = Literal["sayisal", "ea", "sozel", "dil"]
GraduateModeChoiceLiteral = Literal["full_time", "dershane"]


class PromoteYearOption(BaseModel):
    id: int
    name: str
    start_year: int | None


class PromoteChoice(BaseModel):
    value: str
    label: str


class PromoteFormResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/promote-form."""
    student_id: int
    student_name: str
    current_grade_label: str
    current_track: str | None
    current_track_label: str | None
    current_curriculum_model: str | None
    current_curriculum_label: str | None
    current_exam_label: str
    current_graduate_mode: str | None
    current_academic_year_name: str | None
    entry_year_grade9: int | None
    is_graduate: bool
    years: list[PromoteYearOption]
    suggested_year_id: int | None
    suggested_grade: str
    grade_choices: list[PromoteChoice]
    track_choices: list[PromoteChoice]
    graduate_mode_choices: list[PromoteChoice]
    maarif_first_grade9_year: int = 2024


class PromoteBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/promote."""
    grade: GradeChoiceLiteral
    academic_year_id: int | None = None
    track: TrackChoiceLiteral | None = None
    graduate_mode: GraduateModeChoiceLiteral | None = None
    entry_year_grade9: int | None = None


class PromoteResult(BaseModel):
    student_id: int
    new_grade_label: str
    new_curriculum_label: str
    new_track_label: str | None
    new_graduate_mode_label: str | None
    new_academic_year_name: str | None
    message: str


# --- Odak (Focus) — read-only öğretmen görünümü ---

FocusKindLiteral = Literal["work", "short_break", "long_break"]


class FocusSessionRow(BaseModel):
    id: int
    kind: FocusKindLiteral
    started_at: datetime
    ended_at: datetime | None
    planned_minutes: int
    actual_minutes: int
    interrupted: bool
    label: str | None


class FocusBadge(BaseModel):
    kind: str
    title: str
    emoji: str
    description: str
    earned_at: datetime


class TeacherFocusResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/focus."""
    student_id: int
    student_name: str
    today_work_sessions: int
    today_work_minutes: int
    today_break_minutes: int
    today_interrupted_count: int
    streak_days: int
    longest_streak: int
    points_total: int
    work_minutes_30d: int
    badges: list[FocusBadge]
    recent_sessions: list[FocusSessionRow]


# --- DNA + Tükenmişlik ---

DnaChronotypeLiteral = Literal["morning", "afternoon", "evening", "night", "unknown"]
DnaTrendDirectionLiteral = Literal["up", "down", "flat", "insufficient"]
BurnoutRiskLevelLiteral = Literal["healthy", "watch", "warn", "critical"]
BurnoutSeverityLiteral = Literal["low", "medium", "high"]


class DnaSubjectRow(BaseModel):
    subject_id: int | None
    subject_name: str
    planned: int
    completed: int
    completion_rate: float


class DnaTrendInfo(BaseModel):
    direction: DnaTrendDirectionLiteral
    this_week_completed: int
    last_week_completed: int
    delta_pct: float | None


class BurnoutSignalRow(BaseModel):
    kind: str
    severity: BurnoutSeverityLiteral
    label: str
    emoji: str
    detail: str
    metric: float | None = None


class TeacherDnaResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/dna."""
    student_id: int
    student_name: str
    window_days: int
    has_enough_data: bool
    total_completed: int
    total_planned: int
    completion_rate: float
    chronotype: DnaChronotypeLiteral
    peak_hour: int | None
    peak_day_idx: int | None
    peak_day_name: str | None
    heatmap: list[list[int]]
    morning_count: int
    afternoon_count: int
    evening_count: int
    night_count: int
    weekend_count: int
    weekday_count: int
    by_subject: list[DnaSubjectRow]
    trend: DnaTrendInfo | None
    hour_data_confidence: int
    batch_completion_count: int
    fallback_scheduled_count: int
    burnout_risk_score: int
    burnout_risk_level: BurnoutRiskLevelLiteral
    burnout_signals: list[BurnoutSignalRow]
    parent_count: int
    parent_message_preview: str


class DnaNotifyParentBody(BaseModel):
    body: str


class DnaNotifyParentResult(BaseModel):
    note_id: int
    student_id: int
    parent_count: int


# --- Tekrar (Review / FSRS) ---

ReviewStateLiteral = Literal["new", "learning", "review", "relearning"]


class ReviewBreakdownInfo(BaseModel):
    new: int
    learning: int
    review: int
    relearning: int
    due_now: int
    total: int


class ReviewCardRow(BaseModel):
    id: int
    topic_id: int
    topic_name: str
    subject_id: int | None
    subject_name: str | None
    state: ReviewStateLiteral
    state_label: str
    due_at: datetime | None
    last_reviewed_at: datetime | None
    last_rating: int | None
    review_count: int
    lapse_count: int
    stability: float
    difficulty: float


class StruggleSectionOption(BaseModel):
    id: int
    book_id: int
    book_name: str
    label: str
    test_count: int


class StruggleCardRow(BaseModel):
    topic_id: int
    topic_name: str
    subject_id: int
    subject_name: str
    card_id: int
    state: ReviewStateLiteral
    state_label: str
    difficulty: float
    stability: float
    lapse_count: int
    review_count: int
    score: float
    reasons: list[str]
    sections: list[StruggleSectionOption]


class ReviewSubjectOption(BaseModel):
    id: int
    name: str


class TeacherReviewResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/review."""
    student_id: int
    student_name: str
    grade_label: str
    exam_label: str
    breakdown: ReviewBreakdownInfo
    cards: list[ReviewCardRow]
    subjects: list[ReviewSubjectOption]
    struggle_cards: list[StruggleCardRow]


class ReviewSeedBody(BaseModel):
    subject_id: int


class ReviewSeedResult(BaseModel):
    subject_id: int
    subject_name: str
    added: int
    skipped_existing: int


# --- Hedefler (Goals) ---

GoalKindLiteral = Literal["exam_target", "subject", "topic", "weekly", "daily", "custom"]
GoalStatusLiteral = Literal["active", "achieved", "abandoned"]


class GoalNodeRow(BaseModel):
    id: int
    parent_id: int | None
    kind: GoalKindLiteral
    kind_label: str
    kind_emoji: str
    status: GoalStatusLiteral
    title: str
    description: str | None
    target_value: float | None
    current_value: float | None
    unit: str | None
    target_date: str | None
    is_auto_generated: bool
    progress_pct: int | None
    aggregated_pct: int | None
    achieved_count: int
    total_count: int
    achieved_at: datetime | None
    created_at: datetime
    children: list["GoalNodeRow"] = []


class GoalTopicProgressRow(BaseModel):
    section_id: int
    section_label: str
    book_id: int
    book_name: str
    completed_tests: int
    target_tests: int
    progress_pct: int


class GoalSubjectProgressRow(BaseModel):
    subject_id: int
    subject_name: str
    total_completed: int
    total_target: int
    progress_pct: int
    topics: list[GoalTopicProgressRow]


class GoalSummaryInfo(BaseModel):
    total: int
    active: int
    achieved: int
    abandoned: int
    overall_pct: int | None
    next_target_date: str | None


class TeacherGoalsResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/goals."""
    student_id: int
    student_name: str
    subjects: list[GoalSubjectProgressRow]
    topic_count: int
    overall_pct: int
    roots: list[GoalNodeRow]
    summary: GoalSummaryInfo
    finished_topic_count: int
    kind_options: list[PromoteChoice]


class TeacherGoalCreateBody(BaseModel):
    title: str
    kind: GoalKindLiteral = "custom"
    parent_id: int | None = None
    description: str | None = None
    target_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    target_date: str | None = None


class TeacherGoalUpdateBody(BaseModel):
    title: str | None = None
    description: str | None = None
    target_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    target_date: str | None = None


class TeacherGoalActionResult(BaseModel):
    goal_id: int
    student_id: int
    status: GoalStatusLiteral | None = None
    deleted: bool = False


GoalNodeRow.model_rebuild()


# =============================================================================
# Paket 3.5d.1 — Analitik / Veliye Not / Fleet panoları
# =============================================================================

# --- Analitik ---


class AnalyticsTrendPoint(BaseModel):
    date: str           # ISO YYYY-MM-DD
    label: str          # "05 Eki"
    completed: int
    planned: int


class AnalyticsSubjectRow(BaseModel):
    subject_id: int
    name: str
    total: int
    completed: int
    reserved: int
    remaining: int
    percent_done: int
    percent_reserved: int
    last_completed_at: datetime | None


class TeacherStudentAnalyticsResponse(BaseModel):
    student_id: int
    student_name: str
    window_days: int
    trend: list[AnalyticsTrendPoint]
    subjects: list[AnalyticsSubjectRow]


# --- Veliye Not Gönder ---


class ParentNoteBody(BaseModel):
    body: str


class ParentNoteResult(BaseModel):
    note_id: int
    fired: int
    parent_count: int


# --- Fleet panoları (Burnout + Review) ---


class TeacherBurnoutFleetRow(BaseModel):
    student_id: int
    full_name: str
    risk_score: int
    risk_level: BurnoutRiskLevelLiteral
    signal_count: int
    is_active: bool


class TeacherBurnoutFleetResponse(BaseModel):
    rows: list[TeacherBurnoutFleetRow]
    healthy_count: int
    watch_count: int
    warn_count: int
    critical_count: int


class TeacherReviewFleetRow(BaseModel):
    student_id: int
    full_name: str
    due_now: int
    total: int
    is_active: bool


class TeacherReviewFleetResponse(BaseModel):
    rows: list[TeacherReviewFleetRow]
    total_due: int
    total_cards: int


# =============================================================================
# Paket 3.5d.2 — Dashboard warnings-feed + reset-password
# =============================================================================


class DashboardWarningRow(BaseModel):
    student_id: int
    student_name: str
    level: WarningLevelLiteral
    title: str
    detail: str
    is_paused: bool


class DashboardWarningsFeedResponse(BaseModel):
    rows: list[DashboardWarningRow]
    total: int


class StudentResetPasswordResult(BaseModel):
    student_id: int
    email: str
    temp_password: str
    full_name: str


# =============================================================================
# KP4a — Deneme sınavı sonuçları (Akademik Çıktı / Deneme Takibi)
# =============================================================================

ExamSectionLiteral = Literal["lgs", "tyt", "ayt_say", "ayt_ea", "ayt_soz", "ayt_dil"]


class ExamSectionOption(BaseModel):
    value: ExamSectionLiteral
    label: str


class ExamSubjectInput(BaseModel):
    """Ders kırılımı girişi (opsiyonel) — doluysa toplamlar bundan türetilir."""
    name: str
    correct: int = 0
    wrong: int = 0
    blank: int = 0


class ExamCreateBody(BaseModel):
    title: str
    exam_date: str  # ISO YYYY-MM-DD
    section: ExamSectionLiteral
    total_correct: int = 0
    total_wrong: int = 0
    total_blank: int = 0
    subjects: list[ExamSubjectInput] = []
    note: str | None = None


class ExamSubjectRow(BaseModel):
    name: str
    correct: int
    wrong: int
    blank: int
    net: float


class ExamResultRow(BaseModel):
    id: int
    title: str
    exam_date: str
    section: ExamSectionLiteral
    section_label: str
    total_correct: int
    total_wrong: int
    total_blank: int
    total_questions: int
    net: float
    subjects: list[ExamSubjectRow]
    note: str | None = None
    created_at: datetime
    created_by_name: str | None = None


class ExamListSummary(BaseModel):
    count: int
    avg_net: float
    best_net: float
    last_net: float | None = None
    first_net: float | None = None
    trend_delta: float | None = None  # son - ilk (gelişim)


class StudentExamListResponse(BaseModel):
    summary: ExamListSummary
    rows: list[ExamResultRow]
    section_options: list[ExamSectionOption]


# =============================================================================
# KS1 — Koçluk seansı / değerlendirme kaydı
# =============================================================================

SessionStatusLiteral = Literal["done", "postponed", "cancelled", "no_show"]
SessionChannelLiteral = Literal["in_person", "online", "phone"]


SessionCaptureSourceLiteral = Literal["manual", "voice", "photo"]


class CoachingSessionCreateBody(BaseModel):
    session_date: str  # ISO YYYY-MM-DD
    status: SessionStatusLiteral = "done"
    duration_min: int | None = None
    channel: SessionChannelLiteral | None = None
    agenda: str
    next_change: str | None = None
    coach_note: str | None = None
    mood: int | None = None  # 1-5
    tags: list[str] = []
    capture_source: SessionCaptureSourceLiteral | None = None


class CoachingSessionRow(BaseModel):
    id: int
    session_date: str
    status: SessionStatusLiteral
    status_label: str
    duration_min: int | None = None
    channel: SessionChannelLiteral | None = None
    channel_label: str | None = None
    agenda: str
    next_change: str | None = None
    coach_note: str | None = None
    mood: int | None = None
    tags: list[str]
    auto_snapshot: dict | None = None
    capture_source: str
    created_at: datetime


class CoachingSessionSummary(BaseModel):
    total: int
    done_count: int
    postponed_count: int
    cancelled_count: int
    no_show_count: int
    last_session_date: str | None = None


class StudentSessionListResponse(BaseModel):
    summary: CoachingSessionSummary
    rows: list[CoachingSessionRow]


class SessionPrefillSubject(BaseModel):
    name: str
    percent_done: int


class SessionPrefillExam(BaseModel):
    title: str
    exam_date: str
    section_label: str
    net: float
    net_pct: int | None = None


class SessionPrefillResponse(BaseModel):
    """Seans formu 'Bu haftanın verisi' otomatik paneli (Kova 1)."""
    week_planned: int
    week_completed: int
    week_completion_pct: int | None = None
    recent_rate: float
    behind_subjects: list[SessionPrefillSubject]
    latest_exam: SessionPrefillExam | None = None
    exam_count: int


# =============================================================================
# KS2 — Tahsilat (koç ↔ öğrenci)
# =============================================================================

PaymentMethodLiteral = Literal["cash", "transfer", "other"]
BillingStatusLiteral = Literal["no_rate", "paid", "partial", "pending"]


class RateUpdateBody(BaseModel):
    session_fee: int  # TL, seans başı


class PaymentCreateBody(BaseModel):
    amount: int
    paid_at: str  # ISO YYYY-MM-DD
    method: PaymentMethodLiteral = "cash"
    period_month: str | None = None  # "YYYY-MM"
    note: str | None = None


class PaymentRow(BaseModel):
    id: int
    amount: int
    paid_at: str
    method: PaymentMethodLiteral
    method_label: str
    period_month: str | None = None
    note: str | None = None
    created_at: datetime


class StudentPaymentsResponse(BaseModel):
    rows: list[PaymentRow]
    total_paid: int


class BillingStudentRow(BaseModel):
    student_id: int
    student_name: str
    session_fee: int | None = None
    done_sessions: int
    accrued: int | None = None
    paid: int
    balance: int | None = None
    status: BillingStatusLiteral


class BillingTotals(BaseModel):
    accrued: int
    paid: int
    balance: int


class BillingMonthResponse(BaseModel):
    month: str  # "YYYY-MM"
    rows: list[BillingStudentRow]
    totals: BillingTotals


# =============================================================================
# KS3a — AI yakalama (foto → metin)
# =============================================================================


class AiConsentResponse(BaseModel):
    consented: bool
    consent_at: str | None = None
    ai_premium: bool = False        # AI özellikleri ücretli pakette açık mı
    plan_code: str | None = None    # geçerli plan kodu (UI yükseltme yönlendirmesi)


class ParsePhotoBody(BaseModel):
    image_base64: str
    media_type: str  # image/jpeg | image/png | image/webp


class ParseVoiceBody(BaseModel):
    audio_base64: str
    media_type: str  # audio/webm | audio/mp4 | audio/ogg | audio/mpeg | audio/wav


class SessionDraftResponse(BaseModel):
    """AI'dan dönen seans form taslağı (KAYDEDİLMEZ — koç onaylar)."""
    agenda: str
    coach_note: str
    next_change: str
    mood: int | None = None
    tags: list[str]


class CoachingInsightResponse(BaseModel):
    """AI koçluk içgörüsü — bir sonraki seans hazırlığı (DB'de cache'lenir — öneri)."""
    summary: str
    agenda_suggestions: list[str]
    psychological_tips: list[str]
    watch_outs: list[str]
    based_on_sessions: int
    generated_at: str | None = None


class CoachingInsightCacheResponse(BaseModel):
    """İçgörü cache okuması — kredi düşmeden DB'den (None = henüz üretilmemiş)."""
    insight: CoachingInsightResponse | None = None
    is_stale: bool = False


# =============================================================================
# Bağımsız koç — Paket (plan) görüntüleme + yükseltme
# =============================================================================


class TeacherPlanOption(BaseModel):
    code: str
    label: str
    short_description: str
    price_monthly_try: int
    tier_rank: int
    ai_included: bool           # bu planda AI premium özellikleri açık mı
    is_current: bool
    is_upgrade: bool            # mevcut plandan yükseltme mi (UI buton)


class TeacherPlanResponse(BaseModel):
    plan_code: str
    plan_label: str
    is_solo: bool               # bağımsız koç mu (self-serve yükseltme uygun)
    ai_premium: bool            # şu an AI premium açık mı
    trial_active: bool
    trial_days_left: int | None = None
    options: list[TeacherPlanOption]
    note: str | None = None     # kurumlu kullanıcı için açıklama


class PlanUpgradeBody(BaseModel):
    plan: str                   # hedef solo plan kodu (solo_pro | solo_elite)
