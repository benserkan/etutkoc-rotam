import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "@/lib/auth";

export default function Index() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <View className="flex-1 items-center justify-center bg-white">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  // Giriş yapmamış kullanıcı → karşılama (tanıtım carousel). welcome ekranı
  // "tanıtımı gördüm" bayrağına bakıp dönen kullanıcıyı doğrudan login'e yollar.
  return <Redirect href={status === "authed" ? "/(app)" : "/welcome"} />;
}
