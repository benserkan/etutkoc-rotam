"""Canlı — MOBİL koç görev ekleme (Expo web :8095 + backend :8081, 2026-10-16).

  1 "milli desten" arama → Millî Bir Destan
  2 konu → "Kaynaksız" → adet "test" etiketli; 20 yazınca uyarı
  3 kayıt: kitapsız + topic_id dolu + 2 test
  4 kitabı yok → "Kitaptan test" boş durumunda kaynaksız yol → ders → konu → kayıt
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
from app.models import Task, TaskBookItem, Topic, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402

BASE = "http://localhost:8095"
PFX = f"lmat_{secrets.token_hex(3)}"
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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Mobil Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Mobil Öğrenci",
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


def tasks(d):
    with SessionLocal() as db:
        out = []
        for t in db.query(Task).filter(Task.student_id == d["s"]).order_by(Task.id).all():
            for it in t.book_items:
                tp = db.get(Topic, it.topic_id) if it.topic_id else None
                out.append((str(getattr(t.type, "value", t.type)), it.book_id, tp.name if tp else None,
                            it.planned_count, t.title))
        return out


def open_sheet(page, d):
    page.goto(f"{BASE}/teacher-student?id={d['s']}", wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    page.get_by_text("Program", exact=True).first.click(force=True)
    page.wait_for_timeout(4000)
    page.get_by_text("Görev ekle", exact=True).first.click(force=True)
    page.wait_for_timeout(2500)


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = seed()
    print(f"\n=== mobil görev ekleme — {PFX} ===\n")
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            page = br.new_context(viewport={"width": 390, "height": 844}).new_page()
            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            inputs = page.locator("input")
            inputs.nth(0).fill(f"{PFX}_t@test.invalid")
            inputs.nth(1).fill(PWD)
            page.get_by_text("Giriş yap", exact=True).last.click()
            page.wait_for_timeout(8000)

            open_sheet(page, d)
            box = page.locator('input[aria-label="Görev ara"]')
            box.fill("milli desten")
            page.wait_for_timeout(3000)
            hit = page.get_by_text("Millî Bir Destan", exact=False)
            check("1 'milli desten' → Millî Bir Destan", hit.count() > 0)
            page.screenshot(path=".shots/mobile_add_task_search.png")
            hit.first.click(force=True)
            page.wait_for_timeout(1200)
            page.get_by_text("Kaynaksız (müfredat konusuna bağlı)", exact=True).first.click(force=True)
            page.wait_for_timeout(1000)
            qty = page.locator('input[aria-label="Test sayısı"]')
            check("2 adet kutusu + 'test' etiketi", qty.count() > 0 and page.get_by_text("test", exact=True).count() > 0)
            qty.fill("20")
            page.wait_for_timeout(500)
            check("2b 20 → 'test sayısıdır' uyarısı", page.get_by_text("test sayısıdır", exact=False).count() > 0)
            page.screenshot(path=".shots/mobile_add_task_count.png")
            qty.fill("2")
            page.wait_for_timeout(400)
            page.get_by_text("Ekle · 2 test", exact=True).first.click(force=True)
            page.wait_for_timeout(3500)
            rows = tasks(d)
            check("3 kayıt: test, kitapsız, Millî Bir Destan, 2",
                  any(r[0] == "test" and r[1] is None and r[2] and r[2].startswith("Millî Bir Destan") and r[3] == 2
                      for r in rows), str(rows))

            open_sheet(page, d)
            page.get_by_text("Kitaptan test", exact=True).first.click(force=True)
            page.wait_for_timeout(2500)
            check("4 kitap yok → kaynaksız yol önerilir",
                  page.get_by_text("Kitap olmadan da test verebilirsin", exact=False).count() > 0)
            page.get_by_text("Dersin konusundan test (kaynaksız)", exact=True).last.click(force=True)
            page.wait_for_timeout(1500)
            subj = page.get_by_text("Matematik", exact=True)
            check("4b ders listesi dolu", subj.count() > 0)
            subj.first.click(force=True)
            page.wait_for_timeout(3500)
            page.screenshot(path=".shots/mobile_add_task_subject_topics.png")
            n_all = page.locator('div[tabindex="0"]').filter(has_text="sınıf").count()
            page.locator('input[aria-label="Konu ara"]').fill("olasi")
            page.wait_for_timeout(800)
            n_f = page.locator('div[tabindex="0"]').filter(has_text="sınıf").count()
            check("4b2 konu araması listeyi daraltır ('olasi' → olasılık)",
                  0 < n_f < n_all and page.get_by_text("Olasılı", exact=False).count() > 0, f"{n_all}->{n_f}")
            first_topic = page.locator('div[tabindex="0"]').filter(has_text="sınıf").first
            first_topic.click(force=True)
            page.wait_for_timeout(1200)
            page.locator('input[aria-label="Test sayısı"]').fill("3")
            page.wait_for_timeout(400)
            page.get_by_text("Ekle · 3 test", exact=True).first.click(force=True)
            page.wait_for_timeout(3500)
            rows = tasks(d)
            check("4c kayıt: ders listesinden kaynaksız 3 test",
                  any(r[0] == "test" and r[1] is None and r[2] and r[3] == 3 for r in rows), str(rows))
            check("4d başlıklar konu adını taşır ('Görev' değil)",
                  rows and all(r[4] != "Görev" and r[4].startswith(r[2]) for r in rows), str(rows))
            br.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
