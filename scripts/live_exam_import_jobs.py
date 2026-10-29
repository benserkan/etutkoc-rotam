"""Canlı tarayıcı: karne arka planda okunur, kullanıcı başka sayfadayken
köşedeki kutu "okundu" der (2026-10-29).

Akış: koç girişi → öğrenci Denemeler → PDF seç → okuma başlar → "Kapat, arkada
okunmaya devam etsin" → panoya geç → köşede "okunuyor" satırı → okuma bitince
kalıcı "Karne okundu" kutusu → başka sayfaya geç, kutu hâlâ orada → Önizle →
önizleme açılır (PDF yeniden yüklenmeden) → Vazgeç → Denemeler bandında
"Önizle ve kaydet" bekler → Vazgeç (sil) → bant kaybolur.

Kullanım: python scripts/live_exam_import_jobs.py [pdf]   (dev :3000 + :8081,
GERÇEK okuma — dev koçunun kredisinden düşer)
"""
from __future__ import annotations

import os
import secrets
import shutil
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://localhost:3000"
EMAIL, PASSWORD = "rehber-koc@etutkoc.demo", "RehberDemo2026!"
STUDENT_ID = int(os.environ.get("LIVE_STUDENT_ID", "441"))
SHOTS = os.path.join(os.path.dirname(__file__), "..", ".shots")
os.makedirs(SHOTS, exist_ok=True)

passed, failed = 0, []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label} {detail}")


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "ornek_sonuc_karnesi_4.pdf")
    # Her koşuda farklı bayt (aynı PDF koruması testi durdurmasın): sona yorum eklenir
    tmpdir = tempfile.mkdtemp()
    pdf = os.path.join(tmpdir, "Deneme-karnesi-14.10.2026.pdf")
    shutil.copyfile(src, pdf)
    with open(pdf, "ab") as f:
        f.write(f"\n%{secrets.token_hex(8)}\n".encode())

    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.on("dialog", lambda d: d.accept())
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        pg.goto(f"{BASE}/login", wait_until="networkidle")
        pg.fill("#email", EMAIL)
        pg.fill("#password", PASSWORD)
        pg.click("button[type=submit]")
        pg.wait_for_url("**/teacher/**", timeout=30000)
        pg.wait_for_timeout(1500)
        for txt in ("Daha sonra", "Kapat"):
            loc = pg.get_by_role("button", name=txt)
            if loc.count():
                try:
                    loc.first.click(timeout=1500)
                except Exception:
                    pass

        pg.goto(f"{BASE}/teacher/students/{STUDENT_ID}#exams", wait_until="networkidle")
        pg.wait_for_timeout(2000)
        pg.get_by_text("Deneme sonuç PDF'ini yükle", exact=False).first.click()
        pg.wait_for_selector("[role=dialog]", timeout=10000)
        t0 = time.time()
        pg.locator("[role=dialog] input[type=file]").set_input_files(pdf)
        btn = pg.get_by_role("button", name="Kapat, arkada okunmaya devam etsin")
        btn.wait_for(timeout=15000)
        check("1. yükleme sonrası 'arkada okunsun' seçeneği hızlı çıktı", time.time() - t0 < 10,
              f"{time.time() - t0:.1f}s")
        pg.screenshot(path=os.path.join(SHOTS, "job_analyzing.png"))
        btn.click()
        pg.wait_for_timeout(800)
        check("2. pencere kapandı", pg.locator("[role=dialog]").count() == 0)

        pg.goto(f"{BASE}/teacher/dashboard", wait_until="networkidle")
        tracker = pg.locator("[data-section=ai-jobs-tracker]")
        tracker.wait_for(timeout=15000)
        check("3. başka sayfada köşede 'okunuyor' satırı", "okunuyor" in tracker.inner_text(),
              tracker.inner_text()[:120])

        done = pg.get_by_text("Karne okundu", exact=True)
        done.wait_for(timeout=420000)
        check("4. okuma bitince kalıcı 'Karne okundu' kutusu çıktı", done.is_visible())
        pg.screenshot(path=os.path.join(SHOTS, "job_done_notice.png"))

        pg.goto(f"{BASE}/teacher/students", wait_until="networkidle")
        pg.get_by_text("Karne okundu", exact=True).wait_for(timeout=15000)
        check("5. sayfa değişince kutu hâlâ duruyor (havada kalmaz)", True)

        pg.get_by_role("button", name="Önizle ve kaydet").first.click()
        pg.wait_for_selector("[role=dialog]", timeout=10000)
        pg.get_by_text("Kontrol ettim, kaydet").wait_for(timeout=30000)
        check("6. Önizle → taslak açıldı (PDF yeniden yüklenmeden)", True)
        pg.screenshot(path=os.path.join(SHOTS, "job_preview.png"))
        pg.get_by_role("button", name="Vazgeç").first.click()
        pg.wait_for_timeout(1000)
        check("7. önizlenen iş köşeden kalktı",
              pg.get_by_text("Karne okundu", exact=True).count() == 0)

        pg.goto(f"{BASE}/teacher/students/{STUDENT_ID}#exams", wait_until="networkidle")
        band = pg.locator("[data-section='exams:import-jobs']")
        band.wait_for(timeout=15000)
        check("8. Denemeler bandında 'Önizle ve kaydet' bekliyor",
              "Önizle ve kaydet" in band.inner_text(), band.inner_text()[:120])
        pg.screenshot(path=os.path.join(SHOTS, "job_band.png"))
        band.get_by_role("button", name="Vazgeç").first.click()
        pg.wait_for_timeout(2500)
        check("9. Vazgeç → bant kayboldu", pg.locator("[data-section='exams:import-jobs']").count() == 0)

        sw = pg.evaluate("document.documentElement.scrollWidth")
        check("10. yatay taşma yok", sw <= 1440, sw)
        check("11. sayfa hatası yok", not errs, errs[:2])
        b.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
