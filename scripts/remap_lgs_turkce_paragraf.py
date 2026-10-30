"""LGS 8 Türkçe — paragraf/söz varlığı alt konularına geriye dönük taşıma (2026-10-30).

Saha bulgusu (Neslihan Hoca #176, Arı "Paragrafın Ritmi"): LGS 8 Türkçe'de paragraf
tek başlıktı ("Paragrafta Anlam"); yayınevlerinin "Paragrafta Yapı", "Yardımcı
Düşünce", "Anlatım Teknikleri", "Deyimler" bölümleri ya genel başlığa yığıldı ya da
hiç bağlanmadı. Müfredata 7 alt konu eklendi (scripts/curriculum_data.py); bu betik
mevcut bağları yeni konulara taşır.

Kural (tutucu):
  · Yalnız LGS Türkçe (builtin) dersindeki kitap bölümleri, katalog bölümleri ve
    deneme soru satırları.
  · Yalnız şu an GENEL "Paragrafta Anlam" (8. sınıf) ya da BOŞ olanlar taşınır;
    ayrıca bilinen yanlış eşleme: "anlatım yönü/biçimi/tekniği" adlı bölümün
    "Anlatım Bozuklukları"na bağlanması.
  · Hedef yalnız YENİ alt konulardan biri olabilir; belirsizlikte dokunulmaz.
  · exact/alias/contain eşleşmesi gerekir; esnek (fuzzy/partial) eşleşme yalnız
    kitabın adında "paragraf" geçiyorsa kabul edilir ("Yapı" tek başına).
  · Elle düzeltilmiş deneme satırına dokunulmaz.

Kullanım:  python -m scripts.remap_lgs_turkce_paragraf          # kuru çalışma
           python -m scripts.remap_lgs_turkce_paragraf --apply  # uygula
"""
from __future__ import annotations

import sys

from app.database import SessionLocal
from app.models import Book, BookSection, Topic
from app.models.book import BookTemplate, BookTemplateSection
from app.models.curriculum import Subject
from app.models.exam_result import ExamResultQuestion
from app.services.curriculum_mapping import _label_key, _topics_by_norm, resolve_label

NEW_TOPICS = (
    "Söz Varlığı (Deyim ve Atasözleri)", "Paragrafta Ana Düşünce",
    "Paragrafta Yardımcı Düşünce", "Paragrafta Yapı",
    "Anlatım Biçimleri ve Düşünceyi Geliştirme Yolları", "Metin Karşılaştırma",
    "Söz Sanatları",
)
STRICT = {"exact", "tail", "contain", "learned"}
ANLATIM_HINTS = ("anlatim yon", "anlatim bicim", "anlatim teknik", "anlatim yontem", "dusunceyi gelistir")


def main() -> int:
    apply = "--apply" in sys.argv
    db = SessionLocal()
    subj = (db.query(Subject)
            .filter(Subject.name == "Türkçe", Subject.is_builtin.is_(True), Subject.curriculum_model == "lgs")
            .first())
    if subj is None:
        print("LGS Türkçe dersi yok")
        return 1
    g8 = (db.query(Topic)
          .filter(Topic.subject_id == subj.id, Topic.grade_level == 8, Topic.parent_id.is_(None),
                  Topic.is_builtin.is_(True)).all())
    by_name = {t.name: t for t in g8}
    missing = [n for n in NEW_TOPICS if n not in by_name]
    if missing:
        print("Önce seed çalışmalı — eksik konular:", missing)
        return 1
    general = by_name["Paragrafta Anlam"]
    bozuk = by_name.get("Anlatım Bozuklukları")
    new_ids = {by_name[n].id for n in NEW_TOPICS}
    index = _topics_by_norm(g8)

    def target(label: str | None, current: int | None, paragraf_book: bool) -> Topic | None:
        key = _label_key(label)
        movable = current in (None, general.id)
        if bozuk is not None and current == bozuk.id and any(h in key for h in ANLATIM_HINTS):
            movable = True
        if not movable:
            return None
        m = resolve_label(label, index)
        if m is None or m.topic.id not in new_ids:
            return None
        if m.source not in STRICT and not paragraf_book:
            return None
        return m.topic

    moves = {"kitap": 0, "katalog": 0, "deneme": 0}

    rows = (db.query(BookSection, Book)
            .join(Book, Book.id == BookSection.book_id)
            .filter(Book.subject_id == subj.id).all())
    for sec, book in rows:
        t = target(sec.label, sec.topic_id, "paragraf" in _label_key(book.name))
        if t is not None:
            print(f"  kitap #{book.id} {book.name[:40]:40} | {sec.label[:45]:45} -> {t.name}")
            moves["kitap"] += 1
            if apply:
                sec.topic_id = t.id

    trows = (db.query(BookTemplateSection, BookTemplate)
             .join(BookTemplate, BookTemplate.id == BookTemplateSection.template_id)
             .filter(BookTemplate.subject_id == subj.id).all())
    for sec, tpl in trows:
        t = target(sec.label, sec.topic_id, "paragraf" in _label_key(tpl.name))
        if t is not None:
            print(f"  katalog #{tpl.id} {tpl.name[:40]:40} | {sec.label[:45]:45} -> {t.name}")
            moves["katalog"] += 1
            if apply:
                sec.topic_id = t.id

    qrows = (db.query(ExamResultQuestion)
             .filter(ExamResultQuestion.topic_id == general.id,
                     ExamResultQuestion.manually_edited.is_(False)).all())
    for q in qrows:
        t = target(q.topic_label_raw, q.topic_id, False)
        if t is not None:
            moves["deneme"] += 1
            if moves["deneme"] <= 25:
                print(f"  deneme soru #{q.id} | {(q.topic_label_raw or '')[:60]:60} -> {t.name}")
            if apply:
                q.topic_id = t.id

    print("\nToplam:", moves, "(uygulandı)" if apply else "(kuru çalışma — yazılmadı)")
    if apply:
        db.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
