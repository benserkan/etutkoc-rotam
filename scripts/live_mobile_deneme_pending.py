"""Canlı MOBİL (Expo web 390px) — sonucu girilmemiş denemeler kartı (D3, 2026-10-20).

  1 Bugün: deneme görevi "deneme" birimiyle; dokununca görev sayfası deneme bölümüyle açılır
  2 2 satır (Çözdüm/Çözmedim) · D/Y girince boş etiketi + net
  3 1. satır 5D 1Y, 2. satır "Çözmedim" → Kaydet → DB
Önkoşul: backend :8081 (CORS'ta http://localhost:8095) + Expo web :8095.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Subject, Task, TaskBookItem, Track, User, UserRole  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

BASE = "http://localhost:8095"
PFX = f"lmp_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed():
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Mobil Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL)
        db.add(st); db.flush()
        mat = Subject(name="TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(mat); db.commit()
        d = {"coach": coach.id, "st": st.id, "mat": mat.id}
    get_login_limiter().reset()
    c = TestClient(app)
    assert c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD}).status_code == 200
    r = c.post(f"/api/v2/teacher/students/{d['st']}/deneme-tasks",
               json={"date": date.today().isoformat(), "kind": "brans", "subject_id": d["mat"], "count": 2,
                     "question_count": 20, "name": "Özel ders matematik", "is_draft": False})
    assert r.status_code == 200, r.text
    d["task"] = r.json()["data"]["id"]
    d["items"] = sorted(x["id"] for x in r.json()["data"]["items"])
    get_login_limiter().reset()
    s = TestClient(app)
    assert s.post("/api/v2/auth/login", json={"email": f"{PFX}_s@test.invalid", "password": PWD}).status_code == 200
    assert s.post(f"/api/v2/student/tasks/{d['task']}/deneme-results",
                  json={"rows": [{"item_id": i, "solved": True} for i in d["items"]]}).status_code == 200
    get_login_limiter().reset()
    return d


def cleanup(d):
    with SessionLocal() as db:
        u = [d["coach"], d["st"]]
        from app.models import ExamResult as _ER  # D3 köprü kayıtları
        db.execute(sa_delete(_ER).where(_ER.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == d["coach"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright
    from app.models import ExamResult

    d = seed()
    print(f"=== canlı mobil: sonucu girilmemiş denemeler — {PFX} ===")
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
            page.wait_for_timeout(8000)
            body = page.inner_text("body")
            check("1a Bugün'de kart", "Sonucu girilmemiş 2 deneme" in body, body[:400])
            check("1b numaralı satırlar", "1. deneme" in body and "2. deneme" in body)
            page.get_by_text("Sonucu gir", exact=True).first.click(force=True)
            page.wait_for_timeout(1500)
            ins = page.locator("input")
            n = ins.count()
            ins.nth(n - 4).fill("14")
            ins.nth(n - 3).fill("4")
            page.wait_for_timeout(400)
            body = page.inner_text("body")
            check("2a boş 2 · net 13", "Boş 2" in body and "Net 13" in body, body[-300:])
            os.makedirs(SHOTS, exist_ok=True)
            page.screenshot(path=os.path.join(SHOTS, "mobile_deneme_pending.png"))
            page.get_by_text("Kaydet", exact=True).last.click(force=True)
            page.wait_for_timeout(4000)
            with SessionLocal() as db:
                rr = [(r.task_book_item_id, r.net) for r in db.query(ExamResult).filter(ExamResult.student_id == d["st"]).all()]
            check("2b DB: Denemeler kaydı (net 13)", rr == [(d["items"][0], 13.0)], str(rr))
            body = page.inner_text("body")
            check("2c kart 1 denemeye indi", "Sonucu girilmemiş 1 deneme" in body, body[:300])
            br.close()
    finally:
        with SessionLocal() as db:
            from app.models import ExamResult as _ER
            db.execute(sa_delete(_ER).where(_ER.student_id.in_([d["coach"], d["st"]])))
            db.commit()
        cleanup(d)
    print(f"{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
