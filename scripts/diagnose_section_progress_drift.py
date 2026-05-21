"""SectionProgress sayaç drifti teşhis aracı.

reserved_count ve completed_count alanlarının gerçek TaskBookItem verisiyle
uyumlu olup olmadığını kontrol eder.

Beklenen değerler (taslak hariç görevler temelinde):
  expected_reserved  = sum( max(0, planned - completed) ) for non-draft TaskBookItem
  expected_completed = sum( completed_count )             for non-draft TaskBookItem

Çalıştırma:
  python -m scripts.diagnose_section_progress_drift
  python -m scripts.diagnose_section_progress_drift --student-id 2
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
    User,
)


def run(student_id: int | None = None) -> int:
    db = SessionLocal()
    try:
        q = db.query(StudentBook).options(
            joinedload(StudentBook.book).joinedload(Book.subject),
            joinedload(StudentBook.book).joinedload(Book.sections).joinedload(BookSection.topic),
            joinedload(StudentBook.section_progress),
            joinedload(StudentBook.student),
        )
        if student_id:
            q = q.filter(StudentBook.student_id == student_id)
        sbs = q.all()

        all_section_ids = set()
        sb_by_id: dict[int, StudentBook] = {sb.id: sb for sb in sbs}
        for sb in sbs:
            for sec in sb.book.sections:
                all_section_ids.add(sec.id)

        # (student_id, section_id) -> {planned_sum, completed_sum, planned_sum_incl_draft}
        agg_nondraft: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"planned": 0, "completed": 0}
        )
        agg_with_draft: dict[tuple[int, int], dict] = defaultdict(
            lambda: {"planned": 0, "completed": 0}
        )
        rows = (
            db.query(
                Task.student_id,
                TaskBookItem.book_section_id,
                TaskBookItem.planned_count,
                TaskBookItem.completed_count,
                Task.is_draft,
            )
            .join(Task, TaskBookItem.task_id == Task.id)
            .filter(TaskBookItem.book_section_id.in_(all_section_ids))
            .all()
        )
        for sid, sec_id, planned_n, completed_n, is_draft in rows:
            key = (sid, sec_id)
            planned_n = planned_n or 0
            completed_n = completed_n or 0
            agg_with_draft[key]["planned"] += planned_n
            agg_with_draft[key]["completed"] += completed_n
            if not is_draft:
                agg_nondraft[key]["planned"] += planned_n
                agg_nondraft[key]["completed"] += completed_n

        drift_records: list[dict] = []
        total_sp = 0
        for sb in sbs:
            for sp in sb.section_progress:
                total_sp += 1
                key = (sb.student_id, sp.book_section_id)
                nd = agg_nondraft[key]
                wd = agg_with_draft[key]
                expected_reserved_nd = max(0, nd["planned"] - nd["completed"])
                expected_completed_nd = nd["completed"]
                expected_reserved_wd = max(0, wd["planned"] - wd["completed"])
                expected_completed_wd = wd["completed"]

                if (
                    sp.reserved_count != expected_reserved_nd
                    or sp.completed_count != expected_completed_nd
                ):
                    sec_obj = next(
                        (s for s in sb.book.sections if s.id == sp.book_section_id),
                        None,
                    )
                    drift_records.append({
                        "student_id": sb.student_id,
                        "student_name": sb.student.full_name,
                        "book": sb.book.name,
                        "section": sec_obj.label if sec_obj else f"#{sp.book_section_id}",
                        "topic": (sec_obj.topic.name if sec_obj and sec_obj.topic else "—"),
                        "stored_reserved": sp.reserved_count,
                        "stored_completed": sp.completed_count,
                        "expected_reserved_nondraft": expected_reserved_nd,
                        "expected_completed_nondraft": expected_completed_nd,
                        "expected_reserved_with_draft": expected_reserved_wd,
                        "expected_completed_with_draft": expected_completed_wd,
                        "section_progress_id": sp.id,
                    })

        print(f"Toplam SectionProgress incelendi: {total_sp}")
        print(f"Drift'li kayıt sayısı:            {len(drift_records)}")
        if not drift_records:
            print("Tutarsızlık yok ✓")
            return 0

        # Sayaç drift'li ilk 50 kaydı detaylı yazdır
        print("\n--- DRIFT DETAYLARI (max 50) ---")
        for i, d in enumerate(drift_records[:50], 1):
            print(
                f"\n[{i}] {d['student_name']} (id={d['student_id']}) · "
                f"{d['book']} · {d['section']} ({d['topic']})"
            )
            print(
                f"    KAYITLI   : reserved={d['stored_reserved']:>3}  "
                f"completed={d['stored_completed']:>3}"
            )
            print(
                f"    NON-DRAFT : reserved={d['expected_reserved_nondraft']:>3}  "
                f"completed={d['expected_completed_nondraft']:>3}"
            )
            print(
                f"    DRAFT+    : reserved={d['expected_reserved_with_draft']:>3}  "
                f"completed={d['expected_completed_with_draft']:>3}"
            )
        if len(drift_records) > 50:
            print(f"\n... ve {len(drift_records) - 50} kayıt daha.")

        # Drift örneklerini kategorize et
        nd_match = sum(
            1 for d in drift_records
            if d["stored_reserved"] == d["expected_reserved_with_draft"]
            and d["stored_completed"] == d["expected_completed_with_draft"]
        )
        print(f"\nBunlardan {nd_match} tanesi 'draft dahil' beklenenle uyuyor →")
        print("    yani draft görevler de SP sayacına katkı yapıyor demektir.")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int, default=None)
    args = ap.parse_args()
    raise SystemExit(run(student_id=args.student_id))
