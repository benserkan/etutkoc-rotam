"""Stage 10 — KVKK denetim + veri ihracı + RTBF smoke test.

Senaryolar:
1. generate_user_export — teacher için JSON içerik (profile + audit + plan_history)
2. generate_user_export — parent için (links + notif prefs + notif logs)
3. generate_user_export — student için (tasks)
4. password REDACTED garanti
5. request_export — DataSubjectRequest COMPLETED + payload_json snapshot
6. request_deletion — PROCESSING + process_after = +30g
7. request_deletion idempotent (aynı kullanıcı 2 kez → tek kayıt)
8. cancel_request — kullanıcı kendi talebini iptal eder
9. cancel_request — yetki: başka kullanıcı talebini iptal edemez (PermissionError)
10. apply_deletion — anonimleştirme: full_name/email/password/phone temizlenir
11. apply_deletion — AuditLog USER_DELETE yazıldı
12. cron_apply_expired_deletions — process_after geçeni uygular, geçmeyene dokunmaz
13. HTTP /me → 200 (kullanıcı sayfası)
14. HTTP /me/data-export → 200 + Content-Disposition + JSON parse
15. HTTP POST /me/data-delete (confirm yok) → /me?err=confirm
16. HTTP POST /me/data-delete (confirm var) → DataSubjectRequest oluştu
17. HTTP /admin/kvkk → 200 + envanter + bekleyen taleplerle render
18. HTTP /kvkk public → 200 + KVKK madde 11 hak listesi
19. HTTP /privacy public → 200 + güvenlik bölümü
20. request_summary — durum sayım dict döndürür
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    DELETE_GRACE_PERIOD_DAYS,
    DataRequestKind,
    DataRequestStatus,
    DataSubjectRequest,
    Institution,
    NotificationLog,
    ParentNotificationPref,
    ParentStudentLink,
    ParentRelation,
    PlanChangeHistory,
    User,
    UserRole,
)
from app.services.kvkk import (
    DATA_INVENTORY,
    apply_deletion,
    cancel_request,
    cron_apply_expired_deletions,
    generate_user_export,
    request_deletion,
    request_export,
    request_summary,
)


PFX = f"_kvkk_{secrets.token_hex(3)}"
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
        teacher = User(
            email=f"{PFX}_teach@test.invalid", password_hash="x" * 60,
            full_name="Stage10 Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan="solo_pro",
        )
        student = User(
            email=f"{PFX}_stud@test.invalid", password_hash="y" * 60,
            full_name="Stage10 Student", role=UserRole.STUDENT,
            institution_id=None, is_active=True, password_changed_at=now,
        )
        parent = User(
            email=f"{PFX}_parent@test.invalid", password_hash="z" * 60,
            full_name="Stage10 Parent", role=UserRole.PARENT,
            institution_id=None, is_active=True, password_changed_at=now,
        )
        super_admin = User(
            email=f"{PFX}_sa@test.invalid", password_hash="s" * 60,
            full_name="Stage10 Super", role=UserRole.SUPER_ADMIN,
            institution_id=None, is_active=True, password_changed_at=now,
        )
        db.add_all([teacher, student, parent, super_admin]); db.flush()
        teacher_id, student_id, parent_id, sa_id = (
            teacher.id, student.id, parent.id, super_admin.id,
        )
        student.teacher_id = teacher_id
        link = ParentStudentLink(
            parent_id=parent_id, student_id=student_id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        pref = ParentNotificationPref(
            parent_id=parent_id, whatsapp_enabled=True,
            whatsapp_phone="+905551234567",
            whatsapp_phone_verified_at=now,
        )
        # Bir audit log
        audit = AuditLog(
            actor_id=teacher_id, action=AuditAction.LOGIN_SUCCESS,
            ip_address="127.0.0.1",
        )
        db.add_all([link, pref, audit]); db.commit()
        print(f"  teacher={teacher_id}, student={student_id}, parent={parent_id}, sa={sa_id}")

    # ============ STEP 1: generate_user_export — teacher ============
    print("\n=== STEP 1: generate_user_export teacher ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        payload = generate_user_export(db, user=u, requester=u)
        check("schema_version = 1", payload["schema_version"] == 1)
        check("data_subject email doğru",
              payload["data_subject"]["email"] == u.email)
        check("password_hash REDACTED",
              payload["data_subject"]["password_hash"] == "REDACTED")
        check("audit_logs liste",
              isinstance(payload["audit_logs"], list))
        check("plan_history liste",
              isinstance(payload["plan_history"], list))
        check("tasks boş (teacher öğrenci değil)",
              payload["tasks"] == [])

    # ============ STEP 2: generate_user_export — parent ============
    print("\n=== STEP 2: generate_user_export parent ===")
    with SessionLocal() as db:
        u = db.get(User, parent_id)
        payload = generate_user_export(db, user=u, requester=u)
        check("parent_student_links 1 satır",
              len(payload["parent_student_links"]) == 1)
        check("notification_preferences var",
              payload["notification_preferences"] is not None)
        check("whatsapp_phone export'da görünür",
              payload["notification_preferences"]["whatsapp_phone"] == "+905551234567")
        check("notification_logs liste",
              isinstance(payload["notification_logs"], list))

    # ============ STEP 3: generate_user_export — student ============
    print("\n=== STEP 3: generate_user_export student ===")
    with SessionLocal() as db:
        u = db.get(User, student_id)
        payload = generate_user_export(db, user=u, requester=u)
        check("tasks liste (öğrenci)", isinstance(payload["tasks"], list))
        check("parent_student_links 1 (student tarafında)",
              len(payload["parent_student_links"]) == 1)
        check("plan_history boş (student değil teacher)",
              payload["plan_history"] == [])

    # ============ STEP 4: request_export ============
    print("\n=== STEP 4: request_export ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        req = request_export(db, target=u, requester=u, reason="smoke test")
        check("request COMPLETED",
              req.status == DataRequestStatus.COMPLETED)
        check("kind = export", req.kind == DataRequestKind.EXPORT)
        check("payload_json doludur",
              req.payload_json and len(req.payload_json) > 100)
        # JSON parse edilebilir olmalı
        parsed = json.loads(req.payload_json)
        check("payload JSON parse edilebilir",
              parsed.get("data_subject", {}).get("email") == u.email)

    # ============ STEP 5: request_deletion ============
    print("\n=== STEP 5: request_deletion ===")
    with SessionLocal() as db:
        u = db.get(User, parent_id)
        req = request_deletion(db, target=u, requester=u, reason="smoke")
        check("request PROCESSING",
              req.status == DataRequestStatus.PROCESSING)
        check("kind = delete", req.kind == DataRequestKind.DELETE)
        check("process_after set", req.process_after is not None)
        if req.process_after:
            pa = req.process_after
            if pa.tzinfo is None:
                pa = pa.replace(tzinfo=timezone.utc)
            diff_days = (pa - now).days
            check("process_after ≈ +30g",
                  29 <= diff_days <= 30, f"diff={diff_days}")

    # ============ STEP 6: request_deletion idempotent ============
    print("\n=== STEP 6: request_deletion idempotent ===")
    with SessionLocal() as db:
        u = db.get(User, parent_id)
        req2 = request_deletion(db, target=u, requester=u)
        # İlk request_id == ikinci req2.id
        count = (
            db.query(DataSubjectRequest)
            .filter(
                DataSubjectRequest.target_user_id == parent_id,
                DataSubjectRequest.kind == DataRequestKind.DELETE,
                DataSubjectRequest.status.in_([
                    DataRequestStatus.PENDING, DataRequestStatus.PROCESSING,
                ]),
            )
            .count()
        )
        check("aktif silme talep tek satır", count == 1)

    # ============ STEP 7: cancel_request — kendi talebi ============
    print("\n=== STEP 7: cancel_request kendi talebi ===")
    with SessionLocal() as db:
        u = db.get(User, parent_id)
        # Bekleyen silme talebini bul
        req = (
            db.query(DataSubjectRequest)
            .filter(
                DataSubjectRequest.target_user_id == parent_id,
                DataSubjectRequest.status == DataRequestStatus.PROCESSING,
            )
            .first()
        )
        result = cancel_request(db, request_id=req.id, by_user=u)
        check("cancel result CANCELLED",
              result.status == DataRequestStatus.CANCELLED)

    # ============ STEP 8: cancel_request — yetkisiz ============
    print("\n=== STEP 8: cancel_request başka kullanıcı (yetkisiz) ===")
    # Yeni bir delete talebi aç (parent için)
    with SessionLocal() as db:
        u = db.get(User, parent_id)
        req = request_deletion(db, target=u, requester=u, reason="step8")

    with SessionLocal() as db:
        teacher_user = db.get(User, teacher_id)
        try:
            cancel_request(db, request_id=req.id, by_user=teacher_user)
            check("yetkisiz cancel → PermissionError", False, "exception bekleniyordu")
        except PermissionError:
            check("yetkisiz cancel → PermissionError", True)

    # ============ STEP 9: apply_deletion — anonimleştirme ============
    print("\n=== STEP 9: apply_deletion ===")
    with SessionLocal() as db:
        sa_user = db.get(User, sa_id)
        # Bekleyen talebi bul
        req = (
            db.query(DataSubjectRequest)
            .filter(
                DataSubjectRequest.target_user_id == parent_id,
                DataSubjectRequest.status == DataRequestStatus.PROCESSING,
            )
            .first()
        )
        check("bekleyen silme talebi var (apply için)", req is not None)
        if req:
            apply_deletion(db, request=req, by_user=sa_user)

    with SessionLocal() as db:
        u = db.get(User, parent_id)
        check("full_name = (Silinen Kullanıcı)",
              u.full_name == "(Silinen Kullanıcı)")
        check("email anonimize",
              "anonymized" in u.email and "@kvkk.local" in u.email)
        check("password_hash boş", u.password_hash == "")
        check("is_active = False", u.is_active is False)
        # ParentNotificationPref temizlendi
        pref = (
            db.query(ParentNotificationPref)
            .filter(ParentNotificationPref.parent_id == parent_id)
            .first()
        )
        check("whatsapp_phone temizlendi",
              pref is None or pref.whatsapp_phone is None)
        check("notif preferences hepsi kapalı",
              pref is None or (
                  not pref.daily_summary_enabled
                  and not pref.weekly_report_enabled
                  and not pref.whatsapp_enabled
              ))

        # Audit log USER_DELETE
        audit_rows = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == AuditAction.USER_DELETE,
                AuditLog.target_id == parent_id,
            )
            .all()
        )
        check("USER_DELETE audit yazıldı", len(audit_rows) >= 1)

    # ============ STEP 10: cron_apply_expired_deletions ============
    print("\n=== STEP 10: cron_apply_expired_deletions ===")
    # Yeni bir kullanıcı oluştur, silme talebi aç, process_after'ı geçmişe çek
    with SessionLocal() as db:
        cron_target = User(
            email=f"{PFX}_cron@test.invalid", password_hash="c" * 60,
            full_name="Cron Target", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
        )
        db.add(cron_target); db.commit()
        cron_target_id = cron_target.id

    with SessionLocal() as db:
        u = db.get(User, cron_target_id)
        req = request_deletion(db, target=u, requester=u)
        # Process_after'ı geçmişe çek
        req.process_after = now - timedelta(days=1)
        db.commit()

    with SessionLocal() as db:
        result = cron_apply_expired_deletions(db, now=now)
        check("cron processed >= 1",
              result.get("processed", 0) >= 1)

    with SessionLocal() as db:
        u = db.get(User, cron_target_id)
        check("cron sonrası anonimize edildi",
              u.full_name == "(Silinen Kullanıcı)")

    # ============ STEP 11: cron — process_after gelmemiş atlanır ============
    print("\n=== STEP 11: cron skipped_not_due ===")
    with SessionLocal() as db:
        future_user = User(
            email=f"{PFX}_future@test.invalid", password_hash="f" * 60,
            full_name="Future Target", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
        )
        db.add(future_user); db.commit()
        future_id = future_user.id

    with SessionLocal() as db:
        u = db.get(User, future_id)
        req = request_deletion(db, target=u, requester=u)
        # Default process_after = +30g (gelecek)

    with SessionLocal() as db:
        result = cron_apply_expired_deletions(db, now=now)
        # Yeni eklediğimiz future_user dokunulmamış olmalı
        u = db.get(User, future_id)
        check("future user hâlâ aktif (process_after ileri)",
              u.full_name == "Future Target")

    # ============ STEP 12: HTTP /me ============
    print("\n=== STEP 12: HTTP /me ===")
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
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)

    r = client.get("/me")
    check("/me 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("'Hesabım ve Verilerim' başlığı",
          "Hesabım ve Verilerim" in body)
    check("'Verilerimi İndir' CTA",
          "Verilerimi İndir" in body)
    check("'Hesabımı Sil' bölümü", "Hesabımı Sil" in body)
    check("KVKK madde 11 hak listesi",
          "KVKK Madde 11" in body or "veri sahibi" in body.lower())

    # ============ STEP 13: HTTP /me/data-export ============
    print("\n=== STEP 13: /me/data-export ===")
    r = client.get("/me/data-export")
    check("/me/data-export 200", r.status_code == 200)
    check("Content-Disposition attachment",
          "attachment" in r.headers.get("content-disposition", ""))
    check("Content-Type JSON",
          "json" in r.headers.get("content-type", ""))
    parsed = json.loads(r.text)
    check("body data_subject email teacher",
          parsed["data_subject"]["email"] == f"{PFX}_teach@test.invalid")
    check("password_hash REDACTED HTTP'de de",
          parsed["data_subject"]["password_hash"] == "REDACTED")

    # ============ STEP 14: POST /me/data-delete ============
    print("\n=== STEP 14: POST /me/data-delete ===")
    # Confirm yok → reddedilir
    r = client.post("/me/data-delete",
                    data={"reason": "test", "confirm": ""},
                    follow_redirects=False)
    check("confirm yok → 303",
          r.status_code in (302, 303))
    check("redirect ?err=confirm",
          "err=confirm" in r.headers.get("location", ""))

    # Confirm ile
    r = client.post("/me/data-delete",
                    data={"reason": "test", "confirm": "yes"},
                    follow_redirects=False)
    check("confirm var → 303",
          r.status_code in (302, 303))
    check("redirect ?delete_requested=1",
          r.headers.get("location", "").endswith("?delete_requested=1"))

    # DB'de talep oluştu
    with SessionLocal() as db:
        req = (
            db.query(DataSubjectRequest)
            .filter(
                DataSubjectRequest.target_user_id == teacher_id,
                DataSubjectRequest.kind == DataRequestKind.DELETE,
                DataSubjectRequest.status == DataRequestStatus.PROCESSING,
            )
            .first()
        )
        check("DB'de delete talebi", req is not None)

    app.dependency_overrides.clear()

    # ============ STEP 15: HTTP /admin/kvkk ============
    print("\n=== STEP 15: HTTP /admin/kvkk ===")
    app.dependency_overrides[get_current_user] = make_user_override(sa_id)
    app.dependency_overrides[require_super_admin] = make_user_override(sa_id)
    r = client.get("/admin/kvkk")
    check("/admin/kvkk 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("'KVKK Denetim Paneli' başlığı",
          "KVKK Denetim Paneli" in body)
    check("Sistem Veri Envanteri",
          "Sistem Veri Envanteri" in body)
    check("Bekleyen talepler bölümü",
          "Bekleyen Talepler" in body)
    # Envanter sayım
    check("DATA_INVENTORY 9 kategori",
          len(DATA_INVENTORY) == 9)
    app.dependency_overrides.clear()

    # ============ STEP 16: HTTP /kvkk public ============
    print("\n=== STEP 16: /kvkk public ===")
    r = client.get("/kvkk")
    check("/kvkk 200", r.status_code == 200)
    body = r.text
    check("KVKK Aydınlatma Metni",
          "KVKK Aydınlatma Metni" in body)
    check("Madde 11 başlığı",
          "Madde 11" in body)
    check("KVKK email iletişim",
          "kvkk@etutkoc.com" in body)

    # ============ STEP 17: HTTP /privacy public ============
    print("\n=== STEP 17: /privacy public ===")
    r = client.get("/privacy")
    check("/privacy 200", r.status_code == 200)
    body = r.text
    check("Gizlilik Politikası",
          "Gizlilik Politikası" in body)
    check("'Verilerinizi asla satmayız' güvencesi",
          "satmayız" in body.lower() or "verilerinizi" in body.lower())

    # ============ STEP 18: request_summary ============
    print("\n=== STEP 18: request_summary ===")
    with SessionLocal() as db:
        s = request_summary(db)
        check("summary total >= 1", s["total"] >= 1)
        check("summary tüm durumlar dict'te",
              all(k in s for k in ("pending", "processing", "completed", "cancelled", "rejected")))

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_ids = [teacher_id, student_id, parent_id, sa_id, cron_target_id, future_id]
        db.execute(delete(DataSubjectRequest).where(
            DataSubjectRequest.target_user_id.in_(all_ids)
        ))
        db.execute(delete(ParentStudentLink).where(
            (ParentStudentLink.parent_id.in_(all_ids))
            | (ParentStudentLink.student_id.in_(all_ids))
        ))
        db.execute(delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(all_ids)
        ))
        db.execute(delete(AuditLog).where(
            (AuditLog.actor_id.in_(all_ids))
            | (AuditLog.target_id.in_(all_ids))
        ))
        db.execute(delete(PlanChangeHistory).where(
            PlanChangeHistory.owner_id.in_(all_ids)
        ))
        db.execute(delete(NotificationLog).where(
            NotificationLog.parent_id.in_(all_ids)
        ))
        db.execute(delete(User).where(User.id.in_(all_ids)))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
