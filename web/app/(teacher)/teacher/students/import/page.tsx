import { CsvImportClient } from "@/components/teacher/csv-import-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "CSV ile öğrenci ekle",
};

export default function StudentsImportPage() {
  return <CsvImportClient />;
}
