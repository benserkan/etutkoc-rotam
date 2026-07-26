import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ActivityIndicator,
  Alert,
  Image,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  AudioModule,
  createAudioPlayer,
  RecordingPresets,
  setAudioModeAsync,
  useAudioRecorder,
  useAudioRecorderState,
  type AudioPlayer,
} from "expo-audio";
import { File } from "expo-file-system";

import { API_BASE, ApiError, getAccessToken } from "@/lib/api";
import {
  type ChatMessage,
  type CommentaryKind,
  type ParentChatResponse,
  askParentChat,
  getParentChat,
  parentChatAudioPath,
  parentChatKeys,
  parentChatMessageVoice,
  transcribeParentChat,
} from "@/lib/parent";
import { cn } from "@/lib/utils";

/**
 * Rota'ya Sor (P2+P3) — RN sohbeti (Rota kartının sekmesi).
 *
 * P2: kredisiz karşılama + çipler; soru 3 kredi (günde 10). P3: sesli soru
 * (mikrofon → metin, kutuya dolar — otomatik GÖNDERİLMEZ) + Rota cevaplarında
 * "Dinle" (ilk dinlemede üretilir + saklanır; tekrar kredisiz). Ses kaydı
 * SAKLANMAZ.
 */

const AVATAR = `${API_BASE}/static/guide/rota-avatar.png`;

function errAlert(e: unknown) {
  const code = e instanceof ApiError ? e.code : null;
  if (code === "daily_limit_reached")
    Alert.alert("Bugünlük bu kadar", e instanceof ApiError ? e.message : "Günlük hak doldu.");
  else if (code === "ai_credit_exhausted")
    Alert.alert("Rota dinlenmede", "Koçun yapay zekâ kotası bu ay için doldu.");
  else if (code === "ai_unavailable")
    Alert.alert("Şu an kullanılamıyor", "Yapay zekâ servisi geçici olarak yanıt vermiyor.");
  else if (code === "voice_unreadable")
    Alert.alert("Anlaşılamadı", "Ses metne çevrilemedi — daha net konuşup tekrar dener misin?");
  else Alert.alert("Olmadı", e instanceof ApiError ? e.message : "İşlem başarısız, tekrar deneyin.");
}

function RotaBubble({
  body,
  thinking,
  listenState,
  onListen,
}: {
  body: string;
  thinking?: boolean;
  /** undefined = dinleme yok (karşılama) · idle | pending | playing */
  listenState?: "idle" | "pending" | "playing";
  onListen?: () => void;
}) {
  return (
    <View className="flex-row items-start gap-2">
      <View className="size-7 overflow-hidden rounded-full border border-cyan-200">
        <Image source={{ uri: AVATAR }} className="size-full" resizeMode="cover" />
      </View>
      <View className="max-w-[85%] rounded-2xl rounded-tl-sm border border-cyan-200 bg-white px-3 py-2">
        {thinking ? (
          <View className="flex-row items-center gap-1.5">
            <ActivityIndicator size="small" color="#0891b2" />
            <Text className="text-sm text-slate-500">Rota düşünüyor…</Text>
          </View>
        ) : (
          <>
            <Text className="text-sm leading-5 text-slate-800">{body}</Text>
            {listenState && onListen ? (
              <Pressable
                onPress={onListen}
                disabled={listenState === "pending"}
                className="mt-1.5 flex-row items-center gap-1 self-start"
                hitSlop={8}
              >
                {listenState === "pending" ? (
                  <>
                    <ActivityIndicator size="small" color="#0e7490" />
                    <Text className="text-[11px] font-medium text-cyan-700">
                      Ses hazırlanıyor…
                    </Text>
                  </>
                ) : (
                  <>
                    <Ionicons
                      name={listenState === "playing" ? "pause" : "volume-medium"}
                      size={13}
                      color="#0e7490"
                    />
                    <Text className="text-[11px] font-medium text-cyan-700">
                      {listenState === "playing" ? "Duraklat" : "Dinle"}
                    </Text>
                  </>
                )}
              </Pressable>
            ) : null}
          </>
        )}
      </View>
    </View>
  );
}

export function RotaChat({
  studentId,
  onOpenCommentary,
}: {
  studentId: number;
  onOpenCommentary: (kind: CommentaryKind) => void;
}) {
  const qc = useQueryClient();
  const [text, setText] = React.useState("");

  // --- P3: kayıt (sesli soru) — dikte deseni ---
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recState = useAudioRecorderState(recorder, 250);
  const [transcribing, setTranscribing] = React.useState(false);

  // --- P3: dinleme (cevap balonu sesi) ---
  const playerRef = React.useRef<AudioPlayer | null>(null);
  const playerMsgRef = React.useRef<number | null>(null);
  const [playingId, setPlayingId] = React.useState<number | null>(null);
  const [voicePendingId, setVoicePendingId] = React.useState<number | null>(null);

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
    playerMsgRef.current = null;
    setPlayingId(null);
  }, []);
  React.useEffect(() => releasePlayer, [releasePlayer]);

  // Oynatma nabzı — ses bitince düğme başa dönsün
  React.useEffect(() => {
    if (playingId === null) return;
    const iv = setInterval(() => {
      const p = playerRef.current;
      if (!p || !p.playing) setPlayingId(null);
    }, 600);
    return () => clearInterval(iv);
  }, [playingId]);

  const q = useQuery({
    queryKey: parentChatKeys.thread(studentId),
    queryFn: () => getParentChat(studentId),
    enabled: studentId > 0,
    staleTime: 15_000,
  });
  const data = q.data;

  // Yanıt yeni mesajları içerir → cache doğrudan güncellenir
  const askMut = useMutation({
    mutationFn: (message: string) => askParentChat(studentId, message),
    onSuccess: (res) => {
      qc.setQueryData(
        parentChatKeys.thread(studentId),
        (prev: ParentChatResponse | undefined) =>
          prev
            ? {
                ...prev,
                messages: [...prev.messages, ...res.messages],
                daily_left: res.daily_left,
              }
            : prev,
      );
      setText("");
    },
    onError: (e) => {
      errAlert(e);
      const inv = () =>
        void qc.invalidateQueries({ queryKey: parentChatKeys.thread(studentId) });
      inv();
      setTimeout(inv, 8000);
      setTimeout(inv, 20000);
    },
  });

  function send(message: string) {
    const m = message.trim();
    if (m.length < 2 || askMut.isPending) return;
    askMut.mutate(m);
  }

  async function startRecording() {
    const perm = await AudioModule.requestRecordingPermissionsAsync();
    if (!perm.granted) {
      Alert.alert(
        "Mikrofon izni gerekli",
        "Sesli soru için mikrofona izin ver (telefon ayarlarından da açabilirsin).",
      );
      return;
    }
    try {
      releasePlayer();
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
    } catch {
      Alert.alert("Kayıt başlatılamadı", "Lütfen tekrar dene.");
    }
  }

  async function stopRecording() {
    try {
      await recorder.stop();
    } catch {
      // yoksay
    }
    const uri = recorder.uri ?? recState.url;
    if (!uri) {
      Alert.alert("Kayıt alınamadı", "Lütfen tekrar dene.");
      return;
    }
    setTranscribing(true);
    try {
      const b64 = await new File(uri).base64();
      const res = await transcribeParentChat(studentId, b64, "audio/mp4");
      const t = (res.text || "").trim();
      if (t) setText((prev) => (prev ? `${prev} ${t}` : t));
      else
        Alert.alert("Anlaşılamadı", "Ses metne çevrilemedi — daha net konuşup tekrar dene.");
    } catch (e) {
      errAlert(e);
    } finally {
      setTranscribing(false);
    }
  }

  async function toggleListen(m: ChatMessage) {
    if (playingId === m.id) {
      playerRef.current?.pause();
      setPlayingId(null);
      return;
    }
    setVoicePendingId(m.id);
    try {
      // İlk dinlemede üretir (kredi); ses hazırsa sunucu ücretsiz döner
      await parentChatMessageVoice(studentId, m.id);
      if (!playerRef.current || playerMsgRef.current !== m.id) {
        releasePlayer();
        const token = await getAccessToken();
        await setAudioModeAsync({ playsInSilentMode: true }).catch(() => undefined);
        playerRef.current = createAudioPlayer({
          uri: `${API_BASE}${parentChatAudioPath(studentId, m.id)}`,
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        playerMsgRef.current = m.id;
      }
      playerRef.current?.play();
      setPlayingId(m.id);
      qc.setQueryData(
        parentChatKeys.thread(studentId),
        (prev: ParentChatResponse | undefined) =>
          prev
            ? {
                ...prev,
                messages: prev.messages.map((x) =>
                  x.id === m.id ? { ...x, has_audio: true } : x,
                ),
              }
            : prev,
      );
    } catch (e) {
      errAlert(e);
    } finally {
      setVoicePendingId(null);
    }
  }

  if (q.isLoading) return <ActivityIndicator color="#0891b2" />;
  if (data && !data.ai_available) {
    return (
      <Text className="text-sm text-slate-600">
        {data.unavailable_reason ?? "Rota sohbeti şu an kullanılamıyor."}
      </Text>
    );
  }

  const messages: ChatMessage[] = data?.messages ?? [];
  const recording = recState.isRecording;
  const recSecs = Math.max(0, Math.floor((recState.durationMillis ?? 0) / 1000));

  return (
    <View className="gap-3">
      <View className="gap-2.5">
        {data?.greeting ? <RotaBubble body={data.greeting.text} /> : null}
        {messages.map((m) =>
          m.role === "rota" ? (
            <RotaBubble
              key={m.id}
              body={m.body}
              listenState={
                voicePendingId === m.id
                  ? "pending"
                  : playingId === m.id
                    ? "playing"
                    : "idle"
              }
              onListen={() => void toggleListen(m)}
            />
          ) : (
            <View key={m.id} className="flex-row justify-end">
              <View className="max-w-[85%] rounded-2xl rounded-tr-sm bg-cyan-600 px-3 py-2">
                <Text className="text-sm leading-5 text-white">{m.body}</Text>
              </View>
            </View>
          ),
        )}
        {askMut.isPending ? <RotaBubble body="" thinking /> : null}
      </View>

      {data?.greeting?.chips?.length ? (
        <View className="flex-row flex-wrap gap-1.5">
          {data.greeting.chips.map((c) => (
            <Pressable
              key={c.id}
              disabled={askMut.isPending}
              onPress={() =>
                c.action === "commentary"
                  ? onOpenCommentary(c.payload as CommentaryKind)
                  : send(c.payload)
              }
              className="rounded-full border border-cyan-300 bg-white px-3 py-1.5 active:bg-cyan-50"
            >
              <Text className="text-xs font-medium text-cyan-800">{c.label}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      <View className="flex-row items-center gap-2">
        <TextInput
          value={text}
          onChangeText={setText}
          placeholder={recording ? "Dinliyorum… bitince kareye bas" : "Rota'ya sor…"}
          placeholderTextColor="#94a3b8"
          maxLength={500}
          editable={!askMut.isPending && (data?.daily_left ?? 0) > 0}
          className="h-11 flex-1 rounded-xl border border-cyan-200 bg-white px-3 text-sm text-slate-900"
          onSubmitEditing={() => send(text)}
          returnKeyType="send"
        />
        {transcribing ? (
          <View className="h-11 flex-row items-center gap-1.5 rounded-xl border border-cyan-200 bg-white px-3">
            <ActivityIndicator size="small" color="#0e7490" />
            <Text className="text-xs font-medium text-cyan-700">Çevriliyor…</Text>
          </View>
        ) : recording ? (
          <Pressable
            onPress={() => void stopRecording()}
            className="h-11 flex-row items-center gap-1.5 rounded-xl bg-rose-600 px-3 active:bg-rose-700"
          >
            <Ionicons name="stop" size={15} color="#fff" />
            <Text className="text-xs font-semibold text-white">
              {Math.floor(recSecs / 60)}:{String(recSecs % 60).padStart(2, "0")}
            </Text>
          </Pressable>
        ) : (
          <Pressable
            onPress={() => void startRecording()}
            disabled={askMut.isPending || (data?.daily_left ?? 0) <= 0}
            className={cn(
              "size-11 items-center justify-center rounded-xl border",
              askMut.isPending || (data?.daily_left ?? 0) <= 0
                ? "border-cyan-200 bg-white opacity-50"
                : "border-cyan-300 bg-white active:bg-cyan-50",
            )}
          >
            <Ionicons name="mic" size={17} color="#0e7490" />
          </Pressable>
        )}
        <Pressable
          onPress={() => send(text)}
          disabled={askMut.isPending || text.trim().length < 2}
          className={cn(
            "size-11 items-center justify-center rounded-xl",
            askMut.isPending || text.trim().length < 2
              ? "bg-cyan-300"
              : "bg-cyan-600 active:bg-cyan-700",
          )}
        >
          <Ionicons name="send" size={17} color="#fff" />
        </Pressable>
      </View>

      <View className="flex-row items-center justify-between">
        <Text className="flex-1 text-[10px] text-slate-400">
          Rota yalnız çocuğunun verilerine dayanır; koçun özel notları görülmez.
          Ses kaydın saklanmaz.
        </Text>
        <Text className="text-[10px] text-slate-400">
          Kalan soru: {data?.daily_left ?? 0}
        </Text>
      </View>
    </View>
  );
}
