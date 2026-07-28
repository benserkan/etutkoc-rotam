# -*- coding: utf-8 -*-
"""Tanıtım videosu S7 (kurum) kareleri için dolu demo kurum — YALNIZ DEV.

"Atlas Etüt Merkezi": 4 koç × 6 öğrenci; son 4 haftaya yayılmış kitaplı
görevler (koç başına farklı uyum profili: %88 / %72 / %55 / %35) + doğruluk
verisi + öğrenci başına 3 LGS denemesi (gelişen/gerileyen karışık) + 2 boş
programlı ve eski hesaplı öğrenci (Müdahale Merkezi sinyal üretsin).

İdempotent: kurum slug'ı varsa dokunmaz; --delete ile kaldırılır.

  PYTHONPATH=. python scripts/seed_video_demo_kurum.py [--delete]
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import (
    Book, BookSection, Institution, SectionProgress, StudentBook, Subject,
    Task, TaskBookItem, User, UserRole,
)
from app.models.book import BookType
from app.models.exam_result import ExamResult, ExamSection, compute_net
from app.models.task import TaskStatus, TaskType
from app.services.security import hash_password

SLUG = "atlas-etut-video-demo"
PWD = "VideoDemo2026!"
random.seed(42)

KOCLAR = [
    ("Ayşe Yılmaz", 0.88),
    ("Mehmet Kaya", 0.72),
    ("Zeynep Demir", 0.55),
    ("Emre Şahin", 0.35),
]
OGR_ADLARI = [
    "Ali", "Buse", "Can", "Derin", "Ela", "Furkan", "Gizem", "Hakan",
    "İrem", "Kaan", "Lina", "Murat", "Naz", "Okan", "Pelin", "Rüzgar",
    "Selin", "Tuna", "Umut", "Vera", "Yağmur", "Zehra", "Berk", "Ceren",
]
UNITELER = [
    "Çarpanlar ve Katlar", "Üslü İfadeler", "Kareköklü İfadeler",
    "Veri Analizi", "Olasılık", "Cebirsel İfadeler", "Doğrusal Denklemler",
    "Eşitsizlikler", "Üçgenler", "Dönüşüm Geometrisi",
]


def main() -> int:
    delete = "--delete" in sys.argv
    now = datetime.now(timezone.utc)
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    with SessionLocal() as db:
        inst = db.query(Institution).filter_by(slug=SLUG).first()
        if delete:
            if not inst:
                print("yok")
                return 0
            uids = [u.id for u in db.query(User).filter(
                (User.institution_id == inst.id))]
            studs = [u.id for u in db.query(User).filter(User.teacher_id.in_(uids))]
            allids = uids + studs
            for model in (ExamResult,):
                db.query(model).filter(model.student_id.in_(allids)).delete(synchronize_session=False)
            tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(allids))]
            if tids:
                db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
                db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
            sbids = [sb.id for sb in db.query(StudentBook).filter(StudentBook.student_id.in_(allids))]
            if sbids:
                db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbids)).delete(synchronize_session=False)
                db.query(StudentBook).filter(StudentBook.id.in_(sbids)).delete(synchronize_session=False)
            bids = [b.id for b in db.query(Book).filter(Book.teacher_id.in_(uids))]
            if bids:
                db.query(BookSection).filter(BookSection.book_id.in_(bids)).delete(synchronize_session=False)
                db.query(Book).filter(Book.id.in_(bids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(allids)).delete(synchronize_session=False)
            db.delete(inst)
            db.commit()
            print("silindi")
            return 0

        if inst:
            print("zaten var — atlandı (--delete ile kaldır)")
            return 0

        subject = (
            db.query(Subject)
            .filter(Subject.name == "Matematik", Subject.teacher_id.is_(None))
            .first()
        )

        inst = Institution(name="Atlas Etüt Merkezi", slug=SLUG,
                           plan="etut_standart", is_active=True)
        db.add(inst)
        db.flush()

        admin = User(
            email=f"admin@{SLUG}.demo", password_hash=hash_password(PWD),
            full_name="Nurcan Atlas", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(admin)

        ogr_idx = 0
        for k_i, (k_ad, uyum) in enumerate(KOCLAR):
            koc = User(
                email=f"koc{k_i+1}@{SLUG}.demo", password_hash=hash_password(PWD),
                full_name=k_ad, role=UserRole.TEACHER, institution_id=inst.id,
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            db.add(koc)
            db.flush()
            koc.created_at = now - timedelta(days=60)

            book = Book(
                teacher_id=koc.id, name="Atlas LGS Matematik Soru Bankası",
                type=BookType.SORU_BANKASI,
                subject_id=subject.id if subject else None,
            )
            db.add(book)
            db.flush()
            secs = []
            for o, u in enumerate(UNITELER):
                s = BookSection(book_id=book.id, label=u, order=o, test_count=24)
                db.add(s)
                secs.append(s)
            db.flush()

            for s_i in range(6):
                ad = OGR_ADLARI[ogr_idx]; ogr_idx += 1
                stu = User(
                    email=f"ogr{ogr_idx}@{SLUG}.demo", password_hash=hash_password(PWD),
                    full_name=f"{ad} {k_ad.split()[-1]}", role=UserRole.STUDENT,
                    teacher_id=koc.id, institution_id=None, grade_level=8,
                    is_active=True, password_changed_at=now, must_change_password=False,
                )
                db.add(stu)
                db.flush()
                stu.created_at = now - timedelta(days=45)
                stu.last_login = now - timedelta(days=random.randint(0, 2)) \
                    if not (k_i == 3 and s_i >= 4) else now - timedelta(days=9)

                sb = StudentBook(student_id=stu.id, book_id=book.id)
                db.add(sb)
                db.flush()
                sp_map = {}

                # Koç 4'ün son 2 öğrencisi: BU hafta boş program (sinyal)
                bos_program = (k_i == 3 and s_i >= 4)
                haftalar = [0, 1, 2, 3] if not bos_program else [1, 2, 3]
                for w in haftalar:
                    wk_monday = monday - timedelta(days=7 * w)
                    for g in (0, 2, 4):  # Pzt, Çar, Cum
                        d = wk_monday + timedelta(days=g)
                        if d > today:
                            continue
                        sec = secs[(w * 3 + g + s_i) % len(secs)]
                        planned = random.choice((10, 12, 16))
                        oran = min(1.0, max(0.0, random.gauss(uyum, 0.13)))
                        completed = round(planned * oran)
                        dogruluk = min(0.95, max(0.35, random.gauss(
                            0.55 + 0.35 * uyum, 0.08)))
                        correct = round(completed * 10 * dogruluk / 10)
                        correct = min(completed, max(0, correct))
                        done_at = datetime(d.year, d.month, d.day, 17, 30,
                                           tzinfo=timezone.utc)
                        t = Task(
                            student_id=stu.id, date=d, type=TaskType.TEST,
                            title=f"{book.name} — {sec.label}: {planned // 8 or 1} test",
                            status=(TaskStatus.COMPLETED if completed >= planned
                                    else TaskStatus.PENDING),
                            is_draft=False,
                            published_at=done_at - timedelta(days=1),
                            completed_at=done_at if completed >= planned else None,
                        )
                        db.add(t)
                        db.flush()
                        db.add(TaskBookItem(
                            task_id=t.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=planned, completed_count=completed,
                            correct_count=correct * 10 // 10 if completed else None,
                            wrong_count=(completed * 10 - correct * 10) // 10 if completed else None,
                        ))
                        sp = sp_map.get(sec.id)
                        if sp is None:
                            sp = SectionProgress(student_book_id=sb.id,
                                                 book_section_id=sec.id,
                                                 reserved_count=0, completed_count=0)
                            db.add(sp)
                            db.flush()
                            sp_map[sec.id] = sp
                        sp.completed_count += completed

                # 3 LGS denemesi — koç profiline göre taban + eğim
                taban = 30 + 22 * uyum + random.uniform(-4, 4)
                egim = random.choice((4.5, 3.0, 2.0)) if random.random() > 0.2 else -3.0
                for e_i in range(3):
                    d = today - timedelta(days=42 - e_i * 14)
                    net_hedef = max(12, min(82, taban + egim * e_i + random.uniform(-2, 2)))
                    correct = round(net_hedef * 90 / 78)
                    wrong = min(90 - correct, round(correct * 0.28))
                    blank = 90 - correct - wrong
                    db.add(ExamResult(
                        student_id=stu.id, created_by_id=koc.id,
                        title=f"Atlas LGS Deneme {e_i + 1}", exam_date=d,
                        section=ExamSection.LGS,
                        total_correct=correct, total_wrong=wrong, total_blank=blank,
                        net=compute_net(correct, wrong, ExamSection.LGS),
                    ))

        db.commit()
        print(f"Atlas Etüt Merkezi kuruldu — kurum #{inst.id} · admin: admin@{SLUG}.demo / {PWD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
