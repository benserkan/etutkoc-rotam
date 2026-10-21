import { StudentProgressClient } from "@/components/student/progress-client";

export const metadata = { title: "Gelişim" };
export const dynamic = "force-dynamic";

export default function StudentProgressPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Gelişimim</h1>
        <p className="text-sm text-muted-foreground">
          Sınava hazırlık sürecindeki bütün önemli göstergelerin tek sayfada — koçunun gördüğü verilerle aynı.
        </p>
      </header>
      <StudentProgressClient />
    </div>
  );
}
