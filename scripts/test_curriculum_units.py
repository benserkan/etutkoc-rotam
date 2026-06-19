"""Maarif tema/ünite + alt başlık (parent_id) yapısı smoke.

Resmi Maarif yapısı: her tema/ünite PARENT Topic, alt başlıklar parent_id ile
CHILD. Müfredat sayfası leaf (alt başlık) sayar + parent'ı tema başlığı olarak
gruplar. Kitap bölümleri leaf'e eşlenir; tema parent'ı eşleştirme adayı DEĞİL.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, CurriculumModel, SectionProgress, StudentBook,
    Subject, Topic, User, UserRole,
)
from app.services import curriculum_progress as cp
from app.routes.api_v2.library import _accessible_topics
from app.services.security import hash_password

PFX = f"cunit{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def main() -> int:
    print(f"\n=== curriculum units (Maarif tema/alt başlık) smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="Koç", role=UserRole.TEACHER, is_active=True, plan="solo_free")
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True,
                       grade_level=10, is_graduate=False)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        # Maarif Biyoloji benzeri ders
        subj = Subject(name=f"{PFX} Biyoloji", order=1, is_builtin=True, teacher_id=None,
                       curriculum_model=CurriculumModel.MAARIF_LISE, min_grade_level=9, max_grade_level=12)
        db.add(subj); db.flush()
        # Tema: Enerji (parent) + 2 alt başlık (child); Tema: Ekoloji (parent) + 1 alt
        enerji = Topic(subject_id=subj.id, name="1. Tema: Enerji", order=100100, grade_level=10,
                       is_builtin=True, curriculum_model=CurriculumModel.MAARIF_LISE, parent_id=None)
        ekoloji = Topic(subject_id=subj.id, name="2. Tema: Ekoloji", order=100200, grade_level=10,
                        is_builtin=True, curriculum_model=CurriculumModel.MAARIF_LISE, parent_id=None)
        db.add_all([enerji, ekoloji]); db.flush()
        atp = Topic(subject_id=subj.id, name="ATP ve Enerji", order=100101, grade_level=10,
                    is_builtin=True, curriculum_model=CurriculumModel.MAARIF_LISE, parent_id=enerji.id)
        foto = Topic(subject_id=subj.id, name="Fotosentez", order=100102, grade_level=10,
                     is_builtin=True, curriculum_model=CurriculumModel.MAARIF_LISE, parent_id=enerji.id)
        madde = Topic(subject_id=subj.id, name="Madde Döngüleri", order=100201, grade_level=10,
                      is_builtin=True, curriculum_model=CurriculumModel.MAARIF_LISE, parent_id=ekoloji.id)
        db.add_all([atp, foto, madde]); db.flush()
        # Kitap: section'lar LEAF konulara eşli
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book); db.flush()
        s_atp = BookSection(book_id=book.id, label="ATP", test_count=10, order=0, topic_id=atp.id)
        s_foto = BookSection(book_id=book.id, label="Fotosentez", test_count=10, order=1, topic_id=foto.id)
        s_madde = BookSection(book_id=book.id, label="Döngüler", test_count=10, order=2, topic_id=madde.id)
        db.add_all([s_atp, s_foto, s_madde]); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id); db.add(sb); db.flush()
        db.add_all([
            SectionProgress(student_book_id=sb.id, book_section_id=s_atp.id, completed_count=10, reserved_count=0),
            SectionProgress(student_book_id=sb.id, book_section_id=s_foto.id, completed_count=4, reserved_count=2),
            SectionProgress(student_book_id=sb.id, book_section_id=s_madde.id, completed_count=0, reserved_count=0),
        ])
        db.commit()
        ids = {"teacher": teacher.id, "student": student.id, "subj": subj.id, "book": book.id,
               "enerji": enerji.id, "ekoloji": ekoloji.id, "atp": atp.id, "foto": foto.id, "madde": madde.id}

    try:
        with SessionLocal() as db:
            st = db.get(User, ids["student"])
            res = cp.compute_curriculum_progress(db, st, ids["teacher"])
            bio = next((s for s in res.subjects if s.subject_id == ids["subj"]), None)
            check("1. ders haritada var", bio is not None)
            names = [t.name for t in bio.topics]
            check("2. topics yalnız LEAF (3 alt başlık)", len(bio.topics) == 3, f"{names}")
            check("3. parent tema topics LİSTEDE DEĞİL",
                  "1. Tema: Enerji" not in names and "2. Tema: Ekoloji" not in names, f"{names}")
            byid = {t.topic_id: t for t in bio.topics}
            check("4. ATP leaf unit_name='1. Tema: Enerji'",
                  byid[ids["atp"]].unit_name == "1. Tema: Enerji", byid[ids["atp"]].unit_name)
            check("5. Madde Döngüleri unit_name='2. Tema: Ekoloji'",
                  byid[ids["madde"]].unit_name == "2. Tema: Ekoloji", byid[ids["madde"]].unit_name)
            check("6. total_topics=3 (leaf), started=2 (ATP+Fotosentez)",
                  bio.total_topics == 3 and bio.started_topics == 2,
                  f"{bio.total_topics} {bio.started_topics}")
            check("7. ATP tamamlandi, Fotosentez devam, Madde başlanmadı",
                  byid[ids["atp"]].status == "tamamlandi"
                  and byid[ids["foto"]].status == "devam"
                  and byid[ids["madde"]].status == "baslanmadi",
                  f"{byid[ids['atp']].status}/{byid[ids['foto']].status}/{byid[ids['madde']].status}")
            # eşleştirme adayları leaf olmalı (parent hariç)
            cands = _accessible_topics(db, ids["subj"], ids["teacher"])
            cand_ids = {t.id for t in cands}
            check("8. eşleştirme adayları LEAF (3), parent yok",
                  ids["enerji"] not in cand_ids and ids["ekoloji"] not in cand_ids
                  and ids["atp"] in cand_ids and ids["foto"] in cand_ids and ids["madde"] in cand_ids,
                  f"{len(cand_ids)} aday")
            # frontier: sıradaki = Madde Döngüleri (kaynaklı, başlanmamış)
            check("9. frontier sıradaki = Madde Döngüleri", bio.next_topic_name == "Madde Döngüleri",
                  bio.next_topic_name)
            # ekstra yok (hepsi eşli)
            check("10. eşleşmemiş ekstra yok", len(res.extras) == 0, f"{len(res.extras)}")
    finally:
        with SessionLocal() as db:
            secs = [s.id for s in db.query(BookSection).filter(BookSection.book_id == ids["book"]).all()]
            sbs = [sb.id for sb in db.query(StudentBook).filter(StudentBook.student_id == ids["student"]).all()]
            if sbs:
                db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            # önce child sonra parent
            db.execute(sa_delete(Topic).where(Topic.parent_id.isnot(None), Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
