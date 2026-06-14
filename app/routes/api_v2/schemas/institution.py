"""API v2 — Kurum Yöneticisi (INSTITUTION_ADMIN) şemaları.

Dalga 4 Paket 1 kapsamı:
  - Dashboard agregat
  - Öğretmen listesi + create + activate/deactivate + pause-alerts/resume-alerts
  - Öğretmen kart (öğrenci listesi + haftalık özetler)
  - Roster (kurum öğrenci listesi + filtre seçenekleri)
  - Hedef analizi özeti (institution_goal_summary)

Dalga 4 Paket 2 kapsamı (eklendi):
  - Davetiyeler (list / create / revoke)
  - Aktivite ısı haritası (4 / 12 hafta)
  - Risk listesi (privacy korumalı)
  - Burnout listesi
  - Kohortlar (4 sekme: grade / track / curriculum / exam_target)

GİZLİLİK NOTU:
Kurum yöneticisi öğretmenin DETAYLARINI (program, notlar, öğrenci günlüğü)
göremez; bu modüldeki şemalarda öğrenci/öğretmen detayına link açacak
queryKey sağlanmaz, sadece agrega + isim/sınıf bilgisi döner.
"""
from __future__ import annotations

from datetime import date as DateType, datetime
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Ortak — kurum kimliği
# =============================================================================


class InstitutionBrief(BaseModel):
    """Üst panelin tepesinde gösterilecek kurum kimliği."""
    id: int
    name: str
    is_active: bool


# =============================================================================
# Dashboard
# =============================================================================


class TeacherSummaryItem(BaseModel):
    """Dashboard'daki öğretmen tablosu satırı + /teachers liste paylaşılır."""
    id: int
    full_name: str
    email: str
    is_active: bool
    is_paused: bool
    pause_reason: str | None = None
    paused_at: datetime | None = None
    student_count: int
    weekly_planned: int
    weekly_completed: int
    weekly_rate_pct: int | None = None
    weekly_deneme_planned: int = 0
    weekly_deneme_completed: int = 0
    last_login_at: datetime | None = None
    last_login_days: int | None = None


class InstitutionAggregateInfo(BaseModel):
    teacher_count: int
    active_teacher_count: int
    student_count: int
    weekly_planned: int
    weekly_completed: int
    weekly_rate_pct: int | None = None
    weekly_deneme_planned: int = 0
    weekly_deneme_completed: int = 0


class InstitutionRiskBadge(BaseModel):
    at_risk_count: int
    at_risk_critical: int


class InstitutionInactiveBadge(BaseModel):
    inactive_teacher_count: int
    inactive_teacher_names: list[str] = Field(default_factory=list)


class InstitutionDashboardResponse(BaseModel):
    institution: InstitutionBrief
    aggregate: InstitutionAggregateInfo
    risk: InstitutionRiskBadge
    inactive: InstitutionInactiveBadge
    teacher_summaries: list[TeacherSummaryItem]


# =============================================================================
# Teachers liste + create
# =============================================================================


class InstitutionTeacherListResponse(BaseModel):
    institution: InstitutionBrief
    items: list[TeacherSummaryItem]
    total: int


class TeacherCreateBody(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)


class TeacherCreateResult(BaseModel):
    """Tek seferlik geçici şifre dönen create response.

    `temp_password` sadece bu yanıtta görünür; sonraki çağrılarda
    backend tarafından üretilemez. UI'nın "kopyala" akışı buradan beslenir.
    """
    id: int
    full_name: str
    email: str
    temp_password: str
    must_change_password: bool = True


# =============================================================================
# Teacher kart (detay sayfası — öğrenci listesi gizlilik korumalı)
# =============================================================================


class TeacherCardStudentRow(BaseModel):
    """Öğretmen kartında öğrenci satırı. DETAYa link YOK (gizlilik)."""
    id: int
    full_name: str
    grade_level: int | None = None
    display_grade_label: str | None = None
    is_active: bool
    weekly_planned: int
    weekly_completed: int
    weekly_rate_pct: int | None = None


class TeacherCardResponse(BaseModel):
    teacher: TeacherSummaryItem
    students: list[TeacherCardStudentRow]
    total_planned: int
    total_completed: int
    overall_rate_pct: int | None = None


# =============================================================================
# Roster (öğrenci listesi)
# =============================================================================


class RosterRowItem(BaseModel):
    student_id: int
    full_name: str
    grade_level: int | None = None
    display_grade_label: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    weekly_planned: int
    weekly_completed: int
    weekly_rate_pct: int | None = None
    is_active: bool
    is_paused: bool


class RosterTeacherOption(BaseModel):
    id: int
    full_name: str


class RosterFilterOptions(BaseModel):
    teachers: list[RosterTeacherOption]
    grades: list[int]
    has_graduates: bool


class InstitutionRosterResponse(BaseModel):
    institution: InstitutionBrief
    items: list[RosterRowItem]
    total: int
    filters: RosterFilterOptions


# =============================================================================
# Goals summary
# =============================================================================


class InstitutionGoalsResponse(BaseModel):
    students_with_goals: int
    students_without_goals: int
    total_goals: int
    achieved_goals: int
    active_goals: int
    avg_overall_pct: int | None = None


# =============================================================================
# D4 Paket 2 — Davetiyeler
# =============================================================================


InvitationStatusLiteral = Literal["pending", "consumed", "expired", "revoked"]


class InvitationItem(BaseModel):
    """Davetiye satırı — list + create response."""
    id: int
    token: str
    full_name: str | None = None
    email: str | None = None
    role: str
    status: InvitationStatusLiteral
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None = None
    consumed_by_user_id: int | None = None
    revoked_at: datetime | None = None
    is_usable: bool
    # Frontend kopyalama UX'i için tam URL
    signup_url: str


class InvitationListResponse(BaseModel):
    institution: InstitutionBrief
    items: list[InvitationItem]
    total: int
    origin: str


class InvitationCreateBody(BaseModel):
    """E-posta veya isim opsiyonel; ikisi de boşsa "açık davetiye" üretilir."""
    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)


# =============================================================================
# D4 Paket 2 — Aktivite ısı haritası
# =============================================================================


class HeatmapCellData(BaseModel):
    day: DateType
    login_count: int
    tasks_created: int
    notes_created: int
    activity_score: float  # 0..1


class TeacherHeatmapRow(BaseModel):
    teacher_id: int
    full_name: str
    cells: list[HeatmapCellData]
    last_active_day: DateType | None = None
    days_since_active: int | None = None
    total_logins: int
    total_tasks: int
    total_notes: int
    is_inactive: bool
    is_new: bool = False     # yeni hesap (onboarding) — "pasif" değil


class ActivityHeatmapResponse(BaseModel):
    institution: InstitutionBrief
    weeks: int
    days_count: int
    inactive_threshold_days: int
    inactive_count: int
    teachers: list[TeacherHeatmapRow]


# =============================================================================
# D4 Paket 2 — Risk listesi (privacy korumalı)
# =============================================================================


RiskLevelLiteral = Literal["ok", "medium", "high", "critical"]


class RiskIndicatorItem(BaseModel):
    code: str
    title: str
    detail: str
    weight: int


class AtRiskRowItem(BaseModel):
    student_id: int
    full_name: str
    grade_level: int | None = None
    display_grade_label: str | None = None
    is_active: bool
    is_paused: bool
    pause_reason: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    score: int
    level: RiskLevelLiteral
    level_label: str
    level_emoji: str
    indicators: list[RiskIndicatorItem]
    last_login_days: int | None = None
    weekly_planned: int
    weekly_completed: int
    weekly_rate_pct: int | None = None
    is_muted: bool


class AtRiskCountsInfo(BaseModel):
    critical: int
    high: int
    medium: int


class AtRiskResponse(BaseModel):
    institution: InstitutionBrief
    counts: AtRiskCountsInfo
    total_students: int
    healthy_count: int
    at_risk: list[AtRiskRowItem]


# =============================================================================
# D4 Paket 2 — Burnout listesi
# =============================================================================


BurnoutLevelLiteral = Literal["healthy", "watch", "warn", "critical"]


class BurnoutSignalItem(BaseModel):
    kind: str
    severity: str
    label: str
    emoji: str
    detail: str
    metric: float | None = None


class BurnoutRowItem(BaseModel):
    student_id: int
    full_name: str
    grade_level: int | None = None
    display_grade_label: str | None = None
    teacher_id: int | None = None
    teacher_name: str | None = None
    risk_score: int
    risk_level: BurnoutLevelLiteral
    signal_count: int
    signals: list[BurnoutSignalItem] = Field(default_factory=list)


class BurnoutResponse(BaseModel):
    institution: InstitutionBrief
    items: list[BurnoutRowItem]
    total: int


# =============================================================================
# D4 Paket 2 — Kohortlar (4 sekme)
# =============================================================================


CohortTabLiteral = Literal["grade", "track", "curriculum", "exam_target"]


class CohortStatsItem(BaseModel):
    cohort_key: str
    cohort_label: str
    student_count: int
    weekly_planned: int
    weekly_completed: int
    weekly_rate_pct: int | None = None
    at_risk_count: int
    at_risk_pct: int | None = None
    rate_color: str  # green / amber / red / slate


class WeekOverWeekInfo(BaseModel):
    this_week_rate: int | None = None
    last_week_rate: int | None = None
    delta_pct: int | None = None
    direction: Literal["up", "down", "flat", "unknown"]


class CohortTabInfo(BaseModel):
    key: CohortTabLiteral
    label: str


class CohortsResponse(BaseModel):
    institution: InstitutionBrief
    active_tab: CohortTabLiteral
    tabs: list[CohortTabInfo]
    cohorts: list[CohortStatsItem]
    wow: WeekOverWeekInfo


# =============================================================================
# D4 Paket 3 — Abonelik
# =============================================================================


SubscriptionKindLiteral = Literal["monthly", "academic_year", "paused"]


class SubscriptionStatusInfo(BaseModel):
    kind: SubscriptionKindLiteral
    kind_label: str
    period_end: datetime | None = None
    pause_until: datetime | None = None
    in_summer_window: bool
    can_pause: bool
    can_resume: bool
    can_switch_to_academic_year: bool
    days_until_period_end: int | None = None
    performance_guarantee: bool
    guarantee_extended_at: datetime | None = None


class GuaranteeEvaluationInfo(BaseModel):
    eligible: bool
    period_started_at: datetime | None = None
    days_into_period: int | None = None
    period_total_days: int = 60                # toplam değerlendirme penceresi
    average_completion_rate: float | None = None
    threshold: float
    triggered: bool
    already_extended: bool
    can_extend: bool
    note: str
    # Detay: koç + ekrandaki diğer panellerle (compliance) tutarlı sayılar
    student_count: int = 0                     # aktif öğrenci sayısı
    total_planned_questions: int = 0           # toplam planlanan soru (TaskBookItem)
    total_completed_questions: int = 0         # toplam tamamlanan soru
    is_provisional: bool = False               # 60 gün dolmadan hesaplandı mı


class InstitutionPlanOption(BaseModel):
    """Yükseltme talebi için seçilebilir kurum kademesi (pricing kataloğundan)."""
    code: str
    label: str
    coaches: str            # koç aralığı (örn. "2–10 koç")
    price_label: str        # "10.000 ₺/ay" | "Özel teklif"


class SubscriptionResponse(BaseModel):
    institution: InstitutionBrief
    plan: str
    plan_label: str = ""                          # planın okunur adı
    status: SubscriptionStatusInfo
    guarantee_evaluation: GuaranteeEvaluationInfo
    # Plan yükseltme talebi (satın alma DEĞİL — süper admine sinyal)
    available_plans: list[InstitutionPlanOption] = []
    pending_upgrade_request: bool = False
    requested_plan_label: str | None = None       # bekleyen talepte hedef paket


class SubscriptionUpgradeRequestBody(BaseModel):
    plan: str | None = None      # hedef kademe kodu (etut_standart/dershane_pro/enterprise) — opsiyonel
    note: str | None = None      # kurumun ek notu (opsiyonel)


class SubscriptionRequestResult(BaseModel):
    ok: bool = True
    message: str
    already_pending: bool = False


# =============================================================================
# D4 Paket 3 — Quota dashboard
# =============================================================================


class QuotaInfoItem(BaseModel):
    key: str
    label: str
    limit: int          # -1 = sınırsız, 0 = kapalı
    current: int
    pct: int            # 0..100; sınırsızsa 0
    is_unlimited: bool
    is_at_limit: bool
    is_warn: bool
    has_override: bool
    override_note: str | None = None


class PlanQuotaItem(BaseModel):
    plan: str
    teachers: int
    students: int
    institution_admins: int


class QuotaResponse(BaseModel):
    institution: InstitutionBrief
    plan: str
    summary: list[QuotaInfoItem]
    plans: list[PlanQuotaItem]
    warn_pct: int


# =============================================================================
# D4 Paket 3 — Usage dashboard
# =============================================================================


class UsageBreakdownEntry(BaseModel):
    kind: str
    label: str
    credits: int


class UsageDailyPoint(BaseModel):
    day: DateType
    credits: int


class UsageEventItem(BaseModel):
    id: int
    occurred_at: datetime
    kind: str
    kind_label: str
    credits: int
    actor_user_id: int | None = None
    actor_name: str | None = None      # User.full_name (yoksa "Otomatik (sistem)")
    balance_after: int | None = None   # bu olaydan sonra kalan kredi


class UsageAccountInfo(BaseModel):
    period_year_month: str
    plan_code: str
    allocated_credits: int
    bonus_credits: int
    total_allocated: int
    used_credits: int
    remaining_credits: int
    usage_pct: int  # 0..100+
    hard_block_enabled: bool
    blocked_until: datetime | None = None
    # Şeffaflık: ilk/son kullanım + bu periyotta kaç event var
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    total_event_count: int = 0


class UsageResponse(BaseModel):
    institution: InstitutionBrief
    account: UsageAccountInfo
    breakdown: list[UsageBreakdownEntry]
    series: list[UsageDailyPoint]
    events: list[UsageEventItem]
    warn_threshold_pct: int


# =============================================================================
# D4 Paket 3 — Admin Digest
# =============================================================================


class AdminDigestSummary(BaseModel):
    id: int
    institution_id: int
    week_start_date: DateType
    week_end_date: DateType
    send_status: str  # 'sent' / 'failed' / 'log_only' / 'pending' / 'skipped_no_admin'
    recipient_count: int
    sent_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class AdminDigestListResponse(BaseModel):
    institution: InstitutionBrief
    items: list[AdminDigestSummary]
    total: int


class AdminDigestDetailResponse(AdminDigestSummary):
    """Detay: özet alanları + payload + recipient_emails listesi."""
    payload: dict | None = None
    recipient_emails: list[str] = Field(default_factory=list)


class AdminDigestSendResult(BaseModel):
    digest: AdminDigestSummary
    message: str


# ---------------------------- Program Uyum Panosu (2026-05-20) ----------------------------


class ComplianceSummary(BaseModel):
    rate: int | None = None
    rate_color: str
    last_week_rate: int | None = None
    delta: int | None = None
    planned: int
    completed: int
    accuracy: int | None = None
    student_count: int
    empty_count: int
    week_start: str
    week_end: str


class ComplianceTrendPoint(BaseModel):
    week_start: str
    rate: int | None = None
    planned: int
    completed: int


class ComplianceTeacherRow(BaseModel):
    teacher_id: int | None = None
    teacher_name: str
    student_count: int
    empty_students: int
    planned: int
    completed: int
    rate: int | None = None
    rate_color: str
    accuracy: int | None = None


class ComplianceStudentRow(BaseModel):
    student_name: str
    teacher_name: str
    planned: int
    completed: int
    rate: int | None = None
    rate_color: str
    accuracy: int | None = None


class ComplianceEmptyRow(BaseModel):
    teacher_id: int | None = None
    teacher_name: str
    count: int
    sample_students: list[str]


class InstitutionComplianceResponse(BaseModel):
    """GET /api/v2/institution/compliance."""
    institution: InstitutionBrief
    summary: ComplianceSummary
    trend: list[ComplianceTrendPoint]
    teachers: list[ComplianceTeacherRow]
    attention_students: list[ComplianceStudentRow]
    empty_program: list[ComplianceEmptyRow]


# ---------------------------- Müdahale Merkezi (KP1, 2026-05-20) ----------------------------


class ActionCenterItem(BaseModel):
    severity: str            # critical | warn | info
    category: str            # empty_program | low_compliance | at_risk
    title: str
    description: str
    teacher_name: str | None = None
    count: int
    suggestion: str


class ActionCenterSummary(BaseModel):
    critical: int
    warn: int
    info: int
    total: int


class ActionCenterResponse(BaseModel):
    """GET /api/v2/institution/action-center."""
    institution: InstitutionBrief
    summary: ActionCenterSummary
    items: list[ActionCenterItem]


# ---------------------------- Öğretmen Etkililik Karnesi (KP2, 2026-05-20) ----------------------------


class TeacherScorecardRow(BaseModel):
    teacher_id: int | None = None
    teacher_name: str
    student_count: int
    completion_rate: int | None = None
    accuracy: int | None = None
    discipline_per_student_week: int
    discipline_pct: int
    risk_students: int
    score: int
    score_color: str
    score_label: str


class TeacherScorecardSummary(BaseModel):
    teacher_count: int
    avg_score: int
    top_name: str | None = None
    top_score: int | None = None
    weeks: int


class TeacherScorecardResponse(BaseModel):
    """GET /api/v2/institution/teacher-scorecard."""
    institution: InstitutionBrief
    summary: TeacherScorecardSummary
    teachers: list[TeacherScorecardRow]


# ---------------------------- Veli Güveni Görünürlüğü (KP3, 2026-05-20) ----------------------------


class ParentTrustSummary(BaseModel):
    total_students: int
    covered_students: int
    coverage_pct: int | None = None
    parent_count: int
    active_parents: int
    pending_invites: int
    notif_sent: int
    notif_failed: int
    notif_suppressed: int
    notif_success_pct: int | None = None
    days: int


class ParentTrustChannel(BaseModel):
    channel: str
    channel_label: str
    sent: int
    failed: int
    suppressed: int
    success_pct: int | None = None


class ParentTrustResponse(BaseModel):
    """GET /api/v2/institution/parent-trust."""
    institution: InstitutionBrief
    summary: ParentTrustSummary
    channels: list[ParentTrustChannel]


class ParentTrustNotificationItem(BaseModel):
    """Tek bir bildirim satırı (NotificationLog) — detay panelinde gösterilir."""
    id: int
    status: str            # sent / failed / suppressed / queued
    status_label: str
    kind: str
    kind_label: str
    channel: str
    channel_label: str
    subject: str | None = None
    error: str | None = None
    student_name: str | None = None
    parent_email: str | None = None
    parent_name: str | None = None
    created_at: datetime
    sent_at: datetime | None = None


class ParentTrustNotificationListResponse(BaseModel):
    """GET /api/v2/institution/parent-trust/notifications — detay listesi."""
    items: list[ParentTrustNotificationItem]
    days: int
    total_count: int


# =============================================================================
# Üyelik & Aktivite Akışı
# =============================================================================


class ActivityStreamItem(BaseModel):
    """Birleşik aktivite akışı satırı.

    Veri kaynakları: users + invitations + parent_invitations +
    contact_requests + plan_change_history. Kategori 4 grup:
      - signup / invitation / commercial / change
    """
    id: str                              # 'user:42', 'invitation:8', vb.
    occurred_at: datetime
    type: str                            # ham tip kodu
    category: str                        # signup / invitation / commercial / change
    is_commercial: bool                  # paket alımı, abonelik talebi → highlight
    title: str
    subtitle: str | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    target_label: str | None = None
    detail_url: str | None = None       # süper admin: owner-aware 360 linki
    institution_id: int | None = None
    institution_name: str | None = None
    user_id: int | None = None           # ilgili koç/kullanıcı (360 + tıklanabilirlik)


class ActivityStreamResponse(BaseModel):
    items: list[ActivityStreamItem]
    counts: dict[str, int]               # total / signup / invitation / commercial / change / purchases
    days: int


# =============================================================================
# KP4b — Kurum Akademik Çıktı Panosu (deneme net agregasyonu)
# =============================================================================


class AcademicSummary(BaseModel):
    total_students: int
    students_with_exam: int
    coverage_pct: int | None = None
    no_exam_count: int
    total_exams: int
    recent_exams: int
    avg_net_pct: int | None = None
    net_pct_color: str
    delta: int | None = None
    weeks: int


class AcademicSectionRow(BaseModel):
    section: str
    section_label: str
    exam_count: int
    student_count: int
    avg_net: float
    avg_net_pct: int | None = None
    net_pct_color: str


class AcademicTrendPoint(BaseModel):
    week_start: str
    avg_net_pct: int | None = None
    exam_count: int


class AcademicTeacherRow(BaseModel):
    teacher_id: int | None = None
    teacher_name: str
    student_count: int
    exam_count: int
    avg_net_pct: int | None = None
    net_pct_color: str
    last_exam_date: str | None = None


class AcademicMoverRow(BaseModel):
    student_name: str
    teacher_name: str
    first_net_pct: int
    last_net_pct: int
    delta: int
    exam_count: int


class AcademicNoExamRow(BaseModel):
    teacher_id: int | None = None
    teacher_name: str
    count: int
    sample_students: list[str]


class InstitutionAcademicResponse(BaseModel):
    """GET /api/v2/institution/academic."""
    institution: InstitutionBrief
    summary: AcademicSummary
    sections: list[AcademicSectionRow]
    trend: list[AcademicTrendPoint]
    teachers: list[AcademicTeacherRow]
    improving: list[AcademicMoverRow]
    declining: list[AcademicMoverRow]
    no_exam_program: list[AcademicNoExamRow]


# =============================================================================
# Sol menü rozetleri — "işleyince azalır" (handle-to-clear)
# =============================================================================


class InstitutionBadgesResponse(BaseModel):
    """GET /api/v2/institution/badges — 60s polling.

    - support_inbox_pending: öğretmenlerden gelen, BEKLEYEN (açık/değerlendiriliyor)
      talep → incele/cevapla/çöz yapınca düşer.
    - support_answered: kurum yöneticisinin süper admine açtığı, süper adminin
      CEVAPLADIĞI talep → yanıtlayınca/çözülünce düşer.
    """
    support_inbox_pending: int
    support_answered: int = 0
    checked_at: datetime


# =============================================================================
# Koça ilet — riskli öğrenci için kurum yöneticisi → koç talebi (aşağı yönlü)
# =============================================================================


class NotifyCoachBody(BaseModel):
    """Tükenmişlik/risk panosundan koça müdahale talebi açar."""
    teacher_id: int
    student_name: str | None = None
    note: str | None = None
    context: str | None = None  # "burnout" | "at_risk" | None (kaynak panel)


class NotifyCoachResult(BaseModel):
    request_id: int
    teacher_id: int
    teacher_name: str | None = None


# =============================================================================
# P4b — Koça iletilen müdahale geçmişi (risk/tükenmişlik panosu)
# =============================================================================


class CoachInterventionItem(BaseModel):
    request_id: int
    student_name: str | None = None     # subject'ten parse ("Riskli öğrenci: X")
    coach_name: str | None = None
    created_at: datetime
    status: str
    status_label: str


class CoachInterventionsResponse(BaseModel):
    items: list[CoachInterventionItem]
