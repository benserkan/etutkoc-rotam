"""Katman 4 — Discovery Onay Kuyruğu smoke test.

Senaryolar:
  1) Hazırlık: fixture olarak 3 keşif kartı + 1 manuel DRAFT oluştur
  2) GET /admin/feature-catalog/discovery-queue → 200, sadece kesif-* görünür
  3) Kaynak filtresi: ?source=migration / ?source=commit
  4) Tek reject: POST /<id>/reject → manual_hide=True + audit
  5) Bulk reject: POST /discovery-queue/bulk action=reject + ids
  6) Bulk delete: POST /discovery-queue/bulk action=delete + ids
  7) Manuel DRAFT kart bulk action'ından etkilenmez (slug filtresi)
  8) show_rejected=1 reddedilenleri de listeler
  9) /admin/feature-catalog liste sayfasında "Onay Kuyruğu (N)" rozeti
 10) Boş aksiyon / boş id listesi → err redirect

Kullanım:
    python -m scripts.test_discovery_queue
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    FeatureCard,
    FeatureDomain,
    FeatureStatus,
    FeatureTier,
    User,
    UserRole,
)
from app.services import feature_catalog as fc


PFX = f"kesif-test-{secrets.token_hex(3)}"  # NOT 'kesif-mig-' / 'kesif-c-' — bizim ayrı testbed
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


def cleanup(db) -> int:
    """Bu testin tüm fixture'larını temizle."""
    rows = db.query(FeatureCard).filter(
        (FeatureCard.slug.like(f"{PFX}%"))
        | (FeatureCard.slug.like(f"kesif-mig-{PFX}%"))
        | (FeatureCard.slug.like(f"kesif-c-{PFX}%"))
        | (FeatureCard.slug.like(f"manuel-{PFX}%"))
    ).all()
    n = len(rows)
    for c in rows:
        db.delete(c)
    db.commit()
    return n


def main() -> int:
    print(f"=== Katman 4 (Onay Kuyruğu) smoke ===  prefix={PFX}")

    # --- Süper admin bul ---
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("!! super_admin kullanıcı yok — test atlandı")
            return 0
        sa_id = sa.id

    # Fixture oluştur
    fixture_ids: dict[str, int] = {}
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        cleanup(db)

        # 2 migration kaynağı keşif + 1 commit kaynağı + 1 manuel DRAFT
        cases = [
            (f"kesif-mig-{PFX}-a", "test migration A", "migration"),
            (f"kesif-mig-{PFX}-b", "test migration B", "migration"),
            (f"kesif-c-{PFX}-c", "test commit C", "commit"),
            (f"manuel-{PFX}-d", "manuel DRAFT (etkilenmemeli)", "manual"),
        ]
        for slug, title, src in cases:
            card = fc.create(
                db,
                actor_id=sa_id,
                slug=slug,
                title=title,
                category_icon="🆕",
                category_label="Test",
                tagline="(test fixture)",
                description_md="",
                domain=FeatureDomain.GENEL.value,
                tier=FeatureTier.ENHANCEMENT.value,
                status=FeatureStatus.DRAFT.value,
                target_roles=[],
                introduced_at=now,
                introduced_in_commit=("abc1234" if src != "manual" else None),
                strategic_priority=2,
            )
            fixture_ids[slug] = card.id
        db.commit()

    # --- TestClient + super admin override ---
    def _override():
        def factory():
            db2 = SessionLocal()
            try:
                from sqlalchemy.orm import joinedload
                u = (
                    db2.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == sa_id)
                    .first()
                )
                _ = u.institution
                db2.expunge_all()
                return u
            finally:
                db2.close()
        return factory

    app.dependency_overrides[require_super_admin] = _override()
    app.dependency_overrides[require_user] = _override()
    app.dependency_overrides[get_current_user] = _override()

    try:
        c = TestClient(app)

        # ---- 2) GET /discovery-queue ----
        r = c.get("/admin/feature-catalog/discovery-queue")
        check("queue GET 200", r.status_code == 200, f"got {r.status_code}")
        check("kesif-mig adayı görünür", f"kesif-mig-{PFX}-a" in r.text)
        check("kesif-c adayı görünür", f"kesif-c-{PFX}-c" in r.text)
        check("manuel DRAFT görünmez (slug filtresi)",
              f"manuel-{PFX}-d" not in r.text)
        check("'Onay Kuyruğu' başlık", "Onay Kuyruğu" in r.text)
        check("📜 migration rozeti", "📜 migration" in r.text)
        check("💾 commit rozeti", "💾 commit" in r.text)

        # ---- 3) Kaynak filtresi ----
        r = c.get("/admin/feature-catalog/discovery-queue?source=migration")
        check("source=migration 200", r.status_code == 200)
        check("source=migration commit'i gizler",
              f"kesif-c-{PFX}-c" not in r.text)
        check("source=migration mig'i gösterir",
              f"kesif-mig-{PFX}-a" in r.text)

        r = c.get("/admin/feature-catalog/discovery-queue?source=commit")
        check("source=commit mig'i gizler",
              f"kesif-mig-{PFX}-a" not in r.text)
        check("source=commit commit'i gösterir",
              f"kesif-c-{PFX}-c" in r.text)

        # ---- 4) Tek reject ----
        target_id = fixture_ids[f"kesif-mig-{PFX}-a"]
        r = c.post(f"/admin/feature-catalog/{target_id}/reject", follow_redirects=False)
        check("single reject 303", r.status_code == 303, f"got {r.status_code}")
        with SessionLocal() as db:
            card = fc.get_by_id(db, target_id)
            check("reject sonrası manual_hide=True", card.manual_hide is True)
            check("reject sonrası status hala DRAFT",
                  card.status == FeatureStatus.DRAFT.value)
            audit = (
                db.query(AuditLog)
                .filter(
                    AuditLog.action == AuditAction.FEATURE_CARD_DISCOVERY_REJECTED,
                    AuditLog.target_id == target_id,
                )
                .first()
            )
            check("audit FEATURE_CARD_DISCOVERY_REJECTED düştü", audit is not None)

        # Reddedilen varsayılan listede yok
        r = c.get("/admin/feature-catalog/discovery-queue")
        check("reddedilen varsayılan listede yok",
              f"kesif-mig-{PFX}-a" not in r.text)

        # show_rejected=1 ile görünür
        r = c.get("/admin/feature-catalog/discovery-queue?show_rejected=1")
        check("show_rejected=1 reddedileni gösterir",
              f"kesif-mig-{PFX}-a" in r.text)
        check("REDDEDİLDİ etiketi", "REDDEDİLDİ" in r.text)

        # ---- 5) Bulk reject (kalan 2 keşif kartını) ----
        remaining_ids = [
            fixture_ids[f"kesif-mig-{PFX}-b"],
            fixture_ids[f"kesif-c-{PFX}-c"],
        ]
        manuel_id = fixture_ids[f"manuel-{PFX}-d"]
        r = c.post(
            "/admin/feature-catalog/discovery-queue/bulk",
            data={
                "action": "reject",
                # Manuel DRAFT id'sini de gönder — slug filtresi onu reddetmemeli
                "ids": [str(remaining_ids[0]), str(remaining_ids[1]), str(manuel_id)],
            },
            follow_redirects=False,
        )
        check("bulk reject 303", r.status_code == 303, f"got {r.status_code}")
        with SessionLocal() as db:
            for cid in remaining_ids:
                card = fc.get_by_id(db, cid)
                check(f"bulk reject id={cid} manual_hide=True",
                      card.manual_hide is True)
            manuel = fc.get_by_id(db, manuel_id)
            check("manuel DRAFT BULK reject'ten etkilenmedi",
                  manuel.manual_hide is False)

        # ---- 6) Bulk delete (reddedileni de dahil silebiliriz) ----
        r = c.post(
            "/admin/feature-catalog/discovery-queue/bulk",
            data={
                "action": "delete",
                "ids": [str(fixture_ids[f"kesif-mig-{PFX}-a"]), str(manuel_id)],
            },
            follow_redirects=False,
        )
        check("bulk delete 303", r.status_code == 303, f"got {r.status_code}")
        with SessionLocal() as db:
            still_there = fc.get_by_id(db, fixture_ids[f"kesif-mig-{PFX}-a"])
            check("bulk delete keşif kartını sildi", still_there is None)
            manuel = fc.get_by_id(db, manuel_id)
            check("bulk delete manuel kartı silmedi (slug filtresi)",
                  manuel is not None)

        # ---- 10) Boş aksiyon / boş ids ----
        r = c.post(
            "/admin/feature-catalog/discovery-queue/bulk",
            data={"action": "reject"},  # ids yok
            follow_redirects=False,
        )
        check("boş ids err redirect", r.status_code == 303 and "err=" in r.headers.get("location", ""))

        r = c.post(
            "/admin/feature-catalog/discovery-queue/bulk",
            data={"ids": str(manuel_id)},  # action yok
            follow_redirects=False,
        )
        check("boş action err redirect", r.status_code == 303 and "err=" in r.headers.get("location", ""))

        # ---- 9) Liste sayfasında "Onay Kuyruğu" rozeti ----
        # Önce şu an pending kaç tane var bakalım — yeni keşif üret
        with SessionLocal() as db:
            cleanup(db)
            # Mock pending: bir tane kesif-mig fixture
            fc.create(
                db,
                actor_id=sa_id,
                slug=f"kesif-mig-{PFX}-badge",
                title="badge test",
                category_icon="🆕", category_label="Test",
                tagline="x", description_md="",
                domain=FeatureDomain.GENEL.value,
                tier=FeatureTier.ENHANCEMENT.value,
                status=FeatureStatus.DRAFT.value,
                target_roles=[],
                introduced_at=now,
                strategic_priority=2,
            )
            db.commit()

        r = c.get("/admin/feature-catalog")
        check("list page 200", r.status_code == 200)
        check("'Onay Bekleyenler' link rozeti", "Onay Bekleyenler" in r.text)
        check("rozet href doğru",
              "/admin/feature-catalog/discovery-queue" in r.text)

        # Cleanup
        with SessionLocal() as db:
            n = cleanup(db)
            print(f"  Cleanup: {n} kart silindi")

    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
