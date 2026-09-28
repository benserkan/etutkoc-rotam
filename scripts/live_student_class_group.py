"""Şube — öğrenci listesi canlı tarayıcı testi (2026-09-28, kurum toplu kurulumu 4/4).

Kendi verisini kurar/temizler. Dev sunucular (:3000 + :8081) açık olmalı.
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

BASE = "http://localhost:3000"
PFX = f"lscg_{secrets.token_hex(3)}"
PWD = "LiveClassGrp!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Şube Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_unlimited", subscription_status="active")
        db.add(coach)
        db.flush()
        ids = []
        for n, g in [("Ayşe Şubeli Çok Uzun Soyadlı Öğrenci", "10-A"), ("Burak", "10-A"),
                     ("Ceren", None), ("Deniz", None)]:
            u = User(email=f"{PFX}_{len(ids)}@test.invalid", password_hash=hash_password(PWD),
                     full_name=n, role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                     grade_level=10, class_group=g)
            db.add(u)
            db.flush()
            ids.append(u.id)
        db.commit()
        return {"coach": coach.id, "email": coach.email, "ids": ids}


def cleanup(d):
    with SessionLocal() as db:
        db.execute(sa_delete(User).where(User.id.in_(d["ids"] + [d["coach"]])))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1400, "height": 950})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/students", wait_until="networkidle")
            pg.wait_for_timeout(2000)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(600)
            chk("1. şube rozetleri (2)", pg.locator('[data-testid="class-group-badge"]').count() == 2)
            sel = pg.get_by_label("Şube filtresi")
            chk("2. şube filtresi görünür", sel.count() == 1)
            opts = sel.locator("option").all_inner_texts() if sel.count() else []
            chk("3. seçenekler 10-A(2) + Şubesiz(2)",
                any("10-A (2)" in o for o in opts) and any("Şubesiz (2)" in o for o in opts), str(opts))
            # Ceren + Deniz seç → 10-B
            boxes = pg.locator('[data-testid="student-select"]')
            rows = pg.locator("li.group")
            for i in range(rows.count()):
                t = rows.nth(i).inner_text()
                if "Ceren" in t or "Deniz" in t:
                    rows.nth(i).locator('[data-testid="student-select"]').check()
            chk("4. toplu çubuk görünür", pg.locator('[data-testid="class-group-bar"]').count() == 1)
            chk("4a. çubukta açıklama var",
                "Öğrencinin sınıfını değiştirmez" in pg.locator('[data-testid="class-group-help"]').inner_text())
            # 10. sınıf öğrencilerini 12-A'ya almaya çalış → uyuşmazlık uyarısı
            pg.locator('[data-testid="class-group-bar"] input[aria-label="Şube adı"]').fill("12-A")
            pg.click('[data-testid="class-group-apply"]')
            pg.wait_for_timeout(2000)
            mm = pg.locator('[data-testid="class-group-mismatch"]')
            chk("4b. 12-A → sınıf uyuşmuyor uyarısı", mm.count() == 1 and "10. sınıf" in mm.inner_text(),
                mm.inner_text() if mm.count() else "")
            with SessionLocal() as db:
                g12 = [u.class_group for u in db.query(User).filter(User.id.in_(d["ids"]))]
            chk("4c. uyuşmazlıkta hiçbir şey yazılmadı", "12-A" not in g12, str(g12))
            pg.locator('[data-testid="class-group-bar"] input[aria-label="Şube adı"]').fill("10-B")
            chk("4d. ad değişince uyarı kalkar", mm.count() == 0)
            pg.click('[data-testid="class-group-apply"]')
            pg.wait_for_timeout(2500)
            chk("5. rozet sayısı 4 (yenilemesiz)",
                pg.locator('[data-testid="class-group-badge"]').count() == 4)
            with SessionLocal() as db:
                gs = {u.full_name: u.class_group for u in db.query(User).filter(User.id.in_(d["ids"]))}
            chk("6. DB'de 10-B", gs.get("Ceren") == "10-B" and gs.get("Deniz") == "10-B", str(gs))
            chk("7. seçim temizlendi", pg.locator('[data-testid="class-group-bar"]').count() == 0)
            # filtre
            pg.get_by_label("Şube filtresi").select_option("10-B")
            pg.wait_for_timeout(2500)
            names = pg.locator("li.group").all_inner_texts()
            chk("8. 10-B süzgeci 2 öğrenci", len(names) == 2 and all(("Ceren" in n or "Deniz" in n) for n in names),
                str(len(names)))
            chk("9. URL'de class_group", "class_group=10-B" in pg.url, pg.url)
            pg.goto(f"{BASE}/teacher/students", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            ov = pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
            chk("10. yatay taşma yok", not ov)
            pg.screenshot(path=os.path.join(SHOT_DIR, "student_class_group.png"))
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(300)
            rows.nth(0).locator('[data-testid="student-select"]').check()
            bad = measure(pg, '[data-testid="class-group-bar"]', min_ratio=3.0)["bad"]
            chk("11. koyu tema çubuk kontrastı", bad == 0, str(bad))
            pg.set_viewport_size({"width": 390, "height": 800})
            pg.wait_for_timeout(500)
            ov = pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
            chk("12. 390px taşma yok", not ov)
            b.close()
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
