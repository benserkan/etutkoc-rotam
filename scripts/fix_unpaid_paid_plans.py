"""2026-07-24 veri düzeltmesi — ödemesiz ücretli plana geçirilmiş kullanıcılar.

BUG: expire_trials, post_trial_plan ücretli tier ise deneme bitişinde kullanıcıyı
ÖDEME ALMADAN ücretli plana geçiriyordu (kod düzeltildi). Bu script hatadan
etkilenen kullanıcıları düzeltir.

Kapsam (BİLİNÇLİ DAR): yalnız plan geçmişinde TRIAL_EXPIRED ile ücretli plana
geçmiş + abonelik kaydı (subscription_status) OLMAYAN bağımsız koçlar. Diğer
"ödeme kayıtsız ücretli plan" hesapları (eski test/demo hesapları — örn. App
Store inceleme demosu) DOKUNULMAZ; veri bütünlüğü panelinde listelenir, karar
süper adminindir.

Kullanım:
  python -m scripts.fix_unpaid_paid_plans                # dry-run (yalnız listeler)
  python -m scripts.fix_unpaid_paid_plans --apply        # solo_free'ye düşür
  python -m scripts.fix_unpaid_paid_plans --activate 60 --cycle academic_year --apply
      # belirli kullanıcıyı MEŞRU manuel aktivasyonla ücretli bırak
      # (subscription_status=active + platform=manual + dönem sonu)

Düşürülen kullanıcının post_trial_plan'ı KORUNUR → /teacher/plan'da seçtiği
paket ön-seçili gelir, "Kartla Öde" ile aktive olur. E-posta GÖNDERİLMEZ
(kullanıcı kararı 2026-07-24 — standart 'deneme bitti' e-postası zaten gitmişti).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import PlanChangeHistory, PlanChangeReason, PlanOwnerType, User, UserRole

PAID_TIERS = ("solo_pro", "solo_elite", "solo_unlimited")


def find_affected(db) -> list[User]:
    """TRIAL_EXPIRED ile ücretli plana geçmiş + abonelik kayıtsız koçlar."""
    trial_expired_paid_ids = {
        r[0] for r in (
            db.query(PlanChangeHistory.owner_id)
            .filter(
                PlanChangeHistory.owner_type == PlanOwnerType.USER,
                PlanChangeHistory.reason == PlanChangeReason.TRIAL_EXPIRED,
                PlanChangeHistory.to_plan.in_(PAID_TIERS),
            )
            .all()
        )
    }
    if not trial_expired_paid_ids:
        return []
    return (
        db.query(User)
        .filter(
            User.id.in_(trial_expired_paid_ids),
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.plan.in_(PAID_TIERS),
            User.subscription_status.is_(None),
        )
        .order_by(User.id)
        .all()
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Değişiklikleri yaz (yoksa dry-run)")
    ap.add_argument("--activate", type=int, default=None,
                    help="Bu kullanıcı ID'sini düşürme — manuel aktivasyonla ücretli bırak")
    ap.add_argument("--cycle", choices=["monthly", "academic_year"], default="academic_year",
                    help="--activate için abonelik döngüsü")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        affected = find_affected(db)
        print(f"\n=== Ödemesiz ücretli plan düzeltmesi ({'APPLY' if args.apply else 'DRY-RUN'}) ===")
        if not affected:
            print("Etkilenen kullanıcı yok — temiz.")
        for u in affected:
            action = "MANUEL AKTİVASYON" if args.activate == u.id else "solo_free'ye düşür"
            print(f"  #{u.id} {u.email} plan={u.plan} post_trial={u.post_trial_plan} → {action}")

        if not args.apply:
            print("\n(dry-run — hiçbir şey yazılmadı; uygulamak için --apply)")
            return 0

        from app.services.plans import change_plan

        for u in affected:
            if args.activate == u.id:
                # Meşru manuel aktivasyon (admin activate-plan ile aynı alanlar)
                days = 365 if args.cycle == "academic_year" else 30
                u.subscription_status = "active"
                u.subscription_cycle = args.cycle
                u.subscription_period_end = now + timedelta(days=days)
                u.subscription_platform = "manual"
                db.commit()
                print(f"  ✓ #{u.id} manuel aktivasyon: {u.plan} · {args.cycle} · "
                      f"dönem sonu {u.subscription_period_end:%Y-%m-%d}")
                continue

            change_plan(
                db,
                owner_type=PlanOwnerType.USER,
                owner_id=u.id,
                new_plan="solo_free",
                reason=PlanChangeReason.DOWNGRADE,
                note=("Veri düzeltmesi 2026-07-24: deneme bitişi hatası ödeme "
                      "alınmadan ücretli plana geçirmişti — ücretsiz kata alındı; "
                      f"ödeme bekleyen paket: {u.post_trial_plan}"),
                autocommit=True,
            )
            db.refresh(u)
            print(f"  ✓ #{u.id} → {u.plan} (post_trial={u.post_trial_plan} korundu)")

        # Son durum raporu
        remaining = find_affected(db)
        print(f"\nKalan etkilenen: {len(remaining)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
