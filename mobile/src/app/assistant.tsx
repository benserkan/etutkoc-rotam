/**
 * Rota — uygulamanın tek asistanı (2026-10-03; web site-assistant paritesi).
 * Giriş yapmadan da açılır (karşılama/giriş ekranından). Hazır sorular anında,
 * serbest sorular yapay zekâyla cevaplanır; çözemezse "Ekibe yaz" ya da WhatsApp.
 * Parametreler: page (soruldugu ekranın web yolu), q (hazır soru metni), chip.
 */
import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import {
  ActivityIndicator,
  Image,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ApiError } from "@/lib/api";
import {
  askAssistant,
  assistantKeys,
  getAssistantState,
  handoffAssistant,
  mobileHrefFor,
  ROTA_AVATAR,
  type AssistantAction,
  type AssistantMessage,
} from "@/lib/site-assistant";
import { cn } from "@/lib/utils";

type Msg = AssistantMessage & { action?: AssistantAction | null; pending?: boolean };

function one(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default function AssistantScreen() {
  const params = useLocalSearchParams();
  const page = one(params.page) || "/";
  const initQ = one(params.q);
  const initChip = one(params.chip);

  const stateQ = useQuery({
    queryKey: assistantKeys.state(page),
    queryFn: () => getAssistantState(page),
    staleTime: 60_000,
  });
  const [msgs, setMsgs] = React.useState<Msg[]>([]);
  const [input, setInput] = React.useState("");
  const [used, setUsed] = React.useState<string[]>([]);
  const [handoff, setHandoff] = React.useState(false);
  const [form, setForm] = React.useState({ message: "", name: "", phone: "", email: "" });
  const [done, setDone] = React.useState<{ message: string; wa: string } | null>(null);
  const [left, setLeft] = React.useState<number | null>(null);
  const scrollRef = React.useRef<ScrollView>(null);
  const asked = React.useRef(false);

  const history = (): AssistantMessage[] =>
    msgs.filter((m) => !m.pending).map((m) => ({ role: m.role, text: m.text }));

  const ask = useMutation({
    mutationFn: (b: { chip?: string; question?: string; label: string }) =>
      askAssistant({ page, chip: b.chip, label: b.label, question: b.question, history: history() }),
    onMutate: (b) =>
      setMsgs((m) => [...m, { role: "user", text: b.label }, { role: "assistant", text: "", pending: true }]),
    onSuccess: (res) => {
      setLeft(res.ai_left);
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "assistant", text: res.answer, action: res.action }]);
    },
    onError: (err) =>
      setMsgs((m) => [
        ...m.filter((x) => !x.pending),
        {
          role: "assistant",
          text:
            err instanceof ApiError && err.status === 429
              ? err.message
              : "Bağlantıda bir sorun oldu. Tekrar dene ya da ekibimize yaz.",
          action: { type: "handoff", label: "Ekibe yaz" },
        },
      ]),
  });

  React.useEffect(() => {
    if (asked.current || !initQ) return;
    asked.current = true;
    ask.mutate(initChip ? { chip: initChip, label: initQ } : { question: initQ, label: initQ });
  }, [initQ, initChip, ask]);

  const data = stateQ.data;
  const loggedIn = data?.logged_in ?? false;

  const send = useMutation({
    mutationFn: () =>
      handoffAssistant({
        page,
        message: form.message.trim(),
        transcript: history(),
        ...(loggedIn
          ? {}
          : {
              name: form.name.trim(),
              phone: form.phone.trim() || undefined,
              email: form.email.trim() || undefined,
            }),
      }),
    onSuccess: (res) => {
      setDone({ message: res.message, wa: res.whatsapp_url });
      setHandoff(false);
      setForm((f) => ({ ...f, message: "" }));
    },
  });

  const lastQ = [...msgs].reverse().find((m) => m.role === "user")?.text ?? "";
  const waUrl = `https://wa.me/${data?.whatsapp ?? "905056738561"}?text=${encodeURIComponent(
    `Merhaba, ETÜTKOÇ Rotam hakkında yazıyorum.${lastQ ? ` ${lastQ}` : ""}`,
  )}`;
  const chips = (data?.chips ?? []).filter((c) => !used.includes(c.id));
  const aiLeft = left ?? data?.ai_left ?? null;
  const formOk =
    form.message.trim().length >= 3 &&
    (loggedIn || (form.name.trim().length >= 2 && (form.phone.trim() || form.email.trim())));

  function actionTarget(a: AssistantAction): string | null {
    if (a.type === "link" && a.href) return mobileHrefFor(a.href);
    if (a.type === "select_plan" && a.plan) return `/teacher-plan?select=${encodeURIComponent(a.plan)}`;
    return null;
  }

  function onAction(a: AssistantAction) {
    if (a.type === "handoff") {
      setHandoff(true);
      return;
    }
    const to = actionTarget(a);
    if (to) router.push(to as never);
  }

  function submit() {
    const q = input.trim();
    if (!q || ask.isPending) return;
    setInput("");
    ask.mutate({ question: q, label: q });
  }

  const sendErr =
    send.error instanceof ApiError ? send.error.message : send.isError ? "Gönderilemedi, tekrar dene." : null;

  return (
    <SafeAreaView edges={["top", "bottom"]} className="flex-1 bg-white">
      <View className="flex-row items-center gap-3 bg-brand-800 px-4 py-3">
        <Pressable onPress={() => router.back()} hitSlop={10} accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={24} color="#fff" />
        </Pressable>
        <View className="h-10 w-10 overflow-hidden rounded-full border-2 border-white/70">
          <Image source={{ uri: ROTA_AVATAR }} style={{ width: "100%", height: "100%" }} resizeMode="cover" />
        </View>
        <View className="flex-1">
          <Text className="text-base font-bold text-white">Rota</Text>
          <View className="flex-row items-center gap-1.5">
            <Ionicons name="sparkles" size={12} color="#cffafe" />
            <Text className="text-xs text-cyan-100">Yapay zekâ destekli asistan</Text>
          </View>
        </View>
        <Pressable
          onPress={() => Linking.openURL(waUrl)}
          accessibilityLabel="WhatsApp'tan yaz"
          className="flex-row items-center gap-1.5 rounded-full bg-white/15 px-3 py-2 active:bg-white/25"
        >
          <Ionicons name="logo-whatsapp" size={16} color="#fff" />
          <Text className="text-xs font-bold text-white">WhatsApp</Text>
        </Pressable>
      </View>

      <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          ref={scrollRef}
          className="flex-1"
          contentContainerClassName="gap-3 px-4 py-4"
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
          keyboardShouldPersistTaps="handled"
        >
          {stateQ.isLoading ? (
            <ActivityIndicator color="#0e7490" />
          ) : (
            <Bubble role="assistant" text={data?.greeting ?? "Merhaba! Sistemle ilgili ne sormak istersin?"} />
          )}
          {msgs.map((m, i) => {
            const target = m.action ? actionTarget(m.action) : null;
            const showBtn = m.action?.label && (m.action.type === "handoff" || target);
            return (
              <View key={i} className="gap-2">
                {m.pending ? (
                  <View className="flex-row items-center gap-2 self-start rounded-2xl bg-slate-100 px-4 py-3">
                    <ActivityIndicator size="small" color="#64748b" />
                    <Text className="text-sm text-slate-500">Düşünüyor</Text>
                  </View>
                ) : (
                  <Bubble role={m.role} text={m.text} />
                )}
                {showBtn ? (
                  <Pressable
                    onPress={() => onAction(m.action!)}
                    className="self-start rounded-full border border-brand-600 px-4 py-2 active:bg-brand-50"
                  >
                    <Text className="text-sm font-semibold text-brand-700">{m.action!.label}</Text>
                  </Pressable>
                ) : null}
              </View>
            );
          })}

          {done ? (
            <View className="gap-2 rounded-2xl bg-emerald-600 px-4 py-3">
              <Text className="text-sm text-white">{done.message}</Text>
              <Pressable
                onPress={() => Linking.openURL(done.wa)}
                className="flex-row items-center gap-1.5 self-start rounded-full bg-white px-3 py-2"
              >
                <Ionicons name="logo-whatsapp" size={16} color="#047857" />
                <Text className="text-xs font-bold text-emerald-800">Acelen varsa WhatsApp&apos;tan da yaz</Text>
              </Pressable>
            </View>
          ) : null}

          {handoff ? (
            <View className="gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <Text className="text-sm font-bold text-slate-900">Ekibimize yaz</Text>
              <Text className="text-xs text-slate-500">
                Bu konuşma da mesajınla birlikte iletilir.
                {loggedIn ? " Cevabı Destek ekranından ya da e-postandan alırsın." : " Sana telefonla ya da e-postayla döneriz."}
              </Text>
              {!loggedIn ? (
                <>
                  <Input label="Adın" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} />
                  <Input
                    label="Cep telefonun"
                    value={form.phone}
                    onChange={(v) => setForm((f) => ({ ...f, phone: v }))}
                    keyboardType="phone-pad"
                    placeholder="05XX XXX XX XX"
                  />
                  <Input
                    label="E-posta (isteğe bağlı)"
                    value={form.email}
                    onChange={(v) => setForm((f) => ({ ...f, email: v }))}
                    keyboardType="email-address"
                  />
                </>
              ) : null}
              <TextInput
                value={form.message}
                onChangeText={(v) => setForm((f) => ({ ...f, message: v }))}
                placeholder="Ne konuda yardım istediğini kısaca yaz"
                placeholderTextColor="#94a3b8"
                multiline
                maxLength={2000}
                className="min-h-[80px] rounded-xl border border-slate-300 bg-white px-3 py-2 text-base text-slate-900"
              />
              {sendErr ? <Text className="text-xs text-rose-700">{sendErr}</Text> : null}
              <View className="flex-row items-center justify-end gap-2">
                <Pressable onPress={() => setHandoff(false)} className="rounded-full px-4 py-2.5">
                  <Text className="text-sm font-semibold text-slate-600">Vazgeç</Text>
                </Pressable>
                <Pressable
                  disabled={!formOk || send.isPending}
                  onPress={() => send.mutate()}
                  className={cn("rounded-full px-5 py-2.5", formOk ? "bg-brand-700 active:bg-brand-800" : "bg-slate-300")}
                >
                  <Text className="text-sm font-bold text-white">{send.isPending ? "Gönderiliyor" : "Gönder"}</Text>
                </Pressable>
              </View>
            </View>
          ) : null}

          {chips.length > 0 && !ask.isPending && !handoff ? (
            <View className="flex-row flex-wrap gap-2 pt-1">
              {chips.map((c) => (
                <Pressable
                  key={c.id}
                  onPress={() => {
                    setUsed((u) => [...u, c.id]);
                    if (c.id === "human") setHandoff(true);
                    else ask.mutate({ chip: c.id, label: c.label });
                  }}
                  className="rounded-full border border-brand-600/40 bg-white px-3.5 py-2 active:bg-brand-50"
                >
                  <Text className="text-sm text-brand-800">{c.label}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </ScrollView>

        <View className="border-t border-slate-200 bg-white px-3 pb-2 pt-3">
          <View className="flex-row items-end gap-2">
            <TextInput
              value={input}
              onChangeText={setInput}
              onSubmitEditing={submit}
              placeholder="Sorunu yaz"
              placeholderTextColor="#94a3b8"
              maxLength={800}
              returnKeyType="send"
              className="h-12 flex-1 rounded-full border border-slate-300 bg-white px-4 text-base text-slate-900"
            />
            <Pressable
              onPress={submit}
              disabled={!input.trim() || ask.isPending}
              accessibilityLabel="Soruyu gönder"
              className={cn(
                "h-12 w-12 items-center justify-center rounded-full",
                input.trim() ? "bg-brand-700 active:bg-brand-800" : "bg-slate-300",
              )}
            >
              <Ionicons name="send" size={18} color="#fff" />
            </Pressable>
          </View>
          <Text className="mt-1.5 px-1 text-[11px] leading-4 text-slate-500">
            {aiLeft != null ? `Bugün ${aiLeft} serbest soru hakkın var · ` : ""}
            Yapay zekâ yanılabilir; önemli konularda ekibe yaz.
          </Text>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Input({
  label,
  value,
  onChange,
  keyboardType,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  keyboardType?: "phone-pad" | "email-address";
  placeholder?: string;
}) {
  return (
    <View className="gap-1">
      <Text className="text-xs text-slate-600">{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChange}
        keyboardType={keyboardType}
        autoCapitalize={keyboardType ? "none" : "words"}
        placeholder={placeholder}
        placeholderTextColor="#94a3b8"
        className="h-11 rounded-xl border border-slate-300 bg-white px-3 text-base text-slate-900"
      />
    </View>
  );
}

function Bubble({ role, text }: { role: "user" | "assistant"; text: string }) {
  return (
    <View
      className={cn(
        "max-w-[85%] rounded-2xl px-4 py-3",
        role === "user" ? "self-end rounded-br-md bg-brand-700" : "self-start rounded-bl-md bg-slate-100",
      )}
    >
      <Text className={cn("text-[15px] leading-6", role === "user" ? "text-white" : "text-slate-800")}>{text}</Text>
    </View>
  );
}
