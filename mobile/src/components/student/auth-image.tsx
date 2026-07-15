import * as React from "react";
import { View } from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";

import { wrongImageSource } from "@/lib/wrong-questions";
import { cn } from "@/lib/utils";

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
