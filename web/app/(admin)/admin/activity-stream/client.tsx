"use client";

import { ActivityStreamPage } from "@/components/activity-stream";
import { adminKeys, getAdminActivityStream } from "@/lib/api/admin";
import type { ActivityStreamResponse } from "@/lib/types/institution";

export function AdminActivityStreamClient({
  initial,
}: {
  initial: ActivityStreamResponse;
}) {
  return (
    <ActivityStreamPage
      title="Üyelik & Aktivite Akışı"
      description="Sistem genelinde tüm yeni kayıtlar, davetler, abonelik talepleri ve paket satın almaları tek bir kronolojik akışta. Ticari öneme sahip olaylar (paket alımı / talepleri) yeşil ile öne çıkar."
      queryKey={(days, type) => adminKeys.activityStream(days, type)}
      queryFn={(days, type, limit) => getAdminActivityStream(days, type, limit)}
      initial={initial}
    />
  );
}
