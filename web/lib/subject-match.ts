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
  ["türk dili ve edebiyatı", "türk edebiyatı", "edebiyat"],
];

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
