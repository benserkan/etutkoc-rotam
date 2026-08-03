import * as React from "react";
import { View } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";

import { wrongImageSource } from "@/lib/wrong-questions";
import { cn } from "@/lib/utils";

/**
 * Auth'lu BFF ucundan (Bearer header) yanlış-soru fotoğrafı gösterir.
 * Token secure-store'da olduğundan kaynak asenkron çözülür; çözülene kadar
 * yer tutucu görünür.
 *
 * NEDEN sarmalayıcı View + açık style (className DEĞİL):
 * expo-image NativeWind'e kayıtlı olmadığından className sessizce düşer ve
 * görsel 0×0 çizilir (saha hatası 2026-08-02: "fotoğraf görünmüyor").
 * İlk düzeltme modül kapsamında `cssInterop(Image, ...)` çağırmaktı; bu,
 * "nativewind" JS modülünü üretimde İLK KEZ require ederek her iki platformda
 * ekranı route yüklenirken çökertti (2026-08-03 "ErrorBoundary of undefined").
 * KURAL: expo-image boyutu daima açık style ile verilir; className yalnız
 * çekirdek RN bileşenlerinde (View/Text/Pressable) kullanılır — rehber
 * oynatıcısı ve çekim önizlemesiyle aynı, üretimde kanıtlı desen.
 */
export function AuthImage({
  wqId,
  imageId,
  className,
  contentFit = "contain",
}: {
  wqId: number;
  imageId: number;
  className?: string;
  contentFit?: "contain" | "cover";
}) {
  const [src, setSrc] = React.useState<{ uri: string; headers: Record<string, string> } | null>(
    null,
  );

  React.useEffect(() => {
    let alive = true;
    void wrongImageSource(wqId, imageId).then((s) => {
      if (alive) setSrc(s);
    });
    return () => {
      alive = false;
    };
  }, [wqId, imageId]);

  if (!src) {
    return (
      <View className={cn("items-center justify-center bg-slate-100", className)}>
        <Ionicons name="image-outline" size={28} color="#cbd5e1" />
      </View>
    );
  }
  return (
    <View className={cn("overflow-hidden", className)}>
      <Image
        source={src}
        contentFit={contentFit}
        transition={120}
        style={{ width: "100%", height: "100%", backgroundColor: "#f1f5f9" }}
      />
    </View>
  );
}
