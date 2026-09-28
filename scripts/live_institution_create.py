"""Yeni kurum penceresi (yönetici hesabı + logo) — canlı tarayıcı testi (2026-09-28).

Süper admin → Kurumlar → Yeni Kurum: ad + Dershane Pro + kurum sorumlusu +
logo → oluştur → sonuç ekranında geçici şifre → yönetici ile giriş (zorunlu
şifre değişimi) → kurum panelinde logo gerçek oranında görünür.
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
from app.models import AuditLog, Institution, User, UserRole
from app.services.security import hash_password

BASE = "http://localhost:3000"
PFX = f"lic_{secrets.token_hex(3)}"
PWD = "LiveInstCreate!2345"
NEW_PWD = "YeniGuclu!Sifre2026x"
LOGO = sys.argv[1] if len(sys.argv) > 1 else ""
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


def seed() -> dict:
    with SessionLocal() as db:
        sa = User(email=f"{PFX}_sa@test.invalid", password_hash=hash_password(PWD),
                  full_name="Test Süper", role=UserRole.SUPER_ADMIN, is_active=True)
        dup = User(email=f"{PFX}_dup@test.invalid", password_hash=hash_password(PWD),
                   full_name="Var Olan", role=UserRole.TEACHER, is_active=True)
        db.add_all([sa, dup])
        db.commit()
        return {"sa": sa.id, "dup": dup.id, "email": sa.email}


def cleanup(d):
    with SessionLocal() as db:
        insts = [i.id for i in db.query(Institution).filter(Institution.name.like(f"{PFX}%")).all()]
        uids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}_%")).all()]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id.in_(insts)))
        db.commit()


def login(pg, email, pwd):
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', email)
    pg.fill('input[type="password"]', pwd)
    pg.click('button[type="submit"]')
    pg.wait_for_timeout(4000)


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    inst_name = f"{PFX} Açı Seçkin Kurs"
    admin_email = f"{PFX}_admin@test.invalid"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1300, "height": 950})
            pg = ctx.new_page()
            login(pg, d["email"], PWD)
            pg.goto(f"{BASE}/admin/institutions", wait_until="networkidle")

            # 1) Çakışan e-posta → 409, kurum AÇILMAZ
            pg.get_by_role("button", name="Yeni Kurum").click()
            dlg = pg.get_by_role("dialog")
            dlg.locator("#name").fill(inst_name + " Dup")
            dlg.locator("#admin_name").fill("Var Olan Kişi")
            dlg.locator("#contact_email").fill(f"{PFX}_dup@test.invalid")
            dlg.get_by_role("button", name="Oluştur").click()
            pg.wait_for_timeout(2500)
            with SessionLocal() as db:
                n = db.query(Institution).filter(Institution.name == inst_name + " Dup").count()
            chk("1 e-posta çakışmasında kurum yarım açılmaz", n == 0 and dlg.locator("#name").count() == 1)

            # 2) Tam akış
            dlg.locator("#name").fill(inst_name)
            dlg.locator("#plan").select_option("dershane_pro")
            dlg.locator("#admin_name").fill("Fatih Tütüncü")
            dlg.locator("#contact_email").fill(admin_email)
            dlg.get_by_label("Giriş bilgilerini yöneticiye e-postayla gönder").uncheck()
            if LOGO:
                dlg.get_by_test_id("logo-input").set_input_files(LOGO)
                pg.wait_for_timeout(400)
                chk("2 logo önizlemesi", dlg.get_by_test_id("logo-preview").locator("img").count() == 1)
            pg.screenshot(path=os.path.join(SHOT_DIR, "institution_create_form.png"))
            dlg.get_by_role("button", name="Oluştur").click()
            dlg.get_by_test_id("institution-created").wait_for(timeout=20000)
            temp = dlg.get_by_test_id("admin-temp-password").inner_text().strip()
            chk("3 sonuç ekranında geçici şifre", len(temp) >= 10, temp)
            pg.screenshot(path=os.path.join(SHOT_DIR, "institution_create_done.png"))

            with SessionLocal() as db:
                inst = db.query(Institution).filter(Institution.name == inst_name).one()
                adm = db.query(User).filter(User.email == admin_email).one()
                chk("4 kurum Dershane Pro + iletişim e-postası", inst.plan == "dershane_pro"
                    and inst.contact_email == admin_email, f"{inst.plan} {inst.contact_email}")
                chk("5 yönetici: rol + kurum + ilk girişte şifre değişimi", adm.role == UserRole.INSTITUTION_ADMIN
                    and adm.institution_id == inst.id and adm.must_change_password and adm.full_name == "Fatih Tütüncü")
                if LOGO:
                    chk("6 logo kaydedildi", inst.logo_content_type == "image/png")
            ctx.close()

            # 3) Yönetici girişi → şifre değişimi → panelde logo
            ctx2 = b.new_context(viewport={"width": 1300, "height": 950})
            p2 = ctx2.new_page()
            login(p2, admin_email, temp)
            chk("7 ilk girişte şifre değiştirme sayfası", "/password/change" in p2.url, p2.url)
            pws = p2.locator('input[type="password"]')
            for i in range(pws.count()):
                pws.nth(i).fill(temp if i == 0 and pws.count() == 3 else NEW_PWD)
            p2.locator('button[type="submit"]').click()
            p2.wait_for_timeout(4500)
            chk("8 kurum paneline iner", "/institution" in p2.url, p2.url)
            if LOGO:
                brand = p2.get_by_test_id("institution-brand").first
                img = brand.locator("img")
                dims = img.evaluate("e => ({w: e.getBoundingClientRect().width, h: e.getBoundingClientRect().height, nat: e.naturalWidth})")
                chk("9 logo gerçek oranında (geniş, yüklenmiş)", dims["nat"] > 0 and dims["w"] > dims["h"] * 2.5, str(dims))
                chk("10 kurum adı kırpılmadan görünür", "Açı Seçkin Kurs" in brand.inner_text())
            p2.screenshot(path=os.path.join(SHOT_DIR, "institution_panel_logo.png"))
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
