"""API v2 — Veli (PARENT) şemaları (Dalga 5 Paket 1).

GİZLİLİK NOTU:
Veli sadece görev tamamlama metrikleri, ders bazlı ilerleme, istikrar,
projeksiyon ve "veliye iletilebilir" işaretli öğretmen notlarını görür.
ASLA paylaşılmayanlar: deneme net sayıları, konu bazında doğru/yanlış,
öğrenci-öğretmen mesajları, AI iç işleyiş.

Bu şemalar Jinja `app/services/parent_view.py`'deki dict çıktılarıyla
BİREBİR aynı — sadece JSON serialization için Pydantic'e sarılmış.
"""
from __future__ import annotations

from datetime import date as DateType, datetime, time as TimeType
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Ortak — relation enum
# =============================================================================


ParentRelationLiteral = Literal["anne", "baba", "vasi", "diger"]

WarningLevelLiteral = Literal["red", "amber", "green"]


# =============================================================================
# Dashboard — list_parent_students() çıktısı
# =============================================================================


class ParentChildSummary(BaseModel):
    """Dashboard çocuk kartı — parent_view.list_parent_students() dict çıktısı."""
    student_id: int
    full_name: str
    grade_level: int | None = None
    is_graduate: bool = False
    display_grade_label: str | None = None
    academic_year: str | None = None
    exam_date: str | None = None  # ISO date
    exam_label: str | None = None
    exam_target: str = "none"  # "lgs" / "yks" / "none"
    relation: ParentRelationLiteral | None = None
    is_primary: bool = False
    today_planned: int
    today_completed: int
    week_planned: int
    week_completed: int
    week_completion_rate: int | None = None
    # GÖREV-bazlı (her madde 1 görev; deneme/test/etkinlik AYRI)
    today_gorev_total: int = 0
    today_gorev_done: int = 0
    week_gorev_total: int = 0
    week_gorev_done: int = 0
    week_gorev_rate: int | None = None
    week_test_planned: int = 0          # yalnız soru bankası (deneme HARİÇ)
    week_test_completed: int = 0
    rate_7d: int | None = None
    consistency_7d: int | None = None
    warning_level: WarningLevelLiteral
    # Son deneme özet (varsa) — veli paneli kart yansıması
    latest_exam_title: str | None = None
    latest_exam_date: str | None = None  # ISO date
    latest_exam_net: float | None = None  # ham net
    latest_exam_section: str | None = None  # LGS, TYT, AYT, YDT (enum value)
    latest_exam_count: int = 0  # toplam deneme sayısı (rozet için)


class ParentDashboardResponse(BaseModel):
    """GET /api/v2/parent/dashboard yanıtı."""
    children: list[ParentChildSummary]


# =============================================================================
# Student detail — student_overview() çıktısı
# =============================================================================


class ParentStudentInfo(BaseModel):
    id: int
    full_name: str
    grade_level: int | None = None
    is_graduate: bool = False
    display_grade_label: str | None = None
    academic_year: str | None = None
    exam_date: str | None = None
    exam_label: str | None = None
    exam_target: str = "none"


class ParentTodayInfo(BaseModel):
    planned: int
    completed: int
    gorev_total: int = 0
    gorev_done: int = 0


class ParentWeekInfo(BaseModel):
    planned: int
    completed: int
    rate: int | None = None
    gorev_total: int = 0
    gorev_done: int = 0
    gorev_rate: int | None = None
    test_planned: int = 0          # yalnız soru bankası (deneme HARİÇ)
    test_completed: int = 0


class ParentSubjectItem(BaseModel):
    """subject_breakdown çıktısı — name, percent_done, subject_id."""
    subject_id: int | None = None
    name: str
    percent_done: int


class ParentTrendPoint(BaseModel):
    date: str  # ISO
    label: str
    completed: int
    planned: int


class ParentProjectionInfo(BaseModel):
    total_tests: int
    completed_tests: int
    remaining_tests: int
    rate_per_day: float | None = None
    days_left_to_exam: int | None = None
    expected_completed_by_exam: int = 0
    gap: int = 0
    status: WarningLevelLiteral


class ParentTeacherNoteItem(BaseModel):
    id: int
    body: str
    teacher_name: str | None = None
    created_at: str | None = None
    delivered_at: str | None = None


class ParentStudentOverviewResponse(BaseModel):
    """GET /api/v2/parent/students/{id} yanıtı."""
    student: ParentStudentInfo
    today: ParentTodayInfo
    week: ParentWeekInfo
    rate_7d_pct: int | None = None
    rate_30d_pct: int | None = None
    consistency_7d_pct: int | None = None
    warning_level: WarningLevelLiteral
    subjects: list[ParentSubjectItem]
    trend: list[ParentTrendPoint]
    projection: ParentProjectionInfo
    teacher_notes: list[ParentTeacherNoteItem]


# =============================================================================
# Student week — student_week() çıktısı
# =============================================================================


class ParentWeekBookItem(BaseModel):
    book_name: str | None = None
    subject_name: str | None = None
    subject_id: int | None = None
    section_label: str | None = None
    topic_name: str | None = None
    planned_count: int
    completed_count: int


class ParentWeekTask(BaseModel):
    id: int
    title: str
    type: str | None = None  # "test" / "video" / "ozet" / "tekrar" / "konu" / "deneme"
    status: str | None = None  # "completed" / "partial" / "pending" / "skipped"
    book_items: list[ParentWeekBookItem]


class ParentWeekDay(BaseModel):
    date: str  # ISO
    weekday: int  # 0=Pazartesi
    tasks: list[ParentWeekTask]
    task_count: int
    planned_total: int
    completed_total: int
    # GÖREV-bazlı (her madde 1 görev; deneme/test/etkinlik AYRI)
    gorev_total: int = 0
    gorev_done: int = 0
    test_planned: int = 0          # yalnız soru bankası (deneme HARİÇ)
    test_completed: int = 0
    deneme_count: int = 0
    etkinlik_count: int = 0


class ParentStudentRef(BaseModel):
    id: int
    full_name: str


class ParentWeekResponse(BaseModel):
    """GET /api/v2/parent/students/{id}/week?start=YYYY-MM-DD yanıtı."""
    student: ParentStudentRef
    start: str  # ISO
    end: str
    prev_start: str
    next_start: str
    days: list[ParentWeekDay]


# =============================================================================
# Notifications — list_recent_notifications() çıktısı
# =============================================================================


NotificationKindLiteral = Literal[
    "daily_summary", "empty_day", "weekly_report", "new_program",
    "drop_alert", "teacher_note", "invitation", "otp", "exam_approaching",
]
NotificationChannelLiteral = Literal["email", "whatsapp", "sms"]
NotificationStatusLiteral = Literal["queued", "sent", "failed", "suppressed"]


class ParentNotificationItem(BaseModel):
    id: int
    kind: NotificationKindLiteral | str
    channel: NotificationChannelLiteral | str
    status: NotificationStatusLiteral | str
    subject: str | None = None
    student_name: str | None = None
    sent_at: str | None = None
    queued_at: str | None = None


class ParentNotificationsResponse(BaseModel):
    """GET /api/v2/parent/notifications yanıtı."""
    items: list[ParentNotificationItem]
    total: int


# =============================================================================
# Settings — preferences + children + whatsapp state
# =============================================================================


class ParentPreferencesInfo(BaseModel):
    """ParentNotificationPref durumu — 7 toggle × 2 kanal + sessiz saatler + unsubscribe.

    `*_enabled` = e-posta tarafı (default açık, opt-out).
    `*_wa_enabled` = WhatsApp tarafı (default kapalı, opt-in — KVKK).
    `child_whatsapp_consent` = 18 yaş altı öğrenciye doğrudan WA için veli onayı.
    """
    daily_summary_enabled: bool
    weekly_report_enabled: bool
    empty_day_alert_enabled: bool
    drop_alert_enabled: bool
    new_program_alert_enabled: bool
    teacher_note_enabled: bool
    exam_approaching_enabled: bool
    # P0 — WhatsApp kanal toggle'ları
    daily_summary_wa_enabled: bool = False
    weekly_report_wa_enabled: bool = False
    empty_day_alert_wa_enabled: bool = False
    drop_alert_wa_enabled: bool = False
    new_program_alert_wa_enabled: bool = False
    teacher_note_wa_enabled: bool = False
    exam_approaching_wa_enabled: bool = False
    child_whatsapp_consent: bool = False
    quiet_hours_start: str  # HH:MM
    quiet_hours_end: str
    unsubscribed_at: datetime | None = None


class ParentWhatsAppInfo(BaseModel):
    """WA durumu — 3 state: kapalı / kod bekleniyor / aktif."""
    enabled: bool
    phone: str | None = None  # E.164 (90532...)
    verified_at: datetime | None = None
    pending_verify: bool = False
    pending_phone: str | None = None
    pending_expires_at: datetime | None = None
    # DEV stub mode için — production'da None döner
    dev_test_code: str | None = None


class ParentChildLink(BaseModel):
    """Settings içinde child mute toggle için."""
    student_id: int
    full_name: str
    relation: ParentRelationLiteral | None = None
    relation_label: str
    is_primary: bool
    muted: bool


class ParentSettingsResponse(BaseModel):
    """GET /api/v2/parent/settings yanıtı."""
    preferences: ParentPreferencesInfo
    whatsapp: ParentWhatsAppInfo
    children: list[ParentChildLink]


# =============================================================================
# Settings mutations — request bodies
# =============================================================================


class ParentPreferencesBody(BaseModel):
    """POST /api/v2/parent/settings/preferences — 7 e-posta toggle + 7 WhatsApp toggle
    + sessiz saatler + 18 yaş altı WA onayı.

    WhatsApp toggle'ları (`*_wa`) ve `child_whatsapp_consent` opsiyoneldir; eski
    istemciler göndermezse mevcut değerler korunur (False ise False kalır).
    """
    daily_summary: bool
    weekly_report: bool
    empty_day: bool
    new_program: bool
    drop_alert: bool
    teacher_note: bool
    exam_approaching: bool
    # P0 — WhatsApp kanal toggle'ları (opsiyonel, default False)
    daily_summary_wa: bool = False
    weekly_report_wa: bool = False
    empty_day_wa: bool = False
    new_program_wa: bool = False
    drop_alert_wa: bool = False
    teacher_note_wa: bool = False
    exam_approaching_wa: bool = False
    child_whatsapp_consent: bool = False
    quiet_start: str = Field(default="22:00", description="HH:MM")
    quiet_end: str = Field(default="07:00", description="HH:MM")


class ParentMuteBody(BaseModel):
    """POST /api/v2/parent/settings/students/{id}/mute body."""
    muted: bool


class ParentWhatsAppStartBody(BaseModel):
    """POST /api/v2/parent/settings/whatsapp/start body."""
    phone: str


class ParentWhatsAppVerifyBody(BaseModel):
    """POST /api/v2/parent/settings/whatsapp/verify body."""
    code: str


# =============================================================================
# Invitation flow (P2 — public endpoints)
# =============================================================================


InvitationErrorLiteral = Literal[
    "not_found", "expired", "consumed",
    "email_in_use_other_role", "password_too_short",
    "kvkk_not_accepted", "name_required",
]


class ParentInvitationInfo(BaseModel):
    """GET /api/v2/parent/invitation/{token} yanıtı (başarılı)."""
    token: str
    invited_email: str
    student_full_name: str
    invited_by_full_name: str
    relation: ParentRelationLiteral
    relation_label: str
    is_primary: bool
    expires_at: datetime


class ParentInvitationAcceptBody(BaseModel):
    """POST /api/v2/parent/invitation/{token}/accept body.

    P0 (2026-05-30): aktivasyon ekranındaki iletişim tercih matrisinden gelen
    7 e-posta + 7 WhatsApp toggle'ı + sessiz saat + 18 yaş altı WA onayı
    OPSİYONEL olarak alınır. Eski istemci bunları göndermezse varsayılan değerler
    kullanılır (e-posta açık, WhatsApp kapalı).

    P1 (2026-05-30): `phone` alanı yeni istemcilerde zorunlu — kullanıcı
    aktivasyonda cep telefonunu girer, hesap oluştuktan sonra panelde
    "Telefonunuzu doğrulayın" banner'ı SMS OTP başlatır. Eski istemcilerde
    opsiyonel (geriye uyum) — telefon verilmeyebilir, sonra /me/account'tan eklenir.
    """
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=255)
    password_confirm: str
    kvkk_accept: bool
    # P1 — cep telefonu (opsiyonel: eski istemci uyumluluğu)
    phone: str | None = None
    # İletişim tercihleri (opsiyonel — yeni istemcilerden gelir)
    # E-posta: varsayılan True; WhatsApp: varsayılan False; sessiz saat HH:MM
    notification_preferences: dict[str, bool] | None = None
    quiet_start: str | None = Field(default=None, description="HH:MM")
    quiet_end: str | None = Field(default=None, description="HH:MM")
    child_whatsapp_consent: bool = False


class ParentInvitationAcceptResult(BaseModel):
    """Davet kabul başarılı yanıt — session kuruldu."""
    user_id: int
    full_name: str
    email: str
    is_new_account: bool
    redirect_url: str = "/parent"


# =============================================================================
# Unsubscribe (P2)
# =============================================================================


UnsubscribeStatusLiteral = Literal["unsubscribed", "already", "invalid"]


class ParentUnsubscribeResult(BaseModel):
    status: UnsubscribeStatusLiteral


# =============================================================================
# M4 — Veli seans hareketleri (KS1/KS2 görünümü)
#
# KVKK gizliliği: veli aşağıdakileri GÖRMEZ:
#   - coach_note (Kova 2 anlatı — koça özel)
#   - agenda / next_change (Kova 3 koç kararı — koça özel)
#   - mood / tags / auto_snapshot (gelişimsel sinyaller)
#   - capture_source (foto/ses → AI not — operasyonel)
#
# Veli yalnız: tarih + durum + süre + kanal + ödeme verisi görür (operasyonel
# tahsilat şeffaflığı). "Bu seans yapıldı/ertelendi, X ücretten Y ödendi."
# =============================================================================


SessionStatusLiteral = Literal["done", "postponed", "cancelled", "no_show"]
SessionChannelLiteral = Literal["in_person", "online", "phone"]
PaymentMethodLiteral = Literal["cash", "transfer", "other"]


class ParentSessionItem(BaseModel):
    """Tek seans — veli görünümü (gizli alanlar HARİÇ)."""
    id: int
    session_date: DateType
    status: SessionStatusLiteral
    status_label: str
    duration_min: int | None
    channel: SessionChannelLiteral | None
    channel_label: str | None


class ParentPaymentItem(BaseModel):
    """Tek ödeme kaydı."""
    id: int
    paid_at: DateType
    amount: int
    method: PaymentMethodLiteral
    method_label: str
    period_month: str | None       # "YYYY-MM" — hangi ayı kapatıyor
    note: str | None


class ParentBillingMonth(BaseModel):
    """Bir ayın tahsilat özeti — hesaplanır (modelde değil)."""
    period_month: str              # "YYYY-MM"
    period_label: str              # "Mart 2026"
    sessions_done: int             # o ay status=DONE seans sayısı
    session_fee: int               # cari ücret (CoachStudentRate)
    accrued: int                   # sessions_done × session_fee (tahakkuk)
    paid: int                      # o ay period_month'una düşen ödemelerin toplamı
    balance: int                   # accrued − paid (+ kalan; − fazla ödenmiş)


class ParentBillingSummary(BaseModel):
    """Toplam + ay bazlı kırılım."""
    session_fee: int                          # cari ücret (0 = belirlenmemiş)
    total_accrued: int                        # months toplamı
    total_paid: int                           # months toplamı
    open_balance: int                         # total_accrued − total_paid
    months: list[ParentBillingMonth]          # eski → yeni
    payments: list[ParentPaymentItem]         # son N (en yeni → en eski)


class ParentSessionsResponse(BaseModel):
    """GET /api/v2/parent/students/{id}/sessions response.

    `sessions`: son 12 ay seans listesi (en yeni → en eski).
    `billing`: aynı dönem için aylık tahakkuk + ödeme kırılımı.
    Veli bu sayfadan aylık borç durumunu net görür (KVKK: koça-özel notlar yok).
    """
    student_id: int
    student_name: str
    sessions: list[ParentSessionItem]
    billing: ParentBillingSummary
