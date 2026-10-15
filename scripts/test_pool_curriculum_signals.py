"""Havuz → müfredat ilerlemesi köprüsü (2026-10-13, yerel test turu 5. bulgu).

İki boşluk kapandı:
  1. Kaynaksız konulu kalemde rehberin SEANSTA işaretlediği birim müfredata yansımıyordu (yalnız havuz
     yüzdesine giriyordu) → artık kaynaksız çalışma sayılır ("devam").
  2. Havuza yazılmış ama henüz çalışılmamış konu müfredatta "başlanmadı"/"kaynak yok" görünüyordu; gün-gün
     programdaki "planlandı" (rezerv) karşılığı yoktu → açık dönemde bekleyen kalem = "planlandı".
Çift sayım yok: kitaplı test kaleminin seans işareti zaten kitap sayacına (izli koç kaydı) yazılır.

Çalıştır: PYTHONPATH=. python scripts/test_pool_curriculum_signals.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task,
    TaskBookItem, TaskStatus, Topic, Track, User, UserRole,
)
from app.models.curriculum import CurriculumModel  # noqa: E402
from app.models.pool import PERIOD_CLOSED, SOURCE_STUDENT  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.curriculum_progress import compute_curriculum_progress  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.topic_board import build_topic_board  # noqa: E402

PFX = f"pcs_{secrets.token_hex(3)}"
today = date.today()
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password("x"), full_name=f"PCS {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=40), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def statuses(db, student, coach, subject_id):
    cp = compute_curriculum_progress(db, student, coach.id)
    sub = next(s for s in cp.subjects if s.subject_id == subject_id)
    cur = {t.topic_id: (t.status, t.sourceless_completed) for t in sub.topics}
    page = build_topic_board(db, student=student, coach_id=coach.id, subject_id=subject_id)
    bs = next(s for s in page.subjects if s.subject_id == subject_id)
    board = {t.topic_id: (t.status, t.sourceless_completed) for t in bs.topics}
    return cur, board


def main() -> int:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        subj = Subject(name=f"{PFX} Fizik", teacher_id=coach.id, curriculum_model=CurriculumModel.MAARIF_LISE,
                       min_grade_level=9, max_grade_level=12, order=1)
        db.add(subj)
        db.flush()
        ids["subjects"].append(subj.id)
        tp = {}
        for i, n in enumerate(["Kuvvet", "Enerji", "Optik", "Dalgalar", "Akışkanlar", "Elektrik"], start=1):
            t = Topic(subject_id=subj.id, name=n, order=i, teacher_id=coach.id, grade_level=11)
            db.add(t)
            db.flush()
            tp[n] = t
        book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} Kitap", type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        ids["books"].append(book.id)
        sec = BookSection(book_id=book.id, label="Optik", test_count=20, order=1, topic_id=tp["Optik"].id)
        db.add(sec)
        db.flush()
        s = _user(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=11, track=Track.SAYISAL,
                  program_mode="havuz")
        sb = StudentBook(student_id=s.id, book_id=book.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        db.commit()
        sid, cid = s.id, coach.id

    try:
        with SessionLocal() as db:
            s, coach, subj = db.get(User, sid), db.get(User, cid), db.get(Subject, ids["subjects"][0])
            cur0, board0 = statuses(db, s, coach, subj.id)
            T = {t.name: t.id for t in db.query(Topic).filter(Topic.subject_id == subj.id).all()}
            check("Ö0 havuzsuz başlangıç: Kuvvet kaynak_yok · Optik başlanmadı (müfredat + pano)",
                  cur0[T["Kuvvet"]][0] == "kaynak_yok" and cur0[T["Optik"]][0] == "baslanmadi"
                  and board0[T["Kuvvet"]][0] == "kaynak_yok" and board0[T["Optik"]][0] == "baslanmadi",
                  f"{cur0} {board0}")

            p = pm.open_period(db, student=s, coach=coach, opened_on=today - timedelta(days=3))
            sec = db.query(BookSection).filter(BookSection.book_id == ids["books"][0]).first()
            book = db.get(Book, ids["books"][0])
            i_kuv = pm.add_item(db, period=p, student=s, subject=subj, quantity=5, unit="test", topic=db.get(Topic, T["Kuvvet"]))
            i_enj = pm.add_item(db, period=p, student=s, subject=subj, quantity=4, unit="sayfa", topic=db.get(Topic, T["Enerji"]))
            i_opt = pm.add_item(db, period=p, student=s, subject=subj, quantity=6, unit="test", book=book, section=sec)
            i_dlg = pm.add_item(db, period=p, student=s, subject=subj, quantity=3, unit="test", topic=db.get(Topic, T["Dalgalar"]))
            pm.remove_item(db, i_dlg, coach)
            pm.add_item(db, period=p, student=s, subject=subj, quantity=2, unit="test", topic=db.get(Topic, T["Akışkanlar"]),
                        source=SOURCE_STUDENT, created_by=s)
            i_el = pm.add_item(db, period=p, student=s, subject=subj, quantity=2, unit="test", topic=db.get(Topic, T["Elektrik"]))
            db.commit()

            cur, board = statuses(db, s, coach, subj.id)
            check("P1 kaynaksız konulu bekleyen kalem → Kuvvet PLANLANDI (müfredat + pano)",
                  cur[T["Kuvvet"]][0] == "planlandi" and board[T["Kuvvet"]][0] == "planlandi", f"{cur[T['Kuvvet']]} {board[T['Kuvvet']]}")
            check("P2 kitaplı bekleyen kalem (rezervsiz) → Optik PLANLANDI",
                  cur[T["Optik"]][0] == "planlandi" and board[T["Optik"]][0] == "planlandi", f"{cur[T['Optik']]} {board[T['Optik']]}")
            check("P3 sayfa birimli konulu kalem de planlandı (Enerji)", cur[T["Enerji"]][0] == "planlandi", str(cur[T["Enerji"]]))
            check("P4 kaldırılan kalem planlamaz (Dalgalar kaynak_yok)", cur[T["Dalgalar"]][0] == "kaynak_yok", str(cur[T["Dalgalar"]]))
            check("P5 onay bekleyen öğrenci kalemi planlamaz (Akışkanlar kaynak_yok)",
                  cur[T["Akışkanlar"]][0] == "kaynak_yok", str(cur[T["Akışkanlar"]]))

            # seans işaretleri
            pm.session_mark(db, item=i_kuv, actor=coach, count=2)
            pm.session_mark(db, item=i_enj, actor=coach, count=3)
            pm.session_mark(db, item=i_opt, actor=coach, count=2)
            db.commit()
            cur, board = statuses(db, s, coach, subj.id)
            check("S1 kaynaksız test kalemi seans işareti → Kuvvet DEVAM + kaynaksız 2 (müfredat + pano)",
                  cur[T["Kuvvet"]] == ("devam", 2) and board[T["Kuvvet"]] == ("devam", 2), f"{cur[T['Kuvvet']]} {board[T['Kuvvet']]}")
            check("S2 sayfa birimli işaret test hacmine girmez (Enerji hâlâ planlandı, kaynaksız 0)",
                  cur[T["Enerji"]] == ("planlandi", 0), str(cur[T["Enerji"]]))
            sp = db.query(SectionProgress).filter(SectionProgress.book_section_id == sec.id).first()
            check("S3 kitaplı test işareti kitap sayacına yazıldı (2) · kaynaksız SAYILMADI (çift sayım yok) · Optik devam",
                  sp.completed_count == 2 and cur[T["Optik"]] == ("devam", 0), f"sp={sp.completed_count} {cur[T['Optik']]}")

            # öğrencinin kendi kaydı + seans işareti toplanır
            t = pm.put_in_cup(db, item=i_kuv, day=today - timedelta(days=1), count=1)
            for bi in t.book_items:
                bi.completed_count = 1
            t.status = TaskStatus.COMPLETED
            t.completed_at = datetime.combine(today - timedelta(days=1), time(20, 0), tzinfo=timezone.utc)
            db.flush()
            pm.sync_item_progress(db, i_kuv)
            db.commit()
            cur, _ = statuses(db, s, coach, subj.id)
            check("S4 öğrenci kaydı (1) + seans işareti (2) = kaynaksız 3", cur[T["Kuvvet"]] == ("devam", 3), str(cur[T["Kuvvet"]]))

            # dönem kapanınca bekleyen kalem planlamaz; işaret kalıcı
            pm.close_period(db, p, closed_on=today, status=PERIOD_CLOSED)
            db.commit()
            cur, board = statuses(db, s, coach, subj.id)
            check("K1 dönem kapandı → bekleyen Elektrik artık planlanmış değil (kaynak_yok)",
                  cur[T["Elektrik"]][0] == "kaynak_yok" and board[T["Elektrik"]][0] == "kaynak_yok", str(cur[T["Elektrik"]]))
            check("K2 kapanmış dönemin seans işareti kalıcı (Kuvvet devam, 3)", cur[T["Kuvvet"]] == ("devam", 3), str(cur[T["Kuvvet"]]))
            _ = i_el
    finally:
        with SessionLocal() as db:
            u = ids["users"]
            tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
            if tids:
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
            db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
            db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
            db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
            sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
            if sbs:
                db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
            db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
            db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
            db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
            db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
            db.execute(sa_delete(User).where(User.id.in_(u)))
            db.commit()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
