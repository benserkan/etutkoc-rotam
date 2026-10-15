import { apiServer } from "@/lib/api-server";
import type { StudentPoolResponse } from "@/lib/api/pool-student";
import { PoolClient } from "@/components/student/pool-client";

/** /student/pool — Havuzum (haftalık görev havuzu, dershane modu). Mobil ekranla aynı akış. */
export const metadata = { title: "Havuzum" };
export const dynamic = "force-dynamic";

export default async function StudentPoolPage({
  searchParams,
}: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const data = await apiServer<StudentPoolResponse>("/api/v2/student/pool");
  // ?ekle=1: Bugün sayfasındaki "Havuza kalem ekle" → Kalem ekle penceresi açık gelir
  return <PoolClient initial={data} openAdd={sp.ekle === "1"} />;
}
