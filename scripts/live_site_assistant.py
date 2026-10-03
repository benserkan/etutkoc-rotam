"""Canlı test — Rota site asistanı (gerçek tarayıcı + gerçek yapay zekâ) 2026-10-03.

Önkoşul: dev backend (:8081, Gemini erişimli) + Next (:3000).
    python scripts/live_site_assistant.py [taban_url]
Ekran görüntüleri: .shots/assistant_*.png
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
SHOTS = pathlib.Path(".shots")
SHOTS.mkdir(exist_ok=True)
passed = 0
failed: list[str] = []


def check(label, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {extra}")


def overflow(page) -> list[str]:
    return page.evaluate("""() => {
      const d = document.querySelector('[role=dialog][aria-label="Rota asistanı"]');
      if (!d) return ['dialog yok'];
      const out = [];
      if (document.documentElement.scrollWidth > window.innerWidth + 1) out.push('yatay kaydırma');
      d.querySelectorAll('*').forEach(el => {
        const cs = getComputedStyle(el);
        if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) out.push('kırpık: ' + el.textContent.slice(0, 40));
      });
      return out;
    }""")


def last_answer(page) -> str:
    return page.evaluate("""() => {
      const d = document.querySelector('[role=dialog][aria-label="Rota asistanı"]');
      const ps = [...d.querySelectorAll('p.rounded-bl-md')];
      return ps.length ? ps[ps.length - 1].textContent : '';
    }""")


def wait_answer(page, before: int, timeout=60000):
    page.wait_for_function(
        """(n) => {
          const d = document.querySelector('[role=dialog][aria-label="Rota asistanı"]');
          return d && d.querySelectorAll('p.rounded-bl-md').length > n
            && !d.textContent.includes('Düşünüyor');
        }""", arg=before, timeout=timeout)


def n_answers(page) -> int:
    return page.evaluate("""() => document.querySelectorAll('[role=dialog][aria-label="Rota asistanı"] p.rounded-bl-md').length""")


with sync_playwright() as pw:
    br = pw.chromium.launch(channel="chrome")
    # --- 1. Ziyaretçi, fiyat sayfası, telefon genişliği
    ctx = br.new_context(viewport={"width": 390, "height": 844})
    # Ana sayfadaki tanıtım videosu penceresi bu testin konusu değil
    ctx.add_init_script("try{localStorage.setItem('rotam_tour_video_v1','1')}catch(e){}")
    page = ctx.new_page()
    page.goto(f"{BASE}/pricing", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    fab = page.get_by_role("button", name="Rota asistanını aç")
    check("1a ziyaretçi fiyat sayfasında 'Rota'ya sor' balonu", fab.count() == 1)
    fab.click()
    page.wait_for_selector('[role=dialog][aria-label="Rota asistanı"]')
    page.wait_for_function("""() => document.querySelector('[role=dialog][aria-label="Rota asistanı"]').textContent.includes('Paket seçmene')""", timeout=20000)
    check("1b fiyat sayfası karşılaması paket seçimine yönelik", True)
    wa = page.locator('[role=dialog] a[aria-label="WhatsApp\'tan yaz"]').get_attribute("href") or ""
    check("1c WhatsApp bağlantısı numarayla", "wa.me/90" in wa and "5056738561" in wa, wa)
    n0 = n_answers(page)
    page.get_by_role("button", name="Hangi paket bana uygun?").click()
    wait_answer(page, n0)
    check("1d hazır soru anında cevaplandı", "öğrenci" in last_answer(page), last_answer(page)[:120])
    n1 = n_answers(page)
    page.get_by_label("Asistana soru").fill("18 öğrencim var, akademik yıl alırsam toplam ne öderim?")
    page.get_by_role("button", name="Soruyu gönder").click()
    wait_answer(page, n1)
    ans = last_answer(page)
    print("     yapay zekâ:", ans[:300])
    check("1e yapay zekâ cevabı: Rota paketi + akademik yıl tutarı", "Rota" in ans and ("40.000" in ans or "4.000" in ans), ans[:200])
    check("1f taşma/kırpma yok (390px)", not overflow(page), str(overflow(page)))
    page.screenshot(path=str(SHOTS / "assistant_public_mobile.png"))
    page.get_by_role("button", name="Bir insanla görüşmek istiyorum").click()
    page.wait_for_timeout(1500)
    check("1g ekibe yaz formu: ad + telefon alanları", page.get_by_label("Adın").count() == 1 and page.get_by_label("Cep telefonun").count() == 1)
    page.screenshot(path=str(SHOTS / "assistant_public_handoff.png"))
    # sayfa değişince konuşma korunur
    page.get_by_role("button", name="Asistanı kapat").click()
    page.goto(f"{BASE}/", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    page.get_by_role("button", name="Rota asistanını aç").click()
    page.wait_for_timeout(2500)
    check("1h sayfa geçişinde konuşma korunur", "18 öğrencim var" in page.locator('[role=dialog]').inner_text())
    ctx.close()

    # --- 2. Koç (demo), masaüstü, koyu tema
    ctx = br.new_context(viewport={"width": 1366, "height": 860}, color_scheme="dark")
    page = ctx.new_page()
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.fill('input[type=email]', "rehber-koc@etutkoc.demo")
    page.fill('input[type=password]', "RehberDemo2026!")
    page.click('button[type=submit]')
    page.wait_for_url("**/teacher/**", timeout=30000)
    page.goto(f"{BASE}/teacher/library", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    page.get_by_role("button", name="Rota asistanını aç").click()
    page.wait_for_selector('[role=dialog][aria-label="Rota asistanı"]')
    page.wait_for_timeout(2500)
    txt = page.locator('[role=dialog]').inner_text()
    check("2a koç kütüphanesinde kitap ekleme hazır sorusu", "kitap eklerim" in txt, txt[:200])
    n0 = n_answers(page)
    page.get_by_label("Asistana soru").fill("Öğrencinin daha önce çözdüğü testleri nasıl düşerim, programda tekrar çıkmasın")
    page.get_by_role("button", name="Soruyu gönder").click()
    wait_answer(page, n0)
    ans = last_answer(page)
    print("     yapay zekâ:", ans[:300])
    check("2b koç yapay zekâ cevabı 'çözülmüş test' yolunu anlatıyor", "çöz" in ans.lower() and "kitap" in ans.lower(), ans[:200])
    check("2c taşma/kırpma yok (masaüstü)", not overflow(page), str(overflow(page)))
    page.screenshot(path=str(SHOTS / "assistant_teacher_dark.png"))
    page.goto(f"{BASE}/teacher/plan", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    check("2d Paketim sayfasında ikinci balon yok (tek asistan)",
          page.get_by_role("button", name="Rota asistanını aç").count() == 1
          and page.get_by_role("button", name="Paket asistanını aç").count() == 0)
    ctx.close()
    br.close()

print(f"\n=== {passed} passed, {len(failed)} failed ===")
sys.exit(0 if not failed else 1)
