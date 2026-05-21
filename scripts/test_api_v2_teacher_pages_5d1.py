"""API v2 öğretmen 5d.1 smoke — analytics + parent-note + fleet panoları.

Senaryolar (10):
   1. GET /students/{id}/analytics happy (trend len=30, subjects[])
   2. GET /students/{id}/analytics başkasının → 404
   3. POST /students/{id}/parent-note — kısa metin → 422 note_too_short
   4. POST /students/{id}/parent-note — veli yok → 422 no_active_parents
   5. POST /students/{id}/parent-note — happy (veli ekledikten sonra) → 200 + fired
   6. POST /students/{id}/parent-note — başkasının öğrencisi → 404
   7. GET /teacher/burnout — list + counter alanları
   8. GET /teacher/burnout — başka öğretmen kendi öğrencilerini görür (izolasyon)
   9. GET /teacher/review — rows + total_due/total_cards
  10. GET /teacher/review — başka öğretmen kendi öğrencilerini görür (izolasyon)
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
from app.models import (
    ParentStudentLink,
    TeacherNoteToParent,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2_5d_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_s2@test.invalid"
PARENT_EMAIL = f"{PFX}_p@test.invalid"
PASSWORD = "TestPass123!@xyz"

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
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 5d Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen 5d", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        db.add_all([teacher, other_teacher]); db.flush()

        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Öğrenci {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=teacher.id,
        )
        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Diğer Öğrenci {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=other_teacher.id,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Veli {PFX}", role=UserRole.PARENT, is_active=True,
        )
        db.add_all([student, other_student, parent]); db.flush()

        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "other_student_id": other_student.id,
            "parent_id": parent.id,
        }


def _link_parent(seed: dict) -> None:
    with SessionLocal() as db:
        link = ParentStudentLink(
            parent_id=seed["parent_id"],
            student_id=seed["student_id"],
            relation="anne",
            is_primary=True,
        )
        db.add(link)
        db.commit()


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        sids = [seed["student_id"], seed["other_student_id"]]
        db.execute(sa_delete(TeacherNoteToParent).where(TeacherNoteToParent.student_id.in_(sids)))
        db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(sids)))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["teacher_id"], seed["other_teacher_id"],
            seed["student_id"], seed["other_student_id"], seed["parent_id"],
        ])))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher 5d.1 (analytics/parent-note/fleet) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} student={seed['student_id']}\n")

    try:
        client = TestClient(app)
        _login(client, TEACHER_EMAIL)

        # ============ ANALYTICS ============
        # 1) Happy
        r = client.get(f"/api/v2/teacher/students/{seed['student_id']}/analytics")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("window_days") == 30
            and isinstance(body.get("trend"), list)
            and len(body["trend"]) == 30
            and isinstance(body.get("subjects"), list)
            and "label" in body["trend"][0]
            and "completed" in body["trend"][0]
            and "planned" in body["trend"][0]
        )
        check("1. GET /analytics happy", ok, f"status={r.status_code} trend={len(body.get('trend', []))}")

        # 2) 404
        r = client.get(f"/api/v2/teacher/students/{seed['other_student_id']}/analytics")
        ok = r.status_code == 404
        check("2. GET /analytics başkasının → 404", ok, f"status={r.status_code}")

        # ============ PARENT NOTE ============
        # 3) Kısa metin
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/parent-note",
            json={"body": "kısa"},
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "note_too_short"
        )
        check("3. POST /parent-note kısa → 422 note_too_short", ok, f"status={r.status_code}")

        # 4) Veli yok
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/parent-note",
            json={"body": "Bu yeterince uzun bir test notudur."},
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "no_active_parents"
        )
        check("4. POST /parent-note veli yok → 422", ok, f"status={r.status_code}")

        # Veli ekle
        _link_parent(seed)

        # 5) Happy
        r = client.post(
            f"/api/v2/teacher/students/{seed['student_id']}/parent-note",
            json={"body": "Bu yeterince uzun bir test notudur — veliye gönderilecek."},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("parent_count") == 1
            and isinstance(body.get("data", {}).get("note_id"), int)
        )
        check("5. POST /parent-note happy", ok, f"status={r.status_code} body={body}")

        # 6) Başkasının öğrencisi
        r = client.post(
            f"/api/v2/teacher/students/{seed['other_student_id']}/parent-note",
            json={"body": "Yeterince uzun bir not yazıyorum."},
        )
        ok = r.status_code == 404
        check("6. POST /parent-note başkasının → 404", ok, f"status={r.status_code}")

        # ============ FLEET BURNOUT ============
        # 7) Happy
        r = client.get("/api/v2/teacher/burnout")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and isinstance(body.get("rows"), list)
            and len(body["rows"]) == 1
            and body["rows"][0]["student_id"] == seed["student_id"]
            and "healthy_count" in body
            and "critical_count" in body
        )
        check("7. GET /teacher/burnout happy", ok, f"status={r.status_code} rows={len(body.get('rows', []))}")

        # 8) İzolasyon — diğer öğretmen kendi öğrencisini görür, bizimkini değil
        client_other = TestClient(app)
        _login(client_other, OTHER_TEACHER_EMAIL)
        r2 = client_other.get("/api/v2/teacher/burnout")
        b2 = r2.json() if r2.text else {}
        sids_visible = {row["student_id"] for row in b2.get("rows", [])}
        ok = (
            r2.status_code == 200
            and seed["other_student_id"] in sids_visible
            and seed["student_id"] not in sids_visible
        )
        check("8. GET /teacher/burnout izolasyon", ok, f"status={r2.status_code} sids={sids_visible}")

        # ============ FLEET REVIEW ============
        # 9) Happy
        r = client.get("/api/v2/teacher/review")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and isinstance(body.get("rows"), list)
            and len(body["rows"]) == 1
            and "total_due" in body
            and "total_cards" in body
        )
        check("9. GET /teacher/review happy", ok, f"status={r.status_code}")

        # 10) İzolasyon
        r2 = client_other.get("/api/v2/teacher/review")
        b2 = r2.json() if r2.text else {}
        sids_visible = {row["student_id"] for row in b2.get("rows", [])}
        ok = (
            r2.status_code == 200
            and seed["other_student_id"] in sids_visible
            and seed["student_id"] not in sids_visible
        )
        check("10. GET /teacher/review izolasyon", ok, f"status={r2.status_code} sids={sids_visible}")

    finally:
        _cleanup(seed)
        print(f"\n  cleanup OK\n")

    print(f"\n=== SONUÇ: {passed}/{passed + len(failed)} PASS ===")
    if failed:
        print("\nBaşarısız:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
