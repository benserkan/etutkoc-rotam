"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  Mail,
  Smartphone,
  MessageCircle,
  MessageSquare,
  Search,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import {
  adminKeys,
  getAdminCommunicationHealth,
  getAdminCommunicationLog,
} from "@/lib/api/admin";
import type { CommHealthOverview, CommChannelSummary } from "@/lib/types/admin";

const CHANNEL_ICON: Record<string, typeof Mail> = {
  email: Mail,
  push: Smartphone,
  whatsapp: MessageCircle,
  sms: MessageSquare,
};

// Durum tonu — açık zeminde explicit koyu metin (koyu temada okunur)
function statusTone(s: string): string {
  switch (s) {
    case "delivered":
      return "bg-emerald-100 text-emerald-900 ring-1 ring-inset ring-emerald-300";
    case "sent":
      return "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-200";
    case "bounced":
      return "bg-rose-100 text-rose-900 ring-1 ring-inset ring-rose-300";
    case "failed":
      return "bg-rose-50 text-rose-800 ring-1 ring-inset ring-rose-200";
    case "queued":
      return "bg-sky-50 text-sky-800 ring-1 ring-inset ring-sky-200";
    case "suppressed":
      return "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

function pctColor(p: number | null): string {
  if (p === null) return "text-slate-400";
  if (p >= 95) return "text-emerald-600";
  if (p >= 80) return "text-amber-600";
  return "text-rose-600";
}

function fmt(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getDate())}.${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const STATUS_OPTIONS = [
  ["", "Tüm durumlar"],
  ["sent", "Gönderildi"],
  ["delivered", "Ulaştı"],
  ["bounced", "Geri döndü"],
  ["failed", "Başarısız"],
  ["queued", "Kuyrukta"],
  ["suppressed", "Gönderilmedi (tercih)"],
] as const;

const DAYS_OPTIONS = [
  [1, "Son 24 saat"],
  [7, "Son 7 gün"],
  [30, "Son 30 gün"],
] as const;

export function CommunicationHealthClient({ initial }: { initial: CommHealthOverview }) {
  const [days, setDays] = useState(7);
  const [channel, setChannel] = useState(""); // "" = tüm kanallar
  const [status, setStatus] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const limit = 50;

  // Arama debounce
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  const overview = useQuery({
    queryKey: adminKeys.communicationHealth(days),
    queryFn: () => getAdminCommunicationHealth(days),
    initialData: days === 7 ? initial : undefined,
  });

  const filters = useMemo(
    () => ({ channel, status, days, q, page, limit }),
    [channel, status, days, q, page],
  );
  const log = useQuery({
    queryKey: adminKeys.communicationLog(filters),
    queryFn: () => getAdminCommunicationLog(filters),
    placeholderData: keepPreviousData,
  });

  const ov = overview.data;
  const list = log.data;

  return (
    <div className="space-y-6">
      {/* Başlık */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">İletişim Sağlığı</h1>
          <p className="text-sm text-muted-foreground">
            E-posta, mobil bildirim, WhatsApp ve SMS gönderimlerinin sağlığı ve
            tüm gönderim kayıtları tek yerde — ne, kime, ne zaman, hangi durumda.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg border border-slate-300 bg-background px-3 py-1.5 text-sm"
          >
            {DAYS_OPTIONS.map(([v, l]) => (
              <option key={v} value={v}>{l}</option>
            ))}
          </select>
          <button
            onClick={() => { overview.refetch(); log.refetch(); }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
          >
            <RefreshCw className="size-4" /> Yenile
          </button>
        </div>
      </div>

      {/* Genel + kanal kartları */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(ov?.channels ?? []).map((c) => (
          <ChannelCard
            key={c.channel}
            c={c}
            active={channel === c.channel}
            onClick={() => {
              setChannel(channel === c.channel ? "" : c.channel);
              setPage(1);
            }}
          />
        ))}
      </div>
      {ov && (
        <p className="text-xs text-muted-foreground">
          {ov.window_days} günde toplam <b>{ov.overall.total}</b> gönderim · genel
          başarı{" "}
          <b className={pctColor(ov.overall.success_pct)}>
            {ov.overall.success_pct === null ? "—" : `%${ov.overall.success_pct}`}
          </b>{" "}
          · başarı = ulaşan/(ulaşan+başarısız); kuyrukta + tercihle gönderilmeyenler
          hariç.
        </p>
      )}

      {/* Drill-down */}
      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3">
          <span className="text-sm font-semibold text-foreground">
            Gönderim kayıtları
            {channel && (
              <span className="ml-1 text-cyan-700">
                · {ov?.channels.find((c) => c.channel === channel)?.label}
              </span>
            )}
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {channel && (
              <button
                onClick={() => { setChannel(""); setPage(1); }}
                className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs hover:bg-slate-50"
              >
                Tüm kanallar
              </button>
            )}
            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
              className="rounded-lg border border-slate-300 bg-background px-2.5 py-1.5 text-sm"
            >
              {STATUS_OPTIONS.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-slate-400" />
              <input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Alıcı / konu ara"
                className="w-48 rounded-lg border border-slate-300 bg-background py-1.5 pl-8 pr-3 text-sm"
              />
            </div>
          </div>
        </div>

        {/* Tablo */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs text-slate-500">
                <th className="px-3 py-2 font-medium">Zaman</th>
                <th className="px-3 py-2 font-medium">Kanal</th>
                <th className="px-3 py-2 font-medium">Tür</th>
                <th className="px-3 py-2 font-medium">Alıcı</th>
                <th className="px-3 py-2 font-medium">Konu</th>
                <th className="px-3 py-2 font-medium">Durum</th>
              </tr>
            </thead>
            <tbody>
              {(list?.items ?? []).map((it) => {
                const Icon = CHANNEL_ICON[it.channel] ?? Mail;
                return (
                  <tr key={it.id} className="border-b border-slate-50 align-top">
                    <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                      {fmt(it.created_at)}
                    </td>
                    <td className="px-3 py-2">
                      <span className="inline-flex items-center gap-1 text-slate-700">
                        <Icon className="size-3.5 text-slate-400" />
                        {it.channel_label}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-500">{it.category ?? "—"}</td>
                    <td className="px-3 py-2 text-slate-700">
                      {it.to_user_name ? (
                        <span>
                          {it.to_user_name}
                          <span className="block text-xs text-slate-400">
                            {it.to_address}
                          </span>
                        </span>
                      ) : (
                        it.to_address ?? "—"
                      )}
                    </td>
                    <td className="max-w-[220px] truncate px-3 py-2 text-slate-600" title={it.subject ?? ""}>
                      {it.subject ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${statusTone(it.status)}`}>
                        {it.status_label}
                      </span>
                      {it.error && (
                        <span className="ml-1 text-xs text-rose-500" title={it.error}>
                          ⚠
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {list && list.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-sm text-slate-400">
                    Bu filtrelerle gönderim kaydı yok.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Sayfalama */}
        {list && list.pages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-100 p-3 text-sm">
            <span className="text-slate-500">
              {list.total} kayıt · sayfa {list.page}/{list.pages}
            </span>
            <div className="flex gap-1">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1.5 disabled:opacity-40 hover:bg-slate-50"
              >
                <ChevronLeft className="size-4" /> Önceki
              </button>
              <button
                disabled={page >= list.pages}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1.5 disabled:opacity-40 hover:bg-slate-50"
              >
                Sonraki <ChevronRight className="size-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ChannelCard({
  c,
  active,
  onClick,
}: {
  c: CommChannelSummary;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = CHANNEL_ICON[c.channel] ?? Mail;
  const w = c.window;
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition ${
        active
          ? "border-cyan-500 ring-2 ring-cyan-200 bg-cyan-50/40"
          : "border-slate-200 bg-white hover:border-slate-300"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-2 font-semibold text-foreground">
          <Icon className="size-4 text-cyan-700" /> {c.label}
        </span>
        <span className={`text-lg font-bold ${pctColor(w.success_pct)}`}>
          {w.success_pct === null ? "—" : `%${w.success_pct}`}
        </span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs text-slate-600">
        <span>Toplam: <b className="text-slate-800">{w.total}</b></span>
        <span>Gönderildi: <b className="text-emerald-700">{w.sent}</b></span>
        {w.delivered > 0 && <span>Ulaştı: <b className="text-emerald-700">{w.delivered}</b></span>}
        {(w.bounced > 0 || w.failed > 0) && (
          <span>Hata: <b className="text-rose-600">{w.bounced + w.failed}</b></span>
        )}
        {w.suppressed > 0 && <span>Gönderilmedi: <b className="text-slate-500">{w.suppressed}</b></span>}
        {w.queued > 0 && <span>Kuyrukta: <b className="text-sky-700">{w.queued}</b></span>}
      </div>
      <p className="mt-2 text-[11px] text-slate-400">
        Son 24s: {c.last24h.total} gönderim
        {c.last24h.failed > 0 && ` · ${c.last24h.failed} hata`}
      </p>
    </button>
  );
}
