"""Katman 11.C+ — Abuse Remediation smoke test.

abuse_remediation.auto_remediate_signal her 4 sinyal türü için doğru
aksiyonu çalıştırıyor mu, sinyali otomatik resolve ediyor mu, ve
HTTP route audit log yazıyor mu kontrol eder.

Senaryolar:
  1) mass_invitation: davetler expires_at=now ile soft-cancel
  2) mass_notification: QUEUED bildirimler SUPPRESSED'a çekilir
  3) multi_account_same_device: aynı UA+IP oturumları terminated_at set
  4) unsubscribe_spike: otomatik aksiyon yok (ok=False)
  5) HTTP POST /admin/security-monitor/abuse/{id}/remediate → 303 + audit
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
from app.deps import get_current_user, get_db, require_super_admin, require_user
from app.main import app
from app.models import (
    AbuseSignal,
    ActiveSession,
    AuditAction,
    AuditLog,
    Institution,
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentInvitation,
    ParentRelation,
    User,
    UserRole,
)
from app.services.abuse_remediation import (
    ACTION_BUTTON_LABELS_TR,
    auto_remediate_signal,
    get_action_label,
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


def _cleanup(db, pfx: str) -> None:
    db.query(AbuseSignal).filter(
        AbuseSignal.details_json.like(f"%{pfx}%")
    ).delete(synchronize_session=False)
    db.query(ParentInvitation).filter(
        ParentInvitation.invited_email.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.query(NotificationLog).filter(
        NotificationLog.error.like(f"%{pfx}%")
    ).delete(synchronize_session=False)
    db.query(ActiveSession).filter(
        ActiveSession.user_agent.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.query(AuditLog).filter(
        AuditLog.details_json.like(f"%{pfx}%")
    ).delete(synchronize_session=False)
    db.commit()


def _mk_signal(db, *, kind: str, actor_id=None, tenant_id=None,
               details: dict | None = None, count: int = 50) -> int:
    now = datetime.now(timezone.utc)
    sig = AbuseSignal(
        kind=kind,
        severity="warn",
        actor_user_id=actor_id,
        tenant_id=tenant_id,
        count=count,
        window_start=now - timedelta(hours=1),
        window_end=now,
        detected_at=now,
        last_seen_at=now,
        details_json=json.dumps(details or {}),
    )
    db.add(sig)
    db.commit()
    return sig.id


def main() -> int:
    print("=== Katman 11.C+ (Abuse Remediation) smoke ===")
    pfx = f"remed-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        teacher = (
            db.query(User)
            .filter(User.role == UserRole.TEACHER, User.is_active.is_(True))
            .first()
        )
        student = (
            db.query(User).filter(User.role == UserRole.STUDENT).first()
        )
        parent_with_inst = (
            db.query(User)
            .filter(
                User.role == UserRole.PARENT,
                User.institution_id.isnot(None),
            )
            .first()
        )
        if not all([sa, teacher, student]):
            print("  (gerekli kullanıcılar yok — testler atlandı)")
            return 0
        sa_id = sa.id
        teacher_id = teacher.id
        student_id = student.id

        _cleanup(db, pfx)

    # ---- 1) MASS_INVITATION → davet iptal ----
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        for i in range(5):
            db.add(ParentInvitation(
                invited_email=f"{pfx}-veli-{i}@x.com",
                student_id=student_id,
                invited_by_id=teacher_id,
                relation=ParentRelation.DIGER,
                is_primary=False,
                token=f"{pfx}-tok-{i}-{secrets.token_hex(8)}",
                expires_at=now + timedelta(days=7),
                created_at=now - timedelta(minutes=10),
            ))
        db.commit()

        sig_id = _mk_signal(
            db, kind="mass_invitation", actor_id=teacher_id,
            details={"pfx": pfx, "window_hours": 1, "threshold": 3},
            count=5,
        )

        result = auto_remediate_signal(
            db, signal_id=sig_id, by_user_id=sa_id, autocommit=True,
        )
        check("mass_invitation: ok=True", result.ok, str(result))
        check("mass_invitation: action=cancel_invitations",
              result.action == "cancel_invitations")
        check("mass_invitation: 5 davet etkilendi",
              result.affected_count == 5, f"got {result.affected_count}")

        check_now = datetime.now(timezone.utc) + timedelta(seconds=1)
        live = (
            db.query(ParentInvitation)
            .filter(
                ParentInvitation.invited_by_id == teacher_id,
                ParentInvitation.invited_email.like(f"{pfx}%"),
                ParentInvitation.consumed_at.is_(None),
                ParentInvitation.expires_at > check_now,
            )
            .count()
        )
        check("mass_invitation: aktif davet kalmadı (expires_at çekildi)",
              live == 0, f"hala {live} aktif")

        sig = db.get(AbuseSignal, sig_id)
        check("mass_invitation: sinyal auto-resolved",
              sig.resolved_at is not None)
        check("mass_invitation: resolved_by_user_id set",
              sig.resolved_by_user_id == sa_id)
        check("mass_invitation: resolution_note iptal bilgisi içeriyor",
              "cancel_invitations" in (sig.resolution_note or ""),
              sig.resolution_note or "")

    # ---- 2) MASS_NOTIFICATION → SUPPRESSED ----
    if parent_with_inst:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            inst_id = parent_with_inst.institution_id
            parent_id = parent_with_inst.id
            for i in range(4):
                db.add(NotificationLog(
                    parent_id=parent_id,
                    student_id=student_id,
                    kind=NotificationKind.DAILY_SUMMARY,
                    channel=NotificationChannel.EMAIL,
                    status=NotificationStatus.QUEUED,
                    queued_at=now - timedelta(minutes=5),
                    error=f"{pfx}: test",
                ))
            db.commit()

            sig_id = _mk_signal(
                db, kind="mass_notification", tenant_id=inst_id,
                details={"pfx": pfx, "window_hours": 1, "threshold": 3},
                count=4,
            )
            result = auto_remediate_signal(
                db, signal_id=sig_id, by_user_id=sa_id, autocommit=True,
            )
            check("mass_notification: ok=True", result.ok, str(result))
            check("mass_notification: action=suppress_queued",
                  result.action == "suppress_queued")
            check("mass_notification: en az 4 etkilendi",
                  result.affected_count >= 4,
                  f"got {result.affected_count}")

            queued_left = (
                db.query(NotificationLog)
                .filter(
                    NotificationLog.error.like(f"%{pfx}%"),
                    NotificationLog.status == NotificationStatus.QUEUED,
                )
                .count()
            )
            check("mass_notification: QUEUED kalmadı",
                  queued_left == 0, f"{queued_left} QUEUED kaldı")
            suppressed = (
                db.query(NotificationLog)
                .filter(
                    NotificationLog.error.like(f"%{pfx}%"),
                    NotificationLog.status == NotificationStatus.SUPPRESSED,
                )
                .count()
            )
            check("mass_notification: SUPPRESSED'a alındı",
                  suppressed >= 4, f"got {suppressed}")
    else:
        print("  (parent_with_inst yok — mass_notification atlandı)")

    # ---- 3) MULTI_ACCOUNT → oturum revoke ----
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        ua_test = f"{pfx}-Mozilla/Test/1.0"
        ip_test = f"192.0.2.{secrets.randbelow(200) + 1}"
        users = (
            db.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.id)
            .limit(4)
            .all()
        )
        for i, u in enumerate(users):
            db.add(ActiveSession(
                session_token=f"{pfx}-multi-{i}-{secrets.token_hex(8)}",
                user_id=u.id,
                role=u.role.value,
                ip=ip_test,
                user_agent=ua_test,
                login_at=now - timedelta(hours=1),
                last_seen_at=now - timedelta(minutes=5),
            ))
        db.commit()

        sig_id = _mk_signal(
            db, kind="multi_account_same_device",
            details={
                "pfx": pfx, "ip": ip_test, "user_agent": ua_test,
                "window_hours": 24, "threshold": 3,
            },
            count=4,
        )
        result = auto_remediate_signal(
            db, signal_id=sig_id, by_user_id=sa_id, autocommit=True,
        )
        check("multi_account: ok=True", result.ok, str(result))
        check("multi_account: action=revoke_sessions",
              result.action == "revoke_sessions")
        check("multi_account: 4 oturum kapatıldı",
              result.affected_count >= 4, f"got {result.affected_count}")

        still_live = (
            db.query(ActiveSession)
            .filter(
                ActiveSession.user_agent == ua_test,
                ActiveSession.terminated_at.is_(None),
            )
            .count()
        )
        check("multi_account: hayatta oturum kalmadı",
              still_live == 0, f"{still_live} oturum hayatta")
        revoked = (
            db.query(ActiveSession)
            .filter(
                ActiveSession.user_agent == ua_test,
                ActiveSession.termination_reason == "admin_revoke",
            )
            .count()
        )
        check("multi_account: termination_reason=admin_revoke",
              revoked >= 4, f"got {revoked}")

    # ---- 4) UNSUBSCRIBE_SPIKE → otomatik aksiyon yok ----
    with SessionLocal() as db:
        sig_id = _mk_signal(
            db, kind="unsubscribe_spike", tenant_id=None,
            details={"pfx": pfx, "window_hours": 24},
            count=15,
        )
        result = auto_remediate_signal(
            db, signal_id=sig_id, by_user_id=sa_id, autocommit=True,
        )
        check("unsubscribe_spike: ok=False (manuel)",
              not result.ok and result.error == "manual_only")
        sig = db.get(AbuseSignal, sig_id)
        check("unsubscribe_spike: sinyal AÇIK kaldı (auto-resolve yok)",
              sig.resolved_at is None)

    # ---- 5) UI helper: get_action_label ----
    check("label: mass_invitation = 'Davetleri iptal et'",
          get_action_label("mass_invitation") == "Davetleri iptal et")
    check("label: unsubscribe_spike = None (gizle)",
          get_action_label("unsubscribe_spike") is None)
    check("label: bilinmeyen kind = None",
          get_action_label("xxx_unknown") is None)
    check("label haritası 4 türü içerir",
          set(ACTION_BUTTON_LABELS_TR.keys()) >= {
              "mass_invitation", "mass_notification",
              "multi_account_same_device", "unsubscribe_spike",
          })

    # ---- 6) HTTP POST /remediate → 303 + audit log ----
    with SessionLocal() as db:
        # Yeni mass_invitation senaryosu HTTP testi için
        now = datetime.now(timezone.utc)
        for i in range(3):
            db.add(ParentInvitation(
                invited_email=f"{pfx}-http-{i}@x.com",
                student_id=student_id,
                invited_by_id=teacher_id,
                relation=ParentRelation.DIGER,
                is_primary=False,
                token=f"{pfx}-http-tok-{i}-{secrets.token_hex(8)}",
                expires_at=now + timedelta(days=7),
                created_at=now - timedelta(minutes=10),
            ))
        db.commit()
        http_sig_id = _mk_signal(
            db, kind="mass_invitation", actor_id=teacher_id,
            details={"pfx": pfx, "window_hours": 1, "threshold": 3},
            count=3,
        )

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
            r = c.post(
                f"/admin/security-monitor/abuse/{http_sig_id}/remediate",
                follow_redirects=False,
            )
            check("HTTP remediate → 303",
                  r.status_code == 303, f"got {r.status_code}")
            location = r.headers.get("location", "")
            check("HTTP remediate → /abuse'a redirect + ok parametre",
                  "/admin/security-monitor/abuse" in location and "ok=" in location,
                  location)

            with SessionLocal() as db2:
                sig = db2.get(AbuseSignal, http_sig_id)
                check("HTTP sonrası sinyal resolved",
                      sig.resolved_at is not None)
                # Audit log yazıldı mı?
                au = (
                    db2.query(AuditLog)
                    .filter(
                        AuditLog.action == AuditAction.ABUSE_REMEDIATION,
                        AuditLog.target_type == "abuse_signal",
                        AuditLog.target_id == http_sig_id,
                    )
                    .first()
                )
                check("Audit log: ABUSE_REMEDIATION yazıldı", au is not None)
                if au is not None:
                    check("Audit log: actor super admin",
                          au.actor_id == sa_id)
                    payload = json.loads(au.details_json or "{}")
                    check("Audit details: kind doğru",
                          payload.get("kind") == "mass_invitation")
                    check("Audit details: action=cancel_invitations",
                          payload.get("action") == "cancel_invitations")
                    check("Audit details: affected_count>=3",
                          (payload.get("affected_count") or 0) >= 3)

            # Aynı sinyalde 2. kez çağırınca → err (already_resolved)
            r2 = c.post(
                f"/admin/security-monitor/abuse/{http_sig_id}/remediate",
                follow_redirects=False,
            )
            check("HTTP remediate 2. çağrı → 303",
                  r2.status_code == 303)
            check("HTTP remediate 2. çağrı → err parametre (already_resolved)",
                  "err=" in r2.headers.get("location", ""),
                  r2.headers.get("location", ""))

            # Bilinmeyen signal_id → err (not_found)
            r3 = c.post(
                "/admin/security-monitor/abuse/99999999/remediate",
                follow_redirects=False,
            )
            check("HTTP remediate bilinmeyen sinyal → 303 + err",
                  r3.status_code == 303
                  and "err=" in r3.headers.get("location", ""))

            # GET sayfasında yeni buton var mı?
            r4 = c.get("/admin/security-monitor/abuse?only_open=0")
            check("Abuse panosunda 'remediate' formu render edilir",
                  "/remediate" in r4.text)
        finally:
            app.dependency_overrides.pop(require_super_admin, None)
            app.dependency_overrides.pop(require_user, None)
            app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        _cleanup(db, pfx)

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
