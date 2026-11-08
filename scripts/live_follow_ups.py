# -*- coding: utf-8 -*-
"""Takip listesi + Ölçümler — gerçek tarayıcı testi (2026-11-08).

Geçici süper admin + iki koç ölçüm geçmişi kurar; panelde iş ekler, ölçüye
bağlar, tamamlar (tekrarlayan → sıradaki açılır), erteler; Ölçümler sayfası
koç kırılımını gösterir; pano kartı + menü rozeti doğrulanır. Kırpma/taşma
denetimi + 390px. Sonra kendi kayıtlarını siler (tohum kayıtlara dokunmaz).

    python scripts/live_follow_ups.py   (dev :3000 + :8081 açık olmalı)
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import FollowUp, MetricSnapshot, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lfu{secrets.token_hex(3)}"
PWD = "LiveFollow1!@xyz"
SHOTS = Path(__file__).resolve().parent.parent / ".shots"
SHOTS.mkdir(exist_ok=True)
TODAY = date.today()

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


def seed() -> dict:
    with SessionLocal() as db:
        sup = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                   full_name=f"{PFX} Süper", role=UserRole.SUPER_ADMIN, is_active=True)
        c1 = User(email=f"{PFX}_c1@test.invalid", password_hash="x", full_name=f"{PFX} Ayşe Koç",
                  role=UserRole.TEACHER, is_active=True)
        c2 = User(email=f"{PFX}_c2@test.invalid", password_hash="x", full_name=f"{PFX} Mehmet Koç",
                  role=UserRole.TEACHER, is_active=True)
        db.add_all([sup, c1, c2])
        db.flush()
        for d in range(21, -1, -3):
            day = TODAY - timedelta(days=d)
            db.add(MetricSnapshot(metric_key="rec.shown", owner_type="coach", owner_id=c1.id,
                                  measured_on=day, value=62 - (21 - d) * 0.7, sample_n=420))
            db.add(MetricSnapshot(metric_key="rec.shown", owner_type="coach", owner_id=c2.id,
                                  measured_on=day, value=40 + (21 - d) * 0.8, sample_n=310))
        # Bugün vadeli bir iş: pano kartı + rozet
        db.add(FollowUp(title=f"{PFX} bugün bakılacak", due_on=TODAY, category="urun",
                        priority="high", status="open"))
        db.commit()
        return {"sup": sup.id, "c1": c1.id, "c2": c2.id}


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(FollowUp).where(FollowUp.title.like(f"{PFX}%")))
        db.execute(sa_delete(MetricSnapshot).where(MetricSnapshot.owner_id.in_([ids["c1"], ids["c2"]]),
                                                   MetricSnapshot.owner_type == "coach"))
        db.execute(sa_delete(User).where(User.id.in_(list(ids.values()))))
        db.commit()


OVERFLOW_JS = """(sel) => {
  const root = document.querySelector(sel) || document.body;
  const bad = [];
  root.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) bad.push(el.textContent.slice(0,40));
  });
  return {bad, hscroll: document.documentElement.scrollWidth > window.innerWidth + 1};
}"""


def main() -> int:
    ids = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1400, "height": 1000})
            errors: list[str] = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{PFX}_s@test.invalid")
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            page.goto(f"{WEB}/admin", wait_until="networkidle")
            page.wait_for_timeout(2500)
            card = page.locator('[data-section="admin:follow-ups-due"]')
            check("1. pano: 'Bugün bakılacaklar' kartı + iş adı",
                  card.count() == 1 and f"{PFX} bugün bakılacak" in card.inner_text(), "")
            badge_link = page.locator('a[href="/admin/follow-ups"]').first
            check("2. menü 'Takip listesi' rozetli", badge_link.count() == 1
                  and any(ch.isdigit() for ch in badge_link.inner_text()), badge_link.inner_text() if badge_link.count() else "")

            page.goto(f"{WEB}/admin/follow-ups", wait_until="networkidle")
            page.wait_for_timeout(2000)
            check("3. 'Bugün' grubunda iş", page.locator('[data-section="follow-ups:today"]').count() == 1, "")

            # Yeni iş: ölçüye bağlı, 3 hafta sonra, 4 haftada bir
            page.click('button:has-text("Yeni iş")')
            page.wait_for_timeout(600)
            dlg = page.locator('[role="dialog"]')
            dlg.locator("#fu-title").fill(f"{PFX} öneri isabeti kontrol")
            dlg.locator("#fu-desc").fill("Düşen koç var mı bak.")
            dlg.locator('button:has-text("3 hafta sonra")').click()
            dlg.locator("#fu-rec").select_option("28")
            dlg.locator('label:has-text("Bir ölçüye bağla") input').check()
            dlg.locator("#fu-metric").select_option("rec.shown")
            dlg.locator("#fu-owner").select_option("coach")
            dlg.locator("#fu-base").fill((TODAY - timedelta(days=21)).isoformat())
            page.screenshot(path=str(SHOTS / "follow_up_form.png"))
            dlg.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            art = page.locator("article", has_text=f"{PFX} öneri isabeti kontrol")
            txt = art.inner_text() if art.count() else ""
            check("4. iş eklendi: 21 gün kaldı + tekrar + ölçü rozeti",
                  "21 gün kaldı" in txt and "28 günde bir" in txt and "koç bazında" in txt, txt[:200])
            check("5. ölçüm raporu: düşen koç adıyla",
                  "Düşüş var" in txt and f"{PFX} Ayşe Koç" in txt, txt[:400])
            if art.count():
                # Düşüş olan raporda tablo zaten açık gelir; kapalıysa aç
                if art.locator('button:has-text("Ayrıntı (")').count():
                    art.locator('button:has-text("Ayrıntı (")').first.click()
                page.wait_for_timeout(400)
                check("6. ayrıntı tablosu yükselen koçu gösterir",
                      f"{PFX} Mehmet Koç" in art.inner_text() and "İyileşme var" in art.inner_text(), "")
            page.screenshot(path=str(SHOTS / "follow_ups_list.png"), full_page=True)

            # Ertele → bugün grubundan çıkar
            today_art = page.locator("article", has_text=f"{PFX} bugün bakılacak")
            today_art.locator('button:has-text("Ertele")').click()
            page.wait_for_timeout(400)
            page.locator('[role="menuitem"]:has-text("3 gün")').click()
            page.wait_for_timeout(2000)
            t2 = page.locator("article", has_text=f"{PFX} bugün bakılacak").inner_text()
            check("7. ertele 3 gün → '3 gün kaldı' + ilk vade notu", "3 gün kaldı" in t2 and "ertelendi" in t2, t2[:200])

            # Tamamla → sıradaki açılır
            art.locator('button:has-text("Tamamla")').click()
            page.wait_for_timeout(500)
            d2 = page.locator('[role="dialog"]')
            d2.locator("#fu-note").fill("Ayşe Koç ile görüşüldü.")
            d2.locator('button:has-text("Tamamla")').click()
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                rows = db.query(FollowUp).filter(FollowUp.title == f"{PFX} öneri isabeti kontrol").all()
                done = [r for r in rows if r.status == "done"]
                opn = [r for r in rows if r.status == "open"]
            check("8. tamamla → kayıt kapandı + sıradaki 28 gün sonra açıldı",
                  len(done) == 1 and len(opn) == 1 and opn[0].due_on == TODAY + timedelta(days=28)
                  and done[0].result_note == "Ayşe Koç ile görüşüldü.", [(r.status, r.due_on) for r in rows])
            page.click('button:has-text("Kapalı")')
            page.wait_for_timeout(1500)
            check("9. kapalı sekmesinde sonuç notu", "Ayşe Koç ile görüşüldü." in page.inner_text("main"), "")

            ov = page.evaluate(OVERFLOW_JS, "main")
            check("10. kırpma/yatay taşma yok", not ov["bad"] and not ov["hscroll"], ov)

            page.goto(f"{WEB}/admin/metrics", wait_until="networkidle")
            page.wait_for_timeout(2000)
            mcard = page.locator('[data-metric="rec.shown"]')
            check("11. Ölçümler: öneri isabeti kartı", mcard.count() == 1, "")
            mcard.locator('button:has-text("Koç kırılımı")').click()
            page.wait_for_timeout(1500)
            mt = mcard.inner_text()
            check("12. koç kırılımı: iki koç + 3 hafta değişimi",
                  f"{PFX} Ayşe Koç" in mt and f"{PFX} Mehmet Koç" in mt and "puan" in mt, mt[:300])
            page.screenshot(path=str(SHOTS / "metrics_page.png"), full_page=True)

            mob = b.new_page(viewport={"width": 390, "height": 844})
            mob.context.add_cookies(page.context.cookies())
            mob.goto(f"{WEB}/admin/follow-ups", wait_until="networkidle")
            mob.wait_for_timeout(2000)
            ovm = mob.evaluate(OVERFLOW_JS, "main")
            check("13. 390px: yatay taşma yok", not ovm["hscroll"], ovm)
            mob.screenshot(path=str(SHOTS / "follow_ups_mobile.png"), full_page=True)

            real = [e for e in errors if "favicon" not in e and "Download the React" not in e]
            check("14. konsol hatası yok", not real, real[:3])
            b.close()
    finally:
        cleanup(ids)
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
