"""Canlı tarayıcı — öğrenci "Havuza kalem ekle" müfredat/kitap eşleşmeli akış (2026-10-22).

Gerçek dev ortamı ister: Next :3000 + backend :8081. Sistem python (playwright):
    PYTHONPATH=. python scripts/live_student_pool_add_linked.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Topic, Track,
    User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode  # noqa: E402
from app.services.security import hash_password  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lsl_{secrets.token_hex(3)}"
PWD = "Ogrenci!234567xy"
today = date.today()
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
        print(f"  [FAIL] {label}  ({str(detail)[:200]})")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Rehber",
                     role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Ekleme Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                  program_mode="havuz")
        db.add(st)
        db.flush()
        ids["users"] += [coach.id, st.id]
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        ids["subjects"].append(tyt.id)
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=tyt.id, name="Köklü Sayılar", order=2, teacher_id=coach.id)
        db.add_all([t1, t2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal TYT Mat", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        s1 = BookSection(book_id=b.id, label="Köklü Sayılar Testleri", test_count=10, order=1, topic_id=t2.id)
        db.add(s1)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=3))
        pool_mode.open_period(db, student=st, coach=coach, opened_on=today, expected_next_on=today + timedelta(days=7))
        db.commit()
        return {"st": st.id, "email": st.email, "tyt": tyt.id, "t1": t1.id, "b": b.id, "s1": s1.id,
                "subj": tyt.name}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1", "::1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def items():
    with SessionLocal() as db:
        return [(it.topic_id, it.book_id, it.book_section_id, it.unit, it.quantity, it.approval, it.label)
                for it in db.query(PoolItem).filter(PoolItem.student_id == ids["st"]).order_by(PoolItem.id).all()]


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids.update(seed())
    print(f"\n=== Öğrenci kalem ekleme — eşleşmeli ({PFX}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            page = br.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{BASE}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            def open_dialog():
                page.goto(f"{BASE}/student/pool", wait_until="networkidle")
                page.wait_for_timeout(1200)
                later = page.query_selector('button:has-text("Daha sonra")')
                if later:
                    later.click()
                    page.wait_for_timeout(500)
                page.click('button:has-text("Kalem ekle")')
                page.wait_for_selector('[role="dialog"]', timeout=8000)
                dlg = page.locator('[role="dialog"]')
                dlg.locator(f'button:has-text("{ids["subj"]}")').first.click()
                page.wait_for_timeout(800)
                return dlg

            # --- A) müfredat konusundan
            dlg = open_dialog()
            txt = dlg.inner_text()
            check("A1 ders seçilince 'Kitabımdan (1)' ve 'Müfredat konusundan' seçenekleri",
                  "Kitabımdan (1)" in txt and "Müfredat konusundan" in txt, txt)
            dlg.locator('[role="tab"]:has-text("Müfredat konusundan")').click()
            page.wait_for_timeout(1200)
            check("A2 konu listesi geldi", dlg.locator('[data-topic-id]').count() >= 2, dlg.inner_text())
            dlg.locator(f'[data-topic-id="{ids["t1"]}"]').click()
            page.wait_for_timeout(400)
            dlg.locator('button[aria-pressed]:has-text("3")').first.click()
            dlg.locator('input[aria-label="Not"]').fill("Palme yaprak")
            prev = dlg.locator('[data-section="student:pool:add-preview"]').inner_text()
            check("A3 önizleme 'müfredata bağlı · 3 test'", "müfredata bağlı" in prev and "3 test" in prev, prev)
            page.screenshot(path=os.path.join(ROOT, ".shots", "student_pool_add_topic.png"))
            dlg.locator('[data-testid="student-pool-add-submit"]').click()
            page.wait_for_timeout(2500)
            it = items()
            check("A4 kalem konuya bağlı + onay bekliyor + not",
                  len(it) == 1 and it[0][0] == ids["t1"] and it[0][3] == "test" and it[0][4] == 3
                  and it[0][5] == "bekliyor" and it[0][6] == "Palme yaprak", it)

            # --- B) kitabımdan
            dlg = open_dialog()
            dlg.locator('[role="tab"]:has-text("Kitabımdan")').click()
            page.wait_for_timeout(1500)
            sec = dlg.locator(f'[data-section-id="{ids["s1"]}"]')
            check("B1 kitabın bölümü kalanıyla listelenir", sec.count() == 1 and "7 kaldı" in sec.inner_text(),
                  dlg.inner_text())
            sec.click()
            page.wait_for_timeout(400)
            dlg.locator('button[aria-pressed]:has-text("2")').first.click()
            prev = dlg.locator('[data-section="student:pool:add-preview"]').inner_text()
            check("B2 önizleme 'kitaba bağlı · 2 test'", "kitaba bağlı" in prev and "2 test" in prev, prev)
            dlg.locator('[data-testid="student-pool-add-submit"]').click()
            page.wait_for_timeout(2500)
            it = items()
            check("B3 kalem kitap + bölüm bağlı (konu bölümden)",
                  len(it) == 2 and it[1][1] == ids["b"] and it[1][2] == ids["s1"] and it[1][4] == 2, it)

            # --- C) konusuz: test birimi yok, sayfa/etkinlik
            dlg = open_dialog()
            dlg.locator('[role="tab"]:has-text("Müfredat konusundan")').click()
            page.wait_for_timeout(1000)
            dlg.locator('button:has-text("Konusuz")').click()
            page.wait_for_timeout(400)
            radios = [r.inner_text() for r in dlg.locator('[role="radiogroup"][aria-label="Birim"] [role="radio"]').all()]
            check("C1 konusuz kalemde birim yalnız sayfa/etkinlik (test yok)", radios == ["sayfa", "etkinlik"], radios)
            submit = dlg.locator('[data-testid="student-pool-add-submit"]')
            check("C2 'ne çalışacaksın' boşken ekle kapalı", submit.is_disabled())

            # --- koyu tema + dar ekran görsel
            page.emulate_media(color_scheme="dark")
            page.set_viewport_size({"width": 390, "height": 844})
            dlg = open_dialog()
            dlg.locator('[role="tab"]:has-text("Müfredat konusundan")').click()
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(ROOT, ".shots", "student_pool_add_mobile_dark.png"))
            over = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            check("D1 390px'te yatay taşma yok", not over)
            br.close()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
