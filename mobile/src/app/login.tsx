import * as React from "react";
import { useRouter } from "expo-router";
import {
  ActivityIndicator,
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

import { Brand } from "@/components/brand";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginScreen() {
  const router = useRouter();
  const { signIn, verifyTwoFactor } = useAuth();

  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [code, setCode] = React.useState("");
  const [challenge, setChallenge] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function onSubmit() {
    if (busy) return;
    setError(null);
    if (!email.trim() || !password) {
      setError("E-posta ve şifre gerekli.");
      return;
    }
    setBusy(true);
    try {
      const res = await signIn(email.trim(), password);
      if (res.kind === "2fa") {
        setChallenge(res.challenge);
      } else if (res.mustChangePassword) {
        setError(
          "Hesabın için şifre değişikliği gerekiyor. Şimdilik web üzerinden (rotam.etutkoc.com) değiştir, sonra tekrar giriş yap.",
        );
      } else {
        router.replace("/(app)");
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Giriş yapılamadı. Bağlantını kontrol et.");
    } finally {
      setBusy(false);
    }
  }

  async function onVerify() {
    if (busy || !challenge) return;
    setError(null);
    if (code.trim().length < 6) {
      setError("6 haneli doğrulama kodunu gir.");
      return;
    }
    setBusy(true);
    try {
      const res = await verifyTwoFactor(challenge, code.trim());
      if (res.kind === "ok") {
        if (res.mustChangePassword) {
          setError("Şifre değişikliği gerekiyor. Web üzerinden değiştir, sonra giriş yap.");
        } else {
          router.replace("/(app)");
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Doğrulama başarısız.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView className="flex-1 bg-white">
      <KeyboardAvoidingView
        className="flex-1"
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerClassName="grow justify-center px-6 py-10"
          keyboardShouldPersistTaps="handled"
        >
          <View className="items-center mb-8">
            <Brand size="lg" />
            <Text className="mt-2 text-sm text-slate-500">Öğrenci koçluğu takip platformu</Text>
          </View>

          {challenge ? (
            <TwoFactorStep
              code={code}
              setCode={setCode}
              error={error}
              busy={busy}
              onVerify={onVerify}
              onCancel={() => {
                setChallenge(null);
                setCode("");
                setError(null);
              }}
            />
          ) : (
            <View className="gap-4">
              <Text className="text-2xl font-bold text-slate-900">Giriş yap</Text>

              <Field
                label="E-posta"
                value={email}
                onChangeText={setEmail}
                placeholder="ornek@eposta.com"
                keyboardType="email-address"
                autoCapitalize="none"
                autoComplete="email"
              />
              <Field
                label="Şifre"
                value={password}
                onChangeText={setPassword}
                placeholder="••••••••"
                secure
                autoCapitalize="none"
              />

              <Pressable
                onPress={() => void Linking.openURL("https://rotam.etutkoc.com/password/forgot")}
                className="self-end"
              >
                <Text className="text-sm font-medium text-brand-700">Şifremi unuttum?</Text>
              </Pressable>

              {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

              <PrimaryButton label="Giriş yap" busy={busy} onPress={onSubmit} />
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function TwoFactorStep({
  code,
  setCode,
  error,
  busy,
  onVerify,
  onCancel,
}: {
  code: string;
  setCode: (v: string) => void;
  error: string | null;
  busy: boolean;
  onVerify: () => void;
  onCancel: () => void;
}) {
  return (
    <View className="gap-4">
      <Text className="text-2xl font-bold text-slate-900">İki adımlı doğrulama</Text>
      <Text className="text-sm text-slate-500">
        Doğrulama uygulamandaki 6 haneli kodu gir.
      </Text>
      <Field
        label="Doğrulama kodu"
        value={code}
        onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, 8))}
        placeholder="123456"
        keyboardType="number-pad"
        autoCapitalize="none"
      />
      {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}
      <PrimaryButton label="Doğrula" busy={busy} onPress={onVerify} />
      <Pressable onPress={onCancel} className="items-center py-2">
        <Text className="text-sm text-slate-500">Vazgeç</Text>
      </Pressable>
    </View>
  );
}

function Field({
  label,
  secure,
  ...props
}: { label: string; secure?: boolean } & React.ComponentProps<typeof TextInput>) {
  const [show, setShow] = React.useState(false);
  return (
    <View className="gap-1.5">
      <Text className="text-sm font-medium text-slate-700">{label}</Text>
      <View className="flex-row items-center rounded-xl border border-slate-300 bg-white">
        <TextInput
          {...props}
          secureTextEntry={secure ? !show : false}
          placeholderTextColor="#94a3b8"
          className="flex-1 px-4 py-3 text-base text-slate-900"
        />
        {secure ? (
          <Pressable onPress={() => setShow((s) => !s)} className="px-3 py-3" hitSlop={8}>
            <Text className="text-xs font-semibold text-brand-700">
              {show ? "Gizle" : "Göster"}
            </Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

function PrimaryButton({
  label,
  busy,
  onPress,
}: {
  label: string;
  busy: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={busy}
      className={`mt-2 flex-row items-center justify-center rounded-xl px-4 py-3.5 ${
        busy ? "bg-brand-700/60" : "bg-brand-700 active:bg-brand-800"
      }`}
    >
      {busy ? <ActivityIndicator color="white" /> : (
        <Text className="text-base font-semibold text-white">{label}</Text>
      )}
    </Pressable>
  );
}
