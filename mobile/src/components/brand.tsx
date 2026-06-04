import { Text, View } from "react-native";

/** ETÜTKOÇ marka wordmark'ı (web ile aynı: etütkoç petrol + rotam altın). */
export function Brand({ size = "md" }: { size?: "md" | "lg" }) {
  const fs = size === "lg" ? "text-3xl" : "text-2xl";
  return (
    <View className="flex-row items-baseline">
      <Text className={`${fs} font-extrabold tracking-tight text-brand-700`}>etütkoç</Text>
      <Text className={`${fs} font-extrabold text-slate-400`}> · </Text>
      <Text className={`${fs} font-extrabold tracking-tight text-gold`}>rotam</Text>
    </View>
  );
}
