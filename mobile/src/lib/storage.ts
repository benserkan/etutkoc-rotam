import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

/**
 * Token saklama soyutlaması. Native → expo-secure-store (şifreli keychain/
 * keystore). Web (UX screenshot/önizleme) → localStorage (secure-store web'de
 * yok). Aynı API ile her iki platform.
 */
function webStore(): Storage | null {
  try {
    return (globalThis as unknown as { localStorage?: Storage }).localStorage ?? null;
  } catch {
    return null;
  }
}

export async function storageGet(key: string): Promise<string | null> {
  if (Platform.OS === "web") return webStore()?.getItem(key) ?? null;
  return SecureStore.getItemAsync(key);
}

export async function storageSet(key: string, value: string): Promise<void> {
  if (Platform.OS === "web") {
    webStore()?.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

export async function storageDelete(key: string): Promise<void> {
  if (Platform.OS === "web") {
    webStore()?.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}
