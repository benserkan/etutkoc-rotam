import { apiServer } from "@/lib/api-server";
import type { ParentSettingsResponse } from "@/lib/types/parent";
import { ParentSettingsClient } from "@/components/parent/parent-settings-client";

/**
 * /parent/settings — Bildirim tercihleri + çocuk mute + WhatsApp.
 *
 * Jinja kaynağı: parent.py:384-428 + settings_skeleton.html (221 satır)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Ayarlar — Veli Paneli" };

export default async function ParentSettingsPage() {
  const data = await apiServer<ParentSettingsResponse>(
    "/api/v2/parent/settings",
  );
  return <ParentSettingsClient initial={data} />;
}
