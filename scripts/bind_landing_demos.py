"""Anasayfa vitrin kartlarına demo videolarını bağla (idempotent).

Koç/öğrenci ilgili kartlara /demos'taki demo slug'ını ekler → kartta "Demo İzle"
butonu çıkar → demo_click telemetrisi gerçek olur.

İki aşama:
  1. AÇIK eşleme (kesfet-* seed kartları) — slug → demo.
  2. ANAHTAR-KELIME eşlemesi — slug/başlık/kategoride geçen kelimeye göre
     (AI-kümeleme `tema-*` kartları hash'li slug taşır + ileride değişebilir;
     içerik-bazlı eşleme bunları + gelecekteki kartları da kapsar).

Güvenli: yalnız demo_slug BOŞ olan + target_roles'unda teacher/student olan kartı
günceller (admin'in elle bağladığı demolar + kurum-özel kartlar korunur).
Tekrar çalıştırmak güvenli.

Çalıştır:  python -m scripts.bind_landing_demos
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import FeatureCard

DUR = "~2 dk"

# 1. AÇIK eşleme — kart slug → demo slug
DEMO_MAP: dict[str, str] = {
    "kesfet-erken-uyari": "dna-coach",
    "kesfet-ai-seans-hazirligi": "sessions-coach",
    "kesfet-ai-sesli-foto-not": "sessions-coach",
    "kesfet-surdurulebilir-plan": "program-create-coach",
    "kesfet-veli-bilgilendirme": "whatsapp-coach",
    "kesfet-tahsilat": "billing-coach",
}

# 2. ANAHTAR-KELIME eşlemesi — (kelimeler, demo). Sıra = öncelik (ilk eşleşen kazanır).
#    Kartın "kategori + başlık + slug" metninde (küçük harf) aranır.
KEYWORD_DEMOS: list[tuple[list[str], str]] = [
    (["whatsapp", "veli", "iletişim", "iletisim", "bilgilendirme"], "whatsapp-coach"),
    (["odak", "motivasyon"], "focus-coach"),
    (["müfredat", "mufredat", "kütüphane", "kutuphane", "kitap", "akademik"], "book-add-coach"),
    (["yapay zek", "seans", "yapay-zeka"], "sessions-coach"),
    (["tahsilat", "ücret", "ucret", "ödeme", "odeme"], "billing-coach"),
    (["erken uyar", "erken-uyar", "risk", "kopan", "deneme", "net trend"], "dna-coach"),
    (["program", "plan", "haftalık", "haftalik"], "program-create-coach"),
    (["konu performans"], "topic-performance"),
    (["hedef"], "goals-coach"),
    (["tekrar", "aralıklı", "aralikli"], "review-cards-coach"),
]


def _keyword_demo(card: FeatureCard) -> str | None:
    text = " ".join(filter(None, [
        (card.category_label or ""),
        (card.title or ""),
        (card.slug or ""),
    ])).lower()
    for words, demo in KEYWORD_DEMOS:
        if any(w in text for w in words):
            return demo
    return None


def main() -> int:
    explicit = keyword = skipped = no_match = 0
    with SessionLocal() as db:
        cards = db.query(FeatureCard).all()
        for card in cards:
            if (card.demo_slug or "").strip():
                skipped += 1
                continue
            roles = card.target_roles or []
            # demo havuzu koç/öğrenci → yalnız bu kitleyi taşıyan kart
            if not ({"teacher", "student"} & set(roles)):
                continue

            demo = DEMO_MAP.get(card.slug)
            if demo:
                card.demo_slug, card.demo_duration_label = demo, DUR
                explicit += 1
                print(f"  [AÇIK]    {card.slug} → {demo}")
                continue

            demo = _keyword_demo(card)
            if demo:
                card.demo_slug, card.demo_duration_label = demo, DUR
                keyword += 1
                print(f"  [KELIME]  {card.slug} → {demo}")
            else:
                no_match += 1
                print(f"  [EŞLEŞMEDİ] {card.slug} (uygun demo yok — boş bırakıldı)")
        db.commit()
    print(f"\n=== açık {explicit} · kelime {keyword} · atlandı(zaten var) {skipped} · eşleşmedi {no_match} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
