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

import { API_BASE, ApiError } from "@/lib/api";
import {
  type ChatMessage,
  type CommentaryKind,
  type ParentChatResponse,
  askParentChat,
  getParentChat,
  parentChatKeys,
} from "@/lib/parent";
import { cn } from "@/lib/utils";

/**
 * Rota'ya Sor (P2) — RN sohbeti (Rota kartının sekmesi). Kredisiz karşılama +
 * çipler; soru 3 kredi (günde 10). "Yorumla" çipleri kartın ilgili sekmesine
 * köprü (P1 önbelleği — kredisiz).
 */

const AVATAR = `${API_BASE}/static/guide/rota-avatar.png`;

function errAlert(e: unknown) {
  const code = e instanceof ApiError ? e.code : null;
  if (code === "daily_limit_reached")
    Alert.alert("Bugünlük bu kadar", "Bugünlük soru hakkın doldu — yarın yeniden sorabilirsin.");
  else if (code === "ai_credit_exhausted")
    Alert.alert("Rota dinlenmede", "Koçun yapay zekâ kotası bu ay için doldu.");
  else if (code === "ai_unavailable")
    Alert.alert("Şu an kullanılamıyor", "Yapay zekâ servisi geçici olarak yanıt vermiyor.");
  else Alert.alert("Olmadı", e instanceof ApiError ? e.message : "Cevap alınamadı, tekrar deneyin.");
}

function RotaBubble({ body, thinking }: { body: string; thinking?: boolean }) {
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
          <Text className="text-sm leading-5 text-slate-800">{body}</Text>
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

  if (q.isLoading) return <ActivityIndicator color="#0891b2" />;
  if (data && !data.ai_available) {
    return (
      <Text className="text-sm text-slate-600">
        {data.unavailable_reason ?? "Rota sohbeti şu an kullanılamıyor."}
      </Text>
    );
  }

  const messages: ChatMessage[] = data?.messages ?? [];

  return (
    <View className="gap-3">
      <View className="gap-2.5">
        {data?.greeting ? <RotaBubble body={data.greeting.text} /> : null}
        {messages.map((m) =>
          m.role === "rota" ? (
            <RotaBubble key={m.id} body={m.body} />
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
          placeholder="Rota'ya sor…"
          placeholderTextColor="#94a3b8"
          maxLength={500}
          editable={!askMut.isPending && (data?.daily_left ?? 0) > 0}
          className="h-11 flex-1 rounded-xl border border-cyan-200 bg-white px-3 text-sm text-slate-900"
          onSubmitEditing={() => send(text)}
          returnKeyType="send"
        />
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
        </Text>
        <Text className="text-[10px] text-slate-400">
          Kalan soru: {data?.daily_left ?? 0}
        </Text>
      </View>
    </View>
  );
}
