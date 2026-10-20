"""Canlı tarayıcı — Denemeler › Branş denemeleri analizi (2026-10-20).

Ön koşul: `python -m scripts.seed_weekly_progress_demo` (Örnek Öğrenci, 3 branş serisi).
Geçici bir koç açılır, demo öğrenci geçici olarak ona bağlanır, test sonunda geri alınır.
  1 Üst sekme şeridinde "Branş Denemeleri" YOK, menü tek satır
  2 Denemeler sekmesinde 3. kart → branş analizi açılır, URL #program-exams
  3 Bölümler: KPI · öne çıkanlar · ders karnesi · yan yana grafik · ısı · ritim · derin analiz
  4 Karnede satıra tıkla → derin analiz o derse geçer
  5 "Karne denemelerine dön" → karne görünümü
  6 #program-exams doğrudan açılış · koyu tema · 390px taşma yok · konsol temiz
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

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
DEMO_EMAIL = "ornek-haftalik@lgs.local"
COACH_EMAIL = "live_branch_coach@test.invalid"
PWD = "LiveBranch2026!x"
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


def setup():
    db = SessionLocal()
    st = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if st is None:
        raise SystemExit("Demo öğrenci yok: python -m scripts.seed_weekly_progress_demo")
    old = db.query(User).filter(User.email == COACH_EMAIL).first()
    if old:
        db.delete(old)
        db.commit()
    c = User(email=COACH_EMAIL, password_hash=hash_password(PWD), full_name="Canlı Branş Koç",
             role=UserRole.TEACHER, is_active=True, must_change_password=False)
    db.add(c)
    db.flush()
    orig = st.teacher_id
    st.teacher_id = c.id
    db.commit()
    out = (st.id, c.id, orig)
    db.close()
    return out


def teardown(sid, cid, orig):
    db = SessionLocal()
    st = db.get(User, sid)
    if st:
        st.teacher_id = orig
    # Önce bağı geri yazıp kaydet: koç silinirken ORM ilişkisi yüklü öğrencinin teacher_id'sini
    # NULL'lıyordu (demo öğrenci koçsuz kalıp listeden kayboldu).
    db.commit()
    db.expire_all()
    c = db.get(User, cid)
    if c:
        db.delete(c)
    db.commit()
    db.close()


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def main() -> int:
    sid, cid, orig = setup()
    print(f"\n=== canlı branş denemeleri — öğrenci #{sid} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            ctx = b.new_context(viewport={"width": 1440, "height": 950})
            page = ctx.new_page()
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[type="email"]', COACH_EMAIL)
            page.fill('input[type="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(3500)

            page.goto(f"{WEB}/teacher/students/{sid}#exams", wait_until="networkidle")
            page.wait_for_timeout(2500)
            dismiss(page)
            tabs = page.locator('[role="tab"][id^="tab-"]')
            names = [t.inner_text() for t in tabs.all()]
            check("1a üst şeritte 'Branş Denemeleri' sekmesi yok", not any("Branş" in n for n in names), names)
            tops = page.evaluate(
                "[...document.querySelectorAll('[role=tab][id^=tab-]')].map(e=>Math.round(e.getBoundingClientRect().top))"
            )
            check("1b sekme şeridi tek satır (1440px)", len(set(tops)) == 1, tops)

            entry = page.locator('[data-testid="branch-exams-entry"]')
            entry.wait_for(timeout=15000)
            page.wait_for_timeout(1200)
            check("2a 3. kart görünür + özet", "deneme" in entry.inner_text(), entry.inner_text())
            box_e = entry.bounding_box()
            box_p = page.locator("button", has_text="Deneme sonuç PDF").first.bounding_box()
            check("2b üç kart aynı satırda", box_e and box_p and abs(box_e["y"] - box_p["y"]) < 4, (box_e, box_p))
            page.screenshot(path=os.path.join(SHOTS, "branch_entry_cards.png"), clip={
                "x": 0, "y": max(0, (box_p or {"y": 0})["y"] - 120), "width": 1440, "height": 420})
            entry.click()
            page.wait_for_selector('[data-section="brans:report"]', timeout=15000)
            page.wait_for_timeout(1500)
            check("2c URL #program-exams", page.url.endswith("#program-exams"), page.url)
            sel = page.locator('[role="tab"][aria-selected="true"][id^="tab-"]').inner_text()
            check("2d şeritte Denemeler seçili", "Denemeler" in sel, sel)

            for sec in ("brans:kpis", "brans:highlights", "brans:report", "brans:compare", "brans:heat",
                        "brans:rhythm", "brans:detail"):
                check(f"3 bölüm {sec}", page.locator(f'[data-section="{sec}"]').count() == 1)
            rows = page.locator('[data-section="brans:report"] tbody tr')
            check("3b karnede 3 ders", rows.count() == 3, rows.count())
            page.screenshot(path=os.path.join(SHOTS, "branch_analysis_light.png"), full_page=True)

            # 4 satır → derin analiz
            target = rows.nth(1)
            name = target.locator("td").first.locator(".font-bold").first.inner_text().strip()
            target.click()
            page.wait_for_timeout(900)
            h = page.locator('[data-section="brans:detail"] h3').inner_text()
            check("4 satır tıklanınca derin analiz o derse geçer", name in h, (name, h))

            # 5 geri
            page.get_by_role("button", name="Karne denemelerine dön").click()
            page.wait_for_timeout(1500)
            check("5 karne görünümüne dönüldü", page.locator('[data-testid="branch-exams-entry"]').count() == 1
                  and page.url.endswith("#exams"), page.url)

            # 6 doğrudan açılış + koyu tema
            page.emulate_media(color_scheme="dark")
            page.goto(f"{WEB}/teacher/students/{sid}#program-exams", wait_until="networkidle")
            page.wait_for_selector('[data-section="brans:report"]', timeout=15000)
            page.wait_for_timeout(1500)
            check("6a #program-exams doğrudan açılır", True)
            page.screenshot(path=os.path.join(SHOTS, "branch_analysis_dark.png"), full_page=True)
            check("6b masaüstü yatay taşma yok", overflow(page) <= 1, overflow(page))

            m = ctx.new_page()
            m.set_viewport_size({"width": 390, "height": 860})
            m.goto(f"{WEB}/teacher/students/{sid}#program-exams", wait_until="networkidle")
            m.wait_for_selector('[data-section="brans:report"]', timeout=15000)
            m.wait_for_timeout(1500)
            check("6c 390px sayfa yatay taşmıyor", overflow(m) <= 1, overflow(m))
            m.screenshot(path=os.path.join(SHOTS, "branch_analysis_mobile.png"), full_page=True)
            bad = [e for e in errs if "favicon" not in e and "Hydration" not in e]
            check("6d konsol hatası yok", not bad, bad[:3])
            b.close()
    finally:
        teardown(sid, cid, orig)
    print(f"\n{passed} passed · {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
