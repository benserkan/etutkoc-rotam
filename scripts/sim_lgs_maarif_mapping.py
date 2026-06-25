"""SİMÜLASYON — LGS + Maarif Lise müfredat eşleştirme performansı.

TYT/AYT analizinin (sim_tyt_mapping) eşdeğeri: gerçekçi yayınevi test-kitabı ünite
adlarını, GERÇEK auto-map mantığıyla (_label_key/_topic_key) seedlenen müfredat
konularına eşleştirip otomatik (AI'sız, kredisiz) eşleşme oranını ölçer.

DB GEREKMEZ — curriculum_data.py (seed kaynağı) + curriculum_mapping gerçek mantığı.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.curriculum_mapping import _label_key, _topic_key  # noqa: E402
from scripts.curriculum_data import (  # noqa: E402
    LGS_CURRICULUM, MAARIF_LISE_CURRICULUM,
)


def lgs_topic_names(spec, grade=None):
    return [n for (n, g) in spec.get("topics", []) if grade is None or g == grade]


def maarif_leaf_names(spec, grade=None):
    out = []
    for tup in spec["units"]:
        subs = tup[3] if len(tup) > 3 else []
        if grade is None or tup[2] == grade:
            out.extend(subs)
    return out


def auto_match(units, candidates):
    cand = {}
    for c in candidates:
        k = _topic_key(c)
        if k and k not in cand:
            cand[k] = c
    hits = [(u, cand.get(_label_key(u))) for u in units]
    return hits


def report(title, candidates, units, show_miss=True):
    hits = auto_match(units, candidates)
    matched = [(u, m) for u, m in hits if m]
    miss = [u for u, m in hits if not m]
    n = len(units)
    pct = 100 * len(matched) // n if n else 0
    print(f"\n{title}")
    print(f"   aday konu: {len(candidates)} · kitap ünitesi: {n} · "
          f"AUTO-MAP: {len(matched)}/{n} (%{pct})")
    if show_miss and miss:
        print(f"   eşleşmeyen: {', '.join(miss[:12])}" + (" …" if len(miss) > 12 else ""))
    return len(matched), n


# =============================================================================
# Gerçekçi yayınevi test-kitabı ünite listeleri (koçun gireceği tipik adlar)
# =============================================================================

# --- LGS (8. sınıf = LGS sınavı; 6. sınıf = okul-destek) ---
LGS_BOOKS = {
    "Matematik · 8. sınıf (LGS)": ("Matematik", [
        "1. Ünite — Çarpanlar ve Katlar", "2. Ünite — Üslü İfadeler",
        "3. Ünite — Kareköklü İfadeler", "4. Ünite — Veri Analizi",
        "5. Ünite — Basit Olayların Olasılığı", "6. Ünite — Cebirsel İfadeler ve Özdeşlikler",
        "7. Ünite — Doğrusal Denklemler", "8. Ünite — Eşitsizlikler",
        "9. Ünite — Üçgenler", "10. Ünite — Eşlik ve Benzerlik",
        "11. Ünite — Dönüşüm Geometrisi", "12. Ünite — Geometrik Cisimler",
    ]),
    "Matematik · 6. sınıf (okul)": ("Matematik", [
        "Doğal Sayılarla İşlemler", "Çarpanlar ve Katlar", "Kümeler", "Tam Sayılar",
        "Kesirlerle İşlemler", "Ondalık Gösterim", "Oran", "Cebirsel İfadeler",
        "Veri Toplama ve Değerlendirme", "Açılar", "Alan Ölçme", "Çember",
    ]),
    "Türkçe · 8. sınıf (LGS)": ("Türkçe", [
        "Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam", "Metin Türleri",
        "Sözel Mantık", "Fiilimsiler", "Cümlenin Ögeleri", "Fiilde Çatı",
        "Cümle Türleri", "Anlatım Bozuklukları", "Yazım Kuralları", "Noktalama İşaretleri",
    ]),
    "Fen Bilimleri · 8. sınıf (LGS)": ("Fen Bilimleri", [
        "Mevsimler ve İklim", "DNA ve Genetik Kod", "Basınç", "Madde ve Endüstri",
        "Basit Makineler", "Enerji Dönüşümleri ve Çevre Bilimi",
        "Elektrik Yükleri ve Elektrik Enerjisi",
    ]),
    "T.C. İnkılap · 8. sınıf (LGS)": ("T.C. İnkılap Tarihi ve Atatürkçülük", [
        "Bir Kahraman Doğuyor", "Millî Uyanış: Bağımsızlık Yolunda Atılan Adımlar",
        "Millî Bir Destan: Ya İstiklal Ya Ölüm!", "Atatürkçülük ve Çağdaşlaşan Türkiye",
        "Demokratikleşme Çabaları", "Atatürk Dönemi Türk Dış Politikası",
        "Atatürk'ün Ölümü ve Sonrası",
    ]),
}

# --- Maarif Lise: (a) resmi alt-başlık adlarıyla (b) geleneksel/yayınevi adlarıyla ---
MAARIF_BOOKS = {
    "Matematik · resmi alt-başlık adıyla": ("Matematik", [
        "Üslü ve Köklü İfadeler", "Gerçek Sayı Aralıkları",
        "Doğrusal Denklem ve Eşitsizlikler", "Üçgende Açı Özellikleri",
        "Karesel Fonksiyonlar", "Bölünebilme, Asal Çarpanlar, OBEB ve OKEK",
        "Polinom Fonksiyonlar", "Türev ve Türev Alma Kuralları",
    ]),
    "Matematik · yayınevi/geleneksel adla": ("Matematik", [
        "Kümeler", "Denklemler ve Eşitsizlikler", "Üslü Sayılar", "Köklü Sayılar",
        "Mutlak Değer", "Fonksiyonlar", "Polinomlar", "Trigonometri",
        "Türev", "İntegral", "Olasılık",
    ]),
    "Fizik · resmi alt-başlık adıyla": ("Fizik", None),  # ilk 10 leaf otomatik
    "Biyoloji · resmi alt-başlık adıyla": ("Biyoloji", None),
}


def main():
    print("=" * 72)
    print("LGS — yapı: DÜZ konu listesi (flat). 8. sınıf = geleneksel/sınav adları;")
    print("5-7. sınıf = yeni Maarif 'Tema:' adları (karma taksonomi).")
    print("=" * 72)
    lgs_tot = lgs_hit = 0
    for label, (subj, units) in LGS_BOOKS.items():
        cands = lgs_topic_names(LGS_CURRICULUM[subj])
        h, n = report(f"LGS · {label}", cands, units)
        lgs_hit += h; lgs_tot += n

    print("\n" + "=" * 72)
    print("MAARIF LİSE — yapı: Tema(parent) + alt-başlık(leaf). Eşleştirme adayı = LEAF.")
    print("=" * 72)
    mar_tot = mar_hit = 0
    for label, (subj, units) in MAARIF_BOOKS.items():
        leaves = maarif_leaf_names(MAARIF_LISE_CURRICULUM[subj])
        if units is None:
            units = leaves[:10]  # resmi adı birebir → tavan testi
        h, n = report(f"MAARIF · {label}", leaves, units)
        mar_hit += h; mar_tot += n

    print("\n" + "=" * 72)
    print("ÖZET (deterministik auto-map; AI/kredi YOK):")
    print(f"  LGS toplam     : {lgs_hit}/{lgs_tot}  (%{100*lgs_hit//lgs_tot if lgs_tot else 0})")
    print(f"  MAARIF toplam  : {mar_hit}/{mar_tot}  (%{100*mar_hit//mar_tot if mar_tot else 0})")
    print("\nNot: eşleşmeyen kalan = AI semantik öneri + koç onayı ile çözülür.")


if __name__ == "__main__":
    main()
