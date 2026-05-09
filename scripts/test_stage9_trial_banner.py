"""Stage 9 (Faz 2.4) — Trial banner + upgrade required smoke test.

Senaryolar:
1. Trial aktif solo teacher → request.state.trial_banner doludur, banner HTML'de
2. Trial bitmiş solo teacher → banner None
3. Trial aktif kurum (institution_admin'in görmesi) → banner görünür
4. Anonim → banner None
5. Solo Free öğretmen 4. öğrenciyi eklerken → 402 + upgrade_required template
6. Solo Pro öğretmen 16. öğrenci → 402 + upgrade_required (Elite önerisi)
7. Solo Elite öğretmen 100 öğrenci ekleyebilir (sınırsız)
8. Trial aktif solo teacher (sınırsız) → 4. öğrenci eklemek OK
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user
from app.main import app
from app.models import (
    Institution,
    PlanChangeHistory,
    User,
    UserRole,
)
from app.services.plans import (
    SOLO_ELITE,
    SOLO_FREE,
    SOLO_PRO,
    check_solo_student_quota,
    compute_trial_banner,
    count_solo_students,
    solo_student_limit,
    start_solo_trial,
)


PFX = f"_tb_{secrets.token_hex(3)}"
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

    # --- SEED ---
    print("\n=== SEED ===")
    with SessionLocal() as db:
        # Trial aktif teacher
        t_trial = User(
            email=f"{PFX}_trial@test.invalid", password_hash="x" * 60,
            full_name="Trial Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan="free",
        )
        # Trial bitmiş teacher (solo_free)
        t_free = User(
            email=f"{PFX}_free@test.invalid", password_hash="x" * 60,
            full_name="Free Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan=SOLO_FREE,
        )
        # Pro teacher
        t_pro = User(
            email=f"{PFX}_pro@test.invalid", password_hash="x" * 60,
            full_name="Pro Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan=SOLO_PRO,
        )
        # Elite teacher
        t_elite = User(
            email=f"{PFX}_elite@test.invalid", password_hash="x" * 60,
            full_name="Elite Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan=SOLO_ELITE,
        )
        # Kurum + admin (trial aktif)
        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            plan="institution_trial", is_active=True,
        )
        db.add_all([t_trial, t_free, t_pro, t_elite, inst]); db.flush()
        ids = (t_trial.id, t_free.id, t_pro.id, t_elite.id)
        inst_id = inst.id
        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash="x" * 60,
            full_name="Inst Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        db.add(admin); db.flush()
        admin_id = admin.id

        # Trial aktive et
        start_solo_trial(db, user=db.get(User, t_trial.id))
        # Inst trial'ı set et (manuel)
        i = db.get(Institution, inst_id)
        i.trial_ends_at = now + timedelta(days=20)
        i.post_trial_plan = "institution_free"
        db.commit()

    t_trial_id, t_free_id, t_pro_id, t_elite_id = ids
    print(f"  trial={t_trial_id}, free={t_free_id}, pro={t_pro_id}, elite={t_elite_id}, admin={admin_id}")

    # ============ STEP 1: compute_trial_banner — trial aktif solo ============
    print("\n=== STEP 1: compute_trial_banner ===")
    with SessionLocal() as db:
        u = db.get(User, t_trial_id)
        banner = compute_trial_banner(db, user=u, now=now)
        check("trial aktif solo → banner var", banner is not None)
        if banner:
            check("kind = user", banner["kind"] == "user")
            check("days_left ≈ 14", 13 <= banner["days_left"] <= 14)
            check("plan_label '14 Günlük Pro Deneme'",
                  "Pro Deneme" in banner["plan_label"])
            check("post_trial_label 'Solo Ücretsiz'",
                  "Ücretsiz" in banner["post_trial_label"])
            check("is_critical False (14 gün > 3)", not banner["is_critical"])

    # ============ STEP 2: trial bitmiş solo → None ============
    print("\n=== STEP 2: trial bitmiş solo → None ===")
    with SessionLocal() as db:
        u = db.get(User, t_free_id)
        banner = compute_trial_banner(db, user=u, now=now)
        check("solo_free user için banner None", banner is None)

    # ============ STEP 3: kurum trial — admin için banner ============
    print("\n=== STEP 3: kurum trial admin için ===")
    with SessionLocal() as db:
        u = db.get(User, admin_id)
        banner = compute_trial_banner(db, user=u, now=now)
        check("inst admin banner var", banner is not None)
        if banner:
            check("kind = institution", banner["kind"] == "institution")
            check("post_trial_label 'Kurum Tanıma'",
                  "Kurum Tanıma" in banner["post_trial_label"])

    # ============ STEP 4: anonim user → None ============
    print("\n=== STEP 4: anonim user → None ===")
    with SessionLocal() as db:
        banner = compute_trial_banner(db, user=None, now=now)
        check("None user → banner None", banner is None)

    # ============ STEP 5: trial son 3 günde → critical ============
    print("\n=== STEP 5: son 3 gün → is_critical True ===")
    with SessionLocal() as db:
        u = db.get(User, t_trial_id)
        # Trial sonunu 2 güne çek
        u.trial_ends_at = now + timedelta(days=2)
        db.commit()

    with SessionLocal() as db:
        u = db.get(User, t_trial_id)
        banner = compute_trial_banner(db, user=u, now=now)
        check("days_left = 2", banner and banner["days_left"] == 2)
        check("is_critical True", banner and banner["is_critical"] is True)

    # ============ STEP 6: solo_student_limit ============
    print("\n=== STEP 6: solo_student_limit ===")
    check("solo_free = 3", solo_student_limit(SOLO_FREE) == 3)
    check("solo_pro = 15", solo_student_limit(SOLO_PRO) == 15)
    check("solo_elite = -1 (sınırsız)", solo_student_limit(SOLO_ELITE) == -1)
    check("trial = -1 (pro deneyim)",
          solo_student_limit("solo_trial") == -1)

    # ============ STEP 7: check_solo_student_quota — solo_free ile 4. öğrenci ============
    print("\n=== STEP 7: check_solo_student_quota solo_free ===")
    # 3 öğrenci ekle
    with SessionLocal() as db:
        teacher = db.get(User, t_free_id)
        for i in range(3):
            s = User(
                email=f"{PFX}_free_s{i}@test.invalid", password_hash="x" * 60,
                full_name=f"Free S{i}", role=UserRole.STUDENT,
                institution_id=None, teacher_id=t_free_id,
                is_active=True, password_changed_at=now,
            )
            db.add(s)
        db.commit()

    with SessionLocal() as db:
        teacher = db.get(User, t_free_id)
        check("count_solo_students = 3",
              count_solo_students(db, teacher_id=t_free_id) == 3)
        result = check_solo_student_quota(db, teacher=teacher, extra_count=1)
        check("4. öğrenci → ok = False", result.ok is False)
        check("plan_code = solo_free", result.plan_code == SOLO_FREE)
        check("current = 3", result.current == 3)
        check("limit = 3", result.limit == 3)
        check("upgrade_target_code = solo_pro",
              result.upgrade_target_code == SOLO_PRO)

    # ============ STEP 8: HTTP — solo_free 4. öğrenci → upgrade_required ============
    print("\n=== STEP 8: HTTP solo_free 4. öğrenci ===")
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

    client = TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = make_user_override(t_free_id)
    r = client.post(
        "/teacher/students",
        data={"full_name": "Yeni Öğrenci", "email": f"{PFX}_new@test.invalid",
              "grade": "8", "track": "", "graduate_mode": ""},
        follow_redirects=False,
    )
    check("solo_free + 4. öğrenci → 402",
          r.status_code == 402, f"got {r.status_code}")
    body = r.text
    check("upgrade_required template render",
          "Limiti" in body or "Plan Yetersiz" in body)
    check("Solo Pro upgrade kart",
          "Solo Pro" in body)
    check("mevcut plan 'Solo Ücretsiz'",
          "Solo Ücretsiz" in body)

    # Yeni öğrenci OLUŞTURULMADI — DB count hâlâ 3
    with SessionLocal() as db:
        check("4. öğrenci DB'ye yazılmadı",
              count_solo_students(db, teacher_id=t_free_id) == 3)
    app.dependency_overrides.clear()

    # ============ STEP 9: solo_pro 16. öğrenci ============
    print("\n=== STEP 9: solo_pro 16. öğrenci ===")
    with SessionLocal() as db:
        teacher = db.get(User, t_pro_id)
        for i in range(15):
            s = User(
                email=f"{PFX}_pro_s{i}@test.invalid", password_hash="x" * 60,
                full_name=f"Pro S{i}", role=UserRole.STUDENT,
                institution_id=None, teacher_id=t_pro_id,
                is_active=True, password_changed_at=now,
            )
            db.add(s)
        db.commit()

    with SessionLocal() as db:
        teacher = db.get(User, t_pro_id)
        result = check_solo_student_quota(db, teacher=teacher, extra_count=1)
        check("solo_pro 16. → ok=False", not result.ok)
        check("upgrade_target = solo_elite",
              result.upgrade_target_code == SOLO_ELITE)

    # ============ STEP 10: solo_elite sınırsız ============
    print("\n=== STEP 10: solo_elite sınırsız ===")
    with SessionLocal() as db:
        teacher = db.get(User, t_elite_id)
        result = check_solo_student_quota(db, teacher=teacher, extra_count=100)
        check("elite + 100 → ok=True", result.ok)
        check("limit = -1 (sınırsız)", result.limit == -1)
        check("upgrade_target_code None", result.upgrade_target_code is None)

    # ============ STEP 11: Trial aktif solo → sınırsız ============
    print("\n=== STEP 11: Trial aktif → sınırsız ===")
    with SessionLocal() as db:
        teacher = db.get(User, t_trial_id)
        # 50 öğrenci ekle
        for i in range(50):
            s = User(
                email=f"{PFX}_trial_s{i}@test.invalid", password_hash="x" * 60,
                full_name=f"Trial S{i}", role=UserRole.STUDENT,
                institution_id=None, teacher_id=t_trial_id,
                is_active=True, password_changed_at=now,
            )
            db.add(s)
        db.commit()

    with SessionLocal() as db:
        teacher = db.get(User, t_trial_id)
        result = check_solo_student_quota(db, teacher=teacher, extra_count=1)
        check("trial 51. → ok=True (sınırsız)", result.ok)
        check("plan_code = solo_trial", result.plan_code == "solo_trial")

    # ============ STEP 12: Banner middleware'in HTML'e enjekte ettiği ============
    print("\n=== STEP 12: Banner middleware enjekte HTML ===")
    # Doğrudan session signed cookie üretip TestClient'a ver — middleware
    # request.session.get("user_id")'yi orada okuyacak.
    import json as _json
    import base64
    from itsdangerous import TimestampSigner
    from app.config import settings as _settings

    signer = TimestampSigner(_settings.session_secret)
    payload = _json.dumps({"user_id": t_trial_id}).encode("utf-8")
    cookie_value = signer.sign(base64.b64encode(payload)).decode("ascii")

    # TestClient cookie ekle
    client.cookies.set("session", cookie_value)
    app.dependency_overrides[get_current_user] = make_user_override(t_trial_id)
    r = client.get("/teacher/students")
    check("teacher/students 200", r.status_code == 200)
    body = r.text
    check("trial-banner CSS class HTML'de",
          "trial-banner" in body, "session middleware user_id okumamış olabilir")
    check("banner mesajı 'Pro Deneme'",
          "Pro Deneme" in body)
    client.cookies.clear()
    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        # Tüm test öğrencilerini sil — teacher_id eşleşeni
        db.execute(delete(User).where(User.email.like(f"{PFX}_%@test.invalid")))
        db.execute(delete(PlanChangeHistory).where(
            PlanChangeHistory.owner_id.in_(list(ids) + [admin_id, inst_id])
        ))
        db.execute(delete(Institution).where(Institution.id == inst_id))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
