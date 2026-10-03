"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { UserCircle2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { adminKeys, getAdminIndependentTeachers } from "@/lib/api/admin";
import type {
  AdminIndependentTeachersResponse,
  HealthLevel,
} from "@/lib/types/admin";

interface Props {
  initial: AdminIndependentTeachersResponse;
}

/**
 * Bağımsız öğretmenler aktivite listesi — login-bazlı 4-band heuristik.
 *
 * Eşdeğer Jinja: admin.py:131-147 + independent_teachers_list.html.
 */
export function AdminIndependentTeachersClient({ initial }: Props) {
  const q = useQuery<AdminIndependentTeachersResponse>({
    queryKey: adminKeys.independentTeachers(),
    queryFn: () => getAdminIndependentTeachers(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const { summary, rows } = data;

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <UserCircle2 className="size-6 text-violet-700 dark:text-violet-300" aria-hidden />
          Bağımsız Öğretmenler
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Login-bazlı aktivite (kurum bağlı olmayan tüzel kişi öğretmenler).
          Toplam <strong className="tabular-nums">{summary.total}</strong>{" "}
          öğretmen.
        </p>
      </header>

      {/* 4 band stat */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <BandKpi
          label="7g aktif"
          value={summary.healthy}
          tone="emerald"
          sub="Sağlıklı"
        />
        <BandKpi
          label="7-14g"
          value={summary.watch}
          tone="yellow"
          sub="Gözlem"
        />
        <BandKpi
          label="14-30g"
          value={summary.risk}
          tone="amber"
          sub="Riskli"
        />
        <BandKpi
          label="30g+ / Yok"
          value={summary.critical}
          tone="rose"
          sub="Acil"
        />
      </div>

      {/* Table */}
      {rows.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            Henüz bağımsız öğretmen yok.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Bant</th>
                  <th className="text-left px-4 py-2 font-medium">Ad</th>
                  <th className="text-left px-4 py-2 font-medium">E-posta</th>
                  <th className="text-left px-4 py-2 font-medium">
                    Son giriş
                  </th>
                  <th className="text-right px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((r) => (
                  <tr key={r.user.id}>
                    <td className="px-4 py-2">
                      <BandPill band={r.band} />
                    </td>
                    <td className="px-4 py-2 font-medium">
                      <Link
                        href={`/admin/users/${r.user.id}`}
                        className="hover:text-indigo-700"
                      >
                        {r.user.full_name}
                      </Link>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">
                      {r.user.email}
                    </td>
                    <td className="px-4 py-2 text-muted-foreground text-xs">
                      {r.label}
                    </td>
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      <Link
                        href={`/admin/revenue/users/${r.user.id}`}
                        className="text-xs text-indigo-600 dark:text-indigo-300 hover:text-indigo-800"
                      >
                        Ticari 360 →
                      </Link>
                      <Link
                        href={`/admin/users/${r.user.id}`}
                        className="ml-3 text-xs text-muted-foreground hover:text-foreground"
                      >
                        Yönetim
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function BandKpi({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: number;
  tone: "emerald" | "yellow" | "amber" | "rose";
  sub: string;
}) {
  const map = {
    emerald: { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-200" },
    yellow: { dot: "bg-yellow-500", text: "text-yellow-700 dark:text-yellow-300", border: "border-yellow-200" },
    amber: { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300", border: "border-amber-200" },
    rose: { dot: "bg-rose-500", text: "text-rose-700 dark:text-rose-300", border: "border-rose-200" },
  };
  const c = map[tone];
  return (
    <Card className={cn("border", c.border)}>
      <CardContent className="p-3">
        <div className="flex items-center gap-1.5">
          <span className={cn("size-2 rounded-full", c.dot)} />
          <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
            {label}
          </span>
        </div>
        <div
          className={cn("text-2xl font-semibold tabular-nums mt-0.5", c.text)}
        >
          {value}
        </div>
        <div className="text-[10px] text-muted-foreground">{sub}</div>
      </CardContent>
    </Card>
  );
}

function BandPill({ band }: { band: HealthLevel }) {
  const map: Record<HealthLevel, string> = {
    critical: "bg-rose-100 dark:bg-rose-500/15 dark:border-rose-500/30 text-rose-800 dark:text-rose-200 border-rose-300",
    risk: "bg-amber-100 dark:bg-amber-500/15 dark:border-amber-500/30 text-amber-800 dark:text-amber-200 border-amber-300",
    watch: "bg-yellow-100 dark:bg-yellow-500/15 dark:border-yellow-500/30 text-yellow-800 dark:text-yellow-200 border-yellow-300",
    healthy: "bg-emerald-100 dark:bg-emerald-500/15 dark:border-emerald-500/30 text-emerald-800 dark:text-emerald-200 border-emerald-300",
  };
  return (
    <span
      className={cn(
        "text-[10px] px-1.5 py-0.5 rounded font-mono font-bold border",
        map[band],
      )}
    >
      {band}
    </span>
  );
}
