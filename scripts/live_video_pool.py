"""Canlı tarayıcı — havuz editöründe Video Sepeti (2026-10-20).

  1 /pool sayfasında Video Sepeti düğmesi görünür
  2 Sepet havuz metnini gösterir, grup "Havuza ekle" → havuz listesinde video kalemi belirir
  3 Videolar "Havuzda" rozeti alır · koyu tema · konsol temiz

Çalıştır: python scripts/live_video_pool.py   (dev :3000 + :8081 açık)
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
from sqlalchemy import delete as sa_delete  # noqa: E402

from scripts import test_api_v2_pool_student as base  # noqa: E402
from scripts.test_video_pool import seed_videos  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import PoolItem  # noqa: E402
from app.models.video_basket import VideoBasketItem  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402

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
    for txt in ("Daha sonra",):
        try:
            b = page.get_by_role("button", name=txt)
            if b.count() and b.first.is_visible():
                b.first.click()
                page.wait_for_timeout(400)
        except Exception:
            pass


def main() -> int:
    get_login_limiter().reset()
    d = base.seed()
    v = seed_videos(d)
    sid = d["st"]
    print(f"\n=== canlı video → havuz — öğrenci #{sid} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            ctx = b.new_context(viewport={"width": 1440, "height": 950})
            page = ctx.new_page()
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[type="email"]', f"{base.PFX}_t@test.invalid")
            page.fill('input[type="password"]', base.PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3500)
            page.goto(f"{WEB}/teacher/students/{sid}/pool?mod=duzenle", wait_until="networkidle")
            page.wait_for_timeout(2000)
            dismiss(page)
            fab = page.locator('[data-testid="video-basket-fab"]')
            check("1 havuz editöründe Video Sepeti düğmesi", fab.count() == 1 and fab.is_visible())
            page.screenshot(path=os.path.join(SHOTS, "video_pool_before.png"))
            fab.click()
            page.wait_for_selector('[data-section="week:video-basket"]', timeout=10000)
            page.wait_for_timeout(800)
            panel = page.locator('[data-section="week:video-basket"]')
            check("2a sepet havuz açıklamasını gösterir", "Havuza ekle" in panel.inner_text(), panel.inner_text()[:200])
            page.select_option("#vb-list", "all")
            page.wait_for_timeout(500)
            btn = panel.locator('[data-testid="video-group-to-pool"]', has_text="3 video")
            check("2b grupta 'Havuza ekle (3 video)'", btn.count() == 1)
            page.screenshot(path=os.path.join(SHOTS, "video_pool_basket.png"))
            btn.click()
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                n = db.query(PoolItem).filter(PoolItem.student_id == sid, PoolItem.unit == "etkinlik",
                                              PoolItem.label.like("%3 video%")).count()
            check("2c DB: havuza video kalemi yazıldı", n == 1, n)
            ed = page.locator('[data-section="pool:editor"]').inner_text()
            check("2d havuz listesinde kalem yenilemesiz görünür", "3 video (30 dk)" in ed, ed[:300])
            hdr = panel.locator("button", has_text="Hücre").first
            hdr.click()
            page.wait_for_timeout(500)
            check("3a videolar 'Havuzda' rozeti", panel.locator('[data-video-state="havuzda"]').count() == 3,
                  panel.locator('[data-video-state="havuzda"]').count())
            page.emulate_media(color_scheme="dark")
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(SHOTS, "video_pool_dark.png"))
            bad = [e for e in errs if "favicon" not in e and "Hydration" not in e]
            check("3b konsol hatası yok", not bad, bad[:3])
            b.close()
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(VideoBasketItem).where(VideoBasketItem.student_id.in_([d["st"], d["gg"]])))
            db.commit()
        base.cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
