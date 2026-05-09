"""Stage 8 — Kuota + Tenant backup kapsamlı smoke test.

Senaryolar:
1. PLAN_QUOTAS sabit + get_default_limit
2. get_quota_limit override > plan
3. count_current_usage role-bazlı sayım
4. check_quota_for_create OK + QuotaExceeded
5. extra_count toplu (CSV import) check
6. set_override / remove_override
7. get_quota_summary tam liste
8. /institution/quota HTTP 200 + içerik
9. /admin/quota HTTP 200 + tüm kurum tablosu
10. /admin/quota/{id}/override POST + DB güncellenir
11. /admin/quota/overrides/{id}/delete POST
12. tenant_backup.export_tenant döndürdüğü dict — counts + content
13. password_hash REDACTED
14. /admin/institutions/{id}/backup endpoint download (Content-Disposition)
15. backup içeriği parse edilebilir JSON
16. Cross-tenant: backup başka kurumun verisi içermez
17. Audit log yazılır
18. Cleanup
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import (
    get_current_user, require_super_admin, require_user,
)
from app.main import app
from app.models import (
    AuditLog,
    Institution,
    InstitutionQuotaOverride,
    User,
    UserRole,
)
from app.services.quotas import (
    PLAN_QUOTAS,
    QUOTA_KEYS,
    QuotaExceeded,
    check_quota_for_create,
    count_current_usage,
    get_default_limit,
    get_quota_limit,
    get_quota_summary,
    remove_override,
    set_override,
)
from app.services.tenant_backup import (
    SCHEMA_VERSION,
    export_tenant,
    export_tenant_json,
)


PFX = f"_q8_{secrets.token_hex(3)}"
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

    print("\n=== SEED ===")
    with SessionLocal() as db:
        inst_a = Institution(
            name=f"{PFX}_a", slug=f"{PFX}-a", plan="free", is_active=True,
        )
        inst_b = Institution(
            name=f"{PFX}_b", slug=f"{PFX}-b", plan="starter", is_active=True,
        )
        db.add_all([inst_a, inst_b]); db.flush()
        a_id, b_id = inst_a.id, inst_b.id

        # 1 öğretmen + 1 öğrenci a_id altında
        a_teacher = User(
            email=f"{PFX}_a_t@test.invalid", password_hash="x" * 60,
            full_name="A Teacher", role=UserRole.TEACHER,
            institution_id=a_id, is_active=True, password_changed_at=now,
        )
        db.add(a_teacher); db.flush()
        a_teacher_id = a_teacher.id
        a_student = User(
            email=f"{PFX}_a_s@test.invalid", password_hash="x" * 60,
            full_name="A Student", role=UserRole.STUDENT,
            institution_id=a_id, teacher_id=a_teacher_id,
            is_active=True, password_changed_at=now,
        )
        db.add(a_student)
        db.commit()
        print(f"  inst_a={a_id}(free), inst_b={b_id}(starter)")
        print(f"  a_teacher={a_teacher_id}, a_student={a_student.id}")

    # ============ STEP 1-2: PLAN_QUOTAS + get_quota_limit ============
    print("\n=== STEP 1-2: PLAN_QUOTAS + get_quota_limit ===")
    check("PLAN_QUOTAS 4 plan",
          set(PLAN_QUOTAS.keys()) == {"free", "starter", "professional", "enterprise"})
    check("free.teachers = 2", PLAN_QUOTAS["free"]["teachers"] == 2)
    check("enterprise.students = -1 (sınırsız)",
          PLAN_QUOTAS["enterprise"]["students"] == -1)
    check("get_default_limit free.students = 20",
          get_default_limit("free", "students") == 20)
    check("get_default_limit unknown plan → free fallback",
          get_default_limit("xyz", "teachers") == 2)

    with SessionLocal() as db:
        a_inst = db.get(Institution, a_id)
        b_inst = db.get(Institution, b_id)
        # default'tan free.students = 20
        limit, has_o, _ = get_quota_limit(db, institution=a_inst, quota_key="students")
        check("a_inst students default = 20", limit == 20 and not has_o)
        # b_inst starter.teachers = 10
        limit, _, _ = get_quota_limit(db, institution=b_inst, quota_key="teachers")
        check("b_inst teachers default = 10", limit == 10)

    # ============ STEP 3: count_current_usage ============
    print("\n=== STEP 3: count_current_usage ===")
    with SessionLocal() as db:
        check("a_inst teachers = 1",
              count_current_usage(db, institution_id=a_id, quota_key="teachers") == 1)
        check("a_inst students = 1",
              count_current_usage(db, institution_id=a_id, quota_key="students") == 1)
        check("b_inst students = 0 (boş)",
              count_current_usage(db, institution_id=b_id, quota_key="students") == 0)

    # ============ STEP 4: check_quota_for_create ============
    print("\n=== STEP 4: check_quota_for_create OK + QuotaExceeded ===")
    with SessionLocal() as db:
        a_inst = db.get(Institution, a_id)
        # a_inst students = 1/20 → OK
        try:
            check_quota_for_create(db, institution=a_inst, quota_key="students")
            check("a_inst students 1/20 → OK", True)
        except QuotaExceeded:
            check("a_inst students 1/20 → OK", False, "beklenmedik QuotaExceeded")

        # 19 daha + 1 yeni = 21/20 → exceeds
        try:
            check_quota_for_create(
                db, institution=a_inst, quota_key="students", extra_count=20,
            )
            check("a_inst students extra=20 → QuotaExceeded", False, "beklenen exception yok")
        except QuotaExceeded as e:
            check("a_inst students extra=20 → QuotaExceeded", True)
            check("QuotaExceeded.limit = 20", e.limit == 20)
            check("QuotaExceeded.current = 1", e.current == 1)

        # a_inst teachers = 1/2 → OK 1 daha
        try:
            check_quota_for_create(db, institution=a_inst, quota_key="teachers")
            check("a_inst teachers 1/2 → OK", True)
        except QuotaExceeded:
            check("a_inst teachers 1/2 → OK", False)

        # 2 daha → 3/2 → exceeds
        try:
            check_quota_for_create(
                db, institution=a_inst, quota_key="teachers", extra_count=2,
            )
            check("a_inst teachers extra=2 → exceeds", False)
        except QuotaExceeded:
            check("a_inst teachers extra=2 → exceeds", True)

    # ============ STEP 6: set_override / remove_override ============
    print("\n=== STEP 6: set_override + remove_override ===")
    with SessionLocal() as db:
        # Override: a_inst students = 100
        o = set_override(
            db, institution_id=a_id, quota_key="students",
            override_value=100, note="smoke test bonus",
        )
        check("set_override yeni satır", o.id is not None)
        check("override_value = 100", o.override_value == 100)

        a_inst = db.get(Institution, a_id)
        limit, has_o, note = get_quota_limit(db, institution=a_inst, quota_key="students")
        check("override sonrası limit = 100", limit == 100 and has_o)
        check("override note = 'smoke test bonus'", note == "smoke test bonus")

        # check_quota_for_create extra=10 artık OK (1+10 = 11 < 100)
        try:
            check_quota_for_create(
                db, institution=a_inst, quota_key="students", extra_count=10,
            )
            check("override sonrası extra=10 OK", True)
        except QuotaExceeded:
            check("override sonrası extra=10 OK", False)

        # update aynı kanal
        o2 = set_override(
            db, institution_id=a_id, quota_key="students",
            override_value=-1, note="şimdi sınırsız",
        )
        check("set_override aynı satırı günceller (id eşit)", o2.id == o.id)
        check("override_value = -1", o2.override_value == -1)
        a_inst = db.get(Institution, a_id)
        limit, _, _ = get_quota_limit(db, institution=a_inst, quota_key="students")
        check("güncel limit = -1 (sınırsız)", limit == -1)

        # Sınırsızken hiç check yok
        try:
            check_quota_for_create(
                db, institution=a_inst, quota_key="students", extra_count=10000,
            )
            check("sınırsız: 10000 ekleme bile OK", True)
        except QuotaExceeded:
            check("sınırsız: 10000 ekleme bile OK", False)

        ovr_id = o2.id
        ok = remove_override(db, ovr_id)
        check("remove_override True", ok)
        a_inst = db.get(Institution, a_id)
        limit, has_o, _ = get_quota_limit(db, institution=a_inst, quota_key="students")
        check("remove sonrası plan default'a döner (free=20)",
              limit == 20 and not has_o)

    # ============ STEP 7: get_quota_summary ============
    print("\n=== STEP 7: get_quota_summary ===")
    with SessionLocal() as db:
        a_inst = db.get(Institution, a_id)
        summary = get_quota_summary(db, institution=a_inst)
        check("summary 3 kuota", len(summary) == 3)
        students = next((q for q in summary if q.key == "students"), None)
        check("students summary",
              students is not None and students.current == 1 and students.limit == 20,
              f"got {students}")

    # ============ STEP 8-11: HTTP routes ============
    print("\n=== STEP 8-11: HTTP routes ===")
    with SessionLocal() as db:
        sa = db.query(User).filter(
            User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True),
        ).first()
        sa_id = sa.id

    def _override_factory(uid_var):
        def factory():
            db2 = SessionLocal()
            try:
                from sqlalchemy.orm import joinedload
                u = (
                    db2.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == uid_var)
                    .first()
                )
                _ = u.institution
                db2.expunge_all()
                return u
            finally:
                db2.close()
        return factory

    app.dependency_overrides[require_super_admin] = _override_factory(sa_id)
    app.dependency_overrides[require_user] = _override_factory(sa_id)
    app.dependency_overrides[get_current_user] = _override_factory(sa_id)

    new_override_id = None
    backup_payload = None

    try:
        c = TestClient(app)

        # /admin/quota
        r = c.get("/admin/quota")
        check("GET /admin/quota 200", r.status_code == 200, f"got {r.status_code}")
        body = r.text
        check("'Kurum Limitleri' başlığı", "Kurum Limitleri" in body)
        check("inst_a tabloda", f"{PFX}_a" in body)
        check("inst_b tabloda", f"{PFX}_b" in body)

        # Override ekle
        r = c.post(
            f"/admin/quota/{a_id}/override",
            data={"quota_key": "students", "override_value": "50", "note": "smoke"},
            follow_redirects=False,
        )
        check("override POST 303", r.status_code == 303)
        with SessionLocal() as db:
            ovr = db.query(InstitutionQuotaOverride).filter(
                InstitutionQuotaOverride.institution_id == a_id,
                InstitutionQuotaOverride.quota_key == "students",
            ).first()
            check("override DB'de", ovr is not None)
            if ovr:
                check("override_value = 50", ovr.override_value == 50)
                new_override_id = ovr.id

        # Override sil
        if new_override_id:
            r = c.post(f"/admin/quota/overrides/{new_override_id}/delete",
                       follow_redirects=False)
            check("override delete 303", r.status_code == 303)
            with SessionLocal() as db:
                exists = db.get(InstitutionQuotaOverride, new_override_id)
                check("override silindi", exists is None)

        # ============ STEP 12-15: Backup ============
        print("\n=== STEP 12-15: Tenant backup ===")
        with SessionLocal() as db:
            a_inst = db.get(Institution, a_id)
            snap = export_tenant(db, institution=a_inst)
            check("snap.schema_version = 1", snap["schema_version"] == SCHEMA_VERSION)
            check("snap.institution.name doğru",
                  snap["institution"]["name"] == f"{PFX}_a")
            check("snap.counts var",
                  "counts" in snap and snap["counts"]["users"] == 2)  # 1 teacher + 1 student
            # password_hash REDACTED
            for u in snap["users"]:
                if u["password_hash"] != "REDACTED":
                    check("password_hash REDACTED", False,
                          f"got {u['password_hash']!r}")
                    break
            else:
                check("password_hash REDACTED tüm kullanıcılarda", True)

        # /admin/institutions/{id}/backup endpoint
        r = c.get(f"/admin/institutions/{a_id}/backup")
        check("GET backup 200", r.status_code == 200, f"got {r.status_code}")
        check("Content-Disposition attachment",
              "attachment" in r.headers.get("content-disposition", ""))
        check("dosya adı institution slug",
              f"{PFX}-a" in r.headers.get("content-disposition", ""))
        backup_payload = r.text
        # JSON parse
        try:
            parsed = json.loads(backup_payload)
            check("JSON parse OK", True)
            check("parsed.institution.id = a_id",
                  parsed["institution"]["id"] == a_id)
            check("parsed.users 2",
                  len(parsed["users"]) == 2)
        except Exception as e:
            check("JSON parse OK", False, str(e))

        # Cross-tenant: a_id backup'ında b_id yok
        if backup_payload:
            check("b_inst verisi a backup'ında yok",
                  f"{PFX}_b" not in backup_payload,
                  "BETA verisi sızdı")

        # b_id için ayrı backup
        r = c.get(f"/admin/institutions/{b_id}/backup")
        check("GET b backup 200", r.status_code == 200)
        b_payload = r.text
        b_parsed = json.loads(b_payload)
        check("b backup users=0", len(b_parsed["users"]) == 0,
              f"got {len(b_parsed['users'])}")

        # 404 olmayan kurum
        r = c.get("/admin/institutions/9999999/backup")
        check("yok kurum 404", r.status_code == 404)

        # Audit log yazıldı mı
        with SessionLocal() as db:
            recent_audit = (
                db.query(AuditLog)
                .filter(
                    AuditLog.target_type == "institution_backup",
                    AuditLog.target_id == a_id,
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            check("backup audit log yazıldı", recent_audit is not None)

    finally:
        app.dependency_overrides.clear()

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
        db.query(InstitutionQuotaOverride).filter(
            InstitutionQuotaOverride.institution_id.in_([a_id, b_id])
        ).delete(synchronize_session=False)
        db.query(AuditLog).filter(
            AuditLog.target_type.in_(
                ["institution_backup", "quota_override"]
            )
        ).delete(synchronize_session=False)
        db.query(Institution).filter(
            Institution.id.in_([a_id, b_id])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verisi temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 8 quotas+backup testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
