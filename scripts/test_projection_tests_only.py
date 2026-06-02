# -*- coding: utf-8 -*-
"""Projeksiyon izolasyonu: deneme envanteri/tamamlaması projeksiyona GİRMEZ.

Senaryo (geçici hesap): öğrenciye 1 soru bankası (100 test) + 1 genel deneme
kitabı (40 deneme) atanır. Geçmişte hem test hem deneme görevleri tamamlanır.
compute_projection / inventory_totals / recent_rate tests_only=True ile YALNIZ
soru bankasını saymalı.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.services import analytics
from app.services.security import hash_password

PASS = FAIL = 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  [PASS] {name}")
    else:
        FAIL += 1; print(f"  [FAIL] {name} {extra}")

db = SessionLocal()
SUF = "_projiso_tmp"

def cleanup():
    db.rollback()
    for u in db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all():
        tids = [t.id for t in db.query(Task).filter(Task.student_id == u.id).all()]
        if tids:
            db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
        db.query(Task).filter(Task.student_id == u.id).delete(synchronize_session=False)
        sbids = [sb.id for sb in db.query(StudentBook).filter(StudentBook.student_id == u.id).all()]
        if sbids:
            db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbids)).delete(synchronize_session=False)
        db.query(StudentBook).filter(StudentBook.student_id == u.id).delete(synchronize_session=False)
        for b in db.query(Book).filter(Book.teacher_id == u.id).all():
            db.query(BookSection).filter(BookSection.book_id == b.id).delete(synchronize_session=False)
        db.query(Book).filter(Book.teacher_id == u.id).delete(synchronize_session=False)
        db.query(Subject).filter(Subject.teacher_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.commit()

cleanup()
try:
    coach = User(email=f"c{SUF}@x.com", full_name="C", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    db.add(coach); db.flush()
    # Sınav tarihi ileride (projeksiyon anlamlı olsun)
    stu = User(email=f"s{SUF}@x.com", full_name="S", role=UserRole.STUDENT,
               password_hash=hash_password("x"), is_active=True, teacher_id=coach.id,
               grade_level=8, created_at=datetime.now(timezone.utc) - timedelta(days=90))
    db.add(stu); db.flush()
    subj = Subject(teacher_id=coach.id, name="Mat", order=1)
    db.add(subj); db.flush()

    # Soru bankası: 100 test (1 bölüm)
    sb_book = Book(teacher_id=coach.id, name="SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
    db.add(sb_book); db.flush()
    sb_sec = BookSection(book_id=sb_book.id, label="Bölüm 1", order=1, test_count=100)
    db.add(sb_sec); db.flush()
    # Genel deneme kitabı: 40 "deneme"
    dn_book = Book(teacher_id=coach.id, name="GD", type=BookType.GENEL_DENEME, subject_id=subj.id)
    db.add(dn_book); db.flush()
    dn_sec = BookSection(book_id=dn_book.id, label="Denemeler", order=1, test_count=40)
    db.add(dn_sec); db.flush()

    # Envantere ata + ilerleme (test 30 tamam, deneme 10 tamam)
    sb_assign = StudentBook(student_id=stu.id, book_id=sb_book.id)
    dn_assign = StudentBook(student_id=stu.id, book_id=dn_book.id)
    db.add_all([sb_assign, dn_assign]); db.flush()
    db.add(SectionProgress(student_book_id=sb_assign.id, book_section_id=sb_sec.id, reserved_count=0, completed_count=30))
    db.add(SectionProgress(student_book_id=dn_assign.id, book_section_id=dn_sec.id, reserved_count=0, completed_count=10))
    db.flush()

    today = date.today()
    # Geçmiş görevler: her gün hem test (10) hem deneme (2) tamamlanmış
    for i in range(1, 15):
        d = today - timedelta(days=i)
        t1 = Task(student_id=stu.id, date=d, type=TaskType.TEST, title="Test", is_draft=False, status=TaskStatus.COMPLETED)
        db.add(t1); db.flush()
        db.add(TaskBookItem(task_id=t1.id, book_id=sb_book.id, book_section_id=sb_sec.id, planned_count=10, completed_count=10))
        t2 = Task(student_id=stu.id, date=d, type=TaskType.TEST, title="Deneme", is_draft=False, status=TaskStatus.COMPLETED)
        db.add(t2); db.flush()
        db.add(TaskBookItem(task_id=t2.id, book_id=dn_book.id, book_section_id=dn_sec.id, planned_count=2, completed_count=2))
    db.flush()

    # --- inventory_totals ---
    tot_all, comp_all, _ = analytics.inventory_totals(db, stu.id, tests_only=False)
    tot_t, comp_t, _ = analytics.inventory_totals(db, stu.id, tests_only=True)
    check("1. inventory tests_only=False = 140 (100 test + 40 deneme)", tot_all == 140, f"got {tot_all}")
    check("2. inventory tests_only=True = 100 (yalnız soru bankası)", tot_t == 100, f"got {tot_t}")
    check("3. completed tests_only=True = 30 (deneme 10 HARİÇ)", comp_t == 30, f"got {comp_t}")
    check("3b. completed all = 40 (30+10)", comp_all == 40, f"got {comp_all}")

    # --- recent_rate ---
    rate_all = analytics.recent_rate(db, stu.id, today, 7, tests_only=False)
    rate_t = analytics.recent_rate(db, stu.id, today, 7, tests_only=True)
    # 7g pencere bugun + onceki 6 gun doludur (test 10 + deneme 2 = 12/gun).
    # all = 6*12/7 ; test = 6*10/7. Oran tam 1.2 (deneme +%20).
    check("4. rate all > rate test (deneme dahil daha yuksek)", rate_all > rate_t, f"all={rate_all} test={rate_t}")
    check("5. rate_all = rate_test * 1.2 (deneme 2 / test 10 = +%20)", abs(rate_all - rate_t * 1.2) < 0.01, f"all={rate_all} test={rate_t}")

    # --- compute_projection (test-only izole) ---
    proj = analytics.compute_projection(db, stu, today, window_days=28, buffer_days=5)
    check("6. projection.total_tests = 100 (deneme envanteri girmez)", proj.total_tests == 100, f"got {proj.total_tests}")
    check("7. projection.completed = 30 (deneme tamamlamasi girmez)", proj.completed == 30, f"got {proj.completed}")
    remaining = proj.total_tests - proj.completed
    check("8. kalan is = 70 (yalniz test)", remaining == 70, f"got {remaining}")
    # rate_per_day DOW-agirlikli test-only ortalama. Deneme uniform +%20 ekleseydi
    # rate de ×1.2 olurdu. Test-only ~5.0 < deneme-dahil ~6.0 → izolasyon kaniti.
    check("9. projection.rate_per_day test-only (<5.5; deneme dahil ~6.0 olurdu)", 0 < proj.rate_per_day < 5.5, f"got {proj.rate_per_day}")

    print(f"\n  Özet: envanter test={tot_t}/all={tot_all} · hız test={rate_t}/all={rate_all} · "
          f"proj total={proj.total_tests} completed={proj.completed} rate={proj.rate_per_day:.1f}")

finally:
    cleanup()
    db.close()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
