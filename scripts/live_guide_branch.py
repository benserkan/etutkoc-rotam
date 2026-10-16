"""Canlı — dallanan Rota Rehberi (gün gün / havuz), 2026-10-16.

  1 koç rehberi: Program'da giriş bölümü + iki yol başlığı
  2 giriş bölümünün sonu: "Programı nasıl kuracaksın?" seçim kartı (2 seçenek)
  3 "Haftalık havuz" → havuz-giris açılır, gün gün yolu katlanır ("Öbür yol" düğmesi)
  4 sunucu: current_chapter = havuz-giris
  5 "Öbür yol" düğmesi gün gün bölümlerini geri gösterir
  6 havuz sayfasında "Nasıl kullanılır" kartı Havuz bölümünü açar
  7 öğrenci: havuz öğrencisi (Deniz) "Havuzum" bölümünü görür, gün gün öğrenci (Elif) görmez
  8 koyu tema: seçim kartı okunur
Ön koşul: :8081 + :3000, seed_guide_demo + seed_guide_demo_havuz.
"""
from __future__ import annotations

import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import User, UserGuideState  # noqa: E402

WEB = "http://127.0.0.1:3000"
PWD = "RehberDemo2026!"
passed, failed = 0, []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def reset_state(email: str, key: str) -> int:
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).one()
        db.query(UserGuideState).filter_by(user_id=u.id, guide_key=key).delete()
        db.add(UserGuideState(user_id=u.id, guide_key=key, status="in_progress"))
        db.commit()
        return u.id


def server_current(uid: int, key: str) -> str | None:
    with SessionLocal() as db:
        st = db.query(UserGuideState).filter_by(user_id=uid, guide_key=key).one_or_none()
        return st.current_chapter if st else None


def login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    time.sleep(2)
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_url(lambda u: "/login" not in u, timeout=120_000)
    time.sleep(2)


def main() -> int:
    from playwright.sync_api import sync_playwright

    from scripts.lib_live_contrast import measure

    coach_id = reset_state("rehber-koc@etutkoc.demo", "coach_onboarding")
    print("\n=== canlı: dallanan rehber ===\n")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        page = b.new_page(viewport={"width": 1440, "height": 950})
        login(page, "rehber-koc@etutkoc.demo")
        page.goto(f"{WEB}/teacher/guide?bolum=prog-mod", wait_until="networkidle")
        time.sleep(3)
        rail = page.locator("aside").filter(has_text="Bölümler").last
        txt = rail.inner_text()
        check("1 giriş bölümü + iki yol başlığı", "Program modunu seç" in txt
              and "Yol: Gün gün program" in txt and "Yol: Haftalık havuz" in txt, txt[:300])
        # son adıma atla → bitince bölüm sonu
        page.get_by_role("button", name="Bölümü başlat").first.click()
        time.sleep(1)
        dots = page.locator("button[aria-label^='Adım ']")
        dots.nth(dots.count() - 1).click()
        page.get_by_text("Bölümü tamamla ve devam et", exact=False).first.wait_for(timeout=90_000)
        page.get_by_text("Bölümü tamamla ve devam et", exact=False).first.click()
        time.sleep(2)
        card = page.locator("[data-section='guide-branch-choice']")
        check("2 seçim kartı: soru + iki seçenek",
              card.count() == 1 and "Programı nasıl kuracaksın?" in card.inner_text()
              and card.locator("[data-branch]").count() == 2, card.inner_text()[:200] if card.count() else "yok")
        page.screenshot(path=".shots/guide_branch_choice.png")
        card.locator("[data-branch='havuz']").click()
        time.sleep(3)
        txt = page.locator("aside").filter(has_text="Bölümler").last.inner_text()
        title = page.locator("text=Bölüm").first.inner_text() if page.locator("text=Bölüm").count() else ""
        check("3 havuz yolu açık, gün gün katlı",
              "Havuz nedir" in txt and "Gün kartında görev ekle" not in txt
              and page.locator("[data-section='guide-other-branch']").count() == 1, txt[:400])
        time.sleep(1.5)
        check("4 sunucu: current_chapter = havuz-giris", server_current(coach_id, "coach_onboarding") == "havuz-giris",
              str(server_current(coach_id, "coach_onboarding")))
        page.locator("[data-section='guide-other-branch']").click()
        time.sleep(1)
        txt = page.locator("aside").filter(has_text="Bölümler").last.inner_text()
        check("5 'Öbür yol' gün gün bölümlerini gösterir", "Gün kartında görev ekle" in txt and "öbür yol" in txt)
        page.screenshot(path=".shots/guide_branch_rail.png")

        # 6 havuz sayfasındaki rehber kartı
        with SessionLocal() as db:
            deniz = db.query(User).filter(User.email == "rehber-deniz@etutkoc.demo").one().id
        page.goto(f"{WEB}/teacher/students/{deniz}/pool", wait_until="networkidle")
        time.sleep(3)
        hint = page.locator("[data-section='guide-hint']").first
        href = hint.get_attribute("href") if hint.count() else ""
        if not href and hint.count():
            href = hint.locator("a").first.get_attribute("href")
        check("6 havuz sayfası: rehber kartı Havuz bölümüne gider", bool(href) and "havuz-" in (href or ""), str(href))

        # 8 koyu tema
        dpage = b.new_page(viewport={"width": 1440, "height": 950}, color_scheme="dark")
        dpage.context.add_cookies(page.context.cookies())
        reset_state("rehber-koc@etutkoc.demo", "coach_onboarding")
        dpage.goto(f"{WEB}/teacher/guide?bolum=prog-mod", wait_until="networkidle")
        time.sleep(3)
        dpage.get_by_role("button", name="Bölümü başlat").first.click()
        time.sleep(1)
        dd = dpage.locator("button[aria-label^='Adım ']")
        dd.nth(dd.count() - 1).click()
        dpage.get_by_text("Bölümü tamamla ve devam et", exact=False).first.wait_for(timeout=90_000)
        dpage.get_by_text("Bölümü tamamla ve devam et", exact=False).first.click()
        time.sleep(2)
        res = measure(dpage, "[data-section='guide-branch-choice']", 4.5)
        check("8 koyu tema: seçim kartı okunur (4,5)", res["bad"] == 0, str(res["worst"])[:200])
        dpage.screenshot(path=".shots/guide_branch_choice_dark.png")
        b.close()

        # 7 öğrenci: havuz öğrencisi görür, gün gün öğrenci görmez
        b = p.chromium.launch(channel="chrome", headless=True)
        for email, expect in (("rehber-deniz@etutkoc.demo", True), ("rehber-elif@etutkoc.demo", False)):
            sp = b.new_page(viewport={"width": 1440, "height": 950})
            login(sp, email)
            sp.goto(f"{WEB}/student/guide", wait_until="networkidle")
            time.sleep(3)
            later = sp.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                time.sleep(1)
            has = "Havuzum" in sp.locator("aside").filter(has_text="Bölümler").last.inner_text()
            check(f"7 öğrenci {email.split('@')[0]}: Havuzum bölümü {'var' if expect else 'yok'}", has == expect)
            sp.close()
        b.close()

    reset_state("rehber-koc@etutkoc.demo", "coach_onboarding")
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
