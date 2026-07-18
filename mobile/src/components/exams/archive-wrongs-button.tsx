import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ApiError } from "@/lib/api";
import {
  archiveExamWrongs,
  getExamWrongRows,
  type ExamWrongRowsResponse,
} from "@/lib/exam-import";
import { cn } from "@/lib/utils";

/**
 * Faz 3 köprüsü — SEÇİCİ aktarım (mobil): denemenin tüm yanlışlarını yığmak
 * yerine kullanıcı tekrar etmeye değer soruları İŞARETLER; seçilenler arşive
 * girip aralıklı tekrar kuyruğunda yeniden çözülür. İdempotent.
 * (Hata türü atama web'de — mobilde sade seçim.)
 */
export function ArchiveWrongsButton({
  examId,
  studentId = null,
  wrongCount,
  compact = false,
}: {
  examId: number;
  studentId?: number | null;
  wrongCount: number;
  compact?: boolean;
}) {
  const [open, setOpen] = React.useState(false);
  if (wrongCount <= 0) return null;
  return (
    <>
      {compact ? (
        <Pressable
          onPress={() => setOpen(true)}
          hitSlop={8}
          className="flex-row items-center gap-1 rounded-full bg-rose-50 px-2.5 py-1 active:bg-rose-100"
        >
          <Ionicons name="bookmarks-outline" size={14} color="#be123c" />
          <Text className="text-[11px] font-semibold text-rose-700">
            Arşive soru seç
          </Text>
        </Pressable>
      ) : (
        <Pressable
          onPress={() => setOpen(true)}
          className="flex-row items-center justify-center gap-2 rounded-xl border border-rose-300 bg-white px-4 py-3 active:bg-rose-50"
        >
          <Ionicons name="bookmarks-outline" size={18} color="#be123c" />
          <Text className="font-semibold text-rose-700">
            Yanlışlardan arşive soru seç
          </Text>
        </Pressable>
      )}
      {open ? (
        <SelectWrongsModal
          examId={examId}
          studentId={studentId}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function SelectWrongsModal({
  examId,
  studentId,
  onClose,
}: {
  examId: number;
  studentId: number | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [data, setData] = React.useState<ExamWrongRowsResponse | null>(null);
  const [err, setErr] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    getExamWrongRows(examId, studentId)
      .then((d) => { if (alive) setData(d); })
      .catch((e) => {
        if (alive) setErr(e instanceof ApiError ? e.message : "Liste yüklenemedi.");
      });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- yalnız mount'ta
  }, []);

  const selectable = (data?.rows ?? []).filter(
    (r) => !r.archived && r.topic_id != null,
  );

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      const res = await archiveExamWrongs(
        examId, studentId,
        [...selected].map((id) => ({ question_id: id })),
      );
      qc.invalidateQueries({ queryKey: ["student", "wrong-questions"] });
      if (studentId != null) {
        qc.invalidateQueries({
          queryKey: ["teacher", "student", studentId, "wrong-questions"],
        });
      }
      Alert.alert(
        "Soru Arşivi",
        `${res.data.created} soru arşive eklendi — aralıklı tekrar kuyruğunda yeniden çözülecek.`,
      );
      onClose();
    } catch (e) {
      Alert.alert(
        "Arşive eklenemedi",
        e instanceof ApiError ? e.message : "Aktarım başarısız.",
      );
      setBusy(false);
    }
  }

  return (
    <Modal visible animationType="slide" onRequestClose={onClose}>
      <SafeAreaView className="flex-1 bg-slate-50">
        <View className="flex-row items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <Text className="text-base font-bold text-slate-900">
            Yanlışlardan arşive soru seç
          </Text>
          <Pressable onPress={onClose} hitSlop={10}>
            <Ionicons name="close" size={22} color="#475569" />
          </Pressable>
        </View>
        <ScrollView contentContainerClassName="p-4 gap-2">
          {err ? (
            <Text className="text-sm text-rose-700">{err}</Text>
          ) : !data ? (
            <View className="items-center py-10">
              <ActivityIndicator size="large" color="#be123c" />
            </View>
          ) : (
            <>
              <Text className="text-xs text-slate-500">
                Arşiv seçilmiş sorular içindir — hepsini eklemek şart değil.
                Tekrar etmeye değer bulduklarını işaretle; eklenenler aralıklı
                tekrar kuyruğuna girer.
              </Text>
              <View className="flex-row gap-4">
                <Text
                  onPress={() =>
                    setSelected(new Set(selectable.map((r) => r.question_id)))
                  }
                  className="text-xs font-semibold text-rose-700 underline"
                >
                  Tümünü seç ({selectable.length})
                </Text>
                <Text
                  onPress={() => setSelected(new Set())}
                  className="text-xs text-slate-500 underline"
                >
                  Temizle
                </Text>
              </View>
              {(data.rows ?? []).map((r) => {
                const disabled = r.archived || r.topic_id == null;
                const isSel = selected.has(r.question_id);
                return (
                  <Pressable
                    key={r.question_id}
                    onPress={() => { if (!disabled) toggle(r.question_id); }}
                    className={cn(
                      "flex-row items-center gap-2 rounded-xl border bg-white px-3 py-2.5",
                      isSel ? "border-rose-400 bg-rose-50" : "border-slate-200",
                      disabled && "opacity-50",
                    )}
                  >
                    <Ionicons
                      name={isSel ? "checkbox" : "square-outline"}
                      size={20}
                      color={isSel ? "#be123c" : "#94a3b8"}
                    />
                    <View className="min-w-0 flex-1">
                      <Text className="text-xs font-semibold text-slate-900">
                        Soru {r.question_no ?? "?"}{" "}
                        <Text className="font-normal text-slate-400">
                          · {r.subject ?? "—"}
                        </Text>
                      </Text>
                      <Text className="text-[11px] text-slate-500" numberOfLines={1}>
                        {r.topic_name ?? r.topic_label_raw ?? "—"}
                        {r.correct_answer && r.student_answer
                          ? ` · ${r.student_answer}→${r.correct_answer}`
                          : ""}
                      </Text>
                    </View>
                    {r.archived ? (
                      <Text className="text-[10px] font-semibold text-emerald-700">
                        arşivde
                      </Text>
                    ) : r.topic_id == null ? (
                      <Text className="text-[10px] font-semibold text-amber-700">
                        konusuz
                      </Text>
                    ) : null}
                  </Pressable>
                );
              })}
            </>
          )}
        </ScrollView>
        <View className="border-t border-slate-200 bg-white px-4 py-3">
          <Pressable
            onPress={() => void submit()}
            disabled={busy || selected.size === 0}
            className={cn(
              "flex-row items-center justify-center gap-2 rounded-xl px-5 py-3",
              busy || selected.size === 0
                ? "bg-slate-300"
                : "bg-rose-600 active:bg-rose-700",
            )}
          >
            {busy ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Ionicons name="bookmarks-outline" size={16} color="#fff" />
            )}
            <Text className="font-semibold text-white">
              Seçilenleri arşive ekle ({selected.size})
            </Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </Modal>
  );
}
