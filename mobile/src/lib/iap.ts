/**
 * Apple IAP (RevenueCat) sarmalayıcı — App Store 3.1.1 çözümü.
 *
 * OTA GÜVENLİĞİ: react-native-purchases NATİVE modüldür — yalnız yeni EAS
 * build'de bulunur. Dinamik require + try/catch ile eski kurulumda uygulama
 * ÇÖKMEZ; IAP yalnız "desteklenmiyor" davranır (expo-document-picker deseni).
 *
 * Kimlik: RevenueCat appUserID = backend User.id (string) — webhook/sync
 * bu id ile planı aktive eder. iOS public SDK anahtarı (appl_...) app.json
 * extra.revenueCatIosKey'de gömülüdür (public anahtar — gömülmesi güvenlidir).
 */
import Constants from "expo-constants";
import { Platform } from "react-native";

let Purchases: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  Purchases = require("react-native-purchases").default;
} catch {
  Purchases = null;
}

const IOS_KEY: string =
  ((Constants.expoConfig?.extra as Record<string, unknown> | undefined)
    ?.revenueCatIosKey as string | undefined) ?? "";

/** App Store ürün kimliği → solo plan kodu (backend PRODUCT_PLANS ile birebir). */
export const IAP_PRODUCT_TIERS: Record<string, string> = {
  rotam_solo_pro_monthly: "solo_pro",
  rotam_solo_elite_monthly: "solo_elite",
  rotam_solo_unlimited_monthly: "solo_unlimited",
};

let configuredFor: number | null = null;

/** Bu kurulumda satın alma yapılabilir mi (iOS + native modül + anahtar). */
export function iapSupported(): boolean {
  return Platform.OS === "ios" && Purchases != null && IOS_KEY.length > 0;
}

/** Girişte çağrılır — RevenueCat'i kullanıcının backend id'siyle bağlar. */
export async function configureIap(userId: number): Promise<boolean> {
  if (!iapSupported()) return false;
  try {
    if (configuredFor === null) {
      Purchases.configure({ apiKey: IOS_KEY, appUserID: String(userId) });
    } else if (configuredFor !== userId) {
      await Purchases.logIn(String(userId));
    }
    configuredFor = userId;
    return true;
  } catch {
    return false;
  }
}

/** Çıkışta çağrılır (best-effort). */
export async function iapLogout(): Promise<void> {
  if (configuredFor == null || Purchases == null) return;
  configuredFor = null;
  try {
    await Purchases.logOut();
  } catch {
    // anonim kullanıcıda logOut hata verir — önemsiz
  }
}

export interface IapPackage {
  productId: string;
  tierCode: string; // solo_pro | solo_elite | solo_unlimited
  priceString: string; // StoreKit yerelleştirilmiş fiyat ("₺2.499,99")
  title: string;
  rcPackage: unknown; // satın almada geri verilecek RevenueCat paketi
}

/** Mağazadaki solo paketleri (RevenueCat current offering'den). */
export async function getIapPackages(): Promise<IapPackage[]> {
  if (!iapSupported()) return [];
  const offerings = await Purchases.getOfferings();
  const pkgs: any[] = offerings?.current?.availablePackages ?? [];
  const out: IapPackage[] = [];
  for (const p of pkgs) {
    const pid: string = p?.product?.identifier ?? "";
    const tier = IAP_PRODUCT_TIERS[pid];
    if (!tier) continue;
    out.push({
      productId: pid,
      tierCode: tier,
      priceString: p?.product?.priceString ?? "",
      title: p?.product?.title ?? "",
      rcPackage: p,
    });
  }
  return out;
}

/** StoreKit satın alma sayfasını açar. cancelled=true → kullanıcı vazgeçti. */
export async function purchaseIapPackage(
  pkg: IapPackage,
): Promise<{ ok: boolean; cancelled: boolean }> {
  try {
    await Purchases.purchasePackage(pkg.rcPackage);
    return { ok: true, cancelled: false };
  } catch (e: any) {
    if (e?.userCancelled) return { ok: false, cancelled: true };
    throw e;
  }
}

/** "Satın alımları geri yükle" (Apple zorunlu akış). */
export async function restoreIapPurchases(): Promise<void> {
  if (!iapSupported()) return;
  await Purchases.restorePurchases();
}
