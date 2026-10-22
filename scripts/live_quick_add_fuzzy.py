"""Canlı (gerçek tarayıcı) — görev kutusu sezgisel arama + yeni seçim düzeni (2026-10-16).

  1 "milli desten" → Millî Bir Destan (yazım hatası + araya giren sözcük)
  2 konu satırına tıklama (kitabı yok) → kaynaksız seçilir, seçim KUTUNUN İÇİNDE çip
  3 adet kutusunun yanında "test", düğme "Ekle · N test"
  4 30 yazınca "test sayısıdır" uyarısı
  5 kayıt → gün kartında ders adı (T.C. İnkılap…), "Diğer" yok; ders listesinde TYT yok (10. sınıf)
  6 koyu tema + 390px
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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskBookItem, Topic, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lqaf_{secrets.token_hex(3)}"
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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Arama Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        s8 = User(email=f"{PFX}_s8@test.invalid", password_hash=hash_password(PWD), full_name="Sekizinci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=8)
        db.add(s8)
        db.commit()
        return {"coach": coach.id, "s8": s8.id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["s8"], d["coach"]]
        tids = [t.id for t in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def open_box(page, sid):
    page.goto(f"{WEB}/teacher/students/{sid}/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(1200)
    for sel in ('text="Yeni görev ekle"', 'text="Görev ekle"'):
        el = page.query_selector(sel)
        if el:
            el.click()
            page.wait_for_timeout(1000)
            break


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = seed()
    print(f"\n=== canlı: görev kutusu sezgisel arama — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 950})
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{PFX}_t@test.invalid")
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            open_box(page, d["s8"])

            box = page.locator('input[aria-label="Görev ara"]')
            box.click()
            box.fill("milli desten")
            page.wait_for_timeout(1800)
            first = page.locator('[data-testid="quick-add-results"] button').first
            txt = first.inner_text() if first.count() else ""
            check("1 'milli desten' → ilk sonuç Millî Bir Destan", "Millî Bir Destan" in txt, txt[:80])
            check("1b sonuçta ders + sınıf + tema görünür", "İnkılap" in txt and "8. sınıf" in txt, txt[:160])
            page.screenshot(path=".shots/quick_add_fuzzy_results.png")
            first.click()
            page.wait_for_timeout(600)
            chip = page.locator('[data-testid="quick-add-picked"]')
            ctext = chip.inner_text() if chip.count() else ""
            check("2 seçim kutunun içinde çip (konu · ders · kaynaksız)",
                  "Millî Bir Destan" in ctext and "kaynaksız" in ctext, ctext[:160])
            # 2026-10-22 yeni kart: miktar çipleri (öğrenilmiş değer seçili) + "başka" ile elle sayı
            on = page.locator('[role="group"][aria-label="Miktar"] button[aria-pressed="true"]')
            check("3 miktar ön-seçili + birim 'test' yazılı",
                  on.count() == 1 and "test" in page.locator('[role="group"][aria-label="Miktar"]').inner_text(),
                  on.inner_text() if on.count() else "")
            btn = page.locator('form[aria-label="Görev ekleme kutusu"] button[type="submit"]')
            check("3b düğme 'Ekle · N test'", "test" in btn.inner_text(), btn.inner_text())
            page.locator('[role="group"][aria-label="Miktar"] button:has-text("başka")').click()
            qty = page.locator('input[aria-label="Test sayısı"]')
            qty.fill("30")
            page.wait_for_timeout(300)
            check("4 30 yazınca 'test sayısıdır' uyarısı", page.locator("text=test sayısıdır").count() > 0)
            page.screenshot(path=".shots/quick_add_fuzzy_picked.png")
            qty.fill("2")
            btn.click()
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                t = db.query(Task).filter(Task.student_id == d["s8"]).order_by(Task.id.desc()).first()
                it = t.book_items[0] if t else None
                tp = db.get(Topic, it.topic_id) if it and it.topic_id else None
            check("5 kayıt: kaynaksız konu kalemi (Millî Bir Destan, 2 test)",
                  tp is not None and tp.name.startswith("Millî Bir Destan") and it.planned_count == 2)
            page.goto(f"{WEB}/teacher/students/{d['s8']}/week", wait_until="networkidle")
            page.wait_for_timeout(2500)
            card = page.locator("#day-editor").first
            ctxt = card.inner_text() if card.count() else page.inner_text("body")
            check("5b gün kartında ders adı (İnkılap), 'Diğer' yok",
                  "İnkılap" in ctxt and "Diğer" not in ctxt, ctxt[:300])
            check("5c gün kartında 'Deneme' rozeti / 'soru' birimi yok (test görevi)",
                  "DENEME" not in ctxt.upper().split("DERS DAĞILIMI")[-1] and " soru" not in ctxt, ctxt[:300])
            grid = page.locator('text=Hafta Izgarası').locator("xpath=ancestor::section[1]")
            gtxt = page.inner_text("body")
            check("5d ızgara + ders dengesi: '0/2 test' ve '2 test' (soru değil)",
                  "0/2 test" in gtxt and "0/2 soru" not in gtxt, "")
            page.screenshot(path=".shots/quick_add_fuzzy_daycard.png")

            dark = b.new_page(viewport={"width": 390, "height": 844}, color_scheme="dark")
            dark.context.add_cookies(page.context.cookies())
            open_box(dark, d["s8"])
            dbox = dark.locator('input[aria-label="Görev ara"]')
            dbox.click()
            dbox.fill("destan")
            dark.wait_for_timeout(1800)
            dark.locator('[data-testid="quick-add-results"] button').first.click()
            dark.wait_for_timeout(600)
            ov = dark.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("6 390px: yatay taşma yok", ov <= 1, str(ov))
            r = measure(dark, '[data-testid="quick-add-picked"]', 4.5)
            check("6b koyu tema: seçim çipi okunur (4,5)", r["bad"] == 0, str(r["worst"])[:200])
            dark.screenshot(path=".shots/quick_add_fuzzy_dark_mobile.png")
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
