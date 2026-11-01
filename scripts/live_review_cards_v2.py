"""Canlı tarayıcı testi — tekrar kartları v2 (koç ekleme/silme + öğrenci geri al).

Önkoşul: dev backend :8081 + next :3000 + test verisi (geçici koç/öğrenci).
  python scripts/live_review_cards_v2.py <student_id> <shots_dir>
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE = "http://localhost:3000"
PW = "UiTest2026!@xyz"
SID = int(sys.argv[1])
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "."
os.makedirs(SHOTS, exist_ok=True)
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def login(page, email):
    page.context.clear_cookies()
    page.goto(f"{BASE}/login")
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', PW)
    page.click('button[type="submit"]')
    page.wait_for_timeout(4000)


def dismiss(page):
    for name in ("Daha sonra", "Kapat"):
        b = page.get_by_role("button", name=name, exact=True)
        if b.count() and b.first.is_visible():
            b.first.click()
            page.wait_for_timeout(400)


def ellipsis_count(page, sel):
    return page.evaluate(
        """(sel) => { const root = document.querySelector(sel); if (!root) return -1;
        let n = 0; root.querySelectorAll('*').forEach(el => {
          const cs = getComputedStyle(el);
          if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) n++; });
        return n; }""",
        sel,
    )


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome")
    page = br.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    # ---------------- KOÇ ----------------
    login(page, "rv_ui_koc@test.invalid")
    page.goto(f"{BASE}/teacher/students/{SID}/review")
    page.wait_for_timeout(3500)
    dismiss(page)
    check("K1. tekrar sayfası açıldı", page.get_by_text("Konuları kart olarak ekle").count() > 0)
    page.select_option("#review-subject", label="Matematik")
    page.wait_for_selector('[data-testid="review-candidates"]', timeout=15000)
    page.wait_for_timeout(800)
    box = page.locator('[data-testid="review-candidates"]')
    text = box.inner_text()
    check("K2. 8. sınıf grubu 'kendi sınıfı' olarak en üstte",
          text.strip().upper().startswith("8. SINIF"), text[:40])
    check("K3. tema başlığı ('Tema:') listede yok", "Tema:" not in text)
    checked = page.locator('[data-testid="review-candidates"] input[type="checkbox"]:checked')
    check("K4. önerilen 4 konu işaretli geldi", checked.count() == 4, str(checked.count()))
    check("K5. neden rozeti görünüyor ('test çözdü', 'Koç konuyu kapattı')",
          "test çözdü" in text and "Koç konuyu kapattı" in text)
    check("K6. konu listesinde kırpılmış metin yok",
          ellipsis_count(page, '[data-testid="review-candidates"]') == 0)
    page.screenshot(path=os.path.join(SHOTS, "review_v2_koc_secim.png"), full_page=True)

    # Bir alt sınıf konusunu da ekle (koç isterse seçebilir)
    first_unchecked = page.locator('[data-testid="review-candidates"] input[type="checkbox"]:not(:checked):not(:disabled)').first
    first_unchecked.check()
    page.get_by_role("button", name="5 konuyu kart olarak ekle").click()
    page.wait_for_timeout(2500)
    check("K7. 5 kart eklendi (liste güncellendi)", page.get_by_text("Kartlar (5)").count() > 0)
    page.wait_for_timeout(800)
    check("K8. eklenen konular aday listesinde 'kartı var' oldu",
          page.locator('[data-testid="review-candidates"]').inner_text().count("kartı var") >= 5)

    # Sil: bir kartı seç → iki aşamalı onay
    page.locator('input[aria-label$="kartını seç"]').first.check()
    page.get_by_role("button", name="Seçilenleri sil (1)").click()
    check("K9. silmeden önce onay istenir", page.get_by_role("button", name="Eminim, 1 kartı sil").count() == 1)
    page.get_by_role("button", name="Eminim, 1 kartı sil").click()
    page.wait_for_timeout(2500)
    check("K10. kart silindi (4 kaldı)", page.get_by_text("Kartlar (4)").count() > 0)
    page.screenshot(path=os.path.join(SHOTS, "review_v2_koc_kartlar.png"), full_page=True)

    # Koyu tema kontrolü (yalnız ekran görüntüsü)
    page.emulate_media(color_scheme="dark")
    page.screenshot(path=os.path.join(SHOTS, "review_v2_koc_dark.png"), full_page=True)
    page.emulate_media(color_scheme="light")

    # ---------------- ÖĞRENCİ ----------------
    login(page, "rv_ui_ogr@test.invalid")
    page.goto(f"{BASE}/student/review")
    page.wait_for_timeout(3500)
    dismiss(page)
    topic1 = page.locator("p.font-display.text-3xl").first.inner_text()
    check("S1. öğrencinin önüne kart geldi", bool(topic1.strip()), topic1)
    page.get_by_role("button", name="Hatırlamayı dene").click()
    page.get_by_role("button", name="Hatırlamadım", exact=True).click()
    page.wait_for_timeout(2000)
    toast = page.locator("[data-sonner-toast]").first
    ttext = toast.inner_text() if toast.count() else ""
    check("S2. bildirim: 'bu hafta çalış; 7 gün sonra'",
          "Bu hafta bu konuyu çalış" in ttext and "7 gün" in ttext, ttext)
    page.screenshot(path=os.path.join(SHOTS, "review_v2_ogr_toast.png"))
    nxt = page.locator("p.font-display.text-3xl").first.inner_text()
    check("S3. sıradaki kart ekranda", nxt != topic1, f"{topic1} -> {nxt}")
    page.get_by_role("button", name="Geri al").click()
    page.wait_for_timeout(3000)
    back = page.locator("p.font-display.text-3xl").first.inner_text()
    check("S4. 'Geri al' sonrası aynı kart yeniden önde", back == topic1, f"{back} vs {topic1}")

    # İyi → 7 gün
    page.get_by_role("button", name="Hatırlamayı dene").click()
    page.get_by_role("button", name="İyi", exact=True).click()
    page.wait_for_timeout(2000)
    ttext = page.locator("[data-sonner-toast]").first.inner_text()
    check("S5. 'İyi' sonrası sıradaki tekrar 7 gün sonra", "7 gün sonra" in ttext, ttext)

    page.set_viewport_size({"width": 390, "height": 844})
    page.reload()
    page.wait_for_timeout(3000)
    sw = page.evaluate("document.documentElement.scrollWidth")
    check("S6. 390px'te yatay taşma yok", sw <= 391, str(sw))
    page.screenshot(path=os.path.join(SHOTS, "review_v2_ogr_mobile.png"), full_page=True)

    real = [e for e in errors if "favicon" not in e and "Download the React DevTools" not in e]
    check("Z. konsolda hata yok", not real, " | ".join(real[:3]))
    br.close()

print(f"\n{passed} passed, {len(failed)} failed")
for f in failed:
    print("  -", f)
sys.exit(0 if not failed else 1)
