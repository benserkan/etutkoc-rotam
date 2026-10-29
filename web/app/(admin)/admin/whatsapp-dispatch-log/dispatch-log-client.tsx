"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Calendar,
  Filter,
  MessageSquare,
  TrendingUp,
  Users,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
  getAdminWhatsAppDispatchLog,
} from "@/lib/api/messaging";
import { Card, CardContent } from "@/components/ui/card";
import type {
  DispatchLogItem,
  DispatchLogResponse,
} from "@/lib/types/messaging";

interface Props {
  initial: DispatchLogResponse;
}

const ROLE_LABELS_TR: Record<string, string> = {
  super_admin: "Süper Admin",
  institution_admin: "Kurum Yön.",
  teacher: "Öğretmen",
  student: "Öğrenci",
  parent: "Veli",
};

const DAYS_OPTIONS = [
  { value: 1, label: "Bugün" },
  { value: 7, label: "7 gün" },
  { value: 30, label: "30 gün" },
  { value: 90, label: "90 gün" },
];

export function DispatchLogClient({ initial }: Props) {
  const [days, setDays] = React.useState<number>(7);
  const [senderFilter, setSenderFilter] = React.useState<{
    id: number;
    name: string;
  } | null>(null);

  const q = useQuery<DispatchLogResponse>({
    queryKey: ["admin", "wa-dispatch-log", days, senderFilter?.id ?? 0],
    queryFn: () =>
      getAdminWhatsAppDispatchLog(days, senderFilter?.id ?? null, 50),
    initialData:
      days === 7 && senderFilter === null ? initial : undefined,
    staleTime: 30_000,
  });

  const data = q.data ?? initial;

  function applySender(id: number, name: string) {
    setSenderFilter({ id, name });
  }

  function clearSender() {
    setSenderFilter(null);
  }

  return (
    <div className="space-y-5">
      <header>
        <p className="text-[11px] uppercase tracking-wider text-emerald-700 font-semibold">
          <MessageSquare className="inline size-3.5 mr-1" aria-hidden />
          Click-to-WhatsApp Audit
        </p>
        <h1 className="font-display text-2xl font-semibold tracking-tight mt-1">
          Dispatch Log
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Koç/yönetici tarafından tetiklenen tüm WhatsApp gönderim kayıtları.
          URL üretildiğinde log atılır — gerçek mesaj koçun telefonundan
          gönderildiği için sistem tarafında metin saklanmaz; yalnız
          tetik bilgisi.
        </p>
      </header>

      {/* KPI'lar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KpiCard
          icon={<Calendar className="size-4 text-sky-700" aria-hidden />}
          label="Bugün"
          value={data.summary.total_today}
        />
        <KpiCard
          icon={<Activity className="size-4 text-emerald-700" aria-hidden />}
          label="Bu hafta"
          value={data.summary.total_week}
        />
        <KpiCard
          icon={<TrendingUp className="size-4 text-violet-700" aria-hidden />}
          label={`Son ${data.days} gün`}
          value={data.summary.total_period}
        />
        <KpiCard
          icon={<Users className="size-4 text-amber-700" aria-hidden />}
          label="En aktif (gönderen)"
          value={data.summary.top_senders[0]?.count ?? 0}
          sub={data.summary.top_senders[0]?.sender_name ?? "—"}
        />
      </div>

      {/* Süre filtresi + aktif sender filter göstergesi */}
      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 flex-wrap">
              <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold inline-flex items-center gap-1.5">
                <Filter className="size-3.5" aria-hidden />
                Süre
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {DAYS_OPTIONS.map((o) => (
                  <button
                    key={o.value}
                    type="button"
                    onClick={() => setDays(o.value)}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-xs border transition-colors",
                      days === o.value
                        ? "bg-emerald-600 text-white border-emerald-600"
                        : "bg-background hover:bg-muted",
                    )}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Aktif sender filter göstergesi — yalnız filter varsa görünür */}
            {senderFilter ? (
              <div className="inline-flex items-center gap-1.5 rounded-md bg-emerald-100 border border-emerald-400 px-2.5 py-1 text-xs">
                <Filter className="size-3 text-emerald-800" aria-hidden />
                <span className="text-emerald-900">
                  <strong>Gönderen filtresi:</strong>{" "}
                  <span className="font-medium">{senderFilter.name}</span>
                </span>
                <button
                  type="button"
                  onClick={clearSender}
                  className="ml-1 rounded-full hover:bg-emerald-200 p-0.5"
                  aria-label="Filtreyi temizle"
                >
                  <X className="size-3 text-emerald-800" aria-hidden />
                </button>
              </div>
            ) : (
              <p className="text-[11px] text-muted-foreground italic">
                Belirli bir gönderene filtrelemek için &ldquo;En çok mesaj
                atanlar&rdquo; listesinden veya tablodaki bir satırdaki
                gönderen adına tıklayın.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Top senders */}
      <Card>
        <CardContent className="p-4">
          <h3 className="text-xs uppercase tracking-wider text-muted-foreground font-semibold mb-3 inline-flex items-center gap-1.5">
            <TrendingUp className="size-3.5" aria-hidden />
            En çok mesaj atanlar (son {data.days} gün)
          </h3>
          {data.summary.top_senders.length === 0 ? (
            <p className="text-xs text-muted-foreground italic">
              Bu dönemde kayıt yok.
            </p>
          ) : (
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {data.summary.top_senders.map((s, i) => {
                const active = senderFilter?.id === s.sender_user_id;
                return (
                  <li key={s.sender_user_id}>
                    <button
                      type="button"
                      onClick={() => applySender(s.sender_user_id, s.sender_name)}
                      className={cn(
                        "w-full text-left flex items-center gap-2 px-3 py-1.5 rounded-md border transition-colors",
                        active
                          // Açık emerald zemin + explicit koyu emerald metin
                          // (hem light hem dark temada okunur — CLAUDE.md kontrast kuralı)
                          ? "bg-emerald-100 border-emerald-400"
                          : "bg-background border-border hover:bg-muted",
                      )}
                    >
                      <span
                        className={cn(
                          "w-5 text-center text-xs font-semibold",
                          active ? "text-emerald-800" : "text-muted-foreground",
                        )}
                      >
                        {i + 1}.
                      </span>
                      <span className="flex-1 min-w-0">
                        <span
                          className={cn(
                            "block text-sm font-medium truncate",
                            active && "text-emerald-900",
                          )}
                        >
                          {s.sender_name}
                        </span>
                        <span
                          className={cn(
                            "text-[10px]",
                            active ? "text-emerald-700" : "text-muted-foreground",
                          )}
                        >
                          {ROLE_LABELS_TR[s.sender_role] ?? s.sender_role}
                        </span>
                      </span>
                      <span
                        className={cn(
                          "text-sm font-semibold tabular-nums",
                          active && "text-emerald-900",
                        )}
                      >
                        {s.count}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Log tablosu */}
      <Card>
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold inline-flex items-center gap-1.5">
            <MessageSquare className="size-4 text-emerald-700" aria-hidden />
            Son {data.items.length} kayıt
            <span className="text-xs text-muted-foreground font-normal ml-1">
              · toplam {data.total}
            </span>
          </h2>
          {q.isFetching ? (
            <span className="text-[11px] text-muted-foreground">
              Yenileniyor…
            </span>
          ) : null}
        </div>
        {data.items.length === 0 ? (
          <div className="p-6 text-center text-sm text-muted-foreground">
            Filtreye uyan kayıt yok.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-muted-foreground">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Zaman</th>
                  <th className="text-left px-3 py-2 font-medium">Gönderen</th>
                  <th className="text-left px-3 py-2 font-medium">Hedef</th>
                  <th className="text-left px-3 py-2 font-medium">Şablon</th>
                  <th className="text-right px-3 py-2 font-medium">Karakter</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((it) => (
                  <LogRow
                    key={it.id}
                    item={it}
                    activeSenderId={senderFilter?.id ?? null}
                    onPickSender={(id, name) => applySender(id, name)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function LogRow({
  item,
  activeSenderId,
  onPickSender,
}: {
  item: DispatchLogItem;
  activeSenderId: number | null;
  onPickSender: (id: number, name: string) => void;
}) {
  const active = activeSenderId === item.sender_user_id;
  return (
    <tr
      className={cn(
        "hover:bg-muted/30 border-l-4",
        // Aktif satır: zemin müdahalesi yok (koyu temada kontrast sorunu yapmasın),
        // sol BORDER ile vurgu — hem light hem dark'ta belirgin.
        active ? "border-l-emerald-500" : "border-l-transparent",
      )}
    >
      <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
        {formatDateShort(item.created_at)}
      </td>
      <td className="px-3 py-2">
        <button
          type="button"
          onClick={() => onPickSender(item.sender_user_id, item.sender_name)}
          className="text-left hover:underline w-full text-foreground"
          title="Bu gönderene filtrele"
        >
          <div className="font-medium truncate">{item.sender_name}</div>
        </button>
        <div className="text-[10px] text-muted-foreground">
          {ROLE_LABELS_TR[item.sender_role] ?? item.sender_role}
        </div>
      </td>
      <td className="px-3 py-2">
        <div className="font-medium truncate">{item.target_name}</div>
        {item.target_role ? (
          <div className="text-[10px] text-muted-foreground">
            {ROLE_LABELS_TR[item.target_role] ?? item.target_role}
          </div>
        ) : null}
      </td>
      <td className="px-3 py-2">
        <div className="font-medium truncate text-foreground">
          {item.template_name_tr ?? "(silinmiş şablon)"}
        </div>
        <div className="text-[10px] text-muted-foreground font-mono">
          {item.template_key}
        </div>
      </td>
      <td className="px-3 py-2 text-right tabular-nums">
        {item.character_count}
      </td>
    </tr>
  );
}

function KpiCard({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium inline-flex items-center gap-1.5">
          {icon}
          {label}
        </div>
        <div className="text-2xl font-semibold tabular-nums mt-1">{value}</div>
        {sub ? (
          <div className="text-[10px] text-muted-foreground truncate">
            {sub}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function formatDateShort(iso: string): string {
  try {
    const d = new Date(iso);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mn = String(d.getMinutes()).padStart(2, "0");
    return `${dd}.${mm} ${hh}:${mn}`;
  } catch {
    return iso;
  }
}
