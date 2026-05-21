/**
 * Öğretmen ayarları + kredi paneli GET sarmalayıcıları (Paket 9).
 *
 * QueryKey sözleşmesi backend `invalidate` listesindeki
 *   "teacher:{id}:settings"
 *   "teacher:{id}:usage"
 * ile birebir prefix uyumlu.
 */
import { api } from "@/lib/api";
import type {
  TeacherSettingsResponse,
  TeacherUsageResponse,
} from "@/lib/types/settings";

export const settingsKeys = {
  settings: () => ["teacher", "me", "settings"] as const,
  usage: () => ["teacher", "me", "usage"] as const,
} as const;

export function getTeacherSettings(): Promise<TeacherSettingsResponse> {
  return api<TeacherSettingsResponse>("/api/v2/teacher/settings");
}

export function getTeacherUsage(): Promise<TeacherUsageResponse> {
  return api<TeacherUsageResponse>("/api/v2/teacher/usage/current");
}
