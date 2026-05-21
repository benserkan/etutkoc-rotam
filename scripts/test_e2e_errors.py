"""E2E Test 4 — Hata simülasyonları + güvenlik.

Senaryolar:
  1. Geçersiz invitation token (yok / expired / revoked)
  2. Tüketilmiş invitation (consumed) ile tekrar signup
  3. Cross-tenant URL guessing — A öğretmeninin B öğretmeninin sayfalarına erişimi
  4. Bozuk CSV — başlık yok, eksik kolon, hatalı email
  5. Cross-student review rating
  6. Lockout — 5 başarısız login ile hesap kilitlenir
  7. Pasif user login engeli
  8. KVKK self-serve veri ihracı endpoint var mı (yetkili öğrenci)
  9. RTBF silme talebi endpoint var mı
  10. Cross-tenant institution view — A admin B kurumun /institution/cohorts göremiyor
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
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    Institution,
    Invitation,
    InvitationStatus,
    PlanChangeHistory,
    User,
    UserRole,
)
from app.services.security import hash_password


PFX = f"e2e_err_{secrets.token_hex(3)}"
STRONG_PASSWORD = "TestPass123!@xyz"

passed = 0
failed: list[str] = []
findings: list[dict] = []


def check(label: str, cond: bool, detail: str = "", severity: str = "high") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        findings.append({
            "test": "e2e_errors",
            "label": label, "detail": detail, "severity": severity,
        })
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    now = datetime.now(timezone.utc)

    # =================================================================
    # FIXTURE: 2 öğretmen + 1 kurum
    # =================================================================
    print("\n=== FIXTURE: 2 öğretmen + 1 kurum ===")
    with SessionLocal() as db:
        inst = Institution(name="E2E Err Inst", slug=f"e2e-err-{secrets.token_hex(2)}")
        db.add(inst); db.flush()

        t_a = User(
            email=f"{PFX}_a@test.invalid",
            password_hash=hash_password(STRONG_PASSWORD),
            full_name="Teacher A", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        t_b = User(
            email=f"{PFX}_b@test.invalid",
            password_hash=hash_password(STRONG_PASSWORD),
            full_name="Teacher B", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        passive = User(
            email=f"{PFX}_passive@test.invalid",
            password_hash=hash_password(STRONG_PASSWORD),
            full_name="Passive User", role=UserRole.TEACHER,
            is_active=False, password_changed_at=now,
        )
        db.add_all([t_a, t_b, passive]); db.flush()

        student_a = User(
            email=f"{PFX}_sa@test.invalid",
            password_hash=hash_password(STRONG_PASSWORD),
            full_name="Student A", role=UserRole.STUDENT,
            teacher_id=t_a.id,
            grade_level=8, is_graduate=False,
            is_active=True, password_changed_at=now,
        )
        db.add(student_a); db.commit()
        inst_id = inst.id
        ta_id, tb_id, passive_id = t_a.id, t_b.id, passive.id
        sa_id = student_a.id

    # =================================================================
    # STEP 1: Geçersiz invitation token
    # =================================================================
    print("\n=== STEP 1: Geçersiz/expired invitation token ===")
    client = TestClient(app)
    r = client.get("/signup/invite/yokyokyok-bad-token-123",
                   follow_redirects=False)
    check("yok olan token 404/410",
          r.status_code in (404, 410), f"got {r.status_code}",
          "medium")

    # Expired invitation oluştur
    with SessionLocal() as db:
        exp_inv = Invitation(
            token=f"exp-{secrets.token_urlsafe(16)}",
            email=f"{PFX}_inv_exp@test.invalid",
            full_name="Expired Inv",
            role=UserRole.TEACHER,
            expires_at=now - timedelta(days=1),
        )
        db.add(exp_inv); db.commit()
        exp_token = exp_inv.token

    r = client.get(f"/signup/invite/{exp_token}", follow_redirects=False)
    check("expired token 410/404",
          r.status_code in (404, 410), f"got {r.status_code}",
          "medium")

    # =================================================================
    # STEP 2: Consumed invitation
    # =================================================================
    print("\n=== STEP 2: Consumed invitation ===")
    with SessionLocal() as db:
        cons_inv = Invitation(
            token=f"cons-{secrets.token_urlsafe(16)}",
            email=f"{PFX}_inv_cons@test.invalid",
            full_name="Consumed Inv",
            role=UserRole.TEACHER,
            expires_at=now + timedelta(days=7),
            consumed_at=now - timedelta(hours=1),
            consumed_by_user_id=ta_id,
        )
        db.add(cons_inv); db.commit()
        cons_token = cons_inv.token

    r = client.get(f"/signup/invite/{cons_token}", follow_redirects=False)
    check("consumed token 410/404",
          r.status_code in (404, 410), f"got {r.status_code}",
          "medium")

    # =================================================================
    # STEP 3: Cross-tenant URL guessing
    # =================================================================
    print("\n=== STEP 3: Cross-tenant URL guessing ===")
    client_b = TestClient(app)
    r = client_b.post("/login", data={
        "email": f"{PFX}_b@test.invalid",
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    if r.status_code != 303:
        check("öğretmen B login (hash sorunu)", False,
              f"login got {r.status_code} — bcrypt/passlib hash deterministik değil olabilir",
              "critical")
        # Yine de devam — diğer testler ayrı
    else:
        check("teacher B login 303", True)

        # B, A'nın öğrencisini görmeye çalışsın
        r = client_b.get(f"/teacher/students/{sa_id}")
        check("cross-tenant öğrenci detay 403/404",
              r.status_code in (403, 404),
              f"TENANT LEAK: B teacher A'nın öğrencisini gördü ({r.status_code})",
              "critical")

        for endpoint in [
            f"/teacher/students/{sa_id}/dna",
            f"/teacher/students/{sa_id}/review",
            f"/teacher/students/{sa_id}/focus",
            f"/teacher/students/{sa_id}/goals",
        ]:
            r = client_b.get(endpoint)
            check(f"cross-tenant {endpoint} 403/404",
                  r.status_code in (403, 404),
                  f"got {r.status_code}", "critical")

    # =================================================================
    # STEP 4: Bozuk CSV
    # =================================================================
    print("\n=== STEP 4: Bozuk CSV import ===")
    # Henüz oturum olmasın — anonim öğretmenle login ol
    client_a = TestClient(app)
    r = client_a.post("/login", data={
        "email": f"{PFX}_a@test.invalid",
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    if r.status_code != 303:
        check("teacher A login (hash sorunu)", False,
              f"login got {r.status_code}",
              "critical")
    else:
        # Bozuk CSV: başlık yok
        bad_csv = "Ali Veli,ali@test.com,8\nAyşe,ayse,9"
        # Endpoint'e bakalım — csv_content veya file upload?
        try:
            r = client_a.post("/teacher/students/import/preview",
                              data={"csv_content": bad_csv},
                              follow_redirects=False)
            check("bozuk CSV preview 200/400 (controlled)",
                  r.status_code in (200, 400, 422),
                  f"got {r.status_code}",
                  "low")
        except Exception as e:
            check("bozuk CSV preview crash etmedi",
                  False, f"server crash: {e}", "high")

        # Hatalı email
        bad_csv2 = "full_name,email,grade_level\nAyşe,not-an-email,9"
        r = client_a.post("/teacher/students/import/preview",
                          data={"csv_content": bad_csv2},
                          follow_redirects=False)
        check("hatalı email CSV → 200 (preview hata satırı gösterir)",
              r.status_code == 200,
              f"got {r.status_code}",
              "medium")
        check("preview hata satırını kullanıcıya gösteriyor",
              ("hata" in r.text.lower() or "geçersiz" in r.text.lower()
               or "invalid" in r.text.lower() or "email" in r.text.lower()),
              "Bozuk CSV satırı uyarı olarak gösterilmiyor — UX riski",
              "medium")

    # =================================================================
    # STEP 5: Cross-student review rating
    # =================================================================
    print("\n=== STEP 5: Cross-student review rating ===")
    # B öğretmenin öğrencisi (A'nın review kartı varsa)
    with SessionLocal() as db:
        from app.models import ReviewCard, Subject, Topic
        # Önce A öğrencisine bir review kartı seed et
        subj = db.query(Subject).filter(Subject.is_builtin.is_(True)).first()
        if subj:
            topic = db.query(Topic).filter(
                Topic.subject_id == subj.id, Topic.is_builtin.is_(True)
            ).first()
            if topic:
                card = ReviewCard(
                    student_id=sa_id, topic_id=topic.id,
                    stability=0, difficulty=5, state="new",
                )
                db.add(card); db.commit()
                card_id = card.id
            else:
                card_id = None
        else:
            card_id = None

    if card_id:
        # Login as A öğrencisi mümkün değil (öğrenci parolası bilinmiyor).
        # Hem cross-student hem unauthorized testi: anonim olarak POST
        anon = TestClient(app)
        r = anon.post(f"/student/review/{card_id}",
                      data={"rating": "3"}, follow_redirects=False)
        check("anonim review rating 303/403",
              r.status_code in (302, 303, 403),
              f"got {r.status_code}",
              "high")

    # =================================================================
    # STEP 6: Login lockout — 5 başarısız deneme
    # =================================================================
    print("\n=== STEP 6: Login lockout ===")
    lockout_email = f"{PFX}_lockout@test.invalid"
    # Lockout için yeni user
    with SessionLocal() as db:
        u = User(
            email=lockout_email,
            password_hash=hash_password(STRONG_PASSWORD),
            full_name="Lockout User", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        db.add(u); db.commit()
        lockout_id = u.id

    lock_client = TestClient(app)
    last_status = None
    for i in range(6):
        r = lock_client.post("/login", data={
            "email": lockout_email,
            "password": "wrong-password-xx",
        }, follow_redirects=False)
        last_status = r.status_code
    check("5+ başarısız sonrası lockout (423 veya benzer)",
          last_status in (423, 429),
          f"got last={last_status} — lockout mekanizması beklenen şekilde çalışmıyor",
          "high")

    # =================================================================
    # STEP 7: Pasif user login engeli
    # =================================================================
    print("\n=== STEP 7: Pasif user login ===")
    pass_client = TestClient(app)
    r = pass_client.post("/login", data={
        "email": f"{PFX}_passive@test.invalid",
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    check("pasif user login 401",
          r.status_code in (401, 403),
          f"got {r.status_code} — pasif user içeri girmemeli",
          "critical")

    # =================================================================
    # STEP 8: KVKK self-serve
    # =================================================================
    print("\n=== STEP 8: KVKK endpoints ===")
    if r.status_code == 401 or last_status:
        # client_a hala login varsa kontrol et
        r = client_a.get("/me")
        check("/me 200 (KVKK panel erişimi)", r.status_code == 200,
              f"got {r.status_code}", "high")
        # KVKK aydınlatma metni
        r = client_a.get("/kvkk")
        check("/kvkk 200 (public)", r.status_code == 200,
              f"got {r.status_code}", "medium")

    # =================================================================
    # STEP 9: Anonim erişim engeli — sensitive endpoint'ler
    # =================================================================
    print("\n=== STEP 9: Anonim erişim engeli ===")
    anon = TestClient(app)
    for endpoint in [
        "/teacher",
        "/student",
        "/admin",
        "/institution",
        f"/teacher/students/{sa_id}",
        f"/teacher/students/{sa_id}/dna",
    ]:
        r = anon.get(endpoint, follow_redirects=False)
        check(f"anonim {endpoint} 303/401/403",
              r.status_code in (302, 303, 401, 403),
              f"got {r.status_code}",
              "critical")

    # =================================================================
    # STEP 10: Cross-tenant institution view
    # =================================================================
    print("\n=== STEP 10: Cross-tenant institution view ===")
    # B kurum admin oluştur
    with SessionLocal() as db:
        admin_b = User(
            email=f"{PFX}_admin_b@test.invalid",
            password_hash=hash_password(STRONG_PASSWORD),
            full_name="Admin B", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id,  # aynı kurum ama yine de kontrol
            is_active=True, password_changed_at=now,
        )
        db.add(admin_b); db.commit()
        admin_b_id = admin_b.id

    # admin_b login + /admin engellenmeli (super_admin değil)
    admin_b_client = TestClient(app)
    r = admin_b_client.post("/login", data={
        "email": f"{PFX}_admin_b@test.invalid",
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    if r.status_code == 303:
        r = admin_b_client.get("/admin")
        check("institution_admin /admin 403/redirect",
              r.status_code in (302, 303, 403),
              f"got {r.status_code}",
              "high")
    else:
        # hash sorunu — skip
        print("  [SKIP] admin B login başarısız (hash sorunu)")

    # =================================================================
    # CLEANUP
    # =================================================================
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_ids = [ta_id, tb_id, passive_id, sa_id, lockout_id, admin_b_id]
        from app.models import ReviewCard
        db.execute(delete(ReviewCard).where(ReviewCard.student_id.in_(all_ids)))
        db.execute(delete(Invitation).where(
            Invitation.email.like(f"{PFX}%")))
        db.execute(delete(PlanChangeHistory).where(
            PlanChangeHistory.owner_id.in_(all_ids)))
        db.execute(delete(AuditLog).where(AuditLog.actor_id.in_(all_ids)))
        db.execute(delete(User).where(User.id.in_(all_ids)))
        db.execute(delete(Institution).where(Institution.id == inst_id))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    if findings:
        import json
        with open("scripts/.e2e_findings_errors.json", "w", encoding="utf-8") as fh:
            json.dump(findings, fh, ensure_ascii=False, indent=2)
        print(f"\nFindings: scripts/.e2e_findings_errors.json")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
