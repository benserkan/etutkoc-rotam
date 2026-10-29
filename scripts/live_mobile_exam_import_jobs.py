"""Canlı mobil (Expo web :8095): arka planda okunan karne için uygulamanın
üstündeki kalıcı kutu + önizleme (2026-10-29).

Önkoşul: backend :8081 (CORS'ta http://localhost:8095) + Expo web :8095.
Okuma taklit edilir (gerçek yapay zekâ yok); iş, öğrencinin kendi yüklemesi
olarak sunucuda "okundu" durumuna getirilir, sonra öğrenci uygulamaya girer.
"""
from __future__ import annotations

import copy
import os
import secrets
import sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import CreditAccount, UsageEvent, User, UserRole
from app.models.ai_job import AiJob
from app.services import ai_exam_import, push_notifications
from app.services import exam_import_jobs as jobs
from app.services import exam_import_service as svc
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from scripts.test_api_v2_exam_import import build_tyt_read

BASE = "http://localhost:8095"
PFX = f"lmj{secrets.token_hex(3)}"
PWD = "MobileJobs!2026X"
SHOTS = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed, failed = 0, []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label} {str(detail)[:200]}")


def seed() -> dict:
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Mobil Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", subscription_status="active",
                     must_change_password=False, ai_capture_consent_at=now)
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Mobil Öğrenci", role=UserRole.STUDENT, is_active=True,
                  grade_level=12, must_change_password=False)
        db.add_all([coach, st])
        db.flush()
        st.teacher_id = coach.id
        db.commit()
        d = {"coach": coach.id, "st": st.id}

    orig = (ai_exam_import.read_exam_pdf_double, svc.gemini.generate, push_notifications.safe_push)
    r1 = ai_exam_import._normalize_read(copy.deepcopy(build_tyt_read()))
    ai_exam_import.read_exam_pdf_double = lambda b64: (copy.deepcopy(r1), copy.deepcopy(r1))
    svc.gemini.generate = lambda *a, **k: '{"mappings": []}'
    push_notifications.safe_push = lambda *a, **k: None
    jobs.RUN_INLINE = True
    try:
        get_login_limiter().reset()
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": f"{PFX}_s@test.invalid", "password": PWD}).status_code == 200
        pdf = b"%PDF-1.4 mobile " + secrets.token_bytes(24)
        r = c.post("/api/v2/student/exams/import-jobs",
                   files={"file": ("karne.pdf", pdf, "application/pdf")})
        assert r.status_code == 202, r.text
        d["job"] = r.json()["id"]
    finally:
        ai_exam_import.read_exam_pdf_double, svc.gemini.generate, push_notifications.safe_push = orig
        jobs.RUN_INLINE = False
    get_login_limiter().reset()
    return d


def cleanup(d):
    with SessionLocal() as db:
        u = [d["coach"], d["st"]]
        db.execute(sa_delete(AiJob).where(AiJob.owner_id.in_(u)))
        db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id.in_(u)))
        db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(u),
                                                  CreditAccount.owner_type == "user"))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = seed()
    print(f"=== canlı mobil: arka plan karne okuma — {PFX} ===")
    with SessionLocal() as db:
        check("0 iş sunucuda 'okundu'", db.get(AiJob, d["job"]).status == "done")
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            page = br.new_context(viewport={"width": 390, "height": 844}).new_page()
            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            inputs = page.locator("input")
            inputs.nth(0).fill(f"{PFX}_s@test.invalid")
            inputs.nth(1).fill(PWD)
            page.get_by_text("Giriş yap", exact=True).last.click()
            page.wait_for_timeout(9000)
            body = page.inner_text("body")
            check("1 uygulamanın üstünde 'Karne okundu' kutusu", "Karne okundu" in body, body[:300])
            check("1b kendi yüklemesinde 'Deneme karnen' dili", "Deneme karnen hazır" in body)
            os.makedirs(SHOTS, exist_ok=True)
            page.screenshot(path=os.path.join(SHOTS, "mobile_job_banner.png"))
            page.get_by_text("Önizle ve kaydet", exact=True).first.click(force=True)
            page.wait_for_timeout(5000)
            body = page.inner_text("body")
            check("2 önizleme açıldı (PDF yeniden seçilmeden)", "Kaydet" in body or "kaydet" in body, body[-400:])
            page.screenshot(path=os.path.join(SHOTS, "mobile_job_preview.png"))
            with SessionLocal() as db:
                check("3 iş 'görüldü' işaretlendi", db.get(AiJob, d["job"]).acknowledged_at is not None)
            br.close()
    finally:
        cleanup(d)
    print(f"{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
