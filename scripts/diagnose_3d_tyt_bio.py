"""SALT OKUMA: 3D TYT Biyoloji katalog kaydı + Emir'in (#113) kitabı (2026-10-11)."""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookTemplate, SectionProgress, StudentBook, Task, TaskBookItem,
)

STUDENT = int(sys.argv[1]) if len(sys.argv) > 1 else 113

with SessionLocal() as db:
    tpls = db.query(BookTemplate).filter(BookTemplate.name.ilike("%3D%TYT%Biyoloji%")).all()
    for t in tpls:
        print(f"KATALOG #{t.id} {t.name} status={t.catalog_status} teacher={t.teacher_id} usage={t.usage_count} bölüm={len(t.sections)}")
    sbs = (db.query(StudentBook).join(Book).filter(StudentBook.student_id == STUDENT,
           Book.name.ilike("%Biyoloji%")).all())
    for sb in sbs:
        b = sb.book
        print(f"\nKİTAP #{b.id} '{b.name}' src_tpl={b.source_template_id} kind={b.source_kind} "
              f"sb={sb.id} archived={sb.archived_at} öğrenci_sayısı="
              f"{db.query(StudentBook).filter(StudentBook.book_id == b.id).count()}")
        secs = db.query(BookSection).filter(BookSection.book_id == b.id).order_by(BookSection.order, BookSection.id).all()
        for s in secs:
            sp = db.query(SectionProgress).filter_by(student_book_id=sb.id, book_section_id=s.id).first()
            items = (db.query(TaskBookItem, Task).join(Task, Task.id == TaskBookItem.task_id)
                     .filter(TaskBookItem.book_section_id == s.id).all())
            it = ";".join(f"t{t.id}:{t.date}:{i.completed_count}/{i.planned_count}:{t.status}{'*D' if t.is_draft else ''}"
                          for i, t in items)
            print(f"  [{s.id}] o={s.order} tc={s.test_count} done={sp.completed_count if sp else '-'} "
                  f"res={sp.reserved_count if sp else '-'} man={getattr(sp, 'manual_count', None) if sp else '-'} "
                  f"topic={s.topic_id} | {s.label} | {it}")
