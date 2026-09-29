"""Sınava yetişme — ders bazlı aktif kaynak modeli (2026-09-29).

  1. Hiç görev verilmeyen kaynak kalan işe GİRMEZ (Zeynep: 800 testlik seri)
  2. Yeni başlanan kaynak (3 gün önce ilk görev) kendiliğinden AKTİF
  3. 21+ gündür görev verilmeyen kaynak BIRAKILDI sayılır, kalana girmez
  4. Bitmiş kaynak ve koçun kapattığı konu kalana girmez
  5. Aynı kitap iki kez atanmışsa tek sayılır
  6. Hız = son 21 günde çözülen / 21 · bitiş tarihi · geride gün
  7. Geçmişi 14 günden kısa ders → 'erken', kart yok
  8. Geciken ders → exam_behind kartı (kanıtta aktif + bırakılan kaynak)
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject, Task,
    TaskBookItem, TaskStatus, TaskType, Topic, User, UserRole,
)
from app.models.topic_closure import TopicClosure
from app.services import analytics
from app.services.exam_readiness import compute_readiness
from app.services.security import hash_password
from app.services.student_flags import evaluate_flags

PFX = f"exr_{secrets.token_hex(3)}"
today = date.today()
now = datetime.now(timezone.utc)
ids = {"users": [], "books": [], "subjects": [], "topics": []}
coach = 0
passed = 0
failed: list[str] = []
analytics._tr_now = lambda: datetime.combine(today, time(12, 0), tzinfo=timezone.utc)


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def mk_student(tag):
    with SessionLocal() as db:
        s = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password("x"),
                 full_name=f"{PFX} {tag}", role=UserRole.STUDENT, teacher_id=coach,
                 grade_level=12, is_active=True, created_at=now - timedelta(days=90),
                 last_seen_at=now)
        db.add(s)
        db.commit()
        ids["users"].append(s.id)
        return s.id


def mk_subject(name):
    with SessionLocal() as db:
        sub = Subject(name=f"{PFX} {name}", teacher_id=coach)
        db.add(sub)
        db.commit()
        ids["subjects"].append(sub.id)
        return sub.id


def mk_book(sub, name, tests, topic=None):
    with SessionLocal() as db:
        b = Book(teacher_id=coach, subject_id=sub, name=f"{name}", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        sec = BookSection(book_id=b.id, label="Ü1", test_count=tests, topic_id=topic)
        db.add(sec)
        db.commit()
        ids["books"].append(b.id)
        return b.id, sec.id


def assign(sid, bk, completed=0, times=1):
    b, sec = bk
    with SessionLocal() as db:
        for _ in range(times):
            sb = StudentBook(student_id=sid, book_id=b)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec,
                                   reserved_count=0, completed_count=completed))
        db.commit()


def task(sid, day, bk, planned, done):
    b, sec = bk
    with SessionLocal() as db:
        t = Task(student_id=sid, date=day, type=TaskType.TEST, title="T", is_draft=False,
                 published_at=now, status=TaskStatus.COMPLETED if done >= planned else TaskStatus.PENDING,
                 completed_at=now if done >= planned else None)
        db.add(t)
        db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=b, book_section_id=sec,
                            planned_count=planned, completed_count=done))
        db.commit()


def D(n):
    return today - timedelta(days=n)


def cleanup():
    with SessionLocal() as db:
        sids = [u for u in ids["users"] if u != coach]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(sids or [0]))]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids or [0])))
        db.execute(sa_delete(Task).where(Task.id.in_(tids or [0])))
        db.execute(sa_delete(TopicClosure).where(TopicClosure.student_id.in_(sids or [0])))
        sb = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids or [0]))]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sb or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sb or [0])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"] or [0])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"] or [0])))
        db.execute(sa_delete(Topic).where(Topic.id.in_(ids["topics"] or [0])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"] or [0])))
        db.execute(sa_delete(User).where(User.id.in_(ids["users"] or [0])))
        db.commit()


def main() -> int:
    global coach
    with SessionLocal() as db:
        c = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x"), full_name="c",
                 role=UserRole.TEACHER, is_active=True)
        db.add(c)
        db.commit()
        coach = c.id
    ids["users"].append(coach)
    exam_in = {"days": 200}
    analytics.get_exam_date = lambda db, s: today + timedelta(days=exam_in["days"])
    try:
        s = mk_student("mat")
        mat = mk_subject("Mat")
        with SessionLocal() as db:
            tp = Topic(name=f"{PFX} Kapalı konu", subject_id=mat, teacher_id=coach, order=1)
            db.add(tp)
            db.commit()
            ids["topics"].append(tp.id)
            closed_topic = tp.id
        A = mk_book(mat, f"{PFX} A kaynak", 100)
        B = mk_book(mat, f"{PFX} B kullanılmayan", 300)
        C = mk_book(mat, f"{PFX} C yeni", 50)
        Dd = mk_book(mat, f"{PFX} D bırakılan", 60)
        E = mk_book(mat, f"{PFX} E biten", 20)
        K = mk_book(mat, f"{PFX} K kapalı konu", 40, topic=closed_topic)
        assign(s, A, completed=20)
        A2 = mk_book(mat, f"{PFX} A kaynak", 100)   # aynı adla ikinci kitap kaydı
        assign(s, A2, completed=5)
        assign(s, B)
        assign(s, C, completed=4)
        assign(s, Dd, completed=10)
        assign(s, E, completed=20)
        assign(s, K)
        with SessionLocal() as db:
            db.add(TopicClosure(student_id=s, topic_id=closed_topic, closed_by_id=coach))
            db.commit()
        for k in range(1, 22):                     # A: 21 gün, günde 2 test çözüldü
            task(s, D(k), A, 2, 2)
        task(s, D(2), A2, 1, 1)                   # ikinci kayıttan da görev verilmiş
        task(s, D(3), C, 2, 2)                    # C yeni başlandı
        task(s, D(30), Dd, 2, 2)                  # D 30 gün önce bırakıldı
        task(s, D(5), E, 2, 2)                    # E aktif ama bitmiş
        task(s, D(4), K, 2, 0)                    # K aktif ama konusu kapalı
        with SessionLocal() as db:
            rd = compute_readiness(db, db.get(User, s), today)
        sr = next((x for x in rd.subjects if x.subject_id == mat), None)
        names = [b["name"] for b in sr.active_books] if sr else []
        chk("1 kullanılmayan kaynak kalana girmez", sr and not any("kullanılmayan" in n for n in names), str(names))
        chk("2 yeni başlanan kaynak aktif", any("C yeni" in n for n in names), str(names))
        chk("3 bırakılan kaynak listede, kalana girmez", sr and any("D bırakılan" in n for n in sr.dropped_books)
            and not any("D bırakılan" in n for n in names), str(sr.dropped_books if sr else None))
        chk("4 biten kaynak + kapalı konu kalana girmez",
            sr and any("E biten" in n for n in sr.finished_books) and not any("K kapalı" in n for n in names), str(sr))
        chk("5 aynı adlı iki kitap kaydı tek sayılır: kalan 80 + 46 = 126", sr and sr.remaining_tests == 126,
            str(sr.remaining_tests if sr else None))
        # hız: son 21 gün A 42 + A2 1 + C 2 + E 2 = 47 test / 21 gün
        chk("6 hız = 47/21 test/gün", sr and abs(sr.pace - 47 / 21) < 0.01, str(sr.pace if sr else None))
        chk("6b bitiş hedeften önce → yetişiyor", sr and sr.status == "ok" and sr.days_late <= 0,
            f"{sr.status} {sr.days_late}" if sr else "")
        exam_in["days"] = 70                        # hedef = sınav − 6 hafta = 28 gün sonra
        with SessionLocal() as db:
            st = db.get(User, s)
            rd = compute_readiness(db, st, today)
            rep = evaluate_flags(db, st, today, None)
        sr = next(x for x in rd.subjects if x.subject_id == mat)
        chk("6c 126 test / 2.24 = 57 gün > 28 gün → geride", sr.status == "late" and sr.days_late == 57 - 28,
            f"{sr.status} {sr.days_late}")
        eb = next((w for w in rep.primary if w.code == f"exam_behind_{mat}"), None)
        chk("8 geciken ders kartı + kanıtta bırakılan kaynak",
            eb is not None and any(l.startswith("Bırakılan") for l, _ in eb.evidence), str([w.code for w in rep.primary]))
        chk("8b sınava 70 gün → sarı (60 gün altı kırmızı)", eb is not None and eb.level == "amber",
            eb.level if eb else "")

        # 7 kısa geçmiş
        s2 = mk_student("yeni")
        fiz = mk_subject("Fiz")
        F = mk_book(fiz, f"{PFX} F", 200)
        assign(s2, F)
        for k in (1, 2, 3):
            task(s2, D(k), F, 1, 1)
        with SessionLocal() as db:
            st = db.get(User, s2)
            rd = compute_readiness(db, st, today)
            rep = evaluate_flags(db, st, today, None)
        sr = next(x for x in rd.subjects if x.subject_id == fiz)
        chk("7 geçmiş 3 gün → 'erken', kart yok", sr.status == "early"
            and not any(w.code.startswith("exam_") for w in rep.primary), f"{sr.status}")
    finally:
        cleanup()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
