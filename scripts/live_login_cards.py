"""Toplu kayıt sonrası giriş kartları — canlı tarayıcı testi (2026-09-28).

CSV ile 3 öğrenci yüklenir → sonuç ekranında "Giriş kartlarını yazdır" +
"Excel'e indir" doğrulanır (kart sayısı, şifreler, QR, CSV içeriği, kırpma yok).
Kendi verisini kurar/temizler. Dev sunucular (:3000 + :8081) açık olmalı.
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import AuditLog, User, UserRole
from app.services.security import hash_password

BASE = "http://localhost:3000"
PFX = f"llc_{secrets.token_hex(3)}"
PWD = "LiveLoginCard!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


STUDENTS = [
    ("Güneş Deridüzen", f"{PFX}_1@test.invalid", "10", "", "", "10-A"),
    ("Gamze Elif Seda Tarı Uzunsoyadlıoğlu", f"{PFX}_2@test.invalid", "11", "ea", "", "11-B"),
    ("Ecem Gümrükçüoğlu", f"{PFX}_3@test.invalid", "mezun", "dil", "dershane", ""),
]


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Kart Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_unlimited", subscription_status="active")
        db.add(coach)
        db.commit()
        return {"coach": coach.id, "email": coach.email}


def cleanup(d):
    with SessionLocal() as db:
        ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}_%")).all()]
        db.execute(sa_delete(AuditLog).where(AuditLog.target_id.in_(ids), AuditLog.target_type == "user"))
        db.execute(sa_delete(User).where(User.id.in_(ids), User.role == UserRole.STUDENT))
        db.execute(sa_delete(User).where(User.id == d["coach"]))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    csv = "ad soyad,e-posta,sınıf,alan,çalışma şekli,şube\n" + "\n".join(",".join(r) for r in STUDENTS) + "\n"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1300, "height": 950}, accept_downloads=True)
            pg = ctx.new_page()
            dialogs: list[str] = []
            pg.on("dialog", lambda dl: (dialogs.append(dl.message), dl.dismiss()))
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/students/import", wait_until="networkidle")
            pg.fill("#csv-text", csv)
            pg.get_by_role("button", name="Önizleme").click()
            pg.get_by_role("button", name="3 öğrenciyi onayla ve oluştur").click(timeout=30000)
            pg.get_by_test_id("login-cards-print").wait_for(timeout=30000)
            chk("1 sonuç ekranında yazdır + indir düğmeleri", pg.get_by_test_id("login-cards-csv").is_visible())

            pws = pg.locator("li span.font-mono").all_inner_texts()
            chk("2 üç geçici şifre, hepsi farklı", len(pws) == 3 and len(set(pws)) == 3, str(pws))

            # --- Excel (CSV) ---
            with pg.expect_download() as dl_info:
                pg.get_by_test_id("login-cards-csv").click()
            dl = dl_info.value
            raw = open(dl.path(), "rb").read()
            text = raw.decode("utf-8-sig")
            lines = text.strip().split("\r\n")
            chk("3 CSV BOM'lu (Excel Türkçe karakteri doğru açar)", raw.startswith(b"\xef\xbb\xbf"))
            chk("4 CSV başlık + 3 satır, ; ayraçlı", len(lines) == 4 and lines[0].startswith("Ad Soyad;Sınıf;Şube"), lines[0])
            chk("5 CSV'de her şifre ve e-posta var", all(p in text for p in pws) and all(s[1] in text for s in STUDENTS))
            chk("6 CSV mezun satırı 'Mezun' (emoji yok)", "Ecem Gümrükçüoğlu;Mezun;" in text, text)
            chk("7 dosya adı", dl.suggested_filename.startswith("ogrenci-giris-bilgileri-"), dl.suggested_filename)

            # --- Yazdırma ---
            pg.evaluate("window.__printCalls = 0")
            pg.get_by_test_id("login-cards-print").click()
            pg.wait_for_function("document.querySelectorAll('iframe').length > 0", timeout=5000)
            pg.wait_for_timeout(800)
            html = pg.evaluate("(() => { const f=[...document.querySelectorAll('iframe')].pop(); return f.contentDocument.documentElement.outerHTML; })()")
            chk("8 yazdırma çıktısında 3 kart", html.count('class="card"') == 3)
            chk("9 kartlarda tüm şifreler", all(p in html for p in pws))
            chk("10 kartlarda QR (svg) var", html.count("<svg") == 3)
            chk("11 kartta giriş adresi", "rotam.etutkoc.com" in html)
            chk("12 şube + sınıf satırı", "11. sınıf · 11-B" in html and "10. sınıf · 10-A" in html)

            # Kart çıktısını ayrı sayfada render edip ölç + görüntü al
            pp = ctx.new_page()
            pp.set_viewport_size({"width": 794, "height": 1123})  # A4 @96dpi
            pp.set_content(html)
            pp.emulate_media(media="print")
            over = pp.evaluate("""() => [...document.querySelectorAll('.card')].map(c => ({
                over: c.scrollHeight > c.clientHeight + 1,
                pwOver: [...c.querySelectorAll('.pw,.name,.val')].some(e => e.scrollWidth > e.clientWidth + 1)
            }))""")
            chk("13 kart içeriği kart kutusundan taşmıyor", not any(o["over"] for o in over), str(over))
            chk("14 şifre/ad/e-posta kırpılmıyor", not any(o["pwOver"] for o in over), str(over))
            pp.screenshot(path=os.path.join(SHOT_DIR, "login_cards.png"), full_page=True)
            pp.pdf(path=os.path.join(SHOT_DIR, "login_cards.pdf"), format="A4")

            # --- Ayrılma uyarısı ---
            pg.get_by_role("button", name="Yeni içe aktarma").click()
            pg.wait_for_timeout(500)
            chk("15 ayrılırken uyarı çıkar", any("bir daha gösterilemez" in m for m in dialogs), str(dialogs))
            chk("16 uyarı reddedilince şifreler ekranda kalır", pg.get_by_test_id("login-cards-print").is_visible())
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
