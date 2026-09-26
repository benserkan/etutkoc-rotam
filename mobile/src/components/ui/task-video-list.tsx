import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, View } from "react-native";

import { openTaskLink, type TaskVideoRef } from "@/lib/task-display";

/**
 * Çok videolu görev (Video Sepeti) — her video ayrı dokunulabilir satır;
 * dokununca YouTube uygulamasında/tarayıcıda açılır. Tek videoda çağıran
 * taraf mevcut "Videoyu izle" düğmesini kullanır (liste render edilmez).
 */
export function TaskVideoList({ videos }: { videos: TaskVideoRef[] | null | undefined }) {
  if (!videos || videos.length < 2) return null;
  const total = videos.reduce((s, v) => s + (v.duration_min ?? 0), 0);
  return (
    <View className="gap-2">
      <Text className="text-xs font-semibold text-slate-600">
        {videos.length} video{total > 0 ? ` · ${total} dk` : ""} — izlemek için dokun
      </Text>
      {videos.map((v, i) => (
        <Pressable
          key={v.id}
          onPress={() => void openTaskLink(v.url)}
          accessibilityRole="link"
          accessibilityLabel={`${i + 1}. video: ${v.title}`}
          className="flex-row items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
        >
          <View className="size-8 items-center justify-center rounded-full bg-brand-700">
            <Ionicons name="play" size={14} color="#fff" />
          </View>
          <View className="flex-1">
            <Text className="text-[14px] font-medium text-slate-900">
              {i + 1}. {v.title}
            </Text>
            <View className="mt-0.5 flex-row flex-wrap items-center gap-2">
              {v.duration_min ? <Text className="text-xs text-slate-500">{v.duration_min} dk</Text> : null}
              {v.role === "soru" ? (
                <View className="rounded bg-amber-600 px-1.5 py-0.5">
                  <Text className="text-[10px] font-semibold text-white">soru çözümü</Text>
                </View>
              ) : null}
            </View>
          </View>
          <Ionicons name="open-outline" size={16} color="#94a3b8" />
        </Pressable>
      ))}
    </View>
  );
}
