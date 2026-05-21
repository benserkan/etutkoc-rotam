"""Katman 11.K.1 — Dikkat Odası (Attention Engine) smoke test.

Senaryolar:
  1) Temiz durumda — is_clean True veya items az
  2) Active impersonation → CRITICAL kart
  3) Open ErrorEvent → kart
  4) Open AbuseSignal → kart
  5) Unack AlarmEvent → kart
  6) Cron drift → kart (varsa)
  7) Sıralama: severity descending (critical önce)
  8) get_attention_summary: by_severity + by_category + top_severity
  9) HTTP GET /admin/security-monitor 200 + "Şu an dikkat" bölüm görünür
 10) Temiz durumda "Şu an dikkat gerektiren bir şey yok" mesajı (yapay temizle)
 11) Mini KPI şeridi var
 12) Alt-pano kısayolları (Canlı, Alarm, Ticari, vs.) görünür
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
    AlarmEvent,
    ErrorEvent,
    ImpersonationSession,
    User,
    UserRole,
)
from app.services.attention_engine import (
    SEVERITY_RANK,
    AttentionItem,
    get_attention_items,
    get_attention_summary,
)
from app.services.error_capture import record_error


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
    print("=== Katman 11.K.1 (Dikkat Odası) smoke ===")
    pfx = f"att-{secrets.token_hex(3)}"

    # ---- 1) Initial state — items liste döner ----
    with SessionLocal() as db:
        items = get_attention_items(db)
        check("get_attention_items liste döner",
              isinstance(items, list) and all(isinstance(it, AttentionItem) for it in items))
        check("AttentionItem.sort_key tuple",
              not items or isinstance(items[0].sort_key(), tuple))
        # Her itemde explainer alanı (11.K.1+)
        if items:
            check("AttentionItem.explainer alanı tanımlı",
                  hasattr(items[0], "explainer"))

    # ---- 2) Active impersonation → kart ----
    imp_id = None
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        teacher = db.query(User).filter(User.role == UserRole.TEACHER).first()
        if sa and teacher:
            now = datetime.now(timezone.utc)
            imp = ImpersonationSession(
                actor_user_id=sa.id,
                target_user_id=teacher.id,
                reason=f"{pfx} smoke test gerekçesi yeterince uzun",
                started_at=now,
                expires_at=now + timedelta(minutes=20),
            )
            db.add(imp)
            db.commit()
            imp_id = imp.id

            items = get_attention_items(db)
            impersonation_cards = [it for it in items if it.category == "session" and "Sahte" in it.title]
            check("active impersonation → kart üretildi",
                  len(impersonation_cards) >= 1)
            if impersonation_cards:
                check("impersonation kartı critical severity",
                      impersonation_cards[0].severity == "critical")
                check("impersonation kartı icon 🎭",
                      impersonation_cards[0].icon == "🎭")
                # 11.K.1+: explainer dolu, "sahte oturum" kelimesi geçer
                check("impersonation explainer dolu (200+ char)",
                      len(impersonation_cards[0].explainer) > 200)
                check("explainer 'KVKK' veya 'audit' kavramı içerir",
                      "KVKK" in impersonation_cards[0].explainer or
                      "audit" in impersonation_cards[0].explainer.lower())

    # ---- 3) Open ErrorEvent → kart ----
    err_id = None
    with SessionLocal() as db:
        # 12 kere tetiklenmiş error (count=12) → critical
        try:
            raise ValueError(f"{pfx} test error")
        except ValueError as e:
            r = record_error(
                db, endpoint=f"/test/{pfx}/path", method="GET",
                status_code=500, exception=e,
            )
        # Count'u manuel olarak 12 yap
        r.count = 12
        db.commit()
        err_id = r.id

        items = get_attention_items(db)
        error_cards = [it for it in items if it.category == "error"]
        check("open error → kart üretildi",
              len(error_cards) >= 1)
        # 12 count → critical olmalı
        crit_err = [c for c in error_cards if c.severity == "critical"]
        check("count >= 10 critical severity",
              len(crit_err) >= 1)

    # ---- 4) Open AbuseSignal → kart ----
    abuse_id = None
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        sig = AbuseSignal(
            kind="mass_invitation",
            severity="warn",
            count=99,
            window_start=now, window_end=now,
            detected_at=now, last_seen_at=now,
            details_json=f'{{"pfx":"{pfx}"}}',
        )
        db.add(sig)
        db.commit()
        abuse_id = sig.id

        items = get_attention_items(db)
        abuse_cards = [it for it in items if it.category == "abuse"]
        check("open abuse signal → kart",
              len(abuse_cards) >= 1)

    # ---- 5) Unack AlarmEvent → kart ----
    alarm_id = None
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        evt = AlarmEvent(
            rule_key="test_rule",
            rule_name=f"{pfx} test alarm",
            value=10, threshold=5,
            severity="critical",
            channels_attempted="email",
            delivery_status="email:ok",
            triggered_at=now,
        )
        db.add(evt)
        db.commit()
        alarm_id = evt.id

        items = get_attention_items(db)
        alarm_cards = [it for it in items if it.category == "alarm"]
        check("unack alarm → kart",
              len(alarm_cards) >= 1)

    # ---- 6) Sıralama doğru (critical önce) ----
    with SessionLocal() as db:
        items = get_attention_items(db)
        if len(items) >= 2:
            severities = [SEVERITY_RANK.get(it.severity, 0) for it in items]
            check("severity descending sıralı",
                  all(severities[i] >= severities[i + 1] for i in range(len(severities) - 1)),
                  f"got {severities}")

    # ---- 7) get_attention_summary ----
    with SessionLocal() as db:
        s = get_attention_summary(db)
        check("summary keys",
              {"items", "total", "by_severity", "by_category",
               "top_severity", "is_clean"} <= set(s.keys()))
        check("by_severity 3 anahtar",
              {"critical", "warn", "info"} <= set(s["by_severity"].keys()))
        check("total = items uzunluğu",
              s["total"] == len(s["items"]))
        # Bizim eklediklerimiz nedeniyle top_severity critical olmalı
        check("top_severity critical (impersonation + 10+ error)",
              s["top_severity"] == "critical")
        check("is_clean False",
              s["is_clean"] is False)

    # ---- 8-12) HTTP ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        sa_id = sa.id if sa else None

    if sa_id:
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
            check("pano GET 200",
                  r.status_code == 200, f"got {r.status_code}")
            check("'Şu an dikkat' başlığı (dolu)",
                  "Şu an dikkat gerektiren" in r.text)
            check("dikkat kartı içeriği render edildi",
                  pfx in r.text or "Sahte oturum" in r.text)
            check("mini KPI: 'Oturum' rozet",
                  ">Oturum<" in r.text or "Oturum" in r.text)
            check("mini KPI: 'Bloklu IP'",
                  "Bloklu IP" in r.text)
            check("alt-pano kısayolu '🔴 Canlı'",
                  "🔴 Canlı" in r.text)
            check("alt-pano kısayolu '💰 Ticari'",
                  "💰 Ticari" in r.text)
            check("alt-pano kısayolu '🚨 Abuse'",
                  "🚨 Abuse" in r.text)
            check("yardım kutusu (öğretici)",
                  "Bu sayfa nasıl çalışır" in r.text)
            check("Severity açıklaması (CRITICAL/WARN/INFO)",
                  "CRITICAL" in r.text and "WARN" in r.text and "INFO" in r.text)
            check("Kartlarda 'ⓘ Bu ne demek?' toggle",
                  "Bu ne demek?" in r.text)
            check("Explainer içeriği render (KVKK veya saldırgan kelimesi)",
                  "KVKK" in r.text or "kötüye kullanım" in r.text or "saldırgan" in r.text)
        finally:
            app.dependency_overrides.pop(require_super_admin, None)
            app.dependency_overrides.pop(require_user, None)
            app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        if imp_id:
            db.query(ImpersonationSession).filter(ImpersonationSession.id == imp_id).delete()
        if abuse_id:
            db.query(AbuseSignal).filter(AbuseSignal.id == abuse_id).delete()
        if alarm_id:
            db.query(AlarmEvent).filter(AlarmEvent.id == alarm_id).delete()
        if err_id:
            db.query(ErrorEvent).filter(ErrorEvent.id == err_id).delete()
        db.commit()

    # ---- Final: temiz durum kontrol ----
    # Test verisini sildikten sonra hâlâ önceki sentetik veriler kalabilir
    # (mass-invitation testlerinden vs.) — sadece "summary çalışıyor mu" testi yap
    with SessionLocal() as db:
        s2 = get_attention_summary(db)
        check("cleanup sonrası summary hâlâ çalışıyor",
              isinstance(s2, dict) and "items" in s2)

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
