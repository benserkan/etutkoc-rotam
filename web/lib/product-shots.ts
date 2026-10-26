/**
 * Tanıtım sayfalarındaki ürün ekranları (web/public/urun, 2x yakalama —
 * scripts/capture_marketing_shots.py). Boyutlar next/image için gerçek piksel.
 */
export const SHOT_SIZES: Record<string, [number, number]> = {
  "brans-karne": [1800, 977],
  "deneme-ders-isi": [1800, 1083],
  "deneme-firsat": [1800, 1059],
  "deneme-gidisat": [1800, 884],
  "deneme-konu-isi": [1800, 1084],
  "deneme-seans": [1800, 629],
  "deneme-son": [1800, 812],
  "gun-karti": [1222, 1483],
  "hafta-izgara": [1800, 980],
  "havuz-dersler": [1400, 933],
  "ilerleme-bu-hafta": [1800, 1112],
  "ilerleme-gidisat": [1800, 1438],
  "koc-seans": [1800, 1832],
  "kurum-akademik": [1800, 1663],
  "kurum-karne": [1800, 690],
  "kurum-mudahale": [1800, 1267],
  "kurum-pano": [1800, 1399],
  "kurum-uyum": [1800, 1186],
  "mufredat-dersler": [1800, 1505],
  "ogr-gelisim-hero": [1800, 1249],
  "pdf-aktar": [1797, 1086],
  "sube-ders-programi": [1400, 1077],
};

export interface Shot {
  src: string;
  alt: string;
  width: number;
  height: number;
  /** Tarayıcı çerçevesindeki adres çubuğunda görünen yol. */
  url: string;
}

export function shot(name: string, alt: string, url: string): Shot {
  const size = SHOT_SIZES[name];
  if (!size) throw new Error(`Bilinmeyen ürün ekranı: ${name}`);
  return { src: `/urun/${name}.webp`, alt, width: size[0], height: size[1], url };
}
