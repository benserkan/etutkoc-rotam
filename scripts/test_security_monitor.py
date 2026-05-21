"""Katman 11.A — Güvenlik Kamerası smoke test.

Senaryolar:
  1) record_session_start: ActiveSession satırı yazılır
  2) heartbeat: last_seen_at güncellenir; terminated → False döner
  3) terminate_session: terminated_at + reason set edilir
  4) record_failed_login_ip: upsert + distinct emails listesi
  5) Otomatik blok: 10 farklı email → auto_emails_threshold
  6) Otomatik blok: 30+ fail → auto_fails_threshold (tek email)
  7) is_ip_blocked: aktif blok için True
  8) block_ip_manual / unblock_ip: süper admin override
  9) Dashboard data: tüm bölümler render edilebilir
 10) HTTP: GET /admin/security-monitor 200 + sayfa içeriği
 11) HTTP: POST revoke / block / unblock — 303 redirect
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
    ActiveSession,
    AuditAction,
    AuditLog,
    SuspiciousIp,
    User,
    UserRole,
)
from app.services.audit import log_action
from app.services.security_monitor import (
    BRUTE_FORCE_EMAILS_THRESHOLD,
    BRUTE_FORCE_FAILS_THRESHOLD,
    block_ip_manual,
    generate_session_token,
    get_security_dashboard_data,
    heartbeat,
    humanize_ago,
    is_ip_blocked,
    list_active_sessions,
    list_suspicious_ips,
    record_failed_login_ip,
    record_session_start,
    revoke_session_by_token,
    terminate_session,
    unblock_ip,
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
    print("=== Katman 11.A (Güvenlik Kamerası) smoke ===")
    pfx = f"sec-{secrets.token_hex(3)}"

    # ---- 1) Session lifecycle ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — testler atlandı)")
            return 0
        sa_id = sa.id

        # 1) record_session_start
        token1 = generate_session_token()
        sess = record_session_start(
            db, user=sa, session_token=token1, ip="10.0.0.1",
            user_agent="TestAgent/1.0",
        )
        check("ActiveSession kaydı yazıldı", sess.id is not None)
        check("session_token doğru", sess.session_token == token1)
        check("login_at = last_seen_at", sess.login_at == sess.last_seen_at)
        check("ip kaydı", sess.ip == "10.0.0.1")

        # 2) heartbeat
        before = sess.last_seen_at
        import time
        time.sleep(0.01)
        ok = heartbeat(db, session_token=token1)
        check("heartbeat True dönüyor (canlı)", ok is True)
        db.refresh(sess)
        check("last_seen_at güncellendi", sess.last_seen_at > before)

        # 3) terminate + heartbeat sonrası False
        terminate_session(db, session_token=token1, reason="logout")
        db.refresh(sess)
        check("terminated_at set", sess.terminated_at is not None)
        check("termination_reason logout", sess.termination_reason == "logout")
        ok_after = heartbeat(db, session_token=token1)
        check("heartbeat terminated → False", ok_after is False)

        # Cleanup
        db.query(ActiveSession).filter(ActiveSession.session_token == token1).delete()
        db.commit()

    # ---- 4) record_failed_login_ip — upsert + distinct emails ----
    test_ip = f"192.168.99.{secrets.randbelow(200) + 10}"
    with SessionLocal() as db:
        # Clear residue
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == test_ip).delete()
        db.commit()

        r1 = record_failed_login_ip(db, ip=test_ip, email_attempted=f"{pfx}-a@x.com")
        check("upsert: ilk kayıt fail_count=1", r1.fail_count == 1)
        check("upsert: distinct_email_count=1", r1.distinct_email_count == 1)

        r2 = record_failed_login_ip(db, ip=test_ip, email_attempted=f"{pfx}-a@x.com")
        check("aynı email — distinct artmaz", r2.distinct_email_count == 1)
        check("fail_count artar", r2.fail_count == 2)

        r3 = record_failed_login_ip(db, ip=test_ip, email_attempted=f"{pfx}-b@x.com")
        check("yeni email — distinct artar", r3.distinct_email_count == 2)

    # ---- 5) Otomatik blok: 10+ farklı email ----
    test_ip_2 = f"10.99.{secrets.randbelow(200) + 10}.{secrets.randbelow(200) + 10}"
    with SessionLocal() as db:
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == test_ip_2).delete()
        db.commit()
        for i in range(BRUTE_FORCE_EMAILS_THRESHOLD):
            record_failed_login_ip(
                db, ip=test_ip_2, email_attempted=f"{pfx}-mass-{i}@x.com"
            )
        blocked, row = is_ip_blocked(db, ip=test_ip_2)
        check(f"{BRUTE_FORCE_EMAILS_THRESHOLD} farklı email → auto block",
              blocked, f"row={row.block_reason if row else None}")
        check("block_reason = auto_emails_threshold",
              row is not None and row.block_reason == "auto_emails_threshold")

    # ---- 6) Otomatik blok: çok fail (tek email) ----
    test_ip_3 = f"172.16.{secrets.randbelow(200) + 10}.{secrets.randbelow(200) + 10}"
    with SessionLocal() as db:
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == test_ip_3).delete()
        db.commit()
        for _ in range(BRUTE_FORCE_FAILS_THRESHOLD):
            record_failed_login_ip(
                db, ip=test_ip_3, email_attempted=f"{pfx}-single@x.com"
            )
        blocked3, row3 = is_ip_blocked(db, ip=test_ip_3)
        check(f"{BRUTE_FORCE_FAILS_THRESHOLD} fail tek email → auto block",
              blocked3, f"row={row3.block_reason if row3 else None}")
        # Bu IP'de distinct=1 ve fail >= threshold → fails_threshold
        check("block_reason fails_threshold (1 email)",
              row3 is not None and row3.block_reason == "auto_fails_threshold")

    # ---- 7) Manuel blok / unblock ----
    test_ip_4 = f"203.0.113.{secrets.randbelow(200) + 1}"
    with SessionLocal() as db:
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == test_ip_4).delete()
        db.commit()
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        row4 = block_ip_manual(
            db, ip=test_ip_4, hours=2, note="Manuel test", by_user_id=sa.id
        )
        check("manuel blok: block_reason=manual", row4.block_reason == "manual")
        check("manuel blok: blocked_by_user_id set",
              row4.blocked_by_user_id == sa.id)
        check("manuel blok: is_ip_blocked True",
              is_ip_blocked(db, ip=test_ip_4)[0])
        unblock_ip(db, ip=test_ip_4)
        check("unblock sonrası is_ip_blocked False",
              not is_ip_blocked(db, ip=test_ip_4)[0])

    # ---- 8) Dashboard data ----
    with SessionLocal() as db:
        data = get_security_dashboard_data(db)
        check("dashboard: summary keys",
              set(data["summary"].keys()) >= {
                  "active_sessions", "blocked_ips", "watched_ips",
                  "failed_24h", "critical_24h", "super_admin_logins_24h",
              })
        check("dashboard: active_sessions liste",
              isinstance(data["active_sessions"], list))
        check("dashboard: suspicious_ips liste",
              isinstance(data["suspicious_ips"], list))
        check("dashboard: failed_login_buckets liste",
              isinstance(data["failed_login_buckets"], list))
        check("dashboard: critical_audits liste",
              isinstance(data["critical_audits"], list))
        check("dashboard: generated_at datetime",
              isinstance(data["generated_at"], datetime))

    # ---- 9) humanize_ago Türkçe ----
    check("humanize 30sn", humanize_ago(30) == "az önce")
    check("humanize 5dk", humanize_ago(300) == "5 dk önce")
    check("humanize 2 saat", humanize_ago(7200) == "2 saat önce")
    check("humanize 3 gün", humanize_ago(86400 * 3) == "3 gün önce")

    # ---- 10) HTTP /admin/security-monitor ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — HTTP testi atlandı)")
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
                r = c.get("/admin/security-monitor")
                check("security-monitor GET 200",
                      r.status_code == 200, f"got {r.status_code}")
                check("'Güvenlik Kamerası' başlığı",
                      "Güvenlik Kamerası" in r.text)
                # 11.K.1 — Dikkat Odası: artık ana panoda mini KPI + dikkat kartları
                # Aktif oturum / IP / kritik akış / SA login detayları alt sayfalara taşındı
                check("'Şu an dikkat' bölümü",
                      "Şu an dikkat" in r.text)
                check("Mini KPI 'Oturum' rozet",
                      "Oturum" in r.text and "Bloklu IP" in r.text)
                check("Alt pano kısayolu 'Canlı'",
                      "🔴 Canlı" in r.text)
                check("Alt pano kısayolu 'Alarm'",
                      "🔔 Alarm" in r.text)

                # Block IP
                ip_block_test = f"198.51.100.{secrets.randbelow(200) + 1}"
                # Önce listede olduğundan emin ol
                with SessionLocal() as db2:
                    db2.query(SuspiciousIp).filter(
                        SuspiciousIp.ip == ip_block_test
                    ).delete()
                    db2.commit()
                r2 = c.post(
                    "/admin/security-monitor/ips/block",
                    data={"ip": ip_block_test, "hours": "2", "note": "Smoke"},
                    follow_redirects=False,
                )
                check("POST block → 303", r2.status_code == 303,
                      f"got {r2.status_code}")
                with SessionLocal() as db2:
                    blocked, row = is_ip_blocked(db2, ip=ip_block_test)
                    check("HTTP sonrası IP gerçekten bloklu", blocked)
                    check("manuel reason",
                          row is not None and row.block_reason == "manual")

                # Unblock
                r3 = c.post(
                    "/admin/security-monitor/ips/unblock",
                    data={"ip": ip_block_test},
                    follow_redirects=False,
                )
                check("POST unblock → 303", r3.status_code == 303)
                with SessionLocal() as db2:
                    check("HTTP unblock sonrası serbest",
                          not is_ip_blocked(db2, ip=ip_block_test)[0])

                # Revoke active session
                with SessionLocal() as db2:
                    u = db2.query(User).filter(User.id == sa_id).first()
                    token_test = generate_session_token()
                    sess_test = record_session_start(
                        db2, user=u, session_token=token_test,
                        ip="10.10.10.10", user_agent="SmokeAgent",
                    )
                    token_str = token_test
                r4 = c.post(
                    f"/admin/security-monitor/sessions/{token_str}/revoke",
                    follow_redirects=False,
                )
                check("POST revoke → 303", r4.status_code == 303)
                with SessionLocal() as db2:
                    s = (
                        db2.query(ActiveSession)
                        .filter(ActiveSession.session_token == token_str)
                        .first()
                    )
                    check("revoke sonrası terminated_at set",
                          s is not None and s.terminated_at is not None)
                    check("revoke reason admin_revoke",
                          s is not None and s.termination_reason == "admin_revoke")

                # Admin dashboard'da link rozeti
                r5 = c.get("/admin")
                check("admin dashboard 200", r5.status_code == 200)
                check("'Güvenlik Kamerası' kısa yol",
                      "Güvenlik Kamerası" in r5.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup test_ip kayıtları ----
    with SessionLocal() as db:
        for ip in [test_ip, test_ip_2, test_ip_3, test_ip_4]:
            db.query(SuspiciousIp).filter(SuspiciousIp.ip == ip).delete()
        db.query(ActiveSession).filter(
            ActiveSession.user_agent.in_(["TestAgent/1.0", "SmokeAgent"])
        ).delete(synchronize_session=False)
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
