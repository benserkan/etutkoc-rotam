"""Katalog kayıtlarını bir koçun kütüphanesine kopyalar + öğrencisine atar.

UI'daki "katalogdan kitap ekle" (POST /books template_id) + "öğrenci ata"
(PATCH /books/{id}/assignments) akışının birebir karşılığı — koç şifresine
dokunmadan toplu kurulum için. İdempotent: koçta aynı adlı kitap varsa yeniden
oluşturmaz, yalnız eksik atamayı tamamlar.

Kullanım:
  python -m scripts.assign_catalog_books --coach 162 --student 163 \
      --names-from data/kitap-katalog/lgs [--extra-json <yalnız-kapak.json>] [--apply]
Varsayılan dry-run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookTemplate, BookType, CurriculumModel, SectionProgress,
    StudentBook, Subject, User, UserRole,
)
from app.services import book_catalog as catalog_svc
from app.services import curriculum_mapping as cm


def _assign(db, book: Book, student_id: int) -> bool:
    if db.query(StudentBook).filter_by(book_id=book.id, student_id=student_id).first():
        return False
    sb = StudentBook(student_id=student_id, book_id=book.id)
    db.add(sb)
    db.flush()
    for sec in book.sections or []:
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=0, completed_count=0))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coach", type=int, required=True)
    ap.add_argument("--student", type=int, required=True)
    ap.add_argument("--names-from", required=True)
    ap.add_argument("--extra-json", action="append", default=[],
                    help="Katalog dışı kitap (bölümsüz, yalnız kimlik) JSON'u")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    with SessionLocal() as db:
        coach = db.get(User, a.coach)
        stu = db.get(User, a.student)
        assert coach and coach.role == UserRole.TEACHER, "koç bulunamadı"
        assert stu and stu.role == UserRole.STUDENT and stu.teacher_id == coach.id, "öğrenci bu koçun değil"

        created = assigned = reused = 0
        for f in sorted(Path(a.names_from).glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            tpl = catalog_svc.find_duplicate(db, d["name"], d.get("publisher"))
            if tpl is None or tpl.catalog_status != "verified":
                print(f"[!] katalogda yok/verified değil: {d['name']}")
                continue
            book = db.query(Book).filter_by(teacher_id=coach.id, name=tpl.name).first()
            if book is None:
                book = Book(
                    teacher_id=coach.id, subject_id=tpl.subject_id, name=tpl.name,
                    publisher=tpl.publisher, type=tpl.type,
                    target_grade_min=tpl.target_grade_min, target_grade_max=tpl.target_grade_max,
                    target_graduate=bool(tpl.target_graduate),
                )
                db.add(book)
                db.flush()
                for ts in tpl.sections:
                    db.add(BookSection(book_id=book.id, label=ts.label,
                                       test_count=ts.default_test_count, order=ts.order,
                                       topic_id=ts.topic_id))
                catalog_svc.bump_usage(tpl)
                db.flush()
                db.refresh(book)
                cm.auto_apply_sections(db, book)
                created += 1
            else:
                reused += 1
            if _assign(db, book, stu.id):
                assigned += 1
            print(f"  {book.name} · {len(book.sections)} bölüm · "
                  f"{sum(s.test_count or 0 for s in book.sections)} test")

        for ej in a.extra_json:
            d = json.loads(Path(ej).read_text(encoding="utf-8"))
            subj = (db.query(Subject).filter(Subject.name == d["subject"], Subject.is_builtin.is_(True),
                                             Subject.curriculum_model == CurriculumModel.LGS).first())
            book = db.query(Book).filter_by(teacher_id=coach.id, name=d["name"]).first()
            if book is None:
                book = Book(teacher_id=coach.id, subject_id=subj.id, name=d["name"],
                            publisher=d.get("publisher"), type=BookType(d.get("type", "soru_bankasi")),
                            target_grade_min=8, target_grade_max=8)
                db.add(book)
                db.flush()
                created += 1
            if _assign(db, book, stu.id):
                assigned += 1
            print(f"  {book.name} · BÖLÜMSÜZ (içindekiler yok — koç ekleyecek)")

        print(f"\nOluşturulan kitap: {created} · zaten var: {reused} · yeni atama: {assigned}")
        if a.apply:
            db.commit()
            print("UYGULANDI.")
        else:
            db.rollback()
            print("DRY-RUN — değişiklik yazılmadı (--apply).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
