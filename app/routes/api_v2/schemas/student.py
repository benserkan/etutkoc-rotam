"""API v2 — Öğrenci paneli Pydantic şemaları (Dalga 2 Paket 1).

Mevcut `app/routes/student.py` Jinja handler'larının ürettiği veriyi
JSON kontratına çevirir. Yan etki içermez — yalnız okuma şemaları.

Referans:
  - MIGRATION_INVENTORY (student.py: 10 endpoint)
  - API_CONTRACTS_DRAFT §3 (StudentDayResponse + alt tipler)
  - app/models/progress.py (StudentBook properties)
  - app/services/analytics.py (StudentSnapshot, Projection)
"""
from __future__ import annotations

from datetime import date as DateT, datetime
from typing import Literal

from pydantic import BaseModel


# Task.type enum — app/models/task.py:TaskType ile birebir 5 değer
TaskTypeLiteral = Literal["test", "video", "ozet", "tekrar", "other"]

# Task.status enum — app/models/task.py:TaskStatus ile birebir 4 değer
TaskStatusLiteral = Literal["pending", "partial", "completed", "cancelled"]

# Book.type enum — app/models/book.py:BookType ile birebir 5 değer
BookTypeLiteral = Literal[
    "soru_bankasi",
    "fasikul",
    "konu_anlatimli",
    "brans_denemesi",
    "genel_deneme",
]

# Talep tipleri — student_requests.py'da kullanılan
RequestTypeLiteral = Literal["change", "replace", "remove", "question", "add"]

# Cell state — sinema-koltuk grid
CellStateLiteral = Literal["DONE", "RESERVED", "FREE"]

# Projection metodolojisi
ProjectionMethodLiteral = Literal["naive", "dow_weighted"]
ProjectionConfidenceLiteral = Literal["low", "medium", "high"]

# DOW labels (ISO Mon=0..Sun=6 → mapped)
DOW_KEYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


# ============================================================================
# Görev kalemi + görev
# ============================================================================


class StudentTaskItem(BaseModel):
    """Görev içindeki tek kalem (kitap bölümü × planlanan sayı)."""
    id: int
    book_id: int
    book_name: str
    section_id: int | None = None
    section_label: str | None = None
    topic_name: str | None = None
    planned: int                   # planned_count
    completed: int                 # completed_count
    is_full: bool                  # planned == completed
    max_completable: int           # set-completed için tavan (basit: planned_count + section_remaining)


class StudentTask(BaseModel):
    """Tek görev — tipik olarak 1 kalem (basit görev), bazen çoklu."""
    id: int
    title: str
    type: TaskTypeLiteral
    status: TaskStatusLiteral
    date: str                      # "YYYY-MM-DD"
    scheduled_hour: str | None     # "HH:MM" veya None
    items: list[StudentTaskItem]
    planned_count: int             # sum(items.planned)
    completed_count: int           # sum(items.completed)
    pct: float                     # 0..1
    is_future_blocked: bool        # tıklanamaz
    is_past: bool
    has_pending_request: bool      # bu görev için bekleyen TaskRequest var mı


# ============================================================================
# Gün özeti + sidebar (Kaynak Durumu) + projeksiyon
# ============================================================================


class DaySummary(BaseModel):
    total_tasks: int
    total_items: int
    planned_count: int
    completed_count: int
    pct: float                     # 0..1


class ResourceBook(BaseModel):
    """Bir kitabın anlık kalan/rezerv/tamam görünümü."""
    student_book_id: int
    book_id: int
    book_name: str
    book_type: BookTypeLiteral
    total_tests: int
    reserved_tests: int
    completed_tests: int
    remaining_tests: int


class ResourceSubjectGroup(BaseModel):
    """Ders bazlı kitap grupları (sidebar'da accordion için)."""
    subject_id: int
    subject_name: str
    total_tests: int
    reserved_tests: int
    completed_tests: int
    remaining_tests: int
    books: list[ResourceBook]


class ResourceSidebar(BaseModel):
    """Sticky XL sidebar verisi — Kaynak Durumu."""
    total_tests: int
    reserved_tests: int
    completed_tests: int
    remaining_tests: int
    subjects: list[ResourceSubjectGroup]


class ProjectionPanel(BaseModel):
    """Sınav projeksiyon paneli — DOW bazlı forward walk."""
    exam_date: str | None          # "YYYY-MM-DD"
    days_left: int | None
    effective_days: int            # tampon hariç
    buffer_days: int
    methodology: ProjectionMethodLiteral
    confidence_level: ProjectionConfidenceLiteral
    rate_per_day: float
    projected_completable: int
    gap: int                       # + = sınava yetişir, − = yetersiz
    required_rate: float
    # DOW haftagünleri için tutturma oranı (0..1). None = ölçülemedi.
    dow_hit_rates: dict[str, float | None]
    dow_hit_measured: dict[str, bool]


class CanRequestMatrix(BaseModel):
    """Frontend butonlarını göstermek/gizlemek için izin matrisi."""
    change: bool                   # sayı değiştir
    replace: bool                  # kaynak değiştir
    remove: bool                   # çıkar
    question: bool                 # soru
    add: bool                      # yeni görev ekle (gün üzerinden)


# ============================================================================
# Day view response
# ============================================================================


class StudentDayResponse(BaseModel):
    """GET /api/v2/student/day?date=..."""
    date: str                      # "YYYY-MM-DD"
    is_today: bool
    is_future: bool
    is_past: bool
    prev_date: str
    next_date: str
    tasks: list[StudentTask]
    summary: DaySummary
    sidebar: ResourceSidebar
    projection: ProjectionPanel | None
    can_request: CanRequestMatrix


# ============================================================================
# Week view response (salt-okunur 7 gün penceresi)
# ============================================================================


class StudentWeekDay(BaseModel):
    """Haftanın bir günü — özet + görevler (read-only)."""
    date: str                      # "YYYY-MM-DD"
    dow_label: str                 # "Pazartesi"
    is_today: bool
    is_future: bool
    is_past: bool
    tasks_count: int
    planned: int
    completed: int
    pct: float                     # 0..1
    tasks: list[StudentTask]


class StudentWeekResponse(BaseModel):
    """GET /api/v2/student/week?start=..."""
    start_date: str
    end_date: str
    prev_start: str
    next_start: str
    days: list[StudentWeekDay]     # 7 gün
    total_planned: int
    total_completed: int
    total_pct: float


# ============================================================================
# Week PRINT — A4 yazdırma için optimize edilmiş payload
# ============================================================================


class WeekPrintTask(BaseModel):
    """Tek görev satırı, yazdırma için sadeleştirilmiş.

    is_single_item=True → tek kalemli; book_name + section_label + planned_count
    kompakt biçimde gösterilir. False ise title + toplam planned gösterilir.
    """
    title: str
    is_single_item: bool
    book_name: str | None = None
    section_label: str | None = None
    topic_name: str | None = None
    planned_count: int                  # tek kalem ise it.planned_count, çoklu ise toplam
    type_label: str | None = None        # çoklu/diğer tip için ek etiket


class WeekPrintDay(BaseModel):
    date: str                           # "YYYY-MM-DD"
    day_of_month: int
    month_index: int                    # 0..11
    dow_index: int                      # 0=Pzt..6=Paz
    dow_label: str                      # "Pazartesi"
    month_label: str                    # "Mayıs"
    task_count: int
    history_pct: int | None             # geçmiş 12 aynı gündeki ortalama tamamlama yüzdesi
    history_samples: int                # ölçümde kullanılan planlı görev toplamı
    tasks: list[WeekPrintTask]


class WeekPrintResponse(BaseModel):
    """GET /api/v2/student/week-print?start=YYYY-MM-DD"""
    student_name: str
    grade_level: int | None
    academic_year_name: str | None
    exam_label: str | None
    exam_date: str | None
    start_date: str
    end_date: str
    start_day: int
    start_month_label: str
    start_dow_label: str
    end_day: int
    end_month_label: str
    end_year: int
    days: list[WeekPrintDay]            # 7 gün
    week_notes: list[str]               # WeekNote.body listesi (üst-sıralamada gelen)


# ============================================================================
# Books envanteri response
# ============================================================================


class StudentBooksResponse(BaseModel):
    """GET /api/v2/student/books — öğrenciye atanmış tüm kitaplar."""
    total_tests: int
    reserved_tests: int
    completed_tests: int
    remaining_tests: int
    subjects: list[ResourceSubjectGroup]


# ============================================================================
# Book grid (sinema-koltuk) response
# ============================================================================


class BookCell(BaseModel):
    """Sinema-koltuk grid'inde bir hücre.

    state:
      DONE      → çözüldü (yeşil)
      RESERVED  → rezerve (sarı, gelecekteki görev)
      FREE      → boş (gri)
    """
    number: int                    # 1..test_count (kitap içi sıra)
    state: CellStateLiteral
    task_id: int | None = None
    task_date: str | None = None   # "YYYY-MM-DD"


class BookSectionGrid(BaseModel):
    """Kitap bölümü + hücre listesi."""
    section_id: int
    label: str
    topic_name: str | None
    test_count: int
    completed: int
    reserved: int
    cells: list[BookCell]          # exactly test_count adet


class BookGridResponse(BaseModel):
    """GET /api/v2/student/book-grid?book_id=..."""
    student_book_id: int
    book_id: int
    book_name: str
    subject_name: str
    book_type: BookTypeLiteral
    total_tests: int
    total_completed: int
    total_reserved: int
    sections: list[BookSectionGrid]


# ============================================================================
# Cascade — book sections (Kaynağı değiştir / Ekle modali için)
# ============================================================================


class BookSectionOption(BaseModel):
    """GET /api/v2/student/book-sections?book_id=... — bir kalem."""
    id: int
    label: str
    topic_name: str | None
    remaining: int        # kalan kapasite (rezerv + tamamlanan çıkarılmış)
    total: int            # bölümün toplam test sayısı


class BookSectionsResponse(BaseModel):
    """GET /api/v2/student/book-sections?book_id=..."""
    book_id: int
    is_deneme: bool
    items: list[BookSectionOption]


# ============================================================================
# Polling badges
# ============================================================================


class PendingBadgesResponse(BaseModel):
    """GET /api/v2/student/badges — 60s polling.

    Öğretmenden yanıt bekleyen talep sayısı (PENDING). Mevcut Jinja
    `/_partial/student-pending-count` ile aynı sayım.
    """
    pending_count: int
    today_open_count: int = 0   # bugünün tamamlanmamış görevleri (tikleyince düşer)
    checked_at: datetime


# ============================================================================
# Mutation request body'leri (Paket 2 — OOB swap karşılığı)
# ============================================================================


class SetCompletedBody(BaseModel):
    """POST /api/v2/student/tasks/{task_id}/items/{item_id}/set-completed body.

    Service `set_item_completion` üst sınırı `planned_count`'a klampler;
    negatif değerleri 0'a klampler. Bu yüzden ek tip kısıtlaması koymadan
    `int` alıyoruz (negatif test edilebilir → service 0'a düşürür).
    """
    completed: int


# ============================================================================
# Paket 3 — Student Requests (talep sistemi) gövdeleri ve şemaları
# ============================================================================


RequestStatusLiteral = Literal["pending", "approved", "rejected", "withdrawn", "resolved"]


class ChangeRequestBody(BaseModel):
    """POST /api/v2/student/tasks/{task_id}/requests/change body."""
    proposed_count: int
    message: str | None = None


class ReplaceRequestBody(BaseModel):
    """POST /api/v2/student/tasks/{task_id}/requests/replace body."""
    new_book_id: int
    new_section_id: int
    new_count: int
    message: str | None = None


class RemoveRequestBody(BaseModel):
    """POST /api/v2/student/tasks/{task_id}/requests/remove body."""
    message: str | None = None


class QuestionRequestBody(BaseModel):
    """POST /api/v2/student/tasks/{task_id}/requests/question body."""
    message: str


class AddRequestBody(BaseModel):
    """POST /api/v2/student/days/{date}/requests/add body."""
    book_id: int
    section_id: int
    proposed_count: int
    message: str | None = None


class StudentRequestItem(BaseModel):
    """Bir TaskRequest kaydının JSON sözleşmesi (öğrenci perspektifi)."""
    id: int
    type: RequestTypeLiteral
    status: RequestStatusLiteral
    task_id: int | None = None
    task_title: str | None = None
    task_date: str | None = None              # "YYYY-MM-DD"
    message: str | None = None
    proposed_book_id: int | None = None
    proposed_book_name: str | None = None
    proposed_section_id: int | None = None
    proposed_section_label: str | None = None
    proposed_count: int | None = None
    proposed_date: str | None = None          # "YYYY-MM-DD"
    teacher_response: str | None = None
    created_at: datetime
    responded_at: datetime | None = None


class StudentRequestListResponse(BaseModel):
    """GET /api/v2/student/requests — filtreleme + sayım."""
    items: list[StudentRequestItem]
    total: int
    pending_count: int


# ============================================================================
# Paket 4 — Secondary features (focus / dna / review / goals)
# ============================================================================


# -------------------- Focus (Pomodoro) --------------------


PomodoroKindLiteral = Literal["work", "short_break", "long_break"]


class FocusSession(BaseModel):
    """Bir pomodoro seansı (aktif veya bitmiş)."""
    id: int
    kind: PomodoroKindLiteral
    started_at: datetime
    ended_at: datetime | None = None
    planned_minutes: int
    actual_minutes: int
    interrupted: bool
    label: str | None = None
    is_active: bool                  # ended_at is None
    elapsed_seconds: int = 0         # server-computed for active sessions


class FocusTodaySummary(BaseModel):
    """Bugünkü pomodoro özeti (TR günü, UTC pencere)."""
    work_sessions: int
    work_minutes: int
    break_minutes: int
    total_minutes: int
    interrupted_count: int


class FocusResponse(BaseModel):
    """GET /api/v2/student/focus — pomodoro paneli verisi."""
    active_session: FocusSession | None
    today: FocusTodaySummary
    recent_sessions: list[FocusSession]
    streak_days: int
    points: int


class FocusStartBody(BaseModel):
    """POST /api/v2/student/focus/start body.

    Service `start_session` planned_minutes'u [5, 120] aralığına klampler;
    kind geçersizse WORK'e düşer. Ek kısıtlamayı service'e bırakıyoruz.
    """
    planned_minutes: int = 25
    kind: PomodoroKindLiteral = "work"
    label: str | None = None


class FocusEndBody(BaseModel):
    """POST /api/v2/student/focus/{session_id}/stop body.

    actual_minutes None ise server now-started_at'ten hesaplar.
    """
    actual_minutes: int | None = None
    interrupted: bool = False


# -------------------- DNA (Çalışma profili) --------------------


DnaChronotypeLiteral = Literal["morning", "afternoon", "evening", "night", "unknown"]
DnaTrendDirectionLiteral = Literal["up", "down", "flat", "insufficient"]
BurnoutRiskLevelLiteral = Literal["healthy", "watch", "warn", "critical"]


class DnaSubjectActivity(BaseModel):
    subject_id: int | None
    subject_name: str
    planned: int
    completed: int
    completion_rate: float


class DnaTrend(BaseModel):
    direction: DnaTrendDirectionLiteral
    this_week_completed: int
    last_week_completed: int
    delta_pct: float | None


class BurnoutSignal(BaseModel):
    kind: str
    severity: Literal["low", "medium", "high"]
    label: str
    emoji: str
    detail: str
    metric: float | None = None


class DnaResponse(BaseModel):
    """GET /api/v2/student/dna — çalışma DNA profili + burnout."""
    window_days: int
    has_enough_data: bool
    total_completed: int
    total_planned: int
    completion_rate: float
    chronotype: DnaChronotypeLiteral
    peak_hour: int | None
    peak_day_idx: int | None
    peak_day_name: str | None
    heatmap: list[list[int]]          # 7×24 (0=Pzt..6=Paz)
    morning_count: int
    afternoon_count: int
    evening_count: int
    night_count: int
    weekend_count: int
    weekday_count: int
    by_subject: list[DnaSubjectActivity]
    trend: DnaTrend | None
    hour_data_confidence: int
    burnout_risk_score: int
    burnout_risk_level: BurnoutRiskLevelLiteral
    burnout_signals: list[BurnoutSignal]


# -------------------- Review (FSRS spaced repetition) --------------------


ReviewStateLiteral = Literal["new", "learning", "review", "relearning"]


class ReviewCardItem(BaseModel):
    id: int
    topic_id: int
    topic_name: str
    subject_name: str | None = None
    state: ReviewStateLiteral
    due_at: datetime | None = None
    last_reviewed_at: datetime | None = None
    last_rating: int | None = None
    stability: float
    difficulty: float
    review_count: int
    lapse_count: int


class ReviewBreakdown(BaseModel):
    new: int
    learning: int
    review: int
    relearning: int
    due_now: int
    total: int


class ReviewResponse(BaseModel):
    """GET /api/v2/student/review — vadesi gelen kartlar + özet."""
    due_cards: list[ReviewCardItem]
    breakdown: ReviewBreakdown


class ReviewRateBody(BaseModel):
    """POST /api/v2/student/review/{card_id}/rate body. rating ∈ {1,2,3,4}."""
    rating: int


# -------------------- Goals --------------------


GoalKindLiteral = Literal["exam_target", "subject", "topic", "weekly", "daily", "custom"]
GoalStatusLiteral = Literal["active", "achieved", "abandoned"]


class GoalItem(BaseModel):
    id: int
    parent_id: int | None
    kind: GoalKindLiteral
    status: GoalStatusLiteral
    title: str
    description: str | None
    target_value: float | None
    current_value: float | None
    unit: str | None
    target_date: str | None             # "YYYY-MM-DD"
    is_auto_generated: bool
    progress_pct: int | None
    achieved_at: datetime | None
    created_at: datetime


class GoalSummary(BaseModel):
    total: int
    active: int
    achieved: int
    abandoned: int
    overall_pct: int | None
    next_target_date: str | None


class GoalListResponse(BaseModel):
    """GET /api/v2/student/goals — kişisel hedefler + özet."""
    items: list[GoalItem]
    summary: GoalSummary


# Öğrenci tarafında izin verilen hedef tipleri — exam_target/subject auto-only
StudentGoalCreateKindLiteral = Literal["weekly", "daily", "custom", "topic"]


class GoalCreateBody(BaseModel):
    title: str
    kind: StudentGoalCreateKindLiteral = "custom"
    description: str | None = None
    target_value: float | None = None
    current_value: float | None = None
    unit: str | None = None
    target_date: str | None = None       # "YYYY-MM-DD"


class GoalProgressBody(BaseModel):
    """POST /api/v2/student/goals/{goal_id}/progress body."""
    current_value: float


class GoalToggleBody(BaseModel):
    """POST /api/v2/student/goals/{goal_id}/toggle body.

    achieved=True → ACHIEVED; achieved=False → ACTIVE (rollback).
    """
    achieved: bool
