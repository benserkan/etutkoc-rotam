"""Hesap hareketleri + 3 yıl penceresi + arşivleme — smoke test.

Test ettiği:
  - account_history() kurum için plan + fatura birleşik timeline döner
  - account_history() kullanıcı için plan döner (fatura yok)
  - Pencere filtresi: 3 yıldan eski kayıtlar olduğunda older_count artar
  - include_archived=False olduğunda arşivli kayıtlar gizli
  - archive_record() / unarchive_record() çalışıyor
  - bulk_archive_older_than() X yıldan eski TÜM kayıtları arşivler
  - HTTP: /institutions/{id}/account-history, /users/{id}/account-history → 200
  - HTTP: archive/unarchive/bulk-archive route'ları 303 redirect
  - Audit log: arşivleme aksiyonları kayıt altında
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
    Institution,
    Invoice,
    InvoiceStatus,
    PlanChangeHistory,
    PlanChangeReason,
    User,
    UserRole,
)
from app.models.plan_history import PlanOwnerType
from app.services.account_history import (
    DEFAULT_WINDOW_YEARS,
    account_history,
    archive_record,
    bulk_archive_older_than,
    unarchive_record,
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
    print("=== Hesap Hareketleri + Arşivleme smoke ===")
    tag = f"acthist-{secrets.token_hex(3)}"
    now = datetime.now(timezone.utc)
    long_ago = now - timedelta(days=365 * 4)  # 4 yıl önce (3 yıl penceresi dışında)

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        inst = db.query(Institution).filter(Institution.is_active.is_(True)).first()
        teacher = (
            db.query(User)
            .filter(User.role == UserRole.TEACHER, User.is_active.is_(True))
            .first()
        )
        if not all([sa, inst, teacher]):
            print("  (gerekli SA/kurum/teacher yok — atlandı)")
            return 0
        sa_id = sa.id
        inst_id = inst.id
        teacher_id = teacher.id

    # Temizle
    with SessionLocal() as db:
        db.query(PlanChangeHistory).filter(PlanChangeHistory.note.like(f"{tag}%")).delete()
        db.query(Invoice).filter(Invoice.notes.like(f"{tag}%")).delete()
        db.commit()

    # ---- 1) Setup: kurum için 2 yakın + 2 eski plan + 2 yakın + 2 eski fatura ----
    with SessionLocal() as db:
        # Kuruma yakın plan kayıtları (pencere içi)
        for i, reason in enumerate([PlanChangeReason.SIGNUP, PlanChangeReason.UPGRADE]):
            db.add(PlanChangeHistory(
                owner_type=PlanOwnerType.INSTITUTION, owner_id=inst_id,
                from_plan="free", to_plan="solo_pro" if i else "free",
                reason=reason, note=f"{tag} yakın #{i}",
                occurred_at=now - timedelta(days=10 * (i + 1)),
            ))
        # Eski (4 yıl önce)
        for i in range(2):
            db.add(PlanChangeHistory(
                owner_type=PlanOwnerType.INSTITUTION, owner_id=inst_id,
                from_plan="free", to_plan="free",
                reason=PlanChangeReason.SIGNUP,
                note=f"{tag} eski #{i}",
                occurred_at=long_ago - timedelta(days=i),
            ))
        # Kuruma faturalar
        for i in range(2):
            db.add(Invoice(
                institution_id=inst_id, plan="solo_pro", amount_try=1999,
                status=InvoiceStatus.PAID,
                period_start=now - timedelta(days=60 + 30*i),
                period_end=now - timedelta(days=30 + 30*i),
                due_at=now - timedelta(days=30 + 30*i),
                paid_at=now - timedelta(days=28 + 30*i),
                notes=f"{tag} yakın inv #{i}",
            ))
        for i in range(2):
            db.add(Invoice(
                institution_id=inst_id, plan="solo_pro", amount_try=999,
                status=InvoiceStatus.PAID,
                period_start=long_ago - timedelta(days=30),
                period_end=long_ago,
                due_at=long_ago - timedelta(days=i),
                paid_at=long_ago - timedelta(days=i - 1),
                notes=f"{tag} eski inv #{i}",
            ))
        # Öğretmene 1 yakın plan
        db.add(PlanChangeHistory(
            owner_type=PlanOwnerType.USER, owner_id=teacher_id,
            from_plan=None, to_plan="solo_trial",
            reason=PlanChangeReason.SIGNUP, note=f"{tag} teacher yakın",
            occurred_at=now - timedelta(days=5),
        ))
        db.commit()

    # ---- 2) Kurum timeline (varsayılan 3 yıl, arşiv kapalı) ----
    with SessionLocal() as db:
        d = account_history(db, owner_type="institution", owner_id=inst_id)
        check("kurum timeline: dict shape",
              "events" in d and "older_count" in d and "archived_count" in d)
        # En az 4 yakın olay (2 plan + 2 fatura) görünmeli
        own = [e for e in d["events"] if (
            (e.record_type == "plan" and tag in (e.detail.get("note") or ""))
            or (e.record_type == "invoice" and e.detail.get("amount_try") in (1999,))
        )]
        check("kurum timeline: yakın plan + faturalar görünüyor",
              len(own) >= 4, f"görünür own count={len(own)}")
        check("kurum timeline: older_count >= 4 (4 yıl önce 2 plan + 2 fatura)",
              d["older_count"] >= 4, f"older={d['older_count']}")
        check("kurum timeline: archived_count = 0 başta",
              d["archived_count"] == 0)
        # Olay sıralaması (azalan tarih)
        if len(d["events"]) >= 2:
            check("kurum timeline: azalan tarih sıralı",
                  d["events"][0].when >= d["events"][1].when)

    # ---- 3) Öğretmen timeline: sadece plan, fatura yok ----
    with SessionLocal() as db:
        d = account_history(db, owner_type="user", owner_id=teacher_id)
        check("öğretmen timeline: dict döner",
              "events" in d and isinstance(d["events"], list))
        teacher_planlar = [
            e for e in d["events"]
            if e.record_type == "plan"
            and tag in (e.detail.get("note") or "")
        ]
        check("öğretmen timeline: kendi plan kaydı var",
              len(teacher_planlar) >= 1)
        check("öğretmen timeline: fatura yok (sadece kurum)",
              all(e.record_type != "invoice" for e in d["events"]))

    # ---- 4) Tekil arşivle: bir plan kaydı arşive ekle ----
    with SessionLocal() as db:
        plan_row = (
            db.query(PlanChangeHistory)
            .filter(PlanChangeHistory.note.like(f"{tag} yakın #0%"))
            .first()
        )
        plan_id = plan_row.id

    with SessionLocal() as db:
        r = archive_record(
            db, record_type="plan", record_id=plan_id,
            by_user_id=sa_id, note="test arşiv",
        )
        check("archive_record: ok", r.get("ok"), str(r))

    with SessionLocal() as db:
        row = db.get(PlanChangeHistory, plan_id)
        check("archive_record: archived_at set", row.archived_at is not None)
        check("archive_record: archived_by_user_id set",
              row.archived_by_user_id == sa_id)
        check("archive_record: archive_note set",
              row.archive_note == "test arşiv")

    # ---- 5) Arşivlendiği için varsayılan listede yok ----
    with SessionLocal() as db:
        d = account_history(db, owner_type="institution", owner_id=inst_id)
        visible_plan_ids = [e.record_id for e in d["events"] if e.record_type == "plan"]
        check("archive sonrası kayıt timeline'da yok",
              plan_id not in visible_plan_ids,
              f"visible: {visible_plan_ids}")
        check("archived_count >= 1 (pencere içi arşivli)",
              d["archived_count"] >= 1, f"archived={d['archived_count']}")

    # ---- 6) include_archived=True ile yine görünür ----
    with SessionLocal() as db:
        d = account_history(db, owner_type="institution", owner_id=inst_id,
                            include_archived=True)
        visible_plan_ids = [e.record_id for e in d["events"] if e.record_type == "plan"]
        check("include_archived=True ile arşivli kayıt görünür",
              plan_id in visible_plan_ids)

    # ---- 7) Arşivden çıkar ----
    with SessionLocal() as db:
        r = unarchive_record(db, record_type="plan", record_id=plan_id)
        check("unarchive_record: ok", r.get("ok"))
        row = db.get(PlanChangeHistory, plan_id)
        check("unarchive_record: archived_at NULL", row.archived_at is None)

    # ---- 8) Toplu arşivle: 3 yıldan eski tümünü ----
    with SessionLocal() as db:
        r = bulk_archive_older_than(
            db, owner_type="institution", owner_id=inst_id,
            years=3, by_user_id=sa_id,
        )
        check("bulk_archive: ok", r.get("ok"))
        check("bulk_archive: en az 4 kayıt (2 plan + 2 fatura)",
              r.get("total", 0) >= 4, f"total={r.get('total')}")
        check("bulk_archive: plan_count >= 2",
              r.get("plan_count", 0) >= 2)
        check("bulk_archive: invoice_count >= 2",
              r.get("invoice_count", 0) >= 2)

    # ---- 9) Toplu arşiv sonrası older_count düşmeli ----
    with SessionLocal() as db:
        d = account_history(db, owner_type="institution", owner_id=inst_id)
        check("bulk_archive sonrası older_count = 0",
              d["older_count"] == 0,
              f"older={d['older_count']}")

    # ---- 10) HTTP route'lar ----
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

        # Kurum sayfa
        r = c.get(f"/admin/institutions/{inst_id}/account-history")
        check("kurum account-history GET 200", r.status_code == 200)
        check("kurum sayfasında 'Hesap Hareketleri' başlık",
              "Hesap Hareketleri" in r.text)
        check("kurum sayfasında pencere seçici (years=)",
              "years=" in r.text or "name=\"years\"" in r.text)

        # Kullanıcı sayfa
        r2 = c.get(f"/admin/users/{teacher_id}/account-history")
        check("kullanıcı account-history GET 200", r2.status_code == 200)

        # Years parametresi
        r3 = c.get(f"/admin/institutions/{inst_id}/account-history?years=5")
        check("years=5 GET 200", r3.status_code == 200)

        # include_archived
        r4 = c.get(f"/admin/institutions/{inst_id}/account-history?include_archived=1")
        check("include_archived=1 GET 200", r4.status_code == 200)

        # Tekil unarchive (önce setup: bir kayıt arşivle)
        with SessionLocal() as db:
            new_row = PlanChangeHistory(
                owner_type=PlanOwnerType.INSTITUTION, owner_id=inst_id,
                from_plan="free", to_plan="free",
                reason=PlanChangeReason.RESUME,
                note=f"{tag} http test",
                occurred_at=now - timedelta(days=3),
            )
            db.add(new_row)
            db.commit()
            http_plan_id = new_row.id

        # POST archive
        r5 = c.post(
            "/admin/account-history/archive",
            data={
                "record_type": "plan",
                "record_id": http_plan_id,
                "note": "http test",
                "return_to": f"/admin/institutions/{inst_id}/account-history",
            },
            follow_redirects=False,
        )
        check("archive POST → 303", r5.status_code == 303)
        check("archive POST → ok param",
              "ok=" in r5.headers.get("location", ""),
              r5.headers.get("location", ""))

        with SessionLocal() as db2:
            row = db2.get(PlanChangeHistory, http_plan_id)
            check("HTTP archive sonrası archived_at set",
                  row.archived_at is not None)
            # Audit log
            au = (
                db2.query(AuditLog)
                .filter(
                    AuditLog.action == AuditAction.USER_UPDATE,
                    AuditLog.target_type == "account_history_plan",
                    AuditLog.target_id == http_plan_id,
                )
                .first()
            )
            check("HTTP archive audit log yazıldı", au is not None)

        # POST unarchive
        r6 = c.post(
            "/admin/account-history/unarchive",
            data={
                "record_type": "plan",
                "record_id": http_plan_id,
                "return_to": f"/admin/institutions/{inst_id}/account-history",
            },
            follow_redirects=False,
        )
        check("unarchive POST → 303", r6.status_code == 303)
        with SessionLocal() as db2:
            row = db2.get(PlanChangeHistory, http_plan_id)
            check("HTTP unarchive sonrası archived_at NULL",
                  row.archived_at is None)

        # POST bulk-archive (öğretmen için, 5 yıldan eski)
        # Önce 5 yıldan eski bir kayıt ekle
        with SessionLocal() as db:
            db.add(PlanChangeHistory(
                owner_type=PlanOwnerType.USER, owner_id=teacher_id,
                from_plan="solo_trial", to_plan="solo_pro",
                reason=PlanChangeReason.UPGRADE,
                note=f"{tag} teacher 5yıl önce",
                occurred_at=now - timedelta(days=365 * 5 + 30),
            ))
            db.commit()
        r7 = c.post(
            "/admin/account-history/bulk-archive",
            data={
                "owner_type": "user",
                "owner_id": teacher_id,
                "years": "3",
                "note": "test bulk",
                "return_to": f"/admin/users/{teacher_id}/account-history",
            },
            follow_redirects=False,
        )
        check("bulk-archive POST → 303", r7.status_code == 303)
        check("bulk-archive POST → ok param",
              "ok=" in r7.headers.get("location", ""))

        # Geçersiz record_type
        r8 = c.post(
            "/admin/account-history/archive",
            data={"record_type": "garbage", "record_id": 1, "return_to": "/admin"},
            follow_redirects=False,
        )
        check("invalid record_type → 303 + err",
              r8.status_code == 303
              and "err=" in r8.headers.get("location", ""))

        # Bilinmeyen record_id
        r9 = c.post(
            "/admin/account-history/archive",
            data={"record_type": "plan", "record_id": 99999999, "return_to": "/admin"},
            follow_redirects=False,
        )
        check("bilinmeyen record_id → 303 + err",
              r9.status_code == 303
              and "err=" in r9.headers.get("location", ""))
    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(PlanChangeHistory).filter(
            PlanChangeHistory.note.like(f"{tag}%")
        ).delete()
        db.query(Invoice).filter(Invoice.notes.like(f"{tag}%")).delete()
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
