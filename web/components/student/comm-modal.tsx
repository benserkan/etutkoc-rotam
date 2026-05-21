"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getStudentBookSections, studentKeys } from "@/lib/api/student";
import {
  useRequestAdd,
  useRequestChange,
  useRequestQuestion,
  useRequestRemove,
  useRequestReplace,
} from "@/lib/hooks/use-student-mutations";
import type {
  BookSectionsResponse,
  ResourceSidebar,
  StudentTask,
} from "@/lib/types/student";

export type CommMode = "change" | "replace" | "remove" | "question" | "add";

type Props =
  | {
      open: boolean;
      onOpenChange: (open: boolean) => void;
      sidebar: ResourceSidebar;
      dateIso: string;
      mode: "change" | "replace" | "remove" | "question";
      task: StudentTask;
    }
  | {
      open: boolean;
      onOpenChange: (open: boolean) => void;
      sidebar: ResourceSidebar;
      dateIso: string;
      mode: "add";
      targetDate: string;
    };

/**
 * Talep modalı — change / replace / remove / question / add modlarını tek
 * Radix Dialog primitive üzerinde sunar.
 *
 * Mode değiştiğinde form alanları otomatik sıfırlanır (component remount key
 * stratejisi: modal her açılışta state baştan kurulur).
 *
 * Hata zarfı:
 *   - 409 request_already_pending → toast (mutation hook'unda)
 *   - 422 RESERVE_OVER_CAPACITY → toast + modal kapanmaz
 *   - 400 past_day_blocked (add) → toast + modal kapanmaz
 */
export function CommModal(props: Props) {
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      {/* key=mode ile her mode değişiminde form remount → state sızıntısı yok */}
      <DialogContent>
        <CommBody key={props.mode} {...props} />
      </DialogContent>
    </Dialog>
  );
}

function CommBody(props: Props) {
  if (props.mode === "add") {
    return (
      <AddForm
        sidebar={props.sidebar}
        targetDate={props.targetDate}
        onClose={() => props.onOpenChange(false)}
      />
    );
  }
  const close = () => props.onOpenChange(false);
  switch (props.mode) {
    case "change":
      return <ChangeForm task={props.task} dateIso={props.dateIso} onClose={close} />;
    case "replace":
      return (
        <ReplaceForm
          task={props.task}
          sidebar={props.sidebar}
          dateIso={props.dateIso}
          onClose={close}
        />
      );
    case "remove":
      return <RemoveForm task={props.task} dateIso={props.dateIso} onClose={close} />;
    case "question":
      return <QuestionForm task={props.task} dateIso={props.dateIso} onClose={close} />;
  }
}

// =============================================================================
// CHANGE — Sayı değiştir
// =============================================================================

function ChangeForm({
  task,
  dateIso,
  onClose,
}: {
  task: StudentTask;
  dateIso: string;
  onClose: () => void;
}) {
  const [count, setCount] = React.useState<string>(String(task.planned_count));
  const [message, setMessage] = React.useState("");
  const mut = useRequestChange(dateIso);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const n = Number(count);
    if (!Number.isFinite(n) || n < 1) return;
    mut.mutate(
      { task, proposed_count: n, message: message.trim() || undefined },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>Sayıyı değiştir</DialogTitle>
        <DialogDescription>
          Koçunun onayıyla bu görevin test sayısı güncellenir. Mevcut:{" "}
          <span className="font-medium text-foreground">{task.planned_count}</span>
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-2">
        <Label htmlFor="comm-count">Yeni sayı</Label>
        <Input
          id="comm-count"
          type="number"
          min={1}
          value={count}
          onChange={(e) => setCount(e.target.value)}
          autoFocus
        />
      </div>

      <MessageField value={message} onChange={setMessage} optional />

      <Footer
        isPending={mut.isPending}
        onCancel={onClose}
        submitLabel="Talep gönder"
      />
    </form>
  );
}

// =============================================================================
// REPLACE — Kaynak değiştir
// =============================================================================

function ReplaceForm({
  task,
  sidebar,
  dateIso,
  onClose,
}: {
  task: StudentTask;
  sidebar: ResourceSidebar;
  dateIso: string;
  onClose: () => void;
}) {
  // Jinja parite (task_comm_modal.html:75-79): completed_count > 0 ise kaynak
  // değişim formu gizlenir; öğrenci "Çıkar" sekmesini kullanmaya yönlendirilir.
  const hasCompleted = task.completed_count > 0;
  if (hasCompleted) {
    return (
      <div className="space-y-4">
        <DialogHeader>
          <DialogTitle>Kaynağı değiştir</DialogTitle>
        </DialogHeader>
        <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertTriangle
            className="size-5 flex-shrink-0 text-amber-600 mt-0.5"
            aria-hidden
          />
          <div>
            Bu görevde <b>{task.completed_count}</b> test çözülmüş. Kaynak
            değişikliği uygulanamaz. Bunun yerine <b>Çıkar</b> sekmesinden
            görevin çıkarılmasını isteyip yeni bir görev önerebilirsin.
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Kapat
          </Button>
        </DialogFooter>
      </div>
    );
  }
  return (
    <SourcePickerForm
      task={task}
      sidebar={sidebar}
      dateIso={dateIso}
      onClose={onClose}
      mode="replace"
      initialBookId={task.items[0]?.book_id ?? null}
      initialSectionId={task.items[0]?.section_id ?? null}
      initialCount={task.planned_count}
    />
  );
}

/**
 * Kaynak seçici form — Replace ve Add modlarının ortak yapısı.
 * Jinja `task_comm_modal.html:82-119` ile bire bir parite:
 *   - "Yeni kitap" select: optgroup ile ders bazlı gruplama
 *   - "Ünite / Deneme" select: kitap seçilince cascade ile dolar
 *   - "Sayı" input
 */
function SourcePickerForm({
  task,
  sidebar,
  dateIso,
  onClose,
  mode,
  initialBookId,
  initialSectionId,
  initialCount,
  targetDate,
}: {
  task?: StudentTask;
  sidebar: ResourceSidebar;
  dateIso: string;
  onClose: () => void;
  mode: "replace" | "add";
  initialBookId: number | null;
  initialSectionId: number | null;
  initialCount: number;
  targetDate?: string;
}) {
  const [bookId, setBookId] = React.useState<number | "">(
    initialBookId ?? "",
  );
  const [sectionId, setSectionId] = React.useState<number | "">(
    initialSectionId ?? "",
  );
  const [count, setCount] = React.useState<string>(String(initialCount));
  const [message, setMessage] = React.useState("");

  const replaceMut = useRequestReplace(dateIso);
  const addMut = useRequestAdd();
  const mut = mode === "replace" ? replaceMut : addMut;

  // Kitap → ünite cascade (Jinja /student/book-sections HTMX → v2 JSON)
  const sectionsQ = useQuery<BookSectionsResponse>({
    queryKey: studentKeys.bookSections(typeof bookId === "number" ? bookId : 0),
    queryFn: () =>
      getStudentBookSections(typeof bookId === "number" ? bookId : 0),
    enabled: typeof bookId === "number" && bookId > 0,
    staleTime: 60_000,
  });

  function onBookChange(v: string) {
    const num = v === "" ? "" : Number(v);
    setBookId(num as number | "");
    setSectionId(""); // kitap değişince ünite sıfırla (cascade kuralı)
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const n = Number(count);
    if (!Number.isFinite(n) || n < 1) return;
    if (typeof bookId !== "number" || typeof sectionId !== "number") return;
    if (mode === "replace" && task) {
      replaceMut.mutate(
        {
          task,
          new_book_id: bookId,
          new_section_id: sectionId,
          new_count: n,
          message: message.trim() || undefined,
        },
        { onSuccess: () => onClose() },
      );
    } else if (mode === "add" && targetDate) {
      addMut.mutate(
        {
          target_date: targetDate,
          book_id: bookId,
          section_id: sectionId,
          proposed_count: n,
          message: message.trim() || undefined,
        },
        { onSuccess: () => onClose() },
      );
    }
  }

  const isDeneme = sectionsQ.data?.is_deneme ?? false;
  const unitWord = isDeneme ? "deneme" : "test";

  return (
    <form onSubmit={submit} className="space-y-4">
      <DialogHeader>
        {mode === "replace" ? (
          <>
            <DialogTitle>Kaynağı değiştir</DialogTitle>
            <DialogDescription>
              Bu görevi başka bir kaynaktan çözmek istiyorsan — koçun
              onaylayınca eski rezerv iade edilir, yeni kaynaktan rezerv açılır.
            </DialogDescription>
          </>
        ) : (
          <>
            <DialogTitle>Yeni görev iste</DialogTitle>
            <DialogDescription>
              {targetDate} için koçundan ek görev iste — kaynak ve sayıyı sen
              öner, koçun onaylayınca planına eklenir.
            </DialogDescription>
          </>
        )}
      </DialogHeader>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div className="space-y-2 sm:col-span-2">
          <Label htmlFor="src-book">Kitap</Label>
          <select
            id="src-book"
            value={bookId}
            onChange={(e) => onBookChange(e.target.value)}
            className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            required
          >
            <option value="">— kitap seç —</option>
            {sidebar.subjects.map((group) => (
              <optgroup
                key={group.subject_id}
                label={group.subject_name}
              >
                {group.books.map((b) => (
                  <option key={b.book_id} value={b.book_id}>
                    {b.book_name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="src-count">Sayı</Label>
          <Input
            id="src-count"
            type="number"
            min={1}
            value={count}
            onChange={(e) => setCount(e.target.value)}
            required
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="src-section">Ünite / Deneme</Label>
        <select
          id="src-section"
          value={sectionId}
          onChange={(e) =>
            setSectionId(e.target.value ? Number(e.target.value) : "")
          }
          disabled={typeof bookId !== "number" || sectionsQ.isLoading}
          className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
          required
        >
          <option value="">
            {typeof bookId !== "number"
              ? "— önce kitap seç —"
              : sectionsQ.isLoading
                ? "yükleniyor…"
                : `— ${unitWord} seç —`}
          </option>
          {(sectionsQ.data?.items ?? []).map((s) => (
            <option
              key={s.id}
              value={s.id}
              disabled={s.remaining <= 0}
            >
              {s.label}
              {s.topic_name ? ` (${s.topic_name})` : ""} · kalan {s.remaining}
            </option>
          ))}
        </select>
      </div>

      <MessageField value={message} onChange={setMessage} optional />

      <Footer
        isPending={mut.isPending}
        onCancel={onClose}
        submitLabel="Talep gönder"
      />
    </form>
  );
}

// =============================================================================
// REMOVE — Görev çıkar
// =============================================================================

function RemoveForm({
  task,
  dateIso,
  onClose,
}: {
  task: StudentTask;
  dateIso: string;
  onClose: () => void;
}) {
  const [message, setMessage] = React.useState("");
  const mut = useRequestRemove(dateIso);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      { task, message: message.trim() || undefined },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>Görevi çıkar</DialogTitle>
        <DialogDescription>
          Bu görev programdan çıkarılsın istiyorsan koçuna sebebini yazabilirsin.
          Onay sonrası görev silinir, rezervler iade edilir.
        </DialogDescription>
      </DialogHeader>

      <MessageField value={message} onChange={setMessage} optional />

      <Footer
        isPending={mut.isPending}
        onCancel={onClose}
        submitLabel="Çıkar talebi gönder"
        destructive
      />
    </form>
  );
}

// =============================================================================
// QUESTION — Soru sor
// =============================================================================

function QuestionForm({
  task,
  dateIso,
  onClose,
}: {
  task: StudentTask;
  dateIso: string;
  onClose: () => void;
}) {
  const [message, setMessage] = React.useState("");
  const mut = useRequestQuestion(dateIso);
  const isEmpty = message.trim().length === 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (isEmpty) return;
    mut.mutate(
      { task, message: message.trim() },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <DialogHeader>
        <DialogTitle>Koçuna soru sor</DialogTitle>
        <DialogDescription>
          Bu görevle ilgili aklındaki soruyu yaz; koçun yanıtlayınca bildirim
          alacaksın.
        </DialogDescription>
      </DialogHeader>

      <MessageField value={message} onChange={setMessage} required />

      <Footer
        isPending={mut.isPending}
        onCancel={onClose}
        submitLabel="Sor"
        disabled={isEmpty}
      />
    </form>
  );
}

// =============================================================================
// ADD — Yeni görev iste
// =============================================================================

function AddForm({
  sidebar,
  targetDate,
  onClose,
}: {
  sidebar: ResourceSidebar;
  targetDate: string;
  onClose: () => void;
}) {
  return (
    <SourcePickerForm
      sidebar={sidebar}
      dateIso={targetDate}
      onClose={onClose}
      mode="add"
      initialBookId={null}
      initialSectionId={null}
      initialCount={5}
      targetDate={targetDate}
    />
  );
}

// =============================================================================
// Yardımcı UI parçaları
// =============================================================================

function MessageField({
  value,
  onChange,
  optional,
  required,
}: {
  value: string;
  onChange: (s: string) => void;
  optional?: boolean;
  required?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor="comm-msg">
        Mesaj {optional ? <span className="text-muted-foreground">(opsiyonel)</span> : null}
      </Label>
      <textarea
        id="comm-msg"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        maxLength={1000}
        required={required}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        placeholder={
          optional
            ? "Koçuna eklemek istediğin bir not varsa yaz…"
            : "Koçuna soracağın soruyu yaz…"
        }
      />
    </div>
  );
}

function Footer({
  isPending,
  onCancel,
  submitLabel,
  destructive,
  disabled,
}: {
  isPending: boolean;
  onCancel: () => void;
  submitLabel: string;
  destructive?: boolean;
  disabled?: boolean;
}) {
  return (
    <DialogFooter className="gap-2">
      <Button type="button" variant="ghost" onClick={onCancel}>
        Vazgeç
      </Button>
      <Button
        type="submit"
        variant={destructive ? "destructive" : "default"}
        disabled={isPending || disabled}
      >
        {isPending ? <Loader2 className="animate-spin" /> : null}
        {submitLabel}
      </Button>
    </DialogFooter>
  );
}

