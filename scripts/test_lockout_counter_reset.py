"""Kilit sayacı sıfırlanma smoke — "sürekli bloklama" bug'ının regresyon kalkanı.

Bug (2026-07-30, kullanıcı #87 Hatice vakası): kilit süresi dolduğunda
`failed_login_count` sıfırlanmıyordu; yalnız BAŞARILI girişte sıfırlanıyordu.
Sonuç: eşiğe (5) bir kez ulaşan hesap kalıcı olarak "tek yanlış deneme =
anında 10 dk kilit" moduna düşüyordu. Hatice 19 saat bekledikten sonra tek
yanlış denemeyle tekrar kilitlendi.

Senaryolar:
  1-2. Eşiğe kadar sayaç artar, eşikte kilitlenir
  3.   Kilit AKTİFken clear_expired_lockout hiçbir şey yapmaz (ceza erken bitmez)
  4.   Kilit süresi dolunca sonraki yanlış deneme sayacı 1'e çeker, KİLİTLEMEZ
  5.   Kilit sonrası tam 5 hak geri gelir (4. yanlışta hâlâ kilit yok)
  6.   Başarılı giriş her şeyi sıfırlar
  7.   HTTP uçtan uca — Hatice senaryosu: 5 yanlış → 423, süre dolar,
       1 yanlış → 401 (423 DEĞİL), doğru şifre → 200
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
from app.models import ActiveSession, AuditLog, SuspiciousIp, User, UserRole
from app.services.auth_security import (
    LOCKOUT_POLICY,
    clear_expired_lockout,
    is_locked,
    register_failed_login,
    register_successful_login,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"lockreset_{secrets.token_hex(3)}"
EMAIL = f"{PFX}@test.invalid"
PASSWORD = "TestPass123!@xyz"
THRESHOLD, DURATION_MIN = LOCKOUT_POLICY[UserRole.TEACHER]

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


def _seed() -> int:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        u = User(
            email=EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"{PFX} Coach", role=UserRole.TEACHER, is_active=True,
            plan="solo_free", password_changed_at=now, must_change_password=False,
        )
        db.add(u)
        db.commit()
        return u.id


def _cleanup(uid: int) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id == uid))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id == uid))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id == uid))
        db.commit()


def _backdate_lock(uid: int) -> None:
    """Kilit süresini geçmişe al — 'süre doldu' durumunu simüle eder."""
    with SessionLocal() as db:
        u = db.get(User, uid)
        u.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()


def main() -> int:
    print(f"\n=== Kilit sayacı sıfırlanma — prefix: {PFX} "
          f"(eşik={THRESHOLD}, süre={DURATION_MIN}dk) ===\n")
    get_login_limiter().reset()
    uid = _seed()
    print(f"  seeded uid={uid}\n")

    try:
        # ---------- Birim testleri ----------
        with SessionLocal() as db:
            u = db.get(User, uid)

            # 1. Eşiğin altında kilit yok, sayaç artar
            triggered = [register_failed_login(u) for _ in range(THRESHOLD - 1)]
            check(
                f"1. {THRESHOLD - 1} yanlış → kilit yok, sayaç={THRESHOLD - 1}",
                not any(triggered) and u.failed_login_count == THRESHOLD - 1
                and not is_locked(u),
                f"triggered={triggered} count={u.failed_login_count}",
            )

            # 2. Eşikte kilitlenir
            triggered_last = register_failed_login(u)
            check(
                f"2. {THRESHOLD}. yanlış → kilitlendi",
                triggered_last and is_locked(u) and u.failed_login_count == THRESHOLD,
                f"triggered={triggered_last} locked={is_locked(u)} count={u.failed_login_count}",
            )

            # 3. Kilit AKTİFken temizleme çalışmaz (ceza erken bitmemeli)
            cleared = clear_expired_lockout(u)
            check(
                "3. Kilit aktifken clear_expired_lockout no-op (ceza erken bitmez)",
                cleared is False and is_locked(u) and u.failed_login_count == THRESHOLD,
                f"cleared={cleared} locked={is_locked(u)} count={u.failed_login_count}",
            )

            # 4. Süre dolunca sonraki yanlış sayacı 1'e çeker, KİLİTLEMEZ  ← BUG BURADAYDI
            u.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
            triggered_after = register_failed_login(u)
            check(
                "4. Süre dolduktan sonraki yanlış → sayaç 1, kilit YOK (regresyon)",
                triggered_after is False and u.failed_login_count == 1
                and not is_locked(u),
                f"triggered={triggered_after} count={u.failed_login_count} locked={is_locked(u)}",
            )

            # 5. Tam 5 hak geri geldi mi? (2..THRESHOLD-1 hâlâ kilitsiz)
            more = [register_failed_login(u) for _ in range(THRESHOLD - 2)]
            check(
                f"5. Kilit sonrası tam {THRESHOLD} hak geri geldi",
                not any(more) and u.failed_login_count == THRESHOLD - 1
                and not is_locked(u),
                f"more={more} count={u.failed_login_count}",
            )

            # 6. Başarılı giriş her şeyi sıfırlar
            register_successful_login(u, ip="1.2.3.4")
            check(
                "6. Başarılı giriş → sayaç 0 + kilit yok",
                u.failed_login_count == 0 and u.locked_until is None and not is_locked(u),
                f"count={u.failed_login_count} locked_until={u.locked_until}",
            )
            db.rollback()  # birim testleri DB'ye yazmasın

        # ---------- 7. HTTP uçtan uca (Hatice senaryosu) ----------
        c = TestClient(app)
        statuses = []
        for _ in range(THRESHOLD):
            get_login_limiter().reset()
            r = c.post("/api/v2/auth/login",
                       json={"email": EMAIL, "password": "yanlis-sifre"})
            statuses.append(r.status_code)
        check(
            f"7a. HTTP: {THRESHOLD}. yanlışta 423 kilit",
            statuses[-1] == 423 and all(s == 401 for s in statuses[:-1]),
            f"statuses={statuses}",
        )

        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login", json={"email": EMAIL, "password": PASSWORD})
        check(
            "7b. HTTP: kilitliyken DOĞRU şifre bile 423",
            r.status_code == 423, f"status={r.status_code}",
        )

        _backdate_lock(uid)
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": EMAIL, "password": "yanlis-sifre"})
        check(
            "7c. HTTP: süre dolduktan sonra tek yanlış → 401 (423 DEĞİL) ← asıl bug",
            r.status_code == 401, f"status={r.status_code}",
        )
        with SessionLocal() as db:
            u = db.get(User, uid)
            check(
                "7d. HTTP: sayaç 1'e döndü (6'ya çıkmadı)",
                u.failed_login_count == 1 and not is_locked(u),
                f"count={u.failed_login_count} locked_until={u.locked_until}",
            )

        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login", json={"email": EMAIL, "password": PASSWORD})
        check(
            "7e. HTTP: doğru şifre → 200 (kullanıcı içeri girebiliyor)",
            r.status_code == 200, f"status={r.status_code}",
        )
        with SessionLocal() as db:
            u = db.get(User, uid)
            check(
                "7f. HTTP: başarılı giriş sonrası sayaç 0 + kilit yok",
                u.failed_login_count == 0 and u.locked_until is None,
                f"count={u.failed_login_count} locked_until={u.locked_until}",
            )

    finally:
        _cleanup(uid)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
