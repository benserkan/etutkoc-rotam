# -*- coding: utf-8 -*-
"""Dolu demo evreni (demo_universe) smoke — plan + endpoint + build + silme.

Senaryolar (12):
   1. anon POST → 401
   2. koç POST → 403
   3. plan deterministik (aynı seed_id → aynı e-postalar)
   4. süper admin POST (1 koç × 2 öğrenci) → 200 + hesap listesi anında (6 hesap)
   5. arka plan build bitti → kullanıcılar DB'de (is_demo + demo_seed_id)
   6. görev geçmişi + seans + içgörü + Rota yorumu kuruldu
   7. koç girişi → öğrenci listesi 2
   8. aynı adla ikinci POST → 409 universe_exists
   9. /demo-sessions listesinde evren görünür
  10. silme → kullanıcılar + kurum gitti
  11. silme → YSA + anket ataması + Rota yorumu + destek talebi de gitti (dev FK)
  12. geçersiz gövde (coach_count=0) → 422
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import SupportRequest, User, UserRole, WrongQuestion
from app.models.coaching_session import CoachingInsight, CoachingSession
from app.models.institution import Institution
from app.models.parent_commentary import ParentCommentary
from app.models.survey import SurveyAssignment
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"duni_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
SA_EMAIL = f"{PFX}_sa@test.invalid"
T_EMAIL = f"{PFX}_t@test.invalid"
LABEL = f"Evren Testi {PFX}"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    with SessionLocal() as db:
        sa = User(email=SA_EMAIL, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} SA", role=UserRole.SUPER_ADMIN, is_active=True)
        t = User(email=T_EMAIL, password_hash=hash_password(PASSWORD),
                 full_name=f"{PFX} Koç", role=UserRole.TEACHER, is_active=True)
        db.add_all([sa, t])
        db.commit()
        return {"sa": sa.id, "t": t.id}


def _cleanup(ids: dict, seed_id: str | None) -> None:
    with SessionLocal() as db:
        if seed_id:  # evren silinmemişse süpür
            from app.services.demo_seed import delete_demo_session
            try:
                delete_demo_session(db, seed_id=seed_id)
                db.commit()
            except Exception:
                db.rollback()
        db.execute(sa_delete(User).where(User.id.in_(list(ids.values()))))
        db.commit()


def login(c: TestClient, email: str) -> int:
    get_login_limiter().reset()
    return c.post("/api/v2/auth/login",
                  json={"email": email, "password": PASSWORD}).status_code


def main() -> int:
    ids = _seed()
    c = TestClient(app)
    body = {"label": LABEL, "coach_count": 1, "students_per_coach": 2,
            "with_audio": False}
    seed_id = None

    try:
        # 1-2: yetki kapıları
        r = c.post("/api/v2/admin/demo-universe", json=body)
        check("1. anon → 401", r.status_code == 401, str(r.status_code))
        assert login(c, T_EMAIL) == 200
        r = c.post("/api/v2/admin/demo-universe", json=body)
        check("2. koç → 403", r.status_code == 403, str(r.status_code))

        # 3: plan deterministik
        from app.services.demo_universe import plan_universe
        p1 = plan_universe(label=LABEL, coach_count=2, students_per_coach=3,
                           seed_id="abc123")
        p2 = plan_universe(label=LABEL, coach_count=2, students_per_coach=3,
                           seed_id="abc123")
        check("3. plan deterministik (aynı seed → aynı e-postalar)",
              [x.email for pc in p1.coaches for x in pc.students]
              == [x.email for pc in p2.coaches for x in pc.students]
              and p1.coaches[0].email == p2.coaches[0].email, "")

        # 4: süper admin oluşturur — hesaplar anında döner
        assert login(c, SA_EMAIL) == 200
        r = c.post("/api/v2/admin/demo-universe", json=body)
        data = r.json() if r.status_code == 200 else {}
        seed_id = data.get("seed_id")
        check("4. süper admin → 200 + 6 hesap anında + building",
              r.status_code == 200 and len(data.get("accounts", [])) == 6
              and data.get("building") is True and data.get("password"),
              f"{r.status_code} n={len(data.get('accounts', []))}")

        # 5-6: TestClient background task'ı yanıt sonrasında çalıştırdı → DB dolu
        with SessionLocal() as db:
            users = db.query(User).filter(User.demo_seed_id == seed_id).all()
            check("5. build bitti: 6 kullanıcı (is_demo + seed_id)",
                  len(users) == 6 and all(u.is_demo for u in users),
                  f"n={len(users)}")
            stu_ids = [u.id for u in users if u.role == UserRole.STUDENT]
            n_ses = db.query(CoachingSession).filter(
                CoachingSession.student_id.in_(stu_ids)).count()
            n_ins = db.query(CoachingInsight).filter(
                CoachingInsight.student_id.in_(stu_ids)).count()
            n_com = db.query(ParentCommentary).filter(
                ParentCommentary.student_id.in_(stu_ids)).count()
            n_wq = db.query(WrongQuestion).filter(
                WrongQuestion.student_id.in_(stu_ids)).count()
            check("6. seans 10 + içgörü 2 + Rota yorumu ≥2 + YSA ≥4",
                  n_ses == 10 and n_ins == 2 and n_com >= 2 and n_wq >= 4,
                  f"ses={n_ses} ins={n_ins} com={n_com} wq={n_wq}")
            inst = db.query(Institution).filter(
                Institution.demo_seed_id == seed_id).first()
            coach_email = next(u.email for u in users
                               if u.role == UserRole.TEACHER)

        # 7: evren koçu giriş yapıp öğrencilerini görür
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": coach_email, "password": data["password"]})
        ok = r.status_code == 200
        if ok:
            r2 = c.get("/api/v2/teacher/students")
            ok = r2.status_code == 200 and len(r2.json().get("items", [])) == 2
        check("7. evren koçu girer + 2 öğrenci görür", ok, str(r.status_code))

        # 8: aynı ad → 409
        assert login(c, SA_EMAIL) == 200
        r = c.post("/api/v2/admin/demo-universe", json=body)
        check("8. aynı adla tekrar → 409 universe_exists",
              r.status_code == 409
              and r.json()["detail"]["code"] == "universe_exists",
              str(r.status_code))

        # 9: listede görünür
        r = c.get("/api/v2/admin/demo-sessions")
        found = any(it["seed_id"] == seed_id for it in r.json().get("items", []))
        check("9. /demo-sessions listesinde evren var", found, str(r.status_code))

        # 10-11: silme + kapanış
        r = c.post(f"/api/v2/admin/demo-sessions/{seed_id}/delete")
        check("10. silme → 200 + 6 kullanıcı", r.status_code == 200
              and r.json().get("users_deleted") == 6,
              f"{r.status_code} {r.text[:120]}")
        with SessionLocal() as db:
            left_u = db.query(User).filter(User.demo_seed_id == seed_id).count()
            left_i = db.query(Institution).filter(
                Institution.demo_seed_id == seed_id).count()
            left_wq = db.query(WrongQuestion).filter(
                WrongQuestion.student_id.in_(stu_ids)).count()
            left_sa = db.query(SurveyAssignment).filter(
                SurveyAssignment.student_id.in_(stu_ids)).count()
            left_pc = db.query(ParentCommentary).filter(
                ParentCommentary.student_id.in_(stu_ids)).count()
            left_sr = db.query(SupportRequest).filter(
                SupportRequest.target_user_id.in_(
                    [u.id for u in users if u.role == UserRole.TEACHER])).count()
            check("11. kapanış: YSA/anket/yorum/destek de silindi",
                  left_u == 0 and left_i == 0 and left_wq == 0
                  and left_sa == 0 and left_pc == 0 and left_sr == 0,
                  f"u={left_u} i={left_i} wq={left_wq} sa={left_sa} "
                  f"pc={left_pc} sr={left_sr}")
        if left_u == 0:
            seed_id = None  # cleanup'ta tekrar silmeye gerek yok

        # 12: validasyon
        r = c.post("/api/v2/admin/demo-universe",
                   json={**body, "coach_count": 0})
        check("12. coach_count=0 → 422", r.status_code == 422, str(r.status_code))
    finally:
        _cleanup(ids, seed_id)

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
