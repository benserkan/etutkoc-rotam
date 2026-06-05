import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Link, router } from "expo-router";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Brand } from "@/components/brand";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export default function SignupScreen() {
  const { signUp } = useAuth();
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [show, setShow] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function onSubmit() {
    setError(null);
    if (fullName.trim().length < 3) return setError("Ad soyad en az 3 karakter olmalı.");
    if (!email.includes("@")) return setError("Geçerli bir e-posta gir.");
    if (password.length < 8) return setError("Şifre en az 8 karakter olmalı.");
    if (password !== confirm) return setError("Şifreler eşleşmiyor.");
    setBusy(true);
    try {
      await signUp({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        password_confirm: confirm,
        phone: phone.trim() || undefined,
      });
      router.replace("/(app)");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Kayıt yapılamadı. Bağlantını kontrol et.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView edges={["top", "bottom"]} className="flex-1 bg-white">
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} className="flex-1">
        <ScrollView contentContainerClassName="px-6 py-4 gap-4" keyboardShouldPersistTaps="handled">
          <View className="flex-row items-center justify-between">
            <Brand size="md" />
            <Pressable onPress={() => router.back()} hitSlop={8} className="size-9 items-center justify-center rounded-full active:bg-slate-100">
              <Ionicons name="close" size={24} color="#334155" />
            </Pressable>
          </View>

          <View className="mt-2">
            <Text className="text-2xl font-bold text-slate-900">Koç olarak başla</Text>
            <Text className="mt-1 text-sm text-slate-500">14 gün ücretsiz dene — kart gerekmez. Tüm takip + yapay zekâ hazırlık açık.</Text>
          </View>

          <Field label="Ad soyad" value={fullName} onChangeText={setFullName} placeholder="Adın Soyadın" autoCapitalize="words" />
          <Field label="E-posta" value={email} onChangeText={setEmail} placeholder="ornek@eposta.com" keyboardType="email-address" autoCapitalize="none" />
          <Field label="Cep telefonu (opsiyonel)" value={phone} onChangeText={setPhone} placeholder="05XX XXX XX XX" keyboardType="phone-pad" />

          <View>
            <Text className="mb-1 text-xs font-medium text-slate-600">Şifre</Text>
            <View className="flex-row items-center rounded-xl border border-slate-200 bg-white">
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="En az 8 karakter"
                placeholderTextColor="#94a3b8"
                secureTextEntry={!show}
                autoCapitalize="none"
                className="flex-1 px-3 py-3 text-sm text-slate-900"
              />
              <Pressable onPress={() => setShow((s) => !s)} className="px-3 py-3" hitSlop={8}>
                <Ionicons name={show ? "eye-off-outline" : "eye-outline"} size={20} color="#94a3b8" />
              </Pressable>
            </View>
          </View>

          <Field label="Şifre (tekrar)" value={confirm} onChangeText={setConfirm} placeholder="Şifreyi tekrar gir" secureTextEntry={!show} autoCapitalize="none" />

          {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

          <Pressable
            onPress={onSubmit}
            disabled={busy}
            className={cn("mt-1 items-center rounded-2xl bg-brand-700 py-4", busy ? "opacity-50" : "active:bg-brand-800")}
          >
            {busy ? <ActivityIndicator color="#fff" /> : <Text className="text-base font-bold text-white">14 gün ücretsiz başla</Text>}
          </Pressable>

          <Text className="text-center text-xs text-slate-400">
            Kayıt olarak Kullanım Şartları ve KVKK Aydınlatma Metni&apos;ni kabul etmiş olursun.
          </Text>

          <View className="mt-1 flex-row items-center justify-center gap-1">
            <Text className="text-sm text-slate-400">Zaten hesabın var mı?</Text>
            <Link href="/login" replace asChild>
              <Pressable hitSlop={8}>
                <Text className="text-sm font-semibold text-brand-700">Giriş yap</Text>
              </Pressable>
            </Link>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Field({
  label,
  ...props
}: {
  label: string;
} & React.ComponentProps<typeof TextInput>) {
  return (
    <View>
      <Text className="mb-1 text-xs font-medium text-slate-600">{label}</Text>
      <TextInput
        placeholderTextColor="#94a3b8"
        className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-900"
        {...props}
      />
    </View>
  );
}
