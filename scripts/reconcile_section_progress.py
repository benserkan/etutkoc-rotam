"""SectionProgress sayaçlarını gerçek TaskBookItem verisinden yeniden hesapla.

`reserved_count` ve `completed_count` alanları zamanla drift edebilir (bir görev
direkt silindiğinde, manuel SQL ile temizlik yapıldığında, geçmişte fix'lenmemiş
bir bug nedeniyle). Bu script her SectionProgress'i şu beklenen değerlere göre
yeniden hesaplar:

  expected_completed = sum( completed_count ) of non-draft TaskBookItems
  expected_reserved  = sum( max(0, planned_count - completed_count) ) of non-draft TaskBookItems

Çalıştırma:
  # Önizleme (varsayılan — hiçbir şey değiştirmez):
  python -m scripts.reconcile_section_progress
  python -m scripts.reconcile_section_progress --student-id 2

  # Gerçekten uygula:
  python -m scripts.reconcile_section_progress --apply
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
)


def run(student_id: int | None = None, apply_changes: bool = False) -> int:
    db = SessionLocal()
    try:
        q = db.query(StudentBook).options(
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
            joinedload(StudentBook.student),
        )
        if student_id:
            q = q.filter(StudentBook.student_id == student_id)
        sbs = q.all()

        all_section_ids = set()
        for sb in sbs:
            for sec in sb.book.sections:
                all_section_ids.add(sec.id)

        agg: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"planned": 0, "completed": 0}
        )
        rows = (
            db.query(
                Task.student_id,
                TaskBookItem.book_section_id,
                TaskBookItem.planned_count,
                TaskBookItem.completed_count,
            )
            .join(Task, TaskBookItem.task_id == Task.id)
            .filter(
                TaskBookItem.book_section_id.in_(all_section_ids),
                Task.is_draft.is_(False),
            )
            .all()
        )
        for sid, sec_id, planned_n, completed_n in rows:
            key = (sid, sec_id)
            agg[key]["planned"] += planned_n or 0
            agg[key]["completed"] += completed_n or 0

        changes: list[dict] = []
        for sb in sbs:
            for sp in sb.section_progress:
                key = (sb.student_id, sp.book_section_id)
                planned_sum = agg[key]["planned"]
                completed_sum = agg[key]["completed"]
                expected_reserved = max(0, planned_sum - completed_sum)
                expected_completed = completed_sum
                if (
                    sp.reserved_count != expected_reserved
                    or sp.completed_count != expected_completed
                ):
                    sec_obj = next(
                        (s for s in sb.book.sections if s.id == sp.book_section_id), None
                    )
                    changes.append({
                        "sp": sp,
                        "student_id": sb.student_id,
                        "student_name": sb.student.full_name,
                        "book": sb.book.name,
                        "section": sec_obj.label if sec_obj else f"#{sp.book_section_id}",
                        "topic": (sec_obj.topic.name if sec_obj and sec_obj.topic else "-"),
                        "old_reserved": sp.reserved_count,
                        "new_reserved": expected_reserved,
                        "old_completed": sp.completed_count,
                        "new_completed": expected_completed,
                    })

        print(f"Incelenen SectionProgress sayisi: {sum(len(sb.section_progress) for sb in sbs)}")
        print(f"Duzeltilecek kayit sayisi:        {len(changes)}")
        if not changes:
            print("Drift yok - hicbir sey degismedi.")
            return 0

        print("\n--- DEGISIKLIK LISTESI ---")
        for i, c in enumerate(changes, 1):
            print(
                f"[{i}] {c['student_name']} (id={c['student_id']}) | "
                f"{c['book']} | {c['section']} ({c['topic']})"
            )
            print(
                f"    reserved : {c['old_reserved']:>3}  ->  {c['new_reserved']:>3}    "
                f"completed : {c['old_completed']:>3}  ->  {c['new_completed']:>3}"
            )

        if not apply_changes:
            print("\nDry-run modu (varsayilan) - hicbir sey uygulanmadi.")
            print("Gercekten uygulamak icin: --apply ekle.")
            return 0

        for c in changes:
            c["sp"].reserved_count = c["new_reserved"]
            c["sp"].completed_count = c["new_completed"]
        db.commit()
        print(f"\n{len(changes)} SectionProgress guncellendi ve commit edildi.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int, default=None)
    ap.add_argument("--apply", action="store_true",
                    help="Gercekten uygula (default: dry-run)")
    args = ap.parse_args()
    raise SystemExit(run(student_id=args.student_id, apply_changes=args.apply))
