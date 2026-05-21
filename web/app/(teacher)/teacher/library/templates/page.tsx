import { apiServer } from "@/lib/api-server";
import type { BookTemplateListResponse } from "@/lib/types/library";
import { TemplatesListClient } from "@/components/teacher/templates-list-client";

export const dynamic = "force-dynamic";
export const metadata = { title: "Kitap şablonları" };

export default async function TemplatesPage() {
  const data = await apiServer<BookTemplateListResponse>(
    "/api/v2/teacher/library/templates",
  );
  return <TemplatesListClient initial={data} />;
}
