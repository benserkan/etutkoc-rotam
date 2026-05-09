"""Stage 2 — kohort + aktivite haritası kapsamlı smoke test.

Senaryo:
1. ALPHA + BETA iki kurum (tenant izolasyonu için)
2. ALPHA'da:
   - 3 öğretmen
   - 8 öğrenci farklı sınıflarda (5,6,7,8,9,10,11,12 — her sınıftan 1)
   - 11+12 öğrencileri için track set
   - 1 mezun öğrenci graduate_mode=DERSHANE
3. BETA'da: 1 öğretmen + 1 öğrenci (tenant sızma kontrolü için)

Testler:
- Cohort by grade: 8 farklı sınıf görünür, ALPHA içinde sayılar doğru
- Cohort by track: sadece 11+ ve mezun (3 öğrenci)
- Cohort by curriculum: LGS / Klasik / Maarif farkı
- Cohort by exam_target: LGS / YKS / Yıl Sonu
- Week-over-week: bu hafta vs geçen hafta
- Heatmap: 3 öğretmen, login audit'lerinden aktivite
- Inactive teachers: hiç giriş yapmayan öğretmen
- Tenant isolation: ALPHA admin BETA verilerini GÖRMEMELİ
- Anonim erişim: 303 redirect
- /institution/cohorts: 4 tab erişilebilir
- /institution/activity-heatmap: weeks=4, weeks=12, weeks=99 (geçersiz)

Cleanup tüm test verilerini siler.
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    Institution,
    Track,
    User,
    UserRole,
)
from app.models.user import GraduateMode
from app.services.auth_security import generate_strong_password
from app.services.cohort_analysis import (
    cohort_by_curriculum,
    cohort_by_exam_target,
    cohort_by_grade,
    cohort_by_track,
    institution_week_over_week,
)
from app.services.security import hash_password
from app.services.teacher_activity import (
    inactive_teachers,
    teacher_activity_heatmap,
)


PFX = f"_stage2_{secrets.token_hex(3)}"
PWD = "TestPass!234567"

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
    ids: dict = {"users": [], "audit_logs": []}
    print("\n=== SEED ===")
    with SessionLocal() as db:
        pwd_hash = hash_password(PWD)
        now = datetime.now(timezone.utc)

        # ALPHA kurum
        alpha = Institution(
            name=f"{PFX}_ALPHA", slug=f"{PFX}-alpha",
            contact_email=f"{PFX}_alpha@test.invalid", plan="free", is_active=True,
        )
        # BETA kurum (sızma kontrolü)
        beta = Institution(
            name=f"{PFX}_BETA", slug=f"{PFX}-beta",
            contact_email=f"{PFX}_beta@test.invalid", plan="free", is_active=True,
        )
        db.add_all([alpha, beta])
        db.flush()
        ids["alpha_id"] = alpha.id
        ids["beta_id"] = beta.id

        # ALPHA admin
        alpha_admin = User(
            email=f"{PFX}_alpha_admin@test.invalid", password_hash=pwd_hash,
            full_name="Alpha Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=alpha.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # ALPHA 3 öğretmen — t1 aktif (login bugün), t2 yarı (3g önce), t3 pasif
        teachers_alpha = []
        for i, last_login_offset in enumerate([0, 3, 30]):
            t = User(
                email=f"{PFX}_alpha_t{i}@test.invalid", password_hash=pwd_hash,
                full_name=f"Alpha Teacher {i}", role=UserRole.TEACHER,
                institution_id=alpha.id, is_active=True,
                password_changed_at=now, must_change_password=False,
                last_login_at=now - timedelta(days=last_login_offset),
            )
            teachers_alpha.append(t)
            db.add(t)
        db.add(alpha_admin)
        db.flush()
        ids["alpha_admin_email"] = alpha_admin.email
        ids["alpha_admin_id"] = alpha_admin.id
        ids["alpha_t_ids"] = [t.id for t in teachers_alpha]
        ids["users"].extend([alpha_admin.id] + ids["alpha_t_ids"])

        # ALPHA login audit kayıtları (heatmap için)
        for t in teachers_alpha:
            offset = teachers_alpha.index(t)
            # t0: bugün + dün + 2 gün önce, t1: bugün + 3 gün önce, t2: hiç
            login_days = (
                [0, 1, 2] if offset == 0 else
                [0, 3] if offset == 1 else
                []
            )
            for days_ago in login_days:
                audit_dt = now - timedelta(days=days_ago, hours=2)
                a = AuditLog(
                    actor_id=t.id, action=AuditAction.LOGIN_SUCCESS,
                    created_at=audit_dt,
                )
                db.add(a)
                db.flush()
                ids["audit_logs"].append(a.id)

        # ALPHA öğrenciler — 8 farklı sınıf, 1 mezun
        students_alpha_data = [
            # (grade, track, is_grad, graduate_mode, name_suffix)
            (5,  None,         False, None, "g5"),
            (6,  None,         False, None, "g6"),
            (7,  None,         False, None, "g7"),
            (8,  None,         False, None, "g8"),
            (9,  None,         False, None, "g9"),
            (10, None,         False, None, "g10"),
            (11, Track.SAYISAL, False, None, "g11"),
            (12, Track.EA,      False, None, "g12"),
            (None, Track.SOZEL, True, GraduateMode.DERSHANE, "grad"),
        ]
        ids["alpha_s_ids"] = []
        for grade, track, is_grad, gmode, suffix in students_alpha_data:
            s = User(
                email=f"{PFX}_alpha_{suffix}@test.invalid", password_hash=pwd_hash,
                full_name=f"Alpha Student {suffix}", role=UserRole.STUDENT,
                institution_id=alpha.id, teacher_id=teachers_alpha[0].id,
                is_active=True, password_changed_at=now,
                must_change_password=False,
                grade_level=grade, track=track,
                is_graduate=is_grad, graduate_mode=gmode,
                last_login_at=now,
            )
            db.add(s)
            db.flush()
            ids["alpha_s_ids"].append(s.id)
        ids["users"].extend(ids["alpha_s_ids"])

        # BETA: 1 admin + 1 öğretmen + 1 öğrenci (sızma kontrolü)
        beta_admin = User(
            email=f"{PFX}_beta_admin@test.invalid", password_hash=pwd_hash,
            full_name="Beta Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=beta.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        beta_t = User(
            email=f"{PFX}_beta_t@test.invalid", password_hash=pwd_hash,
            full_name="Beta Teacher", role=UserRole.TEACHER,
            institution_id=beta.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([beta_admin, beta_t])
        db.flush()
        beta_s = User(
            email=f"{PFX}_beta_s@test.invalid", password_hash=pwd_hash,
            full_name="Beta Student", role=UserRole.STUDENT,
            institution_id=beta.id, teacher_id=beta_t.id,
            is_active=True, password_changed_at=now,
            must_change_password=False,
            grade_level=8,
        )
        db.add(beta_s)
        db.flush()
        ids["beta_admin_email"] = beta_admin.email
        ids["users"].extend([beta_admin.id, beta_t.id, beta_s.id])

        db.commit()
    print(f"  ALPHA inst={ids['alpha_id']} (3 teacher, 9 student)")
    print(f"  BETA  inst={ids['beta_id']} (1 teacher, 1 student)")

    # ============ STEP 1: cohort_by_grade ============
    print("\n=== STEP 1: cohort_by_grade ===")
    with SessionLocal() as db:
        cohorts = cohort_by_grade(db, institution_id=ids["alpha_id"])
        labels = [c.cohort_label for c in cohorts]
        print(f"  cohorts: {labels}")
        check("9 farklı kohort (5-12 + mezun)", len(cohorts) == 9, f"got {len(cohorts)}")
        check("5. sınıf kohortu var", any("5. sınıf" in l for l in labels))
        check("12. sınıf kohortu var", any("12. sınıf" in l for l in labels))
        check("Mezun kohortu var", any("Mezun" in l for l in labels))
        # 8 öğrenci 5-12, 1 mezun. Total 9.
        total_students = sum(c.student_count for c in cohorts)
        check("Toplam öğrenci sayısı 9", total_students == 9, f"got {total_students}")

    # ============ STEP 2: cohort_by_track ============
    print("\n=== STEP 2: cohort_by_track ===")
    with SessionLocal() as db:
        cohorts = cohort_by_track(db, institution_id=ids["alpha_id"])
        labels = [c.cohort_label for c in cohorts]
        print(f"  cohorts: {labels}")
        # 11.SAY, 12.EA, mezun.SOZEL = 3 öğrenci 11+/mezun
        total = sum(c.student_count for c in cohorts)
        check("11+/mezun toplam 3 öğrenci", total == 3, f"got {total}")
        check("Sayısal kohortu var", any("Sayısal" in l for l in labels))
        check("Eşit Ağırlık kohortu var", any("Eşit Ağırlık" in l for l in labels))
        check("Sözel kohortu var", any("Sözel" in l for l in labels))

    # ============ STEP 3: cohort_by_curriculum ============
    print("\n=== STEP 3: cohort_by_curriculum ===")
    with SessionLocal() as db:
        cohorts = cohort_by_curriculum(db, institution_id=ids["alpha_id"])
        labels = [c.cohort_label for c in cohorts]
        print(f"  cohorts: {labels}")
        check("En az 1 müfredat kohortu", len(cohorts) >= 1)
        # 5-8 → LGS müfredatı; 9-10 → Maarif (sınıf yıl override yok varsayılan)
        # 11-12+mezun → ya Maarif ya Klasik kohort'a göre, default akademik yıl yok
        total = sum(c.student_count for c in cohorts)
        check("Toplam öğrenci 9", total == 9, f"got {total}")

    # ============ STEP 4: cohort_by_exam_target ============
    print("\n=== STEP 4: cohort_by_exam_target ===")
    with SessionLocal() as db:
        cohorts = cohort_by_exam_target(db, institution_id=ids["alpha_id"])
        labels = [c.cohort_label for c in cohorts]
        print(f"  cohorts: {labels}")
        # 8 → LGS, 12 → YKS, mezun → YKS, diğerleri → Yıl Sonu/None
        check("LGS hedefi var", any("LGS" in l for l in labels))
        check("YKS hedefi var", any("YKS" in l for l in labels))

    # ============ STEP 5: week_over_week ============
    print("\n=== STEP 5: institution_week_over_week ===")
    with SessionLocal() as db:
        wow = institution_week_over_week(db, institution_id=ids["alpha_id"])
        # Hiç görev yok → her iki rate de None
        check("hiç görev yokken this_rate None", wow.this_week_rate is None,
              f"got {wow.this_week_rate}")
        check("direction='unknown'", wow.direction == "unknown")

    # ============ STEP 6: teacher_activity_heatmap ============
    print("\n=== STEP 6: teacher_activity_heatmap ===")
    with SessionLocal() as db:
        heatmaps = teacher_activity_heatmap(db, institution_id=ids["alpha_id"], weeks=4)
        check("3 öğretmen heatmap'te", len(heatmaps) == 3, f"got {len(heatmaps)}")
        # t0: aktif (3 login), t1: yarı (2 login), t2: pasif (0 login)
        t0 = next((h for h in heatmaps if "Teacher 0" in h.teacher.full_name), None)
        t2 = next((h for h in heatmaps if "Teacher 2" in h.teacher.full_name), None)
        check("t0 toplam login >= 3",
              t0 is not None and t0.total_logins >= 3,
              f"t0={t0.total_logins if t0 else None}")
        check("t2 hiç login yok",
              t2 is not None and t2.total_logins == 0)
        check("t2 pasif (last_active None)",
              t2 is not None and t2.last_active_day is None)

    # ============ STEP 7: inactive_teachers ============
    print("\n=== STEP 7: inactive_teachers ===")
    with SessionLocal() as db:
        inactives = inactive_teachers(db, institution_id=ids["alpha_id"], days=7)
        names = [t.full_name for t in inactives]
        # t2 kesinlikle pasif (hiç login). t1 3g önce login etti — pasif değil
        check("t2 pasif olarak listelenmeli",
              any("Teacher 2" in n for n in names),
              f"got {names}")
        check("t0 pasif değil (bugün giriş)",
              not any("Teacher 0" in n for n in names),
              f"got {names}")

    # ============ STEP 8: Tenant isolation ============
    print("\n=== STEP 8: tenant isolation ===")
    with SessionLocal() as db:
        alpha_cohorts = cohort_by_grade(db, institution_id=ids["alpha_id"])
        beta_cohorts = cohort_by_grade(db, institution_id=ids["beta_id"])
        alpha_total = sum(c.student_count for c in alpha_cohorts)
        beta_total = sum(c.student_count for c in beta_cohorts)
        check("ALPHA = 9 öğrenci", alpha_total == 9, f"got {alpha_total}")
        check("BETA = 1 öğrenci (sızmadı)", beta_total == 1, f"got {beta_total}")

        alpha_heatmaps = teacher_activity_heatmap(
            db, institution_id=ids["alpha_id"], weeks=4
        )
        beta_heatmaps = teacher_activity_heatmap(
            db, institution_id=ids["beta_id"], weeks=4
        )
        check("ALPHA heatmap = 3 teacher", len(alpha_heatmaps) == 3)
        check("BETA heatmap = 1 teacher (sızmadı)", len(beta_heatmaps) == 1)

    # ============ STEP 9: HTTP — /institution/cohorts ============
    print("\n=== STEP 9: HTTP /institution/cohorts ===")
    c = TestClient(app)
    r = c.post("/login", data={"email": ids["alpha_admin_email"], "password": PWD},
               follow_redirects=False)
    check("alpha_admin login", r.status_code == 303, f"got {r.status_code}")

    for tab in ("grade", "track", "curriculum", "exam_target"):
        r = c.get(f"/institution/cohorts?tab={tab}")
        check(f"/institution/cohorts?tab={tab} -> 200",
              r.status_code == 200, f"got {r.status_code}")

    # Geçersiz tab → grade'e fallback
    r = c.get("/institution/cohorts?tab=BOGUS")
    check("invalid tab -> 200 (fallback grade)", r.status_code == 200)

    # ============ STEP 10: HTTP — /institution/activity-heatmap ============
    print("\n=== STEP 10: HTTP /institution/activity-heatmap ===")
    r = c.get("/institution/activity-heatmap")
    check("heatmap default 200", r.status_code == 200, f"got {r.status_code}")
    check("3 öğretmen UI'da görünür",
          all(f"Alpha Teacher {i}" in r.text for i in range(3)),
          "öğretmen adları yok")
    check("pasif rozet görünür",
          "pasif" in r.text,
          "pasif rozet yok")

    r = c.get("/institution/activity-heatmap?weeks=12")
    check("weeks=12 -> 200", r.status_code == 200)

    r = c.get("/institution/activity-heatmap?weeks=99")
    check("weeks=99 (invalid) -> 200 (fallback 4)", r.status_code == 200)

    # ============ STEP 11: HTTP cross-tenant ============
    print("\n=== STEP 11: HTTP cross-tenant ===")
    r = c.get("/institution/cohorts?tab=grade")
    # ALPHA admin görsün, BETA Student GÖRMESİN
    check("ALPHA admin sayfasında BETA öğrenci YOK",
          "Beta Student" not in r.text,
          "BETA student name leaked")
    # BETA admin'le login
    c2 = TestClient(app)
    r = c2.post("/login", data={"email": ids["beta_admin_email"], "password": PWD},
                follow_redirects=False)
    check("beta_admin login", r.status_code == 303)
    r = c2.get("/institution/activity-heatmap")
    check("BETA admin BETA Teacher görür",
          "Beta Teacher" in r.text)
    check("BETA admin Alpha Teacher GÖRMEZ",
          "Alpha Teacher" not in r.text,
          "ALPHA teacher leaked")

    # ============ STEP 12: HTTP anonim ============
    print("\n=== STEP 12: anonim erişim 303 ===")
    anon = TestClient(app)
    for path in ("/institution/cohorts", "/institution/activity-heatmap"):
        r = anon.get(path, follow_redirects=False)
        check(f"anon {path} -> 303",
              r.status_code == 303, f"got {r.status_code}")

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        # Audit logs
        if ids["audit_logs"]:
            db.query(AuditLog).filter(
                AuditLog.id.in_(ids["audit_logs"])
            ).delete(synchronize_session=False)
        # Tüm test kullanıcılarına ait audit (yeni login'ler dahil)
        if ids["users"]:
            db.query(AuditLog).filter(
                AuditLog.actor_id.in_(ids["users"])
            ).delete(synchronize_session=False)
        # Users
        if ids["users"]:
            db.query(User).filter(User.id.in_(ids["users"])).delete(
                synchronize_session=False
            )
        # Institutions
        db.query(Institution).filter(
            Institution.id.in_([ids["alpha_id"], ids["beta_id"]])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verisi temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 2 testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
