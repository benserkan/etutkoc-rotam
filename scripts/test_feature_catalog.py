"""Katman 1 — Özellik Kataloğu smoke test (project konvansiyonu: scripts/test_*.py).

Senaryolar:
1. Model:
   - slug UNIQUE
   - JSON property'leri round-trip
   - enum property'leri ve fallback
   - is_visible_on_homepage / is_pinned mantığı

2. Service (feature_catalog):
   - slugify Türkçe karakter
   - normalize_accent_color
   - create + validation hataları
   - update kısmi alan
   - get_by_slug / get_by_id
   - list_for_admin filtreleme + arama
   - get_published_visible — status + manual_hide filtresi + pin önceliği
   - count_by_status
   - set_status + set_pin
   - delete

3. HTTP /admin/feature-catalog:
   - liste 200 + sayım rozetleri
   - new GET 200 + form
   - new POST + audit
   - edit GET 200
   - edit POST + audit
   - status change POST + audit
   - pin POST + audit
   - delete POST + audit
   - filtre query string

4. Audit kaydı log_action ile düşmüş mü
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


PFX = f"fctest{secrets.token_hex(3)}"
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


def cleanup_by_prefix(db, prefix: str) -> int:
    cards = db.query(FeatureCard).filter(FeatureCard.slug.like(f"{prefix}%")).all()
    n = len(cards)
    for c in cards:
        db.delete(c)
    db.commit()
    return n


def main() -> int:
    now = datetime.now(timezone.utc)

    # ============ STEP 1: Model bazı ============
    print("\n=== STEP 1: Model + slug UNIQUE + property ===")
    with SessionLocal() as db:
        c = FeatureCard(
            slug=f"{PFX}-a",
            title=f"{PFX} model test",
        )
        c.target_roles = [UserRole.STUDENT, "teacher"]
        c.benefits = [" Fayda 1 ", "", "Fayda 2"]
        c.pain_points = ["Sorun A"]
        db.add(c); db.commit(); db.refresh(c)
        c_id = c.id

        check("target_roles round-trip",
              c.target_roles == ["student", "teacher"],
              f"got {c.target_roles}")
        check("benefits boş satır temizlenir",
              c.benefits == ["Fayda 1", "Fayda 2"],
              f"got {c.benefits}")
        check("pain_points round-trip",
              c.pain_points == ["Sorun A"])
        check("status_enum fallback DRAFT",
              c.status_enum == FeatureStatus.DRAFT)
        check("domain_enum default GENEL",
              c.domain_enum == FeatureDomain.GENEL)
        check("tier_enum default ENHANCEMENT",
              c.tier_enum == FeatureTier.ENHANCEMENT)
        check("is_visible_on_homepage DRAFT False",
              not c.is_visible_on_homepage())

        c.status = FeatureStatus.PUBLISHED.value
        db.commit()
        check("is_visible_on_homepage PUBLISHED True",
              c.is_visible_on_homepage())

        c.manual_hide = True
        db.commit()
        check("manual_hide → is_visible False",
              not c.is_visible_on_homepage())

        # is_pinned — süresiz
        c.manual_pin = True
        c.pin_until = None
        db.commit()
        check("manual_pin süresiz is_pinned=True",
              c.is_pinned(now))

        # is_pinned — gelecek
        c.pin_until = now + timedelta(days=7)
        db.commit()
        check("pin_until gelecek is_pinned=True",
              c.is_pinned(now))

        # is_pinned — geçmiş
        c.pin_until = now - timedelta(days=1)
        db.commit()
        check("pin_until geçmiş is_pinned=False",
              not c.is_pinned(now))

        # UNIQUE
        try:
            dup = FeatureCard(slug=f"{PFX}-a", title="dup")
            db.add(dup); db.commit()
            check("slug UNIQUE ihlali yakaladı", False, "INSERT geçti")
        except Exception:
            db.rollback()
            check("slug UNIQUE ihlali yakaladı", True)

    # ============ STEP 2: Service helper'lar ============
    print("\n=== STEP 2: slugify + normalize_accent_color ===")
    check("slugify TR karakter",
          fc.slugify("Çağrı Düğmesi") == "cagri-dugmesi",
          fc.slugify("Çağrı Düğmesi"))
    check("slugify çoklu boşluk",
          fc.slugify("  Bir  iki  ") == "bir-iki")
    check("slugify özel karakter",
          fc.slugify("a!@#b$%c") == "a-b-c")
    check("slugify boş",
          fc.slugify("") == "")
    check("normalize_accent_color geçerli hex",
          fc.normalize_accent_color("#abc123") == "#abc123")
    check("normalize_accent_color # eksik",
          fc.normalize_accent_color("abc") == "#abc")
    check("normalize_accent_color geçersiz → default",
          fc.normalize_accent_color("not-a-color") == "#3b82f6")
    check("normalize_accent_color None → default",
          fc.normalize_accent_color(None) == "#3b82f6")

    # ============ STEP 3: Service CRUD ============
    print("\n=== STEP 3: service create/get/update/delete ===")
    with SessionLocal() as db:
        card = fc.create(
            db,
            actor_id=None,
            slug=f"{PFX}-svc-1",
            title="Servis test 1",
            tagline="bir satır",
            description_md="## başlık\nİçerik",
            target_roles=[UserRole.STUDENT, UserRole.TEACHER],
            benefits=["A", "B"],
            pain_points=["P1"],
            demo_slug="daily-plan",
            domain="lgs",
            tier="core",
            status="published",
            strategic_priority=4,
            accent_color="#ff0000",
        )
        check("create başarılı", card.id is not None)
        check("create target_roles",
              card.target_roles == ["student", "teacher"])
        check("create benefits",
              card.benefits == ["A", "B"])
        check("create accent_color normalize",
              card.accent_color == "#ff0000")

        # get_by_slug + get_by_id
        check("get_by_slug bulur",
              fc.get_by_slug(db, f"{PFX}-svc-1") is not None)
        check("get_by_id bulur",
              fc.get_by_id(db, card.id) is not None)
        check("get_by_slug yok → None",
              fc.get_by_slug(db, "nonexistent-x") is None)

        # Update kısmi
        fc.update(
            db, card,
            actor_id=None,
            title="Servis test 1 — güncel",
            benefits=["Yeni A"],
        )
        check("update title değişti",
              card.title == "Servis test 1 — güncel")
        check("update benefits değişti",
              card.benefits == ["Yeni A"])
        check("update target_roles dokunulmadı",
              card.target_roles == ["student", "teacher"])

        # Validation: boş slug
        try:
            fc.create(db, actor_id=None, slug="", title="x")
            check("boş slug → hata", False, "yakalanmadı")
        except fc.FeatureCatalogError:
            check("boş slug → hata", True)

        # Validation: duplicate slug
        try:
            fc.create(db, actor_id=None, slug=f"{PFX}-svc-1", title="dup")
            check("dup slug → hata", False, "yakalanmadı")
        except fc.FeatureCatalogError:
            check("dup slug → hata", True)

        # Validation: geçersiz domain
        try:
            fc.create(db, actor_id=None, slug=f"{PFX}-bad", title="x", domain="uzay")
            check("geçersiz domain → hata", False, "yakalanmadı")
        except fc.FeatureCatalogError:
            check("geçersiz domain → hata", True)

        # Validation: priority 1-5 dışı
        try:
            fc.create(
                db, actor_id=None, slug=f"{PFX}-prio",
                title="x", strategic_priority=9,
            )
            check("priority>5 → hata", False, "yakalanmadı")
        except fc.FeatureCatalogError:
            check("priority>5 → hata", True)

        # status değiştir + pin
        fc.set_status(db, card, "hidden", actor_id=None)
        check("set_status HIDDEN",
              card.status == FeatureStatus.HIDDEN.value)
        fc.set_pin(db, card, pinned=True, until=None, actor_id=None)
        check("set_pin sürelis",
              card.manual_pin and card.pin_until is None)

    # ============ STEP 4: list/published/count ============
    print("\n=== STEP 4: list_for_admin + get_published_visible + count ===")
    with SessionLocal() as db:
        # 3 ek kart: published, draft, published-hidden
        c_pub = fc.create(
            db, actor_id=None, slug=f"{PFX}-pub",
            title=f"{PFX} pub", domain="lgs", status="published",
            strategic_priority=5,
        )
        c_draft = fc.create(
            db, actor_id=None, slug=f"{PFX}-draft",
            title=f"{PFX} draft", domain="yks", status="draft",
        )
        c_hidden = fc.create(
            db, actor_id=None, slug=f"{PFX}-hidden",
            title=f"{PFX} hidden", domain="kurumsal", status="published",
            manual_hide=True,
        )

        # list_for_admin
        all_pfx = [
            c for c in fc.list_for_admin(db, search=PFX)
        ]
        check("list_for_admin search PFX bulur >=3",
              len(all_pfx) >= 3, f"got {len(all_pfx)}")

        only_pub = fc.list_for_admin(db, status_filter="published", search=PFX)
        check("status_filter=published",
              all(c.status == "published" for c in only_pub))

        only_lgs = fc.list_for_admin(db, domain_filter="lgs", search=PFX)
        check("domain_filter=lgs",
              all(c.domain == "lgs" for c in only_lgs))

        # get_published_visible
        vis = fc.get_published_visible(db)
        vis_slugs = {c.slug for c in vis}
        check("published görünür",
              f"{PFX}-pub" in vis_slugs)
        check("draft görünmez",
              f"{PFX}-draft" not in vis_slugs)
        check("manual_hide görünmez",
              f"{PFX}-hidden" not in vis_slugs)

        # count_by_status
        counts = fc.count_by_status(db)
        check("count_by_status 4 anahtar",
              set(counts.keys()) == {"draft", "published", "hidden", "deprecated"})
        check("count_by_status published>=1",
              counts["published"] >= 1)

    # ============ STEP 5: HTTP route'lar (auth override) ============
    print("\n=== STEP 5: HTTP route'lar ===")
    with SessionLocal() as db:
        sa = db.query(User).filter(
            User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True),
        ).first()
        if sa is None:
            print("  [SKIP] Süper admin kullanıcı yok — HTTP testleri atlandı")
            return _report()
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

    try:
        c = TestClient(app)

        # Liste
        r = c.get("/admin/feature-catalog")
        check("GET list 200", r.status_code == 200, f"got {r.status_code}")
        check("'Vitrin Kartları' başlık", "Vitrin Kartları" in r.text)

        # PFX kart listede
        check(f"{PFX}-pub listede",
              f"{PFX}-pub" in r.text)

        # Filtre query
        r = c.get("/admin/feature-catalog?status_filter=draft&q=" + PFX)
        check("filtre query 200", r.status_code == 200)

        # New form
        r = c.get("/admin/feature-catalog/new")
        check("GET new form 200", r.status_code == 200)
        check("Slug input var", "name=\"slug\"" in r.text)

        # Create POST
        new_slug = f"{PFX}-http-create"
        r = c.post(
            "/admin/feature-catalog/new",
            data={
                "slug": new_slug,
                "title": f"{PFX} http oluştur",
                "tagline": "HTTP'den geldi",
                "description_md": "açıklama",
                "icon": "rocket",
                "accent_color": "#00ff00",
                "target_roles": ["student", "teacher"],
                "benefits_text": "B1\nB2",
                "pain_points_text": "P1",
                "demo_slug": "daily-plan",
                "domain": "yks",
                "tier": "enhancement",
                "status_field": "published",
                "strategic_priority": 4,
                "cta_label": "Detayları gör",
            },
            follow_redirects=False,
        )
        check("create POST 303", r.status_code == 303, f"got {r.status_code}")
        with SessionLocal() as db:
            created = fc.get_by_slug(db, new_slug)
            check("create DB satırı oluştu", created is not None)
            new_id = created.id if created else None
            if created:
                check("create benefits doğru",
                      created.benefits == ["B1", "B2"])
                check("create target_roles doğru",
                      created.target_roles == ["student", "teacher"])
                check("create domain=yks",
                      created.domain == "yks")
            # Audit kaydı
            audit = (
                db.query(AuditLog)
                .filter(
                    AuditLog.action == AuditAction.FEATURE_CARD_CREATE,
                    AuditLog.target_id == new_id,
                )
                .first()
            )
            check("audit FEATURE_CARD_CREATE", audit is not None)

        # Edit GET
        if new_id:
            r = c.get(f"/admin/feature-catalog/{new_id}")
            check("GET edit form 200", r.status_code == 200)
            check("Slug değeri form'da",
                  f"value=\"{new_slug}\"" in r.text)

        # Update POST
        if new_id:
            r = c.post(
                f"/admin/feature-catalog/{new_id}",
                data={
                    "slug": new_slug,
                    "title": f"{PFX} güncellendi",
                    "tagline": "",
                    "description_md": "yeni",
                    "icon": "rocket",
                    "accent_color": "#00ff00",
                    "target_roles": ["student"],
                    "benefits_text": "Yeni B",
                    "pain_points_text": "",
                    "demo_slug": "",
                    "domain": "yks",
                    "tier": "enhancement",
                    "status_field": "published",
                    "strategic_priority": 3,
                    "cta_label": "Detayları gör",
                },
                follow_redirects=False,
            )
            check("update POST 303", r.status_code == 303)
            with SessionLocal() as db:
                upd = fc.get_by_id(db, new_id)
                check("update title yansıdı",
                      upd.title == f"{PFX} güncellendi" if upd else False)
                check("update target_roles tek rol",
                      upd.target_roles == ["student"] if upd else False)
                audit = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.action == AuditAction.FEATURE_CARD_UPDATE,
                        AuditLog.target_id == new_id,
                    )
                    .first()
                )
                check("audit FEATURE_CARD_UPDATE", audit is not None)

        # Status change
        if new_id:
            r = c.post(
                f"/admin/feature-catalog/{new_id}/status",
                data={"status_field": "hidden"},
                follow_redirects=False,
            )
            check("status change POST 303", r.status_code == 303)
            with SessionLocal() as db:
                upd = fc.get_by_id(db, new_id)
                check("status=hidden DB", upd.status == "hidden" if upd else False)
                audit = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.action == AuditAction.FEATURE_CARD_STATUS_CHANGE,
                        AuditLog.target_id == new_id,
                    )
                    .first()
                )
                check("audit STATUS_CHANGE", audit is not None)

        # Pin POST
        if new_id:
            r = c.post(
                f"/admin/feature-catalog/{new_id}/pin",
                data={"pinned": "on", "pin_until": ""},
                follow_redirects=False,
            )
            check("pin POST 303", r.status_code == 303)
            with SessionLocal() as db:
                upd = fc.get_by_id(db, new_id)
                check("manual_pin DB True", upd.manual_pin if upd else False)
                audit = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.action == AuditAction.FEATURE_CARD_PIN,
                        AuditLog.target_id == new_id,
                    )
                    .first()
                )
                check("audit PIN", audit is not None)

        # Delete POST
        if new_id:
            r = c.post(
                f"/admin/feature-catalog/{new_id}/delete",
                follow_redirects=False,
            )
            check("delete POST 303", r.status_code == 303)
            with SessionLocal() as db:
                gone = fc.get_by_id(db, new_id)
                check("delete DB'den silindi", gone is None)
                audit = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.action == AuditAction.FEATURE_CARD_DELETE,
                        AuditLog.target_id == new_id,
                    )
                    .first()
                )
                check("audit DELETE", audit is not None)

        # Invalid slug create
        r = c.post(
            "/admin/feature-catalog/new",
            data={
                "slug": "",
                "title": "boş",
                "domain": "genel",
                "tier": "enhancement",
                "status_field": "draft",
                "strategic_priority": 3,
                "cta_label": "x",
            },
            follow_redirects=False,
        )
        check("boş slug POST → redirect 303 + err query",
              r.status_code == 303 and "err=" in (r.headers.get("location") or ""))

    finally:
        app.dependency_overrides.clear()

    return _report()


def _report() -> int:
    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")

    # Cleanup
    with SessionLocal() as db:
        n = cleanup_by_prefix(db, PFX)
        if n:
            print(f"  Cleanup: {n} kart silindi")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
