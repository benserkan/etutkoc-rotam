"""Katman 11.I — Veri Bütünlüğü Kamerası smoke test.

Senaryolar:
  1) migration_status: head + current eşit ya da pending bayraklı
  2) db_file_status: size_mb, level alanları
  3) orphan_scan: dict liste, kind/label/count
  4) kvkk_sla_check: open_total + overdue
  5) cron_drift_check: summary + jobs liste
  6) get_integrity_panel_data: aggregator keys
  7) HTTP GET /admin/security-monitor/integrity 200 + bölümler
  8) Ana panoda 'Bütünlük' linki
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
from app.deps import get_current_user, get_db, require_super_admin, require_user
from app.main import app
from app.models import (
    DataRequestKind,
    DataRequestStatus,
    DataSubjectRequest,
    User,
    UserRole,
)
from app.services.data_integrity import (
    cron_drift_check,
    db_file_status,
    get_integrity_panel_data,
    kvkk_sla_check,
    migration_status,
    orphan_scan,
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
    print("=== Katman 11.I (Veri Bütünlüğü) smoke ===")
    pfx = f"di-{secrets.token_hex(3)}"

    # ---- 1) migration_status ----
    with SessionLocal() as db:
        m = migration_status(db)
        check("migration keys",
              {"status", "head", "current", "pending"} <= set(m.keys()))
        check("migration head dolu",
              m["head"] is not None or m["status"] in ("error", "unknown"))

    # ---- 2) db_file_status ----
    f = db_file_status()
    check("db_file keys",
          {"size_mb", "level"} <= set(f.keys()))
    check("size_mb >= 0",
          isinstance(f["size_mb"], (int, float)) and f["size_mb"] >= 0)
    check("level değer",
          f["level"] in ("ok", "warn", "critical", "unknown", "error"))

    # ---- 3) orphan_scan ----
    with SessionLocal() as db:
        o = orphan_scan(db)
        check("orphan keys",
              {"total_findings", "findings"} <= set(o.keys()))
        check("findings liste",
              isinstance(o["findings"], list))
        for f_item in o["findings"]:
            check(f"{f_item['kind']} şema OK",
                  {"kind", "label", "count", "samples"} <= set(f_item.keys()))
            break  # bir tane yeterli

    # ---- 4) kvkk_sla_check ----
    with SessionLocal() as db:
        # SLA aşan sentetik talep yarat
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        student = db.query(User).filter(User.role == UserRole.STUDENT).first()
        if sa and student:
            old_req = DataSubjectRequest(
                kind=DataRequestKind.EXPORT,
                status=DataRequestStatus.PENDING,
                requester_user_id=sa.id,
                target_user_id=student.id,
                admin_note=f"{pfx}-overdue",
                created_at=datetime.now(timezone.utc) - timedelta(days=35),
            )
            db.add(old_req)
            db.commit()
            old_id = old_req.id

        sla = kvkk_sla_check(db)
        check("kvkk_sla keys",
              {"sla_days", "overdue_count", "open_total", "overdue_samples"}
              <= set(sla.keys()))
        check("sla_days = 30", sla["sla_days"] == 30)
        if sa and student:
            check("overdue_count >= 1 (sentetik)",
                  sla["overdue_count"] >= 1)
            check("overdue_samples'da bizim talep var",
                  any(s["id"] == old_id for s in sla["overdue_samples"]))

    # ---- 5) cron_drift_check ----
    with SessionLocal() as db:
        cd = cron_drift_check(db)
        check("cron_drift keys",
              {"summary", "jobs"} <= set(cd.keys()))
        check("summary alt anahtarları",
              {"ok", "warn", "critical"} <= set(cd["summary"].keys()))
        check("jobs liste", isinstance(cd["jobs"], list))

    # ---- 6) get_integrity_panel_data ----
    with SessionLocal() as db:
        d = get_integrity_panel_data(db)
        check("aggregator keys",
              {"generated_at", "migration", "db_file", "orphans",
               "kvkk_sla", "cron_drift"} <= set(d.keys()))
        check("generated_at datetime",
              isinstance(d["generated_at"], datetime))

    # ---- 7-8) HTTP ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — HTTP atlandı)")
        else:
            sa_id = sa.id

            def _ov():
                def factory():
                    db2 = SessionLocal()
                    try:
                        from sqlalchemy.orm import joinedload
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
                r = c.get("/admin/security-monitor/integrity")
                check("integrity pano GET 200",
                      r.status_code == 200, f"got {r.status_code}")
                check("'Veri Bütünlüğü Kamerası' başlığı",
                      "Veri Bütünlüğü Kamerası" in r.text)
                check("'Migration Durumu' kartı",
                      "Migration Durumu" in r.text)
                check("'DB Dosyası' kartı",
                      "DB Dosyası" in r.text)
                check("'Orphan Tutarsızlıklar' bölümü",
                      "Orphan Tutarsızlıklar" in r.text)
                check("'KVKK SLA' bölümü",
                      "KVKK SLA" in r.text)
                check("'Cron Drift' bölümü",
                      "Cron Drift" in r.text)

                # Ana panoda link
                r2 = c.get("/admin/security-monitor")
                check("ana panoda 'Bütünlük' linki",
                      "Bütünlük" in r2.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(DataSubjectRequest).filter(
            DataSubjectRequest.admin_note.like(f"{pfx}%")
        ).delete()
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
