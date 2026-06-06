import "../global.css";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { QueryClientProvider } from "@tanstack/react-query";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ErrorBoundary } from "@/components/error-boundary";
import { AuthProvider } from "@/lib/auth";
import { NotificationObserver } from "@/lib/notification-router";
import { queryClient } from "@/lib/query";

// Yakalanmamış JS hatalarını (render dışı) sessiz çökme yerine logla — release
// teşhisi için. Varsayılan handler isFatal'da uygulamayı kapatır; burada
// kapatmadan loglarız (ErrorBoundary render hatalarını ayrıca ekranda gösterir).
const g = globalThis as unknown as {
  ErrorUtils?: { setGlobalHandler: (h: (e: Error, isFatal?: boolean) => void) => void };
};
g.ErrorUtils?.setGlobalHandler((error, isFatal) => {
  // eslint-disable-next-line no-console
  console.error("GlobalHandler:", isFatal ? "FATAL" : "non-fatal", error?.message, error?.stack);
});

export default function RootLayout() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <SafeAreaProvider>
            <StatusBar style="dark" />
            <NotificationObserver />
            <Stack screenOptions={{ headerShown: false }} />
          </SafeAreaProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
