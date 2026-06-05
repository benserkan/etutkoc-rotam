import { SafeAreaView } from "react-native-safe-area-context";

import { PlanView } from "@/components/teacher/plan-view";
import type { TeacherPlanResponse } from "@/lib/teacher";

const MOCK: TeacherPlanResponse = {
  plan_code: "solo_trial", plan_label: "Solo Başlangıç — 14 gün deneme", is_solo: true,
  ai_premium: true, trial_active: true, trial_days_left: 9,
  options: [
    { code: "solo_pro", label: "Solo Başlangıç", max_students: 10, price_monthly_try: 2500, is_recommended: true },
    { code: "solo_elite", label: "Solo", max_students: 25, price_monthly_try: 5000 },
    { code: "solo_unlimited", label: "Solo Sınırsız", max_students: null, price_monthly_try: 7500 },
  ],
  note: null, status: "trialing", student_count: 6, solo_monthly_price: 2500,
  recommended_plan: "solo_pro", annual_paid_months: 10, sales_email: "satis@etutkoc.com",
  subscription_status: null, subscription_period_end: null, subscription_cycle: null,
  post_trial_plan: "solo_pro", post_trial_plan_label: "Solo Başlangıç", post_trial_plan_credits: 1500,
  ai_credits_used: 18, ai_credits_allocated: 50,
};

export default function TeacherPlanPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <PlanView data={MOCK} busy={false} onUpgrade={() => {}} />
    </SafeAreaView>
  );
}
