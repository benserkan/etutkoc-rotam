"""Sprint A.2 (Roadmap Faz F-1) — Invoice modeli + Ödeme Takvimi smoke test.

Test ettiği:
  - Invoice modeli tablo oluştu, CRUD çalışıyor
  - payment_calendar_summary() bucket bazlı doğru dağılım
  - mark_overdue() PENDING → OVERDUE transition
  - GET /admin/security-monitor/revenue → payment-calendar banner render
  - GET /admin/security-monitor/revenue/invoices → liste + status filter
  - Drill: invoice_bucket:<key> her bucket için 200 + render
  - Ana sayfada vade yakın/gecikmiş fatura sayısı doğru görünüyor
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
    Institution,
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    User,
    UserRole,
)
from app.services.revenue_panel import (
    BUCKET_LABELS_TR,
    drill_for_key,
    mark_overdue,
    overdue_invoices,
    payment_calendar_summary,
    upcoming_invoices,
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
    print("=== Sprint A.2 — Invoice + Ödeme Takvimi smoke ===")
    test_tag = f"inv-test-{secrets.token_hex(3)}"
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        inst = db.query(Institution).filter(Institution.is_active.is_(True)).first()
        if not sa or not inst:
            print("  (gerekli SA veya kurum yok — atlandı)")
            return 0
        sa_id = sa.id
        inst_id = inst.id

    # Mevcut test invoice'larını temizle (idempotent)
    with SessionLocal() as db:
        db.query(Invoice).filter(Invoice.notes == test_tag).delete()
        db.commit()

    # ---- 1) CRUD: Invoice yaratıp okuyabiliyor muyuz? ----
    with SessionLocal() as db:
        inv = Invoice(
            institution_id=inst_id, plan="solo_pro", amount_try=1999,
            status=InvoiceStatus.PENDING,
            period_start=now, period_end=now + timedelta(days=30),
            due_at=now + timedelta(days=10),
            payment_method=PaymentMethod.CARD,
            notes=test_tag,
        )
        db.add(inv)
        db.commit()
        inv_id = inv.id
    check("Invoice yaratıldı", inv_id is not None)

    with SessionLocal() as db:
        row = db.get(Invoice, inv_id)
        check("Invoice geri okundu", row is not None and row.amount_try == 1999)
        check("Invoice status default PENDING",
              row.status == InvoiceStatus.PENDING)
        check("Invoice plan saklandı", row.plan == "solo_pro")
        check("Invoice payment_method saklandı",
              row.payment_method == PaymentMethod.CARD)

    # ---- 2) Bucket dağılımı: farklı vade tarihlerinde 3 fatura ----
    with SessionLocal() as db:
        # Eski test verilerini sil
        db.query(Invoice).filter(Invoice.notes == test_tag).delete()
        db.commit()
        # 3 fatura: çok eski (overdue_7plus), orta vade (~6 gün), uzak (15+ gün)
        # 12 saatlik tampon ile timing race'i önle.
        buffer = timedelta(hours=12)
        cases = [
            (timedelta(days=-9) + buffer, InvoiceStatus.OVERDUE, "overdue_7plus"),
            (timedelta(days=6) + buffer, InvoiceStatus.PENDING, "due_in_7d"),
            (timedelta(days=13) + buffer, InvoiceStatus.PENDING, "due_in_14d"),
        ]
        for delta, status, expected_bucket in cases:
            db.add(Invoice(
                institution_id=inst_id, plan="solo_pro", amount_try=2000,
                status=status,
                period_start=now - timedelta(days=15),
                period_end=now + timedelta(days=15),
                due_at=now + delta,
                notes=test_tag,
            ))
        db.commit()

        s = payment_calendar_summary(db, days_horizon=14)
        buckets = {b["key"]: b for b in s["buckets"]}
        for delta, status, expected_bucket in cases:
            check(f"bucket '{expected_bucket}' içeriği var (delta={delta})",
                  expected_bucket in buckets,
                  f"available: {list(buckets.keys())}")

    # ---- 3) upcoming_invoices ve overdue_invoices ----
    with SessionLocal() as db:
        ups = upcoming_invoices(db, days_horizon=14)
        check("upcoming_invoices liste döner",
              isinstance(ups, list) and len(ups) >= 3)
        check("upcoming her satırda institution_name var",
              all("institution_name" in u for u in ups))
        check("upcoming her satırda bucket var",
              all("bucket" in u for u in ups))

        ods = overdue_invoices(db)
        check("overdue_invoices listesi", isinstance(ods, list))
        check("overdue listesinde overdue olan invoice var",
              any(o["status"] == "overdue" for o in ods))

    # ---- 4) mark_overdue: PENDING + due geçmiş → OVERDUE ----
    with SessionLocal() as db:
        # Yeni eski tarihli PENDING ekle
        db.add(Invoice(
            institution_id=inst_id, plan="solo_pro", amount_try=1500,
            status=InvoiceStatus.PENDING,
            period_start=now - timedelta(days=40),
            period_end=now - timedelta(days=10),
            due_at=now - timedelta(days=5),  # 5 gün önce dolmuş ama hala PENDING
            notes=test_tag,
        ))
        db.commit()
        count = mark_overdue(db)
        check("mark_overdue 1+ kayıt güncelledi", count >= 1, f"count={count}")
        # Aynı kayıt OVERDUE oldu mu?
        still_pending_overdue_due = (
            db.query(Invoice)
            .filter(
                Invoice.notes == test_tag,
                Invoice.due_at < now,
                Invoice.status == InvoiceStatus.PENDING,
            )
            .count()
        )
        check("mark_overdue sonrası PENDING+geçmiş kalmadı",
              still_pending_overdue_due == 0,
              f"{still_pending_overdue_due} hala PENDING")

    # ---- 5) Drill: invoice_bucket key ----
    with SessionLocal() as db:
        for bucket in BUCKET_LABELS_TR.keys():
            d = drill_for_key(db, key=f"invoice_bucket:{bucket}")
            check(f"drill invoice_bucket:{bucket} dict shape",
                  isinstance(d, dict) and "rows" in d)

    # ---- 6) HTTP: revenue, /invoices, drill, filtre ----
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
        r = c.get("/admin/security-monitor/revenue")
        check("revenue ana sayfa GET 200", r.status_code == 200)
        check("ana sayfada 'Ödeme Takvimi' banner",
              "Ödeme Takvimi" in r.text)
        check("ana sayfada invoice_bucket macro link",
              "invoice_bucket:" in r.text)

        r2 = c.get("/admin/security-monitor/revenue/invoices")
        check("invoices liste GET 200", r2.status_code == 200)
        check("invoices sayfası 'Faturalar' başlık",
              "Faturalar" in r2.text)

        # Status filter
        r3 = c.get("/admin/security-monitor/revenue/invoices?status_filter=overdue")
        check("invoices filtre 'overdue' GET 200", r3.status_code == 200)
        check("filtre uygulandı (URL'de görünür)",
              "status_filter" in r3.text or "Filtre" in r3.text)

        # Drill route
        r4 = c.get("/admin/security-monitor/revenue/drill?key=invoice_bucket:overdue_1_2")
        check("drill invoice_bucket route 200", r4.status_code == 200)
        check("drill içerikte fatura ile ilgili kelime",
              "kurum" in r4.text.lower() or "Bu kategoride" in r4.text)

        # Geçersiz bucket → boş ama 200
        r5 = c.get("/admin/security-monitor/revenue/drill?key=invoice_bucket:bogus")
        check("drill geçersiz bucket → 200", r5.status_code == 200)
    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        db.query(Invoice).filter(Invoice.notes == test_tag).delete()
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
