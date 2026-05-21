import { apiServer } from "@/lib/api-server";
import type { TeacherSettingsResponse } from "@/lib/types/settings";
import { SettingsClient } from "@/components/teacher/settings-client";

/**
 * /teacher/settings — öğretmen ayarları (profile + email + cron) (Paket 9).
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Ayarlar",
};

export default async function TeacherSettingsPage() {
  const data = await apiServer<TeacherSettingsResponse>(
    "/api/v2/teacher/settings",
  );
  return <SettingsClient initial={data} />;
}
