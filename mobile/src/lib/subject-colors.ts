/**
 * Ders renk sistemi — web `lib/subject-match.subjectHue` +
 * `components/shared/subject-tag.subjectColors` ile BİREBİR (2026-10-08).
 *
 * Aynı ders koçun web ekranında, öğrencinin web ve mobil ekranında aynı renkte
 * görünür. Web'deki tabloyu değiştirirsen bunu da güncelle.
 */

const SUBJECT_FIXED_HUE: [RegExp, number][] = [
  [/matematik/, 220],
  [/geometri/, 165],
  [/turkce|edebiyat|paragraf|dil bilgisi/, 350],
  [/fizik/, 32],
  [/kimya/, 275],
  [/biyoloji/, 130],
  [/tarih|inkilap/, 55],
  [/cografya/, 90],
  [/felsefe|din|sosyal/, 315],
  [/ingilizce|yabanci|dil$/, 195],
  [/fen/, 165],
];
const SUBJECT_PALETTE = [5, 50, 80, 125, 155, 200, 230, 260, 295, 335, 20, 110];

const TR_FOLD: Record<string, string> = {
  ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u",
};

/** Türkçe küçük harf (Hermes'te locale'e güvenmeden): İ→i, I→ı. */
function trLower(s: string): string {
  return s.trim().replace(/İ/g, "i").replace(/I/g, "ı").toLowerCase();
}

function nameHashNum(name: string): number {
  return Math.abs(
    Array.from(trLower(name)).reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 0),
  );
}

export function subjectHue(name: string): number {
  const low = trLower(name).replace(/[çğıöşü]/g, (ch) => TR_FOLD[ch] ?? ch);
  for (const [re, hue] of SUBJECT_FIXED_HUE) {
    if (re.test(low)) return hue;
  }
  return SUBJECT_PALETTE[nameHashNum(name) % SUBJECT_PALETTE.length];
}

export function subjectColors(name: string) {
  const hue = subjectHue(name);
  return {
    hue,
    tint: `hsl(${hue}, 65%, 91%)`,
    rail: `hsl(${hue}, 75%, 50%)`,
    chip: `hsl(${hue}, 60%, 36%)`,
  };
}

/** "TYT Matematik" → { exam: "TYT", plain: "Matematik" } */
export function splitExamPrefix(name: string): { exam: string | null; plain: string } {
  const m = /^(TYT|AYT|LGS)\s+(.+)$/i.exec(name);
  return m ? { exam: m[1].toUpperCase(), plain: m[2] } : { exam: null, plain: name };
}
