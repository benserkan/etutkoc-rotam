import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { AdminCatalogListResponse } from "@/lib/types/book-catalog";

import { AdminBookCatalogClient } from "./admin-book-catalog-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Kitap Kataloğu — Süper Admin",
};

export default async function AdminBookCatalogPage() {
  let data: AdminCatalogListResponse;
  try {
    data = await apiServer<AdminCatalogListResponse>("/api/v2/admin/book-catalog");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/admin/book-catalog"));
    }
    throw e;
  }

  return <AdminBookCatalogClient initial={data} />;
}
