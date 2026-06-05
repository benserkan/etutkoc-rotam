import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { apiRequest } from "./api";

/**
 * Mobil push bildirim kaydı (Expo).
 *
 * Tüm fonksiyonlar **best-effort**: asla hata fırlatmaz. Web'de / simülatörde /
 * izin reddinde / EAS projectId yoksa sessizce no-op olur. Gerçek cihaz +
 * EAS build'de tam çalışır.
 */

// Bildirim ön planda gelince banner göster.
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

let lastToken: string | null = null;

function getProjectId(): string | null {
  // EAS projectId — app.json extra.eas.projectId veya easConfig.
  const fromExtra = (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)?.eas
    ?.projectId;
  const fromEas = (Constants as unknown as { easConfig?: { projectId?: string } }).easConfig?.projectId;
  return fromExtra ?? fromEas ?? null;
}

/** İzin iste + Expo token al + backend'e kaydet. Token döner (veya null). */
export async function registerForPush(): Promise<string | null> {
  try {
    if (Platform.OS === "web") return null;
    if (!Device.isDevice) return null; // simülatörde push yok

    const existing = await Notifications.getPermissionsAsync();
    let granted = existing.granted;
    if (!granted && existing.canAskAgain) {
      const req = await Notifications.requestPermissionsAsync();
      granted = req.granted;
    }
    if (!granted) return null;

    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "Bildirimler",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    const projectId = getProjectId();
    const tokenResp = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    const token = tokenResp.data;
    if (!token) return null;

    await apiRequest("/api/v2/me/push-token", {
      method: "POST",
      body: { token, platform: Platform.OS },
    });
    lastToken = token;
    return token;
  } catch (e) {
    // EAS projectId yok / Expo Go kısıtı / ağ — sessiz geç (özellik bozulmaz).
    if (__DEV__) console.warn("[push] register skipped:", e);
    return null;
  }
}

/** Çıkışta token'ı backend'den sil. */
export async function unregisterForPush(): Promise<void> {
  if (!lastToken) return;
  const token = lastToken;
  lastToken = null;
  try {
    await apiRequest(`/api/v2/me/push-token?token=${encodeURIComponent(token)}`, {
      method: "DELETE",
    });
  } catch {
    // best-effort
  }
}
