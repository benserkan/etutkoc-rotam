import { SafeAreaView } from "react-native-safe-area-context";

import { InstitutionDashboardView } from "@/components/institution/dashboard-view";
import type { InstitutionDashboardResponse } from "@/lib/institution";

/** UX önizleme — Kurum: panel (mock). Faz 7'de kaldırılacak. */
const MOCK: InstitutionDashboardResponse = {
  institution: { id: 1, name: "ETÜTKOÇ Etüt Merkezi", is_active: true },
  aggregate: {
    teacher_count: 6, active_teacher_count: 5, student_count: 84,
    weekly_planned: 1240, weekly_completed: 812, weekly_rate_pct: 65,
  },
  risk: { at_risk_count: 9, at_risk_critical: 2 },
  inactive: { inactive_teacher_count: 1, inactive_teacher_names: ["Murat T."] },
  teacher_summaries: [
    { id: 1, full_name: "Ayşe Koç", email: "a@e.com", is_active: true, is_paused: false, pause_reason: null, student_count: 18, weekly_planned: 320, weekly_completed: 288, weekly_rate_pct: 90, last_login_days: 0 },
    { id: 2, full_name: "Elif Yıldız", email: "e@e.com", is_active: true, is_paused: false, pause_reason: null, student_count: 15, weekly_planned: 280, weekly_completed: 154, weekly_rate_pct: 55, last_login_days: 1 },
    { id: 3, full_name: "Can Demir", email: "c@e.com", is_active: true, is_paused: false, pause_reason: null, student_count: 20, weekly_planned: 360, weekly_completed: 108, weekly_rate_pct: 30, last_login_days: 4 },
    { id: 4, full_name: "Murat Tan", email: "m@e.com", is_active: true, is_paused: false, pause_reason: null, student_count: 12, weekly_planned: 0, weekly_completed: 0, weekly_rate_pct: null, last_login_days: 12 },
  ],
};

export default function InstitutionDashboardPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <InstitutionDashboardView data={MOCK} />
    </SafeAreaView>
  );
}
