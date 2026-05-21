"""API v2 /student secondary features smoke (Dalga 2 Paket 4).

Focus (pomodoro) + DNA + Review (FSRS) + Goals — yardımcı ama etkileşimi yüksek
özellikler. Mevcut Jinja /student/{focus,dna,review,goals} JSON karşılığı.

Senaryolar (12):
   1. GET /focus      → aktif yok + bugün özeti + streak + puan döner
   2. POST /focus/start → MutationResponse[FocusSession] + invalidate keys
   3. POST /focus/start ikinci kez → 409 focus_session_already_open
   4. POST /focus/{id}/stop → MutationResponse + actual_minutes hesaplanır
   5. POST /focus/{id}/stop zaten kapalı → 400 focus_session_already_closed
   6. POST /focus/9999/cancel → 404 focus_session_not_found
   7. GET /dna → has_enough_data false ama 200 + 7×24 heatmap + chronotype
   8. GET /review → due_cards + breakdown (yeni kart due_now sayar)
   9. POST /review/{id}/rate rating=3 → state ilerler + invalidate keys
  10. POST /review/{id}/rate rating=5 → 422 invalid_rating
  11. GET /goals → kişisel hedefler + summary; POST /goals create → 200
  12. POST /goals/{id}/toggle achieved=True → status=achieved + invalidate

Test verisi: secrets prefix + cleanup; mevcut hesaplara dokunulmaz.
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
    PomodoroSession,
    ReviewCard,
    ReviewLog,
    StudentBadge,
    StudentGoal,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2ss_{secrets.token_hex(3)}"
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


def _seed() -> dict:
    """Test verisi: 1 öğretmen + 1 öğrenci + 1 subject + 1 topic + 1 review card."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Sec Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_free",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Sec Test Öğrenci", role=UserRole.STUDENT, is_active=True,
            grade_level=8,
        )
        db.add_all([teacher, student])
        db.flush()
        student.teacher_id = teacher.id

        subj = Subject(name=f"V2Sec Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name=f"V2Sec Konu {PFX}", order=0, subject_id=subj.id)
        db.add(topic); db.flush()

        # Bir review kartı (state=new, due_at NULL → her zaman due)
        card = ReviewCard(
            student_id=student.id, topic_id=topic.id,
            stability=0.0, difficulty=5.0, state="new",
        )
        db.add(card); db.flush()

        db.commit()
        return {
            "teacher_id": teacher.id,
            "student_id": student.id,
            "subject_id": subj.id,
            "topic_id": topic.id,
            "card_id": card.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        student_id = seed["student_id"]
        db.execute(sa_delete(StudentBadge).where(StudentBadge.student_id == student_id))
        db.execute(sa_delete(ReviewLog).where(ReviewLog.student_id == student_id))
        db.execute(sa_delete(ReviewCard).where(ReviewCard.student_id == student_id))
        db.execute(sa_delete(PomodoroSession).where(PomodoroSession.student_id == student_id))
        # Goal'lar (varsa) — children → parent (CASCADE) ama açıkça da silelim
        db.execute(sa_delete(StudentGoal).where(StudentGoal.student_id == student_id))
        db.execute(sa_delete(Topic).where(Topic.id == seed["topic_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_([student_id, seed["teacher_id"]])))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /student secondary smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded student={seed['student_id']} card={seed['card_id']}\n")

    try:
        client = TestClient(app)
        _login_v2(client, STUDENT_EMAIL)

        # ===== 1. GET /focus baseline =====
        r = client.get("/api/v2/student/focus")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("active_session") is None
            and "today" in body
            and "streak_days" in body
            and "points" in body
        )
        check(
            "1. GET /focus baseline",
            ok,
            f"status={r.status_code} keys={list(body.keys())[:6]}",
        )

        # ===== 2. POST /focus/start happy path =====
        r = client.post(
            "/api/v2/student/focus/start",
            json={"planned_minutes": 25, "kind": "work", "label": "Matematik"},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        invalidate = body.get("invalidate", [])
        session_id = data.get("id")
        ok = (
            r.status_code == 200
            and data.get("is_active") is True
            and data.get("kind") == "work"
            and data.get("planned_minutes") == 25
            and any(":focus" in k for k in invalidate)
            and any(":summary:" in k for k in invalidate)
        )
        check(
            "2. POST /focus/start happy",
            ok,
            f"status={r.status_code} active={data.get('is_active')} invalidate={invalidate}",
        )

        # ===== 3. POST /focus/start ikinci kez → 409 =====
        r = client.post(
            "/api/v2/student/focus/start",
            json={"planned_minutes": 10, "kind": "work"},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "focus_session_already_open"
        )
        check(
            "3. /focus/start zaten açık → 409",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 4. POST /focus/{id}/stop happy =====
        r = client.post(
            f"/api/v2/student/focus/{session_id}/stop",
            json={"actual_minutes": 20, "interrupted": False},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("is_active") is False
            and data.get("actual_minutes") == 20
            and data.get("interrupted") is False
        )
        check(
            "4. /focus/{id}/stop happy",
            ok,
            f"status={r.status_code} active={data.get('is_active')} actual={data.get('actual_minutes')}",
        )

        # ===== 5. POST /focus/{id}/stop zaten kapalı → 400 =====
        r = client.post(
            f"/api/v2/student/focus/{session_id}/stop",
            json={"actual_minutes": 5},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 400
            and body.get("detail", {}).get("code") == "focus_session_already_closed"
        )
        check(
            "5. /focus stop zaten kapalı → 400",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 6. POST /focus/9999999/cancel → 404 =====
        r = client.post("/api/v2/student/focus/9999999/cancel")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "focus_session_not_found"
        )
        check(
            "6. /focus/9999999/cancel → 404",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 7. GET /dna baseline =====
        r = client.get("/api/v2/student/dna")
        body = r.json() if r.text else {}
        # heatmap 7 satır × 24 sütun olmalı
        heatmap_ok = (
            isinstance(body.get("heatmap"), list)
            and len(body["heatmap"]) == 7
            and all(isinstance(row, list) and len(row) == 24 for row in body["heatmap"])
        )
        ok = (
            r.status_code == 200
            and "chronotype" in body
            and "burnout_risk_level" in body
            and "burnout_signals" in body
            and heatmap_ok
        )
        check(
            "7. GET /dna baseline",
            ok,
            f"status={r.status_code} chronotype={body.get('chronotype')} heatmap_ok={heatmap_ok}",
        )

        # ===== 8. GET /review baseline =====
        r = client.get("/api/v2/student/review")
        body = r.json() if r.text else {}
        due = body.get("due_cards", [])
        bd = body.get("breakdown", {})
        ok = (
            r.status_code == 200
            and any(c.get("id") == seed["card_id"] for c in due)
            and bd.get("total", 0) >= 1
            and bd.get("due_now", 0) >= 1
        )
        check(
            "8. GET /review baseline",
            ok,
            f"status={r.status_code} due_count={len(due)} breakdown={bd}",
        )

        # ===== 9. POST /review/{id}/rate rating=3 → state ilerler =====
        r = client.post(
            f"/api/v2/student/review/{seed['card_id']}/rate",
            json={"rating": 3},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        invalidate = body.get("invalidate", [])
        ok = (
            r.status_code == 200
            and data.get("review_count", 0) >= 1
            and data.get("state") in ("learning", "review")
            and any(":review" in k for k in invalidate)
            and any(":badges" in k for k in invalidate)
        )
        check(
            "9. /review/{id}/rate rating=3 → state ilerler",
            ok,
            f"status={r.status_code} state={data.get('state')} count={data.get('review_count')} invalidate={invalidate}",
        )

        # ===== 10. POST /review/{id}/rate rating=5 → 422 =====
        r = client.post(
            f"/api/v2/student/review/{seed['card_id']}/rate",
            json={"rating": 5},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "invalid_rating"
        )
        check(
            "10. /review rate=5 → 422",
            ok,
            f"status={r.status_code} code={body.get('detail', {}).get('code')}",
        )

        # ===== 11. GET /goals baseline + POST /goals create =====
        r0 = client.get("/api/v2/student/goals")
        body0 = r0.json() if r0.text else {}
        items_before = body0.get("items", [])
        r = client.post(
            "/api/v2/student/goals",
            json={
                "title": "Bu hafta 25 test çöz",
                "kind": "weekly",
                "target_value": 25,
                "current_value": 0,
                "unit": "test",
                "target_date": None,
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        goal_id = data.get("id")
        invalidate = body.get("invalidate", [])
        # Listeyi tekrar çekip yeni hedefin geldiğini doğrula
        r2 = client.get("/api/v2/student/goals")
        items_after = r2.json().get("items", [])
        ok = (
            r0.status_code == 200
            and r.status_code == 200
            and data.get("kind") == "weekly"
            and data.get("status") == "active"
            and goal_id is not None
            and any(g.get("id") == goal_id for g in items_after)
            and len(items_after) == len(items_before) + 1
            and any(":goals" in k for k in invalidate)
        )
        check(
            "11. GET /goals + POST /goals create",
            ok,
            f"create_status={r.status_code} kind={data.get('kind')} list_delta={len(items_after) - len(items_before)} invalidate={invalidate}",
        )

        # ===== 12. POST /goals/{id}/toggle achieved=True =====
        r = client.post(
            f"/api/v2/student/goals/{goal_id}/toggle",
            json={"achieved": True},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        invalidate = body.get("invalidate", [])
        ok = (
            r.status_code == 200
            and data.get("status") == "achieved"
            and data.get("achieved_at") is not None
            and any(":goals" in k for k in invalidate)
        )
        check(
            "12. /goals/{id}/toggle achieved=True",
            ok,
            f"status={r.status_code} goal_status={data.get('status')} achieved_at={data.get('achieved_at')}",
        )

    finally:
        _cleanup(seed)
        get_login_limiter().reset()
        print("\n  cleanup OK\n")

    total = passed + len(failed)
    print(f"\n=== SONUÇ: {passed}/{total} PASS ===")
    if failed:
        print("\nFAILED:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
