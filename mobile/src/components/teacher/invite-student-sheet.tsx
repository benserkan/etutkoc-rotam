import * as React from "react";
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import type { StudentCreateBody, StudentCreateResult } from "@/lib/teacher";
import { cn } from "@/lib/utils";

const GRADES = [5, 6, 7, 8, 9, 10, 11, 12];

export function InviteStudentSheet({
  visible,
  busy,
  error,
  result,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  busy: boolean;
  error: string | null;
  result: StudentCreateResult | null;
  onClose: () => void;
  onSubmit: (body: StudentCreateBody) => void;
}) {
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [grade, setGrade] = React.useState<number | null>(8);
  const [copied, setCopied] = React.useState(false);

  const visRef = React.useRef(visible);
  if (visRef.current !== visible) {
    visRef.current = visible;
    if (visible) { setName(""); setEmail(""); setGrade(8); setCopied(false); }
  }

  const canSend = name.trim().length >= 3 && /\S+@\S+\.\S+/.test(email) && !busy;

  async function copyPwd() {
    if (!result) return;
    await Clipboard.setStringAsync(result.temp_password);
    setCopied(true);
  }

  return (
    <FormSheet visible={visible} title={result ? "Öğrenci oluşturuldu" : "Öğrenci davet et"} onClose={onClose}>
      {result ? (
        <View className="gap-4 pb-2">
          <View className="items-center gap-2 py-2">
            <View className="size-14 items-center justify-center rounded-full bg-emerald-100">
              <Ionicons name="checkmark" size={30} color="#059669" />
            </View>
            <Text className="text-center text-base font-semibold text-slate-900">{result.full_name} eklendi</Text>
            <Text className="text-center text-sm text-slate-500">{result.email}</Text>
          </View>
          <View className="rounded-xl border border-amber-200 bg-amber-50 p-4">
            <Text className="text-xs font-semibold text-amber-700">Geçici şifre</Text>
            <Text className="mt-1 text-2xl font-extrabold tracking-wide text-slate-900">{result.temp_password}</Text>
            <Text className="mt-1 text-xs text-amber-700">
              Öğrenciye ilet — ilk girişte kendi şifresini belirleyecek. Bu şifre tekrar gösterilmez.
            </Text>
          </View>
          <Pressable onPress={copyPwd} className="flex-row items-center justify-center gap-2 rounded-xl border border-slate-300 py-3 active:bg-slate-50">
            <Ionicons name={copied ? "checkmark" : "copy-outline"} size={18} color="#0e7490" />
            <Text className="text-base font-semibold text-brand-700">{copied ? "Kopyalandı" : "Şifreyi kopyala"}</Text>
          </Pressable>
          <Pressable onPress={onClose} className="items-center rounded-xl bg-brand-700 py-3.5 active:bg-brand-800">
            <Text className="text-base font-semibold text-white">Tamam</Text>
          </Pressable>
        </View>
      ) : (
        <View className="gap-4 pb-2">
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">Ad soyad</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="Öğrencinin adı soyadı"
              placeholderTextColor="#94a3b8"
              className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
            />
          </View>
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">E-posta</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="ornek@eposta.com"
              placeholderTextColor="#94a3b8"
              autoCapitalize="none"
              keyboardType="email-address"
              className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
            />
          </View>
          <View className="gap-1.5">
            <Text className="text-xs font-medium text-slate-600">Sınıf</Text>
            <View className="flex-row flex-wrap gap-2">
              {GRADES.map((g) => {
                const active = g === grade;
                return (
                  <Pressable
                    key={g}
                    onPress={() => setGrade(g)}
                    className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}
                  >
                    <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{g}.</Text>
                  </Pressable>
                );
              })}
              <Pressable
                onPress={() => setGrade(null)}
                className={cn("rounded-full border px-3 py-1.5", grade == null ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}
              >
                <Text className={cn("text-sm font-medium", grade == null ? "text-brand-700" : "text-slate-600")}>Mezun</Text>
              </Pressable>
            </View>
          </View>

          {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

          <Pressable
            onPress={() =>
              onSubmit({
                full_name: name.trim(),
                email: email.trim(),
                grade_level: grade,
                is_graduate: grade == null,
              })
            }
            disabled={!canSend}
            className={cn("items-center rounded-xl py-3.5", canSend ? "bg-brand-700 active:bg-brand-800" : "bg-brand-700/40")}
          >
            <Text className="text-base font-semibold text-white">{busy ? "Oluşturuluyor…" : "Öğrenciyi oluştur"}</Text>
          </Pressable>
          <Text className="text-[11px] text-slate-400">
            Öğrenci hesabı oluşturulur, geçici şifre verilir. Paket limitin doluysa eklenemez.
          </Text>
        </View>
      )}
    </FormSheet>
  );
}
