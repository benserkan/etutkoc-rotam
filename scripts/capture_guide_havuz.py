"""Rehber — HAVUZ serisi + program modu girişi ekran yakalayıcı (gerçek panel).

Demo koç Aylin Demir · havuz öğrencileri Deniz Arslan (açık dönem) ve Ece Yıldız
(dönemi dün kapandı) · gün gün öğrencisi Mert (mod geçiş penceresi, yazmadan).
Ekranlar 1440×900, 2x. Kalem ekleme gibi yazan adımlar Deniz'in havuzunu değiştirir —
çekimden önce `python -m scripts.seed_guide_demo_havuz` koş.

  python -m scripts.capture_guide_havuz                 # tümü
  python -m scripts.capture_guide_havuz --only giris,izle
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import re
import json
import time

from playwright.sync_api import Page, sync_playwright

import scripts.capture_guide_shots as cgs
from scripts.capture_guide_kitaplar import hide_noise

IDS = cgs.IDS


def _uid(email: str) -> int:
    from app.database import SessionLocal
    from app.models import User

    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            raise SystemExit(f"{email} yok — önce seed_guide_demo_havuz")
        return u.id


DENIZ = _uid("rehber-deniz@etutkoc.demo")
ECE = _uid("rehber-ece@etutkoc.demo")
MERT = IDS["mert"]
ELIF = IDS["elif"]
POOL = f"/teacher/students/{DENIZ}/pool"


def go(page: Page, path: str, wait: str | None = None, settle: float = 2.5) -> None:
    page.goto(cgs.BASE + path, wait_until="domcontentloaded", timeout=120_000)
    if wait:
        page.get_by_text(wait, exact=False).first.wait_for(timeout=60_000)
    time.sleep(settle)
    hide_noise(page)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        time.sleep(0.6)


def sec(page: Page, name: str):
    return page.locator(f'[data-section="{name}"]').first


def center(loc) -> None:
    try:
        loc.evaluate("e => e.scrollIntoView({block: 'center'})")
        time.sleep(0.6)
    except Exception:  # noqa: BLE001
        pass


def top(loc, offset: int = 90) -> None:
    """Öğeyi görünümün üstüne yakın getir (yapışkan başlığın altında)."""
    try:
        loc.evaluate(f"e => window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - {offset})")
        time.sleep(0.6)
    except Exception:  # noqa: BLE001
        pass


def step(name: str):
    def deco(fn):
        def run(page: Page):
            print(f"\n== {name}")
            try:
                fn(page)
            except Exception as e:  # noqa: BLE001
                print(f"  !! {name} yarım kaldı: {type(e).__name__}: {str(e)[:300]}")
        return run
    return deco


# ---------------------------------------------------------------- prog-mod

@step("mod")
def shots_mod(page: Page) -> None:
    # Gün gün öğrencinin başlığı: "Haftalık Program"
    go(page, f"/teacher/students/{ELIF}", "Haftalık Program")
    cgs.snap(page, "hv-baslik-gungun", {
        "dugme": page.get_by_role("link", name="Haftalık Program").first,
        "islemler": page.get_by_role("button", name="İşlemler").first,
    })
    # Havuz öğrencisinin başlığı: "Haftalık Havuz"
    go(page, f"/teacher/students/{DENIZ}", "Haftalık Havuz")
    cgs.snap(page, "hv-baslik-havuz", {
        "dugme": page.get_by_role("link", name="Haftalık Havuz").first,
    })
    # İşlemler menüsü (gün gün öğrenci) — "Haftalık havuz modu" girişi
    go(page, f"/teacher/students/{ELIF}", "Haftalık Program")
    page.get_by_role("button", name="İşlemler").first.click()
    time.sleep(0.8)
    cgs.snap(page, "hv-islemler", {
        "menu": page.get_by_role("menu").first,
        "giris": page.get_by_role("menuitem", name="Haftalık havuz modu").first,
    })
    page.keyboard.press("Escape")
    # Mert'in havuz sayfası: mod kartı → geçiş penceresi (YAZMADAN)
    go(page, f"/teacher/students/{ELIF}/pool", "Havuz moduna geç")
    cgs.snap(page, "hv-mod-kart", {"kart": page.get_by_text("Havuz moduna geç").first.locator("xpath=ancestor::*[contains(@class,'rounded')][1]")})
    page.locator('[data-testid="mode-switch-open"]').first.click()
    time.sleep(2.5)
    dlg = page.locator('[data-testid="mode-switch-dialog"]').first
    cgs.snap(page, "hv-mod-pencere", {"pencere": dlg})


# ---------------------------------------------------------------- giriş

@step("giris")
def shots_giris(page: Page) -> None:
    # Ece: dönemi dün kapandı → "Dönem aç" + devir listesi
    go(page, f"/teacher/students/{ECE}/pool?mod=duzenle", "Dönem aç")
    box = sec(page, "pool:carry")
    top(page.locator('[data-testid="pool-open-period"]').first, 300)
    cgs.snap(page, "hv-donem-ac", {
        "devir": box,
        "ac": page.locator('[data-testid="pool-open-period"]').first,
    })
    # Deniz: dönem kartı (İzle)
    go(page, POOL, "Bu dönem")
    top(sec(page, "pool:period"), 80)
    cgs.snap(page, "hv-donem-kart", {
        "kart": sec(page, "pool:period"),
        "takvim": sec(page, "pool:period:timeline"),
        "olcu": sec(page, "pool:summary"),
        "gorunum": sec(page, "pool:view"),
    })


# ---------------------------------------------------------------- izle

@step("izle")
def shots_izle(page: Page) -> None:
    go(page, POOL, "Bu dönem")
    flags = sec(page, "pool:flags")
    t = page.locator('[data-testid="pool-flags-toggle"]').first
    try:
        page.get_by_role("button", name="Neden?").first.click()
        time.sleep(0.8)
    except Exception:  # noqa: BLE001
        pass
    top(flags, 90)
    cgs.snap(page, "hv-izle-uyari", {"uyari": flags, "kanit": sec(page, "pool:flag:evidence")})
    days = sec(page, "pool:days")
    top(days, 90)
    cgs.snap(page, "hv-izle-gunler", {"gunler": days})
    # bir güne dokun → ayrıntı
    try:
        days.get_by_text("Çar", exact=False).first.click()
        time.sleep(1.2)
    except Exception:  # noqa: BLE001
        pass
    top(days, 90)
    cgs.snap(page, "hv-izle-gun-detay", {"detay": sec(page, "pool:days:detail")})
    subs = sec(page, "pool:subjects")
    top(subs, 90)
    cgs.snap(page, "hv-izle-dersler", {"dersler": subs})
    pend = sec(page, "pool:watch:pending")
    top(pend, 120)
    cgs.snap(page, "hv-izle-onay", {"onay": pend, "acik": sec(page, "pool:watch:open")})
    go(page, "/teacher/appointments", "Bugünkü görüşme listesi")
    cgs.snap(page, "hv-gorusme-listesi", {"liste": sec(page, "pool:daily")})


# ---------------------------------------------------------------- kalem

@step("kalem")
def shots_kalem(page: Page) -> None:
    go(page, POOL + "?mod=duzenle", "Havuza kalem ekle")
    editor = sec(page, "pool:editor")
    top(page.get_by_text("Havuza kalem ekle").first, 90)
    cgs.snap(page, "hv-duzenle", {
        "ekle": page.get_by_text("Havuza kalem ekle").first.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-xl')][1]"),
        "liste": sec(page, "pool:list"),
    })
    # Hızlı yaz
    page.get_by_text("Hızlı yaz", exact=True).first.click()
    time.sleep(0.8)
    ta = page.get_by_placeholder("345 matematik üslü sayılar 4 test").first
    ta.fill("fizik hareket 3 test")
    page.get_by_role("button", name="Ayrıştır").first.click()
    time.sleep(3)
    cgs.snap(page, "hv-hizli", {"kutu": ta, "okunan": page.get_by_text("Okunan", exact=False).first.locator("xpath=ancestor::div[2]")})
    ta.fill("paragraf 4 test")
    page.get_by_role("button", name="Ayrıştır").first.click()
    time.sleep(3)
    cgs.snap(page, "hv-hizli-secenek", {
        "okunan": page.get_by_text("Okunan", exact=True).first.locator("xpath=ancestor::div[1]"),
        "ekle": page.get_by_role("button", name="Böyle ekle").first,
    })
    go(page, POOL + "?mod=duzenle", "Havuza kalem ekle")
    top(page.get_by_text("Havuza kalem ekle").first, 90)
    # Adım 1 — ders
    cgs.snap(page, "hv-kalem-ders", {
        "dersler": page.get_by_text("Sınav dersleri — TYT", exact=False).first.locator("xpath=ancestor::div[2]"),
        "mat": page.get_by_role("button", name="TYT Matematik").first,
    })
    page.get_by_role("button", name="TYT Matematik").first.click()
    time.sleep(2.5)
    books = sec(page, "pool:add:books")
    top(page.get_by_text("Nereden?").first, 90)
    cgs.snap(page, "hv-kalem-kitap", {"kitap": books})
    # kitabın bir bölümünü seç (Çarpanlara Ayırma)
    books.get_by_text("Çarpanlara Ayırma", exact=False).first.click()
    time.sleep(1.5)
    sub = page.locator('[data-testid="pool-add-submit"]').first
    top(page.get_by_text("Miktar").first, 90)
    cgs.snap(page, "hv-kalem-miktar-kitap", {
        "ozet": sec(page, "pool:add:book-summary"),
        "ekle": sub,
    })
    # Müfredat konusundan
    page.get_by_text("Değiştir", exact=True).nth(1).click()
    time.sleep(1.0)
    page.get_by_text("Müfredat konusundan (kaynaksız)", exact=False).first.click()
    time.sleep(2.5)
    topics = sec(page, "pool:add:topics")
    top(page.get_by_text("Nereden?").first, 90)
    cgs.snap(page, "hv-kalem-konu", {"konular": topics, "ara": page.get_by_label("Konu ara").first})
    page.get_by_label("Konu ara").first.fill("olas")
    time.sleep(1.2)
    topics.get_by_role("button").filter(has_text="Olasılık").first.click()
    time.sleep(1.5)
    try:
        page.get_by_text("gün etiketi · ders öğretmeni ödevi", exact=False).first.click()
        time.sleep(0.8)
    except Exception:  # noqa: BLE001
        pass
    top(page.get_by_text("Miktar").first, 90)
    cgs.snap(page, "hv-kalem-miktar", {
        "birim": page.get_by_label("Birim").first,
        "ekle": page.locator('[data-testid="pool-add-submit"]').first,
    })
    page.locator('[data-testid="pool-add-submit"]').first.click()
    time.sleep(2.5)
    lst = sec(page, "pool:list")
    top(lst, 90)
    cgs.snap(page, "hv-kalem-liste", {"liste": lst})
    miss = sec(page, "pool:missing")
    center(miss)
    cgs.snap(page, "hv-kalem-eksik", {"eksik": miss})
    prev = sec(page, "pool:preview")
    top(prev, 90)
    cgs.snap(page, "hv-onizleme", {"onizleme": prev})


# ---------------------------------------------------------------- şube

@step("sube")
def shots_sube(page: Page) -> None:
    go(page, POOL + "?mod=duzenle", "Havuza kalem ekle")
    cg = sec(page, "pool:class-group")
    top(cg, 90)
    cg.get_by_text("dershane ders programı", exact=False).first.click()
    time.sleep(1.2)
    top(cg, 90)
    cgs.snap(page, "hv-sube", {"tablo": page.get_by_label("Şube ders programı").first, "sube": cg})


# ---------------------------------------------------------------- seans

@step("seans")
def shots_seans(page: Page) -> None:
    go(page, POOL + "/session", "Seansı bitir")
    head = sec(page, "pool:session:headline")
    cgs.snap(page, "hv-seans-ust", {"ozet": head, "bitir": page.get_by_role("button", name="Seansı bitir").first})
    items = sec(page, "pool:session:items")
    top(items, 90)
    # bir kaleme "seansta" sayısı yaz (Fizik Hareket kalanı 3 → 1)
    try:
        row = items.get_by_text("Hareket", exact=True).first.locator("xpath=ancestor::li[1]")
        inp = row.locator("input").first
        inp.fill("1")
        inp.press("Enter")
        time.sleep(1.5)
    except Exception as e:  # noqa: BLE001
        print("   seansta işaret yazılamadı:", e)
    top(items, 90)
    cgs.snap(page, "hv-seans-kalem", {"kalemler": items})
    av = sec(page, "pool:session:avoided")
    center(av)
    cgs.snap(page, "hv-seans-kacinilan", {"kacinilan": av})
    # Seansı bitir penceresi (YAZMADAN)
    page.get_by_role("button", name="Seansı bitir").first.click()
    time.sleep(2)
    dlg = page.get_by_role("dialog").first
    cgs.snap(page, "hv-seans-bitir", {"pencere": dlg})
    try:
        dlg.get_by_text("Bu seansla gün gün programa geç", exact=False).first.click()
        time.sleep(1)
        cgs.snap(page, "hv-seans-gungune", {"gecis": dlg.locator("[data-section='pool:finish:switch']").first})
    except Exception as e:  # noqa: BLE001
        print("   gün güne geçiş kutusu:", e)
    page.keyboard.press("Escape")


# ---------------------------------------------------------------- dönem

@step("donem")
def shots_donem(page: Page) -> None:
    go(page, POOL + "?mod=duzenle", "Havuza kalem ekle")
    # Seanssız kapat penceresi (YAZMADAN)
    top(sec(page, "pool:period"), 80)
    page.get_by_role("button", name="Seanssız kapat…").first.click()
    time.sleep(1.5)
    cgs.snap(page, "hv-seanssiz", {"pencere": page.get_by_role("dialog").first})
    page.keyboard.press("Escape")
    time.sleep(0.8)
    hist = sec(page, "pool:history")
    top(hist, 90)
    cgs.snap(page, "hv-gecmis", {
        "gecmis": hist,
        "veli": page.locator('[data-testid="pool-parent-summary-open"]').first,
    })
    # Veli özeti penceresi
    try:
        page.locator('[data-testid="pool-parent-summary-open"]').first.click()
        time.sleep(2.5)
        cgs.snap(page, "hv-veli-ozet", {"pencere": sec(page, "pool:parent-summary"),
                                        "satirlar": sec(page, "pool:parent-summary:lines")})
        page.keyboard.press("Escape")
        time.sleep(0.8)
    except Exception as e:  # noqa: BLE001
        print("   veli özeti:", e)
    # Dönemi aç (geçmiş dönem penceresi)
    top(hist, 90)
    hist.get_by_role("button", name="Aç").first.click()
    time.sleep(2.5)
    dlg = page.get_by_role("dialog").first
    cgs.snap(page, "hv-donem-pencere", {"pencere": dlg})
    try:
        dlg.get_by_role("tab", name="Gün gün").first.click()
    except Exception:  # noqa: BLE001
        dlg.get_by_text("Gün gün", exact=True).first.click()
    time.sleep(1.5)
    cgs.snap(page, "hv-donem-pencere-gun", {"pencere": dlg})
    page.keyboard.press("Escape")


# ---------------------------------------------------------------- öğrenci

def student_login(page: Page) -> None:
    page.goto(cgs.BASE + "/login", wait_until="networkidle")
    time.sleep(2)
    page.locator('input[type="email"]').fill("rehber-deniz@etutkoc.demo")
    page.locator('input[type="password"]').fill("RehberDemo2026!")
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/student/**", timeout=120_000)
    time.sleep(2)


def student_dismiss_guide() -> None:
    from datetime import datetime, timezone

    from app.database import SessionLocal
    from app.models import UserGuideState

    with SessionLocal() as db:
        st = db.query(UserGuideState).filter_by(user_id=DENIZ, guide_key="student_onboarding").one_or_none()
        now = datetime.now(timezone.utc)
        if st is None:
            db.add(UserGuideState(user_id=DENIZ, guide_key="student_onboarding", status="dismissed", dismissed_at=now))
        else:
            st.status, st.dismissed_at = "dismissed", now
        db.commit()


@step("ogrenci")
def shots_ogrenci(page: Page) -> None:
    go(page, "/student/day", "Haftanın havuzu")
    banner = page.get_by_text("Haftanın havuzu", exact=False).first.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-xl')][1]")
    cgs.snap(page, "hv-ogr-bugun", {"kart": banner, "ac": page.get_by_role("link", name="Havuzu aç").first})
    go(page, "/student/pool", "Bugünün kabı")
    cgs.snap(page, "hv-ogr-havuzum", {
        "ozet": page.get_by_text(re.compile("haftan.n havuzu", re.I)).first.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-xl')][1]"),
        "kap": page.get_by_text("Bugünün kabı", exact=False).first.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-xl')][1]"),
    })
    lst = page.get_by_text("Havuzdaki kalemler", exact=False).first.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-xl')][1]")
    top(lst, 90)
    cgs.snap(page, "hv-ogr-liste", {"liste": lst})
    # Kaba al → sayı penceresi
    row = lst.get_by_text("Çarpanlara Ayırma", exact=False).first.locator("xpath=ancestor::li[1]")
    row.get_by_role("button", name="Kaba al").first.click()
    time.sleep(1.5)
    cgs.snap(page, "hv-ogr-kaba-al", {"pencere": page.get_by_role("dialog").first})
    page.get_by_role("dialog").first.get_by_role("button", name="2", exact=True).first.click()
    time.sleep(2.5)
    kap = page.get_by_text("Bugünün kabı", exact=False).first.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-xl')][1]")
    top(kap, 90)
    cgs.snap(page, "hv-ogr-kap", {"kap": kap})
    # Bugün sayfasında işaretle: görevin D/Y/B penceresi
    go(page, "/student/day", "Haftanın havuzu")
    card = page.get_by_text("Çarpanlara Ayırma", exact=False).first.locator("xpath=ancestor::article[1]")
    center(card)
    cgs.snap(page, "hv-ogr-gorev", {"gorev": card})
    # Kalem ekle penceresi
    go(page, "/student/pool", "Bugünün kabı")
    page.get_by_role("button", name="Kalem ekle").first.click()
    time.sleep(1.5)
    cgs.snap(page, "hv-ogr-kalem-ekle", {"pencere": page.get_by_role("dialog").first})
    page.keyboard.press("Escape")
    prj = page.get_by_text("Haftaya nasıl dağılır?", exact=False).first
    prj.click()
    time.sleep(1.2)
    top(prj, 90)
    cgs.snap(page, "hv-ogr-dagilim", {"dagilim": prj.locator("xpath=ancestor::*[contains(@class,'rounded-2xl') or contains(@class,'rounded-xl')][1]")})


@step("veli")
def shots_veli(page: Page) -> None:
    from datetime import datetime, timezone

    from app.database import SessionLocal
    from app.models import User, UserGuideState

    with SessionLocal() as db:
        v = db.query(User).filter(User.email == "rehber-veli-deniz@etutkoc.demo").one()
        st = db.query(UserGuideState).filter_by(user_id=v.id, guide_key="parent_onboarding").one_or_none()
        now = datetime.now(timezone.utc)
        if st is None:
            db.add(UserGuideState(user_id=v.id, guide_key="parent_onboarding", status="dismissed", dismissed_at=now))
        else:
            st.status, st.dismissed_at = "dismissed", now
        db.commit()
    page.goto(cgs.BASE + "/login", wait_until="networkidle")
    time.sleep(2)
    page.locator('input[type="email"]').fill("rehber-veli-deniz@etutkoc.demo")
    page.locator('input[type="password"]').fill("RehberDemo2026!")
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/parent**", timeout=120_000)
    time.sleep(2)
    go(page, f"/parent/students/{DENIZ}", "Haftalık görev havuzu")
    card = sec(page, "parent:pool")
    top(card, 90)
    cgs.snap(page, "hv-veli-kart", {"kart": card, "kap": sec(page, "parent:pool:cup")})


SECTIONS = {
    "mod": shots_mod,
    "giris": shots_giris,
    "izle": shots_izle,
    "sube": shots_sube,
    "seans": shots_seans,
    "donem": shots_donem,
    "kalem": shots_kalem,  # Deniz'in havuzuna yazar — sona yakın
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--student", action="store_true", help="yalnız öğrenci ekranları")
    args = ap.parse_args()
    only = [x for x in args.only.split(",") if x]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        if not args.student:
            ctx = browser.new_context(viewport={"width": cgs.VW, "height": cgs.VH}, device_scale_factor=2)
            page = ctx.new_page()
            cgs.ensure_guide_dismissed()
            cgs.login(page)
            for key, fn in SECTIONS.items():
                if only and key not in only:
                    continue
                fn(page)
            ctx.close()
        if not only or "veli" in only:
            ctx = browser.new_context(viewport={"width": cgs.VW, "height": cgs.VH}, device_scale_factor=2)
            page = ctx.new_page()
            shots_veli(page)
            ctx.close()
        if args.student or not only or "ogrenci" in only:
            student_dismiss_guide()
            ctx = browser.new_context(viewport={"width": cgs.VW, "height": cgs.VH}, device_scale_factor=2)
            page = ctx.new_page()
            student_login(page)
            shots_ogrenci(page)
            ctx.close()
        browser.close()
    data = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8")) if cgs.BOXES_PATH.exists() else {}
    data.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nKutular yazıldı: {len(cgs.boxes_out)} ekran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
