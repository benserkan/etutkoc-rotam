"""Yanlışlarım — web uçtan uca test (gerçek tarayıcı, :3000 → :8081).

Kapsam (kullanıcı isteği: 'backend'den son kullanıcıya kapsamlı test'):
  1. Öğrenci girişi (rehber-elif demo)
  2. Fotoğraflı yanlış ekleme (gerçek dosya yükleme, multipart)
  3. Kartta fotoğrafın GERÇEKTEN çizildiği (naturalWidth > 0 — 0×0 tuzağı)
  4. Detay → 'Çözdüm' → seri 1 + vade İLERİ gider (ilk gerçek tekrar)
  5. AYNI GÜN ikinci 'Çözdüm' → seri ŞİŞMEZ + vade/stabilite DEĞİŞMEZ
     (FSRS aynı-gün koruması — canlı HTTP üzerinden kanıt)
  6. 'Yine yanlış' → seri sıfırlanır + vade ÖNE gelir (kural dışılık kanıtı)
  7. Koç girişi → öğrenci detayı 'Yanlışlar' sekmesi kaydı görür
  8. Temizlik: öğrenci kaydı siler
"""
from __future__ import annotations

import base64
import json
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3000"
STUDENT = ("rehber-elif@etutkoc.demo", "RehberDemo2026!")
COACH = ("rehber-koc@etutkoc.demo", "RehberDemo2026!")

# 40×40 kırmızı PNG (geçerli, görüntülenebilir)
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAACgAAAAoCAYAAACM/rhtAAAAOElEQVR4nO3NMQEAIAzAsIF/"
    "z0MGHpJKyJ2d2c/MOQsAAAAAAAAAAAAAAAAAAAAAAAAAAADgOxtGKAJHOnHrXAAAAABJRU5E"
    "rkJggg=="
)

PASS = 0
FAIL = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK] {label}")
    else:
        FAIL += 1
        print(f"  [HATA] {label}" + (f" -> {detail}" if detail else ""))


def login(page, email: str, pw: str) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', pw)
    page.click('button[type="submit"]')
    page.wait_for_url(re.compile(r"/(student|teacher)"), timeout=30000)


def api(page, method: str, path: str, body: dict | None = None) -> dict:
    """Tarayıcı oturumuyla (cookie) BFF üzerinden istek — gerçek kullanıcı kanalı."""
    script = """async ([method, path, body]) => {
        const res = await fetch(path, {
            method,
            headers: body ? { "content-type": "application/json" } : {},
            body: body ? JSON.stringify(body) : undefined,
            credentials: "include",
        });
        let data = null;
        try { data = await res.json(); } catch {}
        return { status: res.status, data };
    }"""
    return page.evaluate(script, [method, path, body])


def find_item(page, wq_id: int) -> dict | None:
    r = api(page, "GET", "/api/v2/student/wrong-questions")
    for it in r["data"]["items"]:
        if it["id"] == wq_id:
            return it
    return None


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="tr-TR")
        page = ctx.new_page()

        print("\n1) Öğrenci girişi + sayfa açılışı")
        login(page, *STUDENT)
        page.goto(f"{BASE}/student/wrong-questions", wait_until="networkidle")
        check("Yanlışlarım sayfası açıldı", page.get_by_text("Yanlış ekle").first.is_visible())

        print("\n2) Fotoğraflı yanlış ekleme (gerçek yükleme)")
        before = api(page, "GET", "/api/v2/student/wrong-questions")["data"]
        n_before = len(before["items"])
        page.get_by_role("button", name=re.compile("Yanlış ekle")).click()
        page.get_by_text("Yanlış soru ekle").wait_for(timeout=8000)
        page.set_input_files(
            '[role="dialog"] input[type="file"]',
            {"name": "e2e-soru.png", "mimeType": "image/png", "buffer": PNG},
        )
        page.get_by_text("1 fotoğraf seçildi", exact=False).wait_for(timeout=5000)
        dlg = page.locator('[role="dialog"]')
        dlg.get_by_role("button", name=re.compile("Arşive ekle", re.I)).click()
        page.wait_for_timeout(2500)
        after = api(page, "GET", "/api/v2/student/wrong-questions")["data"]
        check("kayıt oluştu", len(after["items"]) == n_before + 1,
              f"{n_before} -> {len(after['items'])}")
        new = max(after["items"], key=lambda x: x["id"])
        wq_id = new["id"]
        print(f"   yeni kayıt id={wq_id}")
        check("fotoğraf kayıtta (kind=question)",
              any(im["kind"] == "question" for im in new["images"]),
              json.dumps(new["images"]))
        check("yeni yanlış HEMEN çözülebilir (is_due)", bool(new["is_due"]))

        print("\n3) Kartta fotoğraf GERÇEKTEN çiziliyor (0×0 tuzağı)")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(1500)
        dims = page.evaluate(
            """() => [...document.querySelectorAll('img')]
                .filter(i => i.src.includes('/wrong-questions/'))
                .map(i => ({w: i.naturalWidth, cw: i.clientWidth, ch: i.clientHeight}))"""
        )
        check("en az bir soru fotoğrafı yüklendi", len(dims) > 0, str(dims))
        check("fotoğraf görünür boyutta (client > 0)",
              any(d["w"] > 0 and d["cw"] > 0 and d["ch"] > 0 for d in dims), str(dims))

        print("\n4) İlk 'Çözdüm' — seri 1, vade ileri")
        r1 = api(page, "POST", f"/api/v2/student/wrong-questions/{wq_id}/attempt",
                 {"rating": 3})
        check("attempt 200", r1["status"] == 200, str(r1))
        it1 = find_item(page, wq_id)
        check("seri 1/2", it1["correct_streak"] == 1, str(it1["correct_streak"]))
        check("hâlâ açık (kapanış aralık ister)", it1["status"] == "acik")
        due1 = it1["due_at"]
        check("vade ileri atıldı (artık due değil)", not it1["is_due"], f"due_at={due1}")

        print("\n5) Aynı gün ikinci 'Çözdüm' — koruma: seri + vade değişmez")
        r2 = api(page, "POST", f"/api/v2/student/wrong-questions/{wq_id}/attempt",
                 {"rating": 3})
        check("attempt 200", r2["status"] == 200)
        it2 = find_item(page, wq_id)
        check("seri ŞİŞMEDİ (1/2 kaldı)", it2["correct_streak"] == 1,
              str(it2["correct_streak"]))
        check("VADE DEĞİŞMEDİ (aynı-gün koruması)", it2["due_at"] == due1,
              f"{due1} -> {it2['due_at']}")
        check("kapanmadı", it2["status"] == "acik")

        print("\n6) 'Yine yanlış' — kural dışı: seri sıfır, vade öne gelir")
        r3 = api(page, "POST", f"/api/v2/student/wrong-questions/{wq_id}/attempt",
                 {"rating": 1})
        check("attempt 200", r3["status"] == 200)
        it3 = find_item(page, wq_id)
        check("seri sıfırlandı", it3["correct_streak"] == 0, str(it3["correct_streak"]))
        check("vade ÖNE geldi", it3["due_at"] < due1, f"{due1} -> {it3['due_at']}")

        print("\n7) Koç tarafı — Yanlışlar sekmesi kaydı görüyor")
        coach_page = ctx.new_page()
        # Ayrı context: koç oturumu öğrenci cookie'sini ezmesin
        cctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="tr-TR")
        coach_page = cctx.new_page()
        login(coach_page, *COACH)
        rr = coach_page.evaluate(
            """async (sid) => {
                const res = await fetch(`/api/v2/teacher/students/${sid}/wrong-questions`,
                    { credentials: "include" });
                return { status: res.status, data: await res.json() };
            }""",
            228,
        )
        check("koç listesi 200", rr["status"] == 200, str(rr["status"]))
        check("koç yeni kaydı görüyor",
              any(it["id"] == wq_id for it in rr["data"]["items"]))

        print("\n8) Temizlik — öğrenci kaydı siler")
        rd = api(page, "POST", f"/api/v2/student/wrong-questions/{wq_id}/delete") \
            if False else api(page, "DELETE", f"/api/v2/student/wrong-questions/{wq_id}")
        check("silme 200", rd["status"] == 200, str(rd))
        check("listeden düştü", find_item(page, wq_id) is None)

        browser.close()

    print("\n" + "=" * 60)
    print(f"SONUC: {PASS} gecti, {FAIL} kaldi")
    print("=" * 60)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
