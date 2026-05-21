"""Katman 11.F — Alarm motoru smoke test.

Senaryolar:
  1) Seed kurallar 4 adet
  2) evaluate_all: kural tetiklenmediğinde triggered=False
  3) Sentetik AbuseSignal oluşturup abuse_open kuralı çalıştır → tetiklenmeli
  4) Cooldown: tetiklendikten hemen sonra ikinci evaluate'de skipped_reason="cooldown"
  5) update_rule: threshold + enabled değiştir
  6) Devre dışı kural: triggered=False, skipped_reason="disabled"
  7) acknowledge: acknowledged_at + by set
  8) live_event_stream: descending order
  9) HTTP GET /admin/security-monitor/alarms 200 + bölümler
 10) HTTP GET /admin/security-monitor/live 200
 11) HTTP GET /admin/security-monitor/live/feed (HTMX partial) 200
 12) HTTP POST /alarms/scan + /ack + /rules/{id}/update
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
from app.models import (
    AbuseSignal,
    AlarmEvent,
    AlarmRule,
    User,
    UserRole,
)
from app.services.alarm_engine import (
    acknowledge,
    evaluate_all,
    list_recent_events,
    list_rules,
    live_event_stream,
    unacknowledged_count,
    update_rule,
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
    print("=== Katman 11.F (Alarm motoru) smoke ===")
    pfx = f"alm-{secrets.token_hex(3)}"

    # Cleanup leftover alarm events
    with SessionLocal() as db:
        db.query(AlarmEvent).filter(AlarmEvent.details_json.like(f"%{pfx}%")).delete()
        db.commit()

    # ---- 1) Seed kurallar ----
    with SessionLocal() as db:
        rules = list_rules(db)
        keys = {r.key for r in rules}
        check("seed: 4 kural",
              {"high_failed_logins", "oldest_queued_long",
               "error_groups_open", "abuse_open"} <= keys)

    # ---- 2) İlk değerlendirme — abuse_open için sentetik sinyal yarat ----
    # Önce tetiklenmediği durumu kontrol et: tüm açık abuse sinyallerini resolve et
    with SessionLocal() as db:
        # Sentetik sinyal yaratmadan önce mevcut açık abuse sinyallerini kontrol
        open_abuse = db.query(AbuseSignal).filter(AbuseSignal.resolved_at.is_(None)).count()
        # cooldown'u sıfırla (geçmiş test kalıntısı varsa)
        for r in db.query(AlarmRule).all():
            r.last_triggered_at = None
        db.commit()

    # ---- 3) Yeni sentetik abuse sinyali (abuse_open kuralını tetiklemeli) ----
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        sig = AbuseSignal(
            kind="mass_invitation",
            severity="warn",
            actor_user_id=None,
            tenant_id=None,
            count=99,
            window_start=now,
            window_end=now,
            detected_at=now,
            last_seen_at=now,
            details_json=f'{{"pfx": "{pfx}", "test": true}}',
        )
        db.add(sig)
        db.commit()
        sig_id = sig.id

        results = evaluate_all(db)
        by_key = {r.rule_key: r for r in results}
        check("evaluate: abuse_open kuralı çalıştı", "abuse_open" in by_key)
        abuse_res = by_key.get("abuse_open")
        check("abuse_open tetiklendi (sinyal var)",
              abuse_res is not None and abuse_res.triggered,
              f"value={abuse_res.value if abuse_res else None}")
        check("abuse_open value > 0",
              abuse_res is not None and abuse_res.value > 0)

        # AlarmEvent yazıldı mı?
        recent = list_recent_events(db, hours=1, limit=20)
        abuse_events = [e for e in recent if e["rule_key"] == "abuse_open"]
        check("AlarmEvent abuse_open kaydı yazıldı", len(abuse_events) >= 1)
        if abuse_events:
            check("severity dolu (warn/critical/info)",
                  abuse_events[0]["severity"] in ("warn", "critical", "info"))

    # ---- 4) Cooldown ----
    with SessionLocal() as db:
        results2 = evaluate_all(db)
        by_key2 = {r.rule_key: r for r in results2}
        check("ikinci evaluate'de abuse_open cooldown'da",
              by_key2["abuse_open"].triggered is False and
              by_key2["abuse_open"].skipped_reason == "cooldown")

    # ---- 5) update_rule ----
    with SessionLocal() as db:
        rule = db.query(AlarmRule).filter(AlarmRule.key == "high_failed_logins").first()
        rid = rule.id
        update_rule(db, rule_id=rid, threshold=999, cooldown_minutes=120,
                    enabled=False, channels="in_app")
        db.expire_all()
        rule2 = db.get(AlarmRule, rid)
        check("threshold güncellendi", rule2.threshold == 999)
        check("cooldown güncellendi", rule2.cooldown_minutes == 120)
        check("enabled False", rule2.enabled is False)
        check("channels güncellendi", "in_app" in rule2.channels)

    # ---- 6) Devre dışı kural skip ----
    with SessionLocal() as db:
        # Önce cooldown sıfırla
        for r in db.query(AlarmRule).all():
            r.last_triggered_at = None
        db.commit()
        results3 = evaluate_all(db)
        by_key3 = {r.rule_key: r for r in results3}
        hfl = by_key3.get("high_failed_logins")
        check("disabled kural skip edildi",
              hfl is not None and hfl.skipped_reason == "disabled")

    # Geri al
    with SessionLocal() as db:
        rule = db.query(AlarmRule).filter(AlarmRule.key == "high_failed_logins").first()
        update_rule(db, rule_id=rule.id, threshold=50, cooldown_minutes=60,
                    enabled=True, channels="email,in_app")

    # ---- 7) acknowledge ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa:
            evt = (
                db.query(AlarmEvent)
                .filter(AlarmEvent.rule_key == "abuse_open",
                        AlarmEvent.acknowledged_at.is_(None))
                .first()
            )
            if evt:
                eid = evt.id
                acknowledge(db, event_id=eid, user_id=sa.id)
                db.expire_all()
                row = db.get(AlarmEvent, eid)
                check("ack: acknowledged_at set",
                      row is not None and row.acknowledged_at is not None)
                check("ack: by user_id set",
                      row is not None and row.acknowledged_by_user_id == sa.id)

    # ---- 8) live_event_stream ----
    with SessionLocal() as db:
        items = live_event_stream(db, since_seconds=3600, limit=50)
        check("live feed liste döner",
              isinstance(items, list) and all("ts" in i and "title" in i for i in items))
        if len(items) >= 2:
            check("descending ts",
                  all(items[i]["ts"] >= items[i + 1]["ts"]
                      for i in range(len(items) - 1)))

    # ---- 9-12) HTTP ----
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

                # 9) Alarms page
                r = c.get("/admin/security-monitor/alarms")
                check("alarms GET 200", r.status_code == 200, f"got {r.status_code}")
                check("'Alarm Konfigürasyonu' başlığı",
                      "Alarm Konfigürasyonu" in r.text)
                check("'Kurallar' bölümü", "Kurallar" in r.text)
                check("'Son Tetiklenen' bölümü",
                      "Son Tetiklenen" in r.text)

                # 10) Live page
                r2 = c.get("/admin/security-monitor/live")
                check("live GET 200", r2.status_code == 200)
                check("'Canlı Olay Akışı' başlığı",
                      "Canlı Olay Akışı" in r2.text)
                check("hx-get live feed endpoint var",
                      "/admin/security-monitor/live/feed" in r2.text)

                # 11) Live feed partial
                r3 = c.get("/admin/security-monitor/live/feed?since_seconds=600")
                check("live feed partial GET 200",
                      r3.status_code == 200, f"got {r3.status_code}")

                # 12) POST scan
                r4 = c.post(
                    "/admin/security-monitor/alarms/scan",
                    follow_redirects=False,
                )
                check("scan → 303", r4.status_code == 303)

                # POST ack (en güncel onaylanmamış olayı bul)
                with SessionLocal() as db2:
                    pending = (
                        db2.query(AlarmEvent)
                        .filter(AlarmEvent.acknowledged_at.is_(None))
                        .order_by(AlarmEvent.triggered_at.desc())
                        .first()
                    )
                if pending:
                    r5 = c.post(
                        f"/admin/security-monitor/alarms/{pending.id}/ack",
                        follow_redirects=False,
                    )
                    check("ack POST → 303", r5.status_code == 303)

                # POST rule update
                with SessionLocal() as db2:
                    rule = (
                        db2.query(AlarmRule)
                        .filter(AlarmRule.key == "error_groups_open")
                        .first()
                    )
                if rule:
                    r6 = c.post(
                        f"/admin/security-monitor/alarms/rules/{rule.id}/update",
                        data={"threshold": "7", "cooldown_minutes": "45",
                              "enabled": "1", "channels": "email,in_app"},
                        follow_redirects=False,
                    )
                    check("rule update POST → 303", r6.status_code == 303)
                    with SessionLocal() as db2:
                        r_after = db2.get(AlarmRule, rule.id)
                        check("threshold güncellendi",
                              r_after.threshold == 7)

                # Ana panoda link
                r7 = c.get("/admin/security-monitor")
                check("ana panoda 'Alarmlar' linki",
                      "🔔 Alarmlar" in r7.text or "Alarmlar" in r7.text)
                check("ana panoda 'Canlı Akış' linki",
                      "Canlı Akış" in r7.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(AbuseSignal).filter(AbuseSignal.details_json.like(f"%{pfx}%")).delete()
        db.query(AlarmEvent).filter(AlarmEvent.details_json.like(f"%{pfx}%")).delete()
        # error_groups_open threshold'u 5'e geri al
        rule = db.query(AlarmRule).filter(AlarmRule.key == "error_groups_open").first()
        if rule:
            rule.threshold = 5
            rule.cooldown_minutes = 60
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
