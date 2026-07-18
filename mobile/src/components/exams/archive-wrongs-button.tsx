import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Pressable, Text } from "react-native";

import { ApiError } from "@/lib/api";
import { archiveExamWrongs } from "@/lib/exam-import";
import { cn } from "@/lib/utils";

/** Faz 3 köprüsünün mobil butonu: denemenin yanlışlarını tek tıkla Yanlış
 *  Soru Arşivine aktarır (idempotent — ikinci basış mükerrer üretmez). */
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
  const qc = useQueryClient();
  const [busy, setBusy] = React.useState(false);
  const [done, setDone] = React.useState(false);
  if (wrongCount <= 0) return null;

  async function run() {
    setBusy(true);
    try {
      const res = await archiveExamWrongs(examId, studentId);
      setDone(true);
      qc.invalidateQueries({ queryKey: ["student", "wrong-questions"] });
      if (studentId != null) {
        qc.invalidateQueries({
          queryKey: ["teacher", "student", studentId, "wrong-questions"],
        });
      }
      const d = res.data;
      const parts = [`${d.created} yanlış arşive eklendi.`];
      if (d.skipped_existing > 0) parts.push(`${d.skipped_existing} zaten vardı.`);
      if (d.skipped_no_topic > 0) {
        parts.push(
          `${d.skipped_no_topic} soru konusuz olduğundan atlandı (web panelinde "Satırları düzelt" ile bağlanabilir).`,
        );
      }
      Alert.alert("Yanlış Soru Arşivi", parts.join(" "));
    } catch (e) {
      Alert.alert(
        "Arşive eklenemedi",
        e instanceof ApiError ? e.message : "Aktarım başarısız.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (compact) {
    return (
      <Pressable
        onPress={() => void run()}
        disabled={busy}
        hitSlop={8}
        className="flex-row items-center gap-1 rounded-full bg-rose-50 px-2.5 py-1 active:bg-rose-100"
      >
        {busy ? (
          <ActivityIndicator size="small" color="#be123c" />
        ) : (
          <Ionicons
            name={done ? "checkmark-circle" : "bookmarks-outline"}
            size={14}
            color={done ? "#047857" : "#be123c"}
          />
        )}
        <Text
          className={cn(
            "text-[11px] font-semibold",
            done ? "text-emerald-700" : "text-rose-700",
          )}
        >
          {done ? "Arşivde" : "Yanlışları arşivle"}
        </Text>
      </Pressable>
    );
  }
  return (
    <Pressable
      onPress={() => void run()}
      disabled={busy || done}
      className={cn(
        "flex-row items-center justify-center gap-2 rounded-xl border px-4 py-3",
        done ? "border-emerald-200 bg-emerald-50" : "border-rose-300 bg-white active:bg-rose-50",
      )}
    >
      {busy ? (
        <ActivityIndicator size="small" color="#be123c" />
      ) : (
        <Ionicons
          name={done ? "checkmark-circle" : "bookmarks-outline"}
          size={18}
          color={done ? "#047857" : "#be123c"}
        />
      )}
      <Text
        className={cn(
          "font-semibold",
          done ? "text-emerald-700" : "text-rose-700",
        )}
      >
        {done ? "Arşive eklendi" : `${wrongCount} yanlışı Soru Arşivine ekle`}
      </Text>
    </Pressable>
  );
}
