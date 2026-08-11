"""Ortak Kitap Kataloğu — 345 TYT Matematik Soru Bankası seed'i (İLK GERÇEK KAYIT).

2026-08-11 gerçek-kitap denemesinin ürünü: yapı 416 sayfalık kitabın kendisinden
çıkarıldı (içindekiler = 30 konu; test adetleri tam-gövde taramasıyla).
SAYIM YÖNTEMİ (v2 — kullanıcı v1'de hata yakaladı, Mutlak Değer 9 yerine 7):
kitapta 3 soru kategorisi var (Klasikleşmiş TEST N / ÖSYM Tadında Sorular N /
Orijinal Sorular N), numaralar kategori başına 1'den başlar ve BANT TESTİN HER
SAYFASINDA TEKRARLANIR → doğru ölçü bant SAYISI DEĞİL, kategori başına EN BÜYÜK
numara toplamı + 1..N zincir denetimi + ÇİFT bağımsız tarama karşılaştırması.
v2'de iki tarama 30/30 konuda birebir uyuştu, zincir kopukluğu 0, Mutlak
Değer=9 kullanıcı sayımıyla doğrulandı. Toplam 202 test.
Müfredat eşleştirmesi: 26 deterministik (alias katmanı) + 3 elle küratörlü
(görsel-mantık bölümleri → Sayısal Yetenek Problemleri); "Tanım ve Formül
Kullanabilme" bilinçli eşsiz (taksonomide karşılığı yok).

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
    ("Gerçel Sayılar - 1", 12, None),
    ("Gerçel Sayılar - 2", 8, None),
    ("Faktöriyel Kavramı", 2, None),
    ("Basamak Kavramı", 4, None),
    ("Görsel Zeka", 5, "Sayısal Yetenek Problemleri"),
    ("Sayısal - Sözel Mantık", 3, "Sayısal Yetenek Problemleri"),
    ("Örüntülü Sayı Grupları", 6, "Sayısal Yetenek Problemleri"),
    ("I ve II Bilinmeyenli Denklemler", 5, None),
    ("I ve II Bilinmeyenli Eşitsizlikler", 7, None),
    ("Mutlak Değer", 9, None),
    ("Üslü Sayılar", 10, None),
    ("Köklü Sayılar", 11, None),
    ("Tanım ve Formül Kullanabilme", 2, None),  # taksonomide karşılığı yok — eşsiz kalır
    ("Oran - Orantı", 7, None),
    ("Çarpanlara Ayırma", 7, None),
    ("Sayı Problemleri", 16, None),
    ("Kesir Problemleri", 7, None),
    ("Yaş Problemleri", 8, None),
    ("Yüzde Problemleri", 9, None),
    ("Karışım Problemleri", 6, None),
    ("Hız Problemleri", 8, None),
    ("Grafik Yorumlama", 4, None),
    ("Emek Problemleri", 3, None),
    ("Asal Çarpanlar", 3, None),
    ("Bölme - Bölünebilme", 5, None),
    ("EBOB - EKOK", 5, None),
    ("Mantık", 6, None),
    ("Kümeler - Kartezyen Çarpım", 7, None),
    ("Fonksiyonlar", 10, None),
    ("Sayma - Olasılık", 7, None),
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
