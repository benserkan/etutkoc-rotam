import { apiServer } from "@/lib/api-server";
import type { BookSetListResponse } from "@/lib/types/library";
import { BookSetsListClient } from "@/components/teacher/book-sets-list-client";

export const dynamic = "force-dynamic";
export const metadata = { title: "Kitap setleri" };

export default async function BookSetsPage() {
  const data = await apiServer<BookSetListResponse>(
    "/api/v2/teacher/library/book-sets",
  );
  return <BookSetsListClient initial={data} />;
}
