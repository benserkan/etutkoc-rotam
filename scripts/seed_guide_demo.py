"""Rehber ekran görüntüleri için demo koç verisi (idempotent).

Rota rehberinin sahneleri GERÇEK panelden çekilir (uydurma yok). Bu script,
ekranların dolu ve gerçekçi görünmesi için bir demo koç ekosistemi kurar:

  - Koç: rehber-koc@etutkoc.demo (solo_pro)
  - Öğrenciler: Elif Kaya (8, LGS — kitap+program+deneme dolu) + Mert Yılmaz (8)
  - Veli: Elif'in velisi (veliye-duyur önizlemesi alıcı göstersin)
  - Kitap: "3D LGS Matematik Soru Bankası" (10 ünite, LGS Matematik dersi)
  - Atama + SectionProgress (rezerv/çözüm sayaçları dolu görünsün)
  - Bu haftanın programı: yayınlanmış görevler (bir kısmı işaretli) + tam deneme
  - 3 deneme sonucu (net trendi) — sonuncusu soru-satırlı (pdf_import) →
    konu analizi ısı haritası dolu görünür

  python -m scripts.seed_guide_demo            # kur (varsa dokunmaz)
  python -m scripts.seed_guide_demo --delete   # tamamen kaldır

YALNIZ dev/demo içindir; start.sh'e EKLENMEZ.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    ExamResult,
    ParentStudentLink,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    Topic,
    User,
    UserGuideState,
    UserRole,
    WeeklyProgram,
)
from app.models.book import BookType
from app.models.exam_result import (
    EQ_RESULT_BOS,
    EQ_RESULT_DOGRU,
    EQ_RESULT_YANLIS,
    ExamResultQuestion,
    ExamSection,
)
from app.models.task import TaskStatus, TaskType
from app.services.security import hash_password

COACH_EMAIL = "rehber-koc@etutkoc.demo"
PASSWORD = "RehberDemo2026!"

SECTIONS = [
    ("Çarpanlar ve Katlar", 24),
    ("Üslü İfadeler", 22),
    ("Kareköklü İfadeler", 26),
    ("Veri Analizi", 14),
    ("Basit Olayların Olma Olasılığı", 12),
    ("Cebirsel İfadeler ve Özdeşlikler", 28),
    ("Doğrusal Denklemler", 24),
    ("Eşitsizlikler", 16),
    ("Üçgenler", 20),
    ("Dönüşüm Geometrisi", 12),
]


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def seed() -> None:
    now = datetime.now(timezone.utc)
    today = date.today()
    week_start = monday(today)
    rng = random.Random(42)

    with SessionLocal() as db:
        if db.execute(select(User).where(User.email == COACH_EMAIL)).scalar_one_or_none():
            print("Demo koç zaten var — dokunulmadı. (--delete ile kaldırıp yeniden kurabilirsin)")
            return

        coach = User(
            email=COACH_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Aylin Demir", role=UserRole.TEACHER, plan="solo_pro",
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add(coach)
        db.flush()

        elif_ = User(
            email="rehber-elif@etutkoc.demo", password_hash=hash_password(PASSWORD),
            full_name="Elif Kaya", role=UserRole.STUDENT, teacher_id=coach.id,
            grade_level=8, is_active=True, password_changed_at=now,
            must_change_password=False,
        )
        mert = User(
            email="rehber-mert@etutkoc.demo", password_hash=hash_password(PASSWORD),
            full_name="Mert Yılmaz", role=UserRole.STUDENT, teacher_id=coach.id,
            grade_level=8, is_active=True, password_changed_at=now,
            must_change_password=False,
        )
        veli = User(
            email="rehber-veli@etutkoc.demo", password_hash=hash_password(PASSWORD),
            full_name="Zeynep Kaya", role=UserRole.PARENT, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([elif_, mert, veli])
        db.flush()
        db.add(ParentStudentLink(parent_id=veli.id, student_id=elif_.id))

        # LGS Matematik builtin dersi (seed'li dev DB'de vardır; yoksa koça özel kur)
        subject = db.execute(
            select(Subject).where(
                Subject.name == "Matematik",
                Subject.is_builtin.is_(True),
                Subject.teacher_id.is_(None),
            ).order_by(Subject.id)
        ).scalars().first()
        if subject is None:
            subject = Subject(name="Matematik", teacher_id=coach.id)
            db.add(subject)
            db.flush()

        book = Book(
            teacher_id=coach.id, subject_id=subject.id,
            name="3D LGS Matematik Soru Bankası", publisher="3D Yayınları",
            type=BookType.SORU_BANKASI, target_grade_min=8, target_grade_max=8,
        )
        db.add(book)
        db.flush()
        sections: list[BookSection] = []
        for i, (label, cnt) in enumerate(SECTIONS):
            s = BookSection(book_id=book.id, label=label, test_count=cnt, order=i)
            db.add(s)
            sections.append(s)
        db.flush()

        sb = StudentBook(student_id=elif_.id, book_id=book.id)
        db.add(sb)
        db.flush()
        # İlk üniteler kısmen çözülmüş + bu haftaya rezerv var görünsün
        progress_plan = [(24, 24, 0), (22, 18, 4), (26, 10, 6), (14, 0, 4), (12, 0, 2)]
        for s, (total, done, reserved) in zip(sections, progress_plan):
            db.add(SectionProgress(
                student_book_id=sb.id, book_section_id=s.id,
                reserved_count=min(reserved + done, total), completed_count=done,
            ))

        # Bu haftanın programı (yayınlanmış) — Pzt..Paz görevler
        db.add(WeeklyProgram(
            student_id=elif_.id, coach_id=coach.id,
            start_date=week_start, end_date=week_start + timedelta(days=6),
        ))

        def add_task(day_offset: int, section: BookSection, planned: int,
                     completed: int, correct: int | None, wrong: int | None,
                     period: str | None = None):
            t = Task(
                student_id=elif_.id, date=week_start + timedelta(days=day_offset),
                type=TaskType.TEST,
                title=f"{book.name} — {section.label}: {planned} test",
                status=TaskStatus.COMPLETED if completed >= planned else TaskStatus.PENDING,
                is_draft=False, published_at=now, period=period,
                completed_at=now if completed >= planned else None,
            )
            db.add(t)
            db.flush()
            db.add(TaskBookItem(
                task_id=t.id, book_id=book.id, book_section_id=section.id,
                planned_count=planned, completed_count=completed,
                correct_count=correct, wrong_count=wrong,
            ))

        add_task(0, sections[1], 4, 4, 34, 6)
        add_task(1, sections[2], 3, 3, 24, 9)
        add_task(2, sections[2], 3, 0, None, None)
        add_task(3, sections[3], 4, 0, None, None)
        add_task(4, sections[4], 2, 0, None, None)
        # Cumartesi tam deneme (kitapsız kalem)
        deneme = Task(
            student_id=elif_.id, date=week_start + timedelta(days=5),
            type=TaskType.OTHER, title="LGS Genel Deneme — 90 soru",
            status=TaskStatus.PENDING, is_draft=False, published_at=now,
        )
        db.add(deneme)
        db.flush()
        db.add(TaskBookItem(task_id=deneme.id, book_id=None, book_section_id=None,
                            label="Deneme", planned_count=90, completed_count=0))

        # Deneme sonuçları — yükselen net trendi
        for weeks_ago, (c, w, b) in [(6, (55, 20, 15)), (3, (61, 17, 12)), (1, (66, 15, 9))]:
            db.add(ExamResult(
                student_id=elif_.id, created_by_id=coach.id,
                title=f"LGS Deneme {7 - weeks_ago}", exam_date=today - timedelta(weeks=weeks_ago),
                section=ExamSection.LGS, total_correct=c, total_wrong=w, total_blank=b,
                net=round(c - w / 3, 2),
            ))

        # Soru-satırlı (pdf_import) 2 deneme → konu analizi ısı haritası dolsun
        topics = db.execute(
            select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.order)
        ).scalars().all()
        topic_names = [t.name for t in topics[:8]] or [s.label for s in sections[:8]]
        topic_ids = [t.id for t in topics[:8]] or [None] * 8
        for k, weeks_ago in enumerate([4, 2]):
            c = 14 + k * 2
            exam = ExamResult(
                student_id=elif_.id, created_by_id=coach.id,
                title=f"Matematik Branş Denemesi {k + 1}",
                exam_date=today - timedelta(weeks=weeks_ago),
                section=ExamSection.LGS, total_correct=c, total_wrong=18 - c // 2,
                total_blank=20 - c - (18 - c // 2) if 20 - c - (18 - c // 2) > 0 else 0,
                net=round(c - (18 - c // 2) / 3, 2), import_source="pdf_import",
            )
            db.add(exam)
            db.flush()
            for q in range(1, 21):
                ti = (q - 1) % len(topic_names)
                roll = rng.random()
                res = EQ_RESULT_DOGRU if roll < 0.55 + k * 0.1 else (
                    EQ_RESULT_YANLIS if roll < 0.85 else EQ_RESULT_BOS
                )
                db.add(ExamResultQuestion(
                    exam_result_id=exam.id, question_no=q,
                    subject_name_raw="Matematik", subject_id=subject.id,
                    topic_label_raw=topic_names[ti], topic_id=topic_ids[ti],
                    result=res,
                ))

        db.commit()
        print("Demo koç kuruldu:")
        print(f"  koç:      {COACH_EMAIL} / {PASSWORD}")
        print(f"  öğrenci:  Elif Kaya (id={elif_.id}) — kitap+program+deneme dolu")
        print(f"  öğrenci:  Mert Yılmaz (id={mert.id})")
        ids = {"coach": coach.id, "elif": elif_.id, "mert": mert.id, "book": book.id}
        out = os.path.join(os.path.dirname(__file__), "guide_demo_ids.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(ids, f)
        print(f"  id dosyası: {out}")


def delete() -> None:
    with SessionLocal() as db:
        users = db.query(User).filter(User.email.like("rehber-%@etutkoc.demo")).all()
        ids = [u.id for u in users]
        if not ids:
            print("Silinecek demo verisi yok.")
            return
        exam_ids = [e.id for e in db.query(ExamResult).filter(ExamResult.student_id.in_(ids))]
        if exam_ids:
            db.query(ExamResultQuestion).filter(
                ExamResultQuestion.exam_result_id.in_(exam_ids)
            ).delete(synchronize_session=False)
            db.query(ExamResult).filter(ExamResult.id.in_(exam_ids)).delete(
                synchronize_session=False
            )
        task_ids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids))]
        if task_ids:
            db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(task_ids)).delete(
                synchronize_session=False
            )
            db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
        db.query(WeeklyProgram).filter(WeeklyProgram.student_id.in_(ids)).delete(
            synchronize_session=False
        )
        sb_ids = [s.id for s in db.query(StudentBook).filter(StudentBook.student_id.in_(ids))]
        if sb_ids:
            db.query(SectionProgress).filter(
                SectionProgress.student_book_id.in_(sb_ids)
            ).delete(synchronize_session=False)
            db.query(StudentBook).filter(StudentBook.id.in_(sb_ids)).delete(
                synchronize_session=False
            )
        book_ids = [b.id for b in db.query(Book).filter(Book.teacher_id.in_(ids))]
        if book_ids:
            db.query(BookSection).filter(BookSection.book_id.in_(book_ids)).delete(
                synchronize_session=False
            )
            db.query(Book).filter(Book.id.in_(book_ids)).delete(synchronize_session=False)
        db.query(Subject).filter(Subject.teacher_id.in_(ids)).delete(synchronize_session=False)
        db.query(ParentStudentLink).filter(
            ParentStudentLink.student_id.in_(ids) | ParentStudentLink.parent_id.in_(ids)
        ).delete(synchronize_session=False)
        db.query(UserGuideState).filter(UserGuideState.user_id.in_(ids)).delete(
            synchronize_session=False
        )
        for u in users:
            db.delete(u)
        db.commit()
        print(f"Silindi: {len(ids)} kullanıcı + bağlı veriler.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", action="store_true")
    args = ap.parse_args()
    if args.delete:
        delete()
    else:
        seed()
