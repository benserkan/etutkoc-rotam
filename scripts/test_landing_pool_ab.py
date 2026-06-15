"""#3 Kart-havuzu A/B (kesfet vs tema) smoke.

Varyanta `pool` (slug öneki) eklenince landing kart havuzunu o önekteki kartlarla
sınırlar. Deterministik hash ataması ile ctrl/test oturumları ayrı havuz görür.
Boş/eksik havuz → graceful fallback (tüm havuz).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import ExperimentStatus, FeatureCard, FeatureExperiment
from app.services import feature_catalog as fc

# slugify underscore→hyphen çevirdiği için PFX'te underscore YOK (slug eşleşsin).
PFX = f"poolab{secrets.token_hex(3)}"
KESFET = [f"kesfet-{PFX}-1", f"kesfet-{PFX}-2"]
TEMA = [f"tema-{PFX}-1", f"tema-{PFX}-2"]
ALL_SLUGS = KESFET + TEMA
EXP_SLUG = f"{PFX}-exp"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def _cleanup():
    with SessionLocal() as db:
        db.execute(sa_delete(FeatureExperiment).where(FeatureExperiment.slug == EXP_SLUG))
        db.execute(sa_delete(FeatureCard).where(FeatureCard.slug.in_(ALL_SLUGS)))
        db.commit()


def _mk_cards(db):
    for s in ALL_SLUGS:
        fc.create(
            db, actor_id=None, slug=s, title=s, domain="lgs",
            status="published", mockup_type="generic",
            target_roles=["teacher"],
        )
    db.commit()


def _mk_experiment(db, *, ctrl_pool, test_pool, running=True):
    now = datetime.now(timezone.utc)
    e = FeatureExperiment(
        slug=EXP_SLUG, name=f"{PFX} exp",
        status=ExperimentStatus.RUNNING.value if running else ExperimentStatus.DRAFT.value,
        created_at=now, updated_at=now,
    )
    ctrl = {"slug": "ctrl", "label": "Kontrol", "strategy": "hybrid_full",
            "weight": 50, "is_control": True}
    test = {"slug": "test", "label": "Test", "strategy": "hybrid_full",
            "weight": 50, "is_control": False}
    if ctrl_pool:
        ctrl["pool"] = ctrl_pool
    if test_pool:
        test["pool"] = test_pool
    e.variants = [ctrl, test]
    db.add(e)
    db.commit()
    return e


def _slugs_for_session(db, session_id):
    cards, variant = fc.get_for_landing_with_variant(
        db, limit=10, viewer=None, session_id=session_id, audience="teacher",
    )
    return {c.slug for c in cards}, variant


def main() -> int:
    print(f"\n=== landing pool A/B smoke — {PFX} ===\n")
    _cleanup()
    try:
        with SessionLocal() as db:
            _mk_cards(db)
            _mk_experiment(db, ctrl_pool="kesfet", test_pool="tema")

            # Deterministik atama → ctrl ve test'e düşen birer session bul.
            ctrl_sess = test_sess = None
            for i in range(200):
                sid = f"{PFX}-s{i}"
                from app.services import experiments as exp
                e = exp.get_active_experiment(db)
                vslug, _ = exp.assign_variant(e, sid)
                if vslug == "ctrl" and ctrl_sess is None:
                    ctrl_sess = sid
                elif vslug == "test" and test_sess is None:
                    test_sess = sid
                if ctrl_sess and test_sess:
                    break
            check("1. ctrl + test oturumu bulundu", ctrl_sess and test_sess,
                  f"ctrl={ctrl_sess} test={test_sess}")

            # NOT: dev DB'de gerçek kesfet-* seed kartları var → sağlam invariant:
            # her dönen kart ilgili öneke ait + karşı havuzdan HİÇ kart yok.
            cs, cv = _slugs_for_session(db, ctrl_sess)
            check("2. ctrl (pool=kesfet) → dönen her kart 'kesfet-' önekli + boş değil",
                  cs and all(s.startswith("kesfet-") for s in cs), f"variant={cv} slugs={cs}")
            check("3. ctrl'de hiç tema kartı yok",
                  not any(s.startswith("tema-") for s in cs), f"slugs={cs}")

            ts, tv = _slugs_for_session(db, test_sess)
            check("4. test (pool=tema) → benim tema kartlarım görünür + hepsi 'tema-' önekli",
                  set(TEMA).issubset(ts) and all(s.startswith("tema-") for s in ts),
                  f"variant={tv} slugs={ts}")
            check("5. test'te hiç kesfet kartı yok",
                  not any(s.startswith("kesfet-") for s in ts), f"slugs={ts}")

            # --- Boş havuz → fallback: var-olmayan önek → tüm kartlar ---
            db.execute(sa_delete(FeatureExperiment).where(FeatureExperiment.slug == EXP_SLUG))
            db.commit()
            _mk_experiment(db, ctrl_pool="", test_pool="yokboyle")
            # test'e düşen oturum: var-olmayan havuz → tüm kartlar (graceful)
            from app.services import experiments as exp
            e = exp.get_active_experiment(db)
            tsess = None
            for i in range(200):
                sid = f"{PFX}-fb{i}"
                if exp.assign_variant(e, sid)[0] == "test":
                    tsess = sid
                    break
            fbs, _ = _slugs_for_session(db, tsess)
            check("6. var-olmayan havuz → fallback (her iki önek de görünür, boş kalmaz)",
                  any(s.startswith("kesfet-") for s in fbs)
                  and any(s.startswith("tema-") for s in fbs), f"slugs={fbs}")

            # --- Havuzsuz ctrl → tüm kartlar (klasik strateji A/B) ---
            csess = None
            for i in range(200):
                sid = f"{PFX}-c2{i}"
                if exp.assign_variant(e, sid)[0] == "ctrl":
                    csess = sid
                    break
            cfs, _ = _slugs_for_session(db, csess)
            check("7. havuzsuz ctrl → havuz filtresi yok (her iki önek de görünür)",
                  any(s.startswith("kesfet-") for s in cfs)
                  and any(s.startswith("tema-") for s in cfs), f"slugs={cfs}")

            # --- pool helper'ları ---
            check("8. pool_published_count(kesfet) >= 2",
                  fc.pool_published_count(db, "kesfet") >= 2)
            check("9. pool_label('tema') AI temalı",
                  "tema" in (fc.pool_label("tema") or ""))
    finally:
        _cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
