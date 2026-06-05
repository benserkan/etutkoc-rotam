import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { Tabs } from "expo-router";

import { getTeacherRequests, teacherRequestKeys } from "@/lib/teacher";

/** Koç alt-sekme kabuğu: Öğrenciler · Talepler · Tahsilat · Destek · Profil. */
export default function TeacherTabsLayout() {
  const pendingQ = useQuery({
    queryKey: teacherRequestKeys.list("pending"),
    queryFn: () => getTeacherRequests("pending"),
    staleTime: 30_000,
  });
  const pending = pendingQ.data?.pending_count ?? 0;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: "#0e7490",
        tabBarInactiveTintColor: "#94a3b8",
        tabBarStyle: { borderTopColor: "#e2e8f0" },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600" },
      }}
    >
      <Tabs.Screen
        name="students"
        options={{
          title: "Öğrenciler",
          tabBarIcon: ({ color, size }) => <Ionicons name="people-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="requests"
        options={{
          title: "Talepler",
          tabBarBadge: pending > 0 ? pending : undefined,
          tabBarIcon: ({ color, size }) => <Ionicons name="git-pull-request-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="billing"
        options={{
          title: "Tahsilat",
          tabBarIcon: ({ color, size }) => <Ionicons name="wallet-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="support"
        options={{
          title: "Destek",
          tabBarIcon: ({ color, size }) => <Ionicons name="chatbubbles-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profil",
          tabBarIcon: ({ color, size }) => <Ionicons name="person-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}
