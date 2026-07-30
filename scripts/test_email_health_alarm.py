"""E-posta sağlığı alarmı smoke (2026-07-30).

Bağlam: ZeptoMail deneme süresi 21 Temmuz'da dolunca SMTP 535 vermeye başladı;
e-posta gönderimi 10 GÜN tamamen durdu ve kimse fark etmedi. İki sebep:
  (a) e-posta teslimatını ölçen bir alarm kuralı YOKtu,
  (b) var olan alarmlar da e-postayla gönderiliyordu → kesinti kendini susturdu.

Senaryolar:
  1.  Örnek yetersizken (az gönderim) alarm YOK — yanlış alarm koruması
  2.  Sağlıklı gönderimde değer düşük
  3.  Tam kesinti (%100 başarısız) → değer 100
  4.  Kısmi kesinti (%50) → değer 50
  5.  queued/suppressed sayılmaz (henüz denenmedi / bilinçli gönderilmedi)
  6.  Yerleşik kural idempotent eklenir + push kanalı ÖNCE tanımlı
  7.  evaluate_all tam kesintide alarmı tetikler + severity critical
  8.  Cooldown: ikinci değerlendirme tetiklemez (alarm yorgunluğu)
  9.  E-posta alıcıları = süper admin + ALARM_EXTRA_EMAILS (tekilleştirilmiş)
  10. Pano bandı (degraded) alarm eşiğiyle AYNI sonucu verir
  11. unacknowledged_count rozeti artar (in_app kanalı görünür olsun)
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

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import AlarmEvent, AlarmRule, CommunicationLog, User, UserRole
from app.services import alarm_engine as ae
from app.services.security import hash_password

PFX = f"mailalarm_{secrets.token_hex(3)}"
RULE_KEY = "email_delivery_failing"

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


def _wipe_logs(db) -> None:
    """Testin penceresindeki TÜM e-posta kaydını sil (değer global hesaplanır)."""
    since = datetime.now(timezone.utc) - timedelta(hours=ae.EMAIL_HEALTH_WINDOW_HOURS + 1)
    db.execute(
        sa_delete(CommunicationLog).where(CommunicationLog.created_at >= since)
    )
    db.commit()


def _add_logs(db, *, status: str, n: int) -> None:
    now = datetime.now(timezone.utc)
    for i in range(n):
        db.add(CommunicationLog(
            channel="email", category=f"{PFX}_cat", to_address=f"{PFX}{i}@test.invalid",
            subject="test", status=status, provider="zeptomail",
            error="(535, b'Authentication Failed')" if status == "failed" else None,
            created_at=now - timedelta(minutes=5),
        ))
    db.commit()


def main() -> int:
    print(f"\n=== E-posta sağlığı alarmı — prefix: {PFX} ===\n")
    admin_id = None
    saved_rows: list[dict] = []

    with SessionLocal() as db:
        # Mevcut (gerçek) e-posta kayıtlarını yedekle — test penceresi global.
        since = datetime.now(timezone.utc) - timedelta(hours=ae.EMAIL_HEALTH_WINDOW_HOURS + 1)
        for r in db.query(CommunicationLog).filter(
            CommunicationLog.created_at >= since
        ).all():
            saved_rows.append({
                c.name: getattr(r, c.name) for c in CommunicationLog.__table__.columns
            })
        print(f"  {len(saved_rows)} mevcut e-posta kaydı yedeklendi\n")

        admin = User(
            email=f"{PFX}@test.invalid", password_hash=hash_password("X1y2Z3!aBcDeFg"),
            full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN, is_active=True,
        )
        db.add(admin)
        db.commit()
        admin_id = admin.id

    try:
        with SessionLocal() as db:
            # 1. Örnek yetersiz → 0
            _wipe_logs(db)
            _add_logs(db, status="failed", n=ae.EMAIL_HEALTH_MIN_SAMPLE - 1)
            v = ae._val_email_delivery_failing(db)
            check(
                f"1. Örnek yetersiz ({ae.EMAIL_HEALTH_MIN_SAMPLE - 1} deneme) → 0 (yanlış alarm yok)",
                v == 0, f"deger={v}",
            )

            # 2. Sağlıklı
            _wipe_logs(db)
            _add_logs(db, status="sent", n=20)
            v = ae._val_email_delivery_failing(db)
            check("2. 20 başarılı gönderim → 0", v == 0, f"deger={v}")

            # 3. Tam kesinti
            _wipe_logs(db)
            _add_logs(db, status="failed", n=10)
            v = ae._val_email_delivery_failing(db)
            check("3. Tam kesinti (10/10 başarısız) → 100", v == 100, f"deger={v}")

            # 4. Kısmi
            _wipe_logs(db)
            _add_logs(db, status="sent", n=5)
            _add_logs(db, status="failed", n=5)
            v = ae._val_email_delivery_failing(db)
            check("4. Kısmi kesinti (5 ok / 5 hata) → 50", v == 50, f"deger={v}")

            # 5. queued + suppressed sayılmaz
            _wipe_logs(db)
            _add_logs(db, status="sent", n=10)
            _add_logs(db, status="queued", n=50)
            _add_logs(db, status="suppressed", n=50)
            v = ae._val_email_delivery_failing(db)
            check("5. queued/suppressed paydaya girmez → 0", v == 0, f"deger={v}")

            # 6. Yerleşik kural + kanal sırası
            ae._ensure_builtin_rules(db)
            rule = db.query(AlarmRule).filter(AlarmRule.key == RULE_KEY).first()
            ae._ensure_builtin_rules(db)  # idempotent
            dupes = db.query(AlarmRule).filter(AlarmRule.key == RULE_KEY).count()
            chans = [c.strip() for c in (rule.channels or "").split(",")] if rule else []
            check(
                "6. Yerleşik kural idempotent + push kanalı tanımlı",
                rule is not None and dupes == 1 and "push" in chans and "in_app" in chans,
                f"rule={rule is not None} dupes={dupes} chans={chans}",
            )

            # 7. evaluate_all tam kesintide tetikler
            _wipe_logs(db)
            _add_logs(db, status="failed", n=10)
            rule.last_triggered_at = None  # cooldown sıfırla
            db.commit()
            before = db.query(AlarmEvent).filter(AlarmEvent.rule_key == RULE_KEY).count()
            results = ae.evaluate_all(db)
            res = next((r for r in results if r.rule_key == RULE_KEY), None)
            after = db.query(AlarmEvent).filter(AlarmEvent.rule_key == RULE_KEY).count()
            ev = (
                db.query(AlarmEvent)
                .filter(AlarmEvent.rule_key == RULE_KEY)
                .order_by(AlarmEvent.id.desc())
                .first()
            )
            check(
                "7. evaluate_all → tetiklendi + AlarmEvent yazıldı + severity critical",
                res is not None and res.triggered and after == before + 1
                and ev is not None and ev.severity == "critical" and ev.value == 100,
                f"trig={res.triggered if res else None} delta={after - before} "
                f"sev={ev.severity if ev else None}",
            )
            # 7b. Teslimat raporu DÜRÜST olmalı: kayıtlı cihaz yoksa push:0,
            # e-posta sağlayıcı reddederse email:0/N. "ok" yazıp geçmek, bu
            # alarmın engellemek için var olduğu sessiz başarısızlığın ta kendisi.
            ds = (ev.delivery_status or "") if ev else ""
            check(
                "7b. Teslimat raporu gerçek sayı veriyor (push:0 = cihaz yok)",
                "push:0" in ds and "in_app:ok" in ds,
                f"delivery={ds}",
            )
            check(
                "7c. E-posta teslimatı gerçek başarı sayısıyla raporlanıyor",
                any(p.startswith("email:") and "/" in p for p in ds.split("|")),
                f"delivery={ds}",
            )

            # 8. Cooldown
            results2 = ae.evaluate_all(db)
            res2 = next((r for r in results2 if r.rule_key == RULE_KEY), None)
            check(
                "8. İkinci değerlendirme cooldown'a takılır (alarm yorgunluğu yok)",
                res2 is not None and not res2.triggered and res2.skipped_reason == "cooldown",
                f"trig={res2.triggered if res2 else None} reason={res2.skipped_reason if res2 else None}",
            )

            # 9. Alıcı listesi
            from app.config import settings
            old_extra = settings.alarm_extra_emails
            try:
                settings.alarm_extra_emails = f" ek@test.invalid , {PFX}@test.invalid , bozuk "
                rec = ae._alarm_email_recipients(db)
                low = [r.lower() for r in rec]
                check(
                    "9. Alıcılar = süper admin + ek adres, tekilleştirilmiş, geçersiz atılır",
                    "ek@test.invalid" in low
                    and low.count(f"{PFX}@test.invalid") == 1
                    and "bozuk" not in low,
                    f"rec={rec}",
                )
            finally:
                settings.alarm_extra_emails = old_extra

            # 10. Pano bandı alarmla aynı sonucu verir
            from app.routes.api_v2.admin import _email_health_for_dashboard
            eh = _email_health_for_dashboard(db)
            check(
                "10. Pano bandı alarmla tutarlı (degraded + %100 + hata mesajı)",
                eh.degraded and eh.failure_pct == 100 and eh.attempts_24h == 10
                and (eh.last_error or "").find("535") >= 0,
                f"degraded={eh.degraded} pct={eh.failure_pct} n={eh.attempts_24h} err={eh.last_error}",
            )

            # 10b. Sağlıklıyken bant çıkmaz
            _wipe_logs(db)
            _add_logs(db, status="sent", n=10)
            eh2 = _email_health_for_dashboard(db)
            check(
                "10b. Sağlıklıyken bant çıkmaz",
                not eh2.degraded and eh2.failure_pct == 0,
                f"degraded={eh2.degraded} pct={eh2.failure_pct}",
            )

            # 11. Rozet sayacı
            all_unack = ae.unacknowledged_count(db)
            recent_unack = ae.unacknowledged_count(db, hours=72)
            check(
                "11. Görülmemiş alarm rozeti > 0 (in_app kanalı görünür)",
                recent_unack > 0, f"unack72={recent_unack}",
            )
            # Rozet penceresi: eski birikinti (prod'da 2300+) rozeti şişirmemeli
            old_ev = AlarmEvent(
                rule_key=RULE_KEY, rule_name="eski", value=1, threshold=0,
                severity="warn", channels_attempted="in_app",
                delivery_status="in_app:ok",
                triggered_at=datetime.now(timezone.utc) - timedelta(days=30),
            )
            db.add(old_ev)
            db.commit()
            check(
                "11b. 30 gün önceki alarm rozete GİRMEZ (alarm körlüğü koruması)",
                ae.unacknowledged_count(db, hours=72) == recent_unack
                and ae.unacknowledged_count(db) == all_unack + 1,
                f"unack72={ae.unacknowledged_count(db, hours=72)} (bekl {recent_unack}) "
                f"tum={ae.unacknowledged_count(db)} (bekl {all_unack + 1})",
            )

    finally:
        with SessionLocal() as db:
            _wipe_logs(db)
            # Yedeklenen gerçek kayıtları geri yükle
            for row in saved_rows:
                db.add(CommunicationLog(**row))
            db.execute(sa_delete(AlarmEvent).where(AlarmEvent.rule_key == RULE_KEY))
            if admin_id:
                db.execute(sa_delete(User).where(User.id == admin_id))
            db.commit()
            restored = db.query(CommunicationLog).filter(
                CommunicationLog.created_at
                >= datetime.now(timezone.utc) - timedelta(hours=ae.EMAIL_HEALTH_WINDOW_HOURS + 1)
            ).count()
            print(f"\n  cleanup OK — {restored} kayıt geri yüklendi "
                  f"(yedek: {len(saved_rows)})")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
