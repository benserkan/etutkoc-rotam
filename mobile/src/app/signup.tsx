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
import {
  fetchSignupPhoneRequired,
  startSignupPhone,
  verifySignupPhone,
} from "@/lib/signup-phone";
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

  // #5 SMS telefon kapısı — yalnız sunucuda açıksa zorunlu (şu an dormant=false)
  const [phoneRequired, setPhoneRequired] = React.useState<boolean | null>(null);
  const [otpSent, setOtpSent] = React.useState(false);
  const [otpCode, setOtpCode] = React.useState("");
  const [devCode, setDevCode] = React.useState<string | null>(null);
  const [phoneToken, setPhoneToken] = React.useState("");
  const [phoneVerified, setPhoneVerified] = React.useState(false);
  const [phoneBusy, setPhoneBusy] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    void fetchSignupPhoneRequired().then((req) => {
      if (alive) setPhoneRequired(req);
    });
    return () => {
      alive = false;
    };
  }, []);

  async function onSendCode() {
    setError(null);
    if (phone.trim().length < 10) return setError("Geçerli bir cep telefonu gir.");
    setPhoneBusy(true);
    try {
      const r = await startSignupPhone(phone.trim());
      setOtpSent(true);
      setDevCode(r.dev_code ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Kod gönderilemedi. Tekrar dene.");
    } finally {
      setPhoneBusy(false);
    }
  }

  async function onVerifyCode() {
    setError(null);
    if (otpCode.trim().length !== 6) return setError("6 haneli kodu gir.");
    setPhoneBusy(true);
    try {
      const r = await verifySignupPhone(phone.trim(), otpCode.trim());
      setPhoneToken(r.phone_token);
      setPhoneVerified(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Doğrulama başarısız.");
    } finally {
      setPhoneBusy(false);
    }
  }

  async function onSubmit() {
    setError(null);
    if (fullName.trim().length < 3) return setError("Ad soyad en az 3 karakter olmalı.");
    if (!email.includes("@")) return setError("Geçerli bir e-posta gir.");
    if (password.length < 8) return setError("Şifre en az 8 karakter olmalı.");
    if (password !== confirm) return setError("Şifreler eşleşmiyor.");
    if (phoneRequired && !phoneVerified) {
      return setError("Devam etmek için cep telefonunu SMS ile doğrula.");
    }
    setBusy(true);
    try {
      await signUp({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        password_confirm: confirm,
        phone: phoneRequired ? undefined : phone.trim() || undefined,
        phone_token: phoneRequired ? phoneToken : undefined,
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

          {phoneRequired ? (
            <View className="gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-3">
              <Text className="text-xs font-semibold text-slate-700">Cep telefonu doğrulama</Text>
              {phoneVerified ? (
                <View className="flex-row items-center gap-2">
                  <Ionicons name="checkmark-circle" size={20} color="#059669" />
                  <Text className="text-sm font-medium text-emerald-700">{phone.trim()} doğrulandı</Text>
                </View>
              ) : (
                <>
                  <View className="flex-row items-end gap-2">
                    <View className="flex-1">
                      <Field label="Cep telefonu" value={phone} onChangeText={setPhone} placeholder="05XX XXX XX XX" keyboardType="phone-pad" editable={!otpSent} />
                    </View>
                    {!otpSent ? (
                      <Pressable onPress={onSendCode} disabled={phoneBusy} className={cn("mb-1 items-center justify-center rounded-xl bg-slate-800 px-4 py-3", phoneBusy && "opacity-50")}>
                        {phoneBusy ? <ActivityIndicator color="#fff" /> : <Text className="text-sm font-semibold text-white">Kod gönder</Text>}
                      </Pressable>
                    ) : null}
                  </View>
                  {otpSent ? (
                    <>
                      <View className="flex-row items-end gap-2">
                        <View className="flex-1">
                          <Field label="SMS kodu" value={otpCode} onChangeText={(v) => setOtpCode(v.replace(/\D/g, "").slice(0, 6))} placeholder="6 haneli kod" keyboardType="number-pad" />
                        </View>
                        <Pressable onPress={onVerifyCode} disabled={phoneBusy} className={cn("mb-1 items-center justify-center rounded-xl bg-brand-700 px-4 py-3", phoneBusy && "opacity-50")}>
                          {phoneBusy ? <ActivityIndicator color="#fff" /> : <Text className="text-sm font-semibold text-white">Doğrula</Text>}
                        </Pressable>
                      </View>
                      <Pressable onPress={onSendCode} hitSlop={6} disabled={phoneBusy}>
                        <Text className="text-xs font-medium text-brand-700">Kodu tekrar gönder</Text>
                      </Pressable>
                      {devCode ? <Text className="text-xs text-slate-400">Test kodu: {devCode}</Text> : null}
                    </>
                  ) : null}
                </>
              )}
            </View>
          ) : (
            <Field label="Cep telefonu (opsiyonel)" value={phone} onChangeText={setPhone} placeholder="05XX XXX XX XX" keyboardType="phone-pad" />
          )}

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
