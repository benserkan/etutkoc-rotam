import { apiServer } from "@/lib/api-server";
import type { TaskTemplateListResponse } from "@/lib/types/teacher";
import type { LibraryBookListResponse } from "@/lib/types/library";
import { TaskTemplatesClient } from "@/components/teacher/task-templates-client";

/**
 * /teacher/library/task-templates — Görev şablonları (sık kullanılan görev kalıpları).
 *
 * Kitap şablonları (bölüm yapısı) ile KARIŞTIRILMAMALI. Bunlar görev kalıbı:
 * kitap+bölüm+test sayısı kaydet → plana eklerken tek tıkla aynı görevi uygula.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Görev şablonları" };

export default async function TaskTemplatesPage() {
  const [templates, books] = await Promise.all([
    apiServer<TaskTemplateListResponse>("/api/v2/teacher/task-templates"),
    apiServer<LibraryBookListResponse>("/api/v2/teacher/library/books"),
  ]);
  return <TaskTemplatesClient initialTemplates={templates} books={books.items} />;
}
