import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type {
  BookSetDetailResponse,
  LibraryBookListResponse,
  SubjectListResponse,
} from "@/lib/types/library";
import { BookSetDetailClient } from "@/components/teacher/book-set-detail-client";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Kitap seti #${id}` };
}

export default async function BookSetDetailPage({ params }: PageProps) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();

  let bookSet: BookSetDetailResponse;
  try {
    bookSet = await apiServer<BookSetDetailResponse>(
      `/api/v2/teacher/library/book-sets/${numericId}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  const [allBooks, subjects] = await Promise.all([
    apiServer<LibraryBookListResponse>("/api/v2/teacher/library/books"),
    apiServer<SubjectListResponse>("/api/v2/teacher/library/subjects"),
  ]);
  return (
    <BookSetDetailClient
      initial={bookSet}
      allBooks={allBooks.items}
      allSubjects={subjects.items}
    />
  );
}
