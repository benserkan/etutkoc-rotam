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

from pydantic import BaseModel, Field


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

    # GÖREV-bazlı (görev/test/deneme AYRI; deneme soruları test'e karışmaz)
    gorev_today_total: int = 0
    gorev_today_done: int = 0
    gorev_week_total: int = 0
    gorev_week_done: int = 0
    gorev_week_rate: float = 0.0        # 0..1 görev tamamlama
    test_week_planned: int = 0          # yalnız soru bankası (deneme HARİÇ)
    test_week_completed: int = 0

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
    worst_warning_title: str | None = None   # satırın NEDEN kırmızı/sarı olduğu
    worst_warning_detail: str | None = None
    today_planned: int                  # soru (test) hacmi — geriye uyum
    today_completed: int
    today_gorev_total: int = 0          # bugünkü GÖREV sayısı (etkinlik dahil)
    today_gorev_done: int = 0
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
    # Görev-bazlı (etkinlik/"Diğer" dahil) — Durum Özeti "X/Y görev" + manşet %
    today_tasks_total: int = 0
    today_tasks_done: int = 0
    today_task_pct: float = 0.0         # 0..1 (görev tamamlama, etkinlik dahil)
    week_tasks_total: int = 0
    week_tasks_done: int = 0
    week_task_pct: float = 0.0


class GorevSubjectItem(BaseModel):
    """Ders bazında TEST görevleri (denemeler ayrı listede)."""
    subject_name: str
    gorev_total: int
    gorev_done: int
    pct: int                 # görev tamamlama %
    test_planned: int        # o derste planlanan test (soru) hacmi
    test_completed: int


class GorevDenemeItem(BaseModel):
    """Tek deneme/tam-deneme görevi (ayrı başlık)."""
    title: str
    subject: str | None = None
    category: str            # "deneme" | "tam_deneme"
    planned: int             # soru sayısı
    completed: int
    done: bool


class GorevBreakdown(BaseModel):
    """Görev/test/deneme ayrımlı özet — gorev_stats çekirdeğinden.

    Manşet = görev (etkinlik dahil). Test hacmi DENEME'den AYRI. Çıktılarda
    "X görev (%Z) · A test · B deneme" deseni; "224/365 test" karışıklığı yok.
    """
    gorev_total: int
    gorev_done: int
    gorev_pct: int           # 0..100
    test_planned: int        # soru bankası test hacmi (deneme HARİÇ)
    test_completed: int
    deneme_planned: int      # branş + tam deneme soru hacmi (AYRI)
    deneme_completed: int
    deneme_count: int        # deneme görev adedi (branş + tam)
    deneme_done: int
    etkinlik_count: int      # video/özet/tekrar görev adedi
    etkinlik_done: int
    subjects: list[GorevSubjectItem] = []
    denemeler: list[GorevDenemeItem] = []


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


class WarningItem(BaseModel):
    """Durum özeti uyarısı — yapısal + kanıt sayfasına link."""
    level: str                          # red | amber | green
    code: str
    title: str
    detail: str
    link: str                           # /teacher/students/{id}/<sayfa>
    link_label: str                     # "Haftalık planı incele" vb.


class TeacherStudentDetailResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}"""
    student: StudentBriefProfile
    program_summary: StudentProgramSummary
    worst_warning_level: WarningLevelLiteral
    warnings: list[str]                 # (geriye uyum) detail/title metinleri
    warning_items: list[WarningItem] = []   # yapısal + linkli durum özeti
    pending_request_count: int          # bu öğrencinin bekleyen talepleri
    # Paket 3.5b — header için aktif dönem rozeti
    active_phase: StudentActivePhase | None = None
    # Paket 3.5b — anchor edit kartı için
    week_anchor: str | None = None      # "YYYY-MM-DD" | None
    anchor_is_manual: bool = False
    # Aktif (explicit) program varsa anchor fallback atıl → UI kartı gizler.
    has_active_program: bool = False
    # Görev/test/deneme ayrımlı özet (gorev_stats) — bugün + bu hafta
    gorev_today: GorevBreakdown | None = None
    gorev_week: GorevBreakdown | None = None


class SetWeekAnchorBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/set-week-anchor"""
    # "clear" stringi gönderilirse manuel anchor silinir; ISO date stringi
    # gönderilirse program_anchor_date set edilir.
    anchor: str


# =============================================================================
# Polling badge + öğretmenin kendi özeti
# =============================================================================


class TeacherBadgesResponse(BaseModel):
    """GET /api/v2/teacher/badges — 60s polling.

    Rozetler 'işleyince azalır' (alarm körlüğü önleme):
      - at_risk_count: aktif (ERTELENMEMİŞ) uyarısı olan öğrenci sayısı →
        Gördüm/Ertele yapınca düşer.
      - pending_request_count: bekleyen öğrenci talebi → cevaplayınca düşer.
      - support_answered_count: süper adminin cevapladığı, koçu bekleyen destek
        talebi → koç yanıtlayınca/çözülünce düşer.
      - support_inbox_pending: kurum yöneticisinin koça ilettiği, koçun henüz
        cevaplamadığı talep (riskli öğrenci vb.) → cevaplayınca/çözünce düşer.
    """
    pending_request_count: int
    at_risk_count: int
    support_answered_count: int = 0
    support_inbox_pending: int = 0
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
    """Öğretmen perspektifi — kalem detayı + rezerv/tamam exposure'ı.
    Kitapsız deneme kaleminde book_id/section_id None; book_name = deneme adı."""
    id: int
    book_id: int | None = None
    book_name: str
    book_type: str | None = None     # BookType.value — birim (test/deneme/soru) için
    subject_id: int | None
    subject_name: str | None
    section_id: int | None = None
    section_label: str | None
    topic_name: str | None
    planned_count: int
    completed_count: int
    # Section'daki anlık rezerv/tamam durumu (öğretmen kapasiteyi anında görsün)
    section_total_tests: int
    section_reserved_count: int
    section_completed_count: int
    section_remaining: int
    # Sonuç (opsiyonel) — koç hem görüntüler hem düzenler.
    correct_count: int | None = None
    wrong_count: int | None = None


class TeacherTask(BaseModel):
    """Öğretmen perspektifi — bir görev tam görünüm."""
    id: int
    student_id: int
    date: str                       # "YYYY-MM-DD"
    type: TaskTypeLiteral
    status: TaskStatusLiteral
    title: str
    scheduled_hour: str | None      # "HH:00" veya None
    period: str | None = None       # "morning"|"noon"|"evening"|None (M6)
    order: int
    is_draft: bool
    notes: str | None
    items: list[TeacherTaskItem]
    planned_count: int              # sum(items.planned_count)
    completed_count: int            # sum(items.completed_count)
    pct: float                      # 0..1
    solved_count: int | None = None  # kalemsiz (etkinlik) görevde öğrencinin girdiği çözülen soru
    has_pending_request: bool
    # Serbest iş bloğu bağı (Katman 3) — görev bir bloğa aitse blok adı + birim.
    work_block_id: int | None = None
    work_block_title: str | None = None
    work_block_unit: str | None = None


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
    # Görev/test/deneme ayrımlı özet (gorev_stats) — manşet GÖREV-bazlı
    gorev: GorevBreakdown | None = None
    # Öğrencinin o güne dair serbest düşünce notu (salt-okuma; öğrenci yazar)
    day_note: str = ""


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
    tasks_count: int           # GÖREV sayısı (etkinlik dahil)
    planned: int               # soru hacmi (test+deneme karışık — geriye uyum)
    completed: int
    pct: float                 # görev tamamlama % (0..1)
    # Görev/test/deneme ayrımı — "122 test" (deneme soruları test sayılıyordu) yerine:
    test_planned: int = 0      # soru bankası test hacmi (deneme HARİÇ)
    test_completed: int = 0
    deneme_planned: int = 0    # branş+tam deneme (AYRI; soru/deneme adedi)
    deneme_completed: int = 0
    deneme_count: int = 0      # deneme görev adedi
    etkinlik_count: int = 0    # video/özet/tekrar görev adedi
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
    # WP2 — Program-aware response (Frontend bunlara göre üst başlık + dropdown)
    active_program_id: int | None = None        # bugünü içeren aktif program
    current_program_id: int | None = None       # gösterilen pencere bir program mı (görünür blok)
    current_program_label: str | None = None    # "Yeni Hafta · 30 May–5 Haz"
    current_program_name: str | None = None     # koç verdiyse özel ad
    current_program_day_count: int | None = None
    programs: list["WeeklyProgramItem"] = []    # dropdown için tüm programlar (en yeni→en eski)
    unlinked_task_count: int = 0                # mavi banner için
    unlinked_earliest: str | None = None
    unlinked_latest: str | None = None


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
    week_start: str                   # ISO (eski parametre — geriye uyum)
    program_id: int | None = None     # WP2 — varsa program tarih aralığı kullanılır


class PublishResult(BaseModel):
    published_count: int
    week_draft_total: int             # sonra kalan taslak (UI banner için)


class TasksReorderBody(BaseModel):
    task_date: str                    # ISO
    task_ids: list[int]               # yeni sıra


class TasksReorderResult(BaseModel):
    reordered_count: int


class NotifyParentsBody(BaseModel):
    week_start: str                   # ISO (eski parametre — geriye uyum)
    program_id: int | None = None     # WP2 — varsa program tarih aralığı kullanılır


class NotifyParentsResult(BaseModel):
    fired: int
    skipped_recent: int
    no_tasks: bool
    message: str                      # insancıl özet


# ---- Veliye duyur ÖNİZLEME (gönderim öncesi "ne gidecek") ----


class ParentProgramPreviewItem(BaseModel):
    book: str                         # kitap adı
    section: str                      # konu/bölüm
    planned: int                      # atanan TEST sayısı
    completed: int


class ParentProgramPreviewGroup(BaseModel):
    """Ders bazlı grup — başlık + konu kalemleri (mailde ders gruplaması)."""
    subject: str
    items: list[ParentProgramPreviewItem]
    total_planned: int


class ParentProgramPreviewActivity(BaseModel):
    """Kalemsiz etkinlik (Diğer/Video/Özet/Tekrar) — sayı yok."""
    title: str
    type: str


class ParentProgramPreviewDeneme(BaseModel):
    """Deneme görevi (AYRI — test'e karışmaz)."""
    title: str
    planned: int
    completed: int
    is_tam: bool = False              # True → birim "soru"; False → "deneme"


class ParentProgramPreviewDay(BaseModel):
    day_iso: str
    day_name: str                     # Pzt/Sal/...
    day_label: str                    # "31 May"
    has_tasks: bool
    subject_groups: list[ParentProgramPreviewGroup]
    denemeler: list[ParentProgramPreviewDeneme] = []
    activities: list[ParentProgramPreviewActivity]
    total_planned: int                # gün toplam TEST (yalnız soru bankası)
    # GÖREV-bazlı (her madde 1 görev; deneme/test AYRI)
    gorev_total: int = 0
    test_planned: int = 0
    deneme_count: int = 0


class ParentProgramPreviewExam(BaseModel):
    """Son 90 gün denemesi (bilgi amaçlı, veli mailindeki tabloyla aynı)."""
    title: str
    date_iso: str | None = None
    net: float | None = None
    correct: int = 0
    wrong: int = 0
    blank: int = 0
    section: str | None = None


class ParentProgramPreviewRecipient(BaseModel):
    name: str
    email: bool = True
    whatsapp: bool = False
    recently_notified: bool = False   # son 24s içinde aynı program duyurulmuş mu


class ParentProgramPreviewResponse(BaseModel):
    student_id: int
    student_name: str
    week_start: str
    week_end: str
    total_tasks: int                  # yayınlanmış (taslak hariç) görev sayısı
    daily_breakdown: list[ParentProgramPreviewDay]
    recent_exams: list[ParentProgramPreviewExam]
    recipients: list[ParentProgramPreviewRecipient]
    has_recipients: bool


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


class SubjectBrief(BaseModel):
    """Görev formu Video/Özet/Tekrar/Diğer dropdown'ı için — kitap atanma
    şartı olmadan öğrencinin müfredat havuzundaki tüm dersler."""
    id: int
    name: str


class SubjectListResponse(BaseModel):
    items: list[SubjectBrief]


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


# ----------------------- Serbest iş bloğu (Katman 3) -----------------------


class WorkBlockItem(BaseModel):
    """GET /students/{id}/work-blocks satırı — hesaplanan dağıtılan/kalan dahil."""
    id: int
    title: str
    subject_id: int | None = None
    subject_name: str | None = None
    total_count: int
    unit: str                         # test | soru | deneme
    note: str | None = None
    status: str                       # active | done | archived
    distributed: int                  # bloğa bağlı görevlerin planlanan toplamı
    completed: int                    # bloğa bağlı görevlerde çözülen toplam
    remaining: int                    # max(0, total - distributed)
    task_count: int                   # bloğa bağlı görev sayısı
    created_at: datetime
    archived_at: datetime | None = None


class WorkBlockListResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/work-blocks"""
    items: list[WorkBlockItem]


class WorkBlockCreateBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/work-blocks"""
    title: str
    total_count: int                  # ≥1
    unit: str = "test"                # test | soru | deneme
    subject_id: int | None = None
    note: str | None = None


class WorkBlockUpdateBody(BaseModel):
    """POST /api/v2/teacher/work-blocks/{id} — None geçilen alan değişmez."""
    title: str | None = None
    total_count: int | None = None
    unit: str | None = None
    subject_id: int | None = None
    note: str | None = None
    status: str | None = None         # active | done | archived


# ----------------------- Mutation bodyleri -----------------------


class TaskItemBody(BaseModel):
    """POST /tasks ve POST /tasks/{id}/items için kalem.

    Kitapsız "deneme" kalemi: book_id/section_id None + label (deneme adı) verilir;
    rezerv/kapasite atlanır, sadece planned_count hacme sayar.
    """
    book_id: int | None = None
    section_id: int | None = None
    label: str | None = None         # kitapsız deneme kaleminde deneme adı
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
    period: str | None = None          # "morning"|"noon"|"evening"|None (M6)
    is_draft: bool | None = None
    notes: str | None = None
    items: list[TaskItemBody]        # ≥1
    # Opsiyonel serbest iş bloğu bağı (Katman 3) — verilirse görev bu bloğa
    # sayılır (blok "dağıtılan" = bağlı görevlerin planlananı).
    work_block_id: int | None = None


class TaskPatchBody(BaseModel):
    """PATCH /api/v2/teacher/tasks/{task_id}

    None geçilen alanlar değişmez. items burada YOK — kalem değişikliği için
    dedicated endpoint'ler kullanılır (rezerv invariant'ı güvenli).
    """
    title: str | None = None
    type: TaskTypeLiteral | None = None
    scheduled_hour: int | None = None
    period: str | None = None          # "morning"|"noon"|"evening"|""(=null)|None
    order: int | None = None
    is_draft: bool | None = None
    notes: str | None = None


class TaskItemPatchBody(BaseModel):
    """PATCH /api/v2/teacher/tasks/{task_id}/items/{item_id}"""
    planned_count: int


class TaskItemResultBody(BaseModel):
    """POST /api/v2/teacher/tasks/{task_id}/items/{item_id}/result

    Koç bir kalemin "çözdüm + doğru/yanlış" sonucunu düzenler. Öğrenci girmedi/
    yanlış girdiyse koç düzeltir. Boş D/Y geçirmek (None) → o alan değişmez;
    `0` geçmek → temizlemek anlamı (öğrenci eski D/Y'sini sıfırlamak için).

    Validation: correct + wrong ≤ completed. completed > planned_count → klamp.
    """
    completed: int
    correct: int | None = None
    wrong: int | None = None


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
    email: str | None = None      # boş string → değişmez; format/çakışma backend'de
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


class SectionCompletedBaselineBody(BaseModel):
    """Bir bölümü 'öğrenci zaten çözmüş' işaretle (geçmiş yıl baseline).

    completed_count doğrudan set edilir; bölümün kalanı (test - rezerv - tamam)
    düşer → programda bir daha atanmaz. 0 = işareti kaldır (tüm bölüm yeniden
    atanabilir).
    """
    completed_count: int = Field(ge=0)


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


class AnalyticsSummary(BaseModel):
    """Tempo + istikrar manşeti."""
    rate_7d: float              # son 7 gün test/gün hızı (yalnız soru bankası)
    rate_30d: float             # son 30 gün test/gün
    consistency_7d_pct: int     # son 7 günün kaçında aktif (0..100)
    consistency_30d_pct: int
    hit_rate_7d_pct: int        # planlanan→tamamlanan (0..100)
    active_days_30: int         # son 30 günde aktif gün sayısı
    longest_streak_30: int      # son 30 günde en uzun kesintisiz aktif seri
    worst_warning_level: str    # green/amber/red


class AnalyticsWeekPoint(BaseModel):
    week_start: str             # ISO Pazartesi
    label: str                  # "12 May"
    planned: int
    completed: int
    pct: int                    # 0..100 (tamamlama)


class AnalyticsDayFlag(BaseModel):
    date: str                   # ISO
    weekday: int                # 0=Pazartesi
    active: bool                # o gün tik var mı
    has_plan: bool              # o gün planlı görev var mıydı


class AnalyticsDow(BaseModel):
    weekday: int                # 0=Pazartesi
    label: str                  # "Pzt"
    avg_completed: float        # o güne ait ortalama tamamlanan test
    hit_pct: int                # o günün tutturma oranı (0..100)
    measured: bool              # geçmişte planlı gün olup ölçülebildi mi


class AnalyticsProjection(BaseModel):
    exam_label: str | None
    exam_date: str | None       # ISO
    days_left: int | None
    total_tests: int
    completed: int
    remaining: int              # total − completed (kalan iş)
    projected_completable: int  # mevcut tempoyla erişilebilir
    gap: int                    # projeksiyon − kalan iş
    rate_per_day: float
    required_rate: float        # günlük gereken hız
    confidence_level: str       # high/medium/low
    status: str                 # green/amber/red


class AnalyticsExamPoint(BaseModel):
    title: str
    exam_date: str | None
    section_label: str
    net: float


class AnalyticsWarningItem(BaseModel):
    level: str                  # green/amber/red
    code: str
    title: str
    detail: str


class TeacherStudentAnalyticsResponse(BaseModel):
    student_id: int
    student_name: str
    window_days: int
    trend: list[AnalyticsTrendPoint]
    subjects: list[AnalyticsSubjectRow]
    # --- Zenginleştirme (koçun "program süreci" panosu) ---
    summary: AnalyticsSummary
    weekly_trend: list[AnalyticsWeekPoint]
    activity_calendar: list[AnalyticsDayFlag]
    dow_performance: list[AnalyticsDow]
    projection: AnalyticsProjection
    exam_trend: list[AnalyticsExamPoint]
    exam_trend_section: str | None = None
    exam_trend_delta: float | None = None
    warnings: list[AnalyticsWarningItem]


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
    code: str                       # uyarı kimliği (gördüm/ertele için)
    title: str
    detail: str
    is_paused: bool
    age_days: int                   # kaç gündür sürüyor (tazelik)
    snoozed: bool                   # ertelenmiş mi (aktif akışta gizli)
    snooze_until: datetime | None


class DashboardWarningsFeedResponse(BaseModel):
    rows: list[DashboardWarningRow]          # aktif (ertelenmemiş) uyarılar
    snoozed_rows: list[DashboardWarningRow]  # ertelenenler (geri alınabilir)
    total: int                               # aktif sayım
    snoozed_count: int


class WarningAckBody(BaseModel):
    student_id: int
    code: str
    snooze_days: int = 3


class WarningUnackBody(BaseModel):
    student_id: int
    code: str


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


class TranscribeResponse(BaseModel):
    """Saf ses→metin dikte sonucu (alan doldurma için)."""
    text: str


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
    max_students: int | None = None   # öğrenci tavanı; null = sınırsız
    tier_rank: int
    ai_included: bool           # bu planda AI premium özellikleri açık mı
    is_current: bool
    is_upgrade: bool            # mevcut plandan yükseltme mi (UI buton)
    is_recommended: bool = False  # öğrenci sayısına en uygun tier


class TeacherPlanResponse(BaseModel):
    plan_code: str
    plan_label: str
    is_solo: bool               # bağımsız koç mu (self-serve yükseltme uygun)
    ai_premium: bool            # şu an AI premium açık mı
    trial_active: bool
    trial_days_left: int | None = None
    options: list[TeacherPlanOption]
    note: str | None = None     # kurumlu kullanıcı için açıklama
    # Uygulama-içi abonelik ekranı (Faz 1) — /pricing ile tutarlı tek kaynak.
    status: str = "free"        # trialing | active | past_due | free | managed
    student_count: int = 0      # bağımsız koçun aktif öğrenci sayısı
    solo_monthly_price: int = 0 # öğrenci sayısına uygun Solo tier aylık ücreti (₺)
    recommended_plan: str = ""  # öğrenci sayısına en uygun solo tier kodu
    annual_paid_months: int = 10  # akademik yıl = N ay öde (2 ay bedava)
    sales_email: str = ""       # manuel aktivasyon iletişimi (pricing.contact)
    subscription_status: str | None = None       # active | canceled | past_due | None
    subscription_period_end: str | None = None  # aktif abonede yenileme tarihi (ISO)
    subscription_cycle: str | None = None        # monthly | academic_year
    # Signup'ta seçilen "14 gün dene" paketinin kodu — trial bitince bu plan'a
    # geçmek için ödeme talep edilir (yoksa solo_free'ye düşer).
    post_trial_plan: str | None = None
    post_trial_plan_label: str | None = None
    # Deneme bitince geçilecek plan'ın aylık AI kredi miktarı — kullanıcıya
    # "Şu an 50 kredi (deneme), Solo Başlangıç'a geçince 1.500/ay" mesajı için.
    post_trial_plan_credits: int | None = None
    # AI kredi durumu — /teacher/plan üst kartında ilerleme çubuğu için
    ai_credits_used: int = 0
    ai_credits_allocated: int = 0


class PlanUpgradeBody(BaseModel):
    plan: str                   # hedef solo plan kodu (solo_pro | solo_elite)


class SubscriptionRequestBody(BaseModel):
    """Koç uygulama-içi abonelik talebi (manuel aktivasyon akışı)."""
    plan: str = "solo_pro"          # solo_pro | solo_elite
    cycle: str = "monthly"          # monthly | academic_year


class SubscriptionRequestResult(BaseModel):
    ok: bool = True
    message: str
    already_pending: bool = False


class TrialStatusResponse(BaseModel):
    """Bağımsız koç trial/ödeme-duvarı durumu — teacher-shell banner için."""
    is_solo: bool
    plan_code: str
    plan_label: str
    trial_active: bool
    days_left: int | None = None
    trial_critical: bool            # trial aktif ve ≤3 gün kaldı (uyarı bandı)
    student_count: int
    student_limit: int              # -1 = sınırsız
    over_limit: bool
    paywall: bool                   # ücretsiz+limit aşıldı VEYA past_due → salt-okunur
    subscription_status: str | None = None  # active | past_due | canceled | None
    past_due: bool = False          # abonelik yenilenmedi
    upgrade_target: str | None = None


# =============================================================================
# Görev şablonları (TaskTemplate) — sık kullanılan görev kalıpları
# =============================================================================


class TaskTemplateItemModel(BaseModel):
    book_id: int
    section_id: int
    book_name: str
    section_label: str
    planned_count: int


class TaskTemplateModel(BaseModel):
    id: int
    name: str
    type: TaskTypeLiteral
    items: list[TaskTemplateItemModel]
    item_count: int
    total_planned: int
    created_at: datetime


class TaskTemplateListResponse(BaseModel):
    items: list[TaskTemplateModel]


class TaskTemplateItemBody(BaseModel):
    book_id: int
    section_id: int
    planned_count: int


class TaskTemplateCreateBody(BaseModel):
    name: str
    type: TaskTypeLiteral = "test"
    items: list[TaskTemplateItemBody]


class TaskTemplateFromTaskBody(BaseModel):
    name: str


class ApplyTaskTemplateBody(BaseModel):
    template_id: int
    date: str                          # "YYYY-MM-DD"
    scheduled_hour: int | None = None
    is_draft: bool | None = None


# =============================================================================
# WP1 — Weekly Programs (yeni program oluştur akışı, 2026-05-31)
# =============================================================================


class WeeklyProgramOverlapItem(BaseModel):
    """Çakışma uyarısı — UI dialog'unda gösterilir."""
    program_id: int
    label: str
    start_date: str                # "YYYY-MM-DD"
    end_date: str
    overlap_days: int
    task_count_in_overlap: int     # silme kararı için info


class WeeklyProgramItem(BaseModel):
    """Tek program — listede + aktif gösterimde."""
    id: int
    student_id: int
    start_date: str
    end_date: str
    day_count: int                 # (end - start) + 1
    name: str | None
    notes: str | None
    is_active: bool                # bugünü içeriyor mu
    created_at: datetime
    label: str                     # UI'da gösterilecek varsayılan ad


class WeeklyProgramListResponse(BaseModel):
    """GET /api/v2/teacher/students/{id}/programs"""
    student_id: int
    items: list[WeeklyProgramItem]
    active_program_id: int | None  # bugünü içeren
    # Mevcut öğrenci için hatırlatıcı: programa bağlı olmayan görev sayısı
    unlinked_task_count: int
    unlinked_earliest: str | None
    unlinked_latest: str | None


class WeeklyProgramCreateBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/programs"""
    start_date: str                # "YYYY-MM-DD"
    end_date: str
    name: str | None = None
    notes: str | None = None
    # Kullanıcı çakışma uyarısını gördü ve onayladı (advanced)
    allow_overlap: bool = False


class WeeklyProgramUpdateBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/programs/{program_id}"""
    start_date: str | None = None
    end_date: str | None = None
    name: str | None = None
    notes: str | None = None
    allow_overlap: bool = False


class WeeklyProgramDeleteBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/programs/{program_id}/delete"""
    delete_tasks: bool = False     # default: program siler, görevler korunur


class WeeklyProgramWrapLegacyBody(BaseModel):
    """POST /api/v2/teacher/students/{id}/programs/wrap-legacy
    Tek tık "Eski Dönem programı yarat" akışı."""
    name: str | None = None        # default "Eski Dönem"
