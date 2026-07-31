"""Güvenlik Kamarası bayat-kayıt temizliği smoke (2026-07-31).

Bulgu: panel "hâlâ doğru" ile "bir zamanlar doğruydu, kimse kapatmadı" ayrımını
yapmıyordu. Prod'da 11 kritik uyarının HİÇBİRİ güncel değildi:
  - süresi 5 hafta önce dolmuş kimliğe-bürünme oturumları "aktif" sayılıyordu
  - 72-75 günlük ActiveSession kayıtları "9 aktif oturum"u şişiriyordu
  - Haziran'dan kalma 2308 onaysız alarm Dikkat Odası'nı dolduruyordu

Senaryolar:
  1.  list_active süresi dolmuş oturumu SAYMAZ
  2.  list_active canlı oturumu sayar (koruma kaybolmadı)
  3.  include_expired=True denetim için tam listeyi verir
  4.  cron bayat ActiveSession'ı kapatır
  5.  cron taze oturuma DOKUNMAZ
  6.  cron süresi dolmuş kimliğe-bürünmeyi kapatır (ended_at = expires_at)
  7.  cron canlı kimliğe-bürünmeye DOKUNMAZ
  8.  cron idempotent (ikinci koşu 0 döner)
  9.  toplu onay eski alarmı işaretler, yenisine dokunmaz
  10. toplu onay kaydı SİLMEZ (denetim izi korunur)
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
from app.models import (
    ActiveSession,
    AlarmEvent,
    ImpersonationSession,
    User,
    UserRole,
)
from app.services import alarm_engine as ae
from app.services.cron_jobs import stale_session_cleanup
from app.services.impersonation import list_active
from app.services.security import hash_password

PFX = f"stale_{secrets.token_hex(3)}"
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
    print(f"\n=== Güvenlik Kamarası bayat kayıt temizliği — {PFX} ===\n")
    now = datetime.now(timezone.utc)
    ids: dict[str, int] = {}

    with SessionLocal() as db:
        admin = User(email=f"{PFX}_a@test.invalid", password_hash=hash_password("Xy1!abcdefghij"),
                     full_name="A", role=UserRole.SUPER_ADMIN, is_active=True)
        target = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("Xy1!abcdefghij"),
                      full_name="T", role=UserRole.TEACHER, is_active=True)
        db.add_all([admin, target]); db.commit()
        ids["admin"], ids["target"] = admin.id, target.id

        # Süresi dolmuş ama kapanmamış (prod'daki 3 kayıt gibi)
        exp = ImpersonationSession(
            actor_user_id=admin.id, target_user_id=target.id, reason="bayat test kaydi",
            started_at=now - timedelta(days=35), expires_at=now - timedelta(days=35) + timedelta(minutes=30),
        )
        # Canlı
        live = ImpersonationSession(
            actor_user_id=admin.id, target_user_id=target.id, reason="canli test kaydi",
            started_at=now - timedelta(minutes=5), expires_at=now + timedelta(minutes=25),
        )
        # Bayat oturum (75 gün) + taze oturum
        old_s = ActiveSession(session_token=f"{PFX}_old", user_id=target.id, role=UserRole.TEACHER,
                              ip="127.0.0.1", login_at=now - timedelta(days=75),
                              last_seen_at=now - timedelta(days=75))
        new_s = ActiveSession(session_token=f"{PFX}_new", user_id=target.id, role=UserRole.TEACHER,
                              ip="1.2.3.4", login_at=now - timedelta(hours=2),
                              last_seen_at=now - timedelta(hours=2))
        # Eski + yeni alarm
        old_a = AlarmEvent(rule_key=f"{PFX}_rule", rule_name="eski", value=1, threshold=0,
                           severity="warn", channels_attempted="in_app", delivery_status="in_app:ok",
                           triggered_at=now - timedelta(days=40))
        new_a = AlarmEvent(rule_key=f"{PFX}_rule", rule_name="yeni", value=1, threshold=0,
                           severity="warn", channels_attempted="in_app", delivery_status="in_app:ok",
                           triggered_at=now - timedelta(hours=2))
        db.add_all([exp, live, old_s, new_s, old_a, new_a]); db.commit()
        ids.update(exp=exp.id, live=live.id, old_a=old_a.id, new_a=new_a.id)

    try:
        with SessionLocal() as db:
            act = list_active(db)
            act_ids = {r["id"] for r in act}
            check("1. Süresi dolmuş kimliğe-bürünme 'aktif' SAYILMAZ",
                  ids["exp"] not in act_ids, f"aktifler={act_ids & {ids['exp'], ids['live']}}")
            check("2. Canlı kimliğe-bürünme sayılır (koruma kaybolmadı)",
                  ids["live"] in act_ids, f"aktifler={act_ids & {ids['exp'], ids['live']}}")
            all_ids = {r["id"] for r in list_active(db, include_expired=True)}
            check("3. include_expired=True denetim için tam liste verir",
                  ids["exp"] in all_ids and ids["live"] in all_ids, f"tum={all_ids}")

            res = stale_session_cleanup(db, now=datetime.now(timezone.utc))
            check("4. Cron bayat oturumu kapattı", res["sessions_closed"] >= 1, str(res))

            old_row = db.query(ActiveSession).filter(ActiveSession.session_token == f"{PFX}_old").first()
            new_row = db.query(ActiveSession).filter(ActiveSession.session_token == f"{PFX}_new").first()
            check("4b. Bayat oturum terminated + sebep işaretli",
                  old_row.terminated_at is not None and old_row.termination_reason == "stale_cleanup",
                  f"term={old_row.terminated_at} reason={old_row.termination_reason}")
            check("5. Taze oturuma DOKUNULMADI",
                  new_row.terminated_at is None, f"term={new_row.terminated_at}")

            e = db.get(ImpersonationSession, ids["exp"])
            l = db.get(ImpersonationSession, ids["live"])
            check("6. Süresi dolmuş kimliğe-bürünme kapatıldı (ended_at = expires_at)",
                  e.ended_at is not None and e.ended_at == e.expires_at,
                  f"ended={e.ended_at} expires={e.expires_at}")
            check("7. Canlı kimliğe-bürünmeye DOKUNULMADI",
                  l.ended_at is None, f"ended={l.ended_at}")

            res2 = stale_session_cleanup(db, now=datetime.now(timezone.utc))
            check("8. Cron idempotent (ikinci koşuda iş yok)",
                  res2["sessions_closed"] == 0 and res2["impersonations_closed"] == 0, str(res2))

            n = ae.acknowledge_older_than(db, user_id=ids["admin"], hours=72)
            oa = db.get(AlarmEvent, ids["old_a"])
            na = db.get(AlarmEvent, ids["new_a"])
            check("9. Toplu onay eski alarmı işaretledi, yenisine dokunmadı",
                  n >= 1 and oa.acknowledged_at is not None and na.acknowledged_at is None,
                  f"n={n} eski={oa.acknowledged_at} yeni={na.acknowledged_at}")
            check("10. Kayıt SİLİNMEDİ (denetim izi korunur) + kim onayladı yazılı",
                  oa is not None and oa.acknowledged_by_user_id == ids["admin"],
                  f"by={oa.acknowledged_by_user_id}")
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(AlarmEvent).where(AlarmEvent.rule_key == f"{PFX}_rule"))
            db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id == ids["target"]))
            db.execute(sa_delete(ImpersonationSession).where(
                ImpersonationSession.actor_user_id == ids["admin"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["admin"], ids["target"]])))
            db.commit()
        print("\n  temizlik OK")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
