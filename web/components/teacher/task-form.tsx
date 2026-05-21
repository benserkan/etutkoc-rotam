"use client";

import * as React from "react";
import { Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type {
  StudentBookListItem,
  StudentBookListResponse,
  TaskCreateBody,
  TaskItemBody,
} from "@/lib/types/teacher";
import type { TaskType } from "@/lib/types/student";

interface Props {
  studentId: number;
  studentBooks: StudentBookListResponse | undefined;
  defaultDate: string;                // "YYYY-MM-DD"
  onSubmit: (body: TaskCreateBody) => void;
  onCancel: () => void;
  isPending: boolean;
}

interface FormItem {
  bookId: number | "";
  sectionId: number | "";
  plannedCount: number;
}

interface BookSectionLite {
  id: number;
  label: string | null;
}

const TASK_TYPE_OPTIONS: Array<{ value: TaskType; label: string }> = [
  { value: "test", label: "Test" },
  { value: "video", label: "Video" },
  { value: "ozet", label: "Özet" },
  { value: "tekrar", label: "Tekrar" },
  { value: "other", label: "Diğer" },
];

/**
 * Görev oluşturma formu — modal/sheet içine yerleştirilir.
 *
 * Çağıran component "atanmış kitap" listesini geçer; bölüm seçeneklerini
 * `studentBooks.items[*]` üzerinden client-side türetiriz — ek API çağrısı
 * gereksiz çünkü `StudentBookListItem` zaten section_count içeriyor.
 *
 * NOT: Bölüm listesi tam detay için "books" endpoint'inde section özetleri
 * yok; gerçek section adlarını gün viewındaki TeacherTaskItem'lardan
 * öğreniyoruz. Burada başlangıç için `section_id` numeric input olarak da
 * verilebilir; daha temiz UX için bölüm select'ini Paket 8 (gelişmiş plan
 * editörü) içinde ele alacağız. Şu an minimal akış: kullanıcı kitap seçer,
 * section_id numeric input + planned_count girer.
 */
export function TaskForm({
  studentId,
  studentBooks,
  defaultDate,
  onSubmit,
  onCancel,
  isPending,
}: Props) {
  void studentId;

  const [date, setDate] = React.useState(defaultDate);
  const [type, setType] = React.useState<TaskType>("test");
  const [title, setTitle] = React.useState("");
  const [scheduledHour, setScheduledHour] = React.useState<string>("");
  const [isDraft, setIsDraft] = React.useState(false);
  const [notes, setNotes] = React.useState("");
  const [items, setItems] = React.useState<FormItem[]>([
    { bookId: "", sectionId: "", plannedCount: 1 },
  ]);
  const [error, setError] = React.useState<string | null>(null);

  function updateItem(idx: number, patch: Partial<FormItem>) {
    setItems((arr) =>
      arr.map((it, i) => (i === idx ? { ...it, ...patch } : it)),
    );
  }

  function removeItem(idx: number) {
    setItems((arr) => arr.filter((_, i) => i !== idx));
  }

  function addItem() {
    setItems((arr) => [
      ...arr,
      { bookId: "", sectionId: "", plannedCount: 1 },
    ]);
  }

  function getBookSections(bookId: number | ""): BookSectionLite[] {
    if (!bookId || !studentBooks) return [];
    // studentBooks (StudentBookListResponse) section listesi içermez; sadece
    // section_count içerir. Boş döner — UI numeric input ile devam eder.
    const found = studentBooks.items.find((b) => b.book_id === bookId);
    if (!found) return [];
    return [];
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("Başlık zorunlu.");
      return;
    }
    if (items.length === 0) {
      setError("En az bir kalem ekleyin.");
      return;
    }
    const itemsBody: TaskItemBody[] = [];
    for (const it of items) {
      if (!it.bookId || !it.sectionId) {
        setError("Tüm kalemler için kitap ve bölüm seçin.");
        return;
      }
      if (it.plannedCount < 1) {
        setError("Sayı 1'den küçük olamaz.");
        return;
      }
      itemsBody.push({
        book_id: Number(it.bookId),
        section_id: Number(it.sectionId),
        planned_count: it.plannedCount,
      });
    }
    let hourNum: number | null = null;
    if (scheduledHour.trim() !== "") {
      const h = Number(scheduledHour);
      if (!Number.isFinite(h) || h < 0 || h > 23) {
        setError("Saat 0-23 arasında olmalı.");
        return;
      }
      hourNum = h;
    }
    onSubmit({
      date,
      type,
      title: cleanTitle,
      scheduled_hour: hourNum,
      is_draft: isDraft,
      notes: notes.trim() ? notes.trim() : null,
      items: itemsBody,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="task-date">Tarih</Label>
          <Input
            id="task-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="task-hour">Saat (0-23, opsiyonel)</Label>
          <Input
            id="task-hour"
            type="number"
            min={0}
            max={23}
            value={scheduledHour}
            onChange={(e) => setScheduledHour(e.target.value)}
          />
        </div>
      </div>

      <div className="space-y-1">
        <Label htmlFor="task-title">Başlık</Label>
        <Input
          id="task-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Örn. Matematik 1. ünite test"
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="task-type">Tip</Label>
          <select
            id="task-type"
            value={type}
            onChange={(e) => setType(e.target.value as TaskType)}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            {TASK_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label className="flex items-center gap-2 h-9">
            <input
              type="checkbox"
              checked={isDraft}
              onChange={(e) => setIsDraft(e.target.checked)}
            />
            Taslak (öğrenci görmesin)
          </Label>
        </div>
      </div>

      <div className="space-y-1">
        <Label htmlFor="task-notes">Not (opsiyonel)</Label>
        <textarea
          id="task-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className={cn(
            "w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        />
      </div>

      <fieldset className="space-y-2 border-t border-border pt-3">
        <legend className="text-sm font-medium">Kalemler</legend>
        {items.map((it, idx) => (
          <ItemRow
            key={idx}
            idx={idx}
            item={it}
            studentBooks={studentBooks}
            sections={getBookSections(it.bookId)}
            onUpdate={(p) => updateItem(idx, p)}
            onRemove={items.length > 1 ? () => removeItem(idx) : undefined}
          />
        ))}
        <Button type="button" variant="outline" size="sm" onClick={addItem}>
          + Kalem ekle
        </Button>
      </fieldset>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onCancel} disabled={isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Görevi ekle
        </Button>
      </div>
    </form>
  );
}

function ItemRow({
  idx,
  item,
  studentBooks,
  sections,
  onUpdate,
  onRemove,
}: {
  idx: number;
  item: FormItem;
  studentBooks: StudentBookListResponse | undefined;
  sections: BookSectionLite[];
  onUpdate: (patch: Partial<FormItem>) => void;
  onRemove: (() => void) | undefined;
}) {
  void sections;
  return (
    <div className="grid grid-cols-12 gap-2 items-end">
      <div className="col-span-5 space-y-1">
        <Label htmlFor={`item-book-${idx}`} className="text-xs">
          Kitap
        </Label>
        <select
          id={`item-book-${idx}`}
          value={item.bookId === "" ? "" : String(item.bookId)}
          onChange={(e) =>
            onUpdate({
              bookId: e.target.value ? Number(e.target.value) : "",
              sectionId: "",
            })
          }
          className={cn(
            "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          <option value="">— Seç —</option>
          {(studentBooks?.items ?? []).map((b: StudentBookListItem) => (
            <option key={b.book_id} value={b.book_id}>
              {b.book_name}
            </option>
          ))}
        </select>
      </div>
      <div className="col-span-4 space-y-1">
        <Label htmlFor={`item-section-${idx}`} className="text-xs">
          Bölüm ID
        </Label>
        <Input
          id={`item-section-${idx}`}
          type="number"
          min={1}
          value={item.sectionId === "" ? "" : item.sectionId}
          onChange={(e) =>
            onUpdate({
              sectionId: e.target.value ? Number(e.target.value) : "",
            })
          }
          placeholder="örn. 12"
          required
        />
      </div>
      <div className="col-span-2 space-y-1">
        <Label htmlFor={`item-count-${idx}`} className="text-xs">
          Sayı
        </Label>
        <Input
          id={`item-count-${idx}`}
          type="number"
          min={1}
          value={item.plannedCount}
          onChange={(e) => onUpdate({ plannedCount: Math.max(1, Number(e.target.value) || 1) })}
          required
        />
      </div>
      <div className="col-span-1">
        {onRemove ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onRemove}
            aria-label="Kalemi kaldır"
            className="h-9 w-9"
          >
            <Trash2 className="size-4" aria-hidden />
          </Button>
        ) : null}
      </div>
    </div>
  );
}
