# -*- coding: utf-8 -*-
"""today_no_tick GÖREV-bazlı: etkinlik-only gün de 'bugün hiç tik yapmadı' verir.

Bug (Image 34, Elvin): 4 etkinlik görev (soru=0), hiçbiri yapılmadı ama uyarı
test hacmine (planned>0) bağlı olduğu için yeşil görünüyordu. Etkinlik
engagement'a sayılır -> uyarı vermeli."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from datetime import date, datetime, timedelta, timezone
from app.database import SessionLocal
from app.models import (User, UserRole, Book, BookType, BookSection, Subject,
                        Task, TaskBookItem, TaskStatus, TaskType)
from app.services import analytics
from app.services.security import hash_password

PASS = FAIL = 0
def check(n, c, e=""):
    global PASS, FAIL
    if c: PASS += 1; print(f"  [PASS] {n}")
    else: FAIL += 1; print(f"  [FAIL] {n} {e}")

db = SessionLocal()
SUF = "_todaytick_tmp"
def clean():
    for u in db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all():
        tids = [t.id for t in db.query(Task).filter(Task.student_id == u.id).all()]
        if tids: db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
        db.query(Task).filter(Task.student_id == u.id).delete(synchronize_session=False)
        for b in db.query(Book).filter(Book.teacher_id == u.id).all():
            db.query(BookSection).filter(BookSection.book_id == b.id).delete(synchronize_session=False)
        db.query(Book).filter(Book.teacher_id == u.id).delete(synchronize_session=False)
        db.query(Subject).filter(Subject.teacher_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.commit()
clean()
def has_today_no_tick(stu):
    snap = analytics.student_snapshot(db, stu, today=date.today())
    return any(w.code == "today_no_tick" for w in snap.warnings)
try:
    coach = User(email=f"c{SUF}@x.com", full_name="C", role=UserRole.TEACHER, password_hash=hash_password("x"), is_active=True)
    db.add(coach); db.flush()
    today = date.today()
    def mkstu(name):
        s = User(email=f"{name}{SUF}@x.com", full_name=name, role=UserRole.STUDENT,
                 password_hash=hash_password("x"), is_active=True, teacher_id=coach.id, grade_level=11,
                 created_at=datetime.now(timezone.utc) - timedelta(days=30))
        db.add(s); db.flush(); return s
    def add_etkinlik(s, status=TaskStatus.PENDING):
        t = Task(student_id=s.id, date=today, type=TaskType.VIDEO, title="Video", is_draft=False, status=status)
        db.add(t); db.flush()  # kalemsiz etkinlik
        return t

    # A) Etkinlik-only, hiçbiri yapılmadı -> today_no_tick VERMELİ
    sa = mkstu("Etk0")
    add_etkinlik(sa); add_etkinlik(sa)
    db.commit()
    check("A. 2 etkinlik görev, 0 yapıldı -> today_no_tick VAR", has_today_no_tick(sa))

    # B) Etkinlik-only ama biri yapıldı -> today_no_tick YOK (engagement var)
    sb = mkstu("EtkDone")
    add_etkinlik(sb, status=TaskStatus.COMPLETED); add_etkinlik(sb)
    db.commit()
    check("B. etkinliklerden biri tamam -> today_no_tick YOK", not has_today_no_tick(sb))

    # C) Hiç görev yok -> today_no_tick YOK
    sc = mkstu("Bos")
    db.commit()
    check("C. bugün görev yok -> today_no_tick YOK", not has_today_no_tick(sc))

    # D) Taslak etkinlik -> yayınlanmamış, today_no_tick YOK
    sd = mkstu("Taslak")
    t = Task(student_id=sd.id, date=today, type=TaskType.VIDEO, title="V", is_draft=True, status=TaskStatus.PENDING)
    db.add(t); db.commit()
    check("D. yalnız taslak görev -> today_no_tick YOK", not has_today_no_tick(sd))
finally:
    clean(); db.close()
print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
