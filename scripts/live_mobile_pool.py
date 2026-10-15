"""Havuzum — MOBİL (Expo web önizlemesi 390px + gerçek backend), Adım 3 (2026-10-12).

Önkoşul: backend :8081 (CORS'ta http://localhost:8095) + Expo web :8095
(EXPO_PUBLIC_API_BASE=http://localhost:8081). Sistem python (playwright):
    python scripts/live_mobile_pool.py

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

BASE = "http://localhost:8095"
PFX = f"lmp_{secrets.token_hex(3)}"
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
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Mobil Havuz",
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
    print(f"\n=== Havuzum — mobil canlı ({PFX}, öğrenci #{ids['st']}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            inputs = page.locator("input")
            inputs.nth(0).fill(ids["email"])
            inputs.nth(1).fill(PWD)
            page.get_by_text("Giriş yap", exact=True).last.click()
            page.wait_for_timeout(8000)

            body = page.inner_text("body")
            check("1a Bugün ekranında 'Haftanın havuzu' kartı", "Haftanın havuzu" in body, page.url)
            check("1b kart: %0 bitti · seansa 6 gün · kabında 0 açık", "%0 bitti" in body and "seansa 6 gün" in body, body[:400])
            page.get_by_text("Haftanın havuzu").first.click(force=True)
            page.wait_for_timeout(4000)
            body = page.inner_text("body")
            check("2a Havuzum ekranı: özet 0/8 birim + tempo cümlesi", "Havuzum" in body and "/8 birim" in body and "günde" in body.lower(), body[:400])
            check("2b bugün dershanede Biyoloji + öneri", ids["bio"] in body and "Bugün için öneri" in body)
            check("2c 'Kaba al' düğmeleri", page.get_by_text("Kaba al").count() >= 3, str(page.get_by_text("Kaba al").count()))

            # kitaplı kalem (4 test) → sayı sayfası → 2
            row = page.get_by_text("Orijinal — Üslü Sayılar").first
            btn = row.locator("xpath=ancestor::div[contains(@class,'flex-row')][1]").get_by_text("Kaba al").first
            btn.click(force=True)
            page.wait_for_timeout(1500)
            check("3a 'Bugün kaç tane?' sayfası", "Bugün kaç tane?" in page.inner_text("body"))
            page.get_by_text("2", exact=True).last.click(force=True)
            page.wait_for_timeout(4000)
            body = page.inner_text("body")
            check("3b kalem kapta (Bugünün kabı dolu + 'kapta' etiketi)", "kapta" in body and "Orijinal — Üslü Sayılar: 2 test" in body, body[:600])
            with SessionLocal() as db:
                sp = db.query(SectionProgress).join(StudentBook).filter(StudentBook.student_id == ids["st"]).one()
                t = db.query(Task).filter(Task.student_id == ids["st"], Task.date == today).all()
                check("3c bugüne görev yazıldı, rezerv 0", len(t) == 1 and sp.reserved_count == 0)
            page.screenshot(path=os.path.join(ROOT, ".shots/mobile_pool.png"), full_page=True)

            # Bugün ekranında kap görevi
            page.get_by_text("Bugün ekranında işaretle").first.click(force=True)
            body = ""
            for _ in range(10):
                page.wait_for_timeout(1500)
                body = page.inner_text("body")
                if "Üslü Sayılar" in body and "BUGÜN" in body and "0/1 görev" in body:
                    break
            check("4a Bugün ekranında kap görevi görünür (0/1 görev · Üslü Sayılar)",
                  "Üslü Sayılar" in body and "BUGÜN" in body and "0/1 görev" in body,
                  " | ".join(body[:400].splitlines()))

            # Havuzum → Kalem ekle (doğrudan adres — yığın geçişi tıklamasız)
            page.goto(f"{BASE}/student-pool", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            page.get_by_text("Kalem ekle").first.click(force=True)
            page.wait_for_timeout(1500)
            check("5a 'Havuza kalem ekle' sayfası", "Havuza kalem ekle" in page.inner_text("body"))
            page.get_by_text(ids["bio"]).last.click()
            page.get_by_placeholder("örn. Palme sayfa 45'e kadar").fill("Hücre bölümü")
            page.get_by_placeholder("sayı").fill("2")
            page.get_by_text("Havuza ekle").click(force=True)
            page.wait_for_timeout(4000)
            body = page.inner_text("body")
            check("5b öğrenci kalemi listede 'onay bekliyor'", "Hücre bölümü" in body and "onay bekliyor" in body, body[:600])
            check("5c yüzde değişmedi (0/8 birim)", "/8 birim" in body)

            page.get_by_text("Haftaya nasıl dağılır?").click(force=True)
            page.wait_for_timeout(800)
            check("6a projeksiyon kutuları", "~" in page.inner_text("body") and "birim" in page.inner_text("body"))
            page.screenshot(path=os.path.join(ROOT, ".shots/mobile_pool_full.png"), full_page=True)
            br.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
