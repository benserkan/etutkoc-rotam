import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { InviteStudentSheet } from "@/components/teacher/invite-student-sheet";
import { StudentsListView } from "@/components/teacher/students-list-view";
import { ApiError } from "@/lib/api";
import {
  createTeacherStudent,
  getTeacherStudents,
  teacherKeys,
  type StudentCreateBody,
  type StudentCreateResult,
} from "@/lib/teacher";

export default function TeacherStudentsScreen() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: teacherKeys.students(), queryFn: () => getTeacherStudents() });

  const [inviteOpen, setInviteOpen] = React.useState(false);
  const [result, setResult] = React.useState<StudentCreateResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const inviteMut = useMutation({
    mutationFn: (body: StudentCreateBody) => createTeacherStudent(body),
    onMutate: () => setError(null),
    onSuccess: (res) => {
      setResult(res.data);
      qc.invalidateQueries({ queryKey: ["teacher", "students"] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "Oluşturulamadı"),
  });

  function openInvite() {
    setResult(null);
    setError(null);
    setInviteOpen(true);
  }

  if (q.isLoading) {
    return (
      <View className="flex-1 items-center justify-center bg-slate-50">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  if (q.isError || !q.data) {
    return (
      <View className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">Öğrenciler yüklenemedi</Text>
        <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }
  return (
    <>
      <StudentsListView
        items={q.data.items}
        onOpenStudent={(id) => router.push({ pathname: "/teacher-student", params: { id: String(id) } })}
        onInvite={openInvite}
        refreshing={q.isRefetching}
        onRefresh={() => q.refetch()}
      />
      <InviteStudentSheet
        visible={inviteOpen}
        busy={inviteMut.isPending}
        error={error}
        result={result}
        onClose={() => setInviteOpen(false)}
        onSubmit={(body) => inviteMut.mutate(body)}
      />
    </>
  );
}
