"""CANLI: kalemsiz (etkinlik) görev oluşturma + tamamlama (:3000).

Kullanıcı kararı (2026-05-24): video/özet/tekrar/diğer tiplerinde kalem ZORUNLU
değil; "test" yine en az bir kalem ister. Öğrenci görev-bazında tamamlar.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
import time
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole, AuditLog
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

B = "http://127.0.0.1:3000"
PFX = "itl_" + secrets.token_hex(3)
PWD = "Itemless!2345aB"
now = datetime.now(timezone.utc)
today = date.today().isoformat()
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1; print(f"  [PASS] {label}")
    else:
        failed.append(label); print(f"  [FAIL] {label}  ({detail})")


def login(email):
    get_login_limiter().reset()
    c = httpx.Client(base_url=B, timeout=40)
    for attempt in range(2):
        r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
        if r.status_code == 200:
            return c
        if r.status_code == 429 and attempt == 0:
            time.sleep(min(int(r.json().get("detail", {}).get("retry_after_seconds", 60)) + 1, 62)); continue
        raise RuntimeError(f"login {email}: {r.status_code} {r.text[:120]}")
    raise RuntimeError("rate limited")


def main() -> int:
    print(f"\n=== KALEMSİZ GÖREV — {PFX} ===\n")
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_c@t.invalid", password_hash=hash_password(PWD), full_name="Koc",
                     role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                     must_change_password=False, password_changed_at=now)
        db.add(coach); db.flush()
        cid = coach.id
        stu = User(email=f"{PFX}_s@t.invalid", password_hash=hash_password(PWD), full_name="Ogr",
                   role=UserRole.STUDENT, teacher_id=cid, institution_id=None, grade_level=8,
                   is_active=True, must_change_password=False, password_changed_at=now)
        db.add(stu); db.commit()
        sid = stu.id
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_([cid, sid]))); db.commit()

    task_id = None
    try:
        tc = login(f"{PFX}_c@t.invalid")
        # 1) "Diğer" kalemsiz → oluşur
        r = tc.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": today, "type": "other", "title": "Mebi Deneme 7",
            "notes": "Mebi Deneme 7", "is_draft": False, "items": []})
        chk("Diğer + kalemsiz → 200 (oluştu)", r.status_code == 200, f"{r.status_code} {r.text[:140]}")
        if r.status_code == 200:
            task_id = r.json()["data"]["id"]
        # 2) "video" kalemsiz → oluşur
        r = tc.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": today, "type": "video", "title": "Trigonometri videosu",
            "is_draft": False, "items": []})
        chk("Video + kalemsiz → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        # 3) "test" kalemsiz → hâlâ 422 no_items
        r = tc.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": today, "type": "test", "title": "Boş test", "is_draft": False, "items": []})
        code = (r.json().get("detail", {}) or {}).get("code") if r.status_code == 422 else None
        chk("Test + kalemsiz → 422 no_items (kalem hâlâ şart)", r.status_code == 422 and code == "no_items", f"{r.status_code} {code}")

        # 4) Kitapsız DENEME görevi (soru sayılı) — type other + bookless item
        r = tc.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": today, "type": "other", "title": "LGS Tam Deneme 7", "is_draft": False,
            "items": [{"book_id": None, "section_id": None, "label": "LGS Tam Deneme 7", "planned_count": 90}]})
        deneme_id = None
        ok4 = r.status_code == 200
        chk("Deneme (kitapsız, 90 soru) → 200", ok4, f"{r.status_code} {r.text[:140]}")
        if ok4:
            d = r.json()["data"]
            deneme_id = d["id"]
            items = d.get("items", [])
            chk("deneme kalemi planned=90 + label görünüyor",
                len(items) == 1 and items[0]["planned_count"] == 90 and items[0]["book_name"] == "LGS Tam Deneme 7",
                str(items))

        # 4b) HAFTA endpoint'i kitapsız kalemde ÇÖKMEMELİ (compute_day_subject_summary)
        rw = tc.get(f"/api/v2/teacher/students/{sid}/week")
        chk("hafta görünümü deneme/kalemsizle 200 (eski 500 fix)", rw.status_code == 200, f"{rw.status_code} {rw.text[:140]}")

        # 5) Öğrenci kalemsiz görevi tamamlar (görev-bazında)
        if task_id:
            sc = login(f"{PFX}_s@t.invalid")
            r = sc.post(f"/api/v2/student/tasks/{task_id}/complete")
            chk("Öğrenci kalemsiz görevi tamamladı → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
            if r.status_code == 200:
                st = (r.json().get("data") or {}).get("status")
                chk("görev status COMPLETED", str(st).lower() == "completed", str(st))

        # 6) Öğrenci denemeyi tamamlar → 90 soru hacme sayar (completed=90)
        if deneme_id:
            sc2 = login(f"{PFX}_s@t.invalid")
            r = sc2.post(f"/api/v2/student/tasks/{deneme_id}/complete")
            ok6 = r.status_code == 200
            chk("Öğrenci denemeyi tamamladı → 200", ok6, f"{r.status_code} {r.text[:120]}")
            if ok6:
                items = (r.json().get("data") or {}).get("items", [])
                comp = items[0]["completed"] if items else None
                chk("deneme completed=90 (çözülen soruya sayar)", comp == 90, str(comp))
    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            from app.models import Task
            sids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_s%")).all()]
            if sids:
                db.execute(sa_delete(Task).where(Task.student_id.in_(sids)))
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"]))); db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
