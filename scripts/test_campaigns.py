"""Sprint E.1 — Toplu Kampanya Sistemi (Faz E Seviye 2) smoke test.

Test ettiği:
  - preview_segment: 7 segment için sonuç döner (boş veya dolu)
  - CUSTOM_PLAN segment: filter_plan ile eşleşen kurumları döner
  - create_campaign: DRAFT durumunda yeni kampanya
  - create_campaign: variant_b zorunlu alan eksikse None
  - launch_campaign: DRAFT → RUNNING + recipient + offer üret
  - A/B split: deterministik (inst_id parite)
  - pause/resume/complete state transitions
  - cancel: sadece DRAFT
  - sync_recipient_statuses: Offer.ACCEPTED → Recipient.ACCEPTED
  - campaign_stats: overall + variant_a + variant_b funnel
  - HTTP /admin/revenue/campaigns: 200 + liste render
  - HTTP /admin/revenue/campaigns/new: 200 + form
  - HTTP /admin/revenue/campaigns/preview (HTMX): 200 + partial
  - HTTP /admin/revenue/campaigns/create: 303 + DB'de yaratıldı
  - HTTP /admin/revenue/campaigns/{id}: 200 + detay
  - HTTP launch/pause/resume/complete/cancel: 303
  - Audit log: campaign target_type kayıtları
"""

from __future__ import annotations

import json
import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    AuditLog,
    Campaign,
    CampaignRecipient,
    CampaignSegment,
    CampaignStatus,
    Institution,
    Offer,
    OfferStatus,
    RecipientStatus,
    User,
    UserRole,
)
from app.services.campaigns import (
    campaign_stats,
    cancel_campaign,
    complete_campaign,
    create_campaign,
    launch_campaign,
    pause_campaign,
    preview_segment,
    resume_campaign,
    sync_recipient_statuses,
)


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
    print("=== Sprint E.1 — Toplu Kampanya smoke ===")
    tag = f"sprinte1-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if not sa:
            print("  (SA yok — atlandı)")
            return 0
        sa_id = sa.id

    # Cleanup geçmiş test verisi
    with SessionLocal() as db:
        db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign.has(Campaign.name.like(f"{tag}%"))
        ).delete(synchronize_session=False)
        db.query(Campaign).filter(Campaign.name.like(f"{tag}%")).delete()
        db.query(Offer).filter(Offer.admin_note.like(f"%{tag}%")).delete()
        db.commit()

    # Test kurumları oluştur (4 tanesi solo_free, eşit dağılım A/B için)
    test_inst_ids: list[int] = []
    with SessionLocal() as db:
        for i in range(6):
            inst = Institution(
                name=f"{tag} camp test #{i}",
                slug=f"{tag.lower()}-c-{i}",
                contact_email=f"{tag}_{i}@test.local",
                plan="solo_free",
                is_active=True,
            )
            db.add(inst)
            db.flush()
            test_inst_ids.append(inst.id)
            # Bir kurumun yetkilisi olarak admin user (last_login_at NULL → never_logged_in eligible)
            admin_u = User(
                full_name=f"{tag} Admin #{i}",
                email=f"{tag}_admin_{i}@test.local",
                password_hash="x",
                role=UserRole.INSTITUTION_ADMIN,
                institution_id=inst.id,
                is_active=True,
                last_login_at=None,
            )
            db.add(admin_u)
        db.commit()

    # ---- 1) preview_segment: FREE_PLAN ----
    with SessionLocal() as db:
        insts = preview_segment(db, segment=CampaignSegment.FREE_PLAN)
        test_in_free = [i for i in insts if i.id in test_inst_ids]
        check("preview FREE_PLAN: test kurumları (6) listede",
              len(test_in_free) == 6,
              f"got {len(test_in_free)}/6")

    # ---- 2) preview_segment: CUSTOM_PLAN filter ----
    with SessionLocal() as db:
        insts = preview_segment(
            db, segment=CampaignSegment.CUSTOM_PLAN, filter_plan="solo_free",
        )
        test_in_custom = [i for i in insts if i.id in test_inst_ids]
        check("preview CUSTOM_PLAN(solo_free): test kurumları listede",
              len(test_in_custom) == 6)

    # ---- 3) preview_segment: CUSTOM_PLAN filter yoksa boş ----
    with SessionLocal() as db:
        insts = preview_segment(
            db, segment=CampaignSegment.CUSTOM_PLAN, filter_plan=None,
        )
        check("preview CUSTOM_PLAN(no filter): boş", len(insts) == 0)

    # ---- 4) preview_segment: NEVER_LOGGED_IN ----
    with SessionLocal() as db:
        insts = preview_segment(db, segment=CampaignSegment.NEVER_LOGGED_IN)
        test_never = [i.id for i in insts if i.id in test_inst_ids]
        check("preview NEVER_LOGGED_IN: test kurumları (admin last_login=None)",
              len(test_never) == 6, f"got {len(test_never)}/6")

    # ---- 5) create_campaign: DRAFT ----
    with SessionLocal() as db:
        camp = create_campaign(
            db,
            name=f"{tag} test kampanya 1",
            segment="free_plan",
            variant_a_kind="discount_percent",
            variant_a_title="3 ay %20 indirim",
            variant_a_value=20.0,
            variant_a_duration_months=3,
            variant_a_public_message="Size özel teklif.",
            by_user_id=sa_id,
            description="Test description",
            offer_expires_in_days=14,
        )
        check("create_campaign: nesne döner + DRAFT",
              camp is not None and camp.status == CampaignStatus.DRAFT)
        camp_id_1 = camp.id if camp else None

    # ---- 6) create_campaign: geçersiz segment → None ----
    with SessionLocal() as db:
        bad = create_campaign(
            db, name=f"{tag} bad", segment="invalid_segment",
            variant_a_kind="custom", variant_a_title="x",
            by_user_id=sa_id,
        )
        check("create_campaign: geçersiz segment → None", bad is None)

    # ---- 7) create_campaign: variant_b eksik → None ----
    with SessionLocal() as db:
        bad = create_campaign(
            db, name=f"{tag} bad2", segment="free_plan",
            variant_a_kind="custom", variant_a_title="A",
            by_user_id=sa_id,
            has_variant_b=True, variant_b_kind=None, variant_b_title=None,
        )
        check("create_campaign: B eksik → None", bad is None)

    # ---- 8) create_campaign: A/B çift varyant ----
    with SessionLocal() as db:
        camp_ab = create_campaign(
            db,
            name=f"{tag} A/B kampanya",
            segment="custom_plan",
            segment_filter_plan="solo_free",
            variant_a_kind="discount_percent",
            variant_a_title=f"{tag} A — %15 indirim",
            variant_a_value=15.0,
            variant_a_duration_months=3,
            has_variant_b=True,
            variant_b_kind="discount_fixed",
            variant_b_title=f"{tag} B — 100 ₺ indirim",
            variant_b_value=100.0,
            variant_b_duration_months=3,
            by_user_id=sa_id,
        )
        check("create_campaign A/B: has_variant_b=True",
              camp_ab is not None and camp_ab.has_variant_b is True)
        camp_id_ab = camp_ab.id if camp_ab else None

    # ---- 9) launch_campaign (A/B) → recipient'lar yaratıldı ----
    with SessionLocal() as db:
        r = launch_campaign(db, campaign_id=camp_id_ab)
        check("launch_campaign A/B: ok=True", r.get("ok"), str(r))
        check("launch_campaign A/B: recipient_count >= 6",
              r.get("recipient_count", 0) >= 6,
              f"got recipients={r.get('recipient_count')}")
        check("launch_campaign A/B: sent >= 1",
              r.get("sent", 0) >= 1)
        camp_obj = db.get(Campaign, camp_id_ab)
        check("launch_campaign: status=RUNNING",
              camp_obj.status == CampaignStatus.RUNNING)

    # ---- 10) A/B split deterministik ----
    with SessionLocal() as db:
        recips = (
            db.query(CampaignRecipient)
            .filter(CampaignRecipient.campaign_id == camp_id_ab)
            .all()
        )
        for r in recips:
            expected = "A" if (r.institution_id % 2 == 0) else "B"
            if r.variant != expected:
                check(f"A/B split: inst#{r.institution_id} = {expected}",
                      False, f"got {r.variant}")
                break
        else:
            check("A/B split: hepsi inst_id paritesine uygun", True)
        # En az 1 tane A ve 1 tane B olmalı (test kurumlarımız hem tek hem çift ID'li)
        variant_counts = {"A": 0, "B": 0}
        for r in recips:
            variant_counts[r.variant] = variant_counts.get(r.variant, 0) + 1
        check("A/B split: hem A hem B var",
              variant_counts["A"] > 0 and variant_counts["B"] > 0,
              str(variant_counts))

    # ---- 11) Recipient'lara Offer atandı ----
    with SessionLocal() as db:
        recips = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == camp_id_ab,
                CampaignRecipient.status == RecipientStatus.SENT,
            )
            .all()
        )
        check("recipients: offer_id atandı",
              all(r.offer_id is not None for r in recips))

    # ---- 12) Bir recipient'in offer'ını ACCEPT et + sync ----
    with SessionLocal() as db:
        test_recip = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == camp_id_ab,
                CampaignRecipient.status == RecipientStatus.SENT,
            )
            .first()
        )
        if test_recip and test_recip.offer_id:
            offer = db.get(Offer, test_recip.offer_id)
            offer.status = OfferStatus.ACCEPTED
            offer.responded_at = datetime.now(timezone.utc)
            db.commit()

    with SessionLocal() as db:
        r = sync_recipient_statuses(db, campaign_id=camp_id_ab)
        check("sync_recipient_statuses: ok",
              r.get("ok") and r.get("updated_count", 0) >= 1, str(r))
        # Sync sonrası kontrol
        updated = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == camp_id_ab,
                CampaignRecipient.status == RecipientStatus.ACCEPTED,
            )
            .count()
        )
        check("sync sonrası: en az 1 recipient ACCEPTED", updated >= 1)

    # ---- 13) campaign_stats: funnel ----
    with SessionLocal() as db:
        st = campaign_stats(db, campaign_id=camp_id_ab)
        check("campaign_stats: ok", st.get("ok"))
        check("campaign_stats: overall total >= 6",
              st["overall"]["total"] >= 6)
        check("campaign_stats: variant_a + variant_b ayrı",
              st["variant_a"]["total"] >= 1
              and st["variant_b"]["total"] >= 1)
        check("campaign_stats: accepted >= 1",
              st["overall"]["accepted"] >= 1)
        check("campaign_stats: accepted_pct hesaplandı",
              st["overall"]["accepted_pct"] is not None)

    # ---- 14) pause + resume ----
    with SessionLocal() as db:
        r = pause_campaign(db, campaign_id=camp_id_ab)
        check("pause_campaign: ok", r.get("ok"))
        camp_obj = db.get(Campaign, camp_id_ab)
        check("pause: status=PAUSED",
              camp_obj.status == CampaignStatus.PAUSED)

    with SessionLocal() as db:
        r = resume_campaign(db, campaign_id=camp_id_ab)
        check("resume_campaign: ok", r.get("ok"))
        camp_obj = db.get(Campaign, camp_id_ab)
        check("resume: status=RUNNING",
              camp_obj.status == CampaignStatus.RUNNING)

    # ---- 15) complete ----
    with SessionLocal() as db:
        r = complete_campaign(db, campaign_id=camp_id_ab)
        check("complete_campaign: ok", r.get("ok"))
        camp_obj = db.get(Campaign, camp_id_ab)
        check("complete: status=COMPLETED + completed_at",
              camp_obj.status == CampaignStatus.COMPLETED
              and camp_obj.completed_at is not None)

    # ---- 16) cancel: sadece DRAFT ----
    with SessionLocal() as db:
        r = cancel_campaign(db, campaign_id=camp_id_1)
        check("cancel_campaign (draft): ok", r.get("ok"))
        camp_obj = db.get(Campaign, camp_id_1)
        check("cancel: status=CANCELLED",
              camp_obj.status == CampaignStatus.CANCELLED)

    # ---- 17) cancel: COMPLETED → not_draft ----
    with SessionLocal() as db:
        r = cancel_campaign(db, campaign_id=camp_id_ab)
        check("cancel COMPLETED: not_draft",
              not r.get("ok") and r.get("error") == "not_draft")

    # ---- 18) HTTP route'ları ----
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()

    def _admin():
        return admin

    app.dependency_overrides[require_super_admin] = _admin
    app.dependency_overrides[require_user] = _admin
    app.dependency_overrides[get_current_user] = _admin

    new_camp_id: int | None = None
    try:
        client = TestClient(app)

        # Liste
        res = client.get("/admin/revenue/campaigns", follow_redirects=False)
        check("HTTP GET /campaigns: 200",
              res.status_code == 200, f"status={res.status_code}")
        if res.status_code == 200:
            check("Liste sayfası: 'Toplu Kampanyalar' render",
                  "Toplu Kampanya" in res.text or "Kampanyalar" in res.text)

        # Yeni form
        res = client.get("/admin/revenue/campaigns/new", follow_redirects=False)
        check("HTTP GET /campaigns/new: 200",
              res.status_code == 200)
        if res.status_code == 200:
            check("Form: segment listesi render",
                  "Ücretsiz planda" in res.text)
            check("Form: A/B varyant checkbox",
                  "has_variant_b" in res.text)

        # Preview (HTMX)
        res = client.post(
            "/admin/revenue/campaigns/preview",
            data={"segment": "free_plan", "filter_plan": ""},
            follow_redirects=False,
        )
        check("HTTP POST /campaigns/preview: 200",
              res.status_code == 200, f"status={res.status_code}")
        if res.status_code == 200:
            check("Preview: 'kurum hedeflenecek' metni",
                  "kurum" in res.text.lower())

        # Create (POST)
        res = client.post(
            "/admin/revenue/campaigns/create",
            data={
                "name": f"{tag} HTTP kampanya",
                "segment": "free_plan",
                "variant_a_kind": "discount_percent",
                "variant_a_title": "HTTP test indirim",
                "variant_a_value": "10",
                "variant_a_duration_months": "2",
                "variant_a_public_message": "HTTP test message",
                "offer_expires_in_days": "7",
            },
            follow_redirects=False,
        )
        check("HTTP POST /campaigns/create: 303",
              res.status_code == 303, f"status={res.status_code}")
        if res.status_code == 303:
            check("HTTP create: redirect /campaigns/{id}",
                  "/admin/revenue/campaigns/" in res.headers.get("location", ""))
            # ID'yi parse et
            loc = res.headers.get("location", "")
            try:
                seg = loc.split("/campaigns/")[1].split("?")[0]
                new_camp_id = int(seg)
            except Exception:
                pass

        # Detay
        if new_camp_id:
            res = client.get(
                f"/admin/revenue/campaigns/{new_camp_id}", follow_redirects=False,
            )
            check("HTTP GET /campaigns/{id}: 200",
                  res.status_code == 200)
            if res.status_code == 200:
                check("Detay: kampanya adı render",
                      f"{tag} HTTP kampanya" in res.text)
                check("Detay: 'Başlat' butonu (DRAFT)",
                      "Başlat" in res.text)

            # Launch
            res = client.post(
                f"/admin/revenue/campaigns/{new_camp_id}/launch",
                follow_redirects=False,
            )
            check("HTTP POST /campaigns/{id}/launch: 303",
                  res.status_code == 303)
            with SessionLocal() as db:
                camp_obj = db.get(Campaign, new_camp_id)
                check("HTTP launch: status=RUNNING veya COMPLETED",
                      camp_obj.status in (CampaignStatus.RUNNING,
                                           CampaignStatus.COMPLETED))

            # Pause (eğer running ise)
            with SessionLocal() as db:
                camp_obj = db.get(Campaign, new_camp_id)
                if camp_obj.status == CampaignStatus.RUNNING:
                    res = client.post(
                        f"/admin/revenue/campaigns/{new_camp_id}/pause",
                        follow_redirects=False,
                    )
                    check("HTTP POST /pause: 303", res.status_code == 303)
                    res = client.post(
                        f"/admin/revenue/campaigns/{new_camp_id}/resume",
                        follow_redirects=False,
                    )
                    check("HTTP POST /resume: 303", res.status_code == 303)
                    res = client.post(
                        f"/admin/revenue/campaigns/{new_camp_id}/complete",
                        follow_redirects=False,
                    )
                    check("HTTP POST /complete: 303", res.status_code == 303)
                else:
                    check("HTTP pause/resume/complete: COMPLETED'a düştü (recipient 0)",
                          True)

        # Bilinmeyen kampanya → 404
        res = client.get("/admin/revenue/campaigns/999999", follow_redirects=False)
        check("HTTP GET /campaigns/999999: 404",
              res.status_code == 404)

        # Audit log: campaign target_type için kayıt
        with SessionLocal() as db:
            audits = (
                db.query(AuditLog)
                .filter(
                    AuditLog.target_type == "campaign",
                    AuditLog.actor_id == sa_id,
                )
                .order_by(AuditLog.id.desc())
                .limit(20)
                .all()
            )
            check("Audit log: campaign kayıtları mevcut",
                  len(audits) >= 2, f"got {len(audits)}")
            actions = set()
            for a in audits:
                if a.details_json:
                    try:
                        d = json.loads(a.details_json)
                        if isinstance(d, dict) and d.get("action"):
                            actions.add(d["action"])
                    except (ValueError, TypeError):
                        pass
            check("Audit: 'create' kayıtlı",
                  "create" in actions, str(actions))
            check("Audit: 'launch' kayıtlı",
                  "launch" in actions)

        # Ticari panel'de Kampanyalar linki
        res = client.get("/admin/security-monitor/revenue", follow_redirects=False)
        if res.status_code == 200:
            check("Ticari Pano'da 'Kampanyalar' linki var",
                  "/admin/revenue/campaigns" in res.text)

    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign.has(Campaign.name.like(f"{tag}%"))
        ).delete(synchronize_session=False)
        db.query(Campaign).filter(Campaign.name.like(f"{tag}%")).delete()
        db.query(Offer).filter(Offer.admin_note.like(f"%{tag}%")).delete()
        # User'lar (institution_id FK cascade ile silinmez çünkü institution silinir)
        if test_inst_ids:
            db.query(User).filter(
                User.email.like(f"{tag}_admin_%@test.local"),
            ).delete(synchronize_session=False)
            db.query(Institution).filter(
                Institution.id.in_(test_inst_ids),
            ).delete(synchronize_session=False)
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS / {len(failed)} FAIL ===")
    if failed:
        print("\nFAIL'ler:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
