"""Stage 6 — Kredi sistemi kapsamlı smoke test.

Senaryolar:
1. Service: get_or_create_account plan-based allocation
2. record_usage kredi düşer + UsageEvent yazılır
3. consume_credits context manager çalışır
4. %80 eşiği geçildiğinde warn_80_sent_at set + email tetiklenir (log_only)
5. Kurum: %100 aşımda hard-block kapalıysa çalışmaya devam (sadece bayrak)
6. Bağımsız öğretmen: %100 aşımda otomatik 5h cooldown set
7. Cooldown süresi dolunca otomatik unblock
8. monthly_refill cron — yeni period satırları idempotent oluşur
9. usage_breakdown_by_kind tip kırılımı doğru
10. daily_usage_series 30 gün serisi doğru
11. HTTP /institution/usage 200 + sayılar doğru
12. HTTP /admin/usage 200 + 2 tab + hard-block toggle
13. HTTP /admin/usage hard-block toggle endpoint
14. HTTP /admin/usage bonus credit endpoint
15. HTTP /teacher/usage (bağımsız) 200
16. HTTP /teacher/usage (kurumlu) → 303 redirect
17. Cross-tenant isolation: kurum admin başka kurumun datasını göremez
18. Cleanup
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
from app.deps import (
    get_current_user, require_institution_admin, require_super_admin,
    require_teacher, require_user,
)
from app.main import app
from app.models import (
    AuditLog,
    CreditAccount,
    Institution,
    UsageEvent,
    UsageKind,
    UsageOwnerType,
    User,
    UserRole,
)
from app.services.credits import (
    CreditBlocked,
    CreditOwner,
    INDEPENDENT_COOLDOWN_HOURS,
    KIND_CREDITS,
    PLAN_ALLOCATIONS,
    check_credit_available,
    consume_credits,
    current_period,
    daily_usage_series,
    get_or_create_account,
    monthly_refill,
    record_usage,
    threshold_just_crossed,
    usage_breakdown_by_kind,
)


PFX = f"_credits_{secrets.token_hex(3)}"

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
    period = current_period(now)

    print("\n=== SEED ===")
    with SessionLocal() as db:
        # 2 kurum (free + starter)
        inst_free = Institution(
            name=f"{PFX}_free", slug=f"{PFX}-free",
            plan="free", is_active=True,
        )
        inst_starter = Institution(
            name=f"{PFX}_starter", slug=f"{PFX}-starter",
            plan="starter", is_active=True,
        )
        db.add_all([inst_free, inst_starter]); db.flush()
        free_id, starter_id = inst_free.id, inst_starter.id

        # ALPHA admin + öğretmen + öğrenci
        free_admin = User(
            email=f"{PFX}_free_admin@test.invalid", password_hash="x" * 60,
            full_name="Free Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=free_id, is_active=True, password_changed_at=now,
        )
        free_teacher = User(
            email=f"{PFX}_free_t@test.invalid", password_hash="x" * 60,
            full_name="Free Teacher", role=UserRole.TEACHER,
            institution_id=free_id, is_active=True, password_changed_at=now,
        )
        starter_admin = User(
            email=f"{PFX}_starter_admin@test.invalid", password_hash="x" * 60,
            full_name="Starter Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=starter_id, is_active=True, password_changed_at=now,
        )
        # Bağımsız öğretmen (institution_id=NULL)
        indep_teacher = User(
            email=f"{PFX}_indep@test.invalid", password_hash="x" * 60,
            full_name="Indep Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan="free",
        )
        db.add_all([free_admin, free_teacher, starter_admin, indep_teacher]); db.flush()
        free_admin_id = free_admin.id
        free_teacher_id = free_teacher.id
        starter_admin_id = starter_admin.id
        indep_id = indep_teacher.id
        db.commit()
        print(f"  free_inst={free_id}, starter_inst={starter_id}, indep_user={indep_id}")

    # ============ STEP 1: get_or_create_account allocation ============
    print("\n=== STEP 1: get_or_create_account ===")
    with SessionLocal() as db:
        free_obj = db.get(Institution, free_id)
        starter_obj = db.get(Institution, starter_id)
        indep_obj = db.get(User, indep_id)

        free_owner = CreditOwner.for_institution(free_obj)
        starter_owner = CreditOwner.for_institution(starter_obj)
        indep_owner = CreditOwner.for_user(indep_obj)

        free_acc = get_or_create_account(db, owner=free_owner)
        starter_acc = get_or_create_account(db, owner=starter_owner)
        indep_acc = get_or_create_account(db, owner=indep_owner)
        db.commit()

        check("free kurum allocation = 50",
              free_acc.allocated_credits == 50, f"got {free_acc.allocated_credits}")
        check("starter kurum allocation = 500",
              starter_acc.allocated_credits == 500, f"got {starter_acc.allocated_credits}")
        check("indep teacher allocation = 50 (free plan)",
              indep_acc.allocated_credits == 50, f"got {indep_acc.allocated_credits}")
        check("plan_code snapshot doğru",
              free_acc.plan_code == "free" and starter_acc.plan_code == "starter")

        # 2. çağrı aynı satırı dönmeli
        free_acc2 = get_or_create_account(db, owner=free_owner)
        check("get_or_create idempotent (aynı id)",
              free_acc2.id == free_acc.id, f"got {free_acc2.id} vs {free_acc.id}")

    # ============ STEP 2: record_usage düşürür ============
    print("\n=== STEP 2: record_usage ===")
    with SessionLocal() as db:
        starter_obj = db.get(Institution, starter_id)
        owner = CreditOwner.for_institution(starter_obj)
        evt = record_usage(
            db, owner=owner, kind=UsageKind.AI_BOOK_TEMPLATE,
            actor_user_id=starter_admin_id,
            metadata={"test": True},
        )
        check("event yazıldı", evt.id is not None)
        check("event credits = 5 (AI_BOOK_TEMPLATE)",
              evt.credits == 5, f"got {evt.credits}")
        # Re-fetch account
        acc = get_or_create_account(db, owner=owner)
        check("used_credits artmış",
              acc.used_credits == 5, f"got {acc.used_credits}")
        check("remaining_credits = 495",
              acc.remaining_credits == 495, f"got {acc.remaining_credits}")

    # ============ STEP 3: consume_credits context manager ============
    print("\n=== STEP 3: consume_credits context manager ===")
    with SessionLocal() as db:
        starter_obj = db.get(Institution, starter_id)
        owner = CreditOwner.for_institution(starter_obj)
        with consume_credits(db, owner=owner, kind=UsageKind.EMAIL_SEND) as ctx:
            ctx.set_metadata({"to": "test@example.com"})
        # Yeni event olmalı (toplam 2 event)
        evt_count = db.query(UsageEvent).filter(
            UsageEvent.owner_type == UsageOwnerType.INSTITUTION,
            UsageEvent.owner_id == starter_id,
        ).count()
        check("2 event toplam", evt_count == 2, f"got {evt_count}")

        # Hata fırlarsa kredi düşmemeli
        before_used = get_or_create_account(db, owner=owner).used_credits
        try:
            with consume_credits(db, owner=owner, kind=UsageKind.AI_INSIGHTS):
                raise RuntimeError("simulated error mid-call")
        except RuntimeError:
            pass
        # Yeni session'la oku (cache'siz)
    with SessionLocal() as db:
        starter_obj = db.get(Institution, starter_id)
        owner = CreditOwner.for_institution(starter_obj)
        after_used = get_or_create_account(db, owner=owner).used_credits
        check("hata durumunda kredi düşmedi (rollback semantiği)",
              after_used == before_used, f"before={before_used} after={after_used}")

    # ============ STEP 4: %80 eşik uyarısı ============
    print("\n=== STEP 4: %80 warn ===")
    with SessionLocal() as db:
        free_obj = db.get(Institution, free_id)
        owner = CreditOwner.for_institution(free_obj)
        # Free 50 kredi; 40 = %80
        # Birden fazla AI çağrısı (her biri 5 kredi) → 8 çağrı = 40 kredi = %80
        for i in range(8):
            record_usage(
                db, owner=owner, kind=UsageKind.AI_BOOK_TEMPLATE,
                actor_user_id=free_admin_id,
            )
        acc = get_or_create_account(db, owner=owner)
        check("free kurum %80 ulaştı", acc.usage_pct == 80, f"got %{acc.usage_pct}")
        check("warn_80_sent_at set edildi",
              acc.warn_80_sent_at is not None, f"got {acc.warn_80_sent_at}")
        # 9. çağrıda warn 2. kez gönderilmemeli
        first_warn_time = acc.warn_80_sent_at
        record_usage(db, owner=owner, kind=UsageKind.EMAIL_SEND, actor_user_id=free_admin_id)
        acc2 = get_or_create_account(db, owner=owner)
        check("warn 2. kez gönderilmedi (idempotent)",
              acc2.warn_80_sent_at == first_warn_time)

    # ============ STEP 5: kurum %100 aşımda hard-block kapalıyken devam ============
    print("\n=== STEP 5: kurum %100 aşım — soft (hard-block kapalı) ===")
    with SessionLocal() as db:
        free_obj = db.get(Institution, free_id)
        owner = CreditOwner.for_institution(free_obj)
        # Kalan ~9; bunu da bitir
        acc = get_or_create_account(db, owner=owner)
        remaining = acc.remaining_credits
        # Push past 100%
        while acc.used_credits < acc.total_allocated:
            record_usage(db, owner=owner, kind=UsageKind.EMAIL_SEND, actor_user_id=free_admin_id)
            acc = get_or_create_account(db, owner=owner)

        check("free kurum 100% ulaştı",
              acc.usage_pct >= 100, f"got %{acc.usage_pct}")
        check("hard_block_enabled=False (manuel)", not acc.hard_block_enabled)
        # check_credit_available ok=True kalmalı (kurum, hard_block kapalı)
        chk = check_credit_available(db, owner=owner, kind=UsageKind.EMAIL_SEND)
        check("kurum %100 aşımda hala ok=True (yumuşak)", chk.ok,
              f"got reason={chk.reason}")

    # ============ STEP 6: bağımsız öğretmen %100 cooldown ============
    print("\n=== STEP 6: bağımsız öğretmen %100 cooldown ===")
    with SessionLocal() as db:
        indep_obj = db.get(User, indep_id)
        owner = CreditOwner.for_user(indep_obj)
        # 50 kredi tüket
        for _ in range(10):
            record_usage(db, owner=owner, kind=UsageKind.AI_BOOK_TEMPLATE,
                         actor_user_id=indep_id)
        acc = get_or_create_account(db, owner=owner)
        check("indep %100 ulaştı", acc.usage_pct >= 100, f"got %{acc.usage_pct}")
        check("blocked_until set edildi",
              acc.blocked_until is not None, f"got {acc.blocked_until}")
        # Yaklaşık 5 saat sonra
        if acc.blocked_until:
            bu = acc.blocked_until
            if bu.tzinfo is None:
                bu = bu.replace(tzinfo=timezone.utc)
            delta_h = (bu - now).total_seconds() / 3600
            check("blocked_until ~5 saat sonra",
                  4.5 <= delta_h <= 5.5, f"got delta={delta_h:.2f}h")

        # check_credit_available reddetmeli
        chk = check_credit_available(db, owner=owner, kind=UsageKind.AI_INSIGHTS)
        check("indep cooldown'da çağrı reddedilir",
              not chk.ok and chk.reason == "cooldown",
              f"ok={chk.ok} reason={chk.reason}")

        # consume_credits CreditBlocked fırlatmalı
        try:
            with consume_credits(db, owner=owner, kind=UsageKind.AI_INSIGHTS):
                pass
            check("CreditBlocked fırlatıldı", False, "exception yok")
        except CreditBlocked as e:
            check("CreditBlocked fırlatıldı", True)
            check("reason=cooldown", e.reason == "cooldown")

    # ============ STEP 7: cooldown süresi dolunca otomatik unblock ============
    print("\n=== STEP 7: cooldown auto-unblock ===")
    with SessionLocal() as db:
        indep_obj = db.get(User, indep_id)
        owner = CreditOwner.for_user(indep_obj)
        acc = get_or_create_account(db, owner=owner)
        # Manuel olarak blocked_until'ı geçmişe çek
        acc.blocked_until = now - timedelta(minutes=1)
        db.commit()

        chk = check_credit_available(db, owner=owner, kind=UsageKind.EMAIL_SEND, now=now)
        # Kredi hâlâ bitmiş, yani auto re-block ile yine cooldown set edilmeli
        # Bu davranış: süre dolduğunda check fonksiyonu blocked_until'ı temizler;
        # ardından kredi yetersizse YENİ cooldown set eder.
        # Yeni cooldown başladığı için ok=False ve cooldown reason
        check("cooldown süresi dolunca: kredi hala bitmiş ise yeni cooldown",
              not chk.ok and chk.reason == "cooldown",
              f"ok={chk.ok} reason={chk.reason}")

        # Bonus ekle, cooldown bitir
        acc = get_or_create_account(db, owner=owner)
        acc.bonus_credits = 100
        acc.blocked_until = None
        db.commit()
        chk = check_credit_available(db, owner=owner, kind=UsageKind.EMAIL_SEND)
        check("bonus eklendikten sonra ok=True",
              chk.ok and chk.remaining > 0,
              f"ok={chk.ok} remaining={chk.remaining}")

    # ============ STEP 8: monthly_refill ============
    print("\n=== STEP 8: monthly_refill cron ===")
    with SessionLocal() as db:
        result = monthly_refill(db, now=now)
        check("monthly_refill dict döndürdü",
              isinstance(result, dict) and "period" in result)
        check("aynı period'da yeni satır oluşmaz (skipped)",
              result["skipped"] >= 3,  # en az 3 sahibimiz vardı
              f"got skipped={result['skipped']}")

    # ============ STEP 9: usage_breakdown_by_kind ============
    print("\n=== STEP 9: usage_breakdown ===")
    with SessionLocal() as db:
        free_obj = db.get(Institution, free_id)
        owner = CreditOwner.for_institution(free_obj)
        bd = usage_breakdown_by_kind(db, owner=owner, period=period)
        check("breakdown dict",
              isinstance(bd, dict) and len(bd) >= 1)
        check("AI_BOOK_TEMPLATE breakdown'da var",
              UsageKind.AI_BOOK_TEMPLATE.value in bd,
              f"keys: {list(bd.keys())}")

    # ============ STEP 10: daily_usage_series ============
    print("\n=== STEP 10: daily_usage_series ===")
    with SessionLocal() as db:
        starter_obj = db.get(Institution, starter_id)
        owner = CreditOwner.for_institution(starter_obj)
        series = daily_usage_series(db, owner=owner, days=30, today=today)
        check("series 30 günlük",
              len(series) == 30, f"got {len(series)}")
        # Bugün kullanım vardı
        today_total = next((c for d, c in series if d == today), 0)
        check("bugün için kullanım var",
              today_total > 0, f"got {today_total}")

    # ============ STEP 11-16: HTTP routes ============
    print("\n=== STEP 11: HTTP /institution/usage ===")

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
                # institution'u eagerly yükle ki template lazy-load patlamasın
                _ = u.institution
                db2.expunge_all()
                return u
            finally:
                db2.close()
        return factory

    # Free admin
    app.dependency_overrides[require_institution_admin] = _override(free_admin_id)
    app.dependency_overrides[require_user] = _override(free_admin_id)
    app.dependency_overrides[get_current_user] = _override(free_admin_id)

    try:
        c = TestClient(app)
        r = c.get("/institution/usage")
        check("GET /institution/usage 200", r.status_code == 200, f"got {r.status_code}")
        body = r.text
        check("'Aylık Kredi Kullanımın' başlığı", "Aylık Kredi Kullanımın" in body)
        check("Free kurum adı görünüyor", f"{PFX}_free" in body)
        check("Plan 'free' yazıyor", "free" in body)

        # Aşım oldu — %100 banner görünmeli
        check("'Aylık kredin tükendi' uyarısı (free %100+)",
              "kredin tükendi" in body or "tükendi" in body)
    finally:
        app.dependency_overrides.clear()

    print("\n=== STEP 12-14: HTTP /admin/usage ===")
    with SessionLocal() as db:
        sa = db.query(User).filter(
            User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True),
        ).first()
        check("Süper admin var", sa is not None)
        sa_id = sa.id

    app.dependency_overrides[require_super_admin] = _override(sa_id)
    app.dependency_overrides[require_user] = _override(sa_id)
    app.dependency_overrides[get_current_user] = _override(sa_id)

    try:
        c = TestClient(app)
        r = c.get("/admin/usage")
        check("GET /admin/usage 200", r.status_code == 200, f"got {r.status_code}")
        body = r.text
        check("'Kredi Kullanımı' başlığı", "Kredi Kullanımı" in body)
        check("Kurumlar tab", "Kurumlar (" in body)
        check("Bağımsız Öğretmenler tab", "Bağımsız Öğretmenler (" in body)
        check("Free kurum tabloda", f"{PFX}_free" in body)

        # tab=independents
        r = c.get("/admin/usage?tab=independents")
        check("GET tab=independents 200", r.status_code == 200)
        body = r.text
        check("Indep teacher tabloda", f"{PFX}_indep" in body)

        # Hard-block toggle (free kurum)
        r = c.post(f"/admin/usage/institution/{free_id}/hard-block",
                   follow_redirects=False)
        check("hard-block POST 303", r.status_code == 303, f"got {r.status_code}")
        with SessionLocal() as db:
            free_obj = db.get(Institution, free_id)
            owner = CreditOwner.for_institution(free_obj)
            acc = get_or_create_account(db, owner=owner)
            check("hard_block_enabled=True", acc.hard_block_enabled)

        # Tekrar toggle → kapansın
        c.post(f"/admin/usage/institution/{free_id}/hard-block",
               follow_redirects=False)
        with SessionLocal() as db:
            free_obj = db.get(Institution, free_id)
            owner = CreditOwner.for_institution(free_obj)
            acc = get_or_create_account(db, owner=owner)
            check("hard_block_enabled=False (toggle off)", not acc.hard_block_enabled)

        # Bonus credit
        r = c.post(f"/admin/usage/institution/{starter_id}/bonus",
                   data={"bonus_amount": 100}, follow_redirects=False)
        check("bonus POST 303", r.status_code == 303, f"got {r.status_code}")
        with SessionLocal() as db:
            starter_obj = db.get(Institution, starter_id)
            owner = CreditOwner.for_institution(starter_obj)
            acc = get_or_create_account(db, owner=owner)
            check("bonus_credits=100", acc.bonus_credits == 100,
                  f"got {acc.bonus_credits}")
    finally:
        app.dependency_overrides.clear()

    print("\n=== STEP 15-16: HTTP /teacher/usage ===")
    # Bağımsız öğretmen — kendi sayfası
    app.dependency_overrides[require_teacher] = _override(indep_id)
    app.dependency_overrides[require_user] = _override(indep_id)
    app.dependency_overrides[get_current_user] = _override(indep_id)

    try:
        c = TestClient(app)
        r = c.get("/teacher/usage", follow_redirects=False)
        check("GET /teacher/usage (bağımsız) 200",
              r.status_code == 200, f"got {r.status_code}")
        body = r.text
        check("Indep teacher kullanım başlığı",
              "Aylık Kredi Kullanımım" in body or "Kullanım & Kredilerim" in body)
    finally:
        app.dependency_overrides.clear()

    # Kurumlu öğretmen — redirect
    app.dependency_overrides[require_teacher] = _override(free_teacher_id)
    app.dependency_overrides[require_user] = _override(free_teacher_id)
    app.dependency_overrides[get_current_user] = _override(free_teacher_id)
    try:
        c = TestClient(app)
        r = c.get("/teacher/usage", follow_redirects=False)
        check("GET /teacher/usage (kurumlu) 303",
              r.status_code == 303, f"got {r.status_code}")
    finally:
        app.dependency_overrides.clear()

    # ============ STEP 17: cross-tenant isolation ============
    print("\n=== STEP 17: cross-tenant isolation ===")
    # Free admin starter kurumun veriler ini görememeli
    app.dependency_overrides[require_institution_admin] = _override(free_admin_id)
    app.dependency_overrides[require_user] = _override(free_admin_id)
    app.dependency_overrides[get_current_user] = _override(free_admin_id)
    try:
        c = TestClient(app)
        r = c.get("/institution/usage")
        body = r.text
        check("free admin starter veriyi GÖREMEZ",
              f"{PFX}_starter" not in body)
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
            db.query(UsageEvent).filter(
                UsageEvent.actor_user_id.in_(all_uids)
            ).delete(synchronize_session=False)
            db.query(UsageEvent).filter(
                UsageEvent.owner_type == UsageOwnerType.USER,
                UsageEvent.owner_id.in_(all_uids),
            ).delete(synchronize_session=False)
            db.query(CreditAccount).filter(
                CreditAccount.owner_type == UsageOwnerType.USER,
                CreditAccount.owner_id.in_(all_uids),
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(all_uids)).delete(
                synchronize_session=False
            )
        # Kurumlara ait usage + credit
        db.query(UsageEvent).filter(
            UsageEvent.owner_type == UsageOwnerType.INSTITUTION,
            UsageEvent.owner_id.in_([free_id, starter_id]),
        ).delete(synchronize_session=False)
        db.query(CreditAccount).filter(
            CreditAccount.owner_type == UsageOwnerType.INSTITUTION,
            CreditAccount.owner_id.in_([free_id, starter_id]),
        ).delete(synchronize_session=False)
        # Kurum-bağlı audit logs (target_type='credit_account' vs.)
        db.query(AuditLog).filter(
            AuditLog.target_type == "credit_account",
        ).delete(synchronize_session=False)
        db.query(Institution).filter(
            Institution.id.in_([free_id, starter_id])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verisi temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 6 credits testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
