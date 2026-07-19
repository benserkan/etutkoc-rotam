import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { InviteStudentSheet } from "@/components/teacher/invite-student-sheet";
import { StudentsListView } from "@/components/teacher/students-list-view";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  createTeacherStudent,
  getTeacherStudents,
  getTeacherTrialStatus,
  teacherKeys,
  type StudentCreateBody,
  type StudentCreateResult,
  type TrialStatusResponse,
} from "@/lib/teacher";
import { showCoachUpgradeAlert } from "@/lib/upsell";

/** Deneme geri sayımı / ödeme duvarı bandı — dokununca Paketim (IAP). */
function TrialBanner({ ts }: { ts: TrialStatusResponse }) {
  if (!ts.is_solo) return null;
  if (ts.paywall || ts.past_due) {
    return (
      <Pressable
        onPress={() => router.push("/teacher-plan")}
        className="mx-4 mt-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 active:bg-rose-100"
      >
        <Text className="text-sm font-semibold text-rose-800">
          {ts.past_due ? "Aboneliğin yenilenmedi" : "Deneme bitti — erişim kısıtlı"}
        </Text>
        <Text className="mt-0.5 text-xs text-rose-700">
          Kesintisiz devam etmek için paketini seç → dokun
        </Text>
      </Pressable>
    );
  }
  if (ts.trial_active && ts.trial_critical) {
    return (
      <Pressable
        onPress={() => router.push("/teacher-plan")}
        className="mx-4 mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 active:bg-amber-100"
      >
        <Text className="text-sm font-semibold text-amber-900">
          Denemenin bitmesine {ts.days_left ?? 0} gün kaldı
        </Text>
        <Text className="mt-0.5 text-xs text-amber-800">
          Paketini şimdi seç, kaldığın yerden devam et → dokun
        </Text>
      </Pressable>
    );
  }
  return null;
}

export default function TeacherStudentsScreen() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const q = useQuery({ queryKey: teacherKeys.students(), queryFn: () => getTeacherStudents() });
  const trialQ = useQuery({
    queryKey: ["teacher", "trial-status"],
    queryFn: getTeacherTrialStatus,
    enabled: user?.institution_id == null,
    staleTime: 5 * 60_000,
  });

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
    onError: (e) => {
      const code = e instanceof ApiError ? e.code : null;
      // Paket öğrenci limiti doldu → Paketim (IAP) yönlendirmesi.
      if (code === "plan_quota_exceeded" || code === "paywall_active") {
        setError(
          code === "paywall_active"
            ? "Deneme bitti / abonelik yenilenmedi — yeni öğrenci için paketini yükselt."
            : "Paketinin öğrenci limiti doldu — daha yüksek pakete geçerek ekleyebilirsin.",
        );
        showCoachUpgradeAlert(
          "Öğrenci limiti",
          code === "paywall_active"
            ? "Deneme bitti veya aboneliğin yenilenmedi. Paketini seçtiğinde kaldığın yerden devam edersin."
            : "Bu paketin öğrenci limiti doldu. Daha yüksek pakete geçerek yeni öğrenci ekleyebilirsin.",
        );
        return;
      }
      setError(e instanceof ApiError ? e.message : "Oluşturulamadı");
    },
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
      {trialQ.data ? <TrialBanner ts={trialQ.data} /> : null}
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
