"""Stage 9 (Faz 2.5) — Akademik yıl + yaz pause + 60g garantisi smoke test.

Senaryolar:
1. current_academic_year_bounds — şu an Eylül-Haziran yıl sınırı
2. is_summer_window — Tem-Ağu için True
3. switch_to_academic_year — kurum aylıktan yıllığa
4. pause_for_summer (yaz dışında) → ValueError
5. pause_for_summer (yaz içinde, mock) — pause_until set
6. resume_from_pause — kurum geri akademik yıla
7. cron_resume_paused_subscriptions — pause_until geçmişse otomatik resume
8. enable_guarantee — flag açık + audit
9. evaluate_guarantee — 60g'den önce → not yet
10. evaluate_guarantee — 60g sonrası, eşik altı → triggered
11. apply_guarantee_extension — period_end +30, guarantee_extended_at set
12. apply_guarantee_extension idempotent (zaten uzatılmışsa no-op)
13. cron_evaluate_guarantees — toplu cron tetik
14. HTTP /institution/subscription — sayfa render
15. HTTP /institution/subscription/switch-academic-year POST
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_institution_admin
from app.main import app
from app.models import (
    Institution,
    PlanChangeHistory,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.subscription import (
    GUARANTEE_PERIOD_DAYS,
    KIND_ACADEMIC_YEAR,
    KIND_MONTHLY,
    KIND_PAUSED,
    apply_guarantee_extension,
    cron_evaluate_guarantees,
    cron_resume_paused_subscriptions,
    current_academic_year_bounds,
    enable_guarantee,
    evaluate_guarantee,
    get_status,
    is_paused,
    is_summer_window,
    pause_for_summer,
    resume_from_pause,
    switch_to_academic_year,
)


PFX = f"_sub_{secrets.token_hex(3)}"
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
        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            plan="dershane_pro", is_active=True,
            subscription_kind=KIND_MONTHLY,
        )
        db.add(inst); db.flush()
        inst_id = inst.id
        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash="x" * 60,
            full_name="Sub Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        # Bir kaç öğretmen + öğrenci ile garanti senaryosu kurabilelim
        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash="x" * 60,
            full_name="Sub Teacher", role=UserRole.TEACHER,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        db.add_all([admin, teacher]); db.flush()
        admin_id, teacher_id = admin.id, teacher.id

        # 5 öğrenci
        students = []
        for i in range(5):
            s = User(
                email=f"{PFX}_s{i}@test.invalid", password_hash="x" * 60,
                full_name=f"Sub Student {i}", role=UserRole.STUDENT,
                institution_id=inst_id, teacher_id=teacher_id,
                is_active=True, password_changed_at=now,
            )
            students.append(s)
        db.add_all(students); db.commit()
        student_ids = [s.id for s in students]
        print(f"  inst={inst_id}, admin={admin_id}, teacher={teacher_id}, students={len(student_ids)}")

    # ============ STEP 1: current_academic_year_bounds ============
    print("\n=== STEP 1: current_academic_year_bounds ===")
    start, end = current_academic_year_bounds(now)
    check("start ayı = Eylül", start.month == 9)
    check("start günü = 1", start.day == 1)
    check("end ayı = Haziran", end.month == 6)
    check("end günü = 30", end.day == 30)
    check("end yıl = start yıl + 1", end.year == start.year + 1)

    # Mocked: Ocak ayı (akademik yıl orta)
    jan = datetime(2026, 1, 15, tzinfo=timezone.utc)
    s2, e2 = current_academic_year_bounds(jan)
    check("Ocak'ta start = 2025-09-01",
          s2 == date(2025, 9, 1))
    check("Ocak'ta end = 2026-06-30",
          e2 == date(2026, 6, 30))

    # Mocked: Ekim ayı (yeni başlamış)
    oct_dt = datetime(2026, 10, 5, tzinfo=timezone.utc)
    s3, e3 = current_academic_year_bounds(oct_dt)
    check("Ekim'de start = 2026-09-01",
          s3 == date(2026, 9, 1))
    check("Ekim'de end = 2027-06-30",
          e3 == date(2027, 6, 30))

    # ============ STEP 2: is_summer_window ============
    print("\n=== STEP 2: is_summer_window ===")
    check("Temmuz → True",
          is_summer_window(datetime(2026, 7, 15, tzinfo=timezone.utc)))
    check("Ağustos → True",
          is_summer_window(datetime(2026, 8, 30, tzinfo=timezone.utc)))
    check("Eylül → False",
          not is_summer_window(datetime(2026, 9, 1, tzinfo=timezone.utc)))
    check("Ocak → False",
          not is_summer_window(datetime(2026, 1, 15, tzinfo=timezone.utc)))

    # ============ STEP 3: switch_to_academic_year ============
    print("\n=== STEP 3: switch_to_academic_year ===")
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        switch_to_academic_year(db, institution=i, actor_user_id=admin_id)

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("subscription_kind = academic_year",
              i.subscription_kind == KIND_ACADEMIC_YEAR)
        check("subscription_period_end set",
              i.subscription_period_end is not None)
        # Audit kaydı
        rows = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_id == inst_id,
                PlanChangeHistory.reason.in_(["academic_year_renewal"]),
            )
            .all()
        )
        check("ACADEMIC_YEAR_RENEWAL audit kaydı", len(rows) >= 1)

    # ============ STEP 4: pause_for_summer kış kontrolü ============
    print("\n=== STEP 4: pause kış aylarında reddedilebilir ===")
    # Servis seviyesinde pause kontrolü kind kontrolü yapıyor (kind != academic_year ise reddet)
    # Yaz penceresi kontrolü route seviyesinde — burada sadece kind kontrol edelim
    with SessionLocal() as db:
        # Önce monthly'ye geri çek
        i = db.get(Institution, inst_id)
        i.subscription_kind = KIND_MONTHLY
        db.commit()
        try:
            pause_for_summer(db, institution=i)
            check("monthly'den pause → ValueError", False, "exception bekleniyordu")
        except ValueError:
            check("monthly'den pause → ValueError", True)
        # Geri academic_year'a çek
        i.subscription_kind = KIND_ACADEMIC_YEAR
        db.commit()

    # ============ STEP 5: pause_for_summer ============
    print("\n=== STEP 5: pause_for_summer ===")
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        until = datetime(now.year, 8, 31, 23, 59, 59, tzinfo=timezone.utc)
        pause_for_summer(db, institution=i, until=until, actor_user_id=admin_id)

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("subscription_kind = paused",
              i.subscription_kind == KIND_PAUSED)
        check("subscription_pause_until set",
              i.subscription_pause_until is not None)
        check("is_paused True",
              is_paused(i, datetime(now.year, 8, 1, tzinfo=timezone.utc)))
        check("Eylül 1'de is_paused False",
              not is_paused(i, datetime(now.year + 1, 9, 1, tzinfo=timezone.utc)))
        rows = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_id == inst_id,
                PlanChangeHistory.reason == "pause",
            )
            .all()
        )
        check("PAUSE audit kaydı", len(rows) == 1)

    # ============ STEP 6: resume_from_pause ============
    print("\n=== STEP 6: resume_from_pause ===")
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        resume_from_pause(db, institution=i, actor_user_id=admin_id)

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("kind = academic_year (resume sonrası)",
              i.subscription_kind == KIND_ACADEMIC_YEAR)
        check("pause_until temizlendi",
              i.subscription_pause_until is None)
        rows = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_id == inst_id,
                PlanChangeHistory.reason == "resume",
            )
            .all()
        )
        check("RESUME audit kaydı", len(rows) == 1)

    # ============ STEP 7: cron_resume_paused_subscriptions ============
    print("\n=== STEP 7: cron_resume_paused_subscriptions ===")
    # Pause + pause_until'i geçmişe çek — cron çalışınca resume olmalı
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        i.subscription_kind = KIND_PAUSED
        i.subscription_pause_until = now - timedelta(days=1)   # geçmiş
        db.commit()

    with SessionLocal() as db:
        result = cron_resume_paused_subscriptions(db, now=now)
        check("cron resumed >= 1", result.get("resumed", 0) >= 1)

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("cron sonrası kind = academic_year",
              i.subscription_kind == KIND_ACADEMIC_YEAR)

    # Hâlâ pause süresi devam edenler atlanmalı
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        i.subscription_kind = KIND_PAUSED
        i.subscription_pause_until = now + timedelta(days=10)   # ileride
        db.commit()
        result = cron_resume_paused_subscriptions(db, now=now)
        check("hâlâ pause süresi devam → resumed=0",
              result.get("resumed", 0) == 0)
        check("skipped_still_paused >= 1",
              result.get("skipped_still_paused", 0) >= 1)

    # ============ STEP 8: enable_guarantee ============
    print("\n=== STEP 8: enable_guarantee ===")
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        i.subscription_kind = KIND_ACADEMIC_YEAR
        i.subscription_pause_until = None
        db.commit()
        enable_guarantee(db, institution=i, actor_user_id=admin_id)

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("performance_guarantee = True",
              i.performance_guarantee is True)
        check("guarantee_extended_at hâlâ None",
              i.guarantee_extended_at is None)

    # ============ STEP 9: evaluate_guarantee — 60g öncesi ============
    print("\n=== STEP 9: evaluate_guarantee 60g öncesi ===")
    # Kurum yeni oluşturuldu — created_at şu an
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        ev = evaluate_guarantee(db, institution=i, now=now)
        check("eligible = True", ev.eligible)
        check("triggered = False (60g geçmemiş)", not ev.triggered)
        check("can_extend = False", not ev.can_extend)
        check("days_into_period < 60",
              ev.days_into_period is not None and ev.days_into_period < 60)

    # ============ STEP 10: evaluate_guarantee — 60g sonrası, eşik altı ============
    print("\n=== STEP 10: evaluate_guarantee 60g sonrası eşik altı ===")
    # Kurum created_at'i 70 gün öncesine çek + planlanmış görevler ekle, hiç tamamlama yok
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        i.created_at = now - timedelta(days=70)
        db.commit()

        # 10 task ekle, hepsi PENDING (tamamlanmamış)
        for sid in student_ids[:3]:
            for offset in range(10):
                t = Task(
                    student_id=sid, type=TaskType.TEST,
                    title=f"Test {offset}",
                    date=(now - timedelta(days=offset + 1)).date(),
                    status=TaskStatus.PENDING,
                )
                db.add(t)
        db.commit()

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        ev = evaluate_guarantee(db, institution=i, now=now)
        check("60g sonrası days_into_period >= 60",
              ev.days_into_period is not None and ev.days_into_period >= 60)
        check("ortalama = 0 (hiç tamamlanmamış)",
              ev.average_completion_rate == 0.0)
        check("triggered = True (eşik altı)", ev.triggered)
        check("can_extend = True", ev.can_extend)
        check("already_extended = False", not ev.already_extended)

    # ============ STEP 11: apply_guarantee_extension ============
    print("\n=== STEP 11: apply_guarantee_extension ===")
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        prev_pe = i.subscription_period_end
        apply_guarantee_extension(db, institution=i, actor_user_id=admin_id)

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("guarantee_extended_at SET",
              i.guarantee_extended_at is not None)
        # period_end +30 gün
        if prev_pe and i.subscription_period_end:
            diff_days = (i.subscription_period_end - prev_pe).days
            check("period_end +30 gün civarı",
                  29 <= diff_days <= 31, f"diff={diff_days}")
        rows = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_id == inst_id,
                PlanChangeHistory.reason == "guarantee_extend",
            )
            .all()
        )
        check("GUARANTEE_EXTEND audit kaydı 2 (enable + extend)",
              len(rows) >= 2)

    # ============ STEP 12: apply_guarantee_extension idempotent ============
    print("\n=== STEP 12: extension idempotent ===")
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        prev_pe = i.subscription_period_end
        apply_guarantee_extension(db, institution=i, actor_user_id=admin_id)

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        # period_end değişmemiş olmalı (already extended)
        check("ikinci kez period_end değişmedi",
              i.subscription_period_end == prev_pe)

        ev = evaluate_guarantee(db, institution=i, now=now)
        check("already_extended = True", ev.already_extended)
        check("can_extend = False", not ev.can_extend)

    # ============ STEP 13: cron_evaluate_guarantees ============
    print("\n=== STEP 13: cron_evaluate_guarantees ===")
    with SessionLocal() as db:
        result = cron_evaluate_guarantees(db, now=now)
        check("evaluated >= 1", result.get("evaluated", 0) >= 1)
        check("skipped_already >= 1 (zaten uzatıldı)",
              result.get("skipped_already", 0) >= 1)

    # ============ STEP 14: HTTP /institution/subscription ============
    print("\n=== STEP 14: HTTP /institution/subscription ===")
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
    app.dependency_overrides[get_current_user] = make_user_override(admin_id)
    app.dependency_overrides[require_institution_admin] = make_user_override(admin_id)

    r = client.get("/institution/subscription")
    check("subscription page → 200", r.status_code == 200,
          f"got {r.status_code}")
    body = r.text
    check("'Abonelik Yönetimi' başlığı", "Abonelik Yönetimi" in body)
    check("'Akademik Yıl Planı' label", "Akademik Yıl" in body)
    check("'60 Gün Performans Garantisi' başlığı",
          "60 Gün Performans" in body)
    check("'Yaz Pause Modu' başlığı", "Yaz Pause" in body)

    # ============ STEP 15: switch-academic-year POST (kind=monthly'ye çekilmemişse no-op) ============
    print("\n=== STEP 15: switch-academic-year POST ===")
    # Kurumu monthly'ye geri çekip endpoint'i çağır
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        i.subscription_kind = KIND_MONTHLY
        i.subscription_period_end = None
        db.commit()

    r = client.post("/institution/subscription/switch-academic-year",
                    follow_redirects=False)
    check("switch POST → 303", r.status_code in (302, 303))
    check("redirect ?switched=1",
          r.headers.get("location", "").endswith("?switched=1"))

    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("DB'de kind = academic_year",
              i.subscription_kind == KIND_ACADEMIC_YEAR)
        check("period_end set", i.subscription_period_end is not None)

    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        db.execute(delete(Task).where(Task.student_id.in_(student_ids)))
        db.execute(delete(PlanChangeHistory).where(
            PlanChangeHistory.owner_id == inst_id
        ))
        all_users = student_ids + [admin_id, teacher_id]
        db.execute(delete(User).where(User.id.in_(all_users)))
        db.execute(delete(Institution).where(Institution.id == inst_id))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
