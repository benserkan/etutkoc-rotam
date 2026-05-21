"""Katman 11.B — Süper Admin Davranış Kamerası smoke test.

Senaryolar:
  1) validate_reason — boş/kısa/uzun/normal
  2) start_session: ImpersonationSession satırı + expires_at = +30dk
  3) is_expired: expires_at < now için True; aktif iken False
  4) expire_if_needed: süresi dolmuşsa ended_at + end_reason="expired"
  5) end_session manual: end_reason="manual" + ended_by
  6) find_active_for_actor_target
  7) list_active: aktif kayıtları dict ile döndürür
  8) HTTP POST /admin/users/{id}/impersonate
     a) reason eksik → 303 redirect + err
     b) reason geçerli → ImpersonationSession yazılır + audit IMPERSONATE_START
     c) impersonation_id session'a yazılır
  9) HTTP POST /admin/security-monitor/impersonations/{id}/end
     → end_reason="revoked" + audit IMPERSONATE_REVOKED
 10) HTTP GET /admin/security-monitor → aktif sahte oturum bandı görünür
 11) audit_list — details_json'da before/after varsa diff görünümü render edilir
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, get_db, require_super_admin, require_user
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    IMPERSONATION_MAX_DURATION_MINUTES,
    ImpersonationSession,
    User,
    UserRole,
)
from app.services.audit import log_action
from app.services.impersonation import (
    end_session,
    expire_if_needed,
    find_active_for_actor_target,
    is_expired,
    list_active,
    start_session,
    validate_reason,
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
    print("=== Katman 11.B (Sahte Oturum Kamerası) smoke ===")
    pfx = f"impb-{secrets.token_hex(3)}"

    # ---- 1) validate_reason ----
    v_empty = validate_reason("")
    check("boş reason reddedilir", v_empty.ok is False)
    v_short = validate_reason("kısa")
    check("kısa reason reddedilir (< 10)", v_short.ok is False)
    v_ok = validate_reason("kullanıcı şikayetini yerinde incelemek için")
    check("normal reason kabul edilir", v_ok.ok is True)
    check("cleaned dolu", len(v_ok.cleaned) > 0)
    v_long = validate_reason("a" * 500)
    check("uzun reason truncate edilir", v_long.ok is True and len(v_long.cleaned) == 200)

    # ---- 2-7) Servis akışları ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        target = (
            db.query(User)
            .filter(User.role == UserRole.TEACHER, User.is_active.is_(True))
            .first()
        )
        if sa is None or target is None:
            print("  (super_admin veya teacher yok — testler atlandı)")
            return 0
        sa_id = sa.id
        target_id = target.id

        # Önceki test kalıntılarını temizle
        db.query(ImpersonationSession).filter(
            ImpersonationSession.actor_user_id == sa_id,
            ImpersonationSession.target_user_id == target_id,
        ).delete()
        db.commit()

        # 2) start_session
        imp = start_session(
            db, actor=sa, target=target,
            reason=f"{pfx}: smoke test gerekçesi (yeterli karakter)",
            ip="10.0.0.5",
        )
        check("ImpersonationSession yazıldı", imp.id is not None)
        check("actor_user_id doğru", imp.actor_user_id == sa_id)
        check("target_user_id doğru", imp.target_user_id == target_id)
        check("reason saklandı", imp.reason.startswith(pfx))
        check(
            "expires_at ~30 dk sonra",
            abs((imp.expires_at - imp.started_at).total_seconds()
                - IMPERSONATION_MAX_DURATION_MINUTES * 60) < 5,
        )
        check("ended_at None (aktif)", imp.ended_at is None)

        # 3) is_expired (yeni başlamış)
        check("yeni başlayan oturum süresi dolmamış", is_expired(imp) is False)

        # Yapay olarak expires_at'ı geçmişe çek
        imp.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        db.refresh(imp)
        check("yapay expired → is_expired True", is_expired(imp) is True)

        # 4) expire_if_needed
        triggered = expire_if_needed(db, session_id=imp.id)
        check("expire_if_needed True döner", triggered is True)
        db.refresh(imp)
        check("ended_at set", imp.ended_at is not None)
        check("end_reason expired", imp.end_reason == "expired")

        # find_active sonrası None döner (artık kapalı)
        active = find_active_for_actor_target(
            db, actor_id=sa_id, target_id=target_id
        )
        check("find_active expire sonrası None", active is None)

        # 5) Yeni session açıp manual end
        imp2 = start_session(
            db, actor=sa, target=target,
            reason="manuel test gerekçesi yeterince uzun",
            ip="10.0.0.6",
        )
        active2 = find_active_for_actor_target(
            db, actor_id=sa_id, target_id=target_id
        )
        check("find_active aktif kaydı döndürür", active2 is not None and active2.id == imp2.id)

        ended = end_session(
            db, session_id=imp2.id, end_reason="manual", ended_by_user_id=sa_id
        )
        check("end_session manual çalışır", ended.end_reason == "manual")
        check("ended_by_user_id set", ended.ended_by_user_id == sa_id)

        # 7) list_active boş olmalı
        active_list = list_active(db)
        active_ids = {a["id"] for a in active_list}
        check("liste'de kapalı oturum yok",
              imp.id not in active_ids and imp2.id not in active_ids)

    # ---- 8-11) HTTP akışları ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        target = (
            db.query(User)
            .filter(User.role == UserRole.TEACHER, User.is_active.is_(True))
            .first()
        )
        if sa is None or target is None:
            print("  (super_admin veya teacher yok — HTTP testleri atlandı)")
            return 0
        sa_id = sa.id
        target_id = target.id

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

            # 8a) Reason eksik → 303 + err query
            # Kalan aktif kayıt varsa kapat
            with SessionLocal() as db2:
                db2.query(ImpersonationSession).filter(
                    ImpersonationSession.actor_user_id == sa_id,
                    ImpersonationSession.target_user_id == target_id,
                    ImpersonationSession.ended_at.is_(None),
                ).update({"ended_at": datetime.now(timezone.utc), "end_reason": "manual"})
                db2.commit()

            r_no_reason = c.post(
                f"/admin/users/{target_id}/impersonate",
                data={"reason": ""},
                follow_redirects=False,
            )
            check("reason yok → 303", r_no_reason.status_code == 303)
            check("redirect URL err= içerir",
                  "err=" in r_no_reason.headers.get("location", ""))

            # 8b) Reason geçerli → ImpersonationSession + audit
            valid_reason = f"{pfx}: HTTP test - kullanıcı destek talebi inceleme"
            r_ok = c.post(
                f"/admin/users/{target_id}/impersonate",
                data={"reason": valid_reason},
                follow_redirects=False,
            )
            check("geçerli reason → 303 hedef anasayfasına",
                  r_ok.status_code == 303,
                  f"got {r_ok.status_code}")
            with SessionLocal() as db2:
                imp_row = (
                    db2.query(ImpersonationSession)
                    .filter(
                        ImpersonationSession.actor_user_id == sa_id,
                        ImpersonationSession.target_user_id == target_id,
                        ImpersonationSession.ended_at.is_(None),
                    )
                    .order_by(ImpersonationSession.started_at.desc())
                    .first()
                )
                check("HTTP sonrası ImpersonationSession yazıldı", imp_row is not None)
                check("reason DB'de doğru",
                      imp_row is not None and pfx in imp_row.reason)
                _exp = imp_row.expires_at if imp_row else None
                if _exp is not None and _exp.tzinfo is None:
                    _exp = _exp.replace(tzinfo=timezone.utc)
                check("expires_at gelecekte",
                      _exp is not None and
                      _exp > datetime.now(timezone.utc))
                # Audit IMPERSONATE_START
                audit = (
                    db2.query(AuditLog)
                    .filter(
                        AuditLog.action == AuditAction.IMPERSONATE_START,
                        AuditLog.actor_id == sa_id,
                        AuditLog.target_id == target_id,
                    )
                    .order_by(AuditLog.created_at.desc())
                    .first()
                )
                check("audit IMPERSONATE_START yazıldı", audit is not None)
                if audit is not None and audit.details_json:
                    d = json.loads(audit.details_json)
                    check("audit detayında reason var",
                          d.get("reason", "").startswith(pfx))
                    check("audit detayında impersonation_id",
                          d.get("impersonation_id") == imp_row.id)

                # 9) Pano akışı — kayıt aktif görünmeli
                http_imp_id = imp_row.id

            r_panel = c.get("/admin/security-monitor")
            check("security-monitor GET 200", r_panel.status_code == 200)
            check("'Aktif Sahte Oturumlar' bandı",
                  "Aktif Sahte Oturumlar" in r_panel.text)
            check("reason metni panoda görünür", pfx in r_panel.text)

            # 9) Uzaktan sonlandır
            r_end = c.post(
                f"/admin/security-monitor/impersonations/{http_imp_id}/end",
                follow_redirects=False,
            )
            check("revoke → 303", r_end.status_code == 303)
            with SessionLocal() as db2:
                imp_after = db2.get(ImpersonationSession, http_imp_id)
                check("revoke sonrası ended_at set",
                      imp_after is not None and imp_after.ended_at is not None)
                check("end_reason revoked",
                      imp_after is not None and imp_after.end_reason == "revoked")
                # Audit IMPERSONATE_REVOKED
                rev_audit = (
                    db2.query(AuditLog)
                    .filter(
                        AuditLog.action == AuditAction.IMPERSONATE_REVOKED,
                        AuditLog.actor_id == sa_id,
                    )
                    .order_by(AuditLog.created_at.desc())
                    .first()
                )
                check("audit IMPERSONATE_REVOKED yazıldı", rev_audit is not None)

            # 10) Pano artık aktif bant göstermeyi durdursun (bu pfx için)
            r_panel2 = c.get("/admin/security-monitor")
            check("revoke sonrası pano render 200",
                  r_panel2.status_code == 200)
            # Bu pfx özelinde aktif bant kalktı mı (basit kontrol — pfx artık aktif değil)
            # Tek aktif olabilir veya hiç olmayabilir; sadece bu pfx aktif olmamalı

            # 11) Audit list — diff görünümü için yapay before/after kayıt yaz
            with SessionLocal() as db2:
                log_action(
                    db2,
                    action=AuditAction.USER_UPDATE,
                    actor_id=sa_id,
                    target_type="user",
                    target_id=target_id,
                    details={
                        "before": {"email": "old@x.com", "is_active": False},
                        "after": {"email": "new@x.com", "is_active": True},
                        "field": "email",
                    },
                )
            r_audit = c.get("/admin/audit")
            check("audit list 200", r_audit.status_code == 200)
            check("'Değişim diff' summary butonu render edildi",
                  "Değişim diff'i" in r_audit.text)
            check("ÖNCE/SONRA kolonları var",
                  "ÖNCE" in r_audit.text and "SONRA" in r_audit.text)

        finally:
            app.dependency_overrides.pop(require_super_admin, None)
            app.dependency_overrides.pop(require_user, None)
            app.dependency_overrides.pop(get_current_user, None)

    # Cleanup: pfx ile yazılmış imp ve audit'leri sil
    with SessionLocal() as db:
        db.query(ImpersonationSession).filter(
            ImpersonationSession.reason.like(f"{pfx}%")
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
