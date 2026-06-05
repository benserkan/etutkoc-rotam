import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ActionCenterView } from "@/components/institution/action-center-view";
import type { ActionCenterResponse } from "@/lib/institution";

/** UX önizleme — Kurum: müdahale merkezi (mock). Faz 7'de kaldırılacak. */
const MOCK: ActionCenterResponse = {
  institution: { id: 1, name: "ETÜTKOÇ", is_active: true },
  summary: { critical: 2, warn: 3, info: 1, total: 6 },
  items: [
    {
      severity: "critical", category: "low_compliance", title: "Can Demir'in sınıfında uyum çok düşük",
      description: "Son 7 günde görev tamamlama %30. Öğrenciler programı uygulamıyor.",
      teacher_name: "Can Demir", count: 20, suggestion: "Koçla görüşüp program yükünü ve takibi gözden geçir.",
    },
    {
      severity: "critical", category: "empty_program", title: "3 öğrencinin programı boş",
      description: "Bu hafta hiç görev atanmamış 3 öğrenci var.",
      teacher_name: "Elif Yıldız", count: 3, suggestion: "Koça programları tamamlamasını hatırlat.",
    },
    {
      severity: "warn", category: "at_risk", title: "9 öğrenci risk altında",
      description: "2 kritik, 7 dikkat seviyesinde öğrenci var.",
      teacher_name: null, count: 9, suggestion: "Risk panelinden öğrencileri inceleyip koçlara ilet.",
    },
  ],
};

export default function InstitutionActionCenterPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-1">
        <ActionCenterView data={MOCK} />
      </View>
    </SafeAreaView>
  );
}
