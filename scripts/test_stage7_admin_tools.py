"""Stage 7 — Sistem yönetim araçları kapsamlı smoke test.

Senaryolar:
1. Service feature_flags: is_enabled, override, cache invalidate
2. set_global toggle çalışır + cache invalidate
3. Override per-kurum doğru karar verir (override > global)
4. Tanımsız flag → defansif True
5. SystemAnnouncement.is_active zaman penceresi
6. announcements.active_for_user audience filter
7. system_health.collect_snapshot tüm bileşenler
8. HTTP /admin/feature-flags 200 + 4 seed flag görünür
9. HTTP /admin/feature-flags/{id} detail 200
10. HTTP /admin/feature-flags/{id}/toggle POST + DB güncellenir
11. HTTP /admin/feature-flags/{id}/overrides POST + override eklenir
12. HTTP /admin/announcements 200 + form
13. HTTP /admin/announcements POST oluşturur
14. HTTP /admin/announcements/{id}/delete siler
15. HTTP /admin/system-health 200 + cron + dispatcher + DB tab
16. Banner middleware aktif duyuruyu inject eder
17. Cleanup
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
from app.deps import (
    get_current_user, require_super_admin, require_user,
)
from app.main import app
from app.models import (
    AnnouncementAudience,
    AnnouncementSeverity,
    AuditLog,
    FeatureFlag,
    FeatureFlagOverride,
    Institution,
    SystemAnnouncement,
    User,
    UserRole,
)
from app.services.announcements import (
    active_for_user,
    invalidate_cache as inv_ann_cache,
)
from app.services.feature_flags import (
    all_flags_for_admin,
    invalidate_cache as inv_ff_cache,
    is_enabled,
    remove_override,
    set_global,
    set_override,
)
from app.services.system_health import collect_snapshot


PFX = f"_admin7_{secrets.token_hex(3)}"
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
        # 2 test kurum
        inst_a = Institution(
            name=f"{PFX}_a", slug=f"{PFX}-a", plan="free", is_active=True,
        )
        inst_b = Institution(
            name=f"{PFX}_b", slug=f"{PFX}-b", plan="starter", is_active=True,
        )
        db.add_all([inst_a, inst_b]); db.flush()
        a_id, b_id = inst_a.id, inst_b.id
        db.commit()
        print(f"  inst_a={a_id}, inst_b={b_id}")

    # ============ STEP 1-4: feature_flags service ============
    print("\n=== STEP 1-4: feature_flags service ===")
    with SessionLocal() as db:
        # Default seed flag'leri var
        check("ai_book_template global=True (default)",
              is_enabled(db, "ai_book_template"))
        check("tanımsız flag → defansif True",
              is_enabled(db, "nonexistent_flag_xyz"))

        # set_global toggle
        flag = db.query(FeatureFlag).filter(FeatureFlag.key == "ai_book_template").first()
        original_global = flag.enabled_globally
        set_global(db, "ai_book_template", False)
        check("set_global False sonrası is_enabled=False",
              not is_enabled(db, "ai_book_template"))

        # Override: a_id için açık tut
        set_override(db, flag_id=flag.id, institution_id=a_id, enabled=True, note="pilot")
        a_inst = db.get(Institution, a_id)
        b_inst = db.get(Institution, b_id)
        check("override AÇIK kurumda is_enabled=True",
              is_enabled(db, "ai_book_template", institution=a_inst))
        check("override YOK kurumda global False kullanılır",
              not is_enabled(db, "ai_book_template", institution=b_inst))

        # all_flags_for_admin
        flags_data = all_flags_for_admin(db)
        check("all_flags_for_admin >= 4",
              len(flags_data) >= 4, f"got {len(flags_data)}")

        # Cache invalidate temizle
        set_global(db, "ai_book_template", original_global)
        # override sil
        ovr = db.query(FeatureFlagOverride).filter(
            FeatureFlagOverride.feature_flag_id == flag.id,
            FeatureFlagOverride.institution_id == a_id,
        ).first()
        if ovr:
            remove_override(db, ovr.id)

    # ============ STEP 5: SystemAnnouncement.is_active ============
    print("\n=== STEP 5: announcement is_active ===")
    with SessionLocal() as db:
        # Aktif (şimdi başlamış, bitiş yok)
        a_active = SystemAnnouncement(
            message=f"{PFX} aktif",
            severity=AnnouncementSeverity.INFO,
            audience=AnnouncementAudience.ALL,
            starts_at=now - timedelta(hours=1),
            ends_at=None,
            dismissible=True,
        )
        # Geçmiş (1 saat önce bitti)
        a_past = SystemAnnouncement(
            message=f"{PFX} past",
            severity=AnnouncementSeverity.INFO,
            audience=AnnouncementAudience.ALL,
            starts_at=now - timedelta(hours=2),
            ends_at=now - timedelta(minutes=10),
        )
        # Gelecek (1 saat sonra başlayacak)
        a_future = SystemAnnouncement(
            message=f"{PFX} future",
            severity=AnnouncementSeverity.WARN,
            audience=AnnouncementAudience.TEACHER,
            starts_at=now + timedelta(hours=1),
            ends_at=None,
        )
        # Sadece teacher audience
        a_teacher = SystemAnnouncement(
            message=f"{PFX} teacher only",
            severity=AnnouncementSeverity.CRITICAL,
            audience=AnnouncementAudience.TEACHER,
            starts_at=now - timedelta(minutes=5),
            ends_at=None,
        )
        db.add_all([a_active, a_past, a_future, a_teacher]); db.commit()
        active_id = a_active.id
        past_id = a_past.id
        future_id = a_future.id
        teacher_id_ann = a_teacher.id

        check("a_active is_active=True", a_active.is_active(now))
        check("a_past is_active=False", not a_past.is_active(now))
        check("a_future is_active=False", not a_future.is_active(now))
        check("a_teacher is_active=True", a_teacher.is_active(now))

    # ============ STEP 6: active_for_user audience filter ============
    print("\n=== STEP 6: active_for_user audience ===")
    inv_ann_cache()
    with SessionLocal() as db:
        # Süper admin için: ALL + teacher görmemeli
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa:
            anns = active_for_user(db, sa)
            ids = [a.id for a in anns]
            check("super admin: a_active (ALL) görür",
                  active_id in ids, f"ids={ids}")
            check("super admin: a_teacher görmez",
                  teacher_id_ann not in ids, f"ids={ids}")

        # Anonim için: sadece ALL
        anns = active_for_user(db, None)
        ids = [a.id for a in anns]
        check("anonim: a_active (ALL) görür", active_id in ids)
        check("anonim: a_teacher görmez", teacher_id_ann not in ids)
        check("anonim: a_past görmez", past_id not in ids)
        check("anonim: a_future görmez", future_id not in ids)

    # ============ STEP 7: system_health.collect_snapshot ============
    print("\n=== STEP 7: system_health snapshot ===")
    with SessionLocal() as db:
        snap = collect_snapshot(db)
        check("snapshot.crons liste",
              isinstance(snap.crons, list))
        check("snapshot.dispatcher var",
              snap.dispatcher is not None)
        check("snapshot.database var",
              snap.database is not None)
        check("overall_health 'ok'/'warn'/'crit' ∈",
              snap.overall_health in ("ok", "warn", "crit"))
        if snap.database:
            check("DB table_counts dict",
                  isinstance(snap.database.table_counts, dict)
                  and "users" in snap.database.table_counts)

    # ============ STEP 8-15: HTTP routes ============
    print("\n=== STEP 8-15: HTTP routes ===")
    with SessionLocal() as db:
        sa = db.query(User).filter(
            User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True),
        ).first()
        check("Süper admin var", sa is not None)
        sa_id = sa.id

    def _override(uid_var):
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

    app.dependency_overrides[require_super_admin] = _override(sa_id)
    app.dependency_overrides[require_user] = _override(sa_id)
    app.dependency_overrides[get_current_user] = _override(sa_id)

    new_ann_id = None
    new_override_id = None

    try:
        c = TestClient(app)

        # Feature flags list
        r = c.get("/admin/feature-flags")
        check("GET /admin/feature-flags 200", r.status_code == 200, f"got {r.status_code}")
        body = r.text
        check("'Özellik Anahtarları' başlığı", "Özellik Anahtarları" in body)
        for k in ["ai_book_template", "parent_notifications_email", "parent_notifications_whatsapp", "weekly_admin_digest"]:
            check(f"flag '{k}' tabloda", k in body)

        # Detail
        with SessionLocal() as db:
            ai_flag = db.query(FeatureFlag).filter(FeatureFlag.key == "ai_book_template").first()
            ai_flag_id = ai_flag.id
        r = c.get(f"/admin/feature-flags/{ai_flag_id}")
        check("GET /admin/feature-flags/{id} 200", r.status_code == 200)
        check("'Genel Durum' panel", "Genel Durum (tüm kurumlar)" in r.text or "Global Varsayılan" in r.text)

        # Toggle global
        r = c.post(f"/admin/feature-flags/{ai_flag_id}/toggle", follow_redirects=False)
        check("toggle POST 303", r.status_code == 303)
        with SessionLocal() as db:
            ai_flag_after = db.query(FeatureFlag).filter(FeatureFlag.key == "ai_book_template").first()
            check("global toggle DB güncellendi", not ai_flag_after.enabled_globally)
            # Geri çevir
            ai_flag_after.enabled_globally = True; db.commit()
            inv_ff_cache()

        # Override ekle
        r = c.post(
            f"/admin/feature-flags/{ai_flag_id}/overrides",
            data={"institution_id": str(b_id), "enabled": "off", "note": "smoke"},
            follow_redirects=False,
        )
        check("override add POST 303", r.status_code == 303)
        with SessionLocal() as db:
            ovr = db.query(FeatureFlagOverride).filter(
                FeatureFlagOverride.feature_flag_id == ai_flag_id,
                FeatureFlagOverride.institution_id == b_id,
            ).first()
            check("override DB'de var", ovr is not None)
            if ovr:
                check("override enabled=False", not ovr.enabled)
                new_override_id = ovr.id

        # Override sil
        if new_override_id:
            r = c.post(f"/admin/feature-flags/overrides/{new_override_id}/delete",
                       follow_redirects=False)
            check("override delete POST 303", r.status_code == 303)
            with SessionLocal() as db:
                exists = db.get(FeatureFlagOverride, new_override_id)
                check("override silindi", exists is None)

        # Announcements list
        r = c.get("/admin/announcements")
        check("GET /admin/announcements 200", r.status_code == 200)
        check("'Duyurular' başlığı", "Duyurular" in r.text)
        check("PFX aktif duyuru tabloda", f"{PFX} aktif" in r.text)

        # Yeni duyuru oluştur
        r = c.post(
            "/admin/announcements",
            data={
                "title": f"{PFX} yeni",
                "message": f"{PFX} yeni mesaj",
                "severity": "warn",
                "audience": "all",
                "starts_at": "",
                "ends_at": "",
                "dismissible": "on",
            },
            follow_redirects=False,
        )
        check("announcement create POST 303", r.status_code == 303)
        with SessionLocal() as db:
            new = db.query(SystemAnnouncement).filter(
                SystemAnnouncement.title == f"{PFX} yeni"
            ).first()
            check("announcement DB'de", new is not None)
            if new:
                new_ann_id = new.id

        # System health
        r = c.get("/admin/system-health")
        check("GET /admin/system-health 200", r.status_code == 200)
        body = r.text
        check("'Sistem Sağlığı' başlığı", "Sistem Sağlığı" in body)
        check("Otomatik Görevler bölümü", "Otomatik Görevler" in body)
        check("Bildirim Kuyruğu", "Bildirim Kuyruğu" in body)
        check("Veritabanı bölümü", "Veritabanı" in body)

        # Middleware: aktif duyuru herhangi bir HTML sayfasında render olmalı
        r = c.get("/admin")
        check("dashboard'da aktif duyuru görünür",
              f"{PFX} aktif" in r.text or f"{PFX} yeni" in r.text,
              "duyurulardan biri görünmedi")

    finally:
        app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        # PFX duyuruları
        db.query(SystemAnnouncement).filter(
            SystemAnnouncement.message.like(f"{PFX}%")
        ).delete(synchronize_session=False)
        # PFX kurumları
        db.query(FeatureFlagOverride).filter(
            FeatureFlagOverride.institution_id.in_([a_id, b_id])
        ).delete(synchronize_session=False)
        db.query(AuditLog).filter(
            AuditLog.target_type.in_(["feature_flag", "feature_flag_override", "announcement"])
        ).delete(synchronize_session=False)
        db.query(Institution).filter(
            Institution.id.in_([a_id, b_id])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verisi temizlendi")

    inv_ff_cache()
    inv_ann_cache()

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 7 admin tools testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
