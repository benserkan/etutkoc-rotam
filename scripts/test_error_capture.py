"""Katman 11.E — Sistem Hata İzleme smoke test.

Senaryolar:
  1) compute_signature: aynı (endpoint, exc, stack_top) → aynı SHA1
  2) record_error: ilk olay yeni satır
  3) record_error dedup: aynı signature → count += 1, yeni satır yok
  4) record_error reopen: resolved kayıt tekrar tetiklenirse resolved_at NULL
  5) record_slow_request: append-only
  6) error_summary 24h: open_groups, new_groups_24h, total_events_24h
  7) endpoint_error_rates: top endpoint
  8) list_slow_requests: descending order
  9) resolve_error: resolved_at + resolved_by_user_id set
 10) get_system_health_data: aggregator keys
 11) HTTP GET /admin/security-monitor/system 200 + bölümler
 12) HTTP POST /security-monitor/system/{id}/resolve 303
 13) Ana panoda 'Sistem Hataları' link
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
from app.deps import get_current_user, get_db, require_super_admin, require_user
from app.main import app
from app.models import ErrorEvent, SlowRequestLog, User, UserRole
from app.services.error_capture import (
    compute_signature,
    endpoint_error_rates,
    error_summary,
    get_system_health_data,
    list_error_groups,
    list_slow_requests,
    record_error,
    record_slow_request,
    resolve_error,
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
    print("=== Katman 11.E (Sistem Hata İzleme) smoke ===")
    pfx = f"err-{secrets.token_hex(3)}"
    test_endpoint = f"/test/{pfx}/route"

    # Cleanup leftover
    with SessionLocal() as db:
        db.query(ErrorEvent).filter(ErrorEvent.endpoint.like(f"%{pfx}%")).delete()
        db.query(SlowRequestLog).filter(SlowRequestLog.endpoint.like(f"%{pfx}%")).delete()
        db.commit()

    # ---- 1) compute_signature deterministik ----
    sig1 = compute_signature(endpoint="/x", exception_type="ValueError", stack_top="a:1:f")
    sig2 = compute_signature(endpoint="/x", exception_type="ValueError", stack_top="a:1:f")
    sig3 = compute_signature(endpoint="/x", exception_type="TypeError", stack_top="a:1:f")
    check("signature deterministik", sig1 == sig2)
    check("signature farklı exc farklı", sig1 != sig3)
    check("signature 40 hex char", len(sig1) == 40)

    # ---- 2-4) record_error + dedup + reopen ----
    # Aynı satırdan raise → aynı stack_top → aynı signature (üretim davranışı)
    def _value_error_raiser(msg: str) -> ValueError:
        try:
            raise ValueError(msg)
        except ValueError as e:
            return e

    def _type_error_raiser(msg: str) -> TypeError:
        try:
            raise TypeError(msg)
        except TypeError as e:
            return e

    with SessionLocal() as db:
        r1 = record_error(
            db,
            endpoint=test_endpoint,
            method="GET",
            status_code=500,
            exception=_value_error_raiser(f"{pfx} test hata"),
            ip="10.0.0.1",
            user_agent="TestAgent",
        )
        check("ilk hata yazıldı", r1 is not None and r1.id is not None)
        check("count=1", r1.count == 1)
        first_id = r1.id
        first_sig = r1.signature

        # Aynı helper'dan → aynı stack_top → dedup
        r2 = record_error(
            db,
            endpoint=test_endpoint,
            method="GET",
            status_code=500,
            exception=_value_error_raiser(f"{pfx} test hata 2"),
            ip="10.0.0.2",
        )
        check("dedup: aynı kayıt", r2.id == first_id,
              f"sig1={first_sig} sig2={r2.signature}")
        check("count += 1 (=2)", r2.count == 2)
        check("last_ip güncellendi", r2.last_ip == "10.0.0.2")

        # Farklı exception type → yeni grup
        r3 = record_error(
            db,
            endpoint=test_endpoint,
            method="GET",
            status_code=500,
            exception=_type_error_raiser(f"{pfx} farklı tip"),
        )
        check("farklı exc → yeni grup", r3.id != first_id)

        # Resolved kaydı tekrar tetikle → re-open
        r2.resolved_at = datetime.now(timezone.utc)
        r2.resolved_by_user_id = None
        db.commit()
        r4 = record_error(
            db,
            endpoint=test_endpoint,
            method="GET",
            status_code=500,
            exception=_value_error_raiser(f"{pfx} tekrarlandı"),
        )
        check("resolved kayıt tekrar tetiklenince re-open",
              r4.id == first_id and r4.resolved_at is None)

    # ---- 5) record_slow_request ----
    with SessionLocal() as db:
        s1 = record_slow_request(
            db,
            endpoint=test_endpoint,
            method="GET",
            status_code=200,
            response_time_ms=3500,
        )
        check("slow request yazıldı", s1 is not None and s1.id is not None)
        check("response_time_ms doğru", s1.response_time_ms == 3500)

        s2 = record_slow_request(
            db,
            endpoint=test_endpoint,
            method="GET",
            status_code=200,
            response_time_ms=1800,
        )
        check("slow request append-only (yeni satır)", s2.id != s1.id)

    # ---- 6) error_summary ----
    with SessionLocal() as db:
        sm = error_summary(db, hours=24)
        check("summary keys",
              set(sm.keys()) >= {"open_groups", "new_groups_24h",
                                  "total_events_24h", "window_hours"})
        check("open_groups > 0", sm["open_groups"] >= 1)
        check("new_groups_24h >= 1", sm["new_groups_24h"] >= 1)
        check("total_events_24h >= 2", sm["total_events_24h"] >= 2)

    # ---- 7) endpoint_error_rates ----
    with SessionLocal() as db:
        top = endpoint_error_rates(db, hours=24, limit=10)
        endpoints = [e["endpoint"] for e in top]
        check("test endpoint top'ta", test_endpoint in endpoints)
        for e in top:
            if e["endpoint"] == test_endpoint:
                check("test endpoint total >= 2", e["total"] >= 2)
                break

    # ---- 8) list_slow_requests descending ----
    with SessionLocal() as db:
        slows = list_slow_requests(db, hours=24, limit=10)
        check("slow listesi dolu", len(slows) > 0)
        check("descending response_time_ms",
              all(slows[i]["response_time_ms"] >= slows[i + 1]["response_time_ms"]
                  for i in range(len(slows) - 1)))

    # ---- 9) resolve_error ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        groups = list_error_groups(db, only_open=True, limit=5)
        target_id = None
        for g in groups:
            if g["endpoint"] == test_endpoint:
                target_id = g["id"]
                break
        check("resolve target group bulundu", target_id is not None)
        if target_id and sa:
            resolve_error(
                db, error_id=target_id, resolved_by_user_id=sa.id,
                note="smoke test çözüldü",
            )
            db.expire_all()
            row = db.get(ErrorEvent, target_id)
            check("resolved_at set", row.resolved_at is not None)
            check("resolved_by set", row.resolved_by_user_id == sa.id)
            check("resolution_note set", row.resolution_note is not None)

    # ---- 10) get_system_health_data ----
    with SessionLocal() as db:
        d = get_system_health_data(db)
        check("aggregator keys",
              set(d.keys()) >= {"generated_at", "summary", "error_groups",
                                "endpoint_top", "slow_requests"})

    # ---- 11-13) HTTP ----
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
                r = c.get("/admin/security-monitor/system")
                check("system pano GET 200",
                      r.status_code == 200, f"got {r.status_code}")
                check("'Sistem Hata Kamerası' başlığı",
                      "Sistem Hata Kamerası" in r.text)
                check("'Açık Hata Grupları' bölümü",
                      "Açık Hata Grupları" in r.text)
                check("'Yavaş İstekler' bölümü",
                      "Yavaş İstekler" in r.text)
                check("'En Çok Hata Veren' bölümü",
                      "En Çok Hata Veren" in r.text)

                # 12) Resolve POST
                with SessionLocal() as db2:
                    # Açık bir grup yarat (yeni endpoint)
                    try:
                        raise RuntimeError(f"{pfx} HTTP test exc")
                    except RuntimeError as e:
                        new_g = record_error(
                            db2,
                            endpoint=f"/test/{pfx}/http-resolve",
                            method="POST",
                            status_code=500,
                            exception=e,
                        )
                    g_id = new_g.id
                r2 = c.post(
                    f"/admin/security-monitor/system/{g_id}/resolve",
                    data={"note": "HTTP test"},
                    follow_redirects=False,
                )
                check("resolve POST → 303", r2.status_code == 303)
                with SessionLocal() as db2:
                    row = db2.get(ErrorEvent, g_id)
                    check("HTTP resolve sonrası resolved_at set",
                          row is not None and row.resolved_at is not None)

                # 13) Ana panoda Sistem Hataları
                r3 = c.get("/admin/security-monitor")
                check("ana panoda 'Sistem Hataları' linki",
                      "Sistem Hataları" in r3.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(ErrorEvent).filter(ErrorEvent.endpoint.like(f"%{pfx}%")).delete()
        db.query(SlowRequestLog).filter(SlowRequestLog.endpoint.like(f"%{pfx}%")).delete()
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
