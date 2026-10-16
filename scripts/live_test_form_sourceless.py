"""Canlı — ayrıntılı form "Test": kitabı olmayan öğrenciye kaynaksız (müfredata bağlı) test (2026-10-16).

  1 kitabı olmayan öğrencide Test → ders listesi DOLU (eskiden boştu)
  2 ders seçince kitap kutusu "Kaynaksız" seçili, konu listesi dolu
  3 konu + 2 → kayıt: kitapsız, topic_id dolu, planned 2, type test
  4 20 yazınca "test sayısıdır" uyarısı
Ön koşul: backend :8081 + Next :3000.
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskBookItem, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"ltfs_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Form Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Kitapsız",
                 role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                 grade_level=8)
        db.add(s)
        db.commit()
        return {"coach": coach.id, "s": s.id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["s"], d["coach"]]
        tids = [t.id for t in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = seed()
    print(f"\n=== canlı: ayrıntılı form kaynaksız test — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 950}, color_scheme="dark")
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{PFX}_t@test.invalid")
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{d['s']}/week", wait_until="networkidle")
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(1000)
            for sel in ('text="Yeni görev ekle"', 'text="Görev ekle"'):
                el = page.query_selector(sel)
                if el:
                    el.click()
                    page.wait_for_timeout(1000)
                    break
            page.click('text="Ayrıntılı form"')
            page.wait_for_timeout(1200)
            selects = page.locator("form select")
            subj = selects.nth(0)
            opts = subj.locator("option").all_inner_texts()
            check("1 ders listesi dolu (kitap yokken)", len(opts) > 3, str(opts[:6]))
            target = next((o for o in opts if "İnkılap" in o), opts[1] if len(opts) > 1 else "")
            subj.select_option(label=target)
            page.wait_for_timeout(2500)
            book = selects.nth(1)
            check("2 kitap kutusu 'Kaynaksız' seçili", "Kaynaksız" in (book.locator("option:checked").inner_text()),
                  book.locator("option:checked").inner_text())
            topic = selects.nth(2)
            topts = topic.locator("option").all_inner_texts()
            check("2b müfredat konusu listesi dolu", len(topts) > 2, str(topts[:4]))
            topic.select_option(index=1)
            qty = page.locator('form input[aria-label="Test sayısı"]')
            qty.fill("20")
            page.wait_for_timeout(300)
            check("4 20 → 'test sayısıdır' uyarısı", page.locator("text=test sayısıdır").count() > 0)
            page.screenshot(path=".shots/test_form_sourceless.png")
            qty.fill("2")
            page.locator('form button[type="submit"]').last.click()
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                t = db.query(Task).filter(Task.student_id == d["s"]).order_by(Task.id.desc()).first()
                it = t.book_items[0] if t and t.book_items else None
                ok = (t is not None and str(t.type.value if hasattr(t.type, "value") else t.type) == "test"
                      and it is not None and it.book_id is None and it.topic_id is not None
                      and it.planned_count == 2)
            check("3 kayıt: test, kitapsız, topic_id dolu, 2 test", ok,
                  f"{t and t.type} {it and (it.book_id, it.topic_id, it.planned_count)}")
            check("3b başlık konu adını taşır ('Görev' değil)",
                  t is not None and t.title != "Görev" and t.title.endswith("— 2 test"), str(t and t.title))
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
