/**
 * Randevu sistemi — tipli fetcher'lar + queryKey üreticileri.
 *
 * invalidate sözleşmesi (backend MutationResponse.invalidate):
 *   koç      → "teacher:{id}:appointments"
 *   öğrenci  → "student:appointments"
 */
import { api } from "@/lib/api";
import type {
  ParentAppointmentsResponse,
  StudentAppointmentsResponse,
  StudentSlotsResponse,
  TeacherAppointmentsResponse,
} from "@/lib/types/appointment";

export const appointmentKeys = {
  teacher: (teacherId: number | "me", start?: string) =>
    ["teacher", String(teacherId), "appointments", start ?? "default"] as const,
  student: () => ["student", "appointments"] as const,
  studentSlots: () => ["student", "appointments", "slots"] as const,
  parentChild: (studentId: number) =>
    ["parent", "students", String(studentId), "appointments"] as const,
} as const;

export function getTeacherAppointments(
  start?: string,
  end?: string,
): Promise<TeacherAppointmentsResponse> {
  const qs = new URLSearchParams();
  if (start) qs.set("start", start);
  if (end) qs.set("end", end);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api<TeacherAppointmentsResponse>(`/api/v2/teacher/appointments${suffix}`);
}

export function getStudentAppointments(): Promise<StudentAppointmentsResponse> {
  return api<StudentAppointmentsResponse>("/api/v2/student/appointments");
}

export function getStudentAppointmentSlots(): Promise<StudentSlotsResponse> {
  return api<StudentSlotsResponse>("/api/v2/student/appointments/slots");
}

export function getParentChildAppointments(
  studentId: number,
): Promise<ParentAppointmentsResponse> {
  return api<ParentAppointmentsResponse>(
    `/api/v2/parent/students/${encodeURIComponent(String(studentId))}/appointments`,
  );
}

export function getGoogleConnectUrl(): Promise<{ url: string }> {
  return api<{ url: string }>("/api/v2/teacher/google/connect-url");
}
