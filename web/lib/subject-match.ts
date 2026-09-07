/**
 * Görev başlığından ders eşleştirme — TEK MERKEZ.
 *
 * Branş/genel denemeler kitapsız olduğundan ders backend'den gelmez; görev adı
 * okunup hangi derse ait olduğu çıkarılır (örn. "AYT Matematik Branş Denemesi"
 * → Matematik). Editör (week-day-card), Hafta Izgarası (week-grid) ve yazdırma
 * (print) AYNI bu modülü kullanır — alias/kural değişikliği tek yerde yapılır.
 */

export type SubjectRef = { id: number; name: string };

// Ders adı eşanlamlıları — branş/genel deneme başlığında dersin TAM adı
// geçmeyebilir (örn. "AYT Edebiyat Branş" ama ders adı "Türk Dili ve Edebiyatı").
// Bir gruptaki HERHANGİ bir terim bir derse denk gelirse, grubun TÜM terimleri
// o ders için başlıkta aranır. Yeni alias gerekince buraya grup ekle.
// (Kısa/çok genel terimlerden kaçın — yanlış-pozitif riski; min 3 harf zaten var.)
const SUBJECT_ALIAS_GROUPS: string[][] = [
  // TYT/AYT'de ders adı "Türk Dili ve Edebiyatı"; başlıkta "Türkçe"/"Edebiyat"
  // geçebilir → hepsi aynı derse eşlensin.
  ["türk dili ve edebiyatı", "türk edebiyatı", "türkçe", "edebiyat"],
  // "Din" tek başına kısa ama Türkçe ı/i ayrımı koruyor ("aydın" = ı, eşleşmez)
  // + en-uzun-terim kazanır (başlıkta başka ders varsa o seçilir). Branş başlığı
  // "AYT Din Branş" gibi salt "din" içerebildiği için bilinçli eklendi.
  ["din kültürü ve ahlak bilgisi", "din kültürü", "dkab", "din"],
];

// --------------------------------------------------------------------------
// Ders grubu anahtarı + rengi — ADA göre (id'ye göre DEĞİL). Aynı ders adı
// farklı müfredat modelinde ayrı Subject kaydı olabilir (farklı id); bir
// öğrencinin programında "Fizik" testi ile "Fizik" branş denemesi TEK grupta
// birleşsin diye anahtar/renk daima normalize ADdan türetilir.
// --------------------------------------------------------------------------

export function normSubjectName(name: string): string {
  return name.trim().toLocaleLowerCase("tr");
}

export function subjectGroupKey(name: string): string {
  return `s:${normSubjectName(name)}`;
}

function nameHashNum(name: string): number {
  return Math.abs(
    Array.from(normSubjectName(name)).reduce(
      (h, c) => (h * 31 + c.charCodeAt(0)) | 0,
      0,
    ),
  );
}

/**
 * Ders adı → hue. Aynı ad daima aynı renk.
 *
 * 2026-09-08: `hash % 360` sürekli hue üretiyordu → iki ders rastgele 10°
 * arayla düşebiliyordu (ölçüm: Fizik ↔ Türkçe satır zemini ΔE 1,1 = aynı
 * renk). Gün kartında ders artık ZEMİN rengiyle okunuyor; birbirine yakın
 * iki hue tasarımı boşa çıkarır.
 *
 * İki katman: (1) yaygın dersler SABİT hue (Matematik hep mavi, Türkçe hep
 * kırmızı — koç öğrencinin tamamında aynı rengi görür); (2) diğerleri 12'lik
 * AYRIK paletten (30° aralık) hash ile. Sabit atamalar paletle çakışmaz diye
 * palet kovaları sabitlerin arasına yerleştirildi.
 */
const SUBJECT_FIXED_HUE: Array<[RegExp, number]> = [
  [/matematik/, 215],     // mavi
  [/geometri/, 190],      // turkuaz
  [/turkce|edebiyat|paragraf|dil bilgisi/, 355], // kırmızı
  [/fizik/, 25],          // turuncu
  [/kimya/, 280],         // mor
  [/biyoloji/, 140],      // yeşil
  [/tarih|inkilap/, 40],  // kahve-altın
  [/cografya/, 95],       // yeşil-sarı
  [/felsefe|din|sosyal/, 320], // pembe-mor
  [/ingilizce|yabanci|dil$/, 170], // deniz yeşili
  [/fen/, 160],           // yeşil-turkuaz
];
const SUBJECT_PALETTE = [5, 50, 80, 125, 155, 200, 230, 260, 295, 335, 20, 110];

const TR_FOLD: Record<string, string> = {
  ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u", i̇: "i",
};

export function subjectHue(name: string): number {
  // Türkçe harfleri sadeleştir ki "Türkçe" → "turkce" regex'e uysun
  const low = normSubjectName(name).replace(/[çğıöşü]/g, (ch) => TR_FOLD[ch] ?? ch);
  for (const [re, hue] of SUBJECT_FIXED_HUE) {
    if (re.test(low)) return hue;
  }
  return SUBJECT_PALETTE[nameHashNum(name) % SUBJECT_PALETTE.length];
}

/** Ders adına göre stabil ton indeksi (0..n-1) — Tailwind ton paleti için. */
export function subjectToneIndex(name: string, n: number): number {
  return nameHashNum(name) % n;
}

function aliasTermsFor(nameLow: string): string[] {
  for (const group of SUBJECT_ALIAS_GROUPS) {
    if (group.some((t) => nameLow.includes(t) || t.includes(nameLow))) return group;
  }
  return [];
}

/** Ders adı TAM eşleşme — "{Ders} · ..." öneki (video/özet/tekrar/diğer/blok) için. */
export function findSubjectByExactName(
  name: string,
  subjects?: SubjectRef[],
): SubjectRef | null {
  if (!subjects?.length) return null;
  const low = name.trim().toLocaleLowerCase("tr");
  return subjects.find((s) => s.name.toLocaleLowerCase("tr") === low) ?? null;
}

/**
 * Başlık içinde ders adı (veya alias'ı) ara — branş/genel deneme için.
 * Eşleşen en UZUN terime sahip ders kazanır (yanlış-pozitif/çakışma azaltma).
 * En az 3 harf.
 */
export function findSubjectInTitle(
  title: string,
  subjects?: SubjectRef[],
): SubjectRef | null {
  if (!subjects?.length) return null;
  const low = title.toLocaleLowerCase("tr");
  let best: SubjectRef | null = null;
  let bestLen = 0;
  for (const s of subjects) {
    const nameLow = s.name.toLocaleLowerCase("tr");
    const terms = [nameLow, ...aliasTermsFor(nameLow)].filter((t) => t.length >= 3);
    for (const t of terms) {
      if (low.includes(t) && t.length > bestLen) {
        best = s;
        bestLen = t.length;
      }
    }
  }
  return best;
}
