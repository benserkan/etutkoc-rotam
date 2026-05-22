"""Trial bildirimleri smoke (Faz 2 — son 3 gün hatırlatma + bitiş e-postası).

E-posta log-only (EMAIL_ENABLED kapalı) → gönderim sayımı = işlenen koç.
Senaryolar:
   1. send_trial_reminders → yalnız ≤3 gün kalan koç işlenir + DRAFT PLAN_UPGRADE teklifi
   2. tekrar çalıştır → 0 (dedup: açık teklif var)
   3. expire_trials → expired_user_ids dolu + notify_trial_expired gönderir
   4. trial_expire wrapper → reminders_sent + expired_emails alanları
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.offer import Offer, OfferKind, OfferStatus
from app.models.plan_history import PlanChangeHistory, PlanOwnerType
from app.services import trial_notifications as tn
from app.services import cron_jobs
from app.services.plans import expire_trials
from app.services.security import hash_password

PFX = f"trialnotif_{secrets.token_hex(3)}"
PWD = hash_password("TrialNotif!23")

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _coach(db, suffix, trial_ends_at):
    u = User(
        email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
        full_name=f"{PFX} {suffix}", role=UserRole.TEACHER, institution_id=None,
        is_active=True, plan="solo_trial", trial_ends_at=trial_ends_at,
        post_trial_plan="solo_free",
        password_changed_at=datetime.now(timezone.utc), must_change_password=False,
    )
    db.add(u)
    return u


def main() -> int:
    print(f"\n=== trial bildirimleri smoke — {PFX} ===\n")
    now = datetime.now(timezone.utc)
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            admin = User(
                email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN, is_active=True,
                password_changed_at=now, must_change_password=False,
            )
            db.add(admin)
            a = _coach(db, "a", now + timedelta(days=2))    # ≤3 gün → hatırlatılır
            b = _coach(db, "b", now + timedelta(days=10))   # uzak → hatırlatılmaz
            c = _coach(db, "c", now - timedelta(days=1))    # geçmiş → expire
            db.commit()
            ids = {"admin": admin.id, "a": a.id, "b": b.id, "c": c.id}

        # 1. reminders
        with SessionLocal() as db:
            n = tn.send_trial_reminders(db, now=now)
            offer_a = db.query(Offer).filter(
                Offer.user_id == ids["a"], Offer.kind == OfferKind.PLAN_UPGRADE,
                Offer.status == OfferStatus.DRAFT,
            ).first()
            offer_b = db.query(Offer).filter(Offer.user_id == ids["b"]).first()
            # NOT: send_trial_reminders DB-geneli çalışır; n, dev DB'deki diğer
            # uygun koçları da kapsar. İzolasyon-güvenli kontrol: A işlendi (teklif
            # var), B (uzak trial) işlenmedi.
            check("1. reminders: A'ya DRAFT teklif var, B (uzak) yok",
                  n >= 1 and offer_a is not None and offer_b is None, f"n={n}")

        # 2. dedup
        with SessionLocal() as db:
            n2 = tn.send_trial_reminders(db, now=now)
            check("2. tekrar → 0 (dedup, açık teklif var)", n2 == 0, f"n2={n2}")

        # 3. expire + notify
        with SessionLocal() as db:
            res = expire_trials(db, now=now)
            exp_ids = res.get("expired_user_ids", [])
            sent = tn.notify_trial_expired(db, user_ids=exp_ids)
            cobj = db.get(User, ids["c"])
            check("3. expire → C düştü (solo_free) + expired_user_ids + bitiş e-postası",
                  ids["c"] in exp_ids and cobj.plan == "solo_free" and sent >= 1,
                  f"exp_ids={exp_ids} c.plan={cobj.plan} sent={sent}")

        # 4. wrapper alanları (idempotent — C zaten düştü, A teklifi var)
        with SessionLocal() as db:
            res = cron_jobs.trial_expire(db, now=now)
            check("4. trial_expire wrapper → reminders_sent + expired_emails alanları",
                  "reminders_sent" in res and "expired_emails" in res, f"{res}")

    finally:
        with SessionLocal() as db:
            uids = list(ids.values())
            if uids:
                db.execute(sa_delete(Offer).where(Offer.user_id.in_(uids)))
                db.execute(sa_delete(PlanChangeHistory).where(
                    PlanChangeHistory.owner_id.in_(uids),
                    PlanChangeHistory.owner_type == PlanOwnerType.USER))
                db.execute(sa_delete(User).where(User.id.in_(uids)))
            # send_trial_reminders DB-geneli çalıştı; bu koşuda üretilmiş diğer
            # otomatik DRAFT teklifleri de temizle (sentetik başlık — dev güvenli).
            db.execute(sa_delete(Offer).where(
                Offer.kind == OfferKind.PLAN_UPGRADE,
                Offer.status == OfferStatus.DRAFT,
                Offer.title == "Pro'ya geçiş — deneme bitiyor",
            ))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
