/**
 * Online görüşme / randevu sistemi tipleri — backend
 * `app/routes/api_v2/schemas/appointment.py` aynası.
 */

export type AppointmentStatus =
  | "pending"
  | "scheduled"
  | "cancelled"
  | "rejected"
  | "done"
  | "no_show";

export interface AppointmentItem {
  id: number;
  student_id: number;
  student_name: string;
  coach_name: string | null;
  date: string; // YYYY-MM-DD
  start_time: string; // HH:MM
  duration_min: number;
  weekday_label: string;
  status: AppointmentStatus;
  status_label: string;
  source: string;
  source_label: string;
  meeting_link: string | null;
  link_source: "manual" | "google" | null;
  note: string | null;
  request_note: string | null;
  cancel_reason: string | null;
  series_id: number | null;
  is_past: boolean;
}

export interface SeriesItem {
  id: number;
  student_id: number;
  student_name: string;
  weekday: number;
  weekday_label: string;
  start_time: string;
  duration_min: number;
  meeting_link: string | null;
  link_source: "manual" | "google" | null;
  active: boolean;
  note: string | null;
}

export interface AvailabilityWindowItem {
  weekday: number;
  start_time: string;
  end_time: string;
  slot_minutes: number;
}

export interface GoogleStatusInfo {
  configured: boolean;
  connected: boolean;
  email: string | null;
  last_error: string | null;
}

export interface TeacherAppointmentsResponse {
  start: string;
  end: string;
  items: AppointmentItem[];
  pending: AppointmentItem[];
  series: SeriesItem[];
  availability: AvailabilityWindowItem[];
  google: GoogleStatusInfo;
}

export interface AppointmentCreateBody {
  student_id: number;
  date: string;
  start_time: string;
  duration_min: number;
  meeting_link?: string | null;
  note?: string | null;
  weekly: boolean;
}

export interface AppointmentUpdateBody {
  date?: string;
  start_time?: string;
  duration_min?: number;
  meeting_link?: string | null;
  note?: string | null;
}

export interface AppointmentMutationResult {
  appointment: AppointmentItem;
  series: SeriesItem | null;
  google_link_attached: boolean;
}

export interface SeriesUpdateResult {
  series: SeriesItem;
  cancelled: number;
  regenerated: number;
}

export interface SlotItem {
  start_time: string;
  duration_min: number;
}

export interface SlotDay {
  date: string;
  weekday_label: string;
  slots: SlotItem[];
}

export interface StudentSlotsResponse {
  days: SlotDay[];
}

export interface StudentAppointmentsResponse {
  upcoming: AppointmentItem[];
  pending: AppointmentItem[];
  past: AppointmentItem[];
  coach_name: string | null;
  can_request: boolean;
  has_pending: boolean;
}

export interface ParentAppointmentsResponse {
  student_name: string;
  upcoming: AppointmentItem[];
}
