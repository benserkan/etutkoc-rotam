"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  Info,
  Loader2,
  Megaphone,
  Plus,
  Send,
  Trash2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminKeys, getAdminAnnouncements } from "@/lib/api/admin";
import {
  useCreateAnnouncement,
  useDeleteAnnouncement,
} from "@/lib/hooks/use-admin-mutations";
import type {
  AnnouncementAudience,
  AnnouncementItem,
  AnnouncementSeverity,
  AnnouncementsListResponse,
} from "@/lib/types/admin";

interface Props {
  initial: AnnouncementsListResponse;
}

/**
 * Duyurular — Jinja `announcements_list.html` feature parity.
 *
 * + Yeni Duyuru formu (severity + audience + starts_at/ends_at + dismissible)
 * + son 50 duyuru tablosu (aktif vurgusu + severity rozeti + sil).
 */
export function AdminAnnouncementsClient({ initial }: Props) {
  const q = useQuery<AnnouncementsListResponse>({
    queryKey: adminKeys.announcements(),
    queryFn: () => getAdminAnnouncements(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

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
          <Megaphone className="size-6 text-indigo-700" aria-hidden />
          Duyurular
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Sistemi kullanan herkese veya belirli rollere üst banner ile mesaj
          göstermek için kullanılır. Bakım uyarısı, yeni özellik duyurusu,
          kritik hata bildirimi gibi durumlar için.
        </p>
      </header>

      <CreateForm
        severities={data.severities}
        audiences={data.audiences}
      />

      {data.items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            Henüz duyuru yok.
          </CardContent>
        </Card>
      ) : (
        <AnnouncementsTable items={data.items} />
      )}
    </div>
  );
}

function CreateForm({
  severities,
  audiences,
}: {
  severities: AnnouncementsListResponse["severities"];
  audiences: AnnouncementsListResponse["audiences"];
}) {
  const router = useRouter();
  const mut = useCreateAnnouncement();
  const [title, setTitle] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [severity, setSeverity] = React.useState<AnnouncementSeverity>("info");
  const [audience, setAudience] = React.useState<AnnouncementAudience>("all");
  const [startsAt, setStartsAt] = React.useState("");
  const [endsAt, setEndsAt] = React.useState("");
  const [dismissible, setDismissible] = React.useState(true);

  function reset() {
    setTitle("");
    setMessage("");
    setSeverity("info");
    setAudience("all");
    setStartsAt("");
    setEndsAt("");
    setDismissible(true);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        title: title.trim() || null,
        message: message.trim(),
        severity,
        audience,
        starts_at: startsAt || null,
        ends_at: endsAt || null,
        dismissible,
      },
      {
        onSuccess: () => {
          reset();
          router.refresh();
        },
      },
    );
  }

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="text-sm font-medium mb-3 inline-flex items-center gap-1.5">
          <Plus className="size-4 text-indigo-700" aria-hidden />
          Yeni Duyuru
        </h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <Label
                htmlFor="ann-title"
                className="text-xs uppercase tracking-wide"
              >
                Başlık (opsiyonel)
              </Label>
              <Input
                id="ann-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={255}
                className="mt-1"
              />
            </div>
            <div>
              <Label
                htmlFor="ann-severity"
                className="text-xs uppercase tracking-wide"
              >
                Önem Düzeyi (renk)
              </Label>
              <select
                id="ann-severity"
                value={severity}
                onChange={(e) =>
                  setSeverity(e.target.value as AnnouncementSeverity)
                }
                className="mt-1 w-full px-3 py-2 border border-input rounded text-sm bg-card"
              >
                {severities.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <Label
              htmlFor="ann-message"
              className="text-xs uppercase tracking-wide"
            >
              Mesaj <span className="text-rose-500">*</span>
            </Label>
            <textarea
              id="ann-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              rows={3}
              placeholder="örn: 14 Mayıs 22:00-23:00 arasında planlı bakım yapılacaktır."
              className="mt-1 w-full px-3 py-2 border border-input rounded text-sm font-sans bg-card"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <Label
                htmlFor="ann-audience"
                className="text-xs uppercase tracking-wide"
              >
                Kimler Görsün
              </Label>
              <select
                id="ann-audience"
                value={audience}
                onChange={(e) =>
                  setAudience(e.target.value as AnnouncementAudience)
                }
                className="mt-1 w-full px-3 py-2 border border-input rounded text-sm bg-card"
              >
                {audiences.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label
                htmlFor="ann-start"
                className="text-xs uppercase tracking-wide"
              >
                Başlangıç (boş = hemen)
              </Label>
              <Input
                id="ann-start"
                type="datetime-local"
                value={startsAt}
                onChange={(e) => setStartsAt(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label
                htmlFor="ann-end"
                className="text-xs uppercase tracking-wide"
              >
                Bitiş (boş = süresiz)
              </Label>
              <Input
                id="ann-end"
                type="datetime-local"
                value={endsAt}
                onChange={(e) => setEndsAt(e.target.value)}
                className="mt-1"
              />
            </div>
          </div>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={dismissible}
                onChange={(e) => setDismissible(e.target.checked)}
                className="accent-indigo-600"
              />
              <span>
                Kullanıcı kendi tarafında kapatabilsin (kapattığında bu cihazda
                bir daha görmez)
              </span>
            </label>
            <Button
              type="submit"
              disabled={mut.isPending || message.trim().length === 0}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Send className="size-4" aria-hidden />
              )}
              Duyuru Yayınla
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground">
            💡 Tüm zamanlar UTC saatine göre yorumlanır. Türkiye saatinden{" "}
            <strong>3 saat çıkar</strong>.
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

function AnnouncementsTable({ items }: { items: AnnouncementItem[] }) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Mesaj</th>
              <th className="text-left px-4 py-2 font-medium">Önem</th>
              <th className="text-left px-4 py-2 font-medium">Görüyor</th>
              <th className="text-left px-4 py-2 font-medium">
                Yayın Aralığı
              </th>
              <th className="text-left px-4 py-2 font-medium">Şu An</th>
              <th className="text-right px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((ann) => (
              <AnnouncementRow key={ann.id} item={ann} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function AnnouncementRow({ item }: { item: AnnouncementItem }) {
  return (
    <tr className={cn(item.is_active_now && "bg-amber-50/30")}>
      <td className="px-4 py-3">
        {item.title && <div className="font-medium">{item.title}</div>}
        <div className="text-xs text-foreground/80 mt-0.5 max-w-md">
          {item.message}
        </div>
      </td>
      <td className="px-4 py-3">
        <SeverityBadge severity={item.severity} label={item.severity_label} />
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {item.audience_label}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
        {formatDateTime(item.starts_at)}
        {" → "}
        {item.ends_at ? (
          formatDateTime(item.ends_at)
        ) : (
          <span className="italic">süresiz</span>
        )}
      </td>
      <td className="px-4 py-3">
        {item.is_active_now ? (
          <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200">
            ● Yayında
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">yayında değil</span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <DeleteButton id={item.id} />
      </td>
    </tr>
  );
}

function SeverityBadge({
  severity,
  label,
}: {
  severity: AnnouncementSeverity;
  label: string;
}) {
  const map: Record<
    AnnouncementSeverity,
    { cls: string; Icon: typeof Info; iconColor: string }
  > = {
    critical: {
      cls: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
      Icon: AlertCircle,
      iconColor: "text-rose-600",
    },
    warn: {
      cls: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
      Icon: AlertTriangle,
      iconColor: "text-amber-600",
    },
    info: {
      cls: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
      Icon: Info,
      iconColor: "text-sky-600",
    },
  };
  const m = map[severity];
  const Icon = m.Icon;
  return (
    <span
      className={cn(
        "text-xs px-2 py-0.5 rounded border inline-flex items-center gap-1",
        m.cls,
      )}
    >
      <Icon className={cn("size-3", m.iconColor)} aria-hidden />
      {label}
    </span>
  );
}

function DeleteButton({ id }: { id: number }) {
  const router = useRouter();
  const mut = useDeleteAnnouncement(id);
  const [open, setOpen] = React.useState(false);

  function doDelete() {
    mut.mutate(undefined, {
      onSuccess: () => {
        setOpen(false);
        router.refresh();
      },
    });
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs text-rose-600 hover:text-rose-800 inline-flex items-center gap-0.5"
      >
        <Trash2 className="size-3" aria-hidden />
        Sil
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Duyuruyu Sil</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Duyuru silinsin mi?
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={doDelete}
              disabled={mut.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Trash2 className="size-4" aria-hidden />
              )}
              Sil
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}
