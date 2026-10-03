/**
 * Rota balonu — rol sekme ekranlarında sağ altta (2026-10-03).
 * Dokununca tek asistan ekranı açılır; bulunulan ekranın sayfasını taşır
 * (sunucu o ekranın hazır sorularını öne alır). Klavye açıkken gizlenir.
 */
import * as React from "react";
import { Image, Keyboard, Pressable, Text, View } from "react-native";
import { router, useGlobalSearchParams, usePathname } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { pageForScreen, ROTA_AVATAR } from "@/lib/site-assistant";

const TAB_PREFIXES = ["/teacher/", "/student/", "/parent/", "/institution/"];

export function AssistantFab() {
  const pathname = usePathname() || "/";
  const params = useGlobalSearchParams();
  const insets = useSafeAreaInsets();
  const [kb, setKb] = React.useState(false);

  React.useEffect(() => {
    const a = Keyboard.addListener("keyboardDidShow", () => setKb(true));
    const b = Keyboard.addListener("keyboardDidHide", () => setKb(false));
    return () => {
      a.remove();
      b.remove();
    };
  }, []);

  if (kb || !TAB_PREFIXES.some((p) => pathname.startsWith(p))) return null;

  return (
    <View pointerEvents="box-none" style={{ position: "absolute", right: 14, bottom: insets.bottom + 62 }}>
      <Pressable
        onPress={() =>
          router.push({ pathname: "/assistant", params: { page: pageForScreen(pathname, params) } } as never)
        }
        accessibilityLabel="Rota asistanını aç"
        className="flex-row items-center gap-2 rounded-full bg-brand-700 py-1.5 pl-1.5 pr-4 shadow-lg active:bg-brand-800"
        style={{ elevation: 6 }}
      >
        <View className="h-8 w-8 overflow-hidden rounded-full border-2 border-white/80">
          <Image source={{ uri: ROTA_AVATAR }} style={{ width: "100%", height: "100%" }} resizeMode="cover" />
        </View>
        <Text className="text-sm font-bold text-white">Rota&apos;ya sor</Text>
      </Pressable>
    </View>
  );
}
