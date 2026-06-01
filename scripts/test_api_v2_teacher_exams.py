"""API v2 /teacher öğrenci deneme sonuçları smoke (KP4a — Akademik Çıktı).

Senaryolar:
   1. Anonim → 401
   2. POST exam happy (LGS, toplam) → 200, net = D - Y/3
   3. POST exam ders kırılımı → toplamlar türetilir + per-subject net
   4. POST boş deneme → 422 empty_exam
   5. POST geçersiz tarih → 422 invalid_date
   6. POST başka öğretmenin öğrencisi → 404
   7. GET liste → summary (count/avg/best/last/first/trend_delta) + rows DESC
   8. GET başka öğretmenin öğrencisi → 404
   9. DELETE happy → 200 + kayıt gider
  10. DELETE başka öğretmenin denemesi → 404
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import ExamResult, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2tex{secrets.token_hex(3)}"
T_EMAIL = f"{PFX}_t@test.invalid"
T2_EMAIL = f"{PFX}_t2@test.invalid"
PASSWORD = "ExamPass1!@xyz"

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


def _seed():
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        t = User(email=T_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        t2 = User(email=T2_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name="Öğr",
                 role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t.id)
        s2 = User(email=f"{PFX}_s2@test.invalid", password_hash=pwd, full_name="Öğr2",
                  role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t2.id)
        db.add_all([s, s2]); db.flush()
        out = {"t_id": t.id, "t2_id": t2.id, "s_id": s.id, "s2_id": s2.id}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        db.execute(sa_delete(ExamResult).where(
            ExamResult.student_id.in_([seed["s_id"], seed["s2_id"]])))
        db.execute(sa_delete(User).where(User.id.in_(
            [seed["t_id"], seed["t2_id"], seed["s_id"], seed["s2_id"]])))
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
    print(f"\n=== API v2 /teacher exams smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
        tc = _login(T_EMAIL)
        t2c = _login(T2_EMAIL)
        sid = seed["s_id"]

        r = TestClient(app).get(f"/api/v2/teacher/students/{sid}/exams")
        check("1. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 2. happy LGS toplam → net = 20 - 6/3 = 18.0
        r = tc.post(f"/api/v2/teacher/students/{sid}/exams", json={
            "title": "3D LGS Deneme 1", "exam_date": "2026-05-01", "section": "lgs",
            "total_correct": 20, "total_wrong": 6, "total_blank": 4})
        j = r.json()
        ok = r.status_code == 200 and abs(j["data"]["net"] - 18.0) < 0.01
        check("2. POST LGS happy net=18.0", ok, f"status={r.status_code} {r.text[:140]}")
        exam1_id = j["data"]["id"] if r.status_code == 200 else None
        check("2b. total_questions=30", r.status_code == 200 and j["data"]["total_questions"] == 30,
              f"{j.get('data', {}).get('total_questions')}")
        check("2c. invalidate exams key",
              r.status_code == 200 and any("exams" in k for k in j["invalidate"]),
              f"{j.get('invalidate')}")

        # 3. ders kırılımı → toplam türetilir: c=22 w=4 b=4, net=22-4/4=21.0
        r = tc.post(f"/api/v2/teacher/students/{sid}/exams", json={
            "title": "TYT Deneme", "exam_date": "2026-05-10", "section": "tyt",
            "subjects": [
                {"name": "Matematik", "correct": 10, "wrong": 4, "blank": 1},
                {"name": "Türkçe", "correct": 12, "wrong": 0, "blank": 3}]})
        j = r.json()
        d = j.get("data", {})
        ok = (r.status_code == 200 and d.get("total_correct") == 22 and d.get("total_wrong") == 4
              and abs(d.get("net", 0) - 21.0) < 0.01 and len(d.get("subjects", [])) == 2)
        check("3. ders kırılımı → toplam+net türetilir", ok, f"status={r.status_code} {d}")
        mat = next((x for x in d.get("subjects", []) if x["name"] == "Matematik"), None)
        check("3b. Matematik net=9.0 (10-4/4)", mat is not None and abs(mat["net"] - 9.0) < 0.01, f"{mat}")

        # 4. boş deneme
        r = tc.post(f"/api/v2/teacher/students/{sid}/exams", json={
            "title": "Boş", "exam_date": "2026-05-11", "section": "lgs",
            "total_correct": 0, "total_wrong": 0, "total_blank": 0})
        check("4. boş deneme → 422 empty_exam",
              r.status_code == 422 and r.json()["detail"]["code"] == "empty_exam",
              f"status={r.status_code} {r.text[:120]}")

        # 5. geçersiz tarih
        r = tc.post(f"/api/v2/teacher/students/{sid}/exams", json={
            "title": "X", "exam_date": "bozuk", "section": "lgs", "total_correct": 5})
        check("5. geçersiz tarih → 422 invalid_date",
              r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date",
              f"status={r.status_code}")

        # 6. başka öğretmenin öğrencisi
        r = tc.post(f"/api/v2/teacher/students/{seed['s2_id']}/exams", json={
            "title": "X", "exam_date": "2026-05-01", "section": "lgs", "total_correct": 5})
        check("6. başka öğr. öğrencisi → 404", r.status_code == 404, f"status={r.status_code}")

        # 7. liste + summary
        r = tc.get(f"/api/v2/teacher/students/{sid}/exams")
        j = r.json()
        s = j["summary"]
        # 2 deneme: net 18.0 (05-01) + 21.0 (05-10). DESC → last=21.0 (en yeni), first=18.0
        ok = (r.status_code == 200 and s["count"] == 2 and abs(s["avg_net"] - 19.5) < 0.01
              and abs(s["best_net"] - 21.0) < 0.01 and abs(s["last_net"] - 21.0) < 0.01
              and abs(s["first_net"] - 18.0) < 0.01 and abs(s["trend_delta"] - 3.0) < 0.01)
        check("7. summary count/avg/best/last/first/trend", ok, f"status={r.status_code} {s}")
        check("7b. rows DESC (en yeni ilk)",
              r.status_code == 200 and j["rows"][0]["exam_date"] == "2026-05-10", f"{[x['exam_date'] for x in j['rows']]}")
        check("7c. section_options 6 adet",
              r.status_code == 200 and len(j["section_options"]) == 6, f"{len(j.get('section_options', []))}")

        # 8. başka öğretmenin öğrencisi GET
        r = tc.get(f"/api/v2/teacher/students/{seed['s2_id']}/exams")
        check("8. başka öğr. öğrencisi GET → 404", r.status_code == 404, f"status={r.status_code}")

        # 8b. UPDATE happy — hatalı giriş düzelt: yeni net = 25 - 3/3 = 24.0
        r = tc.post(f"/api/v2/teacher/exams/{exam1_id}", json={
            "title": "3D LGS Deneme 1 (düzeltildi)", "exam_date": "2026-05-02",
            "section": "lgs", "total_correct": 25, "total_wrong": 3, "total_blank": 2})
        j = r.json()
        ok = (r.status_code == 200 and abs(j["data"]["net"] - 24.0) < 0.01
              and j["data"]["title"] == "3D LGS Deneme 1 (düzeltildi)"
              and j["data"]["exam_date"] == "2026-05-02"
              and j["data"]["total_questions"] == 30)
        check("8b. UPDATE happy → net yeniden hesap (24.0) + alanlar güncel", ok,
              f"status={r.status_code} {r.text[:160]}")

        # 8c. başka öğretmen UPDATE → 404 (sahiplik)
        r = t2c.post(f"/api/v2/teacher/exams/{exam1_id}", json={
            "title": "X", "exam_date": "2026-05-01", "section": "lgs", "total_correct": 5})
        check("8c. başka öğr. UPDATE → 404", r.status_code == 404, f"status={r.status_code}")

        # 9. DELETE happy
        r = tc.delete(f"/api/v2/teacher/exams/{exam1_id}")
        check("9. DELETE happy → 200", r.status_code == 200 and r.json()["data"]["deleted"],
              f"status={r.status_code}")
        r = tc.get(f"/api/v2/teacher/students/{sid}/exams")
        check("9b. silindikten sonra count=1", r.json()["summary"]["count"] == 1, f"{r.json()['summary']}")

        # 10. başka öğretmen DELETE → 404
        r = t2c.delete(f"/api/v2/teacher/exams/{exam1_id}")
        check("10. başka öğr. DELETE → 404", r.status_code == 404, f"status={r.status_code}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
