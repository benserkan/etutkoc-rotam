import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CurriculumTab } from "@/components/teacher/curriculum-tab";
import { ExamsTab } from "@/components/teacher/exams-tab";
import { ProgramTab } from "@/components/teacher/program-tab";
import { SessionsTab } from "@/components/teacher/sessions-tab";
import { StudentDetailView } from "@/components/teacher/student-detail-view";
import { WaSendDialog } from "@/components/messaging/wa-send-dialog";
import { ApiError } from "@/lib/api";
import {
  deactivateTeacherStudent,
  getTeacherStudent,
  reactivateTeacherStudent,
  teacherKeys,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

type Tab = "genel" | "program" | "mufredat" | "denemeler" | "seanslar";
const TABS: { key: Tab; label: string }[] = [
  { key: "genel", label: "Genel" },
  { key: "program", label: "Program" },
  { key: "mufredat", label: "Müfredat" },
  { key: "denemeler", label: "Denemeler" },
  { key: "seanslar", label: "Seanslar" },
];

export default function TeacherStudentRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const studentId = id ? Number(id) : 0;
  const [tab, setTab] = React.useState<Tab>("genel");
  const [waOpen, setWaOpen] = React.useState(false);
  const [toggling, setToggling] = React.useState(false);
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: teacherKeys.student(studentId),
    queryFn: () => getTeacherStudent(studentId),
    enabled: studentId > 0,
  });

  function toggleActive() {
    const active = q.data?.student.is_active ?? true;
    Alert.alert(
      active ? "Öğrenciyi pasife al" : "Öğrenciyi aktif et",
      active
        ? "Öğrenci pasife alınır (kotadan düşer). Veriler silinmez; istediğinde tekrar aktif edebilirsin."
        : "Öğrenci tekrar aktif öğrenci olur.",
      [
        { text: "Vazgeç", style: "cancel" },
        {
          text: active ? "Pasife al" : "Aktif et",
          style: active ? "destructive" : "default",
          onPress: async () => {
            setToggling(true);
            try {
              if (active) await deactivateTeacherStudent(studentId);
              else await reactivateTeacherStudent(studentId);
              await qc.invalidateQueries({ queryKey: teacherKeys.student(studentId) });
              await qc.invalidateQueries({ queryKey: ["teacher", "students"] });
            } catch (e) {
              const err = e as ApiError;
              Alert.alert("İşlem başarısız", err?.message ?? "Bir hata oluştu.");
            } finally {
              setToggling(false);
            }
          },
        },
      ],
    );
  }

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          className="size-10 items-center justify-center rounded-full active:bg-slate-200"
          accessibilityLabel="Geri"
        >
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800" numberOfLines={1}>
          {q.data?.student.full_name ?? "Öğrenci"}
        </Text>
      </View>

      {/* Sekmeler */}
      <View className="flex-row gap-1 border-b border-slate-200 px-3">
        {TABS.map((t) => {
          const active = t.key === tab;
          return (
            <Pressable key={t.key} onPress={() => setTab(t.key)} className="flex-1 items-center py-2.5">
              <Text
                numberOfLines={1}
                adjustsFontSizeToFit
                className={cn("text-[13px] font-semibold", active ? "text-brand-700" : "text-slate-400")}
              >
                {t.label}
              </Text>
              <View className={cn("mt-2 h-0.5 w-full rounded-full", active ? "bg-brand-600" : "bg-transparent")} />
            </Pressable>
          );
        })}
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : tab === "genel" ? (
        <StudentDetailView
          data={q.data}
          onOpenDev={() => router.push({ pathname: "/teacher-student-dev", params: { id: String(studentId) } })}
          onOpenTopics={() => router.push({ pathname: "/topic-performance", params: { source: "teacher", id: String(studentId) } })}
          onSendWa={() => setWaOpen(true)}
          onToggleActive={toggleActive}
          togglingActive={toggling}
        />
      ) : tab === "program" ? (
        <ProgramTab studentId={studentId} />
      ) : tab === "mufredat" ? (
        <CurriculumTab studentId={studentId} />
      ) : tab === "denemeler" ? (
        <ScrollView className="flex-1 bg-slate-50">
          <ExamsTab studentId={studentId} />
        </ScrollView>
      ) : (
        <ScrollView className="flex-1 bg-slate-50">
          <SessionsTab studentId={studentId} />
        </ScrollView>
      )}

      <WaSendDialog
        visible={waOpen}
        onClose={() => setWaOpen(false)}
        targetUserId={studentId}
        targetLabel={q.data?.student.full_name}
        defaultCategory="ogrenci"
      />
    </SafeAreaView>
  );
}
