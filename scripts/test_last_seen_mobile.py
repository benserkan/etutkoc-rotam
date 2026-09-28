"""Son görülme (last_seen_at) — mobil Bearer isteği "giriş yok" uyarısını düşürür
(2026-09-28, Emir #113 vakası).

Mobil uygulama 30 günlük oturumla açık kaldığından last_login_at bayatlıyordu;
öğrenci her gün görev işaretlese de risk panosu "5+ gündür giriş yok" diyordu.
"""
from __future__ import annotations

import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.services.jwt_auth import issue_access_token
from app.services.risk_analysis import compute_risk_score
from app.services.security import hash_password

PFX = f"lsm_{secrets.token_hex(3)}"
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


def codes(db, uid):
    u = db.get(User, uid)
    return {i.code for i in compute_risk_score(db, student=u).indicators}


def main() -> int:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("x"),
                     full_name="LS Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x"),
                   full_name="LS Öğrenci", role=UserRole.STUDENT, teacher_id=coach.id,
                   grade_level=12, is_active=True, created_at=now - timedelta(days=40),
                   last_login_at=now - timedelta(days=12), last_seen_at=now - timedelta(days=12))
        db.add(stu)
        db.commit()
        sid, cid = stu.id, coach.id
    try:
        with SessionLocal() as db:
            chk("1 bayat son görülme → no_login_5d", "no_login_5d" in codes(db, sid))
            u = db.get(User, sid)
            chk("2 hybrid SQL ifadesi sorgulanabilir",
                db.query(User).filter(User.id == sid,
                                      User.last_active_at < now - timedelta(days=5)).count() == 1)
            token = issue_access_token(u)
        c = TestClient(app)
        r = c.get("/api/v2/student/day", headers={"Authorization": f"Bearer {token}"})
        chk("3 mobil Bearer isteği 200", r.status_code == 200, str(r.status_code))
        with SessionLocal() as db:
            u = db.get(User, sid)
            ls = u.last_seen_at if u.last_seen_at.tzinfo else u.last_seen_at.replace(tzinfo=timezone.utc)
            chk("4 last_seen_at güncellendi", (now - ls).total_seconds() < 120, str(ls))
            ll = u.last_login_at if u.last_login_at.tzinfo else u.last_login_at.replace(tzinfo=timezone.utc)
            chk("5 last_login_at DEĞİŞMEDİ (güvenlik alanı)", (now - ll).days >= 11)
            chk("6 no_login_5d düştü", "no_login_5d" not in codes(db, sid))
            first = u.last_seen_at
        c.get("/api/v2/student/day", headers={"Authorization": f"Bearer {token}"})
        with SessionLocal() as db:
            chk("7 10 dk throttle: ikinci istek yazmaz", db.get(User, sid).last_seen_at == first)
        # Sahte oturum (impersonation) son görülmeyi güncellemez
        with SessionLocal() as db:
            db.query(User).filter(User.id == sid).update(
                {User.last_seen_at: now - timedelta(days=9)}, synchronize_session=False)
            db.commit()
            imp = issue_access_token(db.get(User, sid), imp_by=cid)
        c.get("/api/v2/student/day", headers={"Authorization": f"Bearer {imp}"})
        with SessionLocal() as db:
            ls = db.get(User, sid).last_seen_at
            ls = ls if ls.tzinfo else ls.replace(tzinfo=timezone.utc)
            chk("8 impersonation son görülmeyi değiştirmez", (now - ls).days >= 8, str(ls))
    finally:
        with SessionLocal() as db:
            db.query(User).filter(User.id.in_([sid, cid])).delete(synchronize_session=False)
            db.commit()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
