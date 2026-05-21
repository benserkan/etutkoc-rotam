import { apiServer } from "@/lib/api-server";
import type { AnnouncementsListResponse } from "@/lib/types/admin";
import { AdminAnnouncementsClient } from "@/components/admin/admin-announcements-client";

/**
 * /admin/announcements — Sistem duyuruları CRUD.
 *
 * Jinja kaynağı: admin.py:2806-2916 + announcements_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Duyurular — Süper Admin" };

export default async function AdminAnnouncementsPage() {
  const data = await apiServer<AnnouncementsListResponse>(
    "/api/v2/admin/announcements",
  );
  return <AdminAnnouncementsClient initial={data} />;
}
