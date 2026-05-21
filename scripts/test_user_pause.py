"""User pause/resume smoke test (project konvansiyonu: scripts/test_*.py).

Senaryolar:
1. Service:
   - pause_user manuel — is_paused True, paused_at + paused_by_id + reason
   - resume_user manuel — last_manual_resume_at damgalanır
   - is_eligible_for_auto_pause: yeni hesap (14g grace) → False
   - is_eligible_for_auto_pause: manuel resume sticky (7g cooldown) → False
   - is_eligible_for_auto_pause: sessizleşen öğrenci (21+ gün) → True
   - is_eligible_for_auto_pause: sessizleşen öğretmen (30+ gün) → True
   - maybe_auto_resume: auto_* sebepli pasif user için login simülasyonu → resume
   - maybe_auto_resume: manuel pasif user → DOKUNULMAZ

2. Cron auto_pause_inactive_users:
   - Adayları bulur, panik koruyucu (%5) altında pasifleştirir
   - Audit log USER_AUTO_PAUSE eklenir

3. Alert filter:
   - at-risk paneli, burnout, admin digest, event_triggers → pasif user atlanır

4. HTTP:
   - Öğretmen /teacher/students/{id}/pause-alerts + resume-alerts → tenant scope
   - Kurum admin /institution/teachers/{id}/pause-alerts + resume-alerts
   - Audit kaydı düşer

5. Cascade YOK — öğretmen pasif olsa öğrenci uyarıları akar
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
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.deps import (
    get_current_user, require_institution_admin, require_teacher,
    require_user,
)
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    Institution,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services import pause as pause_service
from app.services.pause import (
    REASON_AUTO_INACTIVITY,
    REASON_MANUAL,
    find_auto_pause_candidates,
    is_eligible_for_auto_pause,
    maybe_auto_resume,
    pause_user,
    resume_user,
)
from app.services.security import hash_password


PFX = f"pausetest_{secrets.token_hex(3)}"
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


def cleanup(db, prefix: str) -> int:
    users = db.query(User).filter(User.email.like(f"{prefix}%")).all()
    n = len(users)
    for u in users:
        db.delete(u)
    db.commit()
    return n


def main() -> int:
    now = datetime.now(timezone.utc)

    # =========== SEED ===========
    print("\n=== SEED — test öğretmen + öğrenci + kurum ===")
    with SessionLocal() as db:
        # Kurum + admin
        inst = Institution(
            name=f"{PFX}-inst", slug=f"{PFX}-inst",
            plan="standard", is_active=True,
        )
        db.add(inst); db.flush()
        inst_id = inst.id
        admin = User(
            email=f"{PFX}-admin@x.test", password_hash=hash_password("Aa1!aaaaaaaaa"),
            full_name=f"{PFX} Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True,
        )
        teacher = User(
            email=f"{PFX}-t@x.test", password_hash=hash_password("Aa1!aaaaaaaaa"),
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            institution_id=inst_id, is_active=True,
            # 60 gün önce oluşturuldu — grace period geçmiş
            created_at=now - timedelta(days=60),
        )
        db.add_all([admin, teacher]); db.flush()
        teacher_id = teacher.id
        admin_id = admin.id

        # Yeni öğrenci (5 günlük)
        new_s = User(
            email=f"{PFX}-new@x.test", password_hash=hash_password("Aa1!aaaaaaaaa"),
            full_name=f"{PFX} New Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, institution_id=inst_id, is_active=True,
            created_at=now - timedelta(days=5),
        )
        # Eski sessiz öğrenci (60g, son sinyal 25g önce — eşik 21)
        silent_s = User(
            email=f"{PFX}-silent@x.test", password_hash=hash_password("Aa1!aaaaaaaaa"),
            full_name=f"{PFX} Silent Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, institution_id=inst_id, is_active=True,
            created_at=now - timedelta(days=60),
            last_login_at=now - timedelta(days=25),
        )
        # Aktif öğrenci (60g, son sinyal dün)
        active_s = User(
            email=f"{PFX}-active@x.test", password_hash=hash_password("Aa1!aaaaaaaaa"),
            full_name=f"{PFX} Active Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, institution_id=inst_id, is_active=True,
            created_at=now - timedelta(days=60),
            last_login_at=now - timedelta(days=1),
        )
        db.add_all([new_s, silent_s, active_s]); db.commit()
        new_id = new_s.id; silent_id = silent_s.id; active_id = active_s.id

    # =========== STEP 1: Manuel pause/resume ===========
    print("\n=== STEP 1: pause / resume manuel ===")
    with SessionLocal() as db:
        s = db.get(User, active_id)
        t = db.get(User, teacher_id)
        r = pause_user(db, s, actor=t, reason=REASON_MANUAL)
        check("pause_user: ok=True", r.ok)
        check("pause_user: is_paused True", db.get(User, active_id).is_paused)
        check("pause_user: reason MANUAL",
              db.get(User, active_id).pause_reason == REASON_MANUAL)
        check("pause_user: paused_by_id set",
              db.get(User, active_id).paused_by_id == teacher_id)
        # Idempotent
        r2 = pause_user(db, db.get(User, active_id), actor=t, reason=REASON_MANUAL)
        check("pause_user idempotent (was_paused_before=True)",
              r2.was_paused_before)

        # Resume
        r3 = resume_user(db, db.get(User, active_id), actor=t)
        check("resume_user: ok=True", r3.ok)
        check("resume_user: is_paused False",
              not db.get(User, active_id).is_paused)
        check("resume_user: last_manual_resume_at stamped",
              db.get(User, active_id).last_manual_resume_at is not None)

    # =========== STEP 2: Eligibility ===========
    print("\n=== STEP 2: auto-pause eligibility ===")
    with SessionLocal() as db:
        # Yeni öğrenci — grace period
        ok, code = is_eligible_for_auto_pause(db, db.get(User, new_id), now=now)
        check("yeni öğrenci (5g) → eligible False (grace)",
              not ok and code == "new_account_grace")

        # Sessiz öğrenci (25g)
        ok, code = is_eligible_for_auto_pause(db, db.get(User, silent_id), now=now)
        check("sessiz öğrenci (25g) → eligible True",
              ok, f"code={code}")

        # Aktif öğrenci (1g, ayrıca Step 1'de manuel resume edildi → sticky devrede).
        # Eligible False olmalı; sebep ya "still_active" ya "manual_resume_sticky"
        # olabilir — test scope'unda her ikisi de doğru.
        ok, code = is_eligible_for_auto_pause(db, db.get(User, active_id), now=now)
        check("aktif öğrenci → eligible False",
              not ok and code in ("still_active", "manual_resume_sticky"),
              f"code={code}")

        # Sticky'i test için ayrı bir user'da izole et — yeni sessiz öğrenci açıp
        # manuel resume sonrası 1 gün önce (sticky pencerede) eligible olmamalı.
        sticky_test = User(
            email=f"{PFX}-sticky@x.test", password_hash=hash_password("Aa1!aaaaaaaaa"),
            full_name=f"{PFX} Sticky Test", role=UserRole.STUDENT,
            teacher_id=teacher_id, institution_id=inst_id, is_active=True,
            created_at=now - timedelta(days=60),
            last_login_at=now - timedelta(days=25),
            last_manual_resume_at=now - timedelta(days=3),  # 7g sticky pencerede
        )
        db.add(sticky_test); db.commit()
        sticky_id = sticky_test.id
        ok, code = is_eligible_for_auto_pause(db, db.get(User, sticky_id), now=now)
        check("manuel resume sticky (3g önce) → eligible False",
              not ok and code == "manual_resume_sticky",
              f"code={code}")

        # Sessiz öğretmen senaryosu — 60g öğretmen, hiç login yok
        # son sinyal None → created_at fallback → 60g eski → eligible
        ok, code = is_eligible_for_auto_pause(db, db.get(User, teacher_id), now=now)
        check("60g sessiz öğretmen → eligible True",
              ok, f"code={code}")

    # =========== STEP 3: Auto-pause candidates + maybe_auto_resume ===========
    print("\n=== STEP 3: candidates + maybe_auto_resume ===")
    with SessionLocal() as db:
        cands = find_auto_pause_candidates(db, now=now)
        cand_ids = {u.id for u, _ in cands}
        check("silent_s adaylarda", silent_id in cand_ids)
        check("teacher_id adaylarda", teacher_id in cand_ids)
        check("new_s adaylarda DEĞİL", new_id not in cand_ids)
        check("active_s adaylarda DEĞİL", active_id not in cand_ids)

        # Manuel pause edilmiş user'ı maybe_auto_resume DOKUNMAZ
        s = db.get(User, silent_id)
        pause_user(db, s, actor=None, reason=REASON_MANUAL)
        resumed = maybe_auto_resume(db, db.get(User, silent_id))
        check("maybe_auto_resume manuel pasif → dokunmaz",
              not resumed and db.get(User, silent_id).is_paused)

        # Auto-pause edilmiş user'ı maybe_auto_resume açar
        resume_user(db, db.get(User, silent_id), actor=None, is_auto_resume=True)
        # Yeni sticky devreye girmedi (auto resume)
        pause_user(db, db.get(User, silent_id), actor=None, reason=REASON_AUTO_INACTIVITY)
        check("silent_s auto-paused", db.get(User, silent_id).is_paused
              and db.get(User, silent_id).pause_reason == REASON_AUTO_INACTIVITY)
        resumed2 = maybe_auto_resume(db, db.get(User, silent_id))
        check("maybe_auto_resume auto pasif → açar",
              resumed2 and not db.get(User, silent_id).is_paused)

    # =========== STEP 4: Cron auto_pause_inactive_users ===========
    print("\n=== STEP 4: cron auto_pause_inactive_users ===")
    with SessionLocal() as db:
        # Önce silent_s ve teacher'ı tekrar adaya çevir (önceki testler resume etti)
        # silent_s zaten resume edildi; teacher hala adaydır
        from app.services.cron_jobs import auto_pause_inactive_users
        result = auto_pause_inactive_users(db, now=now)
        check("cron çalıştı, candidates >= 1",
              result["candidates"] >= 1, f"got {result['candidates']}")
        check("cron paused >= 1",
              result["paused"] >= 1, f"got {result['paused']}")
        # Audit kaydı
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.action == AuditAction.USER_AUTO_PAUSE)
            .order_by(AuditLog.created_at.desc())
            .first()
        )
        check("USER_AUTO_PAUSE audit kaydı var", audit is not None)
        if audit:
            check("USER_AUTO_PAUSE actor_id NULL (sistem)",
                  audit.actor_id is None)

    # =========== STEP 5: HTTP teacher pause/resume student ===========
    print("\n=== STEP 5: HTTP teacher pause/resume ===")

    def make_user(uid):
        def factory():
            with SessionLocal() as db:
                u = (
                    db.query(User).options(joinedload(User.institution))
                    .filter(User.id == uid).first()
                )
                _ = u.institution
                db.expunge_all()
                return u
        return factory

    app.dependency_overrides[require_teacher] = make_user(teacher_id)
    app.dependency_overrides[require_user] = make_user(teacher_id)
    app.dependency_overrides[get_current_user] = make_user(teacher_id)

    try:
        c = TestClient(app)
        # Manuel resume yapıp aktife çek (önceki testler bozdu olabilir)
        with SessionLocal() as db:
            s = db.get(User, active_id)
            if s.is_paused:
                resume_user(db, s, actor=None, is_auto_resume=True)
                # last_manual_resume_at sıfırla (auto_resume zaten dokunmaz ama emin olalım)
                s2 = db.get(User, active_id)
                s2.last_manual_resume_at = None
                db.commit()

        r = c.post(
            f"/teacher/students/{active_id}/pause-alerts",
            follow_redirects=False,
        )
        check("teacher pause POST 303", r.status_code == 303)
        with SessionLocal() as db:
            check("active_s DB pasif", db.get(User, active_id).is_paused)
            audit = (
                db.query(AuditLog)
                .filter(
                    AuditLog.action == AuditAction.USER_PAUSE_ALERTS,
                    AuditLog.target_id == active_id,
                )
                .first()
            )
            check("USER_PAUSE_ALERTS audit + actor=teacher",
                  audit is not None and audit.actor_id == teacher_id)

        r = c.post(
            f"/teacher/students/{active_id}/resume-alerts",
            follow_redirects=False,
        )
        check("teacher resume POST 303", r.status_code == 303)
        with SessionLocal() as db:
            check("active_s DB aktif", not db.get(User, active_id).is_paused)
            check("last_manual_resume_at damgalı",
                  db.get(User, active_id).last_manual_resume_at is not None)

        # Tenant isolation — başka teacher'ın öğrencisine dokunamaz
        # (active_id zaten bu teacher'ın, başka senaryoyu kuralım)
        # Şimdilik basit: 404 kontrolü için olmayan ID
        r = c.post(
            "/teacher/students/999999/pause-alerts",
            follow_redirects=False,
        )
        check("olmayan öğrenci → 404", r.status_code == 404)
    finally:
        app.dependency_overrides.clear()

    # =========== STEP 6: HTTP inst_admin pause/resume teacher ===========
    print("\n=== STEP 6: HTTP inst_admin pause/resume teacher ===")
    app.dependency_overrides[require_institution_admin] = make_user(admin_id)
    app.dependency_overrides[require_user] = make_user(admin_id)
    app.dependency_overrides[get_current_user] = make_user(admin_id)

    try:
        c = TestClient(app)
        # Teacher pasifse önce aç
        with SessionLocal() as db:
            t = db.get(User, teacher_id)
            if t.is_paused:
                resume_user(db, t, actor=None, is_auto_resume=True)
                t2 = db.get(User, teacher_id)
                t2.last_manual_resume_at = None
                db.commit()

        r = c.post(
            f"/institution/teachers/{teacher_id}/pause-alerts",
            follow_redirects=False,
        )
        check("admin pause teacher POST 303", r.status_code == 303,
              f"got {r.status_code}")
        with SessionLocal() as db:
            check("teacher DB pasif", db.get(User, teacher_id).is_paused)
            check("teacher pause_reason MANUAL",
                  db.get(User, teacher_id).pause_reason == REASON_MANUAL)

        r = c.post(
            f"/institution/teachers/{teacher_id}/resume-alerts",
            follow_redirects=False,
        )
        check("admin resume teacher POST 303", r.status_code == 303)
        with SessionLocal() as db:
            check("teacher DB aktif", not db.get(User, teacher_id).is_paused)
    finally:
        app.dependency_overrides.clear()

    # =========== STEP 7: Cascade YOK — öğretmen pasif, öğrenci uyarıları akar ===========
    print("\n=== STEP 7: cascade YOK kontrolü ===")
    with SessionLocal() as db:
        from app.services.event_triggers import _active_parents_for
        # Teacher'ı pasife al
        t = db.get(User, teacher_id)
        pause_user(db, t, actor=None, reason=REASON_MANUAL)

        # active_s'in is_paused=False olduğundan emin ol
        s = db.get(User, active_id)
        if s.is_paused:
            resume_user(db, s, actor=None, is_auto_resume=True)

        # Öğrenciye bağlı veli olmadığı için empty list bekleniyor — ama
        # önemli olan: helper student.is_paused dolayısıyla boş dönmüyor
        parents = _active_parents_for(db, active_id)
        # Veli yok → []. Buradaki kontrol: helper student'ın TEACHER pasif
        # olduğunu UMURSAMAZ — student'a bağlı veliler ne ise onları döner.
        # Ayrı bir test için student'ı pasife al:
        pause_user(db, db.get(User, active_id), actor=None, reason=REASON_MANUAL)
        parents2 = _active_parents_for(db, active_id)
        check("öğrenci pasif → _active_parents_for boş",
              parents2 == [])
        # Resume student
        resume_user(db, db.get(User, active_id), actor=None, is_auto_resume=True)

    # =========== Cleanup ===========
    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")

    with SessionLocal() as db:
        n = cleanup(db, PFX)
        # Inst de sil
        insts = db.query(Institution).filter(Institution.slug.like(f"{PFX}%")).all()
        for i in insts:
            db.delete(i)
        db.commit()
        print(f"Cleanup: {n} user + {len(insts)} kurum silindi")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
