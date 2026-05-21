import { apiServer } from "@/lib/api-server";
import type { AiSettingsResponse } from "@/lib/types/admin";
import { AdminAiSettingsClient } from "@/components/admin/admin-ai-settings-client";

/**
 * /admin/settings — Süper admin AI ayarları (tek sağlayıcı Gemini).
 *
 * Anahtarlar DB'de şifreli; tüm sistem buradan okur (env fallback).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "AI Ayarları — Süper Admin" };

export default async function AdminSettingsPage() {
  const data = await apiServer<AiSettingsResponse>("/api/v2/admin/settings/ai");
  return <AdminAiSettingsClient initial={data} />;
}
