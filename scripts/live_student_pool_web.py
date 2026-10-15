"""Havuzum — WEB (öğrenci /student/pool, Next :3000 + backend :8081), Adım 3 (2026-10-12).

Önkoşul: backend :8081 (CORS'ta http://localhost:8095) + Next :3000
(EXPO_PUBLIC_API_BASE=http://localhost:8081). Sistem python (playwright):
    python scripts/live_student_pool_web.py

Akış: havuz öğrencisi → Bugün'de "Haftanın havuzu" kartı → Havuzum: özet + tempo
cümlesi · öneri (bugün dershanede Biyoloji) · "Kaba al" → sayı sayfası → 2 → kapta ·
Bugün ekranında kap görevi · "Kalem ekle" → onay bekliyor · projeksiyon · ekran görüntüsü.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, ClassGroup, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, SuspiciousIp, Task, TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.services import pool_mode  # noqa: E402
from app.services.security import hash_password  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lwp_{secrets.token_hex(3)}"
PWD = "MobilHavuz!2345"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today = date.today()
passed = 0
failed: list[str] = []
ids: dict = {}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Rehber",
                     role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Web Havuz",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                  program_mode="havuz", class_group="12-M", must_change_password=False)
        db.add(st)
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        bio = Subject(name=f"{PFX} TYT Biyoloji", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([tyt, bio])
        db.flush()
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=bio.id, name="Hücre", order=1, teacher_id=coach.id)
        db.add_all([t1, t2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        s1 = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=10, order=1, topic_id=t1.id)
        db.add(s1)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=0))
        db.flush()
        p = pool_mode.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=1),
                                  expected_next_on=today + timedelta(days=6))
        pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=4, unit="test", book=b, section=s1)
        pool_mode.add_item(db, period=p, student=st, subject=bio, quantity=3, unit="test", topic=t2)
        pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=None, unit="etkinlik", label="Üslü videosu")
        cg = pool_mode.get_or_create_class_group(db, coach=coach, name="12-M")
        pool_mode.set_lesson_days(db, cg, {today.weekday(): [bio.id]})
        db.commit()
        return {"coach": coach.id, "st": st.id, "subjects": [tyt.id, bio.id], "book": b.id,
                "email": f"{PFX}_s@test.invalid", "bio": bio.name}


def cleanup():
    with SessionLocal() as db:
        u = [ids["coach"], ids["st"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
        db.execute(sa_delete(Book).where(Book.id == ids["book"]))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(ClassGroup).where(ClassGroup.scope_key == f"coach:{ids['coach']}"))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids.update(seed())
    print(f"\n=== Havuzum — öğrenci web canlı ({PFX}, öğrenci #{ids['st']}) ===\n")
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

            page.goto(f"{BASE}/student/day", wait_until="networkidle")
            page.wait_for_timeout(1500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:  # Rehber karşılama penceresi (yeni hesap)
                later.click()
                page.wait_for_timeout(600)
            page.wait_for_selector('[data-section="student:pool-banner"]', timeout=15000)
            ban = page.query_selector('[data-section="student:pool-banner"]').inner_text()
            check("1a Bugün sayfasında havuz kartı (%0 · seansa 6 gün · kabın boş)", "%0 bitti" in ban and "seansa 6 gün" in ban and "kabın boş" in ban, ban)
            nav_pool = page.query_selector('nav[aria-label="Öğrenci paneli"] a[data-nav-pool="1"]')
            check("1b havuz öğrencisinde 'Havuzum' ana menüde (Daha fazla'da gizli değil), Bugün'den hemen sonra",
                  nav_pool is not None and nav_pool.is_visible()
                  and page.eval_on_selector_all('nav[aria-label="Öğrenci paneli"] > a',
                                               "els => els.map(e => e.getAttribute('href'))")[:2] == ["/student/day", "/student/pool"])
            ban_box = page.query_selector('[data-section="student:pool-banner"]').bounding_box()
            date_box = page.query_selector('input[type="date"]').bounding_box()
            check("1c havuz kartı sayfanın en üstünde (tarih gezgininden önce) + 'Havuzu aç'",
                  ban_box["y"] < date_box["y"] and "Havuzu aç" in ban, f"{ban_box} {date_box}")
            check("1d kap boşken 'Bugünün kabı boş' uyarısı", "Bugünün kabı boş" in ban, ban)
            page.screenshot(path=os.path.join(ROOT, ".shots/student_day_pool_banner.png"))

            page.click('[data-section="student:pool-banner"]')
            page.wait_for_selector('[data-section="student:pool:summary"]', timeout=15000)
            summ = page.query_selector('[data-section="student:pool:summary"]').inner_text()
            check("2a özet 0/8 birim + tempo cümlesi", "/8 birim" in summ and "günde" in summ.lower(), summ[:200])
            body = page.inner_text("body")
            check("2b bugün dershanede Biyoloji + öneri kutusu", ids["bio"] in body and page.query_selector('[data-section="student:pool:suggest"]') is not None)
            check("2c 'Kaba al' düğmeleri (liste + öneri)", page.locator('button:has-text("Kaba al")').count() >= 3, str(page.locator('button:has-text("Kaba al")').count()))
            check("2d kalem adı kırpılmıyor", page.locator('[data-section="student:pool:list"] .truncate').count() == 0)

            # kitaplı kalem (4 test) → sayı penceresi → 2
            row = page.locator('[data-section="student:pool:list"] li', has_text="Orijinal — Üslü Sayılar").first
            row.locator('button:has-text("Kaba al")').click()
            page.wait_for_selector('text=Bugün kaç tane?', timeout=8000)
            check("3a 'Bugün kaç tane?' penceresi", True)
            page.locator('[role="dialog"] button', has_text="2").first.click()
            page.wait_for_timeout(3000)
            cup = page.query_selector('[data-section="student:pool:cup"]').inner_text()
            check("3b kapta: 'Orijinal — Üslü Sayılar: 2 test'", "Orijinal — Üslü Sayılar: 2 test" in cup, cup[:300])
            lst = page.query_selector('[data-section="student:pool:list"]').inner_text()
            check("3c listede 'kapta' etiketi", "kapta" in lst)
            with SessionLocal() as db:
                sp = db.query(SectionProgress).join(StudentBook).filter(StudentBook.student_id == ids["st"]).one()
                t = db.query(Task).filter(Task.student_id == ids["st"], Task.date == today).all()
                check("3d bugüne görev yazıldı, rezerv 0", len(t) == 1 and sp.reserved_count == 0)
            page.screenshot(path=os.path.join(ROOT, ".shots/student_pool_web.png"), full_page=True)

            # Bugün sayfasında kap görevi
            page.click('a:has-text("Bugün sayfasında işaretle")')
            page.wait_for_timeout(4000)
            body = page.inner_text("body")
            check("4a Bugün sayfasında kap görevi", "Üslü Sayılar" in body and "2 test" in body, " | ".join(body[:500].splitlines()))
            ban = page.query_selector('[data-section="student:pool-banner"]').inner_text()
            check("4b kart: kabında 1 kalem · 0 bitti, 'kabı boş' uyarısı YOK", "kabında 1 kalem" in ban and "kabı boş" not in ban, ban)

            # geri al → kap boş
            page.goto(f"{BASE}/student/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="student:pool:cup"]', timeout=15000)
            page.click('[data-section="student:pool:cup"] button[title="Havuza geri al"]')
            page.wait_for_timeout(3000)
            cup = page.query_selector('[data-section="student:pool:cup"]').inner_text()
            check("5a geri al → kap boş", "Kabın boş" in cup, cup[:200])

            # Kalem ekle (öğrenci) → onay bekliyor, yüzde değişmez
            page.click('button:has-text("Kalem ekle")')
            page.wait_for_selector('text=Havuza kalem ekle', timeout=8000)
            page.locator('[role="dialog"] button', has_text=ids["bio"]).first.click()
            page.fill('input[aria-label="Ne çalışacaksın"]', "Hücre bölümü")
            page.fill('input[aria-label="Miktar"]', "2")
            page.click('[role="dialog"] button:has-text("Havuza ekle")')
            page.wait_for_timeout(3000)
            lst = page.query_selector('[data-section="student:pool:list"]').inner_text()
            check("6a öğrenci kalemi listede 'onay bekliyor'", "Hücre bölümü" in lst and "onay bekliyor" in lst, lst[:500])
            summ = page.query_selector('[data-section="student:pool:summary"]').inner_text()
            check("6b yüzde değişmedi (0/8 birim)", "/8 birim" in summ)

            page.click('button:has-text("Haftaya nasıl dağılır?")')
            page.wait_for_timeout(600)
            check("7a projeksiyon kutuları (~N birim)", "~" in page.inner_text("body"))

            # koyu tema kontrast (özet kartı beyaz-üstü-cyan + liste)
            page.emulate_media(color_scheme="dark")
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(500)
            from scripts.lib_live_contrast import measure  # noqa: E402
            m = measure(page, '[data-section="student:pool"]', min_ratio=3.0)
            check("8a koyu tema: okunmayan metin yok", not m["bad"], str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/student_pool_web_dark.png"), full_page=True)
            br.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
