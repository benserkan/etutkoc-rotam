import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import type { SupportCategoryOption, SupportListItem } from "@/lib/support";
import { cn } from "@/lib/utils";

export const STATUS_TONE: Record<string, { bg: string; text: string }> = {
  open: { bg: "bg-sky-50", text: "text-sky-700" },
  under_review: { bg: "bg-amber-50", text: "text-amber-700" },
  answered: { bg: "bg-emerald-50", text: "text-emerald-700" },
  resolved: { bg: "bg-slate-100", text: "text-slate-600" },
  withdrawn: { bg: "bg-slate-100", text: "text-slate-500" },
};

function ago(iso: string): string {
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const h = Math.floor(diff / 3_600_000);
  if (h < 1) return "az önce";
  if (h < 24) return `${h} sa önce`;
  const d = Math.floor(h / 24);
  return `${d} gün önce`;
}

function NewRequestForm({
  categories,
  busy,
  onSubmit,
}: {
  categories: SupportCategoryOption[];
  busy: boolean;
  onSubmit: (body: { category: string; subject: string; body: string }) => void;
}) {
  const [category, setCategory] = React.useState(categories[0]?.value ?? "other");
  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");
  const canSend = subject.trim().length > 0 && body.trim().length > 0 && !busy;
  return (
    <View className="gap-4 pb-2">
      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Konu türü</Text>
        <View className="flex-row flex-wrap gap-2">
          {categories.map((c) => {
            const active = c.value === category;
            return (
              <Pressable
                key={c.value}
                onPress={() => setCategory(c.value)}
                className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}
              >
                <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{c.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Başlık</Text>
        <TextInput
          value={subject}
          onChangeText={setSubject}
          placeholder="Kısa başlık"
          placeholderTextColor="#94a3b8"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Mesaj</Text>
        <TextInput
          value={body}
          onChangeText={setBody}
          placeholder="Talebini ayrıntılı yaz…"
          placeholderTextColor="#94a3b8"
          multiline
          className="min-h-[96px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>
      <Pressable
        onPress={() => onSubmit({ category, subject: subject.trim(), body: body.trim() })}
        disabled={!canSend}
        className={cn("items-center rounded-xl py-3.5", canSend ? "bg-brand-700 active:bg-brand-800" : "bg-brand-700/40")}
      >
        <Text className="text-base font-semibold text-white">{busy ? "Gönderiliyor…" : "Talebi gönder"}</Text>
      </Pressable>
    </View>
  );
}

export function SupportListView({
  view,
  onChangeView,
  showInbox,
  data,
  createBusy,
  onCreate,
  onOpen,
}: {
  view: "mine" | "inbox";
  onChangeView: (v: "mine" | "inbox") => void;
  showInbox: boolean;
  data: { items: SupportListItem[]; categories: SupportCategoryOption[] };
  createBusy: boolean;
  onCreate: (body: { category: string; subject: string; body: string }) => void;
  onOpen: (id: number) => void;
}) {
  const [sheet, setSheet] = React.useState(false);

  return (
    <View className="flex-1 gap-3 px-4 py-4">
      {showInbox ? (
        <View className="flex-row gap-2 rounded-xl bg-slate-100 p-1">
          {(["mine", "inbox"] as const).map((v) => {
            const active = v === view;
            return (
              <Pressable
                key={v}
                onPress={() => onChangeView(v)}
                className={cn("flex-1 items-center rounded-lg py-2", active ? "bg-white" : "")}
              >
                <Text className={cn("text-sm font-semibold", active ? "text-brand-700" : "text-slate-500")}>
                  {v === "mine" ? "Taleplerim" : "Gelen Talepler"}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      {view === "mine" ? (
        <Pressable
          onPress={() => setSheet(true)}
          className="flex-row items-center justify-center gap-2 rounded-2xl border border-brand-200 bg-brand-50 py-3.5 active:bg-brand-100"
        >
          <Ionicons name="add-circle-outline" size={20} color="#0e7490" />
          <Text className="text-base font-semibold text-brand-700">Yeni talep</Text>
        </Pressable>
      ) : null}

      {data.items.length === 0 ? (
        <View className="mt-6 items-center gap-2 px-6">
          <Ionicons name="chatbubbles-outline" size={40} color="#94a3b8" />
          <Text className="text-center text-sm text-slate-500">
            {view === "mine" ? "Henüz talebin yok." : "Gelen talep yok."}
          </Text>
        </View>
      ) : (
        <View className="gap-2.5">
          {data.items.map((it) => {
            const st = STATUS_TONE[it.status] ?? STATUS_TONE.open;
            return (
              <Pressable
                key={it.id}
                onPress={() => onOpen(it.id)}
                className="rounded-2xl border border-slate-200 bg-white p-4 active:bg-slate-50"
              >
                <View className="flex-row items-start justify-between gap-2">
                  <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={1}>
                    {it.subject}
                  </Text>
                  <View className={cn("rounded-full px-2 py-0.5", st.bg)}>
                    <Text className={cn("text-[11px] font-semibold", st.text)}>{it.status_label}</Text>
                  </View>
                </View>
                <Text className="mt-0.5 text-xs text-slate-400">
                  {it.category_label}
                  {view === "inbox" ? ` · ${it.requester_name}` : ""}
                  {" · "}
                  {ago(it.last_activity_at)}
                </Text>
                {it.last_message_preview ? (
                  <Text className="mt-1.5 text-xs text-slate-500" numberOfLines={2}>
                    {it.last_message_preview}
                  </Text>
                ) : null}
              </Pressable>
            );
          })}
        </View>
      )}

      <FormSheet visible={sheet} title="Yeni talep" onClose={() => setSheet(false)}>
        <NewRequestForm
          categories={data.categories}
          busy={createBusy}
          onSubmit={(b) => {
            onCreate(b);
            setSheet(false);
          }}
        />
      </FormSheet>
    </View>
  );
}
