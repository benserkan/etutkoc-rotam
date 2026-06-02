# -*- coding: utf-8 -*-
"""Faz C: günlük özet maili KALDIRILDI + boş-gün eşiği 3 üst üste (görev-bazlı).

Senaryo: gerçek hesaplara dokunmadan geçici koç+öğrenci+veli kurar, program
ekler, cron_jobs.daily_summary'yi farklı günlerde çağırıp NotificationLog
üretimini doğrular.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import (
    Book, BookType, NotificationKind, NotificationLog, ParentStudentLink,
    Subject, Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.models.parent import ParentRelation
from app.services import cron_jobs
from app.services.security import hash_password

PASS = FAIL = 0
def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  [PASS] {name}")
    else:
        FAIL += 1; print(f"  [FAIL] {name}")

db = SessionLocal()
SUF = "_fazc_tmp"
created = []

def cleanup():
    db.rollback()
    for u in db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all():
        db.query(NotificationLog).filter(
            (NotificationLog.parent_id == u.id) | (NotificationLog.student_id == u.id)).delete(synchronize_session=False)
        db.query(ParentStudentLink).filter(
            (ParentStudentLink.parent_id == u.id) | (ParentStudentLink.student_id == u.id)).delete(synchronize_session=False)
        for t in db.query(Task).filter(Task.student_id == u.id).all():
            db.query(TaskBookItem).filter(TaskBookItem.task_id == t.id).delete(synchronize_session=False)
        db.query(Task).filter(Task.student_id == u.id).delete(synchronize_session=False)
        for b in db.query(Book).filter(Book.teacher_id == u.id).all():
            db.query(Subject).filter(Subject.teacher_id == u.id).delete(synchronize_session=False)
        db.query(Book).filter(Book.teacher_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.commit()

cleanup()
try:
    coach = User(email=f"coach{SUF}@x.com", full_name="Coach", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    db.add(coach); db.flush()
    stu = User(email=f"stu{SUF}@x.com", full_name="Stu", role=UserRole.STUDENT,
               password_hash=hash_password("x"), is_active=True, teacher_id=coach.id,
               created_at=datetime.now(timezone.utc) - timedelta(days=60))
    par = User(email=f"par{SUF}@x.com", full_name="Par", role=UserRole.PARENT,
               password_hash=hash_password("x"), is_active=True)
    db.add_all([stu, par]); db.flush()
    db.add(ParentStudentLink(parent_id=par.id, student_id=stu.id, relation=ParentRelation.ANNE, is_primary=True))
    subj = Subject(teacher_id=coach.id, name="Mat", order=1)
    db.add(subj); db.flush()
    book = Book(teacher_id=coach.id, name="SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
    db.add(book); db.flush()

    def add_task(d, planned, completed):
        t = Task(student_id=stu.id, date=d, type=TaskType.TEST,
                 title="Görev", is_draft=False,
                 status=TaskStatus.COMPLETED if completed >= planned and planned > 0 else (TaskStatus.PARTIAL if completed > 0 else TaskStatus.PENDING))
        db.add(t); db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=book.id, planned_count=planned, completed_count=completed))
        db.flush()
        return t

    now = datetime.now(timezone.utc)
    today = now.date()

    # --- Senaryo A: bugün AKTİF (görev tamamlandı) -> günlük özet YOK, EMPTY YOK ---
    add_task(today, 10, 10)
    db.query(NotificationLog).filter(NotificationLog.student_id == stu.id).delete(synchronize_session=False)
    res = cron_jobs.daily_summary(db, now=now)
    daily_logs = db.query(NotificationLog).filter(
        NotificationLog.student_id == stu.id, NotificationLog.kind == NotificationKind.DAILY_SUMMARY).count()
    empty_logs = db.query(NotificationLog).filter(
        NotificationLog.student_id == stu.id, NotificationLog.kind == NotificationKind.EMPTY_DAY).count()
    check("A1: aktif günde DAILY_SUMMARY üretilmez (günlük özet kaldırıldı)", daily_logs == 0)
    check("A2: aktif günde EMPTY_DAY yok", empty_logs == 0)
    check("A3: 'daily' sayacı response'ta yok (kaldırıldı), skipped_active var", "daily" not in res and res.get("skipped_active", 0) >= 1)

    # --- Senaryo B: 2 gün üst üste boş -> eşik altı, EMPTY YOK ---
    db.query(TaskBookItem).filter(TaskBookItem.task_id.in_([t.id for t in db.query(Task).filter(Task.student_id==stu.id).all()])).delete(synchronize_session=False)
    db.query(Task).filter(Task.student_id == stu.id).delete(synchronize_session=False); db.flush()
    add_task(today, 10, 0)            # bugün boş
    add_task(today - timedelta(days=1), 10, 0)  # dün boş (streak=2)
    add_task(today - timedelta(days=2), 10, 5)  # 2 gün önce dolu -> streak kesilir
    db.query(NotificationLog).filter(NotificationLog.student_id == stu.id).delete(synchronize_session=False)
    cron_jobs.daily_summary(db, now=now)
    empty_logs = db.query(NotificationLog).filter(
        NotificationLog.student_id == stu.id, NotificationLog.kind == NotificationKind.EMPTY_DAY).count()
    check("B1: 2 gün üst üste boş (eşik<3) -> EMPTY_DAY YOK", empty_logs == 0)

    # --- Senaryo C: 3 gün üst üste boş -> EMPTY_DAY üretilir ---
    db.query(TaskBookItem).filter(TaskBookItem.task_id.in_([t.id for t in db.query(Task).filter(Task.student_id==stu.id).all()])).delete(synchronize_session=False)
    db.query(Task).filter(Task.student_id == stu.id).delete(synchronize_session=False); db.flush()
    for i in range(3):
        add_task(today - timedelta(days=i), 10, 0)  # 3 gün üst üste boş
    db.query(NotificationLog).filter(NotificationLog.student_id == stu.id).delete(synchronize_session=False)
    cron_jobs.daily_summary(db, now=now)
    empty_logs = db.query(NotificationLog).filter(
        NotificationLog.student_id == stu.id, NotificationLog.kind == NotificationKind.EMPTY_DAY).all()
    check("C1: 3 gün üst üste boş -> EMPTY_DAY üretildi", len(empty_logs) == 1)

    # --- Senaryo D: eşik aşıldı + son 3g içinde uyarı var -> cooldown, tekrar atmaz ---
    cron_jobs.daily_summary(db, now=now)
    empty_logs2 = db.query(NotificationLog).filter(
        NotificationLog.student_id == stu.id, NotificationKind.EMPTY_DAY == NotificationLog.kind).count()
    check("D1: cooldown (3g) — ikinci koşuda tekrar EMPTY_DAY atmaz", empty_logs2 == 1)

    # --- Senaryo E: yeni öğrenci (hesap<5g) için boş gün — gorev_total>0 ise sayılır ---
    # (onboarding grace risk göstergelerinde; bu cron program planlıysa uyarır — beklenen)
    print(f"  (cron response son: {cron_jobs.daily_summary(db, now=now)})")

finally:
    cleanup()
    db.close()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
