import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import {
  denemePendingKey,
  getDenemePending,
  setDenemeResults,
  type DenemePendingRow,
  type DenemeResultRow,
} from "@/lib/student";

/**
 * Sonucu girilmemiş denemeler (D3) — çözüldü işaretli ama doğru/yanlışı girilmemiş.
 * Sonuç girilince Denemeler'e ve net grafiğine işlenir. Liste boşsa hiç çizilmez.
 */
function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function waitText(days: number): string {
  if (days <= 0) return "bugün";
  if (days === 1) return "dün";
  return `${days} gün önce`;
}

function parseNum(s: string): number | null {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <View className="flex-1 gap-1">
      <Text className="text-xs font-medium text-slate-600">{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChange(v.replace(/[^0-9]/g, "").slice(0, 4))}
        keyboardType="number-pad"
        placeholder="—"
        placeholderTextColor="#cbd5e1"
        className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-base text-slate-900"
      />
    </View>
  );
}

function ResultSheet({ row, onClose }: { row: DenemePendingRow; onClose: () => void }) {
  const qc = useQueryClient();
  const [correct, setCorrect] = React.useState("");
  const [wrong, setWrong] = React.useState("");
  const [qn, setQn] = React.useState(row.question_count != null ? String(row.question_count) : "");
  const [dur, setDur] = React.useState(row.duration_minutes != null ? String(row.duration_minutes) : "");
  const c = parseNum(correct);
  const w = parseNum(wrong);
  const q = parseNum(qn);
  const has = c != null || w != null;
  const blank = has && q != null ? Math.max(0, q - (c ?? 0) - (w ?? 0)) : null;
  const over = has && q != null && (c ?? 0) + (w ?? 0) > q;
  const net = has ? (c ?? 0) - (w ?? 0) / (row.exam_section === "lgs" ? 3 : 4) : null;
  const save = useMutation({
    mutationFn: (rows: DenemeResultRow[]) => setDenemeResults(row.task_id, rows),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student"] });
      onClose();
    },
  });
  const submit = () => {
    const o: DenemeResultRow = { item_id: row.item_id, solved: true, correct: c ?? 0, wrong: w ?? 0 };
    if (q != null && q !== row.question_count) o.question_count = q;
    const d = parseNum(dur);
    if (d != null && d > 0) o.duration_minutes = d;
    save.mutate([o]);
  };
  const err = save.error as { message?: string } | null;
  return (
    <FormSheet visible title={row.label} onClose={onClose}>
      <View className="gap-3">
        <Text className="text-sm text-slate-600">
          Doğru ve yanlışını gir; boş kendiliğinden hesaplanır. Kaynağındaki soru sayısı farklıysa “Soru”yu düzelt.
        </Text>
        <View className="flex-row gap-2">
          <Field label="Doğru" value={correct} onChange={setCorrect} />
          <Field label="Yanlış" value={wrong} onChange={setWrong} />
        </View>
        <View className="flex-row gap-2">
          <Field label="Soru" value={qn} onChange={setQn} />
          <Field label="Süre (dk)" value={dur} onChange={setDur} />
        </View>
        <Text className={`text-xs ${over ? "text-rose-600" : "text-slate-500"}`}>
          {over
            ? "Doğru + yanlış soru sayısından fazla — soru sayısını düzelt."
            : has && net != null
              ? `Boş ${blank ?? "—"} · Net ${net.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}`
              : "Doğru ve yanlış sayını yaz."}
        </Text>
        {err?.message ? <Text className="text-sm text-rose-600">{err.message}</Text> : null}
        <Pressable
          onPress={submit}
          disabled={!has || over || save.isPending}
          className={`items-center rounded-xl py-3.5 ${!has || over || save.isPending ? "bg-brand-700/50" : "bg-brand-700 active:bg-brand-800"}`}
        >
          <Text className="text-base font-semibold text-white">{save.isPending ? "Kaydediliyor…" : "Kaydet"}</Text>
        </Pressable>
      </View>
    </FormSheet>
  );
}

export function DenemePendingCard() {
  const q = useQuery({ queryKey: denemePendingKey, queryFn: getDenemePending, staleTime: 30_000 });
  const [open, setOpen] = React.useState<DenemePendingRow | null>(null);
  const data = q.data;
  if (!data || data.count === 0) return null;
  return (
    <View className="gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4">
      <View className="flex-row items-center gap-2">
        <Ionicons name="clipboard-outline" size={18} color="#b45309" />
        <Text className="flex-1 text-sm font-semibold text-amber-950">
          Sonucu girilmemiş {data.count} deneme
        </Text>
      </View>
      <Text className="text-xs text-amber-900">
        Bu denemeleri çözdün ama doğru/yanlışını girmedin. Sonucu girince Denemeler’e ve net grafiğine işlenir.
      </Text>
      {data.rows.map((r) => (
        <Pressable
          key={r.item_id}
          onPress={() => setOpen(r)}
          className="flex-row items-center gap-3 rounded-xl bg-white px-3 py-2.5 active:bg-slate-50"
        >
          <View className="flex-1">
            <Text className="text-sm font-medium text-slate-900">{r.label}</Text>
            <Text className="text-xs text-slate-500">
              {fmtDate(r.date)} · {waitText(r.days_waiting)}
              {r.question_count ? ` · ${r.question_count} soru` : ""}
            </Text>
          </View>
          <Text className="text-sm font-semibold text-brand-700">Sonucu gir</Text>
        </Pressable>
      ))}
      {open ? <ResultSheet row={open} onClose={() => setOpen(null)} /> : null}
    </View>
  );
}
