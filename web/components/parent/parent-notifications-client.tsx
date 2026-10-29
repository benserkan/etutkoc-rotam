"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, BellOff } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { getParentNotifications, parentKeys } from "@/lib/api/parent";
import type {
  ParentNotificationItem,
  ParentNotificationsResponse,
} from "@/lib/types/parent";

interface Props {
  initial: ParentNotificationsResponse;
}

const KIND_LABELS: Record<string, string> = {
  daily_summary: "Günlük özet",
  empty_day: "Boş gün uyarısı",
  weekly_report: "Haftalık rapor",
  new_program: "Yeni program",
  drop_alert: "Düşüş alarmı",
  teacher_note: "Öğretmen notu",
  invitation: "Davet",
  otp: "Doğrulama kodu",
  exam_approaching: "Sınav yaklaşıyor",
};

const CHANNEL_LABELS: Record<string, string> = {
  email: "E-posta",
  whatsapp: "WhatsApp",
  sms: "SMS",
};

const STATUS_META: Record<
  string,
  { tone: string; label: string }
> = {
  sent: {
    tone: "bg-emerald-50 text-emerald-700 border-emerald-200",
    label: "Gönderildi",
  },
  queued: {
    tone: "bg-amber-50 text-amber-700 border-amber-200",
    label: "Sırada",
  },
  failed: {
    tone: "bg-rose-50 text-rose-700 border-rose-200",
    label: "Başarısız",
  },
  suppressed: {
    tone: "bg-slate-100 text-slate-600 border-slate-200",
    label: "Engellendi",
  },
};

/**
 * Bildirim geçmişi — Jinja `notifications.html` feature parity.
 *
 * Son 100 bildirim listesi. kind/channel/status badge'leri ile.
 */
export function ParentNotificationsClient({ initial }: Props) {
  const q = useQuery<ParentNotificationsResponse>({
    queryKey: parentKeys.notifications(),
    queryFn: () => getParentNotifications(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display inline-flex items-center gap-2">
          <Bell className="size-6 text-[#117A86]" aria-hidden />
          Bildirim Geçmişi
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Size gönderilen son {Math.min(100, data.total)} bildirim
        </p>
      </header>

      {data.items.length === 0 ? (
        <EmptyState />
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {data.items.map((it) => (
              <NotificationRow key={it.id} item={it} />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function NotificationRow({ item }: { item: ParentNotificationItem }) {
  const statusMeta =
    STATUS_META[item.status] ?? {
      tone: "bg-slate-100 text-slate-600 border-slate-200",
      label: item.status || "—",
    };
  const kindLabel = KIND_LABELS[item.kind] ?? item.kind;
  const channelLabel = CHANNEL_LABELS[item.channel] ?? item.channel;
  const when = item.sent_at ?? item.queued_at;

  return (
    <li className="px-5 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{kindLabel}</span>
            <span className="text-[10px] uppercase tracking-wider bg-muted text-foreground/80 px-1.5 py-0.5 rounded">
              {channelLabel}
            </span>
            <span
              className={cn(
                "text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border",
                statusMeta.tone,
              )}
            >
              {statusMeta.label}
            </span>
          </div>
          {item.subject && (
            <div className="text-sm text-foreground/80 mt-1 truncate">
              {item.subject}
            </div>
          )}
          <div className="text-[11px] text-muted-foreground mt-1">
            {item.student_name && <span>{item.student_name} · </span>}
            {when && formatTimestamp(when)}
          </div>
        </div>
      </div>
    </li>
  );
}

function EmptyState() {
  return (
    <Card>
      <CardContent className="p-8 text-center space-y-2">
        <BellOff
          className="size-10 mx-auto text-muted-foreground/60"
          aria-hidden
        />
        <p className="text-sm text-muted-foreground">
          Henüz size gönderilmiş bir bildirim yok. Bildirim altyapısı
          hazırlanıyor; öğrencinizin ilk haftalık özeti hazır olduğunda burada
          görebileceksiniz.
        </p>
      </CardContent>
    </Card>
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm}.${yyyy} ${hh}:${mn}`;
}
