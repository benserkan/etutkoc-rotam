# -*- coding: utf-8 -*-
"""section_progress.manual_count backfill — geçmiş elle 'zaten çözülmüştü' girişleri.

manual_count = max(0, completed_count − görev kalemlerinden çözülen toplam).
Görevle çözülen kısım TaskBookItem.completed_count toplamından türetilir
(grid'in 'baseline dolgusu' türetimiyle aynı mantık). Formül, self-study
kayıtları eklendikten sonra da tutarlıdır (completed = görev + manual) →
İDEMPOTENT, tekrar koşmak güvenli.

Kullanım: PYTHONPATH=. python scripts/backfill_manual_progress.py [--dry-run]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import SectionProgress, StudentBook, Task, TaskBookItem


def main() -> int:
    dry = "--dry-run" in sys.argv
    db = SessionLocal()
    changed = scanned = 0
    try:
        rows = (
            db.query(SectionProgress, StudentBook.student_id)
            .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
            .filter(SectionProgress.completed_count > 0)
            .all()
        )
        for sp, student_id in rows:
            scanned += 1
            task_done = (
                db.query(func.coalesce(func.sum(TaskBookItem.completed_count), 0))
                .join(Task, Task.id == TaskBookItem.task_id)
                .filter(
                    Task.student_id == student_id,
                    TaskBookItem.book_section_id == sp.book_section_id,
                )
                .scalar()
            ) or 0
            manual = max(0, int(sp.completed_count) - int(task_done))
            if int(sp.manual_count or 0) != manual:
                print(
                    f"  sp#{sp.id} student={student_id} section={sp.book_section_id}: "
                    f"completed={sp.completed_count} task_done={task_done} "
                    f"manual {sp.manual_count} -> {manual}"
                )
                if not dry:
                    sp.manual_count = manual
                changed += 1
        if not dry:
            db.commit()
        print(f"\n{'DRY-RUN — ' if dry else ''}tarandi={scanned} guncellendi={changed}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
