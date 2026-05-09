"""Stage 5 — Tenant health scorecard kapsamlı smoke test.

Senaryolar:
1. 3 sentetik kurum (sağlıklı / riskli / kritik) yarat
2. compute_health_score her kurum için doğru seviye verir mi?
3. bulk_health_assessment kritik kurumları üste sıralar mı?
4. Her gösterge tetiklenebilir mi (no_teacher_login_30d, no_student_login_30d,
   low_active_*, low_completion, empty_institution)?
5. churn_summary doğru sayar mı?
6. filter_unhealthy seviyelere göre filtreler mi?
7. /admin/institutions HTTP — 3 kurum tabloda görünür, kritik üstte
8. /admin/institutions?filter_level=critical — sadece kritik kurum görünür
9. /admin/institutions/{id} HTTP — sağlık paneli + indicators görünür
10. /admin HTTP — churn callout + en kritik 3 kurum görünür
11. Cleanup — tüm test verisi silinir
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import require_super_admin, require_user, get_current_user
from app.main import app
from app.models import (
    AuditLog,
    Institution,
    Task,
    TaskBookItem,
    User,
    UserRole,
)
from app.services.tenant_health import (
    bulk_health_assessment,
    churn_summary,
    compute_health_score,
    filter_unhealthy,
)


PFX = f"_health_{secrets.token_hex(3)}"

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
    today = now.date()

    print("\n=== SEED: 3 sentetik kurum ===")
    with SessionLocal() as db:
        # ---- HEALTHY: aktif kullanım, yüksek tamamlama ----
        h_inst = Institution(
            name=f"{PFX}_healthy", slug=f"{PFX}-healthy",
            plan="professional", is_active=True,
        )
        # ---- RISK: bazı göstergeler tetikli ama kritik değil ----
        r_inst = Institution(
            name=f"{PFX}_risk", slug=f"{PFX}-risk",
            plan="starter", is_active=True,
        )
        # ---- CRITICAL: çoğu gösterge kırmızı ----
        c_inst = Institution(
            name=f"{PFX}_critical", slug=f"{PFX}-critical",
            plan="free", is_active=True,
        )
        # ---- EMPTY: hiç kullanıcı yok ----
        e_inst = Institution(
            name=f"{PFX}_empty", slug=f"{PFX}-empty",
            plan="free", is_active=True,
        )
        db.add_all([h_inst, r_inst, c_inst, e_inst]); db.flush()
        h_id, r_id, c_id, e_id = h_inst.id, r_inst.id, c_inst.id, e_inst.id

        def _user(role, inst_id, *, name, last_login_days=None, teacher_id=None):
            ll = None if last_login_days is None else now - timedelta(days=last_login_days)
            u = User(
                email=f"{PFX}_{name}@test.invalid",
                password_hash="x" * 60,  # geçerli bcrypt formatına gerek yok
                full_name=name, role=role,
                institution_id=inst_id, teacher_id=teacher_id,
                is_active=True, password_changed_at=now,
                must_change_password=False, last_login_at=ll,
            )
            db.add(u); db.flush()
            return u

        # HEALTHY: 2 öğretmen son 3-5 gün login + 4 öğrenci son 1-3 gün login
        # (4/4 = %100 öğrenci aktivite, %100 öğretmen — hiç gösterge tetiklenmez)
        h_t1 = _user(UserRole.TEACHER, h_id, name="h_t1", last_login_days=1)
        h_t2 = _user(UserRole.TEACHER, h_id, name="h_t2", last_login_days=3)
        for i, dl in enumerate([1, 2, 3, 2]):
            _user(UserRole.STUDENT, h_id, name=f"h_s{i}", last_login_days=dl,
                  teacher_id=h_t1.id if i < 2 else h_t2.id)

        # RISK: 1 öğretmen 8 gün önce login (>7g cutoff → low_active_teacher_pct=0%),
        # 3 öğrenci son 25 gün önce login (>7g cutoff ama <30g → low_active_student_pct=0%)
        # Toplam: low_active_teacher_pct (15) + low_active_student_pct (15) = 30 → watch
        r_t1 = _user(UserRole.TEACHER, r_id, name="r_t1", last_login_days=8)
        for i in range(3):
            _user(UserRole.STUDENT, r_id, name=f"r_s{i}",
                  last_login_days=25, teacher_id=r_t1.id)

        # CRITICAL: 1 öğretmen 35 gün önce login (>30g + >7g), 2 öğrenci 35-50 gün önce
        # Toplam: no_teacher_login_30d (30) + low_active_teacher_pct (15)
        #         + no_student_login_30d (25) + low_active_student_pct (15) = 85 → critical
        c_t1 = _user(UserRole.TEACHER, c_id, name="c_t1", last_login_days=35)
        for i, dl in enumerate([35, 50]):
            _user(UserRole.STUDENT, c_id, name=f"c_s{i}",
                  last_login_days=dl, teacher_id=c_t1.id)

        # EMPTY: hiç kullanıcı yok — empty_institution göstergesi tetiklenir

        db.commit()
        print(f"  HEALTHY={h_id}, RISK={r_id}, CRITICAL={c_id}, EMPTY={e_id}")

    # ============ STEP 1: compute_health_score ============
    print("\n=== STEP 1: compute_health_score her kurum ===")
    with SessionLocal() as db:
        h_obj = db.get(Institution, h_id)
        r_obj = db.get(Institution, r_id)
        c_obj = db.get(Institution, c_id)
        e_obj = db.get(Institution, e_id)

        ha = compute_health_score(db, institution=h_obj, now=now, today=today)
        ra = compute_health_score(db, institution=r_obj, now=now, today=today)
        ca = compute_health_score(db, institution=c_obj, now=now, today=today)
        ea = compute_health_score(db, institution=e_obj, now=now, today=today)

        print(f"  HEALTHY: score={ha.score} level={ha.level} ind={[i.code for i in ha.indicators]}")
        print(f"  RISK:    score={ra.score} level={ra.level} ind={[i.code for i in ra.indicators]}")
        print(f"  CRITICAL: score={ca.score} level={ca.level} ind={[i.code for i in ca.indicators]}")
        print(f"  EMPTY:   score={ea.score} level={ea.level} ind={[i.code for i in ea.indicators]}")

        check("HEALTHY level=healthy", ha.level == "healthy", f"got {ha.level} score={ha.score}")
        check("HEALTHY teacher_count=2", ha.teacher_count == 2, f"got {ha.teacher_count}")
        check("HEALTHY student_count=4", ha.student_count == 4, f"got {ha.student_count}")
        check("HEALTHY indicators boş (sağlıklı)", len(ha.indicators) == 0,
              f"got {[i.code for i in ha.indicators]}")
        check("HEALTHY no critical indicators",
              "no_teacher_login_30d" not in [i.code for i in ha.indicators]
              and "no_student_login_30d" not in [i.code for i in ha.indicators])

        check("RISK level >= watch",
              ra.level in ("watch", "risk", "critical"), f"got {ra.level} score={ra.score}")
        check("RISK has low_active_teacher_pct",
              "low_active_teacher_pct" in [i.code for i in ra.indicators],
              f"indicators: {[i.code for i in ra.indicators]}")
        check("RISK has low_active_student_pct",
              "low_active_student_pct" in [i.code for i in ra.indicators],
              f"indicators: {[i.code for i in ra.indicators]}")

        check("CRITICAL level=critical", ca.level == "critical",
              f"got {ca.level} score={ca.score}")
        check("CRITICAL has no_teacher_login_30d",
              "no_teacher_login_30d" in [i.code for i in ca.indicators],
              f"indicators: {[i.code for i in ca.indicators]}")
        check("CRITICAL has no_student_login_30d",
              "no_student_login_30d" in [i.code for i in ca.indicators])
        check("CRITICAL score >= 70", ca.score >= 70, f"got {ca.score}")

        check("EMPTY has empty_institution indicator",
              "empty_institution" in [i.code for i in ea.indicators],
              f"indicators: {[i.code for i in ea.indicators]}")

    # ============ STEP 2: bulk_health_assessment sıralama ============
    print("\n=== STEP 2: bulk_health_assessment sıralama ===")
    with SessionLocal() as db:
        insts = [
            db.get(Institution, h_id),
            db.get(Institution, r_id),
            db.get(Institution, c_id),
            db.get(Institution, e_id),
        ]
        results = bulk_health_assessment(db, institutions=insts, now=now, today=today)
        check("4 kurum dönüldü", len(results) == 4, f"got {len(results)}")
        # Skor desc — kritik üstte
        check("İlk eleman en yüksek skor",
              results[0].score >= results[-1].score,
              f"first={results[0].score} last={results[-1].score}")
        # Critical kurum, healthy'den önce gelmeli
        c_idx = next(i for i, r in enumerate(results) if r.institution.id == c_id)
        h_idx = next(i for i, r in enumerate(results) if r.institution.id == h_id)
        check("CRITICAL listede HEALTHY'den önce",
              c_idx < h_idx, f"c_idx={c_idx} h_idx={h_idx}")

    # ============ STEP 3: churn_summary ============
    print("\n=== STEP 3: churn_summary sayım ===")
    summary = churn_summary(results)
    check("summary keys",
          all(k in summary for k in ["healthy", "watch", "risk", "critical", "unhealthy_total"]))
    check("Healthy >= 1 (HEALTHY kurumumuz)", summary["healthy"] >= 1,
          f"got {summary['healthy']}")
    check("Critical >= 1 (CRITICAL kurumumuz)", summary["critical"] >= 1,
          f"got {summary['critical']}")
    check("unhealthy_total tutarlı",
          summary["unhealthy_total"] == summary["watch"] + summary["risk"] + summary["critical"])

    # ============ STEP 4: filter_unhealthy ============
    print("\n=== STEP 4: filter_unhealthy ===")
    only_critical = filter_unhealthy(results, min_level="critical")
    check("filter critical >= 1", len(only_critical) >= 1, f"got {len(only_critical)}")
    check("filter critical sadece critical seviye",
          all(r.level == "critical" for r in only_critical),
          f"levels: {[r.level for r in only_critical]}")

    only_unhealthy = filter_unhealthy(results, min_level="watch")
    check("filter watch+ healthy hariç",
          all(r.level != "healthy" for r in only_unhealthy),
          f"levels: {[r.level for r in only_unhealthy]}")

    # ============ STEP 5: HTTP /admin/institutions ============
    print("\n=== STEP 5: HTTP /admin/institutions ===")
    with SessionLocal() as db:
        sa = db.query(User).filter(
            User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True),
        ).first()
        check("Süper admin var", sa is not None)
        sa_id = sa.id

    def _override():
        db = SessionLocal()
        try:
            u = db.get(User, sa_id)
            db.expunge(u)
            return u
        finally:
            db.close()

    app.dependency_overrides[require_super_admin] = _override
    app.dependency_overrides[require_user] = _override
    app.dependency_overrides[get_current_user] = _override

    try:
        c = TestClient(app)

        r = c.get("/admin/institutions")
        check("GET /admin/institutions 200", r.status_code == 200, f"got {r.status_code}")
        body = r.text
        check("Tüm 4 test kurumu listede",
              all(name in body for name in [
                  f"{PFX}_healthy", f"{PFX}_risk", f"{PFX}_critical", f"{PFX}_empty",
              ]))
        check("Sağlık özet kartları var",
              all(k in body for k in ["Sağlıklı", "Gözlem", "Riskli", "Kritik"]))

        # Default sıralama: skoru yüksek (kritik) üstte; healthy aşağıda
        critical_pos = body.find(f"{PFX}_critical")
        healthy_pos = body.find(f"{PFX}_healthy")
        check("CRITICAL listede HEALTHY'den önce (default sort=health)",
              0 <= critical_pos < healthy_pos,
              f"crit_pos={critical_pos} hlth_pos={healthy_pos}")

        # filter_level=critical
        r = c.get("/admin/institutions?filter_level=critical")
        check("filter_level=critical 200", r.status_code == 200)
        body = r.text
        check("filter critical: CRITICAL kurum görünür", f"{PFX}_critical" in body)
        check("filter critical: HEALTHY görünmez", f"{PFX}_healthy" not in body)

        # filter_level=unhealthy
        r = c.get("/admin/institutions?filter_level=unhealthy")
        check("filter_level=unhealthy 200", r.status_code == 200)
        body = r.text
        check("filter unhealthy: HEALTHY görünmez", f"{PFX}_healthy" not in body)
        check("filter unhealthy: CRITICAL görünür", f"{PFX}_critical" in body)

        # sort=name
        r = c.get("/admin/institutions?sort=name")
        check("sort=name 200", r.status_code == 200)

        # ============ STEP 6: HTTP /admin/institutions/{id} ============
        print("\n=== STEP 6: HTTP /admin/institutions/{id} detay ===")
        # CRITICAL detayı — health panel
        r = c.get(f"/admin/institutions/{c_id}")
        check("GET CRITICAL detail 200", r.status_code == 200)
        body = r.text
        check("CRITICAL detail: Sağlık Skoru paneli",
              "Sağlık Skoru" in body)
        check("CRITICAL detail: 'Kritik' etiketi", "Kritik" in body)
        check("CRITICAL detail: Yükselten Sebepler başlığı",
              "Bu Skoru Yükselten Sebepler" in body or "Risk göstergeleri" in body)

        # HEALTHY detayı — sağlıklı mesajı
        r = c.get(f"/admin/institutions/{h_id}")
        check("GET HEALTHY detail 200", r.status_code == 200)
        body = r.text
        check("HEALTHY detail: 'Sağlıklı' veya 'risk göstergesi yok'",
              "sağlıklı görünüyor" in body.lower() or "Sağlıklı" in body)

        # EMPTY detayı — empty_institution göstergesi görünmeli
        r = c.get(f"/admin/institutions/{e_id}")
        check("GET EMPTY detail 200", r.status_code == 200)
        body = r.text
        check("EMPTY detail: 'İçi boş kurum' göstergesi",
              "İçi boş kurum" in body)

        # ============ STEP 7: HTTP /admin dashboard churn callout ============
        print("\n=== STEP 7: HTTP /admin dashboard ===")
        r = c.get("/admin")
        check("GET /admin 200", r.status_code == 200)
        body = r.text
        check("Dashboard: 'Kurum Sağlığı' başlığı", "Kurum Sağlığı" in body)
        check("Dashboard: 'En çok dikkat isteyen kurumlar'",
              "En çok dikkat isteyen" in body)
        check("Dashboard: CRITICAL kurum top_unhealthy listede",
              f"{PFX}_critical" in body)

    finally:
        # Auth override'ı temizle
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

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
            # Task -> TaskBookItem cascade
            tids = [t.id for t in db.query(Task).filter(
                Task.student_id.in_(all_uids)
            ).all()]
            if tids:
                db.query(TaskBookItem).filter(
                    TaskBookItem.task_id.in_(tids)
                ).delete(synchronize_session=False)
                db.query(Task).filter(
                    Task.id.in_(tids)
                ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(all_uids)).delete(
                synchronize_session=False
            )
        db.query(Institution).filter(
            Institution.id.in_([h_id, r_id, c_id, e_id])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verisi temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 5 tenant health testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
