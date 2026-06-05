import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { TodayView } from "@/components/student/today-view";
import { TaskSheet, type ItemUpdate } from "@/components/student/task-sheet";
import { ApiError } from "@/lib/api";
import {
  completeTask,
  getStudentDay,
  setItemCompleted,
  studentKeys,
  uncompleteTask,
  type StudentTask,
} from "@/lib/student";

/**
 * Bir günün (date verilmezse bugün) görev ekranı — TodayView + TaskSheet +
 * tamamlama akışı. Bugün sekmesi ve Hafta'dan açılan gün detayı paylaşır.
 */
export function DayScreen({ date, safeTop = true }: { date?: string; safeTop?: boolean }) {
  const qc = useQueryClient();
  const dayQ = useQuery({ queryKey: studentKeys.day(date), queryFn: () => getStudentDay(date) });

  const [openTask, setOpenTask] = React.useState<StudentTask | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [sheetError, setSheetError] = React.useState<string | null>(null);
  const [quickBusyId, setQuickBusyId] = React.useState<number | null>(null);

  // Tamamlama gün + hafta özetini etkiler → tüm "student" sorgularını tazele.
  const refreshAll = () => qc.invalidateQueries({ queryKey: ["student"] });

  async function quickToggle(task: StudentTask) {
    setQuickBusyId(task.id);
    try {
      const done =
        task.status === "completed" ||
        (task.planned_count > 0 && task.completed_count >= task.planned_count);
      await (done ? uncompleteTask(task.id) : completeTask(task.id));
      await refreshAll();
    } catch {
      // sessiz geç — sonra toast eklenecek
    } finally {
      setQuickBusyId(null);
    }
  }

  async function runAction(fn: () => Promise<unknown>) {
    setBusy(true);
    setSheetError(null);
    try {
      await fn();
      await refreshAll();
      setOpenTask(null);
    } catch (e) {
      setSheetError(e instanceof ApiError ? e.message : "Kaydedilemedi. Bağlantını kontrol et.");
    } finally {
      setBusy(false);
    }
  }

  function closeSheet() {
    setOpenTask(null);
    setSheetError(null);
  }

  if (dayQ.isLoading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }

  if (dayQ.isError || !dayQ.data) {
    return (
      <View className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">
          Program yüklenemedi
        </Text>
        <Text className="text-center text-sm text-slate-500">İnternet bağlantını kontrol et.</Text>
        <Pressable
          onPress={() => dayQ.refetch()}
          className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
        >
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <>
      <TodayView
        day={dayQ.data}
        busyTaskId={quickBusyId}
        onQuickToggle={quickToggle}
        onOpenTask={setOpenTask}
        refreshing={dayQ.isRefetching}
        onRefresh={() => dayQ.refetch()}
        safeTop={safeTop}
      />
      {openTask ? (
        <TaskSheet
          key={openTask.id}
          task={openTask}
          busy={busy}
          error={sheetError}
          onClose={closeSheet}
          onSaveItems={(updates: ItemUpdate[]) =>
            runAction(async () => {
              for (const u of updates) {
                await setItemCompleted(openTask.id, u.itemId, {
                  completed: u.completed,
                  correct: u.correct,
                  wrong: u.wrong,
                });
              }
            })
          }
          onCompleteActivity={(solved) =>
            runAction(() =>
              completeTask(openTask.id, solved != null ? { solved_count: solved } : undefined),
            )
          }
          onUncomplete={() => runAction(() => uncompleteTask(openTask.id))}
        />
      ) : null}
    </>
  );
}
