"""Elif'in Çalışma DNA'sı için geçmiş tamamlanmış görev zenginleştirmesi.

DNA profili en az 5 tamamlanmış görev ister; Elif'te son 28 günün geçmiş
haftaları boştu → "Yetersiz veri". Bu script son 3 haftaya (İÇİNDE BULUNULAN
HAFTA HARİÇ) 12 tamamlanmış TEST görevi serpiştirir:
  - TR akşam saatleri (19:00-21:30) → kronotip "akşam" sinyali
  - günler Pzt-Paz'a dağıtılır, günde 1 görev (batch algılamasına takılmaz)
  - SectionProgress.completed_count aynı miktarda artar (sayaç tutarlılığı)
  - doğru/yanlış girilir → Konu Performansı da zenginleşir

İdempotent işaret: başlık "[dna-demo]" içeren görev varsa dokunmaz.
YALNIZ dev içindir.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.database import SessionLocal
from app.models import Book, BookSection, SectionProgress, StudentBook, Task, TaskBookItem
from app.models.task import TaskStatus, TaskType

ROOT = Path(__file__).resolve().parent.parent
IDS = json.loads((ROOT / "scripts" / "guide_demo_ids.json").read_text())
MARK = "[dna-demo]"


def main() -> int:
    today = date.today()
    monday = today - timedelta(days=today.weekday())  # bu haftanın Pzt'si
    with SessionLocal() as db:
        exists = (
            db.query(Task)
            .filter(Task.student_id == IDS["elif"], Task.title.like(f"%{MARK}%"))
            .first()
        )
        if exists:
            print("DNA zenginleştirmesi zaten var — dokunulmadı.")
            return 0

        book = db.get(Book, IDS["book"])
        secs = (
            db.query(BookSection).filter_by(book_id=book.id).order_by(BookSection.order).all()
        )
        sb = (
            db.query(StudentBook)
            .filter_by(student_id=IDS["elif"], book_id=book.id)
            .one()
        )
        sp_by_sec = {
            sp.book_section_id: sp
            for sp in db.query(SectionProgress).filter_by(student_book_id=sb.id).all()
        }

        # bu haftadan geriye 18 gün içinde 12 gün seç (gün başına 1 görev)
        offsets = [1, 2, 3, 5, 6, 8, 9, 10, 12, 13, 15, 16]  # monday - offset
        # TR akşamı: UTC 16:05-18:35 arası dakika çeşitliliğiyle
        utc_hours = [16, 17, 18, 16, 17, 18, 16, 17, 16, 17, 18, 17]
        minutes = [5, 20, 35, 50, 10, 25, 40, 55, 15, 30, 45, 5]
        plan = [3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2]
        correct_pct = [0.7, 0.8, 0.6, 0.9, 0.7, 0.75, 0.65, 0.8, 0.7, 0.85, 0.75, 0.7]

        created = 0
        for i, off in enumerate(offsets):
            d = monday - timedelta(days=off)
            sec = secs[i % len(secs)]
            planned = plan[i]
            total_q = planned * 10  # bölüm testleri ~10 soruluk varsayım
            correct = round(total_q * correct_pct[i])
            wrong = total_q - correct
            done_at = datetime(
                d.year, d.month, d.day, utc_hours[i], minutes[i], tzinfo=timezone.utc
            )
            t = Task(
                student_id=IDS["elif"], date=d, type=TaskType.TEST,
                title=f"{book.name} — {sec.label}: {planned} test {MARK}",
                status=TaskStatus.COMPLETED, is_draft=False,
                published_at=done_at - timedelta(days=1), completed_at=done_at,
            )
            db.add(t)
            db.flush()
            db.add(TaskBookItem(
                task_id=t.id, book_id=book.id, book_section_id=sec.id,
                planned_count=planned, completed_count=planned,
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
            sp.completed_count = (sp.completed_count or 0) + planned
            created += 1

        db.commit()
        print(f"{created} tamamlanmış görev eklendi (akşam saatleri, {offsets[-1]}-1 gün önce).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
