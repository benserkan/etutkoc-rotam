import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AppState, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { ExamImportFlow } from "@/components/exams/exam-import-flow";
import { useAuth } from "@/lib/auth";
import { aiJobAction, aiJobsKey, getAiJobs, type AiJobBrief } from "@/lib/exam-import";

/**
 * Arka planda okunan karneler — "havada kalmasın" (2026-10-29).
 *
 * Koç ve öğrenci uygulamasında her ekranın üstünde durur: okuma bitince kalıcı
 * kutu ("Deniz'in karnesi okundu — Önizle"). Kullanıcı önizleyene ya da
 * kapatana kadar kaybolmaz; uygulama arka plandan dönünce de yenilenir.
 * Bildirim ayrıca gider (sunucu); bu kutu uygulama açıkken haber verir.
 */
export function AiJobsBanner() {
  const { user } = useAuth();
  const role = user?.role;
  const enabled = role === "teacher" || role === "student";
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();
  const [opened, setOpened] = React.useState<AiJobBrief | null>(null);

  const { data, refetch } = useQuery({
    queryKey: aiJobsKey,
    queryFn: getAiJobs,
    enabled,
    refetchInterval: (q) => ((q.state.data?.active_count ?? 0) > 0 ? 5000 : 45000),
  });

  React.useEffect(() => {
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active" && enabled) void refetch();
    });
    return () => sub.remove();
  }, [enabled, refetch]);

  if (!enabled) return null;
  const notices = (data?.items ?? []).filter(
    (j) => (j.status === "done" || j.status === "failed") && !j.acknowledged,
  );
  const job = notices[0];

  async function ack(j: AiJobBrief) {
    try {
      await aiJobAction(j.id, "ack");
    } finally {
      qc.invalidateQueries({ queryKey: aiJobsKey });
    }
  }

  const who =
    job && (role === "student" || job.own_upload)
      ? "Deneme karnen"
      : job?.student_name
        ? `${job.student_name} — deneme karnesi`
        : "Deneme karnesi";

  return (
    <>
      {job ? (
        <View
          pointerEvents="box-none"
          style={{ position: "absolute", top: insets.top + 8, left: 12, right: 12, zIndex: 50 }}
        >
          <View
            className={
              job.status === "done"
                ? "rounded-2xl border border-emerald-300 bg-white p-4 shadow-lg"
                : "rounded-2xl border border-rose-300 bg-white p-4 shadow-lg"
            }
            style={{ elevation: 8 }}
          >
            <View className="flex-row items-start gap-3">
              <Ionicons
                name={job.status === "done" ? "checkmark-circle" : "alert-circle"}
                size={22}
                color={job.status === "done" ? "#059669" : "#e11d48"}
              />
              <View className="flex-1">
                <Text className="text-sm font-bold text-slate-900">
                  {job.status === "done" ? "Karne okundu" : "Karne okunamadı"}
                </Text>
                <Text className="mt-0.5 text-sm text-slate-600">
                  {who}
                  {job.status === "done"
                    ? " hazır. Kontrol edip kaydetmen gerekiyor."
                    : `: ${job.error_message ?? "okuma tamamlanamadı."}`}
                </Text>
                <View className="mt-3 flex-row flex-wrap gap-2">
                  {job.status === "done" ? (
                    <Pressable
                      onPress={() => {
                        setOpened(job);
                        void ack(job);
                      }}
                      className="rounded-xl bg-emerald-700 px-4 py-2.5 active:bg-emerald-800"
                    >
                      <Text className="font-semibold text-white">Önizle ve kaydet</Text>
                    </Pressable>
                  ) : job.retryable ? (
                    <Pressable
                      onPress={async () => {
                        await aiJobAction(job.id, "retry").catch(() => undefined);
                        qc.invalidateQueries({ queryKey: aiJobsKey });
                      }}
                      className="rounded-xl border border-slate-300 px-4 py-2.5 active:bg-slate-100"
                    >
                      <Text className="font-semibold text-slate-700">Tekrar dene (ücretsiz)</Text>
                    </Pressable>
                  ) : null}
                  <Pressable
                    onPress={() => void ack(job)}
                    className="rounded-xl px-4 py-2.5 active:bg-slate-100"
                  >
                    <Text className="font-semibold text-slate-600">
                      {job.status === "done" ? "Sonra" : "Tamam"}
                    </Text>
                  </Pressable>
                </View>
                {notices.length > 1 ? (
                  <Text className="mt-2 text-xs text-slate-500">
                    +{notices.length - 1} karne daha hazır
                  </Text>
                ) : null}
              </View>
            </View>
          </View>
        </View>
      ) : null}
      {opened ? (
        <ExamImportFlow
          visible
          onClose={() => setOpened(null)}
          jobId={opened.id}
          studentId={role === "teacher" ? opened.student_id : null}
        />
      ) : null}
    </>
  );
}
