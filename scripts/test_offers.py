"""Sprint D.1 — Bireysel Teklif Sistemi (Faz E Seviye 1) smoke test.

Test ettiği:
  - create_offer: DRAFT durumunda yeni teklif
  - send_offer: DRAFT → SENT + sent_at + e-posta tetik (stub)
  - cancel_offer: DRAFT veya SENT → CANCELLED
  - accept_offer (token): SENT → ACCEPTED + PlanChangeHistory yazılır
  - decline_offer (token): SENT → DECLINED + reason kaydedilir
  - PLAN_UPGRADE kabul → institution.plan değişir
  - TRIAL_EXTENSION kabul → institution.trial_ends_at uzar
  - expire_old_offers: süresi dolmuş SENT → EXPIRED
  - HTTP GET /offers/{token} → 200 (public, login yok)
  - HTTP POST /offers/{token}/accept → 303 + accepted=1 redirect
  - HTTP POST /offers/{token}/decline → 303 + reason kaydedilir
  - Admin POST /admin/revenue/institutions/{id}/offers/create → 303
  - Admin POST .../offers/{id}/send → 303 + status SENT
  - Admin POST .../offers/{id}/cancel → 303 + status CANCELLED
  - Audit log: tüm admin müdahaleleri kayıt altında
  - Kurum 360 GET ?tab=offers → 200 + offer listesi render
"""

from __future__ import annotations

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
    Institution,
    Offer,
    OfferKind,
    OfferStatus,
    PlanChangeHistory,
    User,
    UserRole,
)
from app.services.offers import (
    accept_offer,
    cancel_offer,
    create_offer,
    decline_offer,
    describe_offer,
    expire_old_offers,
    get_offer_by_token,
    send_offer,
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
    print("=== Sprint D.1 — Bireysel Teklif Sistemi smoke ===")
    tag = f"sprintd1-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        inst = db.query(Institution).filter(Institution.is_active.is_(True)).first()
        if not sa or not inst:
            print("  (gerekli SA/kurum yok — atlandı)")
            return 0
        sa_id = sa.id
        inst_id = inst.id
        # Trial_ends_at başlangıç değerini kaydet (geri yüklemek için)
        orig_trial = inst.trial_ends_at
        orig_plan = inst.plan

    # Cleanup — geçmiş test verisi
    with SessionLocal() as db:
        db.query(Offer).filter(Offer.admin_note.like(f"{tag}%")).delete()
        db.commit()

    # ---- 1) create_offer: DRAFT ----
    with SessionLocal() as db:
        offer = create_offer(
            db, institution_id=inst_id,
            kind="discount_percent",
            title="3 ay %20 indirim test",
            by_user_id=sa_id,
            value=20.0, duration_months=3,
            admin_note=f"{tag} draft",
            public_message="Size özel teklif.",
            expires_in_days=14,
        )
        check("create_offer: nesne döner", offer is not None)
        if offer is not None:
            check("create_offer: status=DRAFT", offer.status == OfferStatus.DRAFT)
            check("create_offer: token oluştu", len(offer.token) > 20)
            check("create_offer: expires_at ileri tarih",
                  offer.expires_at is not None
                  and offer.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc))
            offer_id_1 = offer.id

    # ---- 2) Geçersiz kind → None ----
    with SessionLocal() as db:
        bad = create_offer(
            db, institution_id=inst_id,
            kind="invalid_kind", title="x", by_user_id=sa_id,
        )
        check("create_offer: geçersiz kind → None", bad is None)

    # ---- 3) send_offer: DRAFT → SENT ----
    with SessionLocal() as db:
        r = send_offer(db, offer_id=offer_id_1)
        check("send_offer: ok=True", r.get("ok"), str(r))
        row = db.get(Offer, offer_id_1)
        check("send_offer: status=SENT", row.status == OfferStatus.SENT)
        check("send_offer: sent_at set", row.sent_at is not None)
        token_1 = row.token

    # ---- 4) send_offer: zaten SENT olan tekrar gönderilemez ----
    with SessionLocal() as db:
        r = send_offer(db, offer_id=offer_id_1)
        check("send_offer: zaten SENT → not_draft",
              not r.get("ok") and r.get("error") == "not_draft", str(r))

    # ---- 5) get_offer_by_token ----
    with SessionLocal() as db:
        o = get_offer_by_token(db, token=token_1)
        check("get_offer_by_token: bulundu", o is not None and o.id == offer_id_1)
        o_none = get_offer_by_token(db, token="invalid_token_xxx")
        check("get_offer_by_token: yok → None", o_none is None)

    # ---- 6) describe_offer ----
    with SessionLocal() as db:
        o = db.get(Offer, offer_id_1)
        desc = describe_offer(o)
        check("describe_offer: summary üretir",
              desc["summary"] and "%20" in desc["summary"], str(desc))

    # ---- 7) decline_offer (public token) ----
    with SessionLocal() as db:
        offer2 = create_offer(
            db, institution_id=inst_id,
            kind="discount_fixed", title="500 ₺ indirim test",
            by_user_id=sa_id, value=500.0,
            admin_note=f"{tag} declined",
            expires_in_days=14,
        )
        send_offer(db, offer_id=offer2.id)
        token_2 = offer2.token

    with SessionLocal() as db:
        r = decline_offer(db, token=token_2, reason="Bütçe yok şu an")
        check("decline_offer: ok=True", r.get("ok"), str(r))
        row = db.query(Offer).filter(Offer.token == token_2).first()
        check("decline_offer: status=DECLINED", row.status == OfferStatus.DECLINED)
        check("decline_offer: decline_reason kaydedildi",
              row.decline_reason and "Bütçe" in row.decline_reason)
        check("decline_offer: responded_at set", row.responded_at is not None)

    # ---- 8) accept_offer (PLAN_UPGRADE) → plan değişir + PlanChangeHistory ----
    new_plan_code = "kurumsal_max_test"
    with SessionLocal() as db:
        offer3 = create_offer(
            db, institution_id=inst_id,
            kind="plan_upgrade", title="Pakete yükselt test",
            by_user_id=sa_id, new_plan=new_plan_code,
            duration_months=3,
            admin_note=f"{tag} upgrade",
        )
        send_offer(db, offer_id=offer3.id)
        token_3 = offer3.token
        offer3_id = offer3.id

    with SessionLocal() as db:
        r = accept_offer(db, token=token_3, by_user_id=None)
        check("accept_offer (plan_upgrade): ok=True", r.get("ok"), str(r))
        check("accept_offer: plan_change_history_id var",
              r.get("plan_change_history_id") is not None)

    with SessionLocal() as db:
        row = db.get(Offer, offer3_id)
        check("accept_offer: status=ACCEPTED", row.status == OfferStatus.ACCEPTED)
        check("accept_offer: responded_at set", row.responded_at is not None)
        inst_now = db.get(Institution, inst_id)
        check("accept_offer (plan_upgrade): institution.plan değişti",
              inst_now.plan == new_plan_code,
              f"got plan={inst_now.plan}")
        # PlanChangeHistory yazıldı mı
        pch = db.query(PlanChangeHistory).filter(
            PlanChangeHistory.id == row.plan_change_history_id,
        ).first()
        check("accept_offer: PlanChangeHistory yazıldı", pch is not None)
        if pch:
            check("PCH: to_plan = new plan", pch.to_plan == new_plan_code,
                  f"got to={pch.to_plan}")

    # Plan'ı geri al
    with SessionLocal() as db:
        inst_now = db.get(Institution, inst_id)
        inst_now.plan = orig_plan
        db.commit()

    # ---- 9) accept_offer (TRIAL_EXTENSION) → trial_ends_at uzar ----
    with SessionLocal() as db:
        # Kuruma bilinen bir trial_ends_at koy
        inst_now = db.get(Institution, inst_id)
        base_te = datetime.now(timezone.utc) + timedelta(days=5)
        inst_now.trial_ends_at = base_te
        db.commit()

        offer4 = create_offer(
            db, institution_id=inst_id,
            kind="trial_extension", title="30 gün deneme uzatma test",
            by_user_id=sa_id, value=30.0,
            admin_note=f"{tag} trialext",
        )
        send_offer(db, offer_id=offer4.id)
        token_4 = offer4.token
        offer4_id = offer4.id

    with SessionLocal() as db:
        r = accept_offer(db, token=token_4, by_user_id=None)
        check("accept_offer (trial_extension): ok=True", r.get("ok"), str(r))
        inst_now = db.get(Institution, inst_id)
        # trial 30 gün uzamış olmalı (orig + 30, yaklaşık)
        new_te = inst_now.trial_ends_at
        if new_te.tzinfo is None:
            new_te = new_te.replace(tzinfo=timezone.utc)
        expected = base_te + timedelta(days=30)
        delta = abs((new_te - expected).total_seconds())
        check("accept_offer (trial_extension): trial_ends_at +30 gün",
              delta < 10, f"got te={new_te}, expected~={expected}")

    # Trial'ı geri al
    with SessionLocal() as db:
        inst_now = db.get(Institution, inst_id)
        inst_now.trial_ends_at = orig_trial
        db.commit()

    # ---- 10) cancel_offer ----
    with SessionLocal() as db:
        offer5 = create_offer(
            db, institution_id=inst_id,
            kind="custom", title="özel test",
            by_user_id=sa_id,
            admin_note=f"{tag} cancel",
        )
        offer5_id = offer5.id

    with SessionLocal() as db:
        r = cancel_offer(db, offer_id=offer5_id)
        check("cancel_offer (draft): ok=True", r.get("ok"), str(r))
        row = db.get(Offer, offer5_id)
        check("cancel_offer: status=CANCELLED",
              row.status == OfferStatus.CANCELLED)

    # ---- 11) cancel_offer: zaten kapalı olan iptal edilmez ----
    with SessionLocal() as db:
        r = cancel_offer(db, offer_id=offer5_id)
        check("cancel_offer: tekrar → already_closed",
              not r.get("ok") and r.get("error") == "already_closed", str(r))

    # ---- 12) accept_offer: hatalı status ----
    with SessionLocal() as db:
        # offer1 (declined token_2'nin offer'ı, ACCEPTED'a değil declined)
        # offer3 zaten accepted
        r = accept_offer(db, token=token_3)
        check("accept_offer: zaten ACCEPTED → not_open",
              not r.get("ok") and r.get("error") == "not_open", str(r))

    # ---- 13) accept_offer: yanlış token ----
    with SessionLocal() as db:
        r = accept_offer(db, token="nonexistent_xxx")
        check("accept_offer: bilinmeyen token → not_found",
              not r.get("ok") and r.get("error") == "not_found", str(r))

    # ---- 14) expire_old_offers: süresi geçmiş SENT → EXPIRED ----
    with SessionLocal() as db:
        offer6 = create_offer(
            db, institution_id=inst_id,
            kind="custom", title="expire test",
            by_user_id=sa_id,
            admin_note=f"{tag} expire",
            expires_in_days=None,
        )
        send_offer(db, offer_id=offer6.id)
        # Manuel olarak expires_at'i geçmişe çek
        offer6_id = offer6.id
        offer6.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

    with SessionLocal() as db:
        r = expire_old_offers(db)
        check("expire_old_offers: count >= 1",
              r.get("expired_count", 0) >= 1, str(r))
        row = db.get(Offer, offer6_id)
        check("expire_old_offers: status=EXPIRED",
              row.status == OfferStatus.EXPIRED)

    # ---- 15) HTTP: public GET /offers/{token} (login YOK) ----
    client = TestClient(app)
    # Kabul edilen offer3 hala token'lı, çekebiliriz
    res = client.get(f"/offers/{token_3}", follow_redirects=False)
    check("HTTP GET /offers/{token}: 200",
          res.status_code == 200, f"status={res.status_code}")
    if res.status_code == 200:
        body = res.text
        check("HTTP view: başlık render",
              "Pakete yükselt test" in body or "ACCEPTED" in body.upper()
              or "Kabul edildi" in body)

    # ---- 16) HTTP: public GET bilinmeyen token → 404 ----
    res = client.get("/offers/nonexistent_xxx_token", follow_redirects=False)
    check("HTTP GET /offers/{bad_token}: 404",
          res.status_code == 404, f"status={res.status_code}")

    # ---- 17) HTTP: public POST accept → 303 ----
    with SessionLocal() as db:
        offer7 = create_offer(
            db, institution_id=inst_id,
            kind="free_feature", title="HTTP accept test",
            by_user_id=sa_id, duration_months=2,
            admin_note=f"{tag} httpaccept",
        )
        send_offer(db, offer_id=offer7.id)
        token_7 = offer7.token
        offer7_id = offer7.id

    res = client.post(f"/offers/{token_7}/accept", follow_redirects=False)
    check("HTTP POST /offers/{token}/accept: 303",
          res.status_code == 303, f"status={res.status_code}")
    if res.status_code == 303:
        check("HTTP accept: redirect ?accepted=1",
              "accepted=1" in res.headers.get("location", ""))

    with SessionLocal() as db:
        row = db.get(Offer, offer7_id)
        check("HTTP accept: DB status=ACCEPTED",
              row.status == OfferStatus.ACCEPTED)

    # ---- 18) HTTP: public POST decline (form ile reason) ----
    with SessionLocal() as db:
        offer8 = create_offer(
            db, institution_id=inst_id,
            kind="onboarding_hours", title="HTTP decline test",
            by_user_id=sa_id, value=5.0,
            admin_note=f"{tag} httpdecline",
        )
        send_offer(db, offer_id=offer8.id)
        token_8 = offer8.token
        offer8_id = offer8.id

    res = client.post(
        f"/offers/{token_8}/decline",
        data={"reason": "Şu an ihtiyaç yok"},
        follow_redirects=False,
    )
    check("HTTP POST /offers/{token}/decline: 303",
          res.status_code == 303, f"status={res.status_code}")
    if res.status_code == 303:
        check("HTTP decline: redirect ?declined=1",
              "declined=1" in res.headers.get("location", ""))

    with SessionLocal() as db:
        row = db.get(Offer, offer8_id)
        check("HTTP decline: DB status=DECLINED",
              row.status == OfferStatus.DECLINED)
        check("HTTP decline: reason kaydedildi",
              row.decline_reason and "ihtiyaç" in row.decline_reason)

    # ---- 19) Admin HTTP: super_admin override ile create + send + cancel ----
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()

    def _admin():
        return admin

    app.dependency_overrides[require_super_admin] = _admin
    app.dependency_overrides[require_user] = _admin
    app.dependency_overrides[get_current_user] = _admin

    try:
        # Admin: create + send_now
        res = client.post(
            f"/admin/revenue/institutions/{inst_id}/offers/create",
            data={
                "kind": "discount_percent",
                "title": f"{tag} admin create",
                "value": "15",
                "duration_months": "2",
                "public_message": "Admin yarattı",
                "admin_note": f"{tag} adminhttp",
                "expires_in_days": "10",
                "send_now": "1",
            },
            follow_redirects=False,
        )
        check("Admin POST /offers/create: 303",
              res.status_code == 303, f"status={res.status_code}")

        with SessionLocal() as db:
            new_offer = db.query(Offer).filter(
                Offer.admin_note == f"{tag} adminhttp",
            ).order_by(Offer.id.desc()).first()
            check("Admin create: DB'de yaratıldı", new_offer is not None)
            if new_offer:
                check("Admin create + send_now: status=SENT",
                      new_offer.status == OfferStatus.SENT)
                new_offer_id = new_offer.id

        # Admin: cancel
        res = client.post(
            f"/admin/revenue/institutions/{inst_id}/offers/{new_offer_id}/cancel",
            follow_redirects=False,
        )
        check("Admin POST /offers/{id}/cancel: 303",
              res.status_code == 303, f"status={res.status_code}")

        with SessionLocal() as db:
            row = db.get(Offer, new_offer_id)
            check("Admin cancel: status=CANCELLED",
                  row.status == OfferStatus.CANCELLED)

        # Admin: create (draft only, send_now boş)
        res = client.post(
            f"/admin/revenue/institutions/{inst_id}/offers/create",
            data={
                "kind": "custom",
                "title": f"{tag} draft only",
                "admin_note": f"{tag} adminhttp_draft",
                "expires_in_days": "14",
            },
            follow_redirects=False,
        )
        check("Admin POST /offers/create (draft only): 303",
              res.status_code == 303)
        with SessionLocal() as db:
            row = db.query(Offer).filter(
                Offer.admin_note == f"{tag} adminhttp_draft",
            ).first()
            check("Admin create draft: status=DRAFT",
                  row is not None and row.status == OfferStatus.DRAFT)
            draft_id = row.id if row else None

        # Admin: send_offer endpoint
        if draft_id:
            res = client.post(
                f"/admin/revenue/institutions/{inst_id}/offers/{draft_id}/send",
                follow_redirects=False,
            )
            check("Admin POST /offers/{id}/send: 303",
                  res.status_code == 303, f"status={res.status_code}")
            with SessionLocal() as db:
                row = db.get(Offer, draft_id)
                check("Admin send: status=SENT",
                      row.status == OfferStatus.SENT)

        # Admin: Kurum 360 ?tab=offers → 200 + offer listesi
        res = client.get(
            f"/admin/revenue/institutions/{inst_id}?tab=offers",
            follow_redirects=False,
        )
        check("Admin GET /revenue/institutions/{id}?tab=offers: 200",
              res.status_code == 200, f"status={res.status_code}")
        if res.status_code == 200:
            check("Admin Kurum 360 offers: 'Teklifler' başlığı render",
                  "Teklif" in res.text)
            check("Admin Kurum 360 offers: form var",
                  "/offers/create" in res.text)

        # Audit log: en az 3 yeni offer kayıt (create, send, cancel)
        import json
        with SessionLocal() as db:
            recent_audits = db.query(AuditLog).filter(
                AuditLog.target_type == "offer",
                AuditLog.actor_id == sa_id,
            ).order_by(AuditLog.id.desc()).limit(20).all()
            check("Audit log: offer target için kayıt mevcut",
                  len(recent_audits) >= 3,
                  f"got {len(recent_audits)} audits")
            actions = set()
            for a in recent_audits:
                if a.details_json:
                    try:
                        d = json.loads(a.details_json)
                        if isinstance(d, dict) and d.get("action"):
                            actions.add(d["action"])
                    except (ValueError, TypeError):
                        pass
            check("Audit log: 'create' aksiyon kayıtlı",
                  "create" in actions, f"actions={actions}")
            check("Audit log: 'send' aksiyon kayıtlı",
                  "send" in actions, f"actions={actions}")
            check("Audit log: 'cancel' aksiyon kayıtlı",
                  "cancel" in actions, f"actions={actions}")

    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        db.query(Offer).filter(Offer.admin_note.like(f"{tag}%")).delete()
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
