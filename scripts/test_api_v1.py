"""API v1 smoke test — JWT auth + key endpoints + CORS + rate limit.

Senaryo:
  1. /api/v1/ping → 200, auth gerektirmez
  2. /api/v1/auth/login geçersiz şifre → 401 + {"error","code"}
  3. /api/v1/auth/login doğru şifre → access + refresh + user
  4. /api/v1/me bearer ile → 200, user dönüyor
  5. /api/v1/me bearer yok → 401 missing_token
  6. /api/v1/me bozuk token → 401 invalid_token
  7. /api/v1/me refresh token ile → 401 wrong_token_type
  8. /api/v1/auth/refresh refresh ile → yeni access
  9. /api/v1/auth/refresh access ile → 401 wrong_token_type
  10. Student: /api/v1/student/today → görev listesi
  11. Student: /api/v1/student/focus/start → /focus/{id}/end → /focus özet
  12. Student: /api/v1/student/review → due cards + breakdown
  13. Teacher: /api/v1/teacher/students → öğrenci listesi
  14. Teacher: /api/v1/teacher/students/{id} → detay
  15. CORS preflight OPTIONS → 200 + Access-Control-Allow-* header
  16. Rate limit: 11x login → 11. istek 429 (limit=10/dk)
  17. /api/v1/auth/logout → ok
  18. Şifre değiştir → eski access token invalid (pwd_stamp mismatch)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.services.security import hash_password


PFX = f"api_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
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


def _seed_users() -> tuple[int, int, int]:
    """Test öğretmen + öğrenci yarat, görev ekle. Returns (teacher_id, student_id, task_id)."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="API Test Öğretmen",
            role=UserRole.TEACHER,
            is_active=True,
            plan="solo_free",
        )
        db.add(teacher)
        db.flush()

        student = User(
            email=STUDENT_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="API Test Öğrenci",
            role=UserRole.STUDENT,
            is_active=True,
            teacher_id=teacher.id,
            grade_level=8,
        )
        db.add(student)
        db.flush()

        # Subject + Topic + Book + Section + Assign + Task
        subj = db.query(Subject).filter(Subject.is_builtin.is_(True)).first()
        if not subj:
            subj = Subject(name="Test", order=999, is_builtin=False, teacher_id=teacher.id)
            db.add(subj); db.flush()
        topic = db.query(Topic).filter(Topic.subject_id == subj.id).first()
        if not topic:
            topic = Topic(name="Test konu", order=999, subject_id=subj.id)
            db.add(topic); db.flush()

        book = Book(
            name=f"API Test Kitap {PFX}",
            subject_id=subj.id,
            type=BookType.SORU_BANKASI,
            teacher_id=teacher.id,
        )
        db.add(book); db.flush()
        sec = BookSection(
            book_id=book.id,
            label="Bölüm 1",
            test_count=50,
            order=0,
            topic_id=topic.id,
        )
        db.add(sec); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()

        task = Task(
            student_id=student.id,
            date=date.today(),
            type=TaskType.TEST,
            title="API test görevi",
            status=TaskStatus.PENDING,
            order=0,
        )
        db.add(task); db.flush()
        item = TaskBookItem(
            task_id=task.id,
            book_id=book.id,
            book_section_id=sec.id,
            planned_count=10,
            completed_count=0,
        )
        db.add(item); db.flush()
        db.commit()
        return teacher.id, student.id, task.id


def _cleanup(teacher_id: int, student_id: int) -> None:
    from sqlalchemy import delete as sa_delete
    with SessionLocal() as db:
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_(
                db.query(Task.id).filter(Task.student_id == student_id)
            )
        ))
        db.execute(sa_delete(Task).where(Task.student_id == student_id))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == student_id))
        # Books, sections — silinir cascade ile teacher silinince
        # Önce öğrenci sil
        db.execute(sa_delete(User).where(User.id == student_id))
        db.execute(sa_delete(User).where(User.id == teacher_id))
        db.commit()


def _reset_rate_limit() -> None:
    """Test öncesi rate limiter cache'i sıfırla (önceki testten bakiye kalmasın)."""
    from app.services.rate_limit import get_login_limiter
    get_login_limiter().reset()


def main() -> int:
    print(f"\n=== API v1 smoke test (prefix={PFX}) ===")
    teacher_id, student_id, task_id = _seed_users()
    _reset_rate_limit()
    client = TestClient(app)

    try:
        # =====================================================================
        # STEP 1 — Ping (no auth)
        # =====================================================================
        print("\n--- STEP 1: ping ---")
        r = client.get("/api/v1/ping")
        check("ping 200", r.status_code == 200, f"got {r.status_code}")
        check("ping ok=true", r.json().get("ok") is True)

        # =====================================================================
        # STEP 2 — Login: wrong password
        # =====================================================================
        print("\n--- STEP 2: login (wrong password) ---")
        r = client.post(
            "/api/v1/auth/login",
            json={"email": TEACHER_EMAIL, "password": "wrong-password"},
        )
        check("wrong pw → 401", r.status_code == 401, f"got {r.status_code}")
        detail = r.json().get("detail", {})
        check(
            "wrong pw → code=invalid_credentials",
            detail.get("code") == "invalid_credentials",
            f"detail={detail}",
        )

        # =====================================================================
        # STEP 3 — Login: success
        # =====================================================================
        print("\n--- STEP 3: login (teacher) ---")
        r = client.post(
            "/api/v1/auth/login",
            json={"email": TEACHER_EMAIL, "password": PASSWORD},
        )
        check("teacher login 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        body = r.json() if r.status_code == 200 else {}
        teacher_access = body.get("tokens", {}).get("access_token")
        teacher_refresh = body.get("tokens", {}).get("refresh_token")
        check("access_token gelmiş", bool(teacher_access))
        check("refresh_token gelmiş", bool(teacher_refresh))
        check(
            "user.role=teacher",
            body.get("user", {}).get("role") == "teacher",
            f"user={body.get('user')}",
        )
        check(
            "access_expires_in == 3600",
            body.get("tokens", {}).get("access_expires_in") == 3600,
        )

        h_teacher = {"Authorization": f"Bearer {teacher_access}"}

        # =====================================================================
        # STEP 4 — /me with bearer
        # =====================================================================
        print("\n--- STEP 4: /me ---")
        r = client.get("/api/v1/me", headers=h_teacher)
        check("/me 200", r.status_code == 200, f"got {r.status_code}")
        check("/me email matches", r.json().get("email") == TEACHER_EMAIL)

        # =====================================================================
        # STEP 5 — /me missing token
        # =====================================================================
        r = client.get("/api/v1/me")
        check("/me without auth → 401", r.status_code == 401)
        check(
            "/me missing_token code",
            r.json().get("detail", {}).get("code") == "missing_token",
        )

        # =====================================================================
        # STEP 6 — /me bozuk token
        # =====================================================================
        r = client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-token"})
        check("/me bozuk token → 401", r.status_code == 401)
        check(
            "/me invalid_token code",
            r.json().get("detail", {}).get("code") == "invalid_token",
        )

        # =====================================================================
        # STEP 7 — /me with refresh token (wrong type)
        # =====================================================================
        r = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {teacher_refresh}"},
        )
        check("/me with refresh → 401", r.status_code == 401)
        check(
            "/me wrong_token_type code",
            r.json().get("detail", {}).get("code") == "wrong_token_type",
        )

        # =====================================================================
        # STEP 8 — /auth/refresh with refresh
        # =====================================================================
        print("\n--- STEP 8: refresh ---")
        r = client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {teacher_refresh}"},
        )
        check("refresh 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        new_access = r.json().get("access_token") if r.status_code == 200 else None
        check("new access_token issued", bool(new_access))

        # /auth/refresh access ile → wrong_token_type
        r = client.post("/api/v1/auth/refresh", headers=h_teacher)
        check("refresh with access → 401", r.status_code == 401)

        # =====================================================================
        # STEP 9 — Teacher endpoints
        # =====================================================================
        print("\n--- STEP 9: teacher endpoints ---")
        r = client.get("/api/v1/teacher/students", headers=h_teacher)
        check("teacher/students 200", r.status_code == 200, f"got {r.status_code}")
        students = r.json().get("students", [])
        check("öğrenci listede", any(s["id"] == student_id for s in students))

        r = client.get(f"/api/v1/teacher/students/{student_id}", headers=h_teacher)
        check("teacher/students/{id} 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            body = r.json()
            check(
                "detail student.id eşleşir",
                body.get("student", {}).get("id") == student_id,
            )

        # Cross access — başka öğretmen olmayan öğrenci_id 999999 → 404
        r = client.get("/api/v1/teacher/students/999999", headers=h_teacher)
        check("teacher/students/999999 → 404", r.status_code == 404)

        # =====================================================================
        # STEP 10 — Student endpoints (login as student first)
        # =====================================================================
        print("\n--- STEP 10: student login + endpoints ---")
        r = client.post(
            "/api/v1/auth/login",
            json={"email": STUDENT_EMAIL, "password": PASSWORD},
        )
        check("student login 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
        s_access = r.json().get("tokens", {}).get("access_token") if r.status_code == 200 else None
        h_student = {"Authorization": f"Bearer {s_access}"}

        r = client.get("/api/v1/student/today", headers=h_student)
        check("student/today 200", r.status_code == 200, f"got {r.status_code}")
        if r.status_code == 200:
            body = r.json()
            tasks = body.get("tasks", [])
            check("bugün 1 görev var", len(tasks) == 1, f"got {len(tasks)} tasks")
            check(
                "görev id matches",
                tasks and tasks[0]["id"] == task_id,
            )

        # Cross role — student'ın teacher endpoint'ine erişimi 403
        r = client.get("/api/v1/teacher/students", headers=h_student)
        check("student → teacher/students → 403", r.status_code == 403)

        # /student/focus/start → /end
        r = client.post(
            "/api/v1/student/focus/start",
            headers=h_student,
            json={"planned_minutes": 25, "kind": "work", "label": "smoke"},
        )
        check(
            "focus/start 200",
            r.status_code == 200,
            f"got {r.status_code}: {r.text[:200]}",
        )
        if r.status_code == 200:
            sid = r.json().get("id")
            check("session id var", bool(sid))
            r2 = client.post(
                f"/api/v1/student/focus/{sid}/end",
                headers=h_student,
                json={"actual_minutes": 25, "interrupted": False},
            )
            check(
                "focus/end 200",
                r2.status_code == 200,
                f"got {r2.status_code}: {r2.text[:200]}",
            )

        r = client.get("/api/v1/student/focus", headers=h_student)
        check("student/focus 200", r.status_code == 200)
        if r.status_code == 200:
            body = r.json()
            check(
                "work_minutes_today >= 25",
                body.get("work_minutes_today", 0) >= 25,
                f"got {body.get('work_minutes_today')}",
            )

        r = client.get("/api/v1/student/review", headers=h_student)
        check("student/review 200", r.status_code == 200)

        # Görev tamamla
        r = client.post(
            f"/api/v1/student/tasks/{task_id}/complete",
            headers=h_student,
        )
        check(
            "tasks/complete 200",
            r.status_code == 200,
            f"got {r.status_code}: {r.text[:200]}",
        )
        if r.status_code == 200:
            check(
                "task status COMPLETED",
                r.json().get("status") == "completed",
                f"got {r.json().get('status')}",
            )

        # =====================================================================
        # STEP 11 — CORS preflight
        # =====================================================================
        print("\n--- STEP 11: CORS preflight ---")
        r = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        check("OPTIONS preflight 200", r.status_code == 200, f"got {r.status_code}")
        check(
            "Access-Control-Allow-Origin header set",
            "access-control-allow-origin" in {k.lower() for k in r.headers.keys()},
        )

        # =====================================================================
        # STEP 12 — Rate limit
        # =====================================================================
        print("\n--- STEP 12: rate limit (login) ---")
        _reset_rate_limit()
        # User-level lockout 5 başarısızda devreye girer → 401/423 karışımı normal.
        # Test odağı: 11. istek 429 olmalı (rate limit IP-bazlı, lockout'tan bağımsız).
        # Farklı bir mail kullan ki kilitleme öğretmen hesabını etkilemesin.
        rl_email = f"{PFX}_rl@test.invalid"
        codes = []
        for i in range(11):
            rr = client.post(
                "/api/v1/auth/login",
                json={"email": rl_email, "password": "wrong-" + str(i)},
            )
            codes.append(rr.status_code)
        # 11. istek IP rate limit (429), user yok → öncekiler hep 401
        check(
            "ilk 10 istek 401 (user yok — lockout devreye girmez)",
            all(c == 401 for c in codes[:10]),
            f"codes={codes[:10]}",
        )
        check("11. istek 429", codes[10] == 429, f"codes={codes}")
        _reset_rate_limit()

        # =====================================================================
        # STEP 13 — Logout
        # =====================================================================
        print("\n--- STEP 13: logout ---")
        # Önceki step'lerden teacher hesabında lockout bakiyesi varsa temizle
        with SessionLocal() as db:
            tu = db.query(User).filter(User.id == teacher_id).first()
            tu.failed_login_count = 0
            tu.locked_until = None
            db.commit()
        # Yeni teacher login (rate limit reset edildi)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": TEACHER_EMAIL, "password": PASSWORD},
        )
        check("teacher login again 200", r.status_code == 200)
        if r.status_code == 200:
            tok = r.json()["tokens"]["access_token"]
            r2 = client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {tok}"},
            )
            check("logout 200", r2.status_code == 200)
            # Stateless — token hâlâ valid (blacklist yok). Bu beklenen davranış.
            r3 = client.get(
                "/api/v1/me",
                headers={"Authorization": f"Bearer {tok}"},
            )
            check(
                "logout sonrası /me hâlâ 200 (stateless)",
                r3.status_code == 200,
                "stateless logout — pwd_stamp ile gerçek revoke yapılır",
            )

        # =====================================================================
        # STEP 14 — Şifre değiştir → eski token invalid
        # =====================================================================
        print("\n--- STEP 14: pwd rotation → token revoke ---")
        # Yeni login → access al
        r = client.post(
            "/api/v1/auth/login",
            json={"email": TEACHER_EMAIL, "password": PASSWORD},
        )
        old_access = r.json()["tokens"]["access_token"]

        # Şifre stamp güncelle (gerçek change_password ile aynı sonuç)
        with SessionLocal() as db:
            u = db.query(User).filter(User.id == teacher_id).first()
            u.password_changed_at = datetime.now(timezone.utc)
            db.commit()

        r = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {old_access}"},
        )
        check(
            "pwd değişti → eski token 401",
            r.status_code == 401,
            f"got {r.status_code}",
        )
        check(
            "code=token_revoked",
            r.json().get("detail", {}).get("code") == "token_revoked",
            f"detail={r.json().get('detail')}",
        )

    finally:
        _cleanup(teacher_id, student_id)
        _reset_rate_limit()

    # =====================================================================
    # Özet
    # =====================================================================
    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} PASS ===")
    if failed:
        print(f"\n[!] {len(failed)} FAIL:")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("\n[OK] Tüm API v1 smoke check'leri geçti.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
