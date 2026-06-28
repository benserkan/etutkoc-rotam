import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";
import {
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
} from "expo-audio";
import { File } from "expo-file-system";

import { ApiError } from "@/lib/api";
import { transcribeSession } from "@/lib/teacher";
import { cn } from "@/lib/utils";

function mmss(ms: number): string {
  const s = Math.floor(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/**
 * Sesli dikte düğmesi — bir form alanının yanına konur.
 * Dokun → kaydet → tekrar dokun → durdur → metne çevir → onText(metin).
 * Ses SAKLANMAZ; ücretli paket + rıza + kredi gerekir (backend kapısı).
 */
export function DictateButton({
  studentId,
  ensureConsent,
  onText,
}: {
  studentId: number;
  ensureConsent: () => Promise<boolean>;
  onText: (text: string) => void;
}) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const state = useAudioRecorderState(recorder, 250);
  const [busy, setBusy] = React.useState(false);

  async function start() {
    const ok = await ensureConsent();
    if (!ok) return;
    const perm = await AudioModule.requestRecordingPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Mikrofon izni gerekli", "Sesli dikte için mikrofona izin ver (telefon ayarlarından da açabilirsin).");
      return;
    }
    try {
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch {
      Alert.alert("Kayıt başlatılamadı", "Lütfen tekrar dene.");
    }
  }

  async function stop() {
    try {
      await recorder.stop();
    } catch {
      /* yoksay */
    }
    const uri = recorder.uri ?? state.url;
    if (!uri) {
      Alert.alert("Kayıt alınamadı", "Lütfen tekrar dene.");
      return;
    }
    setBusy(true);
    try {
      const b64 = await new File(uri).base64();
      const res = await transcribeSession(studentId, { audio_base64: b64, media_type: "audio/mp4" });
      const text = (res.text || "").trim();
      if (text) onText(text);
      else Alert.alert("Anlaşılamadı", "Ses metne çevrilemedi, daha net konuşup tekrar dene.");
    } catch (e) {
      const code = e instanceof ApiError ? e.code : null;
      if (code === "plan_upgrade_required") Alert.alert("Premium özellik", "Sesli dikte premium pakette açıktır.");
      else if (code === "ai_credit_exhausted") Alert.alert("Kredi bitti", "Bu ay yapay zekâ kredin doldu.");
      else if (code === "consent_required") Alert.alert("Onay gerekli", "Sesli dikte için önce açık rıza vermelisin.");
      else if (code === "voice_unreadable") Alert.alert("Anlaşılamadı", "Ses metne çevrilemedi, daha net konuşup tekrar dene.");
      else if (code === "ai_unavailable") Alert.alert("Yapay zekâ kullanılamıyor", "Lütfen birkaç dakika sonra tekrar dene.");
      else Alert.alert("Çevrilemedi", e instanceof ApiError ? e.message : "İşlem başarısız.");
    } finally {
      setBusy(false);
    }
  }

  if (busy) {
    return (
      <View className="h-9 flex-row items-center gap-1.5 rounded-full bg-brand-50 px-3">
        <ActivityIndicator size="small" color="#0e7490" />
        <Text className="text-xs font-medium text-brand-700">Çevriliyor…</Text>
      </View>
    );
  }

  if (state.isRecording) {
    return (
      <Pressable
        onPress={stop}
        hitSlop={6}
        className="h-9 flex-row items-center gap-1.5 rounded-full bg-rose-100 px-3 active:bg-rose-200"
      >
        <Ionicons name="stop" size={15} color="#e11d48" />
        <Text className="text-xs font-semibold text-rose-700">Durdur · {mmss(state.durationMillis)}</Text>
      </Pressable>
    );
  }

  return (
    <Pressable
      onPress={start}
      hitSlop={6}
      className="h-9 flex-row items-center gap-1.5 rounded-full bg-brand-50 px-3 active:bg-brand-100"
    >
      <Ionicons name="mic" size={15} color="#0e7490" />
      <Text className="text-xs font-semibold text-brand-700">Dikte</Text>
    </Pressable>
  );
}
