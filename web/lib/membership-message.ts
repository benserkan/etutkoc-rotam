/**
 * WhatsApp üyelik teklifi — tek kaynak mesaj metni.
 *
 * İki senaryo (offer_type):
 *  - "renewal": üyelik bitiyor → kesintisiz devam vurgusu + teklif + tek-tık yenile.
 *  - "new" (varsayılan): ETÜTKOÇ Rotam'ın ne sunduğunu anlatan bilgi-ağırlıklı
 *    tanıtım + sana özel üyelik teşviki → detaylar için sayfaya yönlendir.
 *
 * Click-to-WhatsApp (wa.me) gönderiminde mesaj metni içine link konur; WhatsApp
 * linkin OG önizleme kartını mesajın ÜSTÜNDE gösterir. Bu yüzden metin amaç-net +
 * değer-odaklı, link en sonda verilir (ham URL gürültüsü en aza iner).
 *
 * EMOJİ YOK: 👇/👋/📦 gibi emojiler bazı cihaz/WhatsApp font'larında "tofu"
 * (kırık kutu ⬚) çıkıyor → amatör görünüm. Yalnız ASCII-güvenli "•" (tipografik
 * madde imi, emoji değil) ve "₺" kullanılır.
 */

function fmtTry(n: number): string {
  return new Intl.NumberFormat("tr-TR").format(n);
}

const CYCLE_SHORT: Record<string, string> = {
  monthly: "ay",
  annual: "akademik yıl",
};

export interface MembershipWaTextArgs {
  offerType: string | null;
  targetName: string | null;
  planLabel: string;
  amount: number | null;
  cycle: string | null;
  url: string;
}

export function buildMembershipWaText({
  offerType,
  targetName,
  planLabel,
  amount,
  cycle,
  url,
}: MembershipWaTextArgs): string {
  const greet = `Merhaba${targetName ? " " + targetName : ""},`;
  const priceLine =
    amount && amount > 0
      ? `${planLabel} · ${fmtTry(amount)} ₺ / ${CYCLE_SHORT[cycle ?? "monthly"] ?? "ay"}`
      : planLabel;

  if (offerType === "renewal") {
    return [
      greet,
      "",
      "ETÜTKOÇ Rotam üyeliğin sona eriyor. Öğrencilerinin programı, deneme takibi ve veli bildirimleri kesintisiz devam etsin diye sana özel yenileme teklifini hazırladık.",
      "",
      `Teklifin: ${priceLine}`,
      "",
      "Kaldığın yerden tek tıkla devam et:",
      url,
    ].join("\n");
  }

  return [
    greet,
    "",
    "ETÜTKOÇ Rotam ile öğrenci koçluğunu tek panelden yönetirsin:",
    "• Günlük & haftalık program + kaynak takibi",
    "• Deneme net analizi ve gelişim grafiği",
    "• Veliye otomatik bilgilendirme",
    "• Yapay zekâ ile seans hazırlığı",
    "• Kopan öğrenciyi erkenden yakalama",
    "",
    `Sana özel üyelik teklifi: ${priceLine}`,
    "",
    "Detayları gör, üyeliğini başlat:",
    url,
  ].join("\n");
}
