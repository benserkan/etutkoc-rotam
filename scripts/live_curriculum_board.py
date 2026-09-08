"""Müfredat paneli — GERÇEK TARAYICI doğrulaması (P5, 2026-09-07).

Dev sunucu (:3000 + :8081) + Playwright ister. Kendi seed'ini kurar/temizler.

Seed EMİR VAKASINI kurar: bir konuda görevde yüksek doğruluk AMA denemede
yanlış → panel "kapatmadan önce bak" demeli. Tek başına hiçbir sayı bunu
söyleyemez; panelin varlık sebebi bu.

Senaryolar:
   1. Panel açılır, ders özeti görünür (kapalı/toplam · kapsama)
   2. Konu satırı tıklanınca detay açılır (çözülen · doğruluk · kalan)
   3. TEMİZ konu "kapatmaya hazır" der
   4. EMİR VAKASI: denemede yanlış olan konu "kapatmadan önce bak" der
   5. "Konuyu kapat" → konu kapanır, satır üstü çizilir
   6. Kapatılan konu "Yeniden aç" ile geri alınır
   7. "+3 test" → görev oluşur
   8. Kaynaksız konuda "Kaynaksız" → kaynaksız görev oluşur (rezerv tutmaz)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets
from datetime import date, timedelta

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    ExamResult,
    ExamSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskType,
    Topic,
    TopicClosure,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.exam_result import ExamResultQuestion
from app.services.security import hash_password

WEB = "http://localhost:3000"
PFX = f"lcb_{secrets.token_hex(3)}"
PWD_PLAIN = "LiveBoard!234"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD_PLAIN),
                     full_name="Panel Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD_PLAIN),
                  full_name="Panel Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()

        subj = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
        db.add(subj)
        db.flush()
        t_clean = Topic(subject_id=subj.id, name="Temiz Konu", order=1,
                        teacher_id=coach.id)
        t_exam = Topic(subject_id=subj.id, name="Yaş Problemleri", order=2,
                       teacher_id=coach.id)
        t_free = Topic(subject_id=subj.id, name="Kaynaksız Konu", order=3,
                       teacher_id=coach.id)
        db.add_all([t_clean, t_exam, t_free])
        db.flush()

        book = Book(name=f"{PFX} SB", teacher_id=coach.id, subject_id=subj.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        s_clean = BookSection(book_id=book.id, label="Temiz Bölüm", order=1,
                              test_count=12, topic_id=t_clean.id)
        s_exam = BookSection(book_id=book.id, label="Yaş Bölümü", order=2,
                             test_count=12, topic_id=t_exam.id)
        db.add_all([s_clean, s_exam])
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        db.add_all([
            SectionProgress(student_book_id=sb.id, book_section_id=s_clean.id,
                            reserved_count=0, completed_count=6),
            SectionProgress(student_book_id=sb.id, book_section_id=s_exam.id,
                            reserved_count=0, completed_count=6),
        ])
        db.flush()

        def solve(sec, tests, correct, wrong, off):
            t = Task(student_id=st.id, date=date.today() - timedelta(days=off),
                     type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=sec.id, planned_count=tests,
                                completed_count=tests, correct_count=correct,
                                wrong_count=wrong))
            db.flush()

        solve(s_clean, 6, 56, 4, 5)    # %93 temiz → ready
        solve(s_exam, 6, 58, 2, 6)     # %97 AMA denemede yanlış → caution

        ex = ExamResult(student_id=st.id, title="Deneme", exam_date=date.today(),
                        section=ExamSection.TYT, total_correct=50, total_wrong=10,
                        total_blank=0, net=47.5, created_by_id=coach.id)
        db.add(ex)
        db.flush()
        for _ in range(2):
            db.add(ExamResultQuestion(exam_result_id=ex.id, topic_id=t_exam.id,
                                      result="yanlis"))
        db.commit()
        return {
            "coach": coach.id, "student": st.id, "subject": subj.id,
            "book": book.id, "exam": ex.id, "t_free": t_free.id,
            "email": f"{PFX}_t@test.invalid",
        }


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uid = [ids["coach"], ids["student"]]
        db.execute(sa_delete(TopicClosure).where(TopicClosure.student_id.in_(uid)))
        db.execute(sa_delete(ExamResultQuestion)
                   .where(ExamResultQuestion.exam_result_id == ids["exam"]))
        db.execute(sa_delete(ExamResult).where(ExamResult.id == ids["exam"]))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uid)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        sbids = [r[0] for r in db.query(StudentBook.id)
                 .filter(StudentBook.book_id == ids["book"]).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress)
                       .where(SectionProgress.student_book_id.in_(sbids)))
            db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
        db.execute(sa_delete(Book).where(Book.id == ids["book"]))
        db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subject"]))
        db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()


def _tasks(student_id: int) -> int:
    with SessionLocal() as db:
        return db.query(Task).filter(Task.student_id == student_id).count()


def _closed(student_id: int) -> int:
    with SessionLocal() as db:
        return (db.query(TopicClosure)
                .filter(TopicClosure.student_id == student_id).count())


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1500, "height": 1000})

            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD_PLAIN)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            page.goto(f"{WEB}/teacher/students/{ids['student']}/week",
                      wait_until="networkidle")
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(1200)

            # ---- 1. Panel (v2 şerit, 2026-09-08). Müfredat varsayılan olarak
            #         sabit DEĞİL → şeritteki simgesinden PEEK açılır; bu testte
            #         dışarı-tıklama kapatmasın diye raptiyeyle panele yerleştir.
            sec = page.query_selector('[data-section="week:curriculum"]')
            if sec is None:
                rail_btn = page.query_selector('[data-rail="week:curriculum"]')
                if rail_btn:
                    rail_btn.click()
                    page.wait_for_timeout(800)
                    pin = page.query_selector('[data-section="week:curriculum"] button[aria-pressed]')
                    if pin:
                        pin.click()
                        page.wait_for_timeout(600)
                sec = page.query_selector('[data-section="week:curriculum"]')
            check("0. Müfredat paneli sağ panelde", sec is not None)
            if sec is None:
                page.screenshot(path="/tmp/board_fail.png")
                b.close()
                return 1
            if sec.get_attribute("data-open") != "1":
                sec.query_selector("button[aria-expanded]").click()
            page.wait_for_timeout(2500)
            check("1. panel açılır ve konular listelenir",
                  page.query_selector('text="Temiz Konu"') is not None)

            # ---- 2+3. Temiz konu detayı
            page.click('[data-section="week:curriculum"] button:has-text("Temiz Konu")')
            page.wait_for_timeout(1200)
            ready = page.query_selector("text=kapatmaya hazır")
            check("2/3. temiz konu detayı + 'kapatmaya hazır' ipucu",
                  ready is not None)

            # ---- 5. Konuyu kapat
            before_closed = _closed(ids["student"])
            page.click('button:has-text("Konuyu kapat")')
            page.wait_for_timeout(2500)
            after_closed = _closed(ids["student"])
            check("5. 'Konuyu kapat' → kapatma kaydı oluştu",
                  after_closed == before_closed + 1,
                  f"{before_closed} → {after_closed}")

            # ---- 6. Yeniden aç
            reopen = page.query_selector('button:has-text("Yeniden aç")')
            check("6a. kapatılan konuda 'Yeniden aç' düğmesi çıkar",
                  reopen is not None)
            if reopen:
                reopen.click()
                page.wait_for_timeout(2200)
                check("6b. yeniden açma kaydı siler",
                      _closed(ids["student"]) == before_closed,
                      f"kalan={_closed(ids['student'])}")

            # ---- 4. EMİR VAKASI
            page.click('[data-section="week:curriculum"] button:has-text("Yaş Problemleri")')
            page.wait_for_timeout(1500)
            caution = page.query_selector("text=kapatmadan önce bak")
            check(
                "4. görevde %97 AMA denemede yanlış → 'kapatmadan önce bak'",
                caution is not None,
            )

            # ---- 7. +3 test
            before = _tasks(ids["student"])
            plus = page.query_selector('button:has-text("+3 test")')
            check("7a. '+3 test' düğmesi var", plus is not None)
            if plus:
                plus.click()
                page.wait_for_timeout(2500)
                check("7b. '+3 test' → görev oluştu",
                      _tasks(ids["student"]) == before + 1,
                      f"{before} → {_tasks(ids['student'])}")

            # ---- 8. Kaynaksız konu
            free = page.query_selector('[data-section="week:curriculum"] button:has-text("Kaynaksız Konu")')
            check("8a. kaynağı olmayan konu da panelde listelenir",
                  free is not None)
            if free:
                free.click()
                page.wait_for_timeout(1200)
                before = _tasks(ids["student"])
                # DİKKAT: 'Kaynaksız Konu' satır butonu da "Kaynaksız" içerir;
                # has-text ilkini yakalayıp detayı kapatıyordu. Tam eşleşme şart.
                btn = page.query_selector('button:text-is("Kaynaksız ver")')
                if btn:
                    btn.click()
                    page.wait_for_timeout(2500)
                ok = _sourceless_ok(ids["student"], ids["t_free"])
                check("8b. 'Kaynaksız' → konuya bağlı kitapsız görev oluştu",
                      _tasks(ids["student"]) == before + 1 and ok,
                      f"gorev={_tasks(ids['student'])} konulu={ok}")

            page.screenshot(path="/tmp/board_final.png")
            b.close()
    finally:
        cleanup(ids)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


def _sourceless_ok(student_id: int, topic_id: int) -> bool:
    with SessionLocal() as db:
        return (
            db.query(TaskBookItem)
            .join(Task, Task.id == TaskBookItem.task_id)
            .filter(
                Task.student_id == student_id,
                TaskBookItem.book_id.is_(None),
                TaskBookItem.topic_id == topic_id,
            )
            .count()
            > 0
        )


if __name__ == "__main__":
    raise SystemExit(main())
