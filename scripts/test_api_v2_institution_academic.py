"""API v2 /institution/academic (Kurum Akademik Çıktı Panosu) smoke (KP4b).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. happy şekil (summary + sections + trend + teachers + improving/declining + no_exam)
   4. kapsama: 3 öğrenci, 2'si deneme girmiş → %67
   5. no_exam_count=1 (deneme girmeyen)
   6. avg_net_pct normalize: [40,60,50] → 50
   7. section kırılımı: LGS (2 deneme, ort net 15, %50) + TYT (1, ort net 60, %50)
   8. improving: s1 +20 delta (40→60)
   9. öğretmen kırılımı 2 koç
  10. weeks param kabul
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import ExamResult, ExamSection, Institution, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2iacad{secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
PASSWORD = "AcadPass1!@xyz"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _exam(student_id, section, correct, wrong, blank, net, d):
    return ExamResult(
        student_id=student_id, title="Deneme", exam_date=d, section=section,
        total_correct=correct, total_wrong=wrong, total_blank=blank, net=net)


def _seed():
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} K", slug=f"{PFX}-k", contact_email=f"{PFX}@t.invalid",
                           plan="free", is_active=True)
        db.add(inst); db.flush()
        admin = User(email=ADMIN_EMAIL, password_hash=pwd, full_name=f"{PFX} Admin",
                     role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True,
                     password_changed_at=now, must_change_password=False, email_verified_at=now)
        t1 = User(email=f"{PFX}_t1@t.invalid", password_hash=pwd, full_name=f"{PFX} Koç1",
                  role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                  password_changed_at=now, must_change_password=False, email_verified_at=now)
        t2 = User(email=f"{PFX}_t2@t.invalid", password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                  password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add_all([admin, t1, t2]); db.flush()
        s1 = User(email=f"{PFX}_s1@t.invalid", password_hash=pwd, full_name="Öğr Bir",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=t1.id, is_active=True)
        s2 = User(email=f"{PFX}_s2@t.invalid", password_hash=pwd, full_name="Öğr İki",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=t2.id, is_active=True)
        s3 = User(email=f"{PFX}_s3@t.invalid", password_hash=pwd, full_name="Öğr Üç",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=t1.id, is_active=True)
        db.add_all([s1, s2, s3]); db.flush()
        # s1: LGS 2 deneme — 12/30=40%, 18/30=60% (gelişiyor)
        db.add(_exam(s1.id, ExamSection.LGS, 12, 0, 18, 12.0, date(2026, 4, 1)))
        db.add(_exam(s1.id, ExamSection.LGS, 18, 0, 12, 18.0, date(2026, 5, 1)))
        # s2: TYT 1 deneme — 60/120=50%
        db.add(_exam(s2.id, ExamSection.TYT, 60, 0, 60, 60.0, date(2026, 5, 10)))
        # s3: deneme yok
        db.flush()
        out = {"inst_id": inst.id, "admin_id": admin.id, "t1": t1.id, "t2": t2.id,
               "s_ids": [s1.id, s2.id, s3.id]}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(seed["s_ids"])))
        uids = [seed["admin_id"], seed["t1"], seed["t2"], *seed["s_ids"]]
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== API v2 /institution/academic smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    seed = _seed()
    try:
        ac = _login(ADMIN_EMAIL)
        tc = _login(f"{PFX}_t1@t.invalid")

        r = tc.get("/api/v2/institution/academic")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        r = TestClient(app).get("/api/v2/institution/academic")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        r = ac.get("/api/v2/institution/academic")
        j = r.json()
        ok = (r.status_code == 200 and all(k in j for k in
              ["summary", "sections", "trend", "teachers", "improving", "declining", "no_exam_program"]))
        check("3. happy şekil", ok, f"status={r.status_code} {r.text[:140]}")

        s = j["summary"]
        check("4. kapsama %67 (3 öğr, 2 deneme)",
              s["total_students"] == 3 and s["students_with_exam"] == 2 and s["coverage_pct"] == 67,
              f"{s}")
        check("5. no_exam_count=1", s["no_exam_count"] == 1, f"{s['no_exam_count']}")
        check("5b. total_exams=3", s["total_exams"] == 3, f"{s['total_exams']}")
        check("6. avg_net_pct=50 (normalize)", s["avg_net_pct"] == 50, f"{s['avg_net_pct']}")

        lgs = next((x for x in j["sections"] if x["section"] == "lgs"), None)
        tyt = next((x for x in j["sections"] if x["section"] == "tyt"), None)
        check("7. LGS section: 2 deneme, ort net 15, %50",
              lgs is not None and lgs["exam_count"] == 2 and abs(lgs["avg_net"] - 15.0) < 0.01
              and lgs["avg_net_pct"] == 50, f"{lgs}")
        check("7b. TYT section: 1 deneme, ort net 60, %50",
              tyt is not None and tyt["exam_count"] == 1 and abs(tyt["avg_net"] - 60.0) < 0.01
              and tyt["avg_net_pct"] == 50, f"{tyt}")

        imp = j["improving"]
        s1mover = next((m for m in imp if m["student_name"] == "Öğr Bir"), None)
        check("8. improving: Öğr Bir +20 (40→60)",
              s1mover is not None and s1mover["delta"] == 20 and s1mover["first_net_pct"] == 40
              and s1mover["last_net_pct"] == 60, f"{s1mover}")

        check("9. öğretmen kırılımı 2 koç (deneme giren öğrencisi olan)",
              len(j["teachers"]) == 2, f"{len(j['teachers'])}")
        t1row = next((t for t in j["teachers"] if t["teacher_name"] == f"{PFX} Koç1"), None)
        check("9b. Koç1: 1 öğrenci (s1), 2 deneme",
              t1row is not None and t1row["student_count"] == 1 and t1row["exam_count"] == 2, f"{t1row}")

        r = ac.get("/api/v2/institution/academic?weeks=12")
        check("10. weeks=12 kabul", r.status_code == 200 and r.json()["summary"]["weeks"] == 12,
              f"status={r.status_code}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
