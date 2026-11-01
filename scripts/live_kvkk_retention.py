"""Canlı tarayıcı testi — KVKK silme talebi + 3 aylık saklama süresi arayüzü.

Önkoşul: dev backend :8081 + next :3000. Test verisini kendisi kurar ve siler.
  python scripts/live_kvkk_retention.py <shots_dir>
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import AuditLog, DataSubjectRequest, ParentStudentLink, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402

BASE = "http://localhost:3000"
PW = "UiTest2026!@xyz"
PFX = f"kvui{secrets.token_hex(2)}"
SHOTS = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(SHOTS, exist_ok=True)
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def em(n):
    return f"{PFX}_{n}@test.invalid"


def seed():
    with SessionLocal() as db:
        def mk(role, n, name, **kw):
            u = User(email=em(n), password_hash=hash_password(PW), full_name=name, role=role,
                     is_active=True, **kw)
            db.add(u); db.flush(); return u
        koc = mk(UserRole.TEACHER, "koc", "KV Koç", plan="solo_pro")
        aktif = mk(UserRole.STUDENT, "aktif", "Aktif Öğrenci", grade_level=8, teacher_id=koc.id)
        pasif = mk(UserRole.STUDENT, "pasif", "Pasif Öğrenci", grade_level=8, teacher_id=koc.id)
        veli = mk(UserRole.PARENT, "veli", "KV Veli")
        admin = mk(UserRole.SUPER_ADMIN, "admin", "KV Admin")
        db.add(ParentStudentLink(parent_id=veli.id, student_id=aktif.id))
        db.commit()
        pasif.is_active = False
        db.commit()
        pasif.deactivated_at = datetime.now(timezone.utc) - timedelta(days=80)
        db.commit()
        return dict(koc=koc.id, aktif=aktif.id, pasif=pasif.id, veli=veli.id, admin=admin.id)


def cleanup(ids):
    with SessionLocal() as db:
        uids = list(ids.values())
        db.query(DataSubjectRequest).filter(DataSubjectRequest.target_user_id.in_(uids)).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.actor_id.in_(uids)).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.target_id.in_(uids), AuditLog.target_type == "user").delete(synchronize_session=False)
        db.query(ParentStudentLink).filter(ParentStudentLink.student_id.in_(uids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
        db.commit()


def login(page, n):
    page.context.clear_cookies()
    page.goto(f"{BASE}/login")
    page.fill('input[type="email"]', em(n))
    page.fill('input[type="password"]', PW)
    page.click('button[type="submit"]')
    page.wait_for_timeout(4000)
    for name in ("Daha sonra", "Kapat"):
        b = page.get_by_role("button", name=name, exact=True)
        if b.count() and b.first.is_visible():
            b.first.click()
            page.wait_for_timeout(300)


def row(page, name):
    return page.locator("li, tr, div.rounded-lg").filter(has_text=name).last


ids = seed()
try:
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome")
        page = br.new_page(viewport={"width": 1440, "height": 1000})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # -------- KOÇ: pasif öğrenci + saklama süresi --------
        login(page, "koc")
        page.goto(f"{BASE}/teacher/students?status=pasif")
        page.wait_for_timeout(3500)
        body = page.locator("main").inner_text()
        check("K1. pasif öğrencide '3 ay sonra silinecek' satırı",
              "Pasif Öğrenci" in body and "koçluk bittikten 3 ay sonra" in body, body[:300])
        page.screenshot(path=os.path.join(SHOTS, "kvkk_list_retention.png"), full_page=True)

        page.get_by_role("button", name="Öğrenci eylemleri").first.click()
        page.get_by_role("menuitem", name="Verilerini sil (KVKK)").click()
        page.wait_for_timeout(500)
        check("K2. silme penceresi açıldı (30 gün açıklaması)",
              page.get_by_text("30 gün sonra").count() > 0)
        page.screenshot(path=os.path.join(SHOTS, "kvkk_delete_dialog.png"))
        page.get_by_role("button", name="Silme talebini aç").click()
        page.wait_for_timeout(2500)
        body = page.locator("main").inner_text()
        # Bu öğrencinin 3 ay sayacı (80. gün) 30 günlük talepten erken doluyor →
        # satır en yakın tarihi gösterir + açık talebi ayrıca belirtir.
        check("K3. satırda en yakın silme tarihi + 'silme talebi de açık'",
              "silme talebi de açık" in body, body[:300])

        page.get_by_role("button", name="Öğrenci eylemleri").first.click()
        page.get_by_role("menuitem", name="Silme talebini iptal et").click()
        page.wait_for_timeout(2500)
        body = page.locator("main").inner_text()
        check("K4. iptal sonrası yeniden saklama süresi satırı",
              "silme talebi de açık" not in body and "3 ay sonra" in body)

        # -------- KOÇ: aktif öğrenci sonlandırma penceresi --------
        page.goto(f"{BASE}/teacher/students?status=aktif")
        page.wait_for_timeout(3500)
        page.get_by_role("button", name="Öğrenci eylemleri").first.click()
        page.get_by_role("menuitem", name="Koçluğu sonlandır").click()
        page.wait_for_timeout(500)
        dlg = page.get_by_role("dialog").inner_text()
        check("K5. sonlandırma penceresi 3 ay + otomatik silme + 14 gün hatırlatmayı söylüyor",
              "3 ay korunur" in dlg and "otomatik silinir" in dlg and "14 gün" in dlg, dlg[:300])
        check("K6. 'Verileri 3 ay beklemeden sil' seçeneği var",
              page.get_by_text("Verileri 3 ay beklemeden sil").count() == 1)
        page.screenshot(path=os.path.join(SHOTS, "kvkk_end_dialog.png"))
        page.keyboard.press("Escape")

        # -------- VELİ --------
        login(page, "veli")
        page.goto(f"{BASE}/parent/settings")
        page.wait_for_timeout(3500)
        check("V1. veli ayarlarında silme kartı", page.get_by_text("Çocuğumun verilerinin silinmesi").count() == 1)
        page.get_by_role("button", name="Verilerin silinmesini iste").click()
        page.wait_for_timeout(400)
        page.get_by_role("button", name="Silme talebini gönder").click()
        page.wait_for_timeout(2500)
        txt = page.locator("main").inner_text()
        check("V2. talep sonrası silinme tarihi görünüyor", "Silme talebi var" in txt, txt[-300:])
        page.screenshot(path=os.path.join(SHOTS, "kvkk_parent.png"), full_page=True)
        page.get_by_role("button", name="Talebi iptal et").click()
        page.wait_for_timeout(2500)
        check("V3. veli talebi iptal etti",
              page.get_by_role("button", name="Verilerin silinmesini iste").count() == 1)

        # -------- SÜPER ADMİN --------
        login(page, "admin")
        page.goto(f"{BASE}/admin/users/{ids['pasif']}")
        page.wait_for_timeout(4000)
        check("A1. admin kullanıcı sayfasında KVKK kartı", page.get_by_text("KVKK silme talebi").count() >= 1)
        page.get_by_label("Gerekçe").fill("Veli e-postayla istedi")
        page.get_by_text("30 gün beklemeden hemen uygula").click()
        page.get_by_role("button", name="Silme talebi aç").click()
        page.get_by_role("button", name="Eminim, şimdi sil").click()
        page.wait_for_timeout(3000)
        with SessionLocal() as db:
            u = db.get(User, ids["pasif"])
            check("A2. 'hemen uygula' ile öğrenci anonimleştirildi",
                  u.email.startswith("anonymized-") and u.full_name == "(Silinen Kullanıcı)")

        page.set_viewport_size({"width": 390, "height": 844})
        login(page, "veli")
        page.goto(f"{BASE}/parent/settings")
        page.wait_for_timeout(3000)
        sw = page.evaluate("document.documentElement.scrollWidth")
        check("Z1. veli ayarları 390px'te taşmıyor", sw <= 391, str(sw))
        real = [e for e in errors if "favicon" not in e and "DevTools" not in e]
        check("Z2. konsolda hata yok", not real, " | ".join(real[:3]))
        br.close()
finally:
    cleanup(ids)

print(f"\n{passed} passed, {len(failed)} failed")
for f in failed:
    print("  -", f)
sys.exit(0 if not failed else 1)
