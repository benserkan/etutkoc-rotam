import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native";

import { ApiError } from "@/lib/api";
import {
  declareSelfStudy,
  getMySelfStudy,
  getSelfStudyOptions,
  selfStudyKeys,
  withdrawSelfStudy,
  type SelfStudyEntryItem,
  type SelfStudyOptionBook,
} from "@/lib/self-study";
import { studentDevKeys } from "@/lib/student";
import { FormSheet } from "@/components/ui/form-sheet";
import { cn } from "@/lib/utils";

/**
 * Öğrenci "Bağımsız çalışma" kartı (Kitaplarım ekranı).
 * Tatilde/program dışında çözülen testler beyan edilir; koç onaylayınca
 * kitap ilerlemesine işlenir.
 */

const STATUS_TONE: Record<string, { bg: string; text: string }> = {
  pending: { bg: "bg-amber-100", text: "text-amber-800" },
  approved: { bg: "bg-emerald-100", text: "text-emerald-800" },
  rejected: { bg: "bg-rose-100", text: "text-rose-800" },
};

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" });
}

function EntryRow({
  item,
  onWithdraw,
}: {
  item: SelfStudyEntryItem;
  onWithdraw?: () => void;
}) {
  const tone = STATUS_TONE[item.status] ?? { bg: "bg-slate-100", text: "text-slate-600" };
  return (
    <View className="flex-row items-center gap-2 py-2">
      <View className="flex-1">
        <Text className="text-[13px] text-slate-800" numberOfLines={1}>
          {item.book_name} · {item.section_label}
        </Text>
        <Text className="text-[11px] text-slate-400">
          {item.status === "approved" ? item.applied_count : item.test_count} test ·{" "}
          {fmtDate(item.created_at)}
          {item.status === "rejected" && item.review_note ? ` · ${item.review_note}` : ""}
        </Text>
      </View>
      <View className={cn("rounded-full px-2 py-0.5", tone.bg)}>
        <Text className={cn("text-[10px] font-semibold", tone.text)}>{item.status_label}</Text>
      </View>
      {onWithdraw ? (
        <Pressable
          onPress={onWithdraw}
          hitSlop={8}
          className="rounded-full p-1 active:bg-slate-100"
          accessibilityLabel="Geri çek"
        >
          <Ionicons name="arrow-undo-outline" size={16} color="#64748b" />
        </Pressable>
      ) : null}
    </View>
  );
}

export function SelfStudyCard() {
  const qc = useQueryClient();
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [showAll, setShowAll] = React.useState(false);

  const listQ = useQuery({ queryKey: selfStudyKeys.list, queryFn: getMySelfStudy });
  const items = listQ.data?.items ?? [];
  const pendingCount = listQ.data?.pending_count ?? 0;

  const withdraw = useMutation({
    mutationFn: (entryId: number) => withdrawSelfStudy(entryId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: selfStudyKeys.list });
    },
    onError: (e) =>
      Alert.alert("Geri çekilemedi", e instanceof ApiError ? e.message : "Sunucu hatası."),
  });

  function confirmWithdraw(item: SelfStudyEntryItem) {
    Alert.alert("Geri çek", "Bu bildirimi geri çekmek istiyor musun?", [
      { text: "Vazgeç", style: "cancel" },
      { text: "Geri çek", style: "destructive", onPress: () => withdraw.mutate(item.id) },
    ]);
  }

  const visible = showAll ? items.slice(0, 20) : items.slice(0, 3);

  return (
    <View className="rounded-2xl border border-cyan-200 bg-cyan-50/60 p-4">
      <View className="flex-row items-start justify-between gap-2">
        <View className="flex-1">
          <Text className="text-[15px] font-bold text-slate-900">
            Kendi başına mı çalıştın?
          </Text>
          <Text className="mt-0.5 text-xs text-slate-500">
            Tatilde/programsız çözdüğün testleri bildir — koçun onaylayınca
            ilerlemene işlenir.
          </Text>
        </View>
        {pendingCount > 0 ? (
          <View className="rounded-full bg-amber-100 px-2 py-0.5">
            <Text className="text-[10px] font-semibold text-amber-800">
              {pendingCount} bekliyor
            </Text>
          </View>
        ) : null}
      </View>

      <Pressable
        onPress={() => setSheetOpen(true)}
        className="mt-3 flex-row items-center justify-center gap-1.5 rounded-xl bg-brand-700 py-2.5 active:bg-brand-800"
      >
        <Ionicons name="trail-sign-outline" size={16} color="#fff" />
        <Text className="text-sm font-semibold text-white">Bağımsız çalışma bildir</Text>
      </Pressable>

      {visible.length > 0 ? (
        <View className="mt-2">
          {visible.map((it) => (
            <EntryRow
              key={it.id}
              item={it}
              onWithdraw={it.status === "pending" ? () => confirmWithdraw(it) : undefined}
            />
          ))}
          {items.length > 3 ? (
            <Pressable onPress={() => setShowAll((v) => !v)} hitSlop={6}>
              <Text className="text-xs font-semibold text-brand-700">
                {showAll ? "Daha az göster" : `Tümünü göster (${items.length})`}
              </Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      <DeclareSheet visible={sheetOpen} onClose={() => setSheetOpen(false)} />
    </View>
  );
}

function DeclareSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const optionsQ = useQuery({
    queryKey: selfStudyKeys.options,
    queryFn: getSelfStudyOptions,
    enabled: visible,
  });
  const [bookId, setBookId] = React.useState<number | null>(null);
  const [counts, setCounts] = React.useState<Record<number, string>>({});
  const [note, setNote] = React.useState("");

  const books = optionsQ.data?.books ?? [];
  const book: SelfStudyOptionBook | null =
    books.find((b) => b.student_book_id === bookId) ?? null;

  const totalEntered = book
    ? book.sections.reduce((s, sec) => s + (Number(counts[sec.section_id]) || 0), 0)
    : 0;

  const declare = useMutation({
    mutationFn: () => {
      const items = (book?.sections ?? [])
        .map((s) => ({
          student_book_id: book!.student_book_id,
          section_id: s.section_id,
          test_count: Math.min(Number(counts[s.section_id]) || 0, s.remaining),
        }))
        .filter((it) => it.test_count > 0);
      return declareSelfStudy({ items, note: note.trim() || null });
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: selfStudyKeys.list });
      qc.invalidateQueries({ queryKey: selfStudyKeys.options });
      qc.invalidateQueries({ queryKey: studentDevKeys.books });
      const skipped = res.data.skipped.length;
      Alert.alert(
        "Koçuna gönderildi",
        `${res.data.pending_total} test onaya gönderildi.` +
          (skipped ? ` ${skipped} bölüm atlandı.` : ""),
      );
      reset();
      onClose();
    },
    onError: (e) =>
      Alert.alert("Bildirilemedi", e instanceof ApiError ? e.message : "Sunucu hatası."),
  });

  function reset() {
    setBookId(null);
    setCounts({});
    setNote("");
  }

  function close() {
    reset();
    onClose();
  }

  return (
    <FormSheet visible={visible} title="Bağımsız çalışma bildir" onClose={close}>
      {optionsQ.isLoading ? (
        <View className="items-center py-8">
          <ActivityIndicator color="#0e7490" />
        </View>
      ) : !book ? (
        <View className="gap-2 pb-2">
          <Text className="text-xs text-slate-500">
            Hangi kitaptan çözdün? Kitabı seç, sonra bölümlere test sayısı gir.
          </Text>
          {books.length === 0 ? (
            <Text className="py-6 text-center text-sm text-slate-500">
              Sana atanmış kitap yok.
            </Text>
          ) : (
            books.map((b) => (
              <Pressable
                key={b.student_book_id}
                onPress={() => setBookId(b.student_book_id)}
                className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-3 active:bg-slate-50"
              >
                <View className="flex-1 pr-2">
                  <Text className="text-[14px] font-medium text-slate-900" numberOfLines={1}>
                    {b.book_name}
                  </Text>
                  <Text className="text-[11px] text-slate-400">
                    {b.subject_name} · {b.book_type_label}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={16} color="#94a3b8" />
              </Pressable>
            ))
          )}
        </View>
      ) : (
        <View className="gap-3 pb-2">
          <Pressable onPress={() => setBookId(null)} className="flex-row items-center gap-1">
            <Ionicons name="chevron-back" size={14} color="#0e7490" />
            <Text className="text-xs font-semibold text-brand-700">{book.book_name}</Text>
          </Pressable>

          <View className="rounded-xl border border-slate-200 bg-white">
            {book.sections.map((s, idx) => {
              const disabled = s.remaining <= 0;
              return (
                <View
                  key={s.section_id}
                  className={cn(
                    "flex-row items-center gap-2 px-3 py-2",
                    idx > 0 && "border-t border-slate-100",
                    disabled && "opacity-50",
                  )}
                >
                  <View className="flex-1">
                    <Text className="text-[13px] text-slate-800" numberOfLines={1}>
                      {s.label}
                    </Text>
                    <Text className="text-[11px] text-slate-400">
                      {s.remaining} boş / {s.test_count} test
                    </Text>
                  </View>
                  {disabled ? (
                    <Text className="text-[11px] text-slate-400">dolu</Text>
                  ) : (
                    <>
                      <TextInput
                        value={counts[s.section_id] ?? ""}
                        onChangeText={(t) =>
                          setCounts((prev) => ({
                            ...prev,
                            [s.section_id]: t.replace(/[^0-9]/g, ""),
                          }))
                        }
                        keyboardType="number-pad"
                        placeholder="0"
                        placeholderTextColor="#cbd5e1"
                        className="h-9 w-14 rounded-lg border border-slate-200 bg-white px-2 text-center text-[14px] text-slate-900"
                      />
                      <Pressable
                        onPress={() =>
                          setCounts((prev) => ({
                            ...prev,
                            [s.section_id]: String(s.remaining),
                          }))
                        }
                        className="rounded-lg border border-slate-200 px-2 py-1.5 active:bg-slate-50"
                      >
                        <Text className="text-[11px] font-semibold text-slate-600">Tümü</Text>
                      </Pressable>
                    </>
                  )}
                </View>
              );
            })}
          </View>

          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="Not (örn: Köydeydim, kendi çalıştım)"
            placeholderTextColor="#94a3b8"
            multiline
            className="min-h-[44px] rounded-xl border border-slate-200 bg-white px-3 py-2 text-[14px] text-slate-900"
          />

          <Pressable
            onPress={() => declare.mutate()}
            disabled={declare.isPending || totalEntered === 0}
            className={cn(
              "flex-row items-center justify-center gap-2 rounded-xl py-3",
              declare.isPending || totalEntered === 0
                ? "bg-slate-300"
                : "bg-brand-700 active:bg-brand-800",
            )}
          >
            {declare.isPending ? <ActivityIndicator color="#fff" size="small" /> : null}
            <Text className="text-sm font-semibold text-white">
              {totalEntered > 0 ? `${totalEntered} testi koça gönder` : "Test sayısı gir"}
            </Text>
          </Pressable>
        </View>
      )}
    </FormSheet>
  );
}
