"""Randevu sistemi (online görüşme) Pydantic şemaları."""

from __future__ import annotations

from pydantic import BaseModel, Field


WEEKDAY_LABELS_TR = [
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
]


class AppointmentItem(BaseModel):
    id: int
    student_id: int
    student_name: str
    coach_name: str | None = None
    date: str                      # YYYY-MM-DD
    start_time: str                # HH:MM
    duration_min: int
    weekday_label: str
    status: str
    status_label: str
    source: str
    source_label: str
    meeting_link: str | None = None
    link_source: str | None = None
    note: str | None = None
    request_note: str | None = None
    cancel_reason: str | None = None
    series_id: int | None = None
    is_past: bool = False


class SeriesItem(BaseModel):
    id: int
    student_id: int
    student_name: str
    weekday: int
    weekday_label: str
    start_time: str
    duration_min: int
    meeting_link: str | None = None
    link_source: str | None = None
    active: bool
    note: str | None = None


class AvailabilityWindowItem(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    slot_minutes: int = Field(default=40, ge=10, le=240)


class GoogleStatusInfo(BaseModel):
    configured: bool
    connected: bool
    email: str | None = None
    last_error: str | None = None


class TeacherAppointmentsResponse(BaseModel):
    start: str
    end: str
    items: list[AppointmentItem]
    pending: list[AppointmentItem]
    series: list[SeriesItem]
    availability: list[AvailabilityWindowItem]
    google: GoogleStatusInfo


class AppointmentCreateBody(BaseModel):
    student_id: int
    date: str                      # YYYY-MM-DD
    start_time: str                # HH:MM
    duration_min: int = Field(default=40, ge=10, le=240)
    meeting_link: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)
    weekly: bool = False


class AppointmentUpdateBody(BaseModel):
    date: str | None = None
    start_time: str | None = None
    duration_min: int | None = Field(default=None, ge=10, le=240)
    meeting_link: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)


class AppointmentStatusBody(BaseModel):
    status: str = Field(pattern="^(cancelled|done|no_show|scheduled)$")
    reason: str | None = Field(default=None, max_length=500)


class RejectBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AvailabilityReplaceBody(BaseModel):
    windows: list[AvailabilityWindowItem] = Field(default_factory=list, max_length=40)


class SeriesUpdateBody(BaseModel):
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: str | None = None
    duration_min: int | None = Field(default=None, ge=10, le=240)
    meeting_link: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class SeriesUpdateResult(BaseModel):
    series: SeriesItem
    cancelled: int
    regenerated: int


class SlotItem(BaseModel):
    start_time: str
    duration_min: int


class SlotDay(BaseModel):
    date: str
    weekday_label: str
    slots: list[SlotItem]


class StudentSlotsResponse(BaseModel):
    days: list[SlotDay]


class StudentAppointmentsResponse(BaseModel):
    upcoming: list[AppointmentItem]
    pending: list[AppointmentItem]
    past: list[AppointmentItem]
    coach_name: str | None = None
    can_request: bool = False        # koç var + uygunluk penceresi tanımlı
    has_pending: bool = False


class StudentRequestBody(BaseModel):
    date: str
    start_time: str
    note: str | None = Field(default=None, max_length=1000)


class ParentAppointmentsResponse(BaseModel):
    student_name: str
    upcoming: list[AppointmentItem]


class GoogleConnectUrlResponse(BaseModel):
    url: str


class AppointmentMutationResult(BaseModel):
    appointment: AppointmentItem
    series: SeriesItem | None = None
    google_link_attached: bool = False


class AvailabilityMutationResult(BaseModel):
    availability: list[AvailabilityWindowItem]


class SimpleOkResult(BaseModel):
    ok: bool = True
