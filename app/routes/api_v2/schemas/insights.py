"""API v2 — AI İçgörü, Tanılama ve Öneri şemaları (Dalga 3 Paket 9).

Kapsam:
  - Filo (fleet) içgörüleri: olgunluk haritası + sağlık ışıkları + trend
  - Öğrenci tanılaması: maturity formül parçaları + pattern/volume/reject
  - 7 günlük öneri panel + accept/reject/accept-all

Referans Jinja (dokunulmaz):
  - app/routes/teacher_ai_insights.py
  - app/routes/teacher_diagnostics.py
  - app/routes/teacher_suggestions.py

Servisler (değişmez):
  - app.services.ai_insights.build_fleet_insights
  - app.services.suggestions.{build_student_model, suggest_for_date, ...}
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


# =============================================================================
# Fleet insights — /teacher/insights/overview
# =============================================================================


HealthOverallLiteral = str  # 'no_students'|'no_data'|'warming_up'|'early'|'growing'|'mature'
HealthActivityLiteral = str  # 'never'|'today'|'recent'|'stale'|'cold'


class TopPatternItem(BaseModel):
    book_id: int
    book_name: str
    section_id: int
    section_label: str
    subject_name: str
    count: int
    students: int


class StudentMaturityItem(BaseModel):
    student_id: int
    full_name: str
    weeks_observed: int
    days_observed: int
    maturity_value: float            # 0..1
    maturity_text: str
    accepted_count: int
    rejected_count: int
    acceptance_rate: float | None    # None = yetersiz veri


class WeekBucketItem(BaseModel):
    start: date
    accepted: int
    rejected: int


class HealthBadge(BaseModel):
    key: str                         # 'no_data', 'mature', vs.
    label: str                       # Türkçe etiket
    color: str                       # CSS hex (#0ea5e9 vb.)


class FleetInsightsResponse(BaseModel):
    teacher_id: int
    today: date
    students: list[StudentMaturityItem]
    fleet_total_accepted: int
    fleet_total_rejected: int
    fleet_acceptance_rate: float | None
    avg_maturity: float
    students_with_data: int
    top_accepted: list[TopPatternItem]
    top_rejected: list[TopPatternItem]
    weekly_trend: list[WeekBucketItem]
    last_activity_at: datetime | None
    health_overall: HealthBadge
    health_activity: HealthBadge


# =============================================================================
# Öğrenci tanılaması — /teacher/insights/students/{id}/diagnostics
# =============================================================================


class DiagnosticsPatternRow(BaseModel):
    dow: int                         # 0..6
    dow_label: str
    book_id: int
    book_name: str
    subject_name: str
    section_id: int
    section_label: str
    topic_name: str | None
    freq: int
    typical_count: int
    samples: list[int]


class DiagnosticsVolumeRow(BaseModel):
    dow: int
    dow_label: str
    task_count: int                  # tipik kalem sayısı / gün
    subject_count: int               # tipik ders çeşitliliği / gün


class DiagnosticsRejectRow(BaseModel):
    dow_label: str
    book_id: int
    book_name: str
    subject_name: str
    section_id: int
    section_label: str
    weight: float
    count: int
    blocked: bool                    # REJECT_STRONG_COUNT eşiği aşıldı mı


class DiagnosticsStudentRef(BaseModel):
    id: int
    full_name: str


class StudentDiagnosticsResponse(BaseModel):
    student: DiagnosticsStudentRef
    today: date
    weeks_observed: int
    days_observed: int
    maturity_value: float
    maturity_label: str
    maturity_pct: int
    maturity_base: float
    maturity_floor_applied: bool
    maturity_weeks_constant: int
    maturity_min_floor: float
    reject_decay_days: int
    reject_strong_count: int
    reject_score_penalty: float
    pattern_rows: list[DiagnosticsPatternRow]
    volume_rows: list[DiagnosticsVolumeRow]
    reject_rows: list[DiagnosticsRejectRow]
    total_accepted: int
    total_rejected: int


# =============================================================================
# Öneri panel — /teacher/insights/students/{id}/suggestions
# =============================================================================


class SuggestionItem(BaseModel):
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
    confidence_label: str            # 'Zayıf'|'Orta'|'Güçlü'|'Çok güçlü'
    score: float
    reasons: list[str]


class SuggestionDayBundle(BaseModel):
    date: date
    suggestions: list[SuggestionItem]


class StudentSuggestionsPanelResponse(BaseModel):
    student_id: int
    target_date: date
    suggestions: list[SuggestionItem]
    maturity_value: float
    maturity_label: str
    weeks_observed: int
    days_observed: int
    active_phase: str | None
    track_required: bool
    track_missing: bool
    track_label: str | None


class StudentSuggestionsAheadResponse(BaseModel):
    """7 günlük (today..today+6) bundle — diagnostics sekmesinde kullanılır."""
    student_id: int
    today: date
    days: list[SuggestionDayBundle]


class SuggestionAcceptBody(BaseModel):
    date: date
    book_id: int
    section_id: int
    planned_count: int               # ≥1


class SuggestionRejectBody(BaseModel):
    date: date
    book_id: int
    section_id: int


class SuggestionAcceptItem(BaseModel):
    book_id: int
    section_id: int
    planned_count: int               # ≥1


class SuggestionAcceptAllBody(BaseModel):
    date: date
    items: list[SuggestionAcceptItem]


class SuggestionAcceptResult(BaseModel):
    accepted: bool
    task_id: int
    date: date


class SuggestionAcceptAllResult(BaseModel):
    created_count: int
    errors: list[str]                # tek tek kalemlerin reddedilme sebepleri (insancıl)


class SuggestionRejectResult(BaseModel):
    rejected: bool
