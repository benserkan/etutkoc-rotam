import { apiServer } from "@/lib/api-server";
import type {
  BookTemplateListResponse,
  SubjectListResponse,
} from "@/lib/types/library";
import { BookCreateForm } from "@/components/teacher/book-create-form";

/**
 * /teacher/library/new — yeni kitap formu (modal yerine sayfa, mobil dostu).
 *
 * Server'da subjects + templates listesi prefetch edilir; form submit sonrası
 * client `/teacher/library/books/{id}`'ye yönlenir.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Yeni kitap",
};

export default async function NewBookPage() {
  const [subjects, templates] = await Promise.all([
    apiServer<SubjectListResponse>("/api/v2/teacher/library/subjects"),
    apiServer<BookTemplateListResponse>("/api/v2/teacher/library/templates"),
  ]);
  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          Yeni kitap
        </h1>
        <p className="text-sm text-muted-foreground">
          Ders, tip ve hedef sınıf seçin. İsteğe bağlı şablon uygulayabilirsiniz.
        </p>
      </header>
      <BookCreateForm
        subjects={subjects.items}
        templates={templates.items}
      />
    </div>
  );
}
