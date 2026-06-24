"""SİMÜLASYON — TYT Matematik kitabı → resmi müfredat eşleştirme analizi.

Amaç: kullanıcının "4K TYT Matematik" kitabında müfredat eşleştirmesinin
neredeyse hiç çalışmamasının (sadece Olasılık eşleşti) sayısal kanıtını üretmek
ve alternatif bir resmi-konu taksonomisinin (TYT-kanonik) ne kadar iyileştirme
getireceğini ölçmek.

DB GEREKMEZ — gerçek `normalize` mantığı (curriculum_mapping ile birebir) +
curriculum_data.py resmi konu listeleri kullanılır. Yalnız deterministik
auto-map (exact normalize) ölçülür + elle "anlamsal tavan" (AI'nin en iyi
ihtimalle yakalayabileceği) işaretlenir.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.curriculum_data import (  # noqa: E402
    KLASIK_LISE_CURRICULUM,
    MAARIF_LISE_CURRICULUM,
)

# Gerçek/sevk edilen eşleştirme katmanı (Aşama 1) — auto-map ile BİREBİR.
from app.services.curriculum_mapping import _label_key, _topic_key  # noqa: E402


# --- Ekran görüntüsündeki 4K TYT Matematik kitabının 34 ünitesi (Image #1) ---
BOOK_UNITS = [
    "1. Ünite — Temel Kavramlar",
    "2. Ünite — Bölme, Bölünebilme",
    "3. Ünite — Rasyonel Sayılar",
    "4. Ünite — Birinci Dereceden Denklemler",
    "5. Ünite — Basit Eşitsizlikler",
    "6. Ünite — Üslü İfadeler",
    "7. Ünite — Köklü İfadeler",
    "8. Ünite — Çarpanlara Ayırma",
    "9. Ünite — Oran ve Orantı",
    "10. Ünite — Sayı - Kesir Problemleri",
    "11. Ünite — İşçi Problemleri",
    "12. Ünite — Yüzde Problemleri",
    "13. Ünite — Mantık",
    "14. Ünite — Kümeler",
    "15. Ünite — Fonksiyonlar",
    "16. Ünite — Polinomlar",
    "17. Ünite — Permütasyon",
    "18. Ünite — Olasılık",
    "19. Ünite — Veri ve İstatistik",
    "Tek/Çift Sayılar",
    "Ardışık Sayılar",
    "Asal Sayılar ve Tam Bölen Sayıları",
    "Faktöriyel Kavramı",
    "Sayı Basamakları",
    "Ebob Ekok",
    "Mutlak Değer",
    "Yaş Problemleri",
    "Kar Zarar Problemleri",
    "Karışım Problemleri",
    "Hareket Problemleri",
    "Grafik Problemleri",
    "Sayısal Yetenek Problemleri",
    "Kombinasyon",
    "Binom",
]


def leaf_names_maarif(subject):
    """Maarif: units = (no, ad, sınıf, [alt başlıklar]) → alt başlıklar = LEAF."""
    out = []
    for tup in subject["units"]:
        subs = tup[3] if len(tup) > 3 else []
        out.extend(subs)
    return out


def leaf_names_klasik(subject):
    return [t[0] for t in subject["topics"]]


# Önerilen TYT-KANONİK Matematik konu seti (ÖSYM/yayınevi taksonomisi).
# Bu, test kitaplarının konuştuğu dildir; bir kez resmi konu olarak seed edilirse
# tüm TYT Mat kitapları otomatik eşleşir.
TYT_CANONICAL_MAT = [
    "Temel Kavramlar", "Sayı Basamakları", "Bölme ve Bölünebilme", "EBOB EKOK",
    "Rasyonel Sayılar", "Basit Eşitsizlikler", "Mutlak Değer", "Üslü İfadeler",
    "Köklü İfadeler", "Çarpanlara Ayırma", "Oran ve Orantı",
    "Birinci Dereceden Denklemler", "Sayı - Kesir Problemleri", "Yaş Problemleri",
    "Yüzde Problemleri", "Kar Zarar Problemleri", "Karışım Problemleri",
    "İşçi Problemleri", "Hareket Problemleri", "Grafik Problemleri",
    "Sayısal Yetenek Problemleri", "Kümeler", "Mantık", "Fonksiyonlar",
    "Polinomlar", "Permütasyon", "Kombinasyon", "Binom", "Olasılık",
    "Veri ve İstatistik", "Tek ve Çift Sayılar", "Ardışık Sayılar",
    "Asal Sayılar", "Faktöriyel",
]


def auto_match(units, candidates, use_strip=False):
    """Gerçek auto-map: _topic_key (resmi konu) ↔ _label_key (kitap etiketi).

    use_strip=False → ham (eski davranış: önek temizlenmemiş kaba normalize).
    use_strip=True  → Aşama 1 sevk edilen katman (_label_key: önek+bağlaç+alias).
    """
    cand = {}
    for c in candidates:
        k = _topic_key(c)
        if k and k not in cand:
            cand[k] = c
    hits = []
    for u in units:
        key = _label_key(u) if use_strip else re.sub(r"[^a-z0-9]+", " ",
                                                     u.lower().translate(
            str.maketrans("çğıöşüâîû", "cgiosuaiu"))).strip()
        hits.append((u, cand.get(key)))
    return hits


def report(title, candidates, units, use_strip=False):
    hits = auto_match(units, candidates, use_strip=use_strip)
    matched = [(u, m) for u, m in hits if m]
    print(f"\n{'='*70}\n{title}")
    print(f"Aday resmi konu sayısı: {len(candidates)}")
    tag = "AUTO-MAP + önek-temizleme" if use_strip else "AUTO-MAP (ham normalize)"
    print(f"{tag} eşleşme: {len(matched)}/{len(units)}")
    for u, m in matched:
        print(f"   ✓ {u!r:42} → {m!r}")
    return len(matched)


def main():
    units = BOOK_UNITS
    print(f"Kitap: 4K Yayınları TYT Matematik — {len(units)} ünite")

    klasik = leaf_names_klasik(KLASIK_LISE_CURRICULUM["Matematik"])
    maarif = leaf_names_maarif(MAARIF_LISE_CURRICULUM["Matematik"])

    a = report("A) MEVCUT — Klasik Lise Matematik (Efe 12.sınıf → KLASIK kohort)",
               klasik, units)
    b = report("B) ALT — Maarif Lise Matematik (tema-bazlı LEAF alt başlıklar)",
               maarif, units)
    c = report("C) ÖNERİ-1 — TYT-Kanonik konu seti, HAM auto-map (önek temizlenmemiş)",
               TYT_CANONICAL_MAT, units)
    d = report("D) ÖNERİ-2 — TYT-Kanonik konu seti + ÖNEK TEMİZLEME (ücretsiz, AI'sız)",
               TYT_CANONICAL_MAT, units, use_strip=True)

    n = len(units)
    print(f"\n{'='*70}\nÖZET (deterministik auto-map; AI/kredi YOK):")
    print(f"  A) Klasik Lise Mat (mevcut)        : {a}/{n}  (%{100*a//n})")
    print(f"  B) Maarif Lise Mat                 : {b}/{n}  (%{100*b//n})")
    print(f"  C) TYT-Kanonik (ham)               : {c}/{n}  (%{100*c//n})")
    print(f"  D) TYT-Kanonik + önek temizleme    : {d}/{n}  (%{100*d//n})")
    print("\nNot: A = kullanıcının yaşadığı durum. Klasik Lise Mat 11-12 konuları")
    print("(Trigonometri/Türev/İntegral...) → TYT 9-10 temelleri sistemde YOK.")
    print("D = aynı sorunun AI/kredi olmadan, önek temizleyici + kanonik set ile çözümü.")


if __name__ == "__main__":
    main()
