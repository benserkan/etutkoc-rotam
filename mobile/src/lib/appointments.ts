import { apiRequest } from "@/lib/api";

/** Randevu sistemi — web lib/types/appointment.ts sözleşmesinin aynısı. */

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
  /** F4: bu randevudan kaydedilen seans (varsa) */
  session_id?: number | null;
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

export interface StudentAppointmentsResponse {
  upcoming: AppointmentItem[];
  pending: AppointmentItem[];
  past: AppointmentItem[];
  coach_name: string | null;
  can_request: boolean;
  has_pending: boolean;
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

export interface TeacherAppointmentsResponse {
  start: string;
  end: string;
  items: AppointmentItem[];
  pending: AppointmentItem[];
  series: unknown[];
  availability: unknown[];
  google: { configured: boolean; connected: boolean; email: string | null };
}

export interface ParentAppointmentsResponse {
  student_name: string;
  upcoming: AppointmentItem[];
}

export const apptKeys = {
  student: ["student", "appointments"] as const,
  studentSlots: ["student", "appointments", "slots"] as const,
  teacher: ["teacher", "me", "appointments"] as const,
  parentChild: (studentId: number) =>
    ["parent", "students", String(studentId), "appointments"] as const,
};

// ---------------------------------------------------------------------------
// Öğrenci
// ---------------------------------------------------------------------------

export function getStudentAppointments(): Promise<StudentAppointmentsResponse> {
  return apiRequest("/api/v2/student/appointments");
}

export function getStudentAppointmentSlots(): Promise<StudentSlotsResponse> {
  return apiRequest("/api/v2/student/appointments/slots");
}

export function requestAppointment(body: {
  date: string;
  start_time: string;
  note?: string;
}): Promise<unknown> {
  return apiRequest("/api/v2/student/appointments/request", {
    method: "POST",
    body,
  });
}

export function withdrawAppointment(apptId: number): Promise<unknown> {
  return apiRequest(`/api/v2/student/appointments/${apptId}/withdraw`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Koç
// ---------------------------------------------------------------------------

export function getTeacherAppointments(): Promise<TeacherAppointmentsResponse> {
  return apiRequest("/api/v2/teacher/appointments");
}

export function approveAppointment(apptId: number): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/appointments/${apptId}/approve`, {
    method: "POST",
  });
}

export function rejectAppointment(
  apptId: number,
  reason?: string,
): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/appointments/${apptId}/reject`, {
    method: "POST",
    body: { reason },
  });
}

/** F4 — biten görüşmeyi tek adımda KS1 seans kaydına çevir (done → tahsilata sayılır). */
export function recordAppointmentSession(
  apptId: number,
  body: {
    outcome: "done" | "no_show";
    agenda?: string;
    coach_note?: string;
    mood?: number;
  },
): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/appointments/${apptId}/record-session`, {
    method: "POST",
    body,
  });
}

export function setAppointmentStatus(
  apptId: number,
  status: "cancelled" | "done" | "no_show",
  reason?: string,
): Promise<unknown> {
  return apiRequest(`/api/v2/teacher/appointments/${apptId}/status`, {
    method: "POST",
    body: { status, reason },
  });
}

// ---------------------------------------------------------------------------
// Veli
// ---------------------------------------------------------------------------

export function getParentChildAppointments(
  studentId: number,
): Promise<ParentAppointmentsResponse> {
  return apiRequest(`/api/v2/parent/students/${studentId}/appointments`);
}

// ---------------------------------------------------------------------------
// Ortak yardımcılar
// ---------------------------------------------------------------------------

export function fmtApptDate(a: Pick<AppointmentItem, "date" | "weekday_label">): string {
  const [, m, d] = a.date.split("-");
  return `${d}.${m} ${a.weekday_label}`;
}
