"use client";

import * as React from "react";
import { MessageCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { StudentReportShareDialog } from "@/components/shared/exam-report-share-dialog";
import { firstNameOf, trGenitive } from "@/lib/tr-genitive";

const TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

function iso(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function weekLabel(mon: Date): string {
  const sun = new Date(mon);
  sun.setDate(mon.getDate() + 6);
  return mon.getMonth() === sun.getMonth()
    ? `${mon.getDate()}–${sun.getDate()} ${TR_MONTHS[sun.getMonth()]}`
    : `${mon.getDate()} ${TR_MONTHS[mon.getMonth()]} – ${sun.getDate()} ${TR_MONTHS[sun.getMonth()]}`;
}

/** Son 4 tamamlanmış Pazartesi–Pazar haftası (veli haftalık e-postasıyla aynı hafta tanımı). */
function lastWeeks(): { value: string; label: string }[] {
  const now = new Date();
  const mon = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  mon.setDate(mon.getDate() - ((mon.getDay() + 6) % 7) - 7);
  return Array.from({ length: 4 }, (_, i) => {
    const d = new Date(mon);
    d.setDate(mon.getDate() - 7 * i);
    return { value: iso(d), label: `${weekLabel(d)}${i === 0 ? " (geçen hafta)" : ""}` };
  });
}

/** Koçun haftalık raporu veliye WhatsApp'tan göndermesi (bağlantı + Rota sesi + PDF). */
export function ParentWeeklyShareBar({ studentId, studentName }: { studentId: number; studentName?: string | null }) {
  const [weeks] = React.useState(lastWeeks);
  const [week, setWeek] = React.useState(weeks[0].value);
  const [open, setOpen] = React.useState(false);
  const label = weeks.find((w) => w.value === week)?.label.replace(" (geçen hafta)", "") ?? "";
  const message = `Merhaba,
${trGenitive(firstNameOf(studentName))} ${label} haftasının raporunu hazırladım: programa uyumu, ders ders çalışmaları ve gelecek hafta.
Ayrıntılar raporda; sesli olarak da dinleyebilirsiniz.`;

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-emerald-300 bg-emerald-50 px-4 py-3">
      <div className="min-w-0 flex-1 basis-56">
        <p className="text-sm font-bold text-emerald-950">Veliye haftalık rapor</p>
        <p className="text-xs text-emerald-900">
          Pazartesi–Pazar haftası; veli bağlantıyla açar, sesli dinler, PDF indirebilir.
        </p>
      </div>
      <select
        value={week}
        onChange={(e) => setWeek(e.target.value)}
        aria-label="Rapor haftası"
        className="h-9 rounded-md border border-emerald-400 bg-white px-2 text-sm text-slate-900"
      >
        {weeks.map((w) => (
          <option key={w.value} value={w.value}>
            {w.label}
          </option>
        ))}
      </select>
      <Button
        size="sm"
        onClick={() => setOpen(true)}
        className="bg-emerald-700 text-white hover:bg-emerald-800 hover:text-white"
        data-testid="weekly-share-parent"
      >
        <MessageCircle className="size-4" aria-hidden />
        Veliye WhatsApp
      </Button>
      <StudentReportShareDialog
        key={week}
        open={open}
        onClose={() => setOpen(false)}
        studentId={studentId}
        kind="weekly"
        weekStart={week}
        title={`${label} haftalık raporu`}
        message={message}
      />
    </div>
  );
}
