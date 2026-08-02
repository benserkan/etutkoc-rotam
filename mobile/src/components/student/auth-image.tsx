import * as React from "react";
import { View } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import { cssInterop } from "nativewind";

import { wrongImageSource } from "@/lib/wrong-questions";
import { cn } from "@/lib/utils";

/**
 * expo-image ÜÇÜNCÜ TARAF bileşendir; NativeWind onu tanımaz, dolayısıyla
 * `className` sessizce yok sayılır ve görsel 0x0 boyutla çizilir (foto "yok"
 * görünür — saha hatası 2026-08-02). Aşağıdaki kayıt className'i style'a çevirir.
 * KURAL: NativeWind dışı bir bileşene className verilecekse önce burada olduğu
 * gibi cssInterop ile kaydedilir; yoksa hata görünmez biçimde geçer.
 */
cssInterop(Image, { className: "style" });

/**
 * Auth'lu BFF ucundan (Bearer header) yanlış-soru fotoğrafı gösterir.
 * Token secure-store'da olduğundan kaynak asenkron çözülür; çözülene kadar
 * yer tutucu görünür. (Kod tabanında header'lı Image ilk kez.)
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
    <Image
      source={src}
      contentFit={contentFit}
      transition={120}
      className={className}
      style={{ backgroundColor: "#f1f5f9" }}
    />
  );
}
