import * as React from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import type { CanRequestMatrix, StudentTask } from "@/lib/student";

export type RequestKind = "question" | "change" | "remove";
export interface RequestPayload {
  message?: string;
  proposed_count?: number;
}

export interface ItemUpdate {
  itemId: number;
  completed: number;
  correct: number | null;
  wrong: number | null;
}

interface Row {
  itemId: number;
  label: string;
  unit: string; // "test" | "soru"
  isBookItem: boolean;
  planned: number;
  completed: number;
  correct: string;
  wrong: string;
}

function buildRows(task: StudentTask): Row[] {
  return task.items
    .filter((it) => (it.planned ?? 0) > 0)
    .map((it) => ({
      itemId: it.id,
      label: it.book_name + (it.section_label ? ` · ${it.section_label}` : ""),
      unit: it.book_id == null ? "soru" : "test",
      isBookItem: it.book_id != null,
      planned: it.planned,
      completed: it.completed,
      correct: it.correct != null ? String(it.correct) : "",
      wrong: it.wrong != null ? String(it.wrong) : "",
    }));
}

function parseNum(s: string): number | null {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
}

function NumField({
  label,
  value,
  onChangeText,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
}) {
  return (
    <View className="flex-1 gap-1">
      <Text className="text-xs font-medium text-slate-600">{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9]/g, "").slice(0, 4))}
        keyboardType="number-pad"
        placeholder="—"
        placeholderTextColor="#cbd5e1"
        className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-base text-slate-900"
      />
    </View>
  );
}

function Stepper({
  value,
  max,
  unit,
  onChange,
}: {
  value: number;
  max: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <View className="flex-row items-center gap-3">
      <Pressable
        onPress={() => onChange(Math.max(0, value - 1))}
        className="size-11 items-center justify-center rounded-full border border-slate-300 active:bg-slate-100"
      >
        <Text className="text-xl font-bold text-slate-700">−</Text>
      </Pressable>
      <View className="min-w-[64px] items-center">
        <Text className="text-2xl font-extrabold text-slate-900">{value}</Text>
        <Text className="text-[11px] text-slate-400">/ {max} {unit}</Text>
      </View>
      <Pressable
        onPress={() => onChange(Math.min(max, value + 1))}
        className="size-11 items-center justify-center rounded-full border border-slate-300 active:bg-slate-100"
      >
        <Text className="text-xl font-bold text-slate-700">+</Text>
      </Pressable>
      <View className="flex-1" />
      <Pressable
        onPress={() => onChange(max)}
        className="rounded-lg bg-brand-50 px-3 py-2 active:bg-brand-100"
      >
        <Text className="text-sm font-semibold text-brand-700">Hepsi</Text>
      </Pressable>
    </View>
  );
}

export function TaskSheetContent({
  task,
  busy,
  error,
  onSaveItems,
  onCompleteActivity,
  onUncomplete,
  canRequest,
  hasPendingRequest,
  requestBusy,
  onSubmitRequest,
  onRequestReplace,
}: {
  task: StudentTask;
  busy: boolean;
  error: string | null;
  onSaveItems: (updates: ItemUpdate[]) => void;
  onCompleteActivity: (solvedCount: number | null) => void;
  onUncomplete: () => void;
  canRequest?: CanRequestMatrix;
  hasPendingRequest?: boolean;
  requestBusy?: boolean;
  onSubmitRequest?: (kind: RequestKind, payload: RequestPayload) => void;
  onRequestReplace?: () => void;
}) {
  const [rows, setRows] = React.useState<Row[]>(() => buildRows(task));
  const [solved, setSolved] = React.useState("");
  const isActivity = rows.length === 0;
  const isDone = task.status === "completed";

  const subject = task.items.find((i) => i.subject_id != null)?.subject_name ?? null;
  const bookItem = task.items.find((it) => it.book_id != null);
  const title = bookItem
    ? bookItem.book_name + (bookItem.section_label ? ` · ${bookItem.section_label}` : "")
    : (task.title.includes(" · ") ? task.title.split(" · ").slice(1).join(" · ") : task.title) ||
      "Görev";

  function setRow(itemId: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r) => (r.itemId === itemId ? { ...r, ...patch } : r)));
  }

  // Kitapsız deneme: doğru + yanlış ≤ çözülen (soru). Kitap kalemi: kısıt yok.
  const localError = (() => {
    for (const r of rows) {
      if (!r.isBookItem) {
        const c = parseNum(r.correct) ?? 0;
        const w = parseNum(r.wrong) ?? 0;
        if (c + w > r.completed) return `Doğru + yanlış, çözülen ${r.completed} soruyu geçemez.`;
      }
    }
    return null;
  })();

  function save() {
    if (localError) return;
    onSaveItems(
      rows.map((r) => ({
        itemId: r.itemId,
        completed: r.completed,
        correct: parseNum(r.correct),
        wrong: parseNum(r.wrong),
      })),
    );
  }

  return (
    <View className="gap-4">
      <View>
        {subject ? (
          <Text className="text-[11px] font-bold uppercase tracking-wide text-brand-700">{subject}</Text>
        ) : null}
        <Text className="text-lg font-bold text-slate-900">{title}</Text>
      </View>

      {isActivity ? (
        <View className="gap-3">
          <Text className="text-sm text-slate-600">
            Bu etkinliği tamamladın mı? İstersen çözdüğün soru sayısını da gir.
          </Text>
          <NumField label="Çözdüğün soru (varsa)" value={solved} onChangeText={setSolved} />
          {isDone ? (
            <Pressable
              onPress={onUncomplete}
              disabled={busy}
              className="items-center rounded-xl border border-slate-300 py-3.5 active:bg-slate-100"
            >
              <Text className="text-base font-semibold text-slate-700">Geri al (yapmadım)</Text>
            </Pressable>
          ) : (
            <Pressable
              onPress={() => onCompleteActivity(parseNum(solved))}
              disabled={busy}
              className={`items-center rounded-xl py-3.5 ${busy ? "bg-emerald-600/60" : "bg-emerald-600 active:bg-emerald-700"}`}
            >
              <Text className="text-base font-semibold text-white">Yaptım olarak işaretle</Text>
            </Pressable>
          )}
        </View>
      ) : (
        <View className="gap-5">
          {rows.map((r) => (
            <View key={r.itemId} className="gap-3">
              {rows.length > 1 ? (
                <Text className="text-sm font-semibold text-slate-800">{r.label}</Text>
              ) : null}
              <View className="gap-1.5">
                <Text className="text-xs font-medium text-slate-600">
                  Çözdüğün {r.unit} sayısı
                </Text>
                <Stepper
                  value={r.completed}
                  max={r.planned}
                  unit={r.unit}
                  onChange={(v) => setRow(r.itemId, { completed: v })}
                />
              </View>
              <View className="flex-row gap-3">
                <NumField label="Doğru (soru)" value={r.correct} onChangeText={(v) => setRow(r.itemId, { correct: v })} />
                <NumField label="Yanlış (soru)" value={r.wrong} onChangeText={(v) => setRow(r.itemId, { wrong: v })} />
              </View>
            </View>
          ))}
          <Text className="text-[11px] text-slate-400">
            Doğru/yanlış soru sayısıdır, boş bırakabilirsin. Sonra düzeltebilirsin.
          </Text>

          {localError || error ? (
            <Text className="text-sm text-rose-600">{localError ?? error}</Text>
          ) : null}

          <Pressable
            onPress={save}
            disabled={busy || !!localError}
            className={`items-center rounded-xl py-3.5 ${busy || localError ? "bg-brand-700/50" : "bg-brand-700 active:bg-brand-800"}`}
          >
            <Text className="text-base font-semibold text-white">{busy ? "Kaydediliyor…" : "Kaydet"}</Text>
          </Pressable>
        </View>
      )}

      {onSubmitRequest ? (
        <RequestSection
          canRequest={canRequest}
          hasPending={!!hasPendingRequest}
          busy={!!requestBusy}
          onSubmit={onSubmitRequest}
          onReplace={onRequestReplace}
        />
      ) : null}
    </View>
  );
}

function RequestSection({
  canRequest,
  hasPending,
  busy,
  onSubmit,
  onReplace,
}: {
  canRequest?: CanRequestMatrix;
  hasPending: boolean;
  busy: boolean;
  onSubmit: (kind: RequestKind, payload: RequestPayload) => void;
  onReplace?: () => void;
}) {
  const [open, setOpen] = React.useState<RequestKind | null>(null);
  const [msg, setMsg] = React.useState("");
  const [count, setCount] = React.useState("");

  if (hasPending) {
    return (
      <View className="mt-1 border-t border-slate-200 pt-4">
        <Text className="text-sm text-amber-700">
          Bu görev için bekleyen bir talebin var. &quot;Taleplerim&quot;den takip edebilirsin.
        </Text>
      </View>
    );
  }

  const opts: { kind: RequestKind; label: string; show: boolean }[] = [
    { kind: "question", label: "Soru sor", show: !!canRequest?.question },
    { kind: "change", label: "Sayı değiştir", show: !!canRequest?.change },
    { kind: "remove", label: "Görevi kaldır", show: !!canRequest?.remove },
  ];
  const showReplace = !!canRequest?.replace && !!onReplace;
  if (!opts.some((o) => o.show) && !showReplace) return null;

  function toggle(kind: RequestKind) {
    setOpen((cur) => (cur === kind ? null : kind));
    setMsg("");
    setCount("");
  }

  function submit() {
    if (open === "question") {
      if (!msg.trim()) return;
      onSubmit("question", { message: msg.trim() });
    } else if (open === "change") {
      const n = Number(count);
      if (!count.trim() || !(n > 0)) return;
      onSubmit("change", { proposed_count: n, message: msg.trim() || undefined });
    } else if (open === "remove") {
      onSubmit("remove", { message: msg.trim() || undefined });
    }
  }

  const sendDisabled =
    busy ||
    (open === "question" && !msg.trim()) ||
    (open === "change" && !(Number(count) > 0));

  return (
    <View className="mt-1 gap-3 border-t border-slate-200 pt-4">
      <Text className="text-sm font-semibold text-slate-800">Koça ilet</Text>
      <View className="flex-row flex-wrap gap-2">
        {opts
          .filter((o) => o.show)
          .map((o) => (
            <Pressable
              key={o.kind}
              onPress={() => toggle(o.kind)}
              className={`rounded-full border px-3 py-1.5 ${
                open === o.kind ? "border-brand-600 bg-brand-50" : "border-slate-300"
              }`}
            >
              <Text className={`text-sm font-medium ${open === o.kind ? "text-brand-700" : "text-slate-600"}`}>
                {o.label}
              </Text>
            </Pressable>
          ))}
        {showReplace ? (
          <Pressable onPress={onReplace} className="rounded-full border border-slate-300 px-3 py-1.5">
            <Text className="text-sm font-medium text-slate-600">Kaynak değiştir</Text>
          </Pressable>
        ) : null}
      </View>

      {open ? (
        <View className="gap-2">
          {open === "change" ? (
            <View className="flex-row gap-3">
              <NumField label="Önerdiğin yeni sayı" value={count} onChangeText={(v) => setCount(v.replace(/[^0-9]/g, "").slice(0, 4))} />
              <View className="flex-1" />
            </View>
          ) : null}
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">
              {open === "question" ? "Sorun" : "Not (isteğe bağlı)"}
            </Text>
            <TextInput
              value={msg}
              onChangeText={setMsg}
              placeholder={open === "question" ? "Koçuna sormak istediğin…" : "Kısa açıklama…"}
              placeholderTextColor="#94a3b8"
              multiline
              className="min-h-[60px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
            />
          </View>
          <Pressable
            onPress={submit}
            disabled={sendDisabled}
            className={`items-center rounded-xl py-3 ${sendDisabled ? "bg-slate-300" : "bg-brand-700 active:bg-brand-800"}`}
          >
            <Text className="text-base font-semibold text-white">{busy ? "Gönderiliyor…" : "Koça gönder"}</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

export function TaskSheet(props: {
  task: StudentTask;
  busy: boolean;
  error: string | null;
  onSaveItems: (updates: ItemUpdate[]) => void;
  onCompleteActivity: (solvedCount: number | null) => void;
  onUncomplete: () => void;
  onClose: () => void;
  canRequest?: CanRequestMatrix;
  hasPendingRequest?: boolean;
  requestBusy?: boolean;
  onSubmitRequest?: (kind: RequestKind, payload: RequestPayload) => void;
  onRequestReplace?: () => void;
}) {
  const { onClose, ...content } = props;
  return (
    <Modal visible transparent statusBarTranslucent animationType="slide" onRequestClose={onClose}>
      <View className="flex-1">
        <Pressable className="absolute inset-0 bg-black/40" onPress={onClose} />
        <KeyboardAvoidingView
          className="flex-1 justify-end"
          behavior="padding"
        >
          <View className="max-h-[88%] rounded-t-3xl bg-white px-5 pb-8 pt-3">
            <View className="mb-2 items-center">
              <View className="h-1.5 w-10 rounded-full bg-slate-300" />
            </View>
            <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive">
              <TaskSheetContent {...content} />
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}
