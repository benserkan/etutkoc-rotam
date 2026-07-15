import * as React from "react";
import { router } from "expo-router";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import * as ImagePicker from "expo-image-picker";

import { ApiError } from "@/lib/api";
import {
  aiTagWrongQuestion,
  attemptWrongQuestion,
  createWrongQuestion,
  deleteWrongQuestion,
  getWrongQuestions,
  updateWrongQuestion,
  wrongKeys,
  type PhotoAsset,
  type WrongListResponse,
  type WrongQuestion,
} from "@/lib/wrong-questions";
import { AuthImage } from "@/components/student/auth-image";
import { FormSheet } from "@/components/ui/form-sheet";
import { cn } from "@/lib/utils";

const RATE: { rating: 1 | 2 | 3 | 4; label: string; cls: string }[] = [
  { rating: 1, label: "Yine yanlış", cls: "bg-rose-600" },
  { rating: 2, label: "Zor çözdüm", cls: "bg-amber-600" },
  { rating: 3, label: "Çözdüm", cls: "bg-emerald-600" },
  { rating: 4, label: "Kolayca", cls: "bg-cyan-700" },
];

function aiErr(e: unknown): string {
  const code = e instanceof ApiError ? e.code : null;
  const map: Record<string, string> = {
    no_coach: "Yapay zekâ için bağlı bir koç gerekir.",
    no_photo: "Etiketleme için sorunun fotoğrafı gerekir.",
    photo_unreadable: "Fotoğraf okunamadı — daha net bir kare deneyin.",
    plan_upgrade_required: "Yapay zekâ koçunun ücretli paketinde kullanılabilir.",
    consent_required: "Koç henüz yapay zekâ onayını vermemiş.",
    ai_credit_exhausted: "Koçun yapay zekâ kredisi bu ay için doldu.",
    ai_unavailable: "Yapay zekâ servisi şu an kullanılamıyor — birazdan deneyin.",
  };
  return (code && map[code]) || (e instanceof ApiError ? e.message : "İşlem başarısız.");
}

export default function StudentWrongQuestionsScreen() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: wrongKeys.list, queryFn: getWrongQuestions });
  const [captureOpen, setCaptureOpen] = React.useState(false);
  const [detailId, setDetailId] = React.useState<number | null>(null);
  const [resolveOpen, setResolveOpen] = React.useState(false);

  const data = q.data;
  const invalidate = () => void qc.invalidateQueries({ queryKey: wrongKeys.list });

  const detail = detailId != null ? data?.items.find((i) => i.id === detailId) ?? null : null;
  const openItems = (data?.items ?? []).filter((i) => i.status === "acik");
  const dueItems = (data?.items ?? []).filter((i) => i.is_due);
  const practiceQueue = dueItems.length > 0 ? dueItems : openItems;

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-2 px-4 pb-2 pt-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="p-1">
          <Ionicons name="chevron-back" size={24} color="#0f172a" />
        </Pressable>
        <Text className="text-xl font-extrabold text-slate-900">Yanlışlarım</Text>
        <Pressable
          onPress={() => setCaptureOpen(true)}
          className="ml-auto flex-row items-center gap-1 rounded-full bg-brand-700 px-3 py-1.5 active:bg-brand-800"
        >
          <Ionicons name="camera" size={16} color="#fff" />
          <Text className="text-sm font-semibold text-white">Ekle</Text>
        </Pressable>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : !data ? (
        <ErrorState onRetry={() => q.refetch()} />
      ) : (
        <ScrollView
          className="flex-1"
          contentContainerClassName="px-4 pb-8 gap-3"
        >
          <Text className="text-xs text-slate-500">
            Yanlış yaptığın soruyu fotoğrafla arşive at. Sistem doğru zamanda
            yeniden sorar; aralıklı iki doğru çözüm soruyu kapatır.
          </Text>

          {/* Yeniden çözme / alıştırma bandı */}
          {practiceQueue.length > 0 ? (
            <Pressable
              onPress={() => setResolveOpen(true)}
              className={cn(
                "flex-row items-center gap-3 rounded-2xl border px-4 py-3 active:opacity-90",
                dueItems.length > 0
                  ? "border-amber-200 bg-amber-50"
                  : "border-cyan-200 bg-cyan-50",
              )}
            >
              <Ionicons
                name="refresh-circle"
                size={26}
                color={dueItems.length > 0 ? "#b45309" : "#0e7490"}
              />
              <View className="flex-1">
                <Text
                  className={cn(
                    "text-[15px] font-bold",
                    dueItems.length > 0 ? "text-amber-900" : "text-cyan-900",
                  )}
                >
                  {dueItems.length > 0
                    ? `Yeniden çözme: ${dueItems.length} soru`
                    : `Alıştırma: ${openItems.length} açık soru`}
                </Text>
                <Text
                  className={cn(
                    "text-xs",
                    dueItems.length > 0 ? "text-amber-800" : "text-cyan-800",
                  )}
                >
                  {dueItems.length > 0
                    ? "Kapatmak için yeniden çöz."
                    : "Vadeleri gelmedi ama şimdi de deneyebilirsin."}
                </Text>
              </View>
              <Ionicons
                name="chevron-forward"
                size={18}
                color={dueItems.length > 0 ? "#b45309" : "#0e7490"}
              />
            </Pressable>
          ) : null}

          {/* Sayaçlar */}
          <View className="flex-row gap-2">
            <Counter label="Açık" value={data.counts.open} tone="amber" />
            <Counter label="Kapanan" value={data.counts.closed} tone="emerald" />
            <Counter label="Toplam" value={data.counts.total} tone="slate" />
          </View>

          {/* Liste */}
          {data.items.length === 0 ? (
            <View className="items-center gap-3 rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-10">
              <Ionicons name="images-outline" size={34} color="#cbd5e1" />
              <Text className="text-center text-sm text-slate-500">
                Henüz arşivde soru yok. İlk yanlışını fotoğrafla ekle — gerisini
                sistem takip eder.
              </Text>
              <Pressable
                onPress={() => setCaptureOpen(true)}
                className="flex-row items-center gap-1.5 rounded-xl bg-brand-700 px-4 py-2.5 active:bg-brand-800"
              >
                <Ionicons name="camera" size={16} color="#fff" />
                <Text className="font-semibold text-white">İlk yanlışını ekle</Text>
              </Pressable>
            </View>
          ) : (
            data.items.map((it) => (
              <WrongCard key={it.id} item={it} onOpen={() => setDetailId(it.id)} />
            ))
          )}
        </ScrollView>
      )}

      {captureOpen ? (
        <CaptureSheet
          onClose={() => setCaptureOpen(false)}
          errorLabels={data?.error_type_labels ?? {}}
          onSaved={invalidate}
        />
      ) : null}
      {detail ? (
        <DetailSheet
          item={detail}
          errorLabels={data?.error_type_labels ?? {}}
          onClose={() => setDetailId(null)}
          onChanged={invalidate}
        />
      ) : null}
      {resolveOpen ? (
        <ResolveSheet
          queue={practiceQueue}
          onClose={() => {
            setResolveOpen(false);
            invalidate();
          }}
        />
      ) : null}
    </SafeAreaView>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <View className="flex-1 items-center justify-center gap-3 px-8">
      <Text className="text-center text-base font-semibold text-slate-700">
        Yüklenemedi
      </Text>
      <Pressable
        onPress={onRetry}
        className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
      >
        <Text className="font-semibold text-white">Tekrar dene</Text>
      </Pressable>
    </View>
  );
}

function Counter({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "amber" | "emerald" | "slate";
}) {
  const t = {
    amber: "text-amber-700",
    emerald: "text-emerald-700",
    slate: "text-slate-900",
  }[tone];
  return (
    <View className="flex-1 items-center rounded-2xl border border-slate-200 bg-white py-3">
      <Text className={cn("text-2xl font-extrabold", t)}>{value}</Text>
      <Text className="text-[11px] text-slate-500">{label}</Text>
    </View>
  );
}

function WrongCard({ item, onOpen }: { item: WrongQuestion; onOpen: () => void }) {
  const qImg = item.images.find((im) => im.kind === "question");
  const closed = item.status === "kapandi";
  return (
    <Pressable
      onPress={onOpen}
      className={cn(
        "overflow-hidden rounded-2xl border bg-white active:opacity-90",
        closed ? "border-emerald-200" : item.is_due ? "border-amber-300" : "border-slate-200",
      )}
    >
      <View className="h-36 w-full">
        {qImg ? (
          <AuthImage wqId={item.id} imageId={qImg.id} className="h-full w-full" contentFit="cover" />
        ) : (
          <View className="h-full w-full items-center justify-center bg-slate-100">
            <Ionicons name="image-outline" size={30} color="#cbd5e1" />
          </View>
        )}
        {closed ? (
          <View className="absolute left-2 top-2 rounded-full bg-emerald-600 px-2 py-0.5">
            <Text className="text-[10px] font-bold text-white">KAPANDI</Text>
          </View>
        ) : item.is_due ? (
          <View className="absolute left-2 top-2 rounded-full bg-amber-500 px-2 py-0.5">
            <Text className="text-[10px] font-bold text-white">YENİDEN ÇÖZ</Text>
          </View>
        ) : null}
      </View>
      <View className="gap-1 p-3">
        <Text className="text-[15px] font-semibold text-slate-900" numberOfLines={1}>
          {item.topic_name ?? item.section_label ?? item.subject_name ?? "Etiketsiz soru"}
        </Text>
        <Text className="text-xs text-slate-500" numberOfLines={1}>
          {[item.subject_name, item.book_name].filter(Boolean).join(" · ") || "—"}
        </Text>
        <View className="mt-1 flex-row items-center gap-2">
          {item.error_type_label ? (
            <View className="rounded bg-rose-50 px-1.5 py-0.5">
              <Text className="text-[10px] font-medium text-rose-700">
                {item.error_type_label}
              </Text>
            </View>
          ) : null}
          {item.ai_hint ? (
            <Ionicons name="sparkles" size={13} color="#7c3aed" />
          ) : null}
          {!closed ? (
            <View className="ml-auto flex-row gap-1">
              {[0, 1].map((i) => (
                <View
                  key={i}
                  className={cn(
                    "size-2 rounded-full",
                    i < item.correct_streak ? "bg-emerald-500" : "bg-slate-300",
                  )}
                />
              ))}
            </View>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

// ---------------------------------------------------------------------------
// Fotoğraf seçici (kamera / galeri)
// ---------------------------------------------------------------------------

async function pickPhoto(source: "camera" | "library"): Promise<PhotoAsset | null> {
  if (source === "camera") {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert(
        "Kamera izni gerekli",
        "Soru fotoğrafı çekmek için kameraya izin ver (telefon ayarlarından da açabilirsin).",
      );
      return null;
    }
    const r = await ImagePicker.launchCameraAsync({ quality: 0.6, mediaTypes: "images" });
    if (r.canceled || !r.assets?.[0]) return null;
    return { uri: r.assets[0].uri, mimeType: r.assets[0].mimeType, fileName: r.assets[0].fileName };
  }
  const r = await ImagePicker.launchImageLibraryAsync({ quality: 0.6, mediaTypes: "images" });
  if (r.canceled || !r.assets?.[0]) return null;
  return { uri: r.assets[0].uri, mimeType: r.assets[0].mimeType, fileName: r.assets[0].fileName };
}

function CaptureSheet({
  onClose,
  errorLabels,
  onSaved,
}: {
  onClose: () => void;
  errorLabels: Record<string, string>;
  onSaved: () => void;
}) {
  const [photo, setPhoto] = React.useState<PhotoAsset | null>(null);
  const [errorType, setErrorType] = React.useState<string>("");
  const [note, setNote] = React.useState("");
  const create = useMutation({
    mutationFn: () =>
      createWrongQuestion(
        { source_kind: "diger", error_type: errorType || undefined, note: note.trim() || undefined },
        photo ? [photo] : [],
      ),
    onSuccess: () => {
      onSaved();
      onClose();
      Alert.alert(
        "Arşive eklendi",
        "Hemen yeniden çözebilirsin; kapanması için aradan zaman geçmiş iki doğru çözüm gerekir.",
      );
    },
    onError: (e) =>
      Alert.alert("Eklenemedi", e instanceof ApiError ? e.message : "İşlem başarısız."),
  });

  const canSave = !!photo || note.trim().length > 0;

  return (
    <FormSheet visible title="Yanlış soru ekle" onClose={create.isPending ? () => {} : onClose}>
      <View className="gap-4">
        {photo ? (
          <View className="overflow-hidden rounded-xl border border-slate-200">
            <Image
              source={{ uri: photo.uri }}
              style={{ width: "100%", height: 200, backgroundColor: "#f1f5f9" }}
              contentFit="contain"
            />
            <Pressable
              onPress={() => setPhoto(null)}
              className="absolute right-2 top-2 rounded-full bg-black/60 p-1"
            >
              <Ionicons name="close" size={16} color="#fff" />
            </Pressable>
          </View>
        ) : (
          <View className="flex-row gap-2">
            <Pressable
              onPress={async () => setPhoto((await pickPhoto("camera")) ?? null)}
              className="flex-1 items-center gap-1 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 py-6 active:bg-slate-100"
            >
              <Ionicons name="camera" size={26} color="#0e7490" />
              <Text className="text-xs font-semibold text-slate-600">Fotoğraf çek</Text>
            </Pressable>
            <Pressable
              onPress={async () => setPhoto((await pickPhoto("library")) ?? null)}
              className="flex-1 items-center gap-1 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 py-6 active:bg-slate-100"
            >
              <Ionicons name="images" size={26} color="#0e7490" />
              <Text className="text-xs font-semibold text-slate-600">Galeriden seç</Text>
            </Pressable>
          </View>
        )}

        <View>
          <Text className="mb-1.5 text-xs font-medium text-slate-600">
            Neden yanlış yaptın?
          </Text>
          <View className="flex-row flex-wrap gap-1.5">
            {Object.entries(errorLabels).map(([k, v]) => (
              <Pressable
                key={k}
                onPress={() => setErrorType(errorType === k ? "" : k)}
                className={cn(
                  "rounded-full border px-3 py-1.5",
                  errorType === k
                    ? "border-rose-500 bg-rose-500"
                    : "border-slate-300 bg-white",
                )}
              >
                <Text
                  className={cn(
                    "text-xs font-medium",
                    errorType === k ? "text-white" : "text-slate-600",
                  )}
                >
                  {v}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        <TextInput
          value={note}
          onChangeText={setNote}
          placeholder="Not (istersen): neyi karıştırdın…"
          placeholderTextColor="#94a3b8"
          multiline
          className="min-h-16 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
        />

        <Pressable
          onPress={() => create.mutate()}
          disabled={!canSave || create.isPending}
          className={cn(
            "flex-row items-center justify-center gap-2 rounded-xl py-3.5",
            !canSave || create.isPending ? "bg-slate-300" : "bg-brand-700 active:bg-brand-800",
          )}
        >
          {create.isPending ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Ionicons name="add" size={18} color="#fff" />
          )}
          <Text className="font-semibold text-white">Arşive ekle</Text>
        </Pressable>
      </View>
    </FormSheet>
  );
}

// ---------------------------------------------------------------------------
// Detay
// ---------------------------------------------------------------------------

function DetailSheet({
  item,
  errorLabels,
  onClose,
  onChanged,
}: {
  item: WrongQuestion;
  errorLabels: Record<string, string>;
  onClose: () => void;
  onChanged: () => void;
}) {
  const closed = item.status === "kapandi";
  const qImgs = item.images.filter((im) => im.kind === "question");
  const sImgs = item.images.filter((im) => im.kind === "solution");

  const attempt = useMutation({
    mutationFn: (r: 1 | 2 | 3 | 4) => attemptWrongQuestion(item.id, r),
    onSuccess: (res) => {
      onChanged();
      if (res.data.status === "kapandi") Alert.alert("Soru kapandı! 🎉", "Aralıklı iki doğru çözüm.");
    },
    onError: (e) => Alert.alert("Kaydedilemedi", e instanceof ApiError ? e.message : "Hata."),
  });
  const aiTag = useMutation({
    mutationFn: () => aiTagWrongQuestion(item.id),
    onSuccess: () => onChanged(),
    onError: (e) => Alert.alert("Etiketleme yapılamadı", aiErr(e)),
  });
  const setErr = useMutation({
    mutationFn: (k: string) => updateWrongQuestion(item.id, { error_type: k }),
    onSuccess: () => onChanged(),
    onError: (e) => Alert.alert("Güncellenemedi", e instanceof ApiError ? e.message : "Hata."),
  });
  const del = useMutation({
    mutationFn: () => deleteWrongQuestion(item.id),
    onSuccess: () => {
      onChanged();
      onClose();
    },
    onError: (e) => Alert.alert("Silinemedi", e instanceof ApiError ? e.message : "Hata."),
  });

  return (
    <FormSheet
      visible
      title={item.topic_name ?? item.section_label ?? "Yanlış soru"}
      onClose={onClose}
    >
      <ScrollView className="max-h-[70vh]" contentContainerClassName="gap-3">
        <View
          className={cn(
            "rounded-xl px-3 py-2",
            closed ? "bg-emerald-50" : "bg-amber-50",
          )}
        >
          <Text className={cn("text-xs", closed ? "text-emerald-900" : "text-amber-900")}>
            {closed
              ? `Kapandı — ${item.attempts_count} denemede.`
              : item.is_due
                ? "Yeniden çözme zamanı geldi."
                : `Açık · doğru serisi ${item.correct_streak}/2.`}
          </Text>
        </View>

        {qImgs.map((im) => (
          <AuthImage
            key={im.id}
            wqId={item.id}
            imageId={im.id}
            className="h-64 w-full rounded-xl"
          />
        ))}

        {/* AI etiketleme / ipucu */}
        {qImgs.length > 0 && !item.ai_hint && !item.ai_tagged_at ? (
          <Pressable
            onPress={() => aiTag.mutate()}
            disabled={aiTag.isPending}
            className="flex-row items-center justify-center gap-2 rounded-xl border border-violet-300 bg-violet-50 py-3 active:bg-violet-100"
          >
            {aiTag.isPending ? (
              <ActivityIndicator size="small" color="#7c3aed" />
            ) : (
              <Ionicons name="sparkles" size={16} color="#7c3aed" />
            )}
            <Text className="text-sm font-semibold text-violet-800">
              Yapay zekâ okusun — konu + yaklaşım ipucu
            </Text>
          </Pressable>
        ) : null}
        {item.ai_hint ? (
          <View className="rounded-xl border border-violet-200 bg-violet-50 px-3 py-2">
            <View className="flex-row items-center gap-1.5">
              <Ionicons name="sparkles" size={13} color="#7c3aed" />
              <Text className="text-[11px] font-bold uppercase text-violet-800">
                Yaklaşım ipucu
              </Text>
              {item.difficulty_guess ? (
                <Text className="ml-auto rounded bg-violet-200 px-1.5 py-0.5 text-[10px] text-violet-900">
                  {item.difficulty_guess}
                </Text>
              ) : null}
            </View>
            <Text className="mt-1 text-sm text-violet-950">{item.ai_hint}</Text>
            <Text className="mt-1 text-[10px] text-violet-700">
              Yapay zekâ çözümü vermez — yolu gösterir. Çözümü sen bul.
            </Text>
          </View>
        ) : null}

        {item.coach_note ? (
          <View className="rounded-xl border border-cyan-200 bg-cyan-50 px-3 py-2">
            <Text className="text-[11px] font-bold uppercase text-cyan-800">
              Koçunun açıklaması
            </Text>
            <Text className="mt-0.5 text-sm text-cyan-950">{item.coach_note}</Text>
          </View>
        ) : null}

        {sImgs.map((im) => (
          <AuthImage
            key={im.id}
            wqId={item.id}
            imageId={im.id}
            className="h-52 w-full rounded-xl"
          />
        ))}

        {/* Yeniden çöz (açık soruda her zaman) */}
        {!closed ? (
          <View className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <Text className="mb-2 text-xs font-medium text-slate-700">
              Yeniden çöz, sonra sonucu işaretle
              {!item.is_due ? " (vadesi gelmedi ama deneyebilirsin)" : ""}:
            </Text>
            <View className="flex-row gap-2">
              {RATE.map((o) => (
                <Pressable
                  key={o.rating}
                  onPress={() => attempt.mutate(o.rating)}
                  disabled={attempt.isPending}
                  className={cn("flex-1 items-center rounded-lg py-2.5", o.cls)}
                >
                  <Text className="text-[11px] font-semibold text-white">{o.label}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : null}

        {/* Hata türü */}
        <View>
          <Text className="mb-1.5 text-[11px] font-bold uppercase text-slate-500">
            Hata türü
          </Text>
          <View className="flex-row flex-wrap gap-1.5">
            {Object.entries(errorLabels).map(([k, v]) => (
              <Pressable
                key={k}
                onPress={() => setErr.mutate(k)}
                className={cn(
                  "rounded-full border px-3 py-1.5",
                  item.error_type === k
                    ? "border-rose-500 bg-rose-500"
                    : "border-slate-300 bg-white",
                )}
              >
                <Text
                  className={cn(
                    "text-xs font-medium",
                    item.error_type === k ? "text-white" : "text-slate-600",
                  )}
                >
                  {v}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {item.note ? (
          <Text className="text-sm text-slate-600">
            <Text className="font-semibold text-slate-900">Notun: </Text>
            {item.note}
          </Text>
        ) : null}

        <View className="flex-row items-center justify-between border-t border-slate-200 pt-3">
          <Text className="text-[11px] text-slate-400">yalnız sen ve koçun görür</Text>
          <Pressable
            onPress={() =>
              Alert.alert("Sil", "Bu soru arşivden silinsin mi?", [
                { text: "Vazgeç", style: "cancel" },
                { text: "Sil", style: "destructive", onPress: () => del.mutate() },
              ])
            }
            className="flex-row items-center gap-1 rounded-lg border border-rose-200 px-3 py-1.5 active:bg-rose-50"
          >
            <Ionicons name="trash-outline" size={14} color="#e11d48" />
            <Text className="text-xs font-medium text-rose-600">Sil</Text>
          </Pressable>
        </View>
      </ScrollView>
    </FormSheet>
  );
}

// ---------------------------------------------------------------------------
// Yeniden çözme turu
// ---------------------------------------------------------------------------

function ResolveSheet({
  queue,
  onClose,
}: {
  queue: WrongQuestion[];
  onClose: () => void;
}) {
  const [frozen] = React.useState<WrongQuestion[]>(() => queue);
  const [idx, setIdx] = React.useState(0);
  const [reveal, setReveal] = React.useState(false);
  const [tally, setTally] = React.useState({ solved: 0, wrong: 0, closed: 0 });
  const [done, setDone] = React.useState(false);
  const current = frozen[idx];

  const attempt = useMutation({
    mutationFn: (r: 1 | 2 | 3 | 4) => attemptWrongQuestion(current!.id, r),
    onError: (e) => Alert.alert("Kaydedilemedi", e instanceof ApiError ? e.message : "Hata."),
  });

  function advance() {
    setReveal(false);
    if (idx + 1 >= frozen.length) setDone(true);
    else setIdx(idx + 1);
  }

  function rate(r: 1 | 2 | 3 | 4) {
    if (!current) return;
    attempt.mutate(r, {
      onSuccess: (res) => {
        setTally((t) => ({
          solved: t.solved + (r >= 3 ? 1 : 0),
          wrong: t.wrong + (r === 1 ? 1 : 0),
          closed: t.closed + (res.data.status === "kapandi" ? 1 : 0),
        }));
        advance();
      },
    });
  }

  const hasHint = current && (current.ai_hint || current.coach_note || current.images.some((i) => i.kind === "solution"));

  return (
    <FormSheet
      visible
      title={done || !current ? "Tur bitti" : `Yeniden çözme · ${idx + 1}/${frozen.length}`}
      onClose={onClose}
    >
      {done || !current ? (
        <View className="items-center gap-4 py-4">
          <Ionicons name="checkmark-circle" size={44} color="#10b981" />
          <View className="flex-row gap-3">
            <TurStat label="çözdün" value={tally.solved} tone="emerald" />
            <TurStat label="yine yanlış" value={tally.wrong} tone="rose" />
            <TurStat label="kapandı" value={tally.closed} tone="cyan" />
          </View>
          <Text className="px-4 text-center text-xs text-slate-500">
            {tally.closed > 0
              ? "Kapanan sorular arşivde 'Kapanan'da. Diğerleri zamanı gelince yine karşına gelecek."
              : "Sistem bu soruları daha sık karşına getirecek."}
          </Text>
          <Pressable onPress={onClose} className="rounded-xl bg-brand-700 px-6 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tamam</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView className="max-h-[72vh]" contentContainerClassName="gap-3">
          <Text className="text-sm text-slate-500">
            {[current.subject_name, current.topic_name ?? current.section_label]
              .filter(Boolean)
              .join(" · ") || "Etiketsiz soru"}
          </Text>
          {current.images
            .filter((im) => im.kind === "question")
            .map((im) => (
              <AuthImage key={im.id} wqId={current.id} imageId={im.id} className="h-72 w-full rounded-xl" />
            ))}
          {current.images.filter((im) => im.kind === "question").length === 0 ? (
            <View className="rounded-xl border border-dashed border-slate-300 px-4 py-6">
              <Text className="text-center text-sm text-slate-500">
                Fotoğraf yok — {current.note ? `notun: "${current.note}"` : "kaynağından bulup çöz"}.
              </Text>
            </View>
          ) : null}

          {hasHint ? (
            !reveal ? (
              <Pressable
                onPress={() => setReveal(true)}
                className="flex-row items-center justify-center gap-1.5 rounded-xl border border-slate-300 py-2.5 active:bg-slate-50"
              >
                <Ionicons name="eye-outline" size={16} color="#334155" />
                <Text className="text-sm font-medium text-slate-700">
                  Takıldım — ipucu/çözümü göster
                </Text>
              </Pressable>
            ) : (
              <View className="gap-2">
                {current.ai_hint ? (
                  <View className="rounded-xl border border-violet-200 bg-violet-50 px-3 py-2">
                    <Text className="text-sm text-violet-950">
                      <Text className="font-bold">İpucu: </Text>
                      {current.ai_hint}
                    </Text>
                  </View>
                ) : null}
                {current.coach_note ? (
                  <View className="rounded-xl border border-cyan-200 bg-cyan-50 px-3 py-2">
                    <Text className="text-sm text-cyan-950">
                      <Text className="font-bold">Koçun: </Text>
                      {current.coach_note}
                    </Text>
                  </View>
                ) : null}
                {current.images
                  .filter((im) => im.kind === "solution")
                  .map((im) => (
                    <AuthImage key={im.id} wqId={current.id} imageId={im.id} className="h-52 w-full rounded-xl" />
                  ))}
              </View>
            )
          ) : null}

          <View className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <Text className="mb-2 text-xs font-medium text-slate-700">
              Önce KENDİN çöz, sonra işaretle:
            </Text>
            <View className="flex-row gap-2">
              {RATE.map((o) => (
                <Pressable
                  key={o.rating}
                  onPress={() => rate(o.rating)}
                  disabled={attempt.isPending}
                  className={cn("flex-1 items-center rounded-lg py-2.5", o.cls)}
                >
                  <Text className="text-[11px] font-semibold text-white">{o.label}</Text>
                </Pressable>
              ))}
            </View>
            <Pressable onPress={advance} className="mt-2 self-start">
              <Text className="text-xs text-slate-500 underline">Şimdilik atla →</Text>
            </Pressable>
          </View>
        </ScrollView>
      )}
    </FormSheet>
  );
}

function TurStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "emerald" | "rose" | "cyan";
}) {
  const t = {
    emerald: "text-emerald-700",
    rose: "text-rose-700",
    cyan: "text-cyan-700",
  }[tone];
  return (
    <View className="items-center rounded-xl border border-slate-200 bg-white px-3 py-2">
      <Text className={cn("text-xl font-extrabold", t)}>{value}</Text>
      <Text className="text-[10px] text-slate-500">{label}</Text>
    </View>
  );
}
