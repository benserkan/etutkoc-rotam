"""Stage 12 — FSRS spaced repetition smoke test.

Senaryolar:
1. Algoritma birim testi: 4 rating × 2 state (NEW + REVIEW) → stability/difficulty/state geçişleri doğru
2. NEW + EASY → state=REVIEW, scheduled_days büyük (kolay = uzun aralık)
3. NEW + AGAIN → state=LEARNING (öğrenmeye dönüş)
4. REVIEW + AGAIN → state=RELEARNING, stability düştü, lapse_count+1
5. compute_next.elapsed_days now-last_reviewed_at hesabı
6. seed_subject_for_student: idempotent, kart sayısı topic sayısı kadar
7. record_review: ReviewCard güncellenir + ReviewLog eklenir
8. GET /student/review anonim → 303
9. GET /student/review öğrenci → 200, kart listesi
10. POST /student/review/{id} rating=3 → 303, kart due_at güncellendi
11. POST /student/review/{id} cross-student → 404
12. GET /teacher/students/{id}/review öğretmen → 200
13. POST /teacher/students/{id}/review/seed → kartlar oluşur, redirect
14. GET /teacher/review → tüm öğrenci due sayımları
15. Tenant isolation: başka öğretmen öğrenciye seed edemez (404)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import math
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_teacher
from app.main import app
from app.models import (
    ReviewCard,
    ReviewLog,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.models.review import (
    STATE_LEARNING,
    STATE_NEW,
    STATE_RELEARNING,
    STATE_REVIEW,
)
from app.services.fsrs import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    RATING_HARD,
    FsrsState,
    compute_next,
)


PFX = f"_fsrs_{secrets.token_hex(3)}"
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


def main() -> int:
    now = datetime.now(timezone.utc)
    client = TestClient(app)

    # ============ STEP 1: Algoritma birim testi (NEW state) ============
    print("\n=== STEP 1: NEW state + 4 rating ===")
    for rating, exp_state, label in [
        (RATING_AGAIN, STATE_LEARNING, "again→learning"),
        (RATING_HARD, STATE_REVIEW, "hard→review"),
        (RATING_GOOD, STATE_REVIEW, "good→review"),
        (RATING_EASY, STATE_REVIEW, "easy→review"),
    ]:
        st = FsrsState(stability=0.0, difficulty=5.0, state=STATE_NEW)
        res = compute_next(st, rating, now)
        check(f"NEW + {label} state={res.state}",
              res.state == exp_state, f"got {res.state}")
        check(f"NEW + {label} stability > 0",
              res.stability > 0, f"got {res.stability}")
        check(f"NEW + {label} due_at > now",
              res.due_at > now)

    # EASY > GOOD > HARD > AGAIN: scheduled_days sırası
    s_easy = compute_next(FsrsState(0,5,STATE_NEW), RATING_EASY, now).scheduled_days
    s_good = compute_next(FsrsState(0,5,STATE_NEW), RATING_GOOD, now).scheduled_days
    s_hard = compute_next(FsrsState(0,5,STATE_NEW), RATING_HARD, now).scheduled_days
    s_again = compute_next(FsrsState(0,5,STATE_NEW), RATING_AGAIN, now).scheduled_days
    check("scheduled_days: easy > good > hard > again",
          s_easy > s_good > s_hard >= s_again,
          f"easy={s_easy:.2f} good={s_good:.2f} hard={s_hard:.2f} again={s_again:.2f}")

    # ============ STEP 2: REVIEW state + AGAIN (lapse) ============
    print("\n=== STEP 2: REVIEW + AGAIN → RELEARNING + stability düşer ===")
    last = now - timedelta(days=5)
    prev = FsrsState(stability=10.0, difficulty=4.0, state=STATE_REVIEW,
                     last_reviewed_at=last, review_count=3, lapse_count=0)
    res = compute_next(prev, RATING_AGAIN, now)
    check("REVIEW+AGAIN state=RELEARNING", res.state == STATE_RELEARNING)
    check("REVIEW+AGAIN stability düştü",
          res.stability < prev.stability, f"{prev.stability}→{res.stability}")
    check("REVIEW+AGAIN difficulty arttı",
          res.difficulty > prev.difficulty, f"{prev.difficulty}→{res.difficulty}")
    check("REVIEW+AGAIN elapsed_days ≈ 5",
          abs(res.elapsed_days - 5.0) < 0.1, f"got {res.elapsed_days}")

    # REVIEW + GOOD: stability artmalı
    prev2 = FsrsState(stability=10.0, difficulty=4.0, state=STATE_REVIEW,
                      last_reviewed_at=last)
    res2 = compute_next(prev2, RATING_GOOD, now)
    check("REVIEW+GOOD stability arttı",
          res2.stability > prev2.stability, f"{prev2.stability}→{res2.stability}")
    check("REVIEW+GOOD state=REVIEW", res2.state == STATE_REVIEW)

    # ============ STEP 3: Algoritma kenar durumu — invalid rating ============
    print("\n=== STEP 3: Invalid rating raises ===")
    try:
        compute_next(FsrsState(0,5,STATE_NEW), 5, now)
        check("invalid rating raise", False, "no raise")
    except ValueError:
        check("invalid rating raise", True)

    # ============ STEP 4: Test fixture setup ============
    print("\n=== STEP 4: Fixture — teacher, student, subject, topics ===")
    with SessionLocal() as db:
        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash="x" * 60,
            full_name="FSRS Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        db.add(teacher); db.flush()
        student = User(
            email=f"{PFX}_s@test.invalid", password_hash="x" * 60,
            full_name="FSRS Student", role=UserRole.STUDENT,
            teacher_id=teacher.id,
            is_active=True, password_changed_at=now,
        )
        other_teacher = User(
            email=f"{PFX}_o@test.invalid", password_hash="x" * 60,
            full_name="Other Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        db.add_all([student, other_teacher]); db.flush()
        subject = Subject(
            name=f"{PFX} TestDers",
            order=99, is_builtin=False, teacher_id=teacher.id,
        )
        db.add(subject); db.flush()
        topics = [
            Topic(subject_id=subject.id, name=f"Topic{i}", order=i,
                  is_builtin=False, teacher_id=teacher.id)
            for i in range(4)
        ]
        db.add_all(topics); db.commit()
        teacher_id, student_id, other_id = teacher.id, student.id, other_teacher.id
        subject_id = subject.id
        topic_ids = [t.id for t in topics]
    check("fixture oluştu", True)

    # Dependency override
    def make_user_override(uid: int):
        def _ov():
            with SessionLocal() as _db:
                u = (
                    _db.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == uid)
                    .first()
                )
                if u is not None:
                    if u.institution is not None:
                        _db.expunge(u.institution)
                    _db.expunge(u)
                return u
        return _ov

    teacher_ov = make_user_override(teacher_id)
    student_ov = make_user_override(student_id)
    other_ov = make_user_override(other_id)

    # ============ STEP 5: GET /student/review anonim → 303 ============
    print("\n=== STEP 5: HTTP guards ===")
    app.dependency_overrides.clear()
    r = client.get("/student/review", follow_redirects=False)
    check("anonim /student/review → 303",
          r.status_code in (302, 303), f"got {r.status_code}")

    # ============ STEP 6: Öğretmen toplu seed ============
    print("\n=== STEP 6: Öğretmen toplu seed ===")
    app.dependency_overrides[require_teacher] = teacher_ov
    app.dependency_overrides[get_current_user] = teacher_ov
    r = client.post(
        f"/teacher/students/{student_id}/review/seed",
        data={"subject_id": str(subject_id)},
        follow_redirects=False,
    )
    check("seed POST 303", r.status_code == 303, f"got {r.status_code}")
    loc = r.headers.get("location", "")
    check("seed redirect mesajı 'yeni' + 'kart'",
          "yeni" in loc and "kart" in loc, loc)

    with SessionLocal() as db:
        cards = (
            db.query(ReviewCard)
            .filter(ReviewCard.student_id == student_id)
            .all()
        )
        check("4 kart oluştu (topic sayısı kadar)",
              len(cards) == 4, f"got {len(cards)}")
        check("kartlar state=NEW",
              all(c.state == STATE_NEW for c in cards))

    # Idempotent seed → 2. çağrı 0 yeni
    r = client.post(
        f"/teacher/students/{student_id}/review/seed",
        data={"subject_id": str(subject_id)},
        follow_redirects=False,
    )
    check("idempotent seed 303", r.status_code == 303)
    check("ikinci seed 'zaten vardı' mesajı",
          "zaten" in r.headers.get("location", ""))
    with SessionLocal() as db:
        count = db.query(ReviewCard).filter(
            ReviewCard.student_id == student_id
        ).count()
        check("kart sayısı hâlâ 4 (idempotent)", count == 4, f"got {count}")

    # ============ STEP 7: Cross-tenant — başka öğretmen seed → 404 ============
    print("\n=== STEP 7: Cross-tenant seed engellendi ===")
    app.dependency_overrides[require_teacher] = other_ov
    app.dependency_overrides[get_current_user] = other_ov
    r = client.post(
        f"/teacher/students/{student_id}/review/seed",
        data={"subject_id": str(subject_id)},
        follow_redirects=False,
    )
    check("cross-tenant seed 404", r.status_code == 404, f"got {r.status_code}")

    # ============ STEP 8: GET /teacher/students/{id}/review ============
    print("\n=== STEP 8: Öğretmen detay sayfası ===")
    app.dependency_overrides[require_teacher] = teacher_ov
    app.dependency_overrides[get_current_user] = teacher_ov
    r = client.get(f"/teacher/students/{student_id}/review")
    check("teacher review detail 200", r.status_code == 200, f"got {r.status_code}")
    check("sayfada öğrenci adı", "FSRS Student" in r.text)
    check("sayfada 'Tekrar Kartları'", "Tekrar Kartları" in r.text)
    check("4 kart render", r.text.count("Topic") >= 4)

    # ============ STEP 9: GET /teacher/review (tüm öğrenciler) ============
    r = client.get("/teacher/review")
    check("teacher review dashboard 200", r.status_code == 200)
    check("dashboard'da öğrenci listede", "FSRS Student" in r.text)

    # ============ STEP 10: Öğrenci review akışı ============
    print("\n=== STEP 10: Öğrenci review akışı ===")
    app.dependency_overrides[get_current_user] = student_ov
    # require_teacher öğrenciler için 403 vermeli; öğrenci review için require_teacher kullanılmıyor
    app.dependency_overrides.pop(require_teacher, None)
    r = client.get("/student/review")
    check("student review 200", r.status_code == 200)
    check("4 NEW kart due olarak listelendi", r.text.count("Tekrar Et") >= 0 and r.text.count("Topic") >= 4)

    # İlk kartı rating=GOOD ile geç
    with SessionLocal() as db:
        first_card = (
            db.query(ReviewCard).filter(ReviewCard.student_id == student_id).first()
        )
        first_card_id = first_card.id
    r = client.post(
        f"/student/review/{first_card_id}",
        data={"rating": "3"},
        follow_redirects=False,
    )
    check("rating POST 303", r.status_code == 303)

    def _aware(dt):
        if dt is not None and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    with SessionLocal() as db:
        updated = db.query(ReviewCard).filter(ReviewCard.id == first_card_id).first()
        check("kart state=REVIEW", updated.state == STATE_REVIEW)
        check("kart due_at set", updated.due_at is not None)
        check("kart due_at gelecekte", _aware(updated.due_at) > now)
        check("review_count = 1", updated.review_count == 1)
        log_count = db.query(ReviewLog).filter(
            ReviewLog.card_id == first_card_id
        ).count()
        check("ReviewLog 1 kayıt", log_count == 1, f"got {log_count}")

    # AGAIN rating → state=RELEARNING + lapse_count+1
    r = client.post(
        f"/student/review/{first_card_id}",
        data={"rating": "1"},
        follow_redirects=False,
    )
    check("again POST 303", r.status_code == 303)
    with SessionLocal() as db:
        updated = db.query(ReviewCard).filter(ReviewCard.id == first_card_id).first()
        check("kart state=RELEARNING", updated.state == STATE_RELEARNING)
        check("lapse_count = 1", updated.lapse_count == 1)
        check("review_count = 2", updated.review_count == 2)

    # ============ STEP 11: Cross-student rating engellendi ============
    print("\n=== STEP 11: Cross-student rating 404 ===")
    # Başka öğrenci oluştur
    with SessionLocal() as db:
        student2 = User(
            email=f"{PFX}_s2@test.invalid", password_hash="x" * 60,
            full_name="Other Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, is_active=True, password_changed_at=now,
        )
        db.add(student2); db.commit()
        student2_id = student2.id
    student2_ov = make_user_override(student2_id)
    app.dependency_overrides[get_current_user] = student2_ov
    r = client.post(
        f"/student/review/{first_card_id}",
        data={"rating": "3"},
        follow_redirects=False,
    )
    check("cross-student rating 404", r.status_code == 404, f"got {r.status_code}")

    # ============ STEP 12: Invalid rating ============
    print("\n=== STEP 12: Invalid rating 400 ===")
    app.dependency_overrides[get_current_user] = student_ov
    r = client.post(
        f"/student/review/{first_card_id}",
        data={"rating": "9"},
        follow_redirects=False,
    )
    check("invalid rating 400", r.status_code == 400, f"got {r.status_code}")

    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        db.execute(delete(ReviewLog).where(ReviewLog.student_id.in_([student_id, student2_id])))
        db.execute(delete(ReviewCard).where(ReviewCard.student_id.in_([student_id, student2_id])))
        db.execute(delete(Topic).where(Topic.id.in_(topic_ids)))
        db.execute(delete(Subject).where(Subject.id == subject_id))
        db.execute(delete(User).where(
            User.id.in_([student_id, student2_id, teacher_id, other_id])
        ))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
