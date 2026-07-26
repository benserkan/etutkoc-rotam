import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Image, Pressable, Text, View } from "react-native";
import { createAudioPlayer, setAudioModeAsync, type AudioPlayer } from "expo-audio";

import { API_BASE, ApiError, getAccessToken } from "@/lib/api";
import {
  type CommentaryKind,
  type ParentCommentaryResponse,
  generateParentCommentary,
  generateParentCommentaryVoice,
  getParentCommentary,
  parentCommentaryAudioPath,
  parentP2Keys,
} from "@/lib/parent";
import { RotaChat } from "@/components/parent/rota-chat";
import { cn } from "@/lib/utils";

/**
 * Rota'nın Yorumu (veli asistanı P1) — web kartının RN paritesi.
 * Program | Denemeler sekmeleri; bölümlü metin + sesli anlatım (expo-audio,
 * Authorization header'lı akış). Okuma/tekrar dinleme ücretsiz; üretim ve ilk
 * seslendirme koçun kredisinden (günlük limit backend'de).
 */

const AVATAR = `${API_BASE}/static/guide/rota-avatar.png`;

function errAlert(e: unknown) {
  const code = e instanceof ApiError ? e.code : null;
  if (code === "daily_limit_reached")
    Alert.alert("Bugünlük bu kadar", "Bugünlük yorum hakkın doldu — yarın yeniden deneyebilirsin.");
  else if (code === "ai_credit_exhausted")
    Alert.alert("Rota dinlenmede", "Koçun yapay zekâ kotası bu ay için doldu. Yorumlar yeni dönemde devam eder.");
  else if (code === "not_enough_data")
    Alert.alert("Henüz veri yok", "Program yayınlandıkça ve denemeler eklendikçe Rota burada anlatacak.");
  else if (code === "ai_unavailable")
    Alert.alert("Şu an kullanılamıyor", "Yapay zekâ servisi geçici olarak yanıt vermiyor, birkaç dakika sonra deneyin.");
  else if (code === "commentary_changed")
    Alert.alert("Yorum yenilendi", "Yorum bu sırada yenilendi — Dinle'ye tekrar basın.");
  else Alert.alert("Olmadı", e instanceof ApiError ? e.message : "Yorum oluşturulamadı, tekrar deneyin.");
}

export function RotaCommentaryCard({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [tab, setTab] = React.useState<CommentaryKind | "sohbet">("program");
  const kind: CommentaryKind = tab === "sohbet" ? "program" : tab;
  const [playing, setPlaying] = React.useState(false);
  const playerRef = React.useRef<AudioPlayer | null>(null);
  const playerBustRef = React.useRef<string | null>(null);

  const q = useQuery({
    queryKey: parentP2Keys.commentary(studentId, kind),
    queryFn: () => getParentCommentary(studentId, kind),
    enabled: studentId > 0 && tab !== "sohbet",
    staleTime: 30_000,
  });
  const data = q.data;
  const commentary = data?.commentary ?? null;

  const releasePlayer = React.useCallback(() => {
    const p = playerRef.current;
    if (p) {
      try {
        p.pause();
        p.remove();
      } catch {
        // yayınlanmış player zaten kaldırılmış olabilir
      }
    }
    playerRef.current = null;
    playerBustRef.current = null;
    setPlaying(false);
  }, []);

  // Sekme/yorum değişince çalan sesi bırak; unmount'ta temizle
  React.useEffect(() => releasePlayer, [releasePlayer]);
  React.useEffect(() => {
    releasePlayer();
  }, [tab, kind, commentary?.generated_at, releasePlayer]);

  // Oynatma durumu — basit nabız (bitince düğme başa dönsün)
  React.useEffect(() => {
    if (!playing) return;
    const iv = setInterval(() => {
      const p = playerRef.current;
      if (!p || !p.playing) setPlaying(false);
    }, 600);
    return () => clearInterval(iv);
  }, [playing]);

  async function playAudio() {
    const c = qc.getQueryData<ParentCommentaryResponse>(
      parentP2Keys.commentary(studentId, kind),
    )?.commentary;
    const bust = c?.generated_at ?? String(Date.now());
    if (!playerRef.current || playerBustRef.current !== bust) {
      releasePlayer();
      const token = await getAccessToken();
      await setAudioModeAsync({ playsInSilentMode: true }).catch(() => undefined);
      playerRef.current = createAudioPlayer({
        uri: `${API_BASE}${parentCommentaryAudioPath(studentId, kind, bust)}`,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      playerBustRef.current = bust;
    }
    playerRef.current?.play();
    setPlaying(true);
  }

  // Yanıt yeni yorumu içerir → cache doğrudan güncellenir
  const genMut = useMutation({
    mutationFn: () => generateParentCommentary(studentId, kind),
    onMutate: () => releasePlayer(),
    onSuccess: (res) => qc.setQueryData(parentP2Keys.commentary(studentId, kind), res),
    onError: (e) => {
      errAlert(e);
      void qc.invalidateQueries({ queryKey: parentP2Keys.commentary(studentId, kind) });
    },
  });

  const voiceMut = useMutation({
    mutationFn: () => generateParentCommentaryVoice(studentId, kind),
    onSuccess: (res) => {
      qc.setQueryData(
        parentP2Keys.commentary(studentId, kind),
        (prev: ParentCommentaryResponse | undefined) =>
          prev?.commentary
            ? {
                ...prev,
                commentary: {
                  ...prev.commentary,
                  has_audio: res.has_audio,
                  audio_content_type: res.audio_content_type,
                },
              }
            : prev,
      );
      void playAudio();
    },
    onError: (e) => {
      errAlert(e);
      void qc.invalidateQueries({ queryKey: parentP2Keys.commentary(studentId, kind) });
    },
  });

  function onListen() {
    if (playing) {
      playerRef.current?.pause();
      setPlaying(false);
      return;
    }
    if (commentary?.has_audio) void playAudio();
    else voiceMut.mutate();
  }

  return (
    <View className="rounded-2xl border border-cyan-200 bg-cyan-50/60 p-4">
      <View className="flex-row items-center gap-3">
        <View
          className={cn(
            "size-12 overflow-hidden rounded-full border-2",
            playing ? "border-cyan-500" : "border-cyan-200",
          )}
        >
          <Image source={{ uri: AVATAR }} className="size-full" resizeMode="cover" />
        </View>
        <View className="min-w-0 flex-1">
          <Text className="text-[15px] font-semibold text-cyan-950">Rota&apos;nın Yorumu</Text>
          <Text className="text-[11px] text-cyan-900/70">
            Çocuğunun durumunu sizin dilinizde — okuyun ya da dinleyin.
          </Text>
        </View>
      </View>

      <View className="mt-3 flex-row rounded-xl border border-cyan-200 bg-white p-0.5">
        {(
          [
            ["program", "Program"],
            ["deneme", "Denemeler"],
            ["sohbet", "Rota'ya Sor"],
          ] as const
        ).map(([k, label]) => (
          <Pressable
            key={k}
            onPress={() => setTab(k)}
            className={cn(
              "flex-1 items-center rounded-lg py-2",
              tab === k ? "bg-cyan-600" : "",
            )}
          >
            <Text
              className={cn(
                "text-xs font-semibold",
                tab === k ? "text-white" : "text-slate-600",
              )}
            >
              {label}
            </Text>
          </Pressable>
        ))}
      </View>

      <View className="mt-3">
        {tab === "sohbet" ? (
          <RotaChat studentId={studentId} onOpenCommentary={(k) => setTab(k)} />
        ) : q.isLoading ? (
          <ActivityIndicator color="#0891b2" />
        ) : data && !data.ai_available ? (
          <Text className="text-sm text-slate-600">
            {data.unavailable_reason ?? "Rota yorumu şu an kullanılamıyor."}
          </Text>
        ) : commentary ? (
          <View className="gap-3">
            {data?.is_stale ? (
              <View className="flex-row items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-2.5">
                <Ionicons name="time-outline" size={15} color="#b45309" style={{ marginTop: 1 }} />
                <Text className="flex-1 text-xs text-amber-800">
                  Bu yorumdan sonra yeni gelişmeler oldu — güncel anlatım için yenileyin.
                </Text>
              </View>
            ) : null}

            <View className="flex-row gap-2">
              <Pressable
                onPress={onListen}
                disabled={voiceMut.isPending}
                className={cn(
                  "flex-1 flex-row items-center justify-center gap-2 rounded-xl py-3",
                  voiceMut.isPending ? "bg-cyan-300" : "bg-cyan-600 active:bg-cyan-700",
                )}
              >
                {voiceMut.isPending ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Ionicons
                    name={playing ? "pause" : commentary.has_audio ? "play" : "volume-high"}
                    size={17}
                    color="#fff"
                  />
                )}
                <Text className="text-sm font-semibold text-white">
                  {voiceMut.isPending
                    ? "Rota hazırlanıyor…"
                    : playing
                      ? "Duraklat"
                      : commentary.has_audio
                        ? "Dinle"
                        : "Rota seslendirsin"}
                </Text>
              </Pressable>
              <Pressable
                onPress={() => genMut.mutate()}
                disabled={genMut.isPending}
                className="flex-row items-center justify-center gap-1.5 rounded-xl border border-cyan-300 px-3 active:bg-cyan-100"
              >
                {genMut.isPending ? (
                  <ActivityIndicator color="#0e7490" size="small" />
                ) : (
                  <Ionicons name="refresh" size={15} color="#0e7490" />
                )}
                <Text className="text-sm font-semibold text-cyan-800">Yenile</Text>
              </Pressable>
            </View>

            <View className="gap-2.5">
              {commentary.sections.map((s, i) => (
                <View key={i}>
                  <Text className="text-sm font-semibold text-cyan-950">{s.title}</Text>
                  <Text className="mt-0.5 text-sm leading-6 text-slate-800">{s.body}</Text>
                </View>
              ))}
            </View>
            <Text className="text-[10px] text-slate-400">
              Öneri amaçlıdır; kesin değerlendirme değildir. Sonucu yalnız siz görürsünüz.
            </Text>
          </View>
        ) : (
          <View className="gap-3">
            <Text className="text-sm text-slate-700">
              {kind === "program"
                ? "Rota, haftalık program ilerlemesini — neyin yapıldığını, neyin aksadığını, evde nasıl destek olabileceğinizi — sizin dilinizde anlatır."
                : "Rota, deneme sonuçlarını ve konu analizini grafiklere boğulmadan anlamanız için derleyip anlatır."}
            </Text>
            <Pressable
              onPress={() => genMut.mutate()}
              disabled={genMut.isPending}
              className={cn(
                "flex-row items-center justify-center gap-2 rounded-xl py-3.5",
                genMut.isPending ? "bg-cyan-300" : "bg-cyan-600 active:bg-cyan-700",
              )}
            >
              {genMut.isPending ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <Ionicons name="sparkles" size={17} color="#fff" />
              )}
              <Text className="text-base font-semibold text-white">
                {genMut.isPending ? "Rota hazırlıyor…" : "Rota yorumlasın"}
              </Text>
            </Pressable>
          </View>
        )}
      </View>
    </View>
  );
}
