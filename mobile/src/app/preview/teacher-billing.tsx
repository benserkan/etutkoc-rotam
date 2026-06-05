import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BillingView } from "@/components/teacher/billing-view";
import type { BillingMonthResponse } from "@/lib/teacher";

/** UX önizleme — Koç: tahsilat (mock). Faz 7'de kaldırılacak. */
const MOCK: BillingMonthResponse = {
  month: "2026-06",
  totals: { accrued: 16000, paid: 9000, balance: 7000 },
  rows: [
    { student_id: 1, student_name: "Yiğit Demir", session_fee: 2000, done_sessions: 4, accrued: 8000, paid: 8000, balance: 0, status: "paid" },
    { student_id: 2, student_name: "Elif Yıldız", session_fee: 2500, done_sessions: 3, accrued: 7500, paid: 1000, balance: 6500, status: "partial" },
    { student_id: 3, student_name: "Ada Kaya", session_fee: 2000, done_sessions: 0, accrued: 0, paid: 0, balance: 0, status: "pending" },
    { student_id: 4, student_name: "Mert Aslan", session_fee: null, done_sessions: 2, accrued: null, paid: 0, balance: null, status: "no_rate" },
  ],
};

export default function TeacherBillingPreview() {
  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <ScrollView className="flex-1">
        <View className="flex-1">
          <BillingView data={MOCK} busy={false} onPrev={() => {}} onNext={() => {}} onSetRate={() => {}} onPay={() => {}} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
