# -*- coding: utf-8 -*-
"""Elif'in Konu Performansı sayfası için Fen Bilimleri zenginleştirmesi.

Veli rehberinin "Konu Performansı" bölümü renk eşiklerini (yeşil/sarı/kırmızı)
GERÇEK veriyle öğretebilsin diye Elif'e Fen kitabından (Sınav Yayınları LGS
Fen SB, id 155) geçmiş günlere tamamlanmış görevler ekler:

  - Mevsimler ve İklim  : 2 test · %80 → yeşil
  - DNA ve Genetik Kod  : 2 test · %70 → yeşil (sınırda)
  - Basınç              : 3 test · %37 → KIRMIZI (rehberin işaret edeceği konu)
  - Madde ve Endüstri   : 1 test · %60 → sarı

Fen dersi geneli ~%59 (sarı) olur → "ders sarı ama asıl suçlu içeride" dersi.
SectionProgress.completed_count aynı miktarda artar (sayaç tutarlılığı).
İdempotent işaret: başlık "[konu-demo]" içeren görev varsa dokunmaz. YALNIZ dev.

  PYTHONPATH=. python scripts/enrich_guide_demo_topics.py
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import Book, BookSection, SectionProgress, StudentBook, Task, TaskBookItem
from app.models.task import TaskStatus, TaskType

ELIF = 228
FEN_BOOK = 155
MARK = "[konu-demo]"

# (bölüm etiketi araması, gün-ofset, test, doğru, yanlış) — soru = test×10
PLAN = [
    ("Mevsimler ve İklim", 16, 1, 8, 2),
    ("Mevsimler ve İklim", 14, 1, 8, 2),
    ("DNA ve Genetik Kod", 12, 1, 7, 3),
    ("DNA ve Genetik Kod", 9, 1, 7, 3),
    ("Basınç", 7, 1, 4, 6),
    ("Basınç", 5, 1, 4, 6),
    ("Basınç", 3, 1, 3, 7),
    ("Madde ve Endüstri", 2, 1, 6, 4),
]
UTC_HOURS = [13, 14, 15, 16, 13, 14, 15, 16]
MINUTES = [10, 25, 40, 55, 15, 30, 45, 20]


def main() -> int:
    today = date.today()
    with SessionLocal() as db:
        exists = (
            db.query(Task)
            .filter(Task.student_id == ELIF, Task.title.like(f"%{MARK}%"))
            .first()
        )
        if exists:
            print("Konu zenginleştirmesi zaten var — dokunulmadı.")
            return 0

        book = db.get(Book, FEN_BOOK)
        if book is None:
            print("Fen kitabı (155) yok — önce kitap-ekle çekim seed'i gerekli.")
            return 1
        secs = db.query(BookSection).filter_by(book_id=book.id).all()
        by_label = {}
        for s in secs:
            by_label[s.label] = s
        sb = (
            db.query(StudentBook)
            .filter_by(student_id=ELIF, book_id=book.id)
            .one()
        )
        sp_by_sec = {
            sp.book_section_id: sp
            for sp in db.query(SectionProgress).filter_by(student_book_id=sb.id).all()
        }

        created = 0
        for i, (needle, off, tests, correct10, wrong10) in enumerate(PLAN):
            sec = next((s for lbl, s in by_label.items() if needle in lbl), None)
            if sec is None:
                print(f"  !! bölüm bulunamadı: {needle}")
                continue
            d = today - timedelta(days=off)
            correct = correct10  # 10 soruluk test başına doğru
            wrong = wrong10
            done_at = datetime(
                d.year, d.month, d.day, UTC_HOURS[i], MINUTES[i], tzinfo=timezone.utc
            )
            t = Task(
                student_id=ELIF, date=d, type=TaskType.TEST,
                title=f"{book.name} — {sec.label}: {tests} test {MARK}",
                status=TaskStatus.COMPLETED, is_draft=False,
                published_at=done_at - timedelta(days=1), completed_at=done_at,
            )
            db.add(t)
            db.flush()
            db.add(TaskBookItem(
                task_id=t.id, book_id=book.id, book_section_id=sec.id,
                planned_count=tests, completed_count=tests,
                correct_count=correct, wrong_count=wrong,
            ))
            sp = sp_by_sec.get(sec.id)
            if sp is None:
                sp = SectionProgress(
                    student_book_id=sb.id, book_section_id=sec.id,
                    reserved_count=0, completed_count=0,
                )
                db.add(sp)
                db.flush()
                sp_by_sec[sec.id] = sp
            sp.completed_count = (sp.completed_count or 0) + tests
            created += 1

        db.commit()
        print(f"{created} tamamlanmış Fen görevi eklendi (2-16 gün önce).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
