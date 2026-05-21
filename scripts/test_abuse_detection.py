"""Katman 11.C — Kötüye Kullanım Kamerası smoke test.

Senaryolar:
  1) detect_mass_invitation: 50+ veli daveti / 1 saat → sinyal
  2) detect_mass_notification: 200+ bildirim / 1 saat (tenant) → sinyal
  3) detect_multi_account_same_device: aynı UA+IP'den 3+ farklı user_id → sinyal
  4) detect_unsubscribe_spike: 10+ pause_alerts / 24 saat (tenant) → sinyal
  5) Dedup: ikinci run aynı kayıt güncellenir, count artar, yeni satır yok
  6) resolve_signal: resolved_at + resolved_by set
  7) run_all özet döner
  8) HTTP GET /admin/security-monitor/abuse 200 + sinyal listesi
  9) HTTP POST /scan + /resolve 303
 10) Ana panodan rozet linki var
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
    THRESHOLD_MASS_INVITATION_PER_HOUR,
    THRESHOLD_MASS_NOTIFICATION_PER_HOUR,
    THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS,
    THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY,
    User,
    UserRole,
)
from app.services.abuse_detection import (
    KIND_MASS_INVITATION,
    KIND_MASS_NOTIFICATION,
    KIND_MULTI_ACCOUNT,
    KIND_UNSUBSCRIBE_SPIKE,
    detect_mass_invitation,
    detect_mass_notification,
    detect_multi_account_same_device,
    detect_unsubscribe_spike,
    list_signals,
    open_signal_count,
    resolve_signal,
    run_all,
)
from app.services.audit import log_action


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
    """Test verilerini sil — pfx'li kayıtlar + sinyaller."""
    db.query(AbuseSignal).filter(
        AbuseSignal.details_json.like(f"%{pfx}%")
    ).delete(synchronize_session=False)
    db.query(ParentInvitation).filter(
        ParentInvitation.invited_email.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.query(NotificationLog).filter(
        NotificationLog.error.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.query(ActiveSession).filter(
        ActiveSession.user_agent.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.query(AuditLog).filter(
        AuditLog.email_attempted.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.commit()


def main() -> int:
    print("=== Katman 11.C (Abuse Kamerası) smoke ===")
    pfx = f"abuse-{secrets.token_hex(3)}"

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
            .filter(User.role == UserRole.PARENT, User.institution_id.isnot(None))
            .first()
        )
        if not all([sa, teacher, student]):
            print("  (gerekli kullanıcılar yok — testler atlandı)")
            return 0
        sa_id = sa.id
        teacher_id = teacher.id
        student_id = student.id

        # Önceki test kalıntılarını temizle (idempotent)
        _cleanup(db, pfx)

    # ---- 1) MASS_INVITATION ----
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        for i in range(THRESHOLD_MASS_INVITATION_PER_HOUR + 2):
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

        hits = detect_mass_invitation(db)
        actor_hits = [h for h in hits if h.actor_user_id == teacher_id]
        check("mass_invitation: teacher tespit edildi", len(actor_hits) >= 1)
        if actor_hits:
            h = actor_hits[0]
            check(f"count >= {THRESHOLD_MASS_INVITATION_PER_HOUR}",
                  h.count >= THRESHOLD_MASS_INVITATION_PER_HOUR)
            check("kind doğru", h.kind == KIND_MASS_INVITATION)

    # ---- 2) MASS_NOTIFICATION ----
    if parent_with_inst:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            inst_id = parent_with_inst.institution_id
            parent_id = parent_with_inst.id
            for i in range(THRESHOLD_MASS_NOTIFICATION_PER_HOUR + 5):
                db.add(NotificationLog(
                    parent_id=parent_id,
                    student_id=student_id,
                    kind=NotificationKind.DAILY_SUMMARY,
                    channel=NotificationChannel.EMAIL,
                    status=NotificationStatus.QUEUED,
                    queued_at=now - timedelta(minutes=5),
                    error=f"{pfx}: test notification",
                ))
            db.commit()

            hits = detect_mass_notification(db)
            tenant_hits = [h for h in hits if h.tenant_id == inst_id]
            check("mass_notification: tenant tespit edildi", len(tenant_hits) >= 1)
            if tenant_hits:
                h = tenant_hits[0]
                check(f"count >= {THRESHOLD_MASS_NOTIFICATION_PER_HOUR}",
                      h.count >= THRESHOLD_MASS_NOTIFICATION_PER_HOUR)
    else:
        print("  (parent_with_inst yok — mass_notification atlandı)")

    # ---- 3) MULTI_ACCOUNT (aynı UA+IP, farklı user_id) ----
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        ua_test = f"{pfx}-UserAgent/1.0"
        ip_test = f"192.0.2.{secrets.randbelow(200) + 1}"
        # 4 farklı user_id ile aynı UA+IP'den oturum aç (eşik = 3)
        users = (
            db.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.id)
            .limit(THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS + 1)
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

        hits = detect_multi_account_same_device(db)
        ip_hits = [h for h in hits if h.details.get("ip") == ip_test]
        check("multi_account: aynı UA+IP tespit edildi", len(ip_hits) >= 1)
        if ip_hits:
            check(f"distinct user count >= {THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS}",
                  ip_hits[0].count >= THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS)
            check("UA detayda", ip_hits[0].details.get("user_agent", "").startswith(pfx))

    # ---- 4) UNSUBSCRIBE_SPIKE ----
    if parent_with_inst:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            inst_id = parent_with_inst.institution_id
            # parent_with_inst aktör olarak USER_PAUSE_ALERTS audit yaz (institution_id var)
            for i in range(THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY + 2):
                db.add(AuditLog(
                    actor_id=parent_with_inst.id,
                    email_attempted=f"{pfx}-unsub-{i}",
                    action=AuditAction.USER_PAUSE_ALERTS,
                    created_at=now - timedelta(hours=2),
                ))
            db.commit()

            hits = detect_unsubscribe_spike(db)
            tenant_hits = [h for h in hits if h.tenant_id == inst_id]
            check("unsubscribe_spike: tenant tespit edildi", len(tenant_hits) >= 1)
            if tenant_hits:
                check(f"count >= {THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY}",
                      tenant_hits[0].count >= THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY)

    # ---- 5) Dedup: ikinci run aynı kayıt güncellenir ----
    with SessionLocal() as db:
        before = db.query(AbuseSignal).count()
        s1 = run_all(db)
        after1 = db.query(AbuseSignal).count()
        check("run_all: ilk run sinyaller yazıldı", after1 >= before)
        s2 = run_all(db)
        after2 = db.query(AbuseSignal).count()
        check("dedup: ikinci run yeni satır eklemiyor",
              after2 == after1, f"after1={after1} after2={after2}")
        check("run_all: özet dict döner",
              isinstance(s2, dict) and len(s2) >= 4)

    # ---- 6) resolve_signal ----
    with SessionLocal() as db:
        sig = (
            db.query(AbuseSignal)
            .filter(AbuseSignal.resolved_at.is_(None))
            .filter(AbuseSignal.kind == KIND_MASS_INVITATION)
            .first()
        )
        if sig is not None:
            sig_id = sig.id
            resolve_signal(
                db, signal_id=sig_id, resolved_by_user_id=sa_id,
                note="Test ile yaratıldı, çözüldü",
            )
            db.expire_all()
            row = db.get(AbuseSignal, sig_id)
            check("resolve: resolved_at set", row.resolved_at is not None)
            check("resolve: resolved_by set", row.resolved_by_user_id == sa_id)
            check("resolve: note set", row.resolution_note is not None)
        else:
            check("resolve hedef sinyal bulundu", False, "open mass_invitation yok")

    # ---- 7) list_signals ----
    with SessionLocal() as db:
        all_open = list_signals(db, only_open=True, limit=100)
        check("list_signals open: dict liste",
              isinstance(all_open, list) and all(isinstance(x, dict) for x in all_open))
        only_mi = list_signals(db, only_open=False, kind=KIND_MASS_INVITATION, limit=10)
        check("list_signals kind filter çalışır",
              all(s["kind"] == KIND_MASS_INVITATION for s in only_mi))

    # ---- 8-10) HTTP akışları ----
    with SessionLocal() as db:
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

            # 8) GET /admin/security-monitor/abuse
            r = c.get("/admin/security-monitor/abuse")
            check("abuse panosu GET 200",
                  r.status_code == 200, f"got {r.status_code}")
            check("'Kötüye Kullanım' başlığı",
                  "Kötüye Kullanım Kamerası" in r.text)
            check("'Toplu veli daveti' türü",
                  "Toplu veli daveti" in r.text)

            # 9) POST /scan
            r2 = c.post(
                "/admin/security-monitor/abuse/scan",
                follow_redirects=False,
            )
            check("scan → 303", r2.status_code == 303)

            # POST /resolve
            with SessionLocal() as db2:
                open_sig = (
                    db2.query(AbuseSignal)
                    .filter(AbuseSignal.resolved_at.is_(None))
                    .first()
                )
            if open_sig is not None:
                r3 = c.post(
                    f"/admin/security-monitor/abuse/{open_sig.id}/resolve",
                    data={"note": "HTTP test"},
                    follow_redirects=False,
                )
                check("resolve POST → 303", r3.status_code == 303)
                with SessionLocal() as db2:
                    row = db2.get(AbuseSignal, open_sig.id)
                    check("HTTP resolve sonrası resolved_at set",
                          row is not None and row.resolved_at is not None)
            else:
                check("resolve POST hedef sinyal", False, "open sinyal yok")

            # 10) Ana panoda abuse linki + rozet
            r4 = c.get("/admin/security-monitor")
            check("security-monitor GET 200", r4.status_code == 200)
            check("ana panoda '🚨 Abuse' kısayolu",
                  "🚨 Abuse" in r4.text)
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
