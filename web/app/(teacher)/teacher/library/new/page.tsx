import { apiServer } from "@/lib/api-server";
import type {
  BookTemplateListResponse,
  SubjectListResponse,
} from "@/lib/types/library";
import type { TeacherStudentListResponse } from "@/lib/types/teacher";
import { BookWizardClient } from "@/components/teacher/book-wizard-client";

/**
 * /teacher/library/new — kitap ekleme sihirbazı (adım adım yönlendirmeli).
 *
 * 1 Bilgiler → 2 Üniteler → 3 Eşleştirme → 4 Öğrenci → Özet. Server'da subjects +
 * templates + öğrenci listesi prefetch edilir; sihirbaz mevcut uçları orkestre eder.
 * Sekmeli kitap detay sayfası (sonradan düzenleme) ayrı durur.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Yeni kitap",
};

export default async function NewBookPage() {
  const [subjects, templates, students] = await Promise.all([
    apiServer<SubjectListResponse>("/api/v2/teacher/library/subjects"),
    apiServer<BookTemplateListResponse>("/api/v2/teacher/library/templates"),
    apiServer<TeacherStudentListResponse>(
      "/api/v2/teacher/students?page_size=100",
    ).catch(
      () =>
        ({
          items: [],
          total: 0,
          page: 1,
          page_size: 100,
          has_next: false,
        }) as TeacherStudentListResponse,
    ),
  ]);
  return (
    <BookWizardClient
      subjects={subjects.items}
      templates={templates.items}
      students={students.items}
    />
  );
}
