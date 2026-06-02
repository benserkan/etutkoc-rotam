# -*- coding: utf-8 -*-
"""KONTROL MEKANİZMASI — kart sayıları tutarlılık + deneme≠test invariant'ları.

Amaç (kullanıcı 2026-06-02): "Ya ben sürekli bu kartların doğruluğunu mu
sorgulayacağım, yok mu bir kontrol mekanizması." → Bu test bilinen bir "golden
senaryo" kurar (test + deneme + tam deneme + etkinlik görevleri) ve TÜM kart
kaynaklarının (gorev_stats truth · veli pano · veli detay · öğrenci gün ·
projeksiyon) AYNI ve DOĞRU sayıyı verdiğini doğrular. Herhangi bir yüzey deneme'yi
test'e karıştırırsa ya da görev sayıları yüzeyler arası tutmazsa kırmızı verir.

Çalıştır: PYTHONPATH=. python scripts/test_card_consistency.py
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
from app.models.parent import ParentRelation, ParentStudentLink
from app.services import analytics, gorev_stats
from app.services.parent_view import list_parent_students, student_overview
from app.routes.api_v2.student import _build_day_summary
from app.services.security import hash_password

PASS = FAIL = 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  [PASS] {name}")
    else:
        FAIL += 1; print(f"  [FAIL] {name}  {extra}")

db = SessionLocal()
SUF = "_cardcons_tmp"

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
        db.query(ParentStudentLink).filter(
            (ParentStudentLink.parent_id == u.id) | (ParentStudentLink.student_id == u.id)).delete(synchronize_session=False)
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
    stu = User(email=f"s{SUF}@x.com", full_name="S", role=UserRole.STUDENT,
               password_hash=hash_password("x"), is_active=True, teacher_id=coach.id,
               grade_level=8, created_at=datetime.now(timezone.utc) - timedelta(days=90))
    par = User(email=f"p{SUF}@x.com", full_name="P", role=UserRole.PARENT,
               password_hash=hash_password("x"), is_active=True)
    db.add_all([stu, par]); db.flush()
    db.add(ParentStudentLink(parent_id=par.id, student_id=stu.id, relation=ParentRelation.ANNE, is_primary=True))
    subj = Subject(teacher_id=coach.id, name="Mat", order=1)
    db.add(subj); db.flush()
    sb_book = Book(teacher_id=coach.id, name="SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
    dn_book = Book(teacher_id=coach.id, name="GD", type=BookType.GENEL_DENEME, subject_id=subj.id)
    db.add_all([sb_book, dn_book]); db.flush()
    sb_sec = BookSection(book_id=sb_book.id, label="B1", order=1, test_count=200)
    dn_sec = BookSection(book_id=dn_book.id, label="D", order=1, test_count=50)
    db.add_all([sb_sec, dn_sec]); db.flush()

    today = date.today()

    def add(d, ttype, status, items):
        t = Task(student_id=stu.id, date=d, type=ttype, title="G", is_draft=False, status=status)
        db.add(t); db.flush()
        for (bid, sid, planned, completed, label) in items:
            db.add(TaskBookItem(task_id=t.id, book_id=bid, book_section_id=sid,
                                planned_count=planned, completed_count=completed, label=label))
        db.flush()
        return t

    # GOLDEN SENARYO (bugün):
    #  - 2 test görev: (10/10 done) + (10/5 partial, NOT done)
    #  - 1 deneme görev (1 deneme, done)
    #  - 1 tam deneme (90 soru, done, kitapsız)
    #  - 1 etkinlik (video, done, kalemsiz)
    add(today, TaskType.TEST, TaskStatus.COMPLETED, [(sb_book.id, sb_sec.id, 10, 10, None)])
    add(today, TaskType.TEST, TaskStatus.PARTIAL, [(sb_book.id, sb_sec.id, 10, 5, None)])
    add(today, TaskType.TEST, TaskStatus.COMPLETED, [(dn_book.id, dn_sec.id, 1, 1, None)])
    add(today, TaskType.TEST, TaskStatus.COMPLETED, [(None, None, 90, 90, "Tam Deneme")])
    add(today, TaskType.VIDEO, TaskStatus.COMPLETED, [])
    # Geçmiş (son 7 gün penceresi için): dün 1 test görev done
    add(today - timedelta(days=1), TaskType.TEST, TaskStatus.COMPLETED, [(sb_book.id, sb_sec.id, 8, 8, None)])

    # Envanter: SB 200 test + deneme kitabı 50 (projeksiyon test-only doğrulama)
    sba = StudentBook(student_id=stu.id, book_id=sb_book.id)
    dna = StudentBook(student_id=stu.id, book_id=dn_book.id)
    db.add_all([sba, dna]); db.flush()
    db.add(SectionProgress(student_book_id=sba.id, book_section_id=sb_sec.id, reserved_count=0, completed_count=18))
    db.add(SectionProgress(student_book_id=dna.id, book_section_id=dn_sec.id, reserved_count=0, completed_count=1))
    db.commit()

    # ---- TRUTH (gorev_stats — tek kaynak) ----
    today_tasks = db.query(Task).filter(Task.student_id == stu.id, Task.date == today).all()
    # book/section joinedload garanti için reload
    from sqlalchemy.orm import joinedload
    opts = joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject)
    today_tasks = (db.query(Task).options(opts)
                   .filter(Task.student_id == stu.id, Task.date == today).all())
    T = gorev_stats.summarize(today_tasks)
    print(f"TRUTH bugün: gorev={T.gorev_done}/{T.gorev_total} test={T.test_completed}/{T.test_planned} "
          f"deneme={T.cat_total['deneme']+T.cat_total['tam_deneme']} etkinlik={T.cat_total['etkinlik']}")

    # Beklenen: 5 görev, 4 done (partial test done DEĞİL); test 15/20; deneme 2 (1 deneme+1 tam); etkinlik 1
    check("TRUTH.1 bugün görev=5", T.gorev_total == 5, f"got {T.gorev_total}")
    check("TRUTH.2 bugün done=4 (partial test sayılmaz)", T.gorev_done == 4, f"got {T.gorev_done}")
    check("TRUTH.3 test_planned=20 (tam deneme 90 + deneme 1 HARİÇ)", T.test_planned == 20, f"got {T.test_planned}")
    check("TRUTH.4 test_completed=15", T.test_completed == 15, f"got {T.test_completed}")
    check("TRUTH.5 deneme=2 (1 deneme + 1 tam deneme)", (T.cat_total['deneme']+T.cat_total['tam_deneme']) == 2)
    check("TRUTH.6 etkinlik=1", T.cat_total['etkinlik'] == 1)
    # INVARIANT: kategoriler toplamı = görev toplamı
    cat_sum = sum(T.cat_total[c] for c in gorev_stats.GOREV_CATEGORIES)
    check("INV.A kategoriler toplamı = görev toplamı", cat_sum == T.gorev_total, f"{cat_sum} vs {T.gorev_total}")
    # INVARIANT: test_planned, tam-deneme'nin 90'ını ASLA içermez
    check("INV.B test_planned < tam-deneme soru sayısı (90 karışmadı)", T.test_planned < 90)

    # ---- ÖĞRENCİ GÜN kartı (_build_day_summary) ----
    DS = _build_day_summary(today_tasks)
    check("GÜN.1 gorev_total = TRUTH", DS.gorev_total == T.gorev_total, f"{DS.gorev_total}")
    check("GÜN.2 gorev_done = TRUTH", DS.gorev_done == T.gorev_done, f"{DS.gorev_done}")
    check("GÜN.3 test_planned = TRUTH (deneme HARİÇ)", DS.test_planned == T.test_planned, f"{DS.test_planned}")
    check("GÜN.4 deneme_count = TRUTH", DS.deneme_count == (T.cat_total['deneme']+T.cat_total['tam_deneme']))

    # ---- VELİ PANO kartı (list_parent_students) ----
    children = list_parent_students(db, par)
    c = next(ch for ch in children if ch["student_id"] == stu.id)
    check("VELİ-PANO.1 today_gorev_total = TRUTH", c["today_gorev_total"] == T.gorev_total, f"{c['today_gorev_total']}")
    check("VELİ-PANO.2 today_gorev_done = TRUTH", c["today_gorev_done"] == T.gorev_done, f"{c['today_gorev_done']}")
    # Hafta (son 7 gün) = bugün 5 + dün 1 = 6 görev; done = bugün 4 + dün 1 = 5
    check("VELİ-PANO.3 week_gorev_total=6 (bugün5+dün1)", c["week_gorev_total"] == 6, f"{c['week_gorev_total']}")
    check("VELİ-PANO.4 week_gorev_done=5", c["week_gorev_done"] == 5, f"{c['week_gorev_done']}")
    # Hafta test hacmi = bugün 20 + dün 8 = 28 (deneme/tam-deneme HARİÇ)
    check("VELİ-PANO.5 week_test_planned=28 (deneme HARİÇ)", c["week_test_planned"] == 28, f"{c['week_test_planned']}")

    # ---- VELİ DETAY (student_overview) ----
    ov = student_overview(db, par, stu.id)
    check("VELİ-DETAY.1 today.gorev_done = TRUTH", ov["today"]["gorev_done"] == T.gorev_done)
    check("VELİ-DETAY.2 week.gorev_total=6", ov["week"]["gorev_total"] == 6, f"{ov['week']['gorev_total']}")
    check("VELİ-DETAY.3 week.test_planned=28 (deneme HARİÇ)", ov["week"]["test_planned"] == 28, f"{ov['week']['test_planned']}")

    # ---- TUTARLILIK: yüzeyler AYNI bugün-görev sayısını veriyor ----
    check("TUTARLILIK bugün-görev: gün==veli-pano==veli-detay",
          DS.gorev_done == c["today_gorev_done"] == ov["today"]["gorev_done"] == T.gorev_done)

    # ---- PROJEKSİYON izole (deneme envanteri girmez) ----
    proj = analytics.compute_projection(db, stu, today, window_days=28, buffer_days=5)
    # SB envanter 200, deneme kitabı 50 → test-only total = 200
    check("PROJ.1 total_tests=200 (deneme kitabı 50 HARİÇ)", proj.total_tests == 200, f"{proj.total_tests}")
    check("PROJ.2 completed=18 (deneme tamamlaması 1 HARİÇ)", proj.completed == 18, f"{proj.completed}")

finally:
    cleanup()
    db.close()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
