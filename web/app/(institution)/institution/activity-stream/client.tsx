"use client";

import { ActivityStreamPage } from "@/components/activity-stream";
import {
  institutionKeys,
  getInstitutionActivityStream,
} from "@/lib/api/institution";
import type { ActivityStreamResponse } from "@/lib/types/institution";

export function InstitutionActivityStreamClient({
  initial,
}: {
  initial: ActivityStreamResponse;
}) {
  return (
    <ActivityStreamPage
      title="Kurum Aktivite Akışı"
      description="Kurumunuzdaki tüm üyelik hareketleri: yeni öğretmen kayıtları, öğrenci oluşturmalar, öğretmenlerin yaptığı veli davetleri, kurum-koç davetleri, abonelik talepleri ve plan değişimleri tek akışta."
      queryKey={(days, type) => institutionKeys.activityStream(days, type)}
      queryFn={(days, type, limit) =>
        getInstitutionActivityStream(days, type, limit)
      }
      initial={initial}
      demoRole="institution_admin"
    />
  );
}
