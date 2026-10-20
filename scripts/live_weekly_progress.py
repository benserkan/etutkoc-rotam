"""Canlı tarayıcı — öğrenci detayı haftalık ilerleme (2026-10-20).

Kurgu test_api_v2_weekly_progress ile aynı (seed/cleanup oradan). Dev sunucular: :3000 + :8081.
  1 Beş bölüm başlığı · eski üst özet şeridi yok · uyarı kartları katlı bölümde
  2 Manşet: görev uyumu %50 + "Geçmişin en kötüsü" + cetvel etiketleri
  3 Gün kartı üzerine gelince yapılmayan görevler
  4 "Seansa ekle" → gündem kuyruğuna yazılır
  5 Kırpma/taşma yok · koyu tema · 390px · konsol temiz
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

import scripts.test_api_v2_weekly_progress as T  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.exam_progress import SessionAgendaItem  # noqa: E402

WEB = "http://localhost:3000"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
os.makedirs(SHOTS, exist_ok=True)
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({str(detail)[:300]})")


def dismiss(page):
    for txt in ("Daha sonra", "Kapat"):
        try:
            b = page.get_by_role("button", name=txt)
            if b.count() and b.first.is_visible():
                b.first.click()
                page.wait_for_timeout(400)
        except Exception:
            pass


def login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', T.PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(3500)


def main() -> int:
    d = T.seed()
    sid = d["st"]
    print(f"\n=== canlı haftalık ilerleme — {T.PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            ctx = b.new_context(viewport={"width": 1440, "height": 950})
            page = ctx.new_page()
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            login(page, f"{T.PFX}_t@test.invalid")
            page.goto(f"{WEB}/teacher/students/{sid}", wait_until="networkidle")
            page.wait_for_selector('[data-section="student:weekly-progress"]', timeout=20000)
            page.wait_for_timeout(1500)
            dismiss(page)
            root = page.locator('[data-section="student:weekly-progress"]')
            body = root.inner_text()
            for h in ("Bu hafta nasıl gidiyor?", "Haftalar arası gidişat", "Önerilen önlemler",
                      "Bu hafta, öğrencinin kendi normaline göre", "Deneme analizi"):
                check(f"1 bölüm: {h}", h in body)
            check("1b eski özet şeridi yok (Hız / Hedef tutturma)",
                  page.get_by_text("HIZ (7G)").count() == 0 and not page.get_by_text("Hedef tutturma", exact=False).first.is_visible()
                  if page.get_by_text("Hedef tutturma", exact=False).count() else True)
            check("1c uyarı kartları katlı bölümde", page.locator("details summary", has_text="Diğer sinyaller").count() == 1)
            check("2a manşet %50", "%50" in body)
            check("2b kritik etiketi", "Geçmişin en kötüsü" in body)
            check("2c cetvel etiketleri", "bu hafta %50" in body and "geçen hafta %88" in body, body[:400])
            check("2d düz yorum", "Geçmiş haftaların en kötüsünden de kötü" in body)

            day = root.locator("button", has_text="Yapılmadı").first
            if not day.count():
                day = root.locator("button", has_text="4 görev yapılmadı").first
            day.hover()
            page.wait_for_timeout(500)
            check("3 gün kartı: yapılmayan görevler açılır", page.get_by_text("Yapılmayan 4 görev").count() >= 1)

            ov = page.evaluate("""() => {
              const r = document.querySelector('[data-section="student:weekly-progress"]');
              let bad = 0;
              r.querySelectorAll('*').forEach(e => { const s = getComputedStyle(e);
                if (s.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1) bad++; });
              return {bad, x: document.documentElement.scrollWidth - document.documentElement.clientWidth};
            }""")
            check("5a kırpma yok + yatay taşma yok", ov["bad"] == 0 and ov["x"] <= 1, ov)
            root.screenshot(path=os.path.join(SHOTS, "weekly_progress_light.png"))

            before = SessionLocal().query(SessionAgendaItem).filter(SessionAgendaItem.student_id == sid).count()
            root.get_by_role("button", name="Seansa ekle").first.click()
            page.wait_for_timeout(1500)
            after = SessionLocal().query(SessionAgendaItem).filter(SessionAgendaItem.student_id == sid).count()
            check("4 Seansa ekle → gündem kuyruğu", after == before + 1, f"{before}->{after}")
            check("5b konsol temiz", not errs, " | ".join(errs)[:300])
            ctx.close()

            dctx = b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark")
            dp = dctx.new_page()
            login(dp, f"{T.PFX}_t@test.invalid")
            dp.goto(f"{WEB}/teacher/students/{sid}", wait_until="networkidle")
            dp.wait_for_selector('[data-section="student:weekly-progress"]', timeout=20000)
            dp.wait_for_timeout(1500)
            dismiss(dp)
            dp.locator('[data-section="student:weekly-progress"]').screenshot(path=os.path.join(SHOTS, "weekly_progress_dark.png"))
            check("5c koyu tema yüklendi", dp.locator('[data-section="student:weekly-progress"]').is_visible())
            dctx.close()

            mctx = b.new_context(viewport={"width": 390, "height": 860})
            mp = mctx.new_page()
            login(mp, f"{T.PFX}_t@test.invalid")
            mp.goto(f"{WEB}/teacher/students/{sid}", wait_until="networkidle")
            mp.wait_for_selector('[data-section="student:weekly-progress"]', timeout=20000)
            mp.wait_for_timeout(1500)
            dismiss(mp)
            x = mp.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("5d 390px yatay kaydırma yok", x <= 1, x)
            mp.screenshot(path=os.path.join(SHOTS, "weekly_progress_mobile.png"), full_page=True)
            mctx.close()
            b.close()
    finally:
        with SessionLocal() as db:
            db.query(SessionAgendaItem).filter(SessionAgendaItem.student_id.in_(T.ids["users"])).delete(
                synchronize_session=False)
            db.commit()
        T.cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
