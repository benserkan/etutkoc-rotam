import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type {
  BookTemplateListResponse,
  LibraryBookDetailResponse,
  SubjectListResponse,
  TopicListResponse,
} from "@/lib/types/library";
import type { TeacherStudentListResponse } from "@/lib/types/teacher";
import { BookDetailClient } from "@/components/teacher/book-detail-client";

/**
 * /teacher/library/books/[id] — kitap detayı (sekmeli).
 *
 * Server'da topics, templates ve öğretmenin öğrenci listesi prefetch edilir;
 * client TanStack Query ile interaktif kalır.
 */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Kitap #${id}` };
}

export default async function BookDetailPage({ params }: PageProps) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();

  let book: LibraryBookDetailResponse;
  try {
    book = await apiServer<LibraryBookDetailResponse>(
      `/api/v2/teacher/library/books/${numericId}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  // Aynı dersin topics + tüm şablonlar + öğretmenin öğrencileri (assignment için)
  // Subjects'in tamamı liste ekranı yapar; burada sadece bu kitabın ders topic'lerini
  // çekiyoruz (bulk-from-catalog için).
  const [topics, templates, students, subjects] = await Promise.all([
    apiServer<TopicListResponse>(
      `/api/v2/teacher/library/subjects/${book.subject_id}/topics`,
    ).catch(() => ({ items: [] }) as TopicListResponse),
    apiServer<BookTemplateListResponse>("/api/v2/teacher/library/templates"),
    apiServer<TeacherStudentListResponse>(
      "/api/v2/teacher/students?page_size=100",
    ),
    apiServer<SubjectListResponse>("/api/v2/teacher/library/subjects").catch(
      () => ({ items: [] }) as SubjectListResponse,
    ),
  ]);
  return (
    <BookDetailClient
      initialBook={book}
      topics={topics.items}
      templates={templates.items}
      students={students.items}
      subjects={subjects.items}
    />
  );
}
