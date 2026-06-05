import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { AddTaskSheet } from "@/components/teacher/add-task-sheet";
import { TeacherWeekView } from "@/components/teacher/week-view";
import {
  createTeacherTask,
  deleteTeacherTask,
  getTeacherStudentBooks,
  getTeacherStudentWeek,
  teacherMiscKeys,
  type TaskCreateBody,
} from "@/lib/teacher";

export function ProgramTab({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [start, setStart] = React.useState<string | undefined>(undefined);
  const [addDate, setAddDate] = React.useState<string | null>(null);

  const weekQ = useQuery({
    queryKey: teacherMiscKeys.week(studentId, start),
    queryFn: () => getTeacherStudentWeek(studentId, start),
    enabled: studentId > 0,
  });

  // Kitaplar yalnız ekleme sayfası açılınca yüklenir.
  const booksQ = useQuery({
    queryKey: teacherMiscKeys.studentBooks(studentId),
    queryFn: () => getTeacherStudentBooks(studentId),
    enabled: addDate != null,
  });

  function invalidateWeek() {
    qc.invalidateQueries({ queryKey: ["teacher", "student", studentId, "week"] });
  }

  const addMut = useMutation({
    mutationFn: (body: TaskCreateBody) => createTeacherTask(studentId, body),
    onSuccess: () => { invalidateWeek(); setAddDate(null); },
  });
  const delMut = useMutation({
    mutationFn: (taskId: number) => deleteTeacherTask(taskId),
    onSuccess: invalidateWeek,
  });

  function shiftToPrev() { setStart(weekQ.data?.prev_start); }
  function shiftToNext() { setStart(weekQ.data?.next_start); }

  if (weekQ.isLoading) {
    return (
      <View className="items-center justify-center py-16">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  if (weekQ.isError || !weekQ.data) {
    return (
      <View className="items-center gap-3 py-16 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">Program yüklenemedi</Text>
        <Pressable onPress={() => weekQ.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View className="flex-1">
      <TeacherWeekView
        week={weekQ.data}
        onPrev={shiftToPrev}
        onNext={shiftToNext}
        onThisWeek={() => setStart(undefined)}
        onAddTask={(date) => setAddDate(date)}
        onDeleteTask={(id) => delMut.mutate(id)}
        refreshing={weekQ.isRefetching}
        onRefresh={() => weekQ.refetch()}
      />
      <AddTaskSheet
        visible={addDate != null}
        date={addDate}
        books={booksQ.data?.items ?? []}
        booksLoading={booksQ.isLoading}
        busy={addMut.isPending}
        onClose={() => setAddDate(null)}
        onSubmit={(body) => addMut.mutate(body)}
      />
    </View>
  );
}
