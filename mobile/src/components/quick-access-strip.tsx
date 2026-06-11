import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";

import {
  clickQuickCard,
  dismissQuickCard,
  getQuickCards,
  mobileHrefForCard,
  pinQuickCard,
  quickAccessKeys,
  type QuickCard,
} from "@/lib/quick-access";

/**
 * QuickAccessStrip (mobil) — davranıştan öğrenen hızlı erişim kartları.
 *
 * Web'deki şeridin RN karşılığı: 4 rolün ana ekranının üstünde yatay
 * kaydırmalı kart listesi. Dokun → ekrana git (+ kart tıkı: 3'te kalıcı);
 * BASILI TUT → Sabitle / Kaldır menüsü (mobilde hover yok).
 * Mobilde karşılığı olmayan kartlar (örn. kütüphane) gizlenir.
 * Yeterli veri yokken hiçbir şey render edilmez.
 */
export function QuickAccessStrip({ padded = true }: { padded?: boolean }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: quickAccessKeys.cards,
    queryFn: () => getQuickCards(),
    staleTime: 5 * 60_000,
  });

  const cards = (q.data?.cards ?? [])
    .map((card) => ({ card, href: mobileHrefForCard(card) }))
    .filter((x): x is { card: QuickCard; href: string } => x.href !== null)
    .slice(0, 6);

  if (cards.length === 0) return null;

  const refresh = () => qc.invalidateQueries({ queryKey: quickAccessKeys.cards });

  function openMenu(card: QuickCard) {
    const pinned = card.state === "pinned";
    Alert.alert(card.label, card.sublabel ?? "Hızlı erişim kartı", [
      {
        text: pinned ? "Sabitlemeyi kaldır" : "Sabitle",
        onPress: () => {
          pinQuickCard(card, !pinned).then(refresh).catch(() => {});
        },
      },
      {
        text: "Kaldır (90 gün önerilmez)",
        style: "destructive",
        onPress: () => {
          dismissQuickCard(card).then(refresh).catch(() => {});
        },
      },
      { text: "Vazgeç", style: "cancel" },
    ]);
  }

  function open(card: QuickCard, href: string) {
    clickQuickCard(card).then(refresh).catch(() => {});
    router.push(href as never);
  }

  return (
    <View className={padded ? "mb-3" : undefined}>
      <View
        className={
          padded
            ? "mb-1.5 flex-row items-center gap-1.5 px-4"
            : "mb-1.5 flex-row items-center gap-1.5"
        }
      >
        <Ionicons name="flash" size={13} color="#0e7490" />
        <Text className="text-xs font-semibold text-slate-700">Hızlı Erişim</Text>
        <Text className="flex-1 text-[10px] text-slate-400" numberOfLines={1}>
          alışkanlığından öğrenir · basılı tut: sabitle/kaldır
        </Text>
      </View>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={{ paddingHorizontal: padded ? 16 : 0, gap: 8 }}
      >
        {cards.map(({ card, href }) => (
          <Pressable
            key={`${card.route_key}:${card.entity_id ?? 0}`}
            onPress={() => open(card, href)}
            onLongPress={() => openMenu(card)}
            className={
              card.state === "pinned"
                ? "min-w-[140px] max-w-[200px] rounded-xl border border-cyan-300 bg-white px-3 py-2.5 active:bg-cyan-50"
                : "min-w-[140px] max-w-[200px] rounded-xl border border-slate-200 bg-white px-3 py-2.5 active:bg-slate-100"
            }
          >
            <View className="flex-row items-center gap-1">
              <Text
                className="flex-1 text-[13px] font-semibold text-slate-900"
                numberOfLines={1}
              >
                {card.label}
              </Text>
              {card.state === "pinned" && (
                <Ionicons name="pin" size={11} color="#0e7490" />
              )}
            </View>
            <View className="mt-0.5 flex-row items-center gap-1.5">
              <Text className="text-[11px] text-slate-500" numberOfLines={1}>
                {card.sublabel ?? "Sayfa"}
              </Text>
              {card.state === "suggested" && (
                <View className="rounded-full border border-cyan-200 bg-cyan-50 px-1.5 py-px">
                  <Text className="text-[9px] font-medium text-cyan-900">önerilen</Text>
                </View>
              )}
            </View>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}
