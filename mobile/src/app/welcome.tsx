import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Redirect, router } from "expo-router";
import {
  ActivityIndicator,
  Dimensions,
  Linking,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Brand } from "@/components/brand";
import { useAuth } from "@/lib/auth";
import { storageGet, storageSet } from "@/lib/storage";
import { cn } from "@/lib/utils";

const SEEN_KEY = "etk_onboarding_seen";
const SIGNUP_URL = "https://rotam.etutkoc.com/signup/teacher";

type Slide = {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  body: string;
};

const SLIDES: Slide[] = [
  {
    icon: "calendar-outline",
    title: "Öğrencini tek panelden takip et",
    body: "Günlük/haftalık program, deneme sonuçları ve gelişim analizleri tek yerde. Kim geride kaldı, kim hedefte — bir bakışta gör.",
  },
  {
    icon: "sparkles-outline",
    title: "Yapay zekâ ile hazırlan",
    body: "Seans notlarını sesle veya fotoğrafla al; koçluk içgörüsü üret. Zamanını öğrenciye ayır, formaliteyi yapay zekâ halletsin.",
  },
  {
    icon: "heart-outline",
    title: "Veli otomatik bilgilenir",
    body: "Haftalık rapor, deneme netleri ve 'kopan öğrenci' uyarısı veliye otomatik gider. Sen aramadan veli haberdar olur.",
  },
];

export default function WelcomeScreen() {
  const { status } = useAuth();
  const [seenChecked, setSeenChecked] = React.useState(false);
  const [shouldSkip, setShouldSkip] = React.useState(false);
  const [index, setIndex] = React.useState(0);
  const scrollRef = React.useRef<ScrollView>(null);
  const width = Dimensions.get("window").width;

  React.useEffect(() => {
    let alive = true;
    storageGet(SEEN_KEY).then((v) => {
      if (!alive) return;
      setShouldSkip(v === "1");
      setSeenChecked(true);
    });
    return () => {
      alive = false;
    };
  }, []);

  // Giriş yapmışsa app'e, tanıtımı görmüşse login'e
  if (status === "authed") return <Redirect href="/(app)" />;
  if (seenChecked && shouldSkip) return <Redirect href="/login" />;
  if (!seenChecked || status === "loading") {
    return (
      <View className="flex-1 items-center justify-center bg-white">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }

  async function markSeen() {
    try {
      await storageSet(SEEN_KEY, "1");
    } catch {
      // sessiz
    }
  }

  function onScroll(e: NativeSyntheticEvent<NativeScrollEvent>) {
    const i = Math.round(e.nativeEvent.contentOffset.x / width);
    if (i !== index) setIndex(i);
  }

  async function goLogin() {
    await markSeen();
    router.replace("/login");
  }
  async function goSignup() {
    await markSeen();
    // Şimdilik web signup (Turnstile + aktivasyon orada); native signup sıradaki adım.
    Linking.openURL(SIGNUP_URL).catch(() => router.replace("/login"));
  }
  function next() {
    if (index < SLIDES.length - 1) {
      scrollRef.current?.scrollTo({ x: (index + 1) * width, animated: true });
    }
  }

  const isLast = index === SLIDES.length - 1;

  return (
    <SafeAreaView edges={["top", "bottom"]} className="flex-1 bg-white">
      {/* Üst: marka + atla */}
      <View className="flex-row items-center justify-between px-5 pt-2">
        <Brand size="md" />
        <Pressable onPress={goLogin} hitSlop={8} className="px-2 py-1">
          <Text className="text-sm font-medium text-slate-400">Atla</Text>
        </Pressable>
      </View>

      {/* Carousel */}
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onScroll={onScroll}
        scrollEventThrottle={16}
        className="flex-1"
      >
        {SLIDES.map((s) => (
          <View key={s.title} style={{ width }} className="flex-1 items-center justify-center px-8">
            <View className="size-28 items-center justify-center rounded-3xl bg-brand-50">
              <Ionicons name={s.icon} size={56} color="#0e7490" />
            </View>
            <Text className="mt-8 text-center text-2xl font-extrabold text-slate-900">{s.title}</Text>
            <Text className="mt-3 text-center text-base leading-relaxed text-slate-500">{s.body}</Text>
          </View>
        ))}
      </ScrollView>

      {/* Noktalar */}
      <View className="flex-row items-center justify-center gap-2 pb-4">
        {SLIDES.map((s, i) => (
          <View
            key={s.title}
            className={cn("h-2 rounded-full", i === index ? "w-6 bg-brand-700" : "w-2 bg-slate-200")}
          />
        ))}
      </View>

      {/* CTA'lar */}
      <View className="gap-3 px-6 pb-2">
        {!isLast ? (
          <Pressable onPress={next} className="items-center rounded-2xl bg-brand-700 py-4 active:bg-brand-800">
            <Text className="text-base font-bold text-white">Devam</Text>
          </Pressable>
        ) : (
          <Pressable onPress={goSignup} className="items-center rounded-2xl bg-brand-700 py-4 active:bg-brand-800">
            <Text className="text-base font-bold text-white">14 gün ücretsiz dene</Text>
          </Pressable>
        )}
        <Pressable onPress={goLogin} className="items-center rounded-2xl border border-slate-200 py-4 active:bg-slate-50">
          <Text className="text-base font-semibold text-slate-700">Giriş yap</Text>
        </Pressable>
        <Text className="pt-1 text-center text-xs text-slate-400">
          Öğrenci veya veli misin? Koçundan aldığın bilgilerle <Text className="font-semibold text-slate-500">Giriş yap</Text>.
        </Text>
      </View>
    </SafeAreaView>
  );
}
