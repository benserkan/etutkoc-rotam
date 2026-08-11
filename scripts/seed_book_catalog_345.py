"""Ortak Kitap Kataloğu — 345 TYT Matematik Soru Bankası seed'i (İLK GERÇEK KAYIT).

2026-08-11 gerçek-kitap denemesinin ürünü: yapı 416 sayfalık kitabın kendisinden
çıkarıldı (içindekiler = 30 konu; test adetleri sayfa-şeridi taramasıyla sayıldı
— kitapta 3 soru kategorisi var [Klasikleşmiş/ÖSYM Tadında/Orijinal], TEST
numarası kategori başına yeniden başlıyor; adet = numaralı bant sayısı).
Toplam 216 test. Müfredat eşleştirmesi: 26 deterministik (alias katmanı) +
3 elle küratörlü (görsel-mantık bölümleri → Sayısal Yetenek Problemleri);
"Tanım ve Formül Kullanabilme" bilinçli eşsiz (taksonomide karşılığı yok).

İdempotent: aynı ad+yayınevi katalogda varsa dokunmaz. `--reset` siler + yeniden
kurar (usage_count sıfırlanır — yalnız gerekiyorsa).
Kullanım: PYTHONPATH=. python -m scripts.seed_book_catalog_345 [--reset]
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import BookTemplate, BookType, Subject, Topic
from app.services import book_catalog as svc

NAME = "345 TYT Matematik Soru Bankası"
PUBLISHER = "345 Yayınları"
SUBJECT_NAME = "TYT Matematik"

# (bölüm adı, test adedi, elle küratörlü konu adı | None=auto-map'e bırak)
SECTIONS: list[tuple[str, int, str | None]] = [
    ("Gerçel Sayılar - 1", 8, None),
    ("Gerçel Sayılar - 2", 8, None),
    ("Faktöriyel Kavramı", 4, None),
    ("Basamak Kavramı", 5, None),
    ("Görsel Zeka", 5, "Sayısal Yetenek Problemleri"),
    ("Sayısal - Sözel Mantık", 3, "Sayısal Yetenek Problemleri"),
    ("Örüntülü Sayı Grupları", 4, "Sayısal Yetenek Problemleri"),
    ("I ve II Bilinmeyenli Denklemler", 6, None),
    ("I ve II Bilinmeyenli Eşitsizlikler", 8, None),
    ("Mutlak Değer", 7, None),
    ("Üslü Sayılar", 10, None),
    ("Köklü Sayılar", 17, None),
    ("Tanım ve Formül Kullanabilme", 2, None),  # taksonomide karşılığı yok — eşsiz kalır
    ("Oran - Orantı", 8, None),
    ("Çarpanlara Ayırma", 8, None),
    ("Sayı Problemleri", 13, None),
    ("Kesir Problemleri", 8, None),
    ("Yaş Problemleri", 12, None),
    ("Yüzde Problemleri", 10, None),
    ("Karışım Problemleri", 6, None),
    ("Hız Problemleri", 6, None),
    ("Grafik Yorumlama", 2, None),
    ("Emek Problemleri", 4, None),
    ("Asal Çarpanlar", 2, None),
    ("Bölme - Bölünebilme", 6, None),
    ("EBOB - EKOK", 6, None),
    ("Mantık", 8, None),
    ("Kümeler - Kartezyen Çarpım", 8, None),
    ("Fonksiyonlar", 12, None),
    ("Sayma - Olasılık", 10, None),
]


def main() -> int:
    reset = "--reset" in sys.argv
    with SessionLocal() as db:
        existing = svc.find_duplicate(db, NAME, PUBLISHER)
        if existing is not None:
            if not reset:
                print(f"Zaten katalogda (id={existing.id}, {existing.catalog_status}) — dokunulmadı.")
                return 0
            db.delete(existing)
            db.flush()
            print(f"--reset: eski kayıt (id={existing.id}) silindi.")

        subj = (
            db.query(Subject)
            .filter(Subject.name == SUBJECT_NAME, Subject.is_builtin.is_(True))
            .first()
        )
        if subj is None:
            print(f"HATA: builtin '{SUBJECT_NAME}' dersi yok (seed_exam_curriculum koşmalı).")
            return 1
        by_name = {
            t.name: t.id
            for t in db.query(Topic).filter(
                Topic.subject_id == subj.id, Topic.is_builtin.is_(True),
            )
        }
        entry = svc.create_entry(
            db,
            name=NAME,
            publisher=PUBLISHER,
            book_type=BookType.SORU_BANKASI,
            subject_id=subj.id,
            target_grade_min=11,
            target_grade_max=12,
            target_graduate=True,
            sections=[
                {"label": label, "test_count": tc, "topic_id": by_name.get(curated) if curated else None}
                for label, tc, curated in SECTIONS
            ],
            status="verified",
            source="admin_seed",
            dedup=True,
        )
        db.commit()
        db.refresh(entry)
        mapped = sum(1 for s in entry.sections if s.topic_id is not None)
        total = sum(s.default_test_count for s in entry.sections)
        print(
            f"Kataloğa eklendi: '{entry.name}' (id={entry.id}, verified) — "
            f"{len(entry.sections)} bölüm · {total} test · {mapped}/{len(entry.sections)} müfredat eşli"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
