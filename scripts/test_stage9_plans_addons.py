"""Stage 9 (Faz 2) — Plans + Add-ons smoke test.

Senaryolar:
1. PLAN_CATALOG bütünlük: 9 plan (4 solo + 5 institution) + alanlar
2. is_solo_plan / is_institution_plan / is_paid_plan / is_trial_plan helper'ları
3. start_solo_trial: trial_ends_at=now+14d, post_trial_plan='solo_free'
4. start_institution_trial: trial_ends_at=now+30d, post_trial_plan='institution_free'
5. trial_days_left + is_trial_active
6. expire_trials cron — süresi dolmuş trial'ları post_trial_plan'a düşürür
7. PlanChangeHistory audit kayıtları doğru üretilir
8. change_plan: from_plan/to_plan + reason + autocommit
9. Add-on activate_addon: AI_PLUS → CreditAccount.bonus_credits +1000
10. Add-on activate_addon idempotent (aynı period için aynı kind tekrar açılmaz)
11. is_addon_active + addon_grants_feature_flag (WHATSAPP_PARENT)
12. cancel_addon: cancelled_at set, auto_renew=False, kayıt kalıyor
13. monthly_addon_renewal cron — auto_renew=True olanları yeni aya taşır,
    cancelled_at olan satırları yenilemez
14. /signup/teacher submit → otomatik 14g trial başlar
15. PlanChangeReason.SIGNUP audit
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.database import SessionLocal
from app.models import (
    ADDON_MONTHLY_PRICE_TRY,
    Addon,
    AddonKind,
    CreditAccount,
    Institution,
    PlanChangeHistory,
    PlanChangeReason,
    PlanOwnerType,
    User,
    UserRole,
    UsageOwnerType,
)
from app.services import addons as addon_svc
from app.services.addons import (
    activate_addon,
    addon_grants_feature_flag,
    cancel_addon,
    get_active_addons,
    is_addon_active,
    monthly_addon_renewal,
)
from app.services.credits import CreditOwner, get_or_create_account
from app.services.plans import (
    ALL_PLANS,
    DERSHANE_PRO,
    ENTERPRISE,
    ETUT_STANDART,
    INSTITUTION_FREE,
    INSTITUTION_PLANS,
    INSTITUTION_TRIAL,
    PLAN_CATALOG,
    SOLO_ELITE,
    SOLO_FREE,
    SOLO_PLANS,
    SOLO_PRO,
    SOLO_TRIAL,
    change_plan,
    expire_trials,
    is_institution_plan,
    is_paid_plan,
    is_solo_plan,
    is_trial_active,
    is_trial_plan,
    start_institution_trial,
    start_solo_trial,
    trial_days_left,
)


PFX = f"_s9_{secrets.token_hex(3)}"
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
        # Bağımsız öğretmen — solo plan için
        teacher = User(
            email=f"{PFX}_solo@test.invalid", password_hash="x" * 60,
            full_name="Solo Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan="free",
        )
        # Kurum + admin
        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            plan="free", is_active=True,
        )
        db.add_all([teacher, inst]); db.flush()
        teacher_id, inst_id = teacher.id, inst.id

        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash="x" * 60,
            full_name="Inst Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        db.add(admin); db.commit()
        admin_id = admin.id
        print(f"  teacher={teacher_id}, inst={inst_id}, admin={admin_id}")

    # ============ STEP 1: PLAN_CATALOG bütünlük ============
    print("\n=== STEP 1: PLAN_CATALOG ===")
    check("PLAN_CATALOG 9 plan", len(PLAN_CATALOG) == 9)
    check("4 solo plan", len(SOLO_PLANS) == 4)
    check("5 institution plan", len(INSTITUTION_PLANS) == 5)
    check("ALL_PLANS = 9", len(ALL_PLANS) == 9)
    check("solo_pro PlanInfo var", SOLO_PRO in PLAN_CATALOG)
    info = PLAN_CATALOG[SOLO_PRO]
    check("solo_pro fiyat = 299", info.price_monthly_try == 299)
    check("solo_pro yıllık = 2691 (9×299)", info.price_yearly_try == 2691)
    check("solo_pro badge 'En Popüler' içerir",
          info.badge is not None and "En Popüler" in info.badge)
    check("solo_pro features_included 5+", len(info.features_included) >= 5)
    check("enterprise fiyat = -1 (görüşme)",
          PLAN_CATALOG[ENTERPRISE].price_monthly_try == -1)

    # ============ STEP 2: helper'lar ============
    print("\n=== STEP 2: helper'lar ===")
    check("is_solo_plan(solo_pro) = True", is_solo_plan(SOLO_PRO))
    check("is_solo_plan(etut_standart) = False",
          not is_solo_plan(ETUT_STANDART))
    check("is_institution_plan(dershane_pro) = True",
          is_institution_plan(DERSHANE_PRO))
    check("is_paid_plan(solo_pro) = True", is_paid_plan(SOLO_PRO))
    check("is_paid_plan(solo_free) = False", not is_paid_plan(SOLO_FREE))
    check("is_paid_plan(solo_trial) = False (trial ücretsiz)",
          not is_paid_plan(SOLO_TRIAL))
    check("is_trial_plan(solo_trial)", is_trial_plan(SOLO_TRIAL))
    check("is_trial_plan(institution_trial)",
          is_trial_plan(INSTITUTION_TRIAL))
    check("is_trial_plan(solo_free) = False",
          not is_trial_plan(SOLO_FREE))

    # ============ STEP 3: start_solo_trial ============
    print("\n=== STEP 3: start_solo_trial ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        start_solo_trial(db, user=u)
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        check("trial sonrası plan = solo_trial", u.plan == SOLO_TRIAL)
        check("trial_ends_at None değil", u.trial_ends_at is not None)
        check("post_trial_plan = solo_free", u.post_trial_plan == SOLO_FREE)
        days = trial_days_left(owner=u)
        check("trial_days_left ≈ 14", 13 <= (days or 0) <= 14)
        check("is_trial_active = True", is_trial_active(u))

        # PlanChangeHistory kaydı
        history = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_type == PlanOwnerType.USER,
                PlanChangeHistory.owner_id == teacher_id,
            )
            .all()
        )
        check("plan_change_history 1 kayıt var", len(history) == 1)
        check("history.reason = SIGNUP",
              history[0].reason == PlanChangeReason.SIGNUP)
        check("history.to_plan = solo_trial",
              history[0].to_plan == SOLO_TRIAL)

    # ============ STEP 4: start_institution_trial ============
    print("\n=== STEP 4: start_institution_trial ===")
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        start_institution_trial(db, institution=i)
    with SessionLocal() as db:
        i = db.get(Institution, inst_id)
        check("inst plan = institution_trial",
              i.plan == INSTITUTION_TRIAL)
        check("inst trial_ends_at None değil", i.trial_ends_at is not None)
        check("inst post_trial_plan = institution_free",
              i.post_trial_plan == INSTITUTION_FREE)
        days = trial_days_left(owner=i)
        check("inst trial_days_left ≈ 30",
              29 <= (days or 0) <= 30)

    # ============ STEP 5: expire_trials (geçmişe çekerek) ============
    print("\n=== STEP 5: expire_trials ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        i = db.get(Institution, inst_id)
        # Trial'ı geçmiş zamana çek
        u.trial_ends_at = now - timedelta(days=1)
        i.trial_ends_at = now - timedelta(days=1)
        db.commit()

    with SessionLocal() as db:
        counts = expire_trials(db, now=now)
        check("expire_trials users_expired = 1",
              counts.get("users_expired") == 1)
        check("expire_trials institutions_expired = 1",
              counts.get("institutions_expired") == 1)

    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        i = db.get(Institution, inst_id)
        check("user plan trial sonrası = solo_free",
              u.plan == SOLO_FREE)
        check("user.trial_ends_at temizlendi", u.trial_ends_at is None)
        check("inst plan = institution_free",
              i.plan == INSTITUTION_FREE)
        # PlanChangeHistory: TRIAL_EXPIRED kaydı eklendi
        rows = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_id == teacher_id,
                PlanChangeHistory.reason == PlanChangeReason.TRIAL_EXPIRED,
            )
            .all()
        )
        check("user için TRIAL_EXPIRED kaydı var", len(rows) == 1)
        check("from_plan=solo_trial → to_plan=solo_free",
              rows[0].from_plan == SOLO_TRIAL and rows[0].to_plan == SOLO_FREE)

    # ============ STEP 6: change_plan (manuel upgrade) ============
    print("\n=== STEP 6: change_plan upgrade ===")
    with SessionLocal() as db:
        result = change_plan(
            db, owner_type=PlanOwnerType.USER, owner_id=teacher_id,
            new_plan=SOLO_PRO, reason=PlanChangeReason.UPGRADE,
            actor_user_id=teacher_id, note="kullanıcı ücretli plana geçti",
        )
        check("change_plan döndürdü User", result is not None)
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        check("user.plan = solo_pro", u.plan == SOLO_PRO)
        rows = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_id == teacher_id,
                PlanChangeHistory.reason == PlanChangeReason.UPGRADE,
            )
            .all()
        )
        check("UPGRADE history var", len(rows) == 1)
        check("from=solo_free, to=solo_pro",
              rows[0].from_plan == SOLO_FREE and rows[0].to_plan == SOLO_PRO)

    # ============ STEP 7: Add-on activate AI_PLUS → kredi bonusu ============
    print("\n=== STEP 7: activate_addon AI_PLUS ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        # Önce mevcut bonus ne — referans nokta
        co = CreditOwner.for_user(u)
        acc_before = get_or_create_account(db, owner=co)
        bonus_before = acc_before.bonus_credits
        db.commit()

    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        ad = activate_addon(
            db, owner=u, addon_kind=AddonKind.AI_PLUS,
            actor_user_id=teacher_id,
            note="smoke test — AI Plus",
        )
        check("activate_addon döndürdü Addon", ad.id is not None)
        check("Addon.addon_kind = AI_PLUS",
              ad.addon_kind == AddonKind.AI_PLUS)
        check("price_try = 149",
              ad.price_try == ADDON_MONTHLY_PRICE_TRY[AddonKind.AI_PLUS])
        check("auto_renew = True", ad.auto_renew is True)
        check("cancelled_at None", ad.cancelled_at is None)

    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        co = CreditOwner.for_user(u)
        acc_after = get_or_create_account(db, owner=co)
        check("AI Plus sonrası bonus_credits +1000",
              acc_after.bonus_credits == bonus_before + 1000,
              f"before={bonus_before} after={acc_after.bonus_credits}")

    # ============ STEP 8: activate_addon idempotent ============
    print("\n=== STEP 8: activate_addon idempotent ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        ad1_id = (
            db.query(Addon)
            .filter(
                Addon.owner_type == "user",
                Addon.owner_id == teacher_id,
                Addon.addon_kind == AddonKind.AI_PLUS,
            )
            .first()
            .id
        )
        ad2 = activate_addon(
            db, owner=u, addon_kind=AddonKind.AI_PLUS,
            note="ikinci kez — idempotent olmalı",
        )
        check("aynı period için aynı kind: aynı row döner",
              ad2.id == ad1_id)
        # Tek bir AI_PLUS satırı bu period için
        count = (
            db.query(Addon)
            .filter(
                Addon.owner_type == "user",
                Addon.owner_id == teacher_id,
                Addon.addon_kind == AddonKind.AI_PLUS,
            )
            .count()
        )
        check("AI_PLUS satır sayısı 1 (idempotent)", count == 1)

    # ============ STEP 9: is_addon_active + addon_grants_feature_flag ============
    print("\n=== STEP 9: is_addon_active + flag override ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        check("is_addon_active(AI_PLUS) = True",
              is_addon_active(db, owner=u, addon_kind=AddonKind.AI_PLUS))
        check("is_addon_active(WHATSAPP_PARENT) = False (yok)",
              not is_addon_active(
                  db, owner=u, addon_kind=AddonKind.WHATSAPP_PARENT,
              ))

        # WHATSAPP_PARENT add-on aktive et
        activate_addon(
            db, owner=u, addon_kind=AddonKind.WHATSAPP_PARENT,
            note="smoke — WhatsApp paketi",
        )

    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        check("WHATSAPP_PARENT şimdi aktif",
              is_addon_active(
                  db, owner=u, addon_kind=AddonKind.WHATSAPP_PARENT,
              ))
        check("addon_grants_feature_flag(parent_notifications_whatsapp)=True",
              addon_grants_feature_flag(
                  db, owner=u, flag_key="parent_notifications_whatsapp",
              ))
        check("addon_grants_feature_flag(unrelated_flag) = False",
              not addon_grants_feature_flag(
                  db, owner=u, flag_key="weekly_admin_digest",
              ))

        # get_active_addons şu an 2 add-on döndürmeli
        actives = get_active_addons(db, owner=u)
        check("get_active_addons = 2 (AI_PLUS + WHATSAPP)",
              len(actives) == 2)

    # ============ STEP 10: cancel_addon ============
    print("\n=== STEP 10: cancel_addon ===")
    with SessionLocal() as db:
        u = db.get(User, teacher_id)
        wa = (
            db.query(Addon)
            .filter(
                Addon.owner_type == "user",
                Addon.owner_id == teacher_id,
                Addon.addon_kind == AddonKind.WHATSAPP_PARENT,
            )
            .first()
        )
        wa_id = wa.id

    with SessionLocal() as db:
        result = cancel_addon(db, addon_id=wa_id, by_user_id=teacher_id)
        check("cancel_addon döndürdü Addon",
              result is not None and result.id == wa_id)

    with SessionLocal() as db:
        wa = db.get(Addon, wa_id)
        check("cancelled_at set", wa.cancelled_at is not None)
        check("auto_renew = False", wa.auto_renew is False)
        check("cancelled_by_user_id = teacher_id",
              wa.cancelled_by_user_id == teacher_id)
        # Önemli: period_end'e kadar hâlâ aktif sayılır
        u = db.get(User, teacher_id)
        check("iptal sonrası HÂLÂ aktif (period_end gelmedi)",
              is_addon_active(
                  db, owner=u, addon_kind=AddonKind.WHATSAPP_PARENT,
              ))

    # ============ STEP 11: monthly_addon_renewal ============
    print("\n=== STEP 11: monthly_addon_renewal ===")
    # Geçmiş aya çekip bir add-on uydur — renewal'ın yakaladığını doğrula
    with SessionLocal() as db:
        # Manuel: teacher için "geçen ayın" period_start/end'i ile bir AI_PLUS
        # oluştur — auto_renew=True, cancelled_at=None
        last_month = now - timedelta(days=35)
        ps = datetime(last_month.year, last_month.month, 1, tzinfo=timezone.utc)
        if ps.month == 12:
            pe = datetime(ps.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            pe = datetime(ps.year, ps.month + 1, 1, tzinfo=timezone.utc)

        old = Addon(
            owner_type="institution",
            owner_id=inst_id,
            addon_kind=AddonKind.AI_PLUS,
            period_start=ps,
            period_end=pe,
            auto_renew=True,
            price_try=149,
            note="smoke — geçen ay",
        )
        db.add(old)
        db.commit()

    with SessionLocal() as db:
        result = monthly_addon_renewal(db, now=now)
        check("renewed >= 1", result.get("renewed", 0) >= 1)
        check("credit_bonus_granted >= 1",
              result.get("credit_bonus_granted", 0) >= 1)

    with SessionLocal() as db:
        # Yeni dönem satırı oluştu mu?
        new_period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        new = (
            db.query(Addon)
            .filter(
                Addon.owner_type == "institution",
                Addon.owner_id == inst_id,
                Addon.addon_kind == AddonKind.AI_PLUS,
                Addon.period_start == new_period_start,
            )
            .first()
        )
        check("yeni dönem satırı var", new is not None)
        if new:
            check("yeni satırın auto_renew = True", new.auto_renew is True)
            check("note 'Otomatik yenileme' içerir",
                  new.note and "yenileme" in (new.note or "").lower())

        # Kuruma ait CreditAccount.bonus_credits arttı
        i = db.get(Institution, inst_id)
        co = CreditOwner.for_institution(i)
        acc = get_or_create_account(db, owner=co)
        check("kurum CreditAccount bonus_credits ≥ 1000",
              acc.bonus_credits >= 1000)

    # ============ STEP 12: monthly_addon_renewal idempotent ============
    print("\n=== STEP 12: monthly_addon_renewal idempotent ===")
    with SessionLocal() as db:
        result = monthly_addon_renewal(db, now=now)
        check("ikinci çalıştırma yenileme yapmaz",
              result.get("renewed", 0) == 0)
        check("skipped_already_renewed >= 1",
              result.get("skipped_already_renewed", 0) >= 1)

    # ============ STEP 13: cancelled add-on yenilenmez ============
    print("\n=== STEP 13: cancelled add-on yenilenmez ===")
    # Yeni bir test fixture: geçen ay dönemli WHATSAPP_PARENT, cancelled_at SET
    with SessionLocal() as db:
        last_month = now - timedelta(days=35)
        ps = datetime(last_month.year, last_month.month, 1, tzinfo=timezone.utc)
        if ps.month == 12:
            pe = datetime(ps.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            pe = datetime(ps.year, ps.month + 1, 1, tzinfo=timezone.utc)

        cancelled_old = Addon(
            owner_type="institution",
            owner_id=inst_id,
            addon_kind=AddonKind.WHATSAPP_PARENT,
            period_start=ps,
            period_end=pe,
            auto_renew=True,           # ama cancelled_at set
            cancelled_at=now - timedelta(days=20),
            cancelled_by_user_id=admin_id,
            price_try=99,
            note="smoke — iptal edilmiş geçen ay",
        )
        db.add(cancelled_old)
        db.commit()

    with SessionLocal() as db:
        result = monthly_addon_renewal(db, now=now)
        # cancelled_at varsa filtreden geçmez → renewed = 0
        check("cancelled_old yenilenmez (renewed=0)",
              result.get("renewed", 0) == 0)
        new_period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        new_wa = (
            db.query(Addon)
            .filter(
                Addon.owner_type == "institution",
                Addon.owner_id == inst_id,
                Addon.addon_kind == AddonKind.WHATSAPP_PARENT,
                Addon.period_start == new_period_start,
            )
            .first()
        )
        check("yeni dönem WHATSAPP satırı yok", new_wa is None)

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        db.execute(delete(Addon).where(Addon.owner_id.in_([teacher_id, inst_id])))
        db.execute(delete(PlanChangeHistory).where(
            PlanChangeHistory.owner_id.in_([teacher_id, inst_id])
        ))
        db.execute(delete(CreditAccount).where(CreditAccount.owner_id.in_([teacher_id, inst_id])))
        db.execute(delete(User).where(User.id.in_([teacher_id, admin_id])))
        db.execute(delete(Institution).where(Institution.id == inst_id))
        db.commit()
    print("  cleanup OK")

    # ============ Sonuç ============
    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
