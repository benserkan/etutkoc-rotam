"""change_plan → mevcut period CreditAccount senkronizasyonu regresyon.

Bağlam: 2026-05-26 ETUTKOC vakası. Kurum plan=free → etut_standart yapıldı
ama mevcut Mayıs periyodunun CreditAccount.allocated_credits=50 kaldı (eski).
Fix: change_plan içinde _refresh_current_period_allocation çağrısı.

Senaryolar (in-memory SQLite, izole):
  S1: Kurum upgrade (free → etut_standart) → allocated 50 → 10000, used korunur.
  S2: Solo koç upgrade (solo_trial → solo_pro) → 50 → 1500, used korunur.
  S3: Downgrade (etut_standart → institution_free) → 10000 → 200, used korunur
      (remaining negatife düşebilir — kabul).
  S4: Same plan (no-op) → allocated değişmez.
  S5: Mevcut period yok (CreditAccount henüz yaratılmamış) → atlanır, hata olmaz.

Çalıştırma: PYTHONPATH=. python scripts/simulate_change_plan_credit_sync.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa
from app.database import Base
from app.models import (
    CreditAccount, Institution, User, UserRole, UsageOwnerType,
)
from app.models.plan_history import PlanChangeReason, PlanOwnerType
from app.services.credits import current_period
from app.services.plans import change_plan


ENGINE = create_engine("sqlite:///:memory:")
Base.metadata.create_all(ENGINE)
Session = sessionmaker(bind=ENGINE)


def _setup_institution(db, *, slug: str, plan: str = "free") -> Institution:
    inst = Institution(name=f"Test-{slug}", slug=slug, plan=plan)
    db.add(inst); db.flush()
    return inst


def _setup_solo(db, *, email: str, plan: str = "solo_trial") -> User:
    u = User(
        email=email, password_hash="x", full_name="Solo Koç",
        role=UserRole.TEACHER, plan=plan, is_active=True,
    )
    db.add(u); db.flush()
    return u


def _make_account(db, *, owner_type: UsageOwnerType, owner_id: int,
                  plan_code: str, allocated: int, used: int = 0) -> CreditAccount:
    acc = CreditAccount(
        owner_type=owner_type, owner_id=owner_id,
        period_year_month=current_period(),
        plan_code=plan_code, allocated_credits=allocated,
        bonus_credits=0, used_credits=used,
    )
    db.add(acc); db.flush()
    return acc


def _assert(label, ok, expected, actual) -> int:
    if ok:
        print(f"  [OK]   {label}: {actual}")
        return 0
    print(f"  [FAIL] {label}: beklenen={expected}  gerçek={actual}")
    return 1


def s1_institution_upgrade() -> int:
    print("\n=== S1 — Kurum upgrade free → etut_standart ===")
    db = Session()
    inst = _setup_institution(db, slug="s1", plan="free")
    acc = _make_account(db, owner_type=UsageOwnerType.INSTITUTION,
                        owner_id=inst.id, plan_code="free",
                        allocated=50, used=56)
    db.commit()
    change_plan(db, owner_type=PlanOwnerType.INSTITUTION, owner_id=inst.id,
                new_plan="etut_standart", reason=PlanChangeReason.UPGRADE)
    db.refresh(acc); db.refresh(inst)
    fails = 0
    fails += _assert("inst.plan", inst.plan == "etut_standart", "etut_standart", inst.plan)
    fails += _assert("acc.plan_code", acc.plan_code == "etut_standart", "etut_standart", acc.plan_code)
    fails += _assert("acc.allocated", acc.allocated_credits == 10000, 10000, acc.allocated_credits)
    fails += _assert("acc.used (korundu)", acc.used_credits == 56, 56, acc.used_credits)
    fails += _assert("acc.remaining > 0", acc.remaining_credits > 0,
                     ">0", acc.remaining_credits)
    db.close()
    return fails


def s2_solo_upgrade() -> int:
    print("\n=== S2 — Solo koç upgrade solo_trial → solo_pro ===")
    db = Session()
    u = _setup_solo(db, email="s2@test.invalid", plan="solo_trial")
    u.trial_ends_at = datetime.now(timezone.utc)
    acc = _make_account(db, owner_type=UsageOwnerType.USER,
                        owner_id=u.id, plan_code="solo_trial",
                        allocated=50, used=30)
    db.commit()
    change_plan(db, owner_type=PlanOwnerType.USER, owner_id=u.id,
                new_plan="solo_pro", reason=PlanChangeReason.UPGRADE)
    db.refresh(acc); db.refresh(u)
    fails = 0
    fails += _assert("user.plan", u.plan == "solo_pro", "solo_pro", u.plan)
    fails += _assert("user.trial_ends_at = None", u.trial_ends_at is None, None, u.trial_ends_at)
    fails += _assert("acc.plan_code", acc.plan_code == "solo_pro", "solo_pro", acc.plan_code)
    fails += _assert("acc.allocated", acc.allocated_credits == 1500, 1500, acc.allocated_credits)
    db.close()
    return fails


def s3_downgrade() -> int:
    print("\n=== S3 — Downgrade etut_standart → institution_free ===")
    db = Session()
    inst = _setup_institution(db, slug="s3", plan="etut_standart")
    acc = _make_account(db, owner_type=UsageOwnerType.INSTITUTION,
                        owner_id=inst.id, plan_code="etut_standart",
                        allocated=10000, used=500)
    db.commit()
    change_plan(db, owner_type=PlanOwnerType.INSTITUTION, owner_id=inst.id,
                new_plan="institution_free", reason=PlanChangeReason.DOWNGRADE)
    db.refresh(acc); db.refresh(inst)
    fails = 0
    fails += _assert("inst.plan", inst.plan == "institution_free", "institution_free", inst.plan)
    fails += _assert("acc.plan_code", acc.plan_code == "institution_free", "institution_free", acc.plan_code)
    fails += _assert("acc.allocated", acc.allocated_credits == 200, 200, acc.allocated_credits)
    fails += _assert("acc.used (korundu)", acc.used_credits == 500, 500, acc.used_credits)
    fails += _assert("acc.remaining negatif (downgrade aşımı)",
                     acc.remaining_credits < 0, "<0", acc.remaining_credits)
    db.close()
    return fails


def s4_same_plan_noop() -> int:
    print("\n=== S4 — Same plan no-op ===")
    db = Session()
    inst = _setup_institution(db, slug="s4", plan="etut_standart")
    acc = _make_account(db, owner_type=UsageOwnerType.INSTITUTION,
                        owner_id=inst.id, plan_code="etut_standart",
                        allocated=10000, used=200)
    db.commit()
    change_plan(db, owner_type=PlanOwnerType.INSTITUTION, owner_id=inst.id,
                new_plan="etut_standart", reason=PlanChangeReason.UPGRADE)
    db.refresh(acc)
    fails = 0
    fails += _assert("acc.allocated değişmedi", acc.allocated_credits == 10000,
                     10000, acc.allocated_credits)
    db.close()
    return fails


def s5_no_current_account() -> int:
    print("\n=== S5 — Mevcut period CreditAccount yok ===")
    db = Session()
    inst = _setup_institution(db, slug="s5", plan="free")
    # Hiç CreditAccount yaratma
    db.commit()
    # Hata fırlatmamalı
    change_plan(db, owner_type=PlanOwnerType.INSTITUTION, owner_id=inst.id,
                new_plan="etut_standart", reason=PlanChangeReason.UPGRADE)
    db.refresh(inst)
    fails = 0
    fails += _assert("inst.plan güncellendi (CreditAccount olmadan)",
                     inst.plan == "etut_standart", "etut_standart", inst.plan)
    # CreditAccount hâlâ yok — get_or_create_account ileride yaratacak
    acc_exists = db.query(CreditAccount).filter(
        CreditAccount.owner_type == UsageOwnerType.INSTITUTION,
        CreditAccount.owner_id == inst.id,
    ).count()
    fails += _assert("CreditAccount yaratılmadı (var olan yok)", acc_exists == 0,
                     0, acc_exists)
    db.close()
    return fails


def main() -> int:
    failed = 0
    failed += s1_institution_upgrade()
    failed += s2_solo_upgrade()
    failed += s3_downgrade()
    failed += s4_same_plan_noop()
    failed += s5_no_current_account()
    print(f"\n{'=' * 50}")
    if failed == 0:
        print("✓ TÜM SENARYOLAR YEŞİL")
        return 0
    print(f"✗ {failed} SENARYO BAŞARISIZ")
    return 1


if __name__ == "__main__":
    sys.exit(main())
