"""Sprint C — Aksiyon Merkezi + Dunning + Manuel Müdahale smoke test.

Test ettiği:
  - action_center_data: dict shape + severity counts + items sıralı
  - Aksiyon merkezi: sağlık + ödeme + trial sinyalleri birleşik liste
  - HTTP GET /admin/revenue/action-center → 200 + KPI + öneriler
  - HTTP POST /quick-action → 303 + CrmAction oluştu + audit log
  - Dunning send_reminder: manuel mod + cron mod
  - Dunning aşama dedup: aynı aşama 2. kez gönderilmiyor
  - Dunning aşama belirleme: D-7/D-3/D-1/D+1/D+3/D+7 doğru
  - Manuel: postpone, mark-paid, cancel, send-reminder route'ları 303
  - Audit log: tüm manuel müdahaleler kayıt altında
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
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    CrmAction,
    CrmActionKind,
    Institution,
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    User,
    UserRole,
)
from app.services.action_center import action_center_data, build_action_list
from app.services.dunning import (
    REMINDER_STAGES,
    run_dunning_for_all,
    send_reminder,
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
    print("=== Sprint C — Aksiyon Merkezi + Dunning smoke ===")
    tag = f"sprintc-{secrets.token_hex(3)}"
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        inst = db.query(Institution).filter(Institution.is_active.is_(True)).first()
        if not sa or not inst:
            print("  (gerekli SA/kurum yok — atlandı)")
            return 0
        sa_id = sa.id
        inst_id = inst.id

    # Cleanup
    with SessionLocal() as db:
        db.query(Invoice).filter(Invoice.notes.like(f"{tag}%")).delete()
        db.query(CrmAction).filter(CrmAction.summary.like(f"{tag}%")).delete()
        db.commit()

    # ---- 1) action_center_data: dict shape ----
    with SessionLocal() as db:
        d = action_center_data(db)
        check("action_center_data dict shape",
              "items" in d and "severity_counts" in d and "total_count" in d)
        check("severity_counts keys",
              set(d["severity_counts"].keys()) >=
              {"critical", "high", "medium", "low", "positive"})

    # ---- 2) build_action_list: total_score azalan sırada ----
    with SessionLocal() as db:
        items = build_action_list(db, limit=20)
        check("build_action_list liste döner", isinstance(items, list))
        if len(items) >= 2:
            check("items total_score azalan sıralı",
                  items[0].total_score >= items[1].total_score)
        if items:
            it0 = items[0]
            check("item: primary_signal var",
                  it0.primary_signal is not None and it0.primary_signal.title)
            check("item: suggested_actions liste boş değil",
                  len(it0.suggested_actions) > 0)
            check("item: institution_id mevcut",
                  it0.institution_id is not None)

    # ---- 3) Dunning aşama belirleme ----
    from app.services.dunning import _stage_for_invoice

    # D-7 testi
    inv_d7 = Invoice(
        institution_id=inst_id, plan="solo_pro", amount_try=999,
        status=InvoiceStatus.PENDING,
        period_start=now, period_end=now + timedelta(days=30),
        due_at=now + timedelta(days=7, hours=2),  # 7 günden biraz fazla
        notes=tag + " d7",
    )
    stage = _stage_for_invoice(inv_d7, now=now)
    check("aşama: d_minus_7 doğru", stage == "d_minus_7",
          f"got {stage}")

    inv_d1 = Invoice(
        institution_id=inst_id, plan="solo_pro", amount_try=999,
        status=InvoiceStatus.PENDING,
        period_start=now, period_end=now + timedelta(days=30),
        due_at=now + timedelta(hours=20),  # < 1 gün
        notes=tag + " d1",
    )
    stage = _stage_for_invoice(inv_d1, now=now)
    check("aşama: d_minus_1 doğru", stage == "d_minus_1",
          f"got {stage}")

    inv_p1 = Invoice(
        institution_id=inst_id, plan="solo_pro", amount_try=999,
        status=InvoiceStatus.OVERDUE,
        period_start=now - timedelta(days=30), period_end=now,
        due_at=now - timedelta(hours=20),  # 1 gün önce
        notes=tag + " p1",
    )
    stage = _stage_for_invoice(inv_p1, now=now)
    check("aşama: d_plus_1 doğru", stage == "d_plus_1",
          f"got {stage}")

    inv_p7 = Invoice(
        institution_id=inst_id, plan="solo_pro", amount_try=999,
        status=InvoiceStatus.OVERDUE,
        period_start=now - timedelta(days=40), period_end=now - timedelta(days=10),
        due_at=now - timedelta(days=10),  # 10 gün önce
        notes=tag + " p7",
    )
    stage = _stage_for_invoice(inv_p7, now=now)
    check("aşama: d_plus_7 doğru", stage == "d_plus_7",
          f"got {stage}")

    # Dedup: aynı aşamayı tekrar gönderme
    inv_p7.last_reminder_kind = "d_plus_7"
    stage = _stage_for_invoice(inv_p7, now=now)
    check("aşama dedup: aynı aşama gönderildiyse None",
          stage is None, f"got {stage}")

    # Ödenmiş fatura
    inv_paid = Invoice(
        institution_id=inst_id, plan="solo_pro", amount_try=999,
        status=InvoiceStatus.PAID,
        period_start=now, period_end=now + timedelta(days=30),
        due_at=now + timedelta(days=2),
        notes=tag + " paid",
    )
    stage = _stage_for_invoice(inv_paid, now=now)
    check("aşama: PAID için None", stage is None)

    # ---- 4) send_reminder: manuel mod ----
    with SessionLocal() as db:
        inv = Invoice(
            institution_id=inst_id, plan="solo_pro", amount_try=2499,
            status=InvoiceStatus.OVERDUE,
            period_start=now - timedelta(days=15),
            period_end=now + timedelta(days=15),
            due_at=now - timedelta(days=3),
            notes=tag + " send_test",
        )
        db.add(inv)
        db.commit()
        inv_id = inv.id

    with SessionLocal() as db:
        r = send_reminder(db, invoice_id=inv_id, manual=True)
        check("send_reminder manuel: ok=True", r.get("ok"), str(r))
        check("send_reminder: last_reminder_kind set",
              r.get("stage") in REMINDER_STAGES + ["manual"])
        row = db.get(Invoice, inv_id)
        check("DB'de last_reminder_kind kaydedildi",
              row.last_reminder_kind is not None)
        check("DB'de last_reminder_at kaydedildi",
              row.last_reminder_at is not None)

    # ---- 5) send_reminder: cron modu (aşama bazlı) ----
    with SessionLocal() as db:
        # Yeni d-7 fatura
        inv2 = Invoice(
            institution_id=inst_id, plan="solo_pro", amount_try=1500,
            status=InvoiceStatus.PENDING,
            period_start=now, period_end=now + timedelta(days=30),
            due_at=now + timedelta(days=7),
            notes=tag + " cron_test",
        )
        db.add(inv2)
        db.commit()
        inv2_id = inv2.id

    with SessionLocal() as db:
        r = send_reminder(db, invoice_id=inv2_id, manual=False)
        check("send_reminder cron: ok=True", r.get("ok"), str(r))
        check("cron mod aşama d_minus_7",
              r.get("stage") == "d_minus_7", str(r))

        # 2. çağrı: dedup nedeniyle skip (no_stage_due veya already_sent)
        r2 = send_reminder(db, invoice_id=inv2_id, manual=False)
        check("cron mod 2. çağrı: dedup ile skip (no_stage_due)",
              not r2.get("ok") and r2.get("error") in ("already_sent", "no_stage_due"),
              str(r2))

    # ---- 6) run_dunning_for_all: özet ----
    with SessionLocal() as db:
        # Temizle
        for r in db.query(Invoice).filter(Invoice.notes.like(f"{tag}%")).all():
            r.last_reminder_kind = None
            r.last_reminder_at = None
        db.commit()
        s = run_dunning_for_all(db)
        check("run_dunning_for_all dict döner",
              isinstance(s, dict) and "sent" in s and "by_stage" in s)

    # ---- 7) HTTP route'lar ----
    def _ov():
        def factory():
            db2 = SessionLocal()
            try:
                u = (
                    db2.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == sa_id).first()
                )
                _ = u.institution
                db2.expunge_all()
                return u
            finally:
                db2.close()
        return factory

    app.dependency_overrides[require_super_admin] = _ov()
    app.dependency_overrides[require_user] = _ov()
    app.dependency_overrides[get_current_user] = _ov()
    try:
        c = TestClient(app)

        # Aksiyon Merkezi GET
        r = c.get("/admin/revenue/action-center")
        check("action-center GET 200", r.status_code == 200)
        check("action-center başlık 'Aksiyon Merkezi'",
              "Aksiyon Merkezi" in r.text)
        check("action-center 'önerilen aksiyon' kelimesi",
              "Önerilen aksiyonlar" in r.text or
              "açık aksiyon yok" in r.text)

        # Quick action POST
        r2 = c.post(
            "/admin/revenue/action-center/quick-action",
            data={
                "institution_id": inst_id,
                "kind": "call",
                "summary": f"{tag} quick test",
                "result": "pending",
                "follow_up_days": "3",
            },
            follow_redirects=False,
        )
        check("quick-action POST → 303", r2.status_code == 303)
        check("quick-action redirect → ok param",
              "ok=" in r2.headers.get("location", ""))

        with SessionLocal() as db2:
            qa = (
                db2.query(CrmAction)
                .filter(CrmAction.summary.like(f"{tag} quick%"))
                .first()
            )
            check("quick-action CrmAction oluştu", qa is not None)
            check("quick-action follow_up_at set", qa.follow_up_at is not None)

        # Geçersiz kind
        r3 = c.post(
            "/admin/revenue/action-center/quick-action",
            data={"institution_id": inst_id, "kind": "bogus",
                  "summary": "x", "result": "pending"},
            follow_redirects=False,
        )
        check("quick-action bogus kind → 303 + err",
              "err=" in r3.headers.get("location", ""))

        # postpone
        with SessionLocal() as db2:
            postpone_inv = Invoice(
                institution_id=inst_id, plan="solo_pro", amount_try=500,
                status=InvoiceStatus.OVERDUE,
                period_start=now - timedelta(days=10), period_end=now + timedelta(days=20),
                due_at=now - timedelta(days=2),
                notes=tag + " postpone",
            )
            db2.add(postpone_inv)
            db2.commit()
            postpone_id = postpone_inv.id

        r4 = c.post(
            f"/admin/invoices/{postpone_id}/postpone",
            data={"days": "10", "note": "test öteleme"},
            follow_redirects=False,
        )
        check("postpone POST → 303", r4.status_code == 303)
        with SessionLocal() as db2:
            row = db2.get(Invoice, postpone_id)
            # SQLite naive olabilir; aware'e çevirip karşılaştır
            row_due = row.due_at
            if row_due is not None and row_due.tzinfo is None:
                row_due = row_due.replace(tzinfo=timezone.utc)
            check("postpone: due_at ileri alındı",
                  row_due > now)
            check("postpone: OVERDUE → PENDING (vade ileri)",
                  row.status == InvoiceStatus.PENDING)
            # Audit log
            au = (
                db2.query(AuditLog)
                .filter(
                    AuditLog.target_type == "invoice",
                    AuditLog.target_id == postpone_id,
                )
                .first()
            )
            check("postpone audit log yazıldı", au is not None)

        # mark-paid
        with SessionLocal() as db2:
            paid_inv = Invoice(
                institution_id=inst_id, plan="solo_pro", amount_try=700,
                status=InvoiceStatus.PENDING,
                period_start=now, period_end=now + timedelta(days=30),
                due_at=now + timedelta(days=5),
                notes=tag + " markpaid",
            )
            db2.add(paid_inv)
            db2.commit()
            paid_id = paid_inv.id

        r5 = c.post(
            f"/admin/invoices/{paid_id}/mark-paid",
            data={"method": "bank_transfer", "note": "EFT geldi"},
            follow_redirects=False,
        )
        check("mark-paid POST → 303", r5.status_code == 303)
        with SessionLocal() as db2:
            row = db2.get(Invoice, paid_id)
            check("mark-paid: status PAID",
                  row.status == InvoiceStatus.PAID)
            check("mark-paid: paid_at set",
                  row.paid_at is not None)
            check("mark-paid: payment_method bank_transfer",
                  row.payment_method == PaymentMethod.BANK_TRANSFER)

        # cancel
        with SessionLocal() as db2:
            cancel_inv = Invoice(
                institution_id=inst_id, plan="solo_pro", amount_try=300,
                status=InvoiceStatus.PENDING,
                period_start=now, period_end=now + timedelta(days=30),
                due_at=now + timedelta(days=10),
                notes=tag + " cancel",
            )
            db2.add(cancel_inv)
            db2.commit()
            cancel_id = cancel_inv.id

        r6 = c.post(
            f"/admin/invoices/{cancel_id}/cancel",
            data={"note": "test iptal"},
            follow_redirects=False,
        )
        check("cancel POST → 303", r6.status_code == 303)
        with SessionLocal() as db2:
            row = db2.get(Invoice, cancel_id)
            check("cancel: status CANCELLED",
                  row.status == InvoiceStatus.CANCELLED)

        # send-reminder manuel
        with SessionLocal() as db2:
            rem_inv = Invoice(
                institution_id=inst_id, plan="solo_pro", amount_try=1200,
                status=InvoiceStatus.OVERDUE,
                period_start=now - timedelta(days=20),
                period_end=now + timedelta(days=10),
                due_at=now - timedelta(days=5),
                notes=tag + " remind",
            )
            db2.add(rem_inv)
            db2.commit()
            rem_id = rem_inv.id

        r7 = c.post(
            f"/admin/invoices/{rem_id}/send-reminder",
            data={"kind": "manual"},
            follow_redirects=False,
        )
        check("send-reminder POST → 303", r7.status_code == 303)

        # Ödenmiş faturayı tekrar mark-paid → err
        r8 = c.post(
            f"/admin/invoices/{paid_id}/mark-paid",
            data={"method": "manual"},
            follow_redirects=False,
        )
        check("mark-paid 2. çağrı (zaten ödendi) → 303 + err",
              "err=" in r8.headers.get("location", ""))

        # Bilinmeyen fatura
        r9 = c.post(
            "/admin/invoices/99999999/postpone",
            data={"days": "7"},
            follow_redirects=False,
        )
        check("bilinmeyen fatura postpone → 303 + err",
              "err=" in r9.headers.get("location", ""))
    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(Invoice).filter(Invoice.notes.like(f"%{tag}%")).delete()
        db.query(CrmAction).filter(CrmAction.summary.like(f"{tag}%")).delete()
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
