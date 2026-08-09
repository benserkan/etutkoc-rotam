"""Alarm Teşhis Kartı smoke (2026-08-09).

NEDEN: alarm körlüğü tekrarlayan bir sorun. Panelde alarmın "hâlâ geçerli mi",
"kimi ilgilendiriyor", "ne yapmalıyım" ve "bu yanlış alarmdı" bilgisi yoktu.
Bu paket o dört yüzeyi kilitler.

Senaryolar:
   1. diagnose Teacher → 403
   2. diagnose Anonim → 401
   3. diagnose bilinmeyen olay → 404
   4. diagnose happy — rehber alanları dolu (ne oldu/neden/ne yapmalı)
   5. canlı yeniden değerlendirme çalışıyor (guncel_deger + hala_gecerli)
   6. TÜM yerleşik kurallarda rehber TANIMLI (yeni kural eklenince kırılır)
   7. TÜM kanıt çözücüleri patlamadan çalışır
   8. resolve happy → resolved + ack birlikte damgalanır
   9. resolve notu kaydedilir
  10. false_positive işareti kaydedilir
  11. kural listesinde false_positive_30d sayılır
  12. resolve bilinmeyen olay → 404
  13. resolve Teacher → 403
  14. gürültü uyarısı: 3+ yanlış alarm → gurultu_uyarisi True
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import AlarmEvent, AuditLog, SuspiciousIp, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"alrmdx_{secrets.token_hex(3)}"
PASSWORD = "AlarmDx2026!x"
gecti = kaldi = 0


def check(ad: str, kosul: bool, detay: str = "") -> None:
    global gecti, kaldi
    if kosul:
        gecti += 1
        print(f"  [PASS] {ad}")
    else:
        kaldi += 1
        print(f"  [FAIL] {ad} {detay}")


def login(c: TestClient, email: str) -> bool:
    get_login_limiter().reset()
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    return r.status_code == 200


def main() -> int:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        admin = User(email=f"{PFX}-a@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Teşhis Admin", role=UserRole.SUPER_ADMIN,
                     is_active=True, must_change_password=False)
        koc = User(email=f"{PFX}-k@t.invalid", password_hash=hash_password(PASSWORD),
                   full_name="Teşhis Koç", role=UserRole.TEACHER, is_active=True,
                   plan="solo_free", must_change_password=False)
        db.add_all([admin, koc])
        db.commit()
        admin_id, koc_id = admin.id, koc.id

        ev = AlarmEvent(
            rule_key="moment_silent",
            rule_name="Bağlamsal uyarı gösterilmedi (moment sessiz)",
            value=1, threshold=0, severity="warn",
            channels_attempted="in_app", delivery_status="in_app:ok",
            triggered_at=now - timedelta(hours=2),
        )
        db.add(ev)
        db.commit()
        ev_id = ev.id

    c = TestClient(app)
    try:
        # --- 1-2) yetki ---
        print("\n1) Yetki kapıları")
        check("anonim diagnose → 401",
              c.get(f"/api/v2/admin/security-monitor/alarms/{ev_id}/diagnose")
              .status_code == 401)
        assert login(c, f"{PFX}-k@t.invalid")
        check("koç diagnose → 403",
              c.get(f"/api/v2/admin/security-monitor/alarms/{ev_id}/diagnose")
              .status_code == 403)
        check("koç resolve → 403",
              c.post(f"/api/v2/admin/security-monitor/alarms/{ev_id}/resolve",
                     json={"note": "", "false_positive": False}).status_code == 403)
        c.post("/api/v2/auth/logout")

        assert login(c, f"{PFX}-a@t.invalid")
        check("bilinmeyen olay diagnose → 404",
              c.get("/api/v2/admin/security-monitor/alarms/99999999/diagnose")
              .status_code == 404)
        check("bilinmeyen olay resolve → 404",
              c.post("/api/v2/admin/security-monitor/alarms/99999999/resolve",
                     json={"note": "", "false_positive": False}).status_code == 404)

        # --- 3) teşhis içeriği ---
        print("\n2) Teşhis kartı içeriği")
        r = c.get(f"/api/v2/admin/security-monitor/alarms/{ev_id}/diagnose")
        check("diagnose 200", r.status_code == 200, r.text[:160])
        d = r.json()
        check("ne oldu / neden dolu", bool(d["ne_oldu"]) and bool(d["neden"]))
        check("ne yapmalı en az 2 adım", len(d["ne_yapmali"]) >= 2, str(d["ne_yapmali"]))
        check("ilgili bağlantı var", len(d["baglantilar"]) >= 1)
        check("sorumlu etiketi geçerli",
              d["sorumlu"] in ("sen", "kod", "saglayici"), d["sorumlu"])
        check("canlı yeniden değerlendirme yapıldı",
              d["degerlendirme_hatasi"] is None and d["guncel_deger"] is not None,
              str(d.get("degerlendirme_hatasi")))
        check("hala_gecerli bool", isinstance(d["hala_gecerli"], bool))
        check("kanıt listesi döndü (liste tipi)", isinstance(d["kanit"], list))

        # --- 4) her kural için rehber + kanıt ---
        print("\n3) Tüm kurallar kapsanıyor mu?")
        from app.services.alarm_diagnosis import GUIDES, evidence_for
        from app.services.alarm_engine import EVALUATORS

        eksik = [k for k in EVALUATORS if k not in GUIDES]
        check("her yerleşik kuralın teşhis rehberi var", not eksik,
              f"rehbersiz: {eksik}")

        with SessionLocal() as db:
            patlayan = []
            for key in EVALUATORS:
                try:
                    evidence_for(db, key)
                except Exception as exc:  # noqa: BLE001
                    patlayan.append(f"{key}:{exc}")
            check("tüm kanıt çözücüleri patlamadan çalışır", not patlayan,
                  str(patlayan))

        # --- 5) çözümleme ---
        print("\n4) Çözümleme (çözüldü / yanlış alarm)")
        r = c.post(f"/api/v2/admin/security-monitor/alarms/{ev_id}/resolve",
                   json={"note": "Kanıt incelendi, uyarı gösterilmiş.",
                         "false_positive": False})
        check("resolve 200", r.status_code == 200, r.text[:160])
        with SessionLocal() as db:
            ev = db.get(AlarmEvent, ev_id)
            check("resolved_at damgalandı", ev.resolved_at is not None)
            check("çözmek görmeyi de kapsar (ack)", ev.acknowledged_at is not None)
            check("çözüm notu kaydedildi",
                  (ev.resolution_note or "").startswith("Kanıt incelendi"),
                  str(ev.resolution_note))
            check("yanlış alarm değil", ev.false_positive is False)

        # --- 6) yanlış alarm + sayaç ---
        print("\n5) Yanlış alarm işareti ve kural rozeti")
        yeni_ids = []
        with SessionLocal() as db:
            for i in range(3):
                e = AlarmEvent(
                    rule_key="moment_silent", rule_name="Bağlamsal uyarı gösterilmedi",
                    value=1, threshold=0, severity="warn",
                    channels_attempted="in_app", delivery_status="in_app:ok",
                    triggered_at=now - timedelta(hours=3 + i),
                )
                db.add(e)
                db.commit()
                yeni_ids.append(e.id)
        for eid in yeni_ids:
            c.post(f"/api/v2/admin/security-monitor/alarms/{eid}/resolve",
                   json={"note": "Koç panele hiç girmemiş.", "false_positive": True})
        with SessionLocal() as db:
            e = db.get(AlarmEvent, yeni_ids[0])
            check("false_positive kaydedildi", e.false_positive is True)

        r = c.get("/api/v2/admin/security-monitor/alarms")
        kural = next((x for x in r.json()["rules"] if x["key"] == "moment_silent"), None)
        check("kural listesinde false_positive_30d sayılıyor",
              kural is not None and kural["false_positive_30d"] >= 3,
              str(kural and kural["false_positive_30d"]))

        r = c.get(f"/api/v2/admin/security-monitor/alarms/{yeni_ids[0]}/diagnose")
        dd = r.json()
        check("gürültü uyarısı yükseldi", dd["gurultu_uyarisi"] is True,
              f"yanlış={dd['son_30g_yanlis_alarm']} tetik={dd['son_30g_tetik']}")
        check("çözülmüş alarm teşhiste çözülmüş görünür",
              dd["resolved_at"] is not None and dd["false_positive"] is True)
    finally:
        with SessionLocal() as db:
            ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}-%")).all()]
            db.execute(sa_delete(AlarmEvent).where(
                AlarmEvent.rule_key == "moment_silent",
                AlarmEvent.resolution_note.in_([
                    "Kanıt incelendi, uyarı gösterilmiş.",
                    "Koç panele hiç girmemiş.",
                ])))
            if ids:
                db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}-%")))
            db.commit()

    print(f"\n=== {gecti} passed, {kaldi} failed ===")
    return 0 if kaldi == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
