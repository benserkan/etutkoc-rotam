"""API v2 — Öğretmen ayarları + kredi paneli şemaları (Dalga 3 Paket 9).

Kapsam:
  - /teacher/settings — profil + cron tablosu + e-posta SMTP durumu
  - /teacher/settings/test-email — kendi e-posta yapılandırmasını dene
  - /teacher/settings/cron/{id} — cron schedule güncelle
  - /teacher/settings/cron/run-now — manuel tüm cron tetikleme
  - /teacher/usage — bağımsız öğretmen için aylık kredi paneli

Referans Jinja (dokunulmaz):
  - app/routes/teacher_settings.py
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


# =============================================================================
# Settings — /teacher/settings
# =============================================================================


class CronJobInfo(BaseModel):
    title: str                       # "Günlük öğrenci özeti"
    what: str                        # uzun açıklama
    applies: str                     # kime uygulanır
    default_hint: str                # önerilen UTC zaman bilgisi


class CronScheduleItem(BaseModel):
    id: int
    job_key: str
    description: str | None
    hour: int                        # 0..23 (UTC)
    minute: int                      # 0..59
    day_of_week: int | None          # 0=Pzt..6=Pzr, None=her gün
    interval_minutes: int | None
    enabled: bool
    last_run_at: datetime | None
    last_status: str | None          # 'success' | 'failed' | 'skipped' | None
    last_error: str | None
    time_label: str                  # "18:00"
    tr_time_label: str               # "21:00" (UTC+3, gün taşması varsa belirtir)
    dow_label: str                   # "Her gün" / "Pazartesi" vb.
    info: CronJobInfo | None         # JOB_INFO[job_key] varsa


class EmailConfigStatus(BaseModel):
    enabled: bool
    smtp_host: str | None
    smtp_port: int | None
    from_address: str | None


class TeacherProfileBrief(BaseModel):
    id: int
    full_name: str
    email: str | None
    role: str                        # 'teacher'
    institution_id: int | None
    plan: str | None                 # 'free'|'starter'|...


class TeacherSettingsResponse(BaseModel):
    teacher: TeacherProfileBrief
    email_config: EmailConfigStatus
    cron_schedules: list[CronScheduleItem]


class TestEmailBody(BaseModel):
    to: str | None = None            # boş ise kullanıcının kendi e-postası


class TestEmailResult(BaseModel):
    sent: bool
    to: str
    message: str                     # insancıl sonuç ("Test e-postası gönderildi: …")


class CronSchedulePatchBody(BaseModel):
    """None geçilen alan değişmez. day_of_week=None özel: 'her gün'."""
    hour: int | None = None
    minute: int | None = None
    day_of_week: int | None = None   # 0..6 veya None
    enabled: bool | None = None
    clear_day_of_week: bool = False  # True ise day_of_week sıfırlanır (her gün)


class CronRunNowResult(BaseModel):
    summary: str                     # _summarize_run çıktısı
    sent: int                        # dispatcher gönderim sayısı
    suppressed: int                  # bastırılan sayısı


# =============================================================================
# Usage — /teacher/usage
# =============================================================================


class UsagePeriodAccount(BaseModel):
    period: str                      # 'YYYY-MM'
    plan_code: str
    allocated_credits: int
    used_credits: int
    bonus_credits: int
    remaining_credits: int
    usage_pct: int                   # 0..100+
    hard_block_enabled: bool
    blocked_until: datetime | None
    warn_80_sent_at: datetime | None
    is_currently_blocked: bool


class UsageBreakdownItem(BaseModel):
    kind: str                        # UsageKind value
    label: str                       # Türkçe (USAGE_KIND_LABELS_TR)
    credits: int
    cost_per_call: int               # KIND_CREDITS[kind]


class UsageDailyPoint(BaseModel):
    date: date
    credits: int


class UsageEventItem(BaseModel):
    id: int
    kind: str
    label: str
    credits: int
    occurred_at: datetime
    actor_user_id: int | None
    metadata: dict | None


class PlanAllocationItem(BaseModel):
    plan_code: str                   # 'free'|'starter'|...
    monthly_credits: int


class TeacherUsageResponse(BaseModel):
    is_independent: bool             # True ise kendi havuzu; False ise kuruma yönlendir
    institution_id: int | None
    account: UsagePeriodAccount | None
    breakdown: list[UsageBreakdownItem]
    daily_series: list[UsageDailyPoint]
    recent_events: list[UsageEventItem]
    plan_allocations: list[PlanAllocationItem]
    kind_costs: list[UsageBreakdownItem]   # cost_per_call referans tablosu
