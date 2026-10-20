"""Canlı — deneme sonuç penceresi (D2, 2026-10-20): öğrenci Bugün + koç hafta.

  1 Öğrenci Bugün: deneme görevi 2 satır "çözülmedi"; tik → sonuç penceresi (2 satır) açılır
  2 1. satır 4D 1Y → boş otomatik (1) + net 3,75 görünür; soru 7 yazınca boş 2
  3 Aşan giriş (soru 7, 6D 2Y) → uyarı + Kaydet kapalı
  4 Kaydet: 1. satır sonuçlu, 2. satır "sonuç bekliyor" (DB + kart çipleri)
  5 Koç hafta: rozet "sonuç bekliyor" → pencere (koç) → 3D 2Y kaydet → DB net
  6 Pencere taşma/kırpma yok · koyu tema + 390px ekran görüntüsü · konsol temiz
Ön koşul: backend :8081 + Next :3000.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject, Task, TaskBookItem, Track, User,
    UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"ldr_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed():
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Deneme Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Deneme Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL)
        db.add(st); db.flush()
        bio = Subject(name="TYT Biyoloji", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(bio); db.flush()
        b = Book(teacher_id=coach.id, subject_id=bio.id, name=f"{PFX} Bio Branş", type=BookType.BRANS_DENEMESI)
        db.add(b); db.flush()
        db.add_all([BookSection(book_id=b.id, label=f"DENEME {i}", test_count=1, order=i) for i in range(1, 5)])
        db.add(StudentBook(student_id=st.id, book_id=b.id))
        db.commit()
        d = {"coach": coach.id, "st": st.id, "book": b.id}
    get_login_limiter().reset()
    c = TestClient(app)
    assert c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD}).status_code == 200
    r = c.post(f"/api/v2/teacher/students/{d['st']}/deneme-tasks",
               json={"date": date.today().isoformat(), "kind": "brans", "book_id": d["book"], "count": 2,
                     "is_draft": False})
    assert r.status_code == 200, r.text
    d["task"] = r.json()["data"]["id"]
    d["items"] = [x["id"] for x in r.json()["data"]["items"]]
    get_login_limiter().reset()
    return d


def cleanup(d):
    with SessionLocal() as db:
        u = [d["coach"], d["st"]]
        from app.models import ExamResult as _ER  # D3 köprü kayıtları
        db.execute(sa_delete(_ER).where(_ER.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == d["book"]))
        db.execute(sa_delete(Book).where(Book.id == d["book"]))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == d["coach"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def items(d):
    with SessionLocal() as db:
        return {i.id: (i.completed_count, i.correct_count, i.wrong_count, i.blank_count, i.question_count)
                for i in db.query(TaskBookItem).filter(TaskBookItem.task_id == d["task"]).all()}


def login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)


def dismiss(page):
    for t in ("Daha sonra", "Kapat"):
        el = page.query_selector(f'button:has-text("{t}")')
        if el and el.is_visible():
            el.click()
            page.wait_for_timeout(500)


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOTS, exist_ok=True)
    d = seed()
    i1, i2 = d["items"]
    print(f"\n=== canlı: deneme sonuç penceresi — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark")
            page = ctx.new_page()
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            login(page, f"{PFX}_s@test.invalid")
            page.goto(f"{WEB}/student/day", wait_until="networkidle")
            page.wait_for_timeout(2500)
            dismiss(page)
            card = page.locator("article").filter(has_text="Bio Branş").first
            check("1a deneme kartında 2 satır 'çözülmedi'", card.locator("text=çözülmedi").count() == 2,
                  card.inner_text()[:300])
            card.locator('button').first.click()  # tik
            page.wait_for_timeout(1200)
            dlg = page.locator('[role="dialog"]')
            check("1b tik → sonuç penceresi, 2 satır", dlg.count() == 1 and dlg.locator('[data-testid="deneme-row"]').count() == 2)

            r1 = dlg.locator('[data-testid="deneme-row"]').nth(0)
            r1.locator('input[aria-label="Doğru"]').fill("4")
            r1.locator('input[aria-label="Yanlış"]').fill("1")
            page.wait_for_timeout(300)
            check("2a boş otomatik 1 (yer tutucu)", r1.locator('input[aria-label="Boş"]').get_attribute("placeholder") == "1")
            check("2b net 3,75", "3,75" in r1.inner_text(), r1.inner_text())
            r1.locator('input[aria-label="Soru"]').fill("7")
            page.wait_for_timeout(200)
            check("2c soru 7 → boş 2", r1.locator('input[aria-label="Boş"]').get_attribute("placeholder") == "2")
            r1.locator('input[aria-label="Doğru"]').fill("6")
            r1.locator('input[aria-label="Yanlış"]').fill("2")
            page.wait_for_timeout(200)
            save_btn = dlg.locator('button:has-text("Kaydet")').last
            check("3a aşan girişte uyarı", "soru sayısından fazla" in r1.inner_text())
            check("3b Kaydet kapalı", save_btn.is_disabled())
            r1.locator('input[aria-label="Doğru"]').fill("4")
            r1.locator('input[aria-label="Yanlış"]').fill("1")
            r1.locator('input[aria-label="Süre (dk)"]').fill("12")
            page.wait_for_timeout(200)
            ov = page.evaluate("() => { const d = document.querySelector('[role=dialog]'); return d.scrollWidth - d.clientWidth; }")
            check("6a pencere yatay taşma yok", ov <= 1, str(ov))
            dlg.screenshot(path=os.path.join(SHOTS, "deneme_results_dark.png"))
            save_btn.click()
            page.wait_for_timeout(2500)
            it = items(d)
            check("4a DB: 1. satır 4D 1Y 2B, soru 7", it[i1] == (1, 4, 1, 2, 7), str(it[i1]))
            check("4b DB: 2. satır çözüldü, sonuç yok", it[i2][0] == 1 and it[i2][1] is None, str(it[i2]))
            card = page.locator("article").filter(has_text="Bio Branş").first
            txt = card.inner_text()
            check("4c kartta 'sonuç bekliyor' + net", "sonuç bekliyor" in txt and "net 3,75" in txt, txt[:300])
            check("6c öğrenci konsolu temiz", not errs, " | ".join(errs)[:300])

            # 390px
            m = ctx.new_page()
            m.set_viewport_size({"width": 390, "height": 860})
            m.goto(f"{WEB}/student/day", wait_until="networkidle")
            m.wait_for_timeout(2500)
            dismiss(m)
            m.locator("article").filter(has_text="Bio Branş").first.locator('button:has-text("Sonuçları düzenle")').click()
            m.wait_for_timeout(1000)
            ov2 = m.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("6b 390px yatay kaydırma yok", ov2 <= 1, str(ov2))
            m.screenshot(path=os.path.join(SHOTS, "deneme_results_mobile.png"))
            m.close()
            ctx.close()

            # koç
            ctx2 = b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark")
            cp = ctx2.new_page()
            login(cp, f"{PFX}_t@test.invalid")
            cp.goto(f"{WEB}/teacher/students/{d['st']}/week", wait_until="networkidle")
            cp.wait_for_timeout(3000)
            dismiss(cp)
            badge = cp.locator('button[title="Deneme sonucunu gir / düzelt"]:has-text("sonuç bekliyor")')
            check("5a koç rozeti 'sonuç bekliyor'", badge.count() >= 1)
            if badge.count():
                badge.first.click()
                cp.wait_for_timeout(1000)
                cd = cp.locator('[role="dialog"]')
                cd.locator('input[aria-label="Doğru"]').fill("3")
                cd.locator('input[aria-label="Yanlış"]').fill("2")
                cd.locator('button:has-text("Kaydet")').last.click()
                cp.wait_for_timeout(2500)
                it = items(d)
                check("5b koç kaydetti: 2. satır 3D 2Y 1B", it[i2][1:4] == (3, 2, 1), str(it[i2]))
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
