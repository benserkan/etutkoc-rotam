import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { ReportView, type ExamReport } from "./report-view";

/**
 * /rapor/[token] — veliye bağlantıyla giden deneme analiz raporu (2026-11-13).
 * Login gerektirmez; bağlantı 60 gün geçerli, koç iptal edebilir.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Deneme raporu",
  robots: { index: false, follow: false },
};

export default async function ExamReportPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  let report: ExamReport | null = null;
  try {
    report = await apiServer<ExamReport>(`/api/v2/public/exam-report/${encodeURIComponent(token)}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  if (!report) {
    return (
      <main className="force-light flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="max-w-sm rounded-xl border border-slate-300 bg-white p-6 text-center">
          <h1 className="text-lg font-bold text-slate-900">Rapor açılamadı</h1>
          <p className="mt-2 text-sm text-slate-600">
            Bu bağlantının süresi dolmuş ya da koç tarafından kapatılmış. Güncel rapor için koçunuzla
            iletişime geçebilirsiniz.
          </p>
        </div>
      </main>
    );
  }
  return <ReportView token={token} report={report} />;
}
