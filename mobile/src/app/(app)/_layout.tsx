import { Redirect, Stack } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { PanelVisitTracker } from "@/components/panel-visit-tracker";
import { useAuth } from "@/lib/auth";

export default function AppLayout() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <View className="flex-1 items-center justify-center bg-white">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  if (status !== "authed") return <Redirect href="/login" />;

  return (
    <>
      <PanelVisitTracker />
      <Stack screenOptions={{ headerShown: false }} />
    </>
  );
}
