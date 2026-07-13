import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { Badge, InstitutionScreen } from "@/components/institution/ui";
import {
  getInstitutionSubscription,
  institutionKeys,
  type SubscriptionResponse,
} from "@/lib/institution";

function date(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR");
}

// NOT (Apple App Store yönergesi 3.1.1 — 2026-06-30 reddi): mobil uygulamada
// paket yükseltme talebi, abonelik/plan değişikliği aksiyonları ve "ödeme
// uygulama dışında düzenlenir" tarzı metinler GÖSTERİLMEZ (uygulama-dışı ödemeye
// yönlendirme sayılıyor). Bu ekran YALNIZ mevcut paket durumunu gösterir; tüm
// abonelik işlemleri (yükseltme talebi / akademik yıl / duraklat / garanti)
// web panelinde durur.
export default function InstitutionSubscriptionScreen() {
  const q = useQuery({ queryKey: institutionKeys.subscription, queryFn: getInstitutionSubscription });

  return (
    <InstitutionScreen<SubscriptionResponse> title="Hesap Ayarları" query={q} demoContext="membership">
      {(d) => {
        const s = d.status;
        return (
          <View className="rounded-2xl border border-slate-200 bg-white p-4">
            <View className="flex-row items-center justify-between">
              <Text className="text-xs font-medium text-slate-400">Mevcut paket</Text>
              <Badge label={s.kind_label} tone="sky" />
            </View>
            <Text className="mt-1 text-xl font-extrabold text-slate-900">{d.plan_label}</Text>
            <View className="mt-2 gap-1">
              <Row label="Dönem sonu" value={date(s.period_end)} />
              {s.days_until_period_end != null ? <Row label="Kalan gün" value={`${s.days_until_period_end} gün`} /> : null}
              {s.pause_until ? <Row label="Duraklatma" value={date(s.pause_until)} /> : null}
              <Row label="Performans garantisi" value={s.performance_guarantee ? "Aktif" : "—"} />
            </View>
          </View>
        );
      }}
    </InstitutionScreen>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-row items-center justify-between">
      <Text className="text-xs text-slate-500">{label}</Text>
      <Text className="text-sm font-medium text-slate-800">{value}</Text>
    </View>
  );
}
