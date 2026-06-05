import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BillingView } from "@/components/teacher/billing-view";
import {
  createStudentPayment,
  getTeacherBilling,
  setStudentRate,
  teacherBillingKeys,
  type PaymentCreateBody,
} from "@/lib/teacher";

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function TeacherBillingScreen() {
  const qc = useQueryClient();
  const [month, setMonth] = React.useState(currentMonth());

  const q = useQuery({
    queryKey: teacherBillingKeys.month(month),
    queryFn: () => getTeacherBilling(month),
  });

  function invalidate() {
    qc.invalidateQueries({ queryKey: teacherBillingKeys.month(month) });
  }

  const rateMut = useMutation({
    mutationFn: ({ id, fee }: { id: number; fee: number }) => setStudentRate(id, fee),
    onSuccess: invalidate,
  });
  const payMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: PaymentCreateBody }) => createStudentPayment(id, body),
    onSuccess: invalidate,
  });

  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <View className="px-5 pb-1 pt-3">
        <Text className="text-2xl font-extrabold text-slate-900">Tahsilat</Text>
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
      ) : (
        <ScrollView className="flex-1">
          <BillingView
            data={q.data}
            busy={rateMut.isPending || payMut.isPending}
            onPrev={() => setMonth((m) => shiftMonth(m, -1))}
            onNext={() => setMonth((m) => shiftMonth(m, 1))}
            onSetRate={(id, fee) => rateMut.mutate({ id, fee })}
            onPay={(id, body) => payMut.mutate({ id, body })}
          />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
