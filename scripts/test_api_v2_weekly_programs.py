"""WP1 — Weekly Programs smoke (10 senaryo).

1.  POST happy: 30 May–5 Haz (7 gün) → 200 + day_count=7
2.  Süre 15 gün → 422 too_long
3.  Bitiş < başlangıç → 422 invalid_range
4.  Çakışma → 409 + detail.overlaps listesi
5.  allow_overlap=true → 200 (zorla yarat)
6.  GET liste → 2 program + active_program_id (today eklenmiş aralıkta)
7.  PATCH tarih → 200, day_count güncel
8.  PATCH çakıştıran tarih (başkasıyla) → 409
9.  DELETE program → 200, listede yok
10. wrap-legacy: programa bağlı olmayan 5 görev → 200 + tek "Eski Dönem" program
11. Başka koçun öğrencisi (sahiplik) → 404 not_found
12. Anon → 401, başka rol → 403
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    SuspiciousIp,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
    WeeklyProgram,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2wp_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
TEACHER2_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
STUDENT2_EMAIL = f"{PFX}_s2@test.invalid"   # teacher2'nin öğrencisi (sahiplik testi)
PARENT_EMAIL = f"{PFX}_p@test.invalid"
PASSWORD = "TestPass123!@xyz"

passed = 0
failed: list[str] = []
created_program_ids: list[int] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    """1 koç + 1 öğrenci + 1 koç2 + 1 öğrenci2 (sahiplik için) + 5 task (programa bağlı değil)."""
    today = date.today()
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="WP Test Koç", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        teacher2 = User(
            email=TEACHER2_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="WP Test Koç 2", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="WP Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        student2 = User(
            email=STUDENT2_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Başka Koç Öğrencisi", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="WP Veli (rol guard)", role=UserRole.PARENT,
            is_active=True,
        )
        db.add_all([teacher, teacher2, student, student2, parent])
        db.flush()
        student.teacher_id = teacher.id
        student2.teacher_id = teacher2.id

        # 5 unlinked task (today-10 → today-6)
        for i in range(5):
            task_date = today - timedelta(days=10 - i)  # today-10, -9, -8, -7, -6
            t = Task(
                student_id=student.id, date=task_date, type=TaskType.OTHER,
                title=f"Legacy görev {i+1}",
                status=TaskStatus.PENDING, order=0, is_draft=False,
                published_at=datetime.now(timezone.utc),
            )
            db.add(t)
            db.flush()
            # Kitapsız etiket — basit
            db.add(TaskBookItem(
                task_id=t.id, book_id=None, book_section_id=None,
                label="Test", planned_count=5,
            ))
        db.commit()
        return {
            "teacher_id": teacher.id,
            "teacher2_id": teacher2.id,
            "student_id": student.id,
            "student2_id": student2.id,
            "parent_id": parent.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        # Programlar
        if created_program_ids:
            db.execute(sa_delete(WeeklyProgram).where(
                WeeklyProgram.id.in_(created_program_ids)))
        db.execute(sa_delete(WeeklyProgram).where(
            WeeklyProgram.student_id.in_([seed["student_id"], seed["student2_id"]])))
        # Tasks
        task_ids = [tid for (tid,) in db.query(Task.id)
                    .filter(Task.student_id == seed["student_id"]).all()]
        if task_ids:
            db.execute(sa_delete(TaskBookItem).where(
                TaskBookItem.task_id.in_(task_ids)))
            db.execute(sa_delete(Task).where(Task.id.in_(task_ids)))
        # Users
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["student2_id"], seed["parent_id"],
            seed["teacher_id"], seed["teacher2_id"],
        ])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(client: TestClient, email: str) -> int:
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    return r.status_code


def main() -> int:
    print(f"\n=== WP1 weekly programs smoke — prefix: {PFX} ===\n")
    seed = _seed()
    sid = seed["student_id"]

    try:
        client = TestClient(app)
        assert _login(client, TEACHER_EMAIL) == 200

        today = date.today()
        sd1 = today.isoformat()
        ed1 = (today + timedelta(days=6)).isoformat()

        # 1. happy
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs",
            json={"start_date": sd1, "end_date": ed1, "name": "Test Hafta 1"},
        )
        body = r.json() if r.text else {}
        p1_id = body.get("data", {}).get("id")
        if p1_id:
            created_program_ids.append(p1_id)
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("day_count") == 7
            and body.get("data", {}).get("is_active") is True
        )
        check("1. POST happy 7 gün → 200 + active",
              ok, f"status={r.status_code} body={r.text[:200]}")

        # 2. too_long (15 gün)
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs",
            json={
                "start_date": (today + timedelta(days=20)).isoformat(),
                "end_date": (today + timedelta(days=34)).isoformat(),
            },
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 422
              and body.get("detail", {}).get("code") == "too_long")
        check("2. 15 gün → 422 too_long",
              ok, f"status={r.status_code} body={r.text[:200]}")

        # 3. invalid_range
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs",
            json={
                "start_date": (today + timedelta(days=30)).isoformat(),
                "end_date": (today + timedelta(days=20)).isoformat(),
            },
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 422
              and body.get("detail", {}).get("code") == "invalid_range")
        check("3. end < start → 422 invalid_range",
              ok, f"status={r.status_code}")

        # 4. çakışma (today + 2gun --> today + 8gun çakışıyor P1 ile)
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs",
            json={
                "start_date": (today + timedelta(days=2)).isoformat(),
                "end_date": (today + timedelta(days=8)).isoformat(),
            },
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "overlap"
            and isinstance(body.get("detail", {}).get("overlaps"), list)
            and len(body["detail"]["overlaps"]) == 1
        )
        check("4. çakışma → 409 + overlaps listesi",
              ok, f"status={r.status_code} body={r.text[:200]}")

        # 5. allow_overlap=True → zorla yarat
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs",
            json={
                "start_date": (today + timedelta(days=2)).isoformat(),
                "end_date": (today + timedelta(days=8)).isoformat(),
                "allow_overlap": True,
            },
        )
        body = r.json() if r.text else {}
        p2_id = body.get("data", {}).get("id")
        if p2_id:
            created_program_ids.append(p2_id)
        ok = r.status_code == 200 and body.get("data", {}).get("day_count") == 7
        check("5. allow_overlap=True → 200",
              ok, f"status={r.status_code}")

        # 6. GET liste
        r = client.get(f"/api/v2/teacher/students/{sid}/programs")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and len(items) == 2
            and body.get("active_program_id") in (p1_id, p2_id)  # ikisi de today'i kapsıyor
            and body.get("unlinked_task_count", 0) >= 5  # legacy task'lar unlinked
        )
        check("6. GET liste → 2 program + active_id + unlinked≥5",
              ok, f"items={len(items)} active={body.get('active_program_id')} unlinked={body.get('unlinked_task_count')}")

        # 7. PATCH çakışma (P1'i P2 üstüne uzatmaya çalış — P2 hâlâ var)
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs/{p1_id}",
            json={"end_date": (today + timedelta(days=10)).isoformat()},
        )
        body = r.json() if r.text else {}
        ok = (r.status_code == 409
              and body.get("detail", {}).get("code") == "overlap")
        check("7. PATCH çakışma → 409",
              ok, f"status={r.status_code}")

        # 8. DELETE P2 → kalır sadece P1 [today..today+6]
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs/{p2_id}/delete",
            json={"delete_tasks": False},
        )
        ok = r.status_code == 200
        check("8. DELETE P2 → 200",
              ok, f"status={r.status_code}")
        if ok and p2_id in created_program_ids:
            created_program_ids.remove(p2_id)

        # 9. PATCH P1'i 5 güne kısalt → 200
        new_end = (today + timedelta(days=4)).isoformat()
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs/{p1_id}",
            json={"end_date": new_end},
        )
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("data", {}).get("day_count") == 5
        check("9. PATCH bitiş → 5 gün",
              ok, f"status={r.status_code} day_count={body.get('data', {}).get('day_count')}")

        # 10. wrap-legacy: legacy (today-10..today-6) hiç bir programda değil
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs/wrap-legacy",
            json={"name": "Eski Dönem Test"},
        )
        body = r.json() if r.text else {}
        p3_id = body.get("data", {}).get("id")
        if p3_id:
            created_program_ids.append(p3_id)
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("name") == "Eski Dönem Test"
            and body.get("data", {}).get("day_count") == 5  # today-10..today-6 = 5 gün
        )
        check("10. wrap-legacy → 'Eski Dönem' programı, 5 gün",
              ok, f"status={r.status_code} day_count={body.get('data', {}).get('day_count')}")

        # 10b. wrap-legacy tekrar → unlinked yok artık → 422
        r = client.post(
            f"/api/v2/teacher/students/{sid}/programs/wrap-legacy",
            json={},
        )
        body = r.json() if r.text else {}
        detail = body.get("detail")
        # detail dict olmalı; Pydantic 422'lerinde liste olur, biz manuel 422 atıyoruz dict
        code = detail.get("code") if isinstance(detail, dict) else None
        ok = r.status_code == 422 and code == "no_unlinked_tasks"
        check("10b. wrap-legacy yine → 422 no_unlinked_tasks",
              ok, f"status={r.status_code} code={code}")

        # 11. Başka koçun öğrencisi
        r = client.get(
            f"/api/v2/teacher/students/{seed['student2_id']}/programs"
        )
        ok = r.status_code == 404
        check("11. Başka koçun öğrencisi → 404",
              ok, f"status={r.status_code}")

        # 12. Anon + parent role
        anon = TestClient(app)
        r1 = anon.get(f"/api/v2/teacher/students/{sid}/programs")
        ok_anon = r1.status_code == 401

        pc = TestClient(app)
        assert _login(pc, PARENT_EMAIL) == 200
        r2 = pc.get(f"/api/v2/teacher/students/{sid}/programs")
        ok_parent = r2.status_code == 403
        check("12. anon→401 + parent→403",
              ok_anon and ok_parent,
              f"anon={r1.status_code} parent={r2.status_code}")

    finally:
        _cleanup(seed)

    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} geçti ===\n")
    if failed:
        print("Başarısız senaryolar:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
