import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text } from "react-native";
import * as WebBrowser from "expo-web-browser";

import { cn } from "@/lib/utils";
import { demoFor, demoPlayUrl, type DemoRole } from "@/lib/demos";

/**
 * Panel-içi "▶ Nasıl kullanılır?" rozeti (mobil).
 *
 * contextKey + role'e karşılık yayınlanmış demo varsa rozet çıkar; dokununca
 * demo uygulama-içi tarayıcıda (expo-web-browser) açılır → kullanıcı uygulamadan
 * ÇIKMAZ, sesli anlatımlı web oynatıcıyı görür, kapatınca uygulamaya döner.
 * Demo yoksa hiçbir şey render etmez (slot kodda hazır, video gelince belirir).
 */
export function DemoHint({
  contextKey,
  role,
  className,
}: {
  contextKey: string;
  role: DemoRole;
  className?: string;
}) {
  const demo = demoFor(contextKey, role);
  if (!demo) return null;

  return (
    <Pressable
      onPress={() =>
        void WebBrowser.openBrowserAsync(demoPlayUrl(demo.slug), {
          presentationStyle: WebBrowser.WebBrowserPresentationStyle.PAGE_SHEET,
          toolbarColor: "#0e7490",
          controlsColor: "#ffffff",
        })
      }
      className={cn(
        "flex-row items-center gap-1.5 self-start rounded-full border border-cyan-300 bg-cyan-50 px-3 py-1.5 active:opacity-80",
        className,
      )}
    >
      <Ionicons name="play-circle" size={15} color="#0e7490" />
      <Text className="text-[12.5px] font-medium text-cyan-800">Nasıl kullanılır?</Text>
      <Text className="text-[11px] text-cyan-600">· {demo.durationLabel}</Text>
    </Pressable>
  );
}
