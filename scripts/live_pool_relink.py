"""Canlı tarayıcı — koç, öğrencinin eklediği kalemin konusunu onaydan önce değiştirir (2026-10-22).

Next :3000 + backend :8081. PYTHONPATH=. python scripts/live_pool_relink.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import scripts.live_student_pool_add_linked as base  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import PoolItem, StudyPeriod, User  # noqa: E402

BASE = "http://localhost:3000"


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = base.ids
    ids.update(base.seed())
    check = base.check
    with SessionLocal() as db:
        per = db.query(StudyPeriod).filter(StudyPeriod.student_id == ids["st"]).first()
        it = PoolItem(period_id=per.id, student_id=ids["st"], subject_id=ids["tyt"], topic_id=ids["t1"],
                      quantity=3, unit="test", source="ogrenci", approval="bekliyor", label="yanlış konu")
        db.add(it)
        db.commit()
        iid = it.id
        coach_email = db.get(User, ids["users"][0]).email
    print(f"\n=== Koç kalem bağı düzeltme ({base.PFX}) ===\n")
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            page = br.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{BASE}/login", wait_until="networkidle")
            page.fill('input[name="email"]', coach_email)
            page.fill('input[name="password"]', base.PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{BASE}/teacher/students/{ids['st']}/pool?mod=izle", wait_until="networkidle")
            page.wait_for_timeout(2000)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(500)
            btn = page.locator('[data-testid="relink-open"]').first
            check("1 onay satırında 'Konuyu değiştir'", btn.count() == 1)
            btn.click()
            dlg = page.locator('[data-section="pool:relink"]')
            dlg.wait_for(timeout=8000)
            check("2 pencerede mevcut bağ yazar", "Üslü Sayılar" in dlg.inner_text(), dlg.inner_text()[:300])
            dlg.locator('[role="tab"]:has-text("Öğrencinin kitabından")').click()
            page.wait_for_timeout(1500)
            dlg.locator(f'[data-section-id="{ids["s1"]}"]').first.click()
            page.wait_for_timeout(400)
            check("3 yeni seçim özeti", "Köklü Sayılar Testleri" in dlg.locator('[data-testid="relink-picked"]').inner_text())
            page.screenshot(path=os.path.join(ROOT, ".shots", "pool_relink.png"))
            over = dlg.evaluate("e => e.scrollWidth > e.clientWidth + 1")
            check("4 pencerede yatay taşma yok", not over)
            dlg.locator('[data-testid="relink-approve"]').click()
            page.wait_for_timeout(3000)
            with SessionLocal() as db:
                row = db.get(PoolItem, iid)
                check("5 kalem kitaba bağlandı + onaylandı + miktar 3",
                      row.book_section_id == ids["s1"] and row.approval == "onaylandi" and row.quantity == 3,
                      (row.book_section_id, row.approval, row.quantity))
            check("6 pencere kapandı", page.locator('[data-section="pool:relink"]').count() == 0)
            br.close()
    finally:
        base.cleanup()
    print(f"\n{base.passed} passed · {len(base.failed)} failed")
    return 1 if base.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
