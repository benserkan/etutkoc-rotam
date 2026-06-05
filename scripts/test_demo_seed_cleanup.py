"""Demo seansı temizliği — demo kullanıcılar + ÜRETTİKLERİ tam süpürülüyor mu?

Kullanıcı kararı (2026-06-05): demo silme yalnız demo-işaretli kayıtları değil,
demo kullanıcıların oluşturduğu GERÇEK (demo-işaretsiz) kayıtları da temizlemeli:
  - demo koçun manuel oluşturduğu öğrenci + velisi + kitap + görev + deneme
  - demo kurum yöneticisinin DAVET ettiği öğretmen + onun öğrencisi + velisi + kitabı

Bu test her iki senaryoyu kurar, delete_demo_session çağırır, HİÇBİR kayıt
(demo + üretilen) kalmadığını + YETİM kalmadığını doğrular.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import (
    Book as _Book2,
    BookSection as _BS,
    BookType as _BT,
    Invitation,
    ParentStudentLink,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult, compute_net
from app.services.demo_seed import create_demo_ecosystem, delete_demo_session
from app.services.security import hash_password

PFX = f"democlean_{_secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _mk_student(db, *, coach_id, institution_id=None, name) -> User:
    u = User(
        email=f"{PFX}-{_secrets.token_hex(2)}@real.invalid",
        password_hash=hash_password("Real123!@"),
        full_name=name, role=UserRole.STUDENT, is_active=True,
        teacher_id=coach_id, institution_id=institution_id, grade_level=8,
    )
    db.add(u); db.flush()
    return u


def _mk_parent(db, *, student_id, name) -> User:
    p = User(
        email=f"{PFX}-{_secrets.token_hex(2)}@real.invalid",
        password_hash=hash_password("Real123!@"),
        full_name=name, role=UserRole.PARENT, is_active=True,
    )
    db.add(p); db.flush()
    db.add(ParentStudentLink(parent_id=p.id, student_id=student_id)); db.flush()
    return p


def _mk_book_with_data(db, *, coach_id, student_id) -> tuple[int, int, int]:
    """Koça kitap + öğrenciye görev + deneme. Returns (book_id, task_id, exam_id)."""
    subj = Subject(name=f"{PFX} Ders", order=900, teacher_id=coach_id)
    db.add(subj); db.flush()
    topic = Topic(name="Genel", order=0, subject_id=subj.id)
    db.add(topic); db.flush()
    book = _Book2(name=f"{PFX} Kitap", subject_id=subj.id, type=_BT.SORU_BANKASI, teacher_id=coach_id)
    db.add(book); db.flush()
    sec = _BS(book_id=book.id, label="B1", test_count=100, order=0, topic_id=topic.id)
    db.add(sec); db.flush()
    task = Task(student_id=student_id, date=date.today(), type=TaskType.TEST,
                title="Görev", status=TaskStatus.PENDING, order=0, is_draft=False)
    db.add(task); db.flush()
    db.add(TaskBookItem(task_id=task.id, book_id=book.id, book_section_id=sec.id,
                        planned_count=10, completed_count=0)); db.flush()
    exam = ExamResult(student_id=student_id, created_by_id=coach_id,
                      title="Deneme", exam_date=date.today() - timedelta(days=1),
                      section=ExamSection.LGS, total_correct=50, total_wrong=10,
                      total_blank=10, net=compute_net(50, 10, ExamSection.LGS))
    db.add(exam); db.flush()
    return book.id, task.id, exam.id


def _alive(db, ids):
    """user_ids içinden hâlâ var olan User sayısı."""
    if not ids:
        return 0
    return db.query(User).filter(User.id.in_(list(ids))).count()


def main() -> int:
    print(f"\n=== demo seed cleanup smoke — {PFX} ===\n")

    # =========================================================================
    # Senaryo 1: SOLO demo koç + manuel non-demo öğrenci/veli/kitap/görev/deneme
    # =========================================================================
    with SessionLocal() as db:
        res = create_demo_ecosystem(db, kind="solo_coach", label=f"{PFX} solo")
        seed1 = res.seed_id
        coach_id = next(c.user_id for c in res.credentials if c.role_label == "Koç")
        demo_user_ids = {c.user_id for c in res.credentials}

        # Manuel (demo koçun oluşturduğu gerçek kayıtlar)
        zeynep = _mk_student(db, coach_id=coach_id, name=f"{PFX} Gerçek Zeynep")
        zeynep_parent = _mk_parent(db, student_id=zeynep.id, name=f"{PFX} Gerçek Veli")
        book_id, task_id, exam_id = _mk_book_with_data(db, coach_id=coach_id, student_id=zeynep.id)
        db.commit()

        all_user_ids = demo_user_ids | {zeynep.id, zeynep_parent.id}
        print(f"  solo: demo={len(demo_user_ids)} + gerçek 2 = {len(all_user_ids)} user; coach={coach_id}")

        # >>> SİL <<<
        counts = delete_demo_session(db, seed_id=seed1)
        db.commit()

        check("S1.1 tüm kullanıcılar silindi (demo + gerçek Zeynep + veli)",
              _alive(db, all_user_ids) == 0, f"kalan={_alive(db, all_user_ids)}")
        check("S1.2 koça bağlı YETİM öğrenci kalmadı (teacher_id)",
              db.query(User).filter(User.teacher_id == coach_id).count() == 0)
        check("S1.3 koçun kitapları silindi (teacher_id)",
              db.query(_Book2).filter(_Book2.teacher_id == coach_id).count() == 0)
        check("S1.4 gerçek Zeynep'in görevi silindi",
              db.query(Task).filter(Task.id == task_id).count() == 0)
        check("S1.5 gerçek Zeynep'in denemesi silindi",
              db.query(ExamResult).filter(ExamResult.id == exam_id).count() == 0)
        check("S1.6 veli bağı silindi",
              db.query(ParentStudentLink).filter(ParentStudentLink.student_id == zeynep.id).count() == 0)

    # =========================================================================
    # Senaryo 2: demo KURUM + davet edilmiş non-demo öğretmen + onun öğrencisi
    # =========================================================================
    with SessionLocal() as db:
        res = create_demo_ecosystem(db, kind="institution", label=f"{PFX} kurum")
        seed2 = res.seed_id
        inst_id = res.institution_id
        demo_user_ids2 = {c.user_id for c in res.credentials}

        # Kurum yöneticisinin DAVET ettiği (non-demo) öğretmen + davet kaydı
        invited_teacher = User(
            email=f"{PFX}-invteacher@real.invalid",
            password_hash=hash_password("Real123!@"),
            full_name=f"{PFX} Davetli Öğretmen", role=UserRole.TEACHER,
            is_active=True, institution_id=inst_id,
        )
        db.add(invited_teacher); db.flush()
        inv = Invitation(
            token=_secrets.token_urlsafe(24), role=UserRole.TEACHER,
            institution_id=inst_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(inv); db.flush()
        inv_id = inv.id

        # Davetli öğretmenin oluşturduğu non-demo öğrenci + veli + kitap/veri
        inv_student = _mk_student(db, coach_id=invited_teacher.id, institution_id=inst_id,
                                  name=f"{PFX} Davetli Öğr. Öğrencisi")
        inv_parent = _mk_parent(db, student_id=inv_student.id, name=f"{PFX} Davetli Veli")
        ibook_id, itask_id, iexam_id = _mk_book_with_data(
            db, coach_id=invited_teacher.id, student_id=inv_student.id)
        db.commit()

        all_user_ids2 = demo_user_ids2 | {invited_teacher.id, inv_student.id, inv_parent.id}
        print(f"  kurum: demo={len(demo_user_ids2)} + davetli 3 = {len(all_user_ids2)} user; inst={inst_id}")

        # >>> SİL <<<
        counts2 = delete_demo_session(db, seed_id=seed2)
        db.commit()

        from app.models import Institution
        check("S2.1 demo kurum silindi",
              db.query(Institution).filter(Institution.id == inst_id).count() == 0)
        check("S2.2 tüm kullanıcılar silindi (demo + davetli öğretmen + öğrenci + veli)",
              _alive(db, all_user_ids2) == 0, f"kalan={_alive(db, all_user_ids2)}")
        check("S2.3 kuruma bağlı YETİM üye kalmadı (institution_id)",
              db.query(User).filter(User.institution_id == inst_id).count() == 0)
        check("S2.4 davetli öğretmene bağlı YETİM öğrenci kalmadı",
              db.query(User).filter(User.teacher_id == invited_teacher.id).count() == 0)
        check("S2.5 davetli öğretmenin kitabı silindi",
              db.query(_Book2).filter(_Book2.teacher_id == invited_teacher.id).count() == 0)
        check("S2.6 öğretmen daveti (Invitation) silindi",
              db.query(Invitation).filter(Invitation.id == inv_id).count() == 0)
        check("S2.7 davetli öğrencinin görev+denemesi silindi",
              db.query(Task).filter(Task.id == itask_id).count() == 0
              and db.query(ExamResult).filter(ExamResult.id == iexam_id).count() == 0)

    # Güvenlik: artakalan PFX kullanıcı temizliği (test izolasyonu)
    with SessionLocal() as db:
        from sqlalchemy import delete as sa_delete
        leftovers = db.query(User).filter(User.email.like(f"{PFX}-%")).all()
        if leftovers:
            db.execute(sa_delete(User).where(User.id.in_([u.id for u in leftovers])))
            db.commit()
            print(f"  (not: {len(leftovers)} artık PFX user temizlendi)")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
