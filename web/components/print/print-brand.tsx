import { apiServer } from "@/lib/api-server";
import type { MyAccountResponse } from "@/lib/types/me";

/** Yazdırma başlığı için öğrenci adı + kurum markası (kuruma bağlı → kurum logosu/adı,
 *  bağımsız koçun öğrencisi → platform amblemi). */
export async function getPrintBrand(): Promise<{
  studentName: string;
  instName: string | null;
  logoUrl: string | null;
}> {
  let me: MyAccountResponse | null = null;
  try {
    me = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch {
    me = null;
  }
  return {
    studentName: me?.user.full_name ?? "",
    instName: me?.brand?.name ?? null,
    logoUrl: me?.brand?.logo_url ?? null,
  };
}

export function PrintBrandHeader({
  title,
  subtitle,
  studentName,
  instName,
  logoUrl,
  right,
}: {
  title: string;
  subtitle: string;
  studentName: string;
  instName: string | null;
  logoUrl: string | null;
  right?: React.ReactNode;
}) {
  return (
    <header className="mb-3 flex items-end justify-between gap-4 border-b-2 border-stone-800 pb-2">
      <div className="flex items-center gap-3">
        {logoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF kurum logosu ucu + yazdırma
          <img src={logoUrl} alt={instName ?? "Kurum"} className="h-10 w-auto max-w-[150px] object-contain" />
        ) : instName ? (
          <span className="max-w-[180px] text-base font-bold leading-tight text-stone-900">{instName}</span>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- platform amblemi (yazdırma)
          <img src="/etutkoc-mark.png" alt="ETÜTKOÇ Rotam" className="h-9 w-9 object-contain" />
        )}
        <div>
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h1 className="text-lg font-bold tracking-tight">{title}</h1>
            <span className="text-sm font-semibold text-stone-800">{studentName || "—"}</span>
          </div>
          <div className="text-[11px] text-stone-500">
            {subtitle}
            {instName ? <span className="text-stone-600"> · {instName}</span> : null}
          </div>
        </div>
      </div>
      <div className="text-right text-[10px] text-stone-500">
        {right}
        <div className="text-stone-400">{instName ? "Altyapı: ETÜTKOÇ Rotam" : "etütkoç·rotam"}</div>
      </div>
    </header>
  );
}

const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];
const TR_DOW = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];

export function fmtLongDate(iso: string, withDow = false): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const base = `${d} ${TR_MONTHS[m - 1]} ${y}`;
  if (!withDow) return base;
  return `${base}, ${TR_DOW[new Date(y, m - 1, d).getDay()]}`;
}
