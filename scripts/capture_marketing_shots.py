"""Tanıtım sayfaları için 2x (retina) ürün ekranları — gerçek panelden.

Yerel dev sunucuları (:8081 + :3000) açıkken çalışır; demo hesaplarla girip
belirli panelleri öğe öğe (data-section) ya da tam sayfa yakalar. Çıktı ham PNG
(scratch klasörüne); kırpma + webp dönüştürme ayrı adımda yapılır.

  python -m scripts.capture_marketing_shots OUT_DIR [--only ad1,ad2]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:3000"

ACCOUNTS = {
    "coach": ("ogretmen@lgs.local", "ogretmen123"),
    "inst": ("kuzey-etut-merkezi-yonetici@etutkoc.demo", "RotamDemo2026!"),
    "student": ("ornek-haftalik@lgs.local", "OrnekHafta2026!"),
    "coach2": ("kuzey-etut-merkezi-koc1@etutkoc.demo", "RotamDemo2026!"),
    "parent": ("kuzey-etut-merkezi-veli.sevgi.ates@etutkoc.demo", "RotamDemo2026!"),
}

# (ad, hesap, yol, seçici | None=tam sayfa, ön-tıklama metni | None)
TARGETS = [
    ("deneme-dbg", "coach", "/teacher/students/452#exams", None, None),
    ("haftalik-ilerleme", "coach", "/teacher/students/459", '[data-section="student:weekly-progress"]', None),
    ("hafta-plan", "coach", "/teacher/students/459/week?program_id=45", None, None),
    ("deneme-genel", "coach", "/teacher/students/452#exams", None, "Genel Bakış"),
    ("deneme-konu", "coach", "/teacher/students/452#exams", None, "Konu Analizi"),
    ("deneme-net", "coach", "/teacher/students/452#exams", None, "Net Gelişimi"),
    ("deneme-puan", "coach", "/teacher/students/452#exams", None, "Puan Tahmini"),
    ("mufredat", "coach", "/teacher/students/459#curriculum", '[data-section="curriculum-panel"]', None),
    ("pano-uyari", "coach", "/teacher/dashboard", None, None),
    ("brans", "coach", "/teacher/students/459#program-exams", '[data-section="program-exams"]', None),
    ("kurum-pano", "inst", "/institution", None, None),
    ("kurum-uyum", "inst", "/institution/compliance", None, None),
    ("kurum-karne", "inst", "/institution/teacher-scorecard", None, None),
    ("ogrenci-bugun", "student", "/student/day", None, None),
    ("ogrenci-gelisim", "student", "/student/progress", None, None),
    ("veli-pano", "parent", "/parent", None, None),
    ("veli-cocuk", "parent", "/parent/students/477", None, None),
    ("koc-seans", "coach2", "/teacher/students/477#sessions", None, None),
    ("koc2-pano", "coach2", "/teacher/dashboard", None, None),
    ("koc-tahsilat", "coach2", "/teacher/billing", None, None),
    ("koc-gorusme", "coach2", "/teacher/appointments", None, None),
    ("koc-gelisim-477", "coach2", "/teacher/students/477", '[data-section="student:weekly-progress"]', None),
    ("kurum-akademik", "inst", "/institution/academic", None, None),
    ("kurum-risk", "inst", "/institution/at-risk", None, None),
    ("kurum-mudahale", "inst", "/institution/action-center", None, None),
]


def login(page, who: str):
    """Form hidrasyon yarışına takılmamak için API ile giriş (çerezler bağlamda kalır)."""
    email, pwd = ACCOUNTS[who]
    r = page.context.request.post(BASE + "/api/v2/auth/login", data={"email": email, "password": pwd})
    if not r.ok:
        raise RuntimeError(f"giriş başarısız {who}: {r.status}")
    time.sleep(0.5)


def dismiss(page):
    for label in ("Daha sonra", "Kapat", "Şimdi değil"):
        try:
            b = page.get_by_role("button", name=label, exact=True)
            if b.count() and b.first.is_visible():
                b.first.click()
                time.sleep(0.5)
        except Exception:
            pass
    page.keyboard.press("Escape")


HIDE_CSS = """
nextjs-portal, [data-nextjs-toast], .tsqd-open-btn-container, .tsqd-parent-container,
[data-section="guide-hint"], [data-sonner-toaster], [data-floating], .fixed.right-4, .fixed.bottom-4, .fixed.bottom-6, .fixed.bottom-5 { display: none !important; }
"""


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctxs: dict[str, object] = {}
        for name, who, path, sel, pre in TARGETS:
            if only and name not in only:
                continue
            if who not in ctxs:
                ctx = browser.new_context(
                    viewport={"width": 1280, "height": 860}, device_scale_factor=2,
                    locale="tr-TR", color_scheme="light",
                )
                pg = ctx.new_page()
                login(pg, who)
                ctxs[who] = pg
            page = ctxs[who]
            try:
                page.goto(BASE + path, wait_until="domcontentloaded", timeout=120_000)
                time.sleep(8)
                page.add_style_tag(content=HIDE_CSS)
                dismiss(page)
                if pre:
                    page.get_by_text(pre, exact=True).first.click()
                    time.sleep(3)
                if sel:
                    loc = page.locator(sel).first
                    loc.wait_for(timeout=30_000)
                    loc.scroll_into_view_if_needed()
                    time.sleep(1.5)
                    loc.screenshot(path=str(out / f"{name}.png"))
                else:
                    page.screenshot(path=str(out / f"{name}.png"), full_page=True)
                print("OK", name)
            except Exception as e:  # noqa: BLE001
                print("FAIL", name, str(e)[:200])
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
