import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { Badge, Banner, InstitutionScreen, Section } from "@/components/institution/ui";
import { ApiError } from "@/lib/api";
import {
  enableInstitutionGuarantee,
  getInstitutionSubscription,
  institutionKeys,
  pauseInstitutionForSummer,
  requestInstitutionUpgrade,
  resumeInstitutionFromPause,
  switchInstitutionAcademicYear,
  type InstitutionPlanOption,
  type SubscriptionResponse,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function date(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR");
}

export default function InstitutionSubscriptionScreen() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: institutionKeys.subscription, queryFn: getInstitutionSubscription });
  const [open, setOpen] = React.useState(false);
  const [plan, setPlan] = React.useState<InstitutionPlanOption | null>(null);
  const [note, setNote] = React.useState("");

  const mut = useMutation({
    mutationFn: () => requestInstitutionUpgrade({ plan: plan?.code, note: note.trim() || undefined }),
    onSuccess: (res) => {
      setOpen(false);
      qc.invalidateQueries({ queryKey: institutionKeys.subscription });
      Alert.alert(res.data.already_pending ? "Zaten bekliyor" : "Talebin alındı", res.data.message);
    },
    onError: (e) => Alert.alert("Gönderilemedi", e instanceof ApiError ? e.message : "İşlem başarısız"),
  });

  // P4e — abonelik aksiyonları (akademik yıl / yaz duraklat-devam / garanti)
  const action = useMutation({
    mutationFn: (fn: () => Promise<unknown>) => fn(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: institutionKeys.subscription });
      Alert.alert("Tamam", "İşlem uygulandı.");
    },
    onError: (e) => Alert.alert("Yapılamadı", e instanceof ApiError ? e.message : "İşlem başarısız"),
  });
  function confirmAction(title: string, msg: string, fn: () => Promise<unknown>) {
    Alert.alert(title, msg, [
      { text: "Vazgeç", style: "cancel" },
      { text: "Onayla", onPress: () => action.mutate(fn) },
    ]);
  }

  return (
    <InstitutionScreen<SubscriptionResponse> title="Hesap Ayarları" query={q}>
      {(d) => {
        const s = d.status;
        return (
          <>
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

            {/* Abonelik işlemleri (yenileme/duraklatma) — backend can_* flag'lerine göre */}
            {(s.can_switch_to_academic_year || s.can_pause || s.can_resume || !s.performance_guarantee) ? (
              <Section title="Abonelik işlemleri">
                {s.can_switch_to_academic_year ? (
                  <Pressable disabled={action.isPending} onPress={() => confirmAction("Akademik yıla geç", "Aboneliğin akademik yıl planına geçirilsin mi?", switchInstitutionAcademicYear)}
                    className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-3 active:bg-brand-100">
                    <Text className="text-sm font-semibold text-brand-700">Akademik yıla geç</Text>
                    <Text className="text-[11px] text-brand-700/80">Tüm öğretim yılını kapsayan plan</Text>
                  </Pressable>
                ) : null}
                {s.can_pause ? (
                  <Pressable disabled={action.isPending} onPress={() => confirmAction("Yaz duraklatması", "Aboneliğin yaz penceresinde duraklatılsın mı?", pauseInstitutionForSummer)}
                    className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 active:bg-amber-100">
                    <Text className="text-sm font-semibold text-amber-800">Yaz için duraklat</Text>
                    <Text className="text-[11px] text-amber-700">Yaz döneminde faturalama durur</Text>
                  </Pressable>
                ) : null}
                {s.can_resume ? (
                  <Pressable disabled={action.isPending} onPress={() => confirmAction("Devam ettir", "Aboneliğin tekrar aktive edilsin mi?", resumeInstitutionFromPause)}
                    className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 active:bg-emerald-100">
                    <Text className="text-sm font-semibold text-emerald-800">Aboneliği devam ettir</Text>
                    <Text className="text-[11px] text-emerald-700">Duraklatmadan geri dön</Text>
                  </Pressable>
                ) : null}
                {!s.performance_guarantee ? (
                  <Pressable disabled={action.isPending} onPress={() => confirmAction("Performans garantisi", "60 gün performans garantisi etkinleştirilsin mi?", enableInstitutionGuarantee)}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-3 active:bg-slate-50">
                    <Text className="text-sm font-semibold text-slate-800">Performans garantisini aç</Text>
                    <Text className="text-[11px] text-slate-500">60 gün içinde hedefe ulaşılmazsa süre uzatılır</Text>
                  </Pressable>
                ) : null}
              </Section>
            ) : null}

            {d.pending_upgrade_request ? (
              <Banner kind="warn">
                Bekleyen yükseltme talebin var{d.requested_plan_label ? ` (${d.requested_plan_label})` : ""}. Ekibimiz iletişime geçecek.
              </Banner>
            ) : (
              <Pressable onPress={() => { setPlan(d.available_plans[0] ?? null); setNote(""); setOpen(true); }} className="flex-row items-center justify-center gap-2 rounded-xl bg-brand-700 py-3.5 active:bg-brand-800">
                <Text className="text-base font-semibold text-white">Planı yükselt (talep)</Text>
              </Pressable>
            )}

            <Banner kind="info">
              Bu bir satın alma değil, yükseltme talebidir. Talep süper admine iletilir, ekibimiz ödeme/aktivasyon için seninle iletişime geçer.
            </Banner>

            <FormSheet visible={open} title="Plan yükseltme talebi" onClose={() => setOpen(false)}>
              <View className="gap-4 pb-2">
                <Section title="Kademe seç">
                  {d.available_plans.map((p) => {
                    const active = p.code === plan?.code;
                    return (
                      <Pressable key={p.code} onPress={() => setPlan(p)} className={cn("rounded-xl border p-3", active ? "border-brand-600 bg-brand-50" : "border-slate-200 bg-white")}>
                        <Text className={cn("text-sm font-semibold", active ? "text-brand-700" : "text-slate-800")}>{p.label}</Text>
                        {p.coach_range || p.description ? <Text className="text-[11px] text-slate-500">{p.coach_range ?? p.description}</Text> : null}
                      </Pressable>
                    );
                  })}
                </Section>
                <View className="gap-1">
                  <Text className="text-xs font-medium text-slate-600">Not (opsiyonel)</Text>
                  <TextInput value={note} onChangeText={setNote} placeholder="Eklemek istediğin not…" placeholderTextColor="#94a3b8" multiline className="min-h-16 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
                </View>
                <Pressable onPress={() => mut.mutate()} disabled={mut.isPending || !plan} className={cn("items-center rounded-xl py-3.5", mut.isPending || !plan ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}>
                  <Text className="text-base font-semibold text-white">{mut.isPending ? "Gönderiliyor…" : "Talebi gönder"}</Text>
                </Pressable>
              </View>
            </FormSheet>
          </>
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
