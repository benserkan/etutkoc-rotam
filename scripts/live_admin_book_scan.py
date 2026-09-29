"""Süper admin "Tam kitap tara" canlı testi (2026-09-29).

Dev sunucular (:3000 + :8081, Gemini erişimli run_dev_patched) açık olmalı.
Kullanım: python -m scripts.live_admin_book_scan "<tam kitap.pdf>"
GERÇEK tarama yapar (Gemini) — dijital PDF birkaç dk, taranmış PDF 10-20 dk.
"""
from __future__ import annotations

import os
import secrets
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.book_scan_job import BookScanJob
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

BASE = "http://localhost:3000"
PFX = f"lbscan_{secrets.token_hex(3)}"
PWD = "LiveScan!2345xyz"
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


def overflow(pg) -> bool:
    return pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")


def main() -> int:
    from playwright.sync_api import sync_playwright
    pdf = sys.argv[1]
    os.makedirs(SHOT_DIR, exist_ok=True)
    with SessionLocal() as db:
        u = User(email=f"{PFX}@test.invalid", password_hash=hash_password(PWD), full_name="Canlı Tarama Admin",
                 role=UserRole.SUPER_ADMIN, is_active=True)
        db.add(u)
        db.commit()
        uid, email = u.id, u.email
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1300, "height": 950})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', email)
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/admin/book-catalog", wait_until="networkidle")
            pg.wait_for_timeout(2000)
            chk("1. 'Tam kitap tara' paneli görünür", pg.locator('[data-testid="scan-jobs-panel"]').count() == 1)
            pg.locator('[data-testid="scan-file"]').set_input_files(pdf)
            t0 = time.time()
            pg.locator('[data-testid="scan-start"]').click()
            fname = os.path.basename(pdf)
            row = pg.locator('[data-testid="scan-job-row"]').filter(has_text=fname).first
            row.wait_for(timeout=600_000)
            print(f"     yükleme + iş açılışı {time.time() - t0:.0f} sn")
            chk("2. iş satırı açıldı", "Sırada" in row.inner_text() or "Taranıyor" in row.inner_text()
                or "Bitti" in row.inner_text(), row.inner_text()[:120])
            pg.screenshot(path=os.path.join(SHOT_DIR, "admin_scan_running.png"))
            deadline = time.time() + 40 * 60
            last = ""
            while time.time() < deadline:
                txt = row.inner_text()
                line = txt.replace("\n", " | ")[:160]
                if line != last:
                    print("     ", line)
                    last = line
                if "Bitti" in txt or "Başarısız" in txt:
                    break
                pg.wait_for_timeout(5000)
            txt = row.inner_text()
            chk("3. tarama bitti", "Bitti" in txt, txt[:300])
            print(f"     toplam süre {time.time() - t0:.0f} sn")
            if "Bitti" not in txt:
                raise SystemExit
            row.locator('[data-testid="scan-open"]').click()
            pg.wait_for_selector('[data-testid="scan-result"]', timeout=30_000)
            gates = pg.locator('[data-testid="scan-gates"] li').count()
            chk("4. sonuç: kapılar listelendi", gates >= 2, str(gates))
            chk("5. sonuç penceresinde taşma yok", not overflow(pg))
            pg.screenshot(path=os.path.join(SHOT_DIR, "admin_scan_result.png"), full_page=True)
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(300)
            bad = measure(pg, '[data-testid="scan-result"]', min_ratio=3.0)["bad"]
            chk("6. koyu tema kontrastı (sonuç)", bad == 0, str(bad))
            pg.evaluate("() => document.documentElement.classList.remove('dark')")
            pg.locator('[data-testid="scan-import"]').click()
            pg.wait_for_timeout(1500)
            dlg = pg.locator('[role="dialog"]')
            labels = dlg.locator('input[placeholder="Bölüm / ünite adı"]').count()
            chk("7. 'Kataloğa aktar' → kayıt formu bölümlerle dolu", labels >= 5, str(labels))
            pg.screenshot(path=os.path.join(SHOT_DIR, "admin_scan_import.png"), full_page=True)
            b.close()
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(BookScanJob).where(BookScanJob.created_by_id == uid))
            db.execute(sa_delete(User).where(User.id == uid))
            db.commit()
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
