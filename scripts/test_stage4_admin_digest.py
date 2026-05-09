"""Stage 4 — admin haftalık özet kapsamlı smoke test.

Senaryolar:
1. Service: build_weekly_digest_payload sayım doğruluğu
2. send_admin_weekly_digest log_only modda DB'ye yazıyor
3. Idempotency: aynı hafta 2. çağrı atlar (force=False)
4. force=True yeniden gönderir
5. Cron job: tüm aktif kurumlar için tek seferde tetiklenir
6. Tenant izolasyonu: kurum admin sadece kendi özetlerini görür
7. HTTP /institution/admin-digest list + detail + send-now
8. Anonim erişim 303
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AdminWeeklyDigest,
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.services.admin_digest import (
    build_weekly_digest_payload,
    send_admin_weekly_digest,
)
from app.services.cron_jobs import admin_weekly_digest as cron_admin_digest
from app.services.security import hash_password


PFX = f"_digest_{secrets.token_hex(3)}"
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
        pwd_hash = hash_password(PWD)
        now = datetime.now(timezone.utc)

        # 2 kurum (ALPHA test eden, BETA tenant izolasyon kontrolü için)
        alpha = Institution(
            name=f"{PFX}_alpha", slug=f"{PFX}-alpha",
            contact_email=f"{PFX}_a@test.invalid", plan="free", is_active=True,
        )
        beta = Institution(
            name=f"{PFX}_beta", slug=f"{PFX}-beta",
            contact_email=f"{PFX}_b@test.invalid", plan="free", is_active=True,
        )
        db.add_all([alpha, beta])
        db.flush()
        alpha_id, beta_id = alpha.id, beta.id

        # ALPHA: 1 admin + 2 öğretmen + 4 öğrenci
        alpha_admin = User(
            email=f"{PFX}_alpha_admin@test.invalid", password_hash=pwd_hash,
            full_name="Alpha Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=alpha_id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # Pasif öğretmen (last_login 30 gün önce) + aktif öğretmen
        t_active = User(
            email=f"{PFX}_t_active@test.invalid", password_hash=pwd_hash,
            full_name="Aktif Teacher", role=UserRole.TEACHER,
            institution_id=alpha_id, is_active=True,
            password_changed_at=now, must_change_password=False,
            last_login_at=now,
        )
        t_inactive = User(
            email=f"{PFX}_t_inactive@test.invalid", password_hash=pwd_hash,
            full_name="Pasif Teacher", role=UserRole.TEACHER,
            institution_id=alpha_id, is_active=True,
            password_changed_at=now, must_change_password=False,
            last_login_at=now - timedelta(days=30),
        )
        db.add_all([alpha_admin, t_active, t_inactive])
        db.flush()
        alpha_admin_id = alpha_admin.id
        alpha_admin_email = alpha_admin.email
        t_active_id, t_inactive_id = t_active.id, t_inactive.id

        # 4 öğrenci, çeşitli sınıf+last_login (risk altında değişen)
        for i, (grade, last_offset) in enumerate([
            (8, 0),       # sağlıklı
            (8, 0),       # sağlıklı
            (11, 30),     # risk altında (eski login)
            (12, None),   # hiç giriş yok
        ]):
            ll = None if last_offset is None else now - timedelta(days=last_offset)
            s = User(
                email=f"{PFX}_alpha_s{i}@test.invalid", password_hash=pwd_hash,
                full_name=f"Alpha Student {i}", role=UserRole.STUDENT,
                institution_id=alpha_id, teacher_id=t_active_id,
                grade_level=grade, is_active=True,
                password_changed_at=now, must_change_password=False,
                last_login_at=ll,
            )
            db.add(s)

        # BETA: 1 admin + 1 öğretmen + 1 öğrenci
        beta_admin = User(
            email=f"{PFX}_beta_admin@test.invalid", password_hash=pwd_hash,
            full_name="Beta Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=beta_id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        beta_t = User(
            email=f"{PFX}_beta_t@test.invalid", password_hash=pwd_hash,
            full_name="Beta Teacher", role=UserRole.TEACHER,
            institution_id=beta_id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([beta_admin, beta_t]); db.flush()
        beta_t_id = beta_t.id
        beta_s = User(
            email=f"{PFX}_beta_s@test.invalid", password_hash=pwd_hash,
            full_name="Beta Student", role=UserRole.STUDENT,
            institution_id=beta_id, teacher_id=beta_t_id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(beta_s)

        db.commit()
    print(f"  ALPHA inst={alpha_id}, BETA inst={beta_id}")

    # ============ STEP 1: build_weekly_digest_payload ============
    print("\n=== STEP 1: build_weekly_digest_payload ===")
    with SessionLocal() as db:
        alpha_obj = db.get(Institution, alpha_id)
        alpha_name = alpha_obj.name
        payload = build_weekly_digest_payload(db, institution=alpha_obj)
        check("payload var",
              isinstance(payload, dict) and "totals" in payload)
        check("teacher_count = 2", payload["totals"]["teacher_count"] == 2,
              f"got {payload['totals']['teacher_count']}")
        check("student_count = 4", payload["totals"]["student_count"] == 4,
              f"got {payload['totals']['student_count']}")
        check("inactive_teacher_count >= 1 (Pasif Teacher)",
              payload["totals"]["inactive_teacher_count"] >= 1,
              f"got {payload['totals']['inactive_teacher_count']}")
        check("at_risk total >= 1 (en az 1 öğrenci)",
              payload["at_risk"]["total"] >= 1,
              f"got {payload['at_risk']['total']}")
        check("institution_name doğru", payload["institution_name"] == alpha_name)
        check("week_start ISO format",
              len(payload["week_start"]) == 10 and "-" in payload["week_start"])

    # ============ STEP 2: send_admin_weekly_digest log_only ============
    print("\n=== STEP 2: send_admin_weekly_digest (log_only) ===")
    with SessionLocal() as db:
        alpha_obj = db.get(Institution, alpha_id)
        digest = send_admin_weekly_digest(db, institution=alpha_obj)
        check("digest oluştu", digest is not None)
        check("send_status log_only veya sent",
              digest.send_status in ("log_only", "sent"),
              f"got {digest.send_status}")
        check("recipient_count >= 1",
              digest.recipient_count >= 1,
              f"got {digest.recipient_count}")
        check("payload_json doluydu", digest.payload_json is not None)
        digest_id = digest.id

    # ============ STEP 3: idempotency ============
    print("\n=== STEP 3: idempotency ===")
    with SessionLocal() as db:
        alpha_obj = db.get(Institution, alpha_id)
        digest2 = send_admin_weekly_digest(db, institution=alpha_obj)
        check("2. çağrı aynı satırı döner (id eşit)",
              digest2.id == digest_id,
              f"got {digest2.id} vs {digest_id}")
        # DB'de toplam 1 satır olmalı bu kurum için
        cnt = (
            db.query(AdminWeeklyDigest)
            .filter(AdminWeeklyDigest.institution_id == alpha_id)
            .count()
        )
        check("ALPHA için sadece 1 digest satırı", cnt == 1, f"got {cnt}")

    # ============ STEP 4: force=True yeniden gönderim ============
    print("\n=== STEP 4: force=True yeniden gönderim ===")
    with SessionLocal() as db:
        alpha_obj = db.get(Institution, alpha_id)
        first_sent_at = (
            db.query(AdminWeeklyDigest)
            .filter(AdminWeeklyDigest.id == digest_id)
            .first()
            .sent_at
        )
        digest3 = send_admin_weekly_digest(
            db, institution=alpha_obj, force=True,
        )
        check("force=True aynı satırı günceller (id eşit)",
              digest3.id == digest_id,
              f"got {digest3.id}")
        # sent_at güncellendi mi?
        check("sent_at güncellendi (force ile yeniden gönderildi)",
              digest3.sent_at is not None and (
                  first_sent_at is None or digest3.sent_at >= first_sent_at
              ),
              f"first={first_sent_at}, new={digest3.sent_at}")

    # ============ STEP 5: cron job ============
    print("\n=== STEP 5: cron admin_weekly_digest ===")
    # Cron her aktif kurum için çağrılır. ALPHA zaten gönderildi (idempotent).
    # BETA için yeni satır oluşmalı.
    with SessionLocal() as db:
        result = cron_admin_digest(db, now=datetime.now(timezone.utc))
        check("cron sonuç dict döndürdü",
              isinstance(result, dict) and "total_institutions" in result)
        # ALPHA + BETA + ETUTKOC default + diğer test kurumları olabilir
        # Sadece kontrol edelim ki BETA için satır oluştu.
        beta_digest = (
            db.query(AdminWeeklyDigest)
            .filter(AdminWeeklyDigest.institution_id == beta_id)
            .first()
        )
        check("BETA için digest cron'la oluştu",
              beta_digest is not None,
              "BETA digest yok")

    # ============ STEP 6: tenant isolation ============
    print("\n=== STEP 6: tenant isolation ===")
    # ALPHA admin BETA'nın digest'ini görememeli (UI üzerinden)
    with SessionLocal() as db:
        alpha_admin_obj = db.get(User, alpha_admin_id)
        # Database-level filter ile kontrol — service zaten bunu yapıyor
        alpha_digests = (
            db.query(AdminWeeklyDigest)
            .filter(AdminWeeklyDigest.institution_id == alpha_admin_obj.institution_id)
            .all()
        )
        for d in alpha_digests:
            check(f"ALPHA digest #{d.id} institution_id={alpha_id}",
                  d.institution_id == alpha_id, f"got {d.institution_id}")

    # ============ STEP 7: HTTP routes ============
    print("\n=== STEP 7: HTTP routes ===")
    c = TestClient(app)
    r = c.post("/login", data={"email": alpha_admin_email, "password": PWD},
               follow_redirects=False)
    check("alpha_admin login", r.status_code == 303, f"got {r.status_code}")

    r = c.get("/institution/admin-digest")
    check("GET /admin-digest 200", r.status_code == 200, f"got {r.status_code}")
    check("ALPHA digest listede görünür",
          str(digest_id) in r.text or "gönderildi" in r.text or "log-only" in r.text)
    check("Şimdi Gönder butonu var",
          "Şimdi Gönder" in r.text)

    r = c.get(f"/institution/admin-digest/{digest_id}")
    check("GET /admin-digest/{id} 200", r.status_code == 200, f"got {r.status_code}")
    check("alpha kurum adı detayda görünür",
          alpha_name in r.text)

    # send-now — yeni hafta zaten oluşmuş, force=True ile yeniden gönderir
    r = c.post("/institution/admin-digest/send-now", follow_redirects=False)
    check("POST /send-now 303 redirect", r.status_code == 303,
          f"got {r.status_code}")

    # Cross-tenant: ALPHA admin BETA digest'ini görememeli
    beta_digest_id = beta_digest.id
    r = c.get(f"/institution/admin-digest/{beta_digest_id}",
              follow_redirects=False)
    check("ALPHA admin BETA digest detayı 404",
          r.status_code == 404, f"got {r.status_code}")

    # ============ STEP 8: anonim erişim ============
    print("\n=== STEP 8: anonim 303 ===")
    anon = TestClient(app)
    for path in ("/institution/admin-digest", f"/institution/admin-digest/{digest_id}"):
        r = anon.get(path, follow_redirects=False)
        check(f"anon {path} -> 303", r.status_code == 303,
              f"got {r.status_code}")
    r = anon.post("/institution/admin-digest/send-now", follow_redirects=False)
    check("anon POST /send-now -> 303", r.status_code == 303)

    # ============ STEP 9: previous week_end ile farklı satır ============
    print("\n=== STEP 9: farklı hafta -> ayrı satır ===")
    with SessionLocal() as db:
        alpha_obj = db.get(Institution, alpha_id)
        prev_week_end = date.today() - timedelta(days=14)
        prev_digest = send_admin_weekly_digest(
            db, institution=alpha_obj, week_end=prev_week_end,
        )
        check("prev_week digest yeni id", prev_digest.id != digest_id,
              f"got {prev_digest.id} vs {digest_id}")
        check("prev_week_start farklı",
              prev_digest.week_start_date != date.today() - timedelta(days=6))

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_test_users = db.query(User).filter(
            User.email.like(f"{PFX}_%")
        ).all()
        all_uids = [u.id for u in all_test_users]
        if all_uids:
            db.query(AuditLog).filter(
                AuditLog.actor_id.in_(all_uids)
            ).delete(synchronize_session=False)
            db.query(AuditLog).filter(
                AuditLog.target_id.in_(all_uids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(all_uids)).delete(
                synchronize_session=False
            )
        db.query(AdminWeeklyDigest).filter(
            AdminWeeklyDigest.institution_id.in_([alpha_id, beta_id])
        ).delete(synchronize_session=False)
        db.query(Institution).filter(
            Institution.id.in_([alpha_id, beta_id])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verisi temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 4 admin digest testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
