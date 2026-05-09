"""Stage 1 — Risk panel smoke test.

Senaryo:
1. 1 kurum + 1 institution_admin + 1 teacher + 4 öğrenci seed
   - Sağlıklı (programı var, güncel giriş)
   - Düşük tamamlama (planı var ama %0)
   - Hiç giriş yok (last_login NULL, plan yok)
   - Mute edilmiş (öğretmen susturmuş)
2. /teacher/at-risk → mute hariç 3 risk altında öğrenci görmeli
3. show_muted=1 → 4 öğrenci
4. /teacher/at-risk/{id}/mute → öğrenci panelden çıkmalı
5. /teacher/at-risk/{id}/unmute → geri gelmeli
6. /institution/at-risk → kurum genel görünümü, öğretmen-öğrenci eşlemesi
7. Anonim erişim → 303 /login

Cleanup tüm test verisini siler.
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
    AtRiskMute,
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.services.risk_analysis import compute_risk_score
from app.services.security import hash_password


PFX = f"_at_risk_{secrets.token_hex(3)}"
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
    print("\n=== SEED ===")
    with SessionLocal() as db:
        pwd = hash_password(PWD)
        now = datetime.now(timezone.utc)

        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst); db.flush()
        inst_id = inst.id

        admin = User(
            email=f"{PFX}_admin@test.invalid",
            password_hash=pwd, full_name="Risk Admin",
            role=UserRole.INSTITUTION_ADMIN, institution_id=inst_id,
            is_active=True, password_changed_at=now,
            must_change_password=False,
        )
        teacher = User(
            email=f"{PFX}_teacher@test.invalid",
            password_hash=pwd, full_name="Risk Teacher",
            role=UserRole.TEACHER, institution_id=inst_id,
            is_active=True, password_changed_at=now,
            must_change_password=False,
            last_login_at=now,
        )
        db.add_all([admin, teacher]); db.flush()
        admin_id, admin_email = admin.id, admin.email
        teacher_id, teacher_email = teacher.id, teacher.email

        # 4 öğrenci, last_login varyasyonlarıyla risk profili
        # (Task seed yapmıyoruz — no_program göstergesi tüm 4'ünde olacak)
        students_data = [
            # tag,            last_login              expected_level
            ("healthy",       now,                    "ok"),       # bugün giriş yapmış, sadece no_program (10) → ok
            ("old_login",     now - timedelta(days=10),"medium"),  # eski + no_program → 35 → medium
            ("never_login",   None,                   "medium"),   # hiç + no_program → 35 → medium
            ("to_mute",       now - timedelta(days=10),"medium"),  # eski + no_program → 35 → mute edilecek
        ]
        student_ids = {}
        for tag, last_login, _ in students_data:
            s = User(
                email=f"{PFX}_{tag}@test.invalid",
                password_hash=pwd, full_name=f"Risk Student {tag}",
                role=UserRole.STUDENT, institution_id=inst_id,
                teacher_id=teacher_id,
                is_active=True, password_changed_at=now,
                must_change_password=False,
                last_login_at=last_login,
                grade_level=8,
            )
            db.add(s); db.flush()
            student_ids[tag] = s.id

        db.commit()
    print(f"  inst={inst_id}, admin={admin_id}, teacher={teacher_id}, students={student_ids}")

    # ========== 1. Service-level direct test ==========
    print("\n=== STEP 1: compute_risk_score sanity ===")
    with SessionLocal() as db:
        for tag, sid in student_ids.items():
            s = db.get(User, sid)
            r = compute_risk_score(db, student=s)
            print(f"  {tag} (id={sid}): score={r.score} level={r.level} indicators={[i.code for i in r.indicators]}")

    # ========== 2. Teacher login + at-risk panel ==========
    print("\n=== STEP 2: /teacher/at-risk (mute öncesi) ===")
    c = TestClient(app)
    r = c.post("/login", data={"email": teacher_email, "password": PWD},
               follow_redirects=False)
    check("teacher login", r.status_code == 303, f"got {r.status_code}")

    r = c.get("/teacher/at-risk")
    check("at-risk page 200", r.status_code == 200, f"got {r.status_code}")
    # 'healthy' panelde olmamalı, diğer 3'ü olmalı (hepsi düşük login)
    check("old_login görünür", "Risk Student old_login" in r.text)
    check("never_login görünür", "Risk Student never_login" in r.text)
    check("to_mute görünür", "Risk Student to_mute" in r.text)
    check("healthy GÖRÜNMEZ (sağlıklı)",
          "Risk Student healthy" not in r.text,
          "healthy student panelde, olmamalı")

    # ========== 3. Mute aksiyonu ==========
    print("\n=== STEP 3: mute + panelden gizleme ===")
    r = c.post(
        f"/teacher/at-risk/{student_ids['to_mute']}/mute",
        data={"reason": "tatildeyim"},
        follow_redirects=False,
    )
    check("mute redirect", r.status_code == 303, f"got {r.status_code}")
    with SessionLocal() as db:
        m = (
            db.query(AtRiskMute)
            .filter(
                AtRiskMute.teacher_id == teacher_id,
                AtRiskMute.student_id == student_ids["to_mute"],
            )
            .first()
        )
        check("AtRiskMute kaydı oluştu", m is not None)
        if m:
            check("reason kaydedildi", m.reason == "tatildeyim", f"got {m.reason!r}")
            # SQLite naive datetime — UTC kabul et
            exp = m.expires_at if m.expires_at.tzinfo else m.expires_at.replace(tzinfo=timezone.utc)
            check("expires_at gelecekte", exp > datetime.now(timezone.utc))

    r = c.get("/teacher/at-risk")
    check("mute sonrası panelde gizli",
          "Risk Student to_mute" not in r.text,
          "to_mute hala panelde")

    # ========== 4. show_muted=1 ==========
    print("\n=== STEP 4: show_muted=1 ===")
    r = c.get("/teacher/at-risk?show_muted=1")
    check("show_muted=1 to_mute görünür",
          "Risk Student to_mute" in r.text,
          "show_muted=1 to_mute gizli")
    check("susturulmuş etiketi var", "susturulmuş" in r.text)

    # ========== 5. Unmute ==========
    print("\n=== STEP 5: unmute ===")
    r = c.post(
        f"/teacher/at-risk/{student_ids['to_mute']}/unmute",
        follow_redirects=False,
    )
    check("unmute redirect", r.status_code == 303, f"got {r.status_code}")
    with SessionLocal() as db:
        m = (
            db.query(AtRiskMute)
            .filter(
                AtRiskMute.teacher_id == teacher_id,
                AtRiskMute.student_id == student_ids["to_mute"],
            )
            .first()
        )
        check("AtRiskMute silindi", m is None)

    r = c.get("/teacher/at-risk")
    check("unmute sonrası to_mute geri geldi",
          "Risk Student to_mute" in r.text,
          "to_mute panelde değil")

    # ========== 6. Institution admin panel ==========
    print("\n=== STEP 6: /institution/at-risk ===")
    c2 = TestClient(app)
    r = c2.post("/login", data={"email": admin_email, "password": PWD},
                follow_redirects=False)
    check("admin login", r.status_code == 303, f"got {r.status_code}")

    r = c2.get("/institution/at-risk")
    check("institution at-risk 200", r.status_code == 200, f"got {r.status_code}")
    check("institution panel teacher adı görünür", "Risk Teacher" in r.text)
    check("institution panel öğrenci görünür", "Risk Student old_login" in r.text)
    check("institution panel /teacher/* link YOK (gizlilik)",
          "/teacher/students/" not in r.text,
          "teacher detay link sızdı")

    # ========== 7. Anonim erişim ==========
    print("\n=== STEP 7: anonim 303 ===")
    anon = TestClient(app)
    r = anon.get("/teacher/at-risk", follow_redirects=False)
    check("anon /teacher/at-risk -> 303", r.status_code == 303)
    r = anon.get("/institution/at-risk", follow_redirects=False)
    check("anon /institution/at-risk -> 303", r.status_code == 303)

    # ========== CLEANUP ==========
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_ids = list(student_ids.values()) + [teacher_id, admin_id]
        # Sırasıyla dış FK'lı tablolar önce
        db.query(AtRiskMute).filter(
            AtRiskMute.teacher_id.in_(all_ids)
        ).delete(synchronize_session=False)
        db.query(AtRiskMute).filter(
            AtRiskMute.student_id.in_(all_ids)
        ).delete(synchronize_session=False)
        # Audit logs (FK SET NULL ama temiz olsun)
        db.query(AuditLog).filter(
            AuditLog.actor_id.in_(all_ids)
        ).delete(synchronize_session=False)
        # Users
        db.query(User).filter(User.id.in_(all_ids)).delete(synchronize_session=False)
        # Institution
        db.query(Institution).filter(Institution.id == inst_id).delete()
        db.commit()
        print("  test verisi temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 1 risk panel testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
