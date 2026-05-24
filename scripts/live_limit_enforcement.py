"""CANLI limit/duvar testi — solo + kurum aşma senaryoları (:3000 → :8081).

Her plan için: limit kadar kayıt seed edilir, sonra API'den +1 oluşturma DENENİR;
beklenen → ENGELLENİR (422 plan_quota_exceeded / quota_exceeded). Sınırsız plan +
limit-altı → 200. Tarayıcı yolu (httpx + cookie). Sonunda temizler.

Kullanım: python scripts/live_limit_enforcement.py [BASE_URL]  (vars. :3000)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Institution, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"lim_{secrets.token_hex(3)}"
PWD = hash_password("Limit!2345")
PWDH = "Limit!2345"
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
all_user_ids: list[int] = []
all_inst_ids: list[int] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _code(r):
    try:
        return (r.json().get("detail", {}) or {}).get("code")
    except Exception:
        return None


def login(email):
    # Sunucu içi-bellek login limiter'ı (10/dk per IP) bu süreçten reset edilemez;
    # 429 dönerse sunucunun verdiği retry_after kadar bekleyip bir kez yeniden dene.
    get_login_limiter().reset()
    c = httpx.Client(base_url=BASE, timeout=40.0, follow_redirects=False)
    for attempt in range(2):
        r = c.post("/api/v2/auth/login", json={"email": email, "password": PWDH})
        if r.status_code == 200:
            return c
        if r.status_code == 429 and attempt == 0:
            try:
                wait = int(r.json().get("detail", {}).get("retry_after_seconds", 60))
            except Exception:
                wait = 60
            time.sleep(min(wait + 1, 62))
            continue
        raise RuntimeError(f"login {email}: {r.status_code} {r.text[:150]}")
    raise RuntimeError(f"login {email}: rate limited")


def make_coach(suffix, plan, seed_students):
    with SessionLocal() as db:
        c = User(email=f"{PFX}_{suffix}@t.invalid", password_hash=PWD, full_name=f"{PFX} {suffix}",
                 role=UserRole.TEACHER, institution_id=None, is_active=True, plan=plan,
                 password_changed_at=now, must_change_password=False)
        db.add(c); db.flush()
        cid = c.id
        for i in range(seed_students):
            s = User(email=f"{PFX}_{suffix}_s{i}@t.invalid", password_hash=PWD,
                     full_name=f"{PFX} {suffix} Ogr {i}", role=UserRole.STUDENT, teacher_id=cid,
                     institution_id=None, grade_level=8, is_active=True,
                     password_changed_at=now, must_change_password=False)
            db.add(s)
        db.commit()
        all_user_ids.append(cid)
        all_user_ids.extend(
            r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_{suffix}_s%")).all()
        )
    return f"{PFX}_{suffix}@t.invalid"


def make_institution(suffix, plan, seed_teachers):
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} {suffix}", slug=f"{PFX}-{suffix}", plan=plan, is_active=True)
        db.add(inst); db.flush()
        iid = inst.id
        adm = User(email=f"{PFX}_{suffix}_adm@t.invalid", password_hash=PWD, full_name="Adm",
                   role=UserRole.INSTITUTION_ADMIN, institution_id=iid, is_active=True,
                   password_changed_at=now, must_change_password=False)
        db.add(adm)
        for i in range(seed_teachers):
            t = User(email=f"{PFX}_{suffix}_t{i}@t.invalid", password_hash=PWD, full_name=f"T{i}",
                     role=UserRole.TEACHER, institution_id=iid, is_active=True,
                     password_changed_at=now, must_change_password=False)
            db.add(t)
        db.commit()
        all_inst_ids.append(iid)
        all_user_ids.extend(r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_{suffix}_%")).all())
    return f"{PFX}_{suffix}_adm@t.invalid"


def create_student(cli):
    sx = secrets.token_hex(2)
    return cli.post("/api/v2/teacher/students", json={
        "full_name": f"Yeni {sx}", "email": f"{PFX}_new_{sx}@t.invalid", "grade_level": 8})


def create_teacher(cli):
    sx = secrets.token_hex(2)
    return cli.post("/api/v2/institution/teachers", json={
        "full_name": f"Ogretmen {sx}", "email": f"{PFX}_nt_{sx}@t.invalid"})


def main() -> int:
    print(f"\n=== CANLI LİMİT/DUVAR TESTİ — BASE={BASE} — {PFX} ===\n")
    try:
        # ── SOLO ──
        print("SOLO (öğrenci limiti):")
        # free=3: limitte +1 engellenir
        e = make_coach("free", "solo_free", 3)
        r = create_student(login(e))
        check("free (3) limitte +1 → 422 plan_quota_exceeded",
              r.status_code == 422 and _code(r) == "plan_quota_exceeded", f"{r.status_code} {_code(r)}")
        # free=2 (limit altı): +1 başarılı
        e = make_coach("free2", "solo_free", 2)
        r = create_student(login(e))
        check("free (2) limit altı → 200 (eklenir)", r.status_code == 200, f"{r.status_code} {r.text[:100]}")
        # solo_pro=10: limitte +1 engellenir
        e = make_coach("pro", "solo_pro", 10)
        r = create_student(login(e))
        check("solo_pro (10) limitte +1 → 422", r.status_code == 422 and _code(r) == "plan_quota_exceeded",
              f"{r.status_code} {_code(r)}")
        # solo_elite=25: limitte +1 engellenir
        e = make_coach("elite", "solo_elite", 25)
        r = create_student(login(e))
        check("solo_elite (25) limitte +1 → 422", r.status_code == 422 and _code(r) == "plan_quota_exceeded",
              f"{r.status_code} {_code(r)}")
        # solo_unlimited=30: hâlâ eklenebilir
        e = make_coach("unl", "solo_unlimited", 30)
        r = create_student(login(e))
        check("solo_unlimited (30) → 200 (sınırsız, eklenir)", r.status_code == 200, f"{r.status_code}")

        # ── KURUM ──
        print("\nKURUM (öğretmen limiti):")
        # institution_free=2: limitte +1 öğretmen DOĞRUDAN create → 422 (bug fix)
        e = make_institution("ifree", "institution_free", 2)
        r = create_teacher(login(e))
        check("institution_free (2) limitte doğrudan öğretmen +1 → 422 quota_exceeded (DUVAR)",
              r.status_code == 422 and _code(r) == "quota_exceeded", f"{r.status_code} {_code(r)}")
        # institution_free=1 (altı): +1 başarılı
        e = make_institution("ifree1", "institution_free", 1)
        r = create_teacher(login(e))
        check("institution_free (1) limit altı → 201 (eklenir)", r.status_code in (200, 201), f"{r.status_code} {r.text[:100]}")
        # etut_standart=2 öğretmen (limit 10): +1 başarılı (ücretli plan free'ye düşmez)
        e = make_institution("etut", "etut_standart", 2)
        r = create_teacher(login(e))
        check("etut_standart (2/10) → 201 (ücretli plan free'ye düşmüyor — stale-key bug fix)",
              r.status_code in (200, 201), f"{r.status_code} {r.text[:100]}")
        # etut_standart=10 (limitte): +1 engellenir
        e = make_institution("etut10", "etut_standart", 10)
        r = create_teacher(login(e))
        check("etut_standart (10) limitte +1 → 422", r.status_code == 422 and _code(r) == "quota_exceeded",
              f"{r.status_code} {_code(r)}")

    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            insts = [r[0] for r in db.query(Institution.id).filter(Institution.slug.like(f"{PFX}-%")).all()]
            if insts:
                db.execute(sa_delete(Institution).where(Institution.id.in_(insts)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
