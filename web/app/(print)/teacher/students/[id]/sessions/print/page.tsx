import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { TeacherStudentDetailResponse } from "@/lib/types/teacher";

/**
 * /teacher/students/[id]/sessions/print — yazdırılabilir boş görüşme formu (KS1).
 *
 * Koç A4 çıktısını alır, el yazısıyla doldurur. (KS3'te fotoğraf → AI bu formu
 * dijital seans kaydına çevirecek.)
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Görüşme Formu" };

const FIELDS: { label: string; lines: number }[] = [
  { label: "Haftanın en verimli çalışma günleri hangileriydi? Neden?", lines: 2 },
  { label: "Haftanın en zorlayıcı çalışma günü hangisiydi? Karşılaşılan temel zorluklar?", lines: 2 },
  { label: "Tam olarak anlaşılmayan / tekrar edilmesi gereken konu veya soru tipi var mı?", lines: 2 },
  { label: "Çalışma temposu ve molalar hakkında notlar", lines: 2 },
  { label: "Haftanın en büyük başarısı", lines: 2 },
  { label: "Bu hafta en çok tekrar eden zorluk / problem", lines: 2 },
  { label: "Gelecek haftanın programında değiştirilecek / iyileştirilecek 1 şey", lines: 2 },
  { label: "Koçluk seansında gündeme getirilecek konular", lines: 3 },
];

export default async function SessionPrintPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let studentName = "";
  try {
    const data = await apiServer<TeacherStudentDetailResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(id)}`,
    );
    studentName = data.student.full_name;
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }

  return (
    <main className="mx-auto max-w-[800px] bg-white px-10 py-8 text-stone-900">
      <style>{`@media print { @page { size: A4 portrait; margin: 16mm; } .no-print { display:none } }`}</style>

      <header className="mb-6 border-b-2 border-stone-800 pb-3">
        <h1 className="text-xl font-bold tracking-tight">Haftalık Koçluk Görüşme Formu</h1>
        <div className="mt-3 flex items-end justify-between text-sm">
          <span>Öğrenci: <b>{studentName || "______________________"}</b></span>
          <span>Tarih: ______ / ______ / 20____</span>
        </div>
      </header>

      <div className="space-y-5">
        {FIELDS.map((f) => (
          <section key={f.label}>
            <p className="mb-1.5 text-sm font-semibold">{f.label}</p>
            <div className="space-y-3">
              {Array.from({ length: f.lines }).map((_, i) => (
                <div key={i} className="border-b border-dotted border-stone-400" style={{ height: "1.1rem" }} />
              ))}
            </div>
          </section>
        ))}
      </div>

      <footer className="mt-8 flex items-center justify-between text-[11px] text-stone-500">
        <span>etütkoç · rotam</span>
        <span>Doldurduktan sonra fotoğrafını çekip sisteme yükleyebilirsiniz (yakında).</span>
      </footer>

      <div className="no-print mt-6 text-center">
        <p className="text-xs text-stone-400">Yazdırmak için tarayıcıdan Ctrl/Cmd + P.</p>
      </div>
    </main>
  );
}
