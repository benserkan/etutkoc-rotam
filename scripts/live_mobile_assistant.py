"""Canlı test — mobil Rota asistanı (Expo web önizlemesi + gerçek backend/yapay zekâ).

Önkoşul: backend :8081 (CORS_ORIGINS'te http://localhost:8095) + Expo web :8095
(EXPO_PUBLIC_API_BASE=http://localhost:8081). Expo web'de kanal = android sayılır.
    python scripts/live_mobile_assistant.py
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8095"
SHOTS = pathlib.Path(".shots")
SHOTS.mkdir(exist_ok=True)
passed = 0
failed: list[str] = []
BANNED = ("iyzico", "kartla", "havale", "₺", "web sitesi")


def check(label, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {extra}")


def body(page) -> str:
    return page.inner_text("body")


def wait_reply(page, before: str, timeout=60000):
    page.wait_for_function(
        """(b) => { const t = document.body.innerText;
                     return t.length > b.length + 20 && !t.includes('Düşünüyor'); }""",
        arg=before, timeout=timeout)


with sync_playwright() as pw:
    br = pw.chromium.launch(channel="chrome")
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    page = ctx.new_page()

    # 1 — ziyaretçi: karşılama ekranından
    page.goto(f"{BASE}/welcome", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    link = page.get_by_text("Sorun mu var? Rota'ya sor")
    check("1a karşılama ekranında 'Rota'ya sor'", link.count() == 1)
    link.click()
    page.wait_for_timeout(5000)
    t = body(page)
    check("1b asistan açıldı + ziyaretçi karşılaması (fiyatsız)", "Rota" in t and "asistan" in t.lower()
          and not any(b in t.lower() for b in BANNED), t[:300])
    check("1c WhatsApp düğmesi", "WhatsApp" in t)
    before = body(page)
    page.get_by_text("Paketler nasıl işliyor?").click()
    wait_reply(page, before)
    t = body(page)
    check("1d uygulama paket cevabı: Paketim ekranı, fiyat/kart yok", "Paketim" in t
          and not any(b in t.lower() for b in BANNED), t[-400:])
    before = body(page)
    page.get_by_placeholder("Sorunu yaz").fill("Öğrencim nasıl kayıt olur?")
    page.keyboard.press("Enter")
    wait_reply(page, before)
    t = body(page)
    print("     yapay zekâ:", t[len(before):][:300].replace("\n", " "))
    check("1e yapay zekâ cevabı: öğrenciyi koç ekler", "kayıt" in t.lower() and ("koç" in t.lower() or "eklersin" in t.lower()), t[-300:])
    page.screenshot(path=str(SHOTS / "mobile_assistant_public.png"))
    page.get_by_text("Bir insanla görüşmek istiyorum").click()
    page.wait_for_timeout(1200)
    t = body(page)
    check("1f ekibe yaz formu: ad + telefon", "Adın" in t and "Cep telefonun" in t)
    page.screenshot(path=str(SHOTS / "mobile_assistant_handoff.png"))

    # 2 — öğrenci: sekme ekranındaki balon
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    check("2a giriş ekranında 'Rota'ya sor'", page.get_by_text("Yardım mı lazım? Rota'ya sor").count() == 1)
    inputs = page.locator("input")
    inputs.nth(0).fill("rehber-elif@etutkoc.demo")
    inputs.nth(1).fill("RehberDemo2026!")
    page.get_by_text("Giriş yap", exact=True).last.click()
    page.wait_for_timeout(8000)
    fab = page.get_by_label("Rota asistanını aç")
    check("2b öğrenci sekme ekranında balon", fab.count() >= 1, page.url)
    page.screenshot(path=str(SHOTS / "mobile_assistant_fab.png"))
    fab.first.click()
    page.wait_for_timeout(5000)
    t = body(page)
    check("2c öğrenci hazır soruları (görev işaretleme)", "işaret" in t.lower(), t[:300])
    before = body(page)
    page.get_by_placeholder("Sorunu yaz").fill("Yanlış yaptığım soruyu nasıl kaydederim?")
    page.keyboard.press("Enter")
    wait_reply(page, before)
    ans = body(page)[len(before):]
    print("     yapay zekâ:", ans[:300].replace("\n", " "))
    check("2d yapay zekâ cevabı Yanlışlarım'ı anlatıyor", "yanlış" in ans.lower(), ans[:200])
    page.screenshot(path=str(SHOTS / "mobile_assistant_student.png"))
    br.close()

print(f"\n=== {passed} passed, {len(failed)} failed ===")
sys.exit(0 if not failed else 1)
