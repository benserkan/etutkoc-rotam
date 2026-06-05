# -*- coding: utf-8 -*-
"""Kötüye kullanım senaryosu — çoklu hesap çiftliği güvenlik kamerası testi.

SENARYO (kullanıcı): bir bağımsız koç 14 gün için üye olur, sonra birden çok
ayrı koç hesabı açıp her birinde 3 öğrenci tanımlar → solo_free 3-öğrenci
limitini AŞAR (çok sayıda hesaptan çok sayıda öğrenci).

SORU: süper admin güvenlik kamerası (abuse_detection.detect_multi_account_same_device)
bunu yakalıyor mu?

Bu test KANITLAR:
  A) Aynı cihaz/IP+UA'dan 3+ koç hesabı giriş yaparsa → YAKALANIR (multi_account sinyali).
  B) Farklı IP/cihazdan giriş yapılırsa → YAKALANMAZ (bypass — zayıflık).
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.active_session import ActiveSession
from app.services.abuse_detection import (
    KIND_MULTI_ACCOUNT,
    detect_multi_account_same_device,
)
from app.services.security import hash_password

PFX = f"abusefarm_{secrets.token_hex(3)}"
FARM_IP = f"203.0.113.{secrets.randbelow(200) + 1}"      # bu test'e özgü IP
FARM_UA = f"ETUTKOC-Mobile-{secrets.token_hex(2)}"        # bu test'e özgü UA
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _mk_coach(db, n) -> int:
    u = User(email=f"{PFX}_c{n}@test.invalid", password_hash=hash_password("x"),
             full_name=f"{PFX} Koç {n}", role=UserRole.TEACHER, is_active=True,
             plan="solo_free")
    db.add(u); db.flush()
    return u.id


def _mk_session(db, *, user_id, ip, ua, role="teacher", imp_by=None):
    now = datetime.now(timezone.utc)
    db.add(ActiveSession(session_token=secrets.token_hex(20), user_id=user_id,
                         role=role, ip=ip, user_agent=ua,
                         login_at=now, last_seen_at=now, imp_by=imp_by))


def main() -> int:
    print(f"\n=== çoklu-hesap çiftliği abuse kamerası — {PFX} ===")
    print(f"  test IP={FARM_IP}  UA={FARM_UA}\n")
    coach_ids: list[int] = []
    try:
        # --- Senaryo A: aynı cihazdan 3 koç hesabı ---
        with SessionLocal() as db:
            for n in range(3):
                cid = _mk_coach(db, n)
                coach_ids.append(cid)
                _mk_session(db, user_id=cid, ip=FARM_IP, ua=FARM_UA)
            db.commit()

        with SessionLocal() as db:
            hits = detect_multi_account_same_device(db)
            my_hits = [h for h in hits if h.details.get("ip") == FARM_IP]
            check("A. Aynı IP+UA'dan 3 koç → multi_account YAKALANDI",
                  len(my_hits) == 1 and my_hits[0].kind == KIND_MULTI_ACCOUNT
                  and my_hits[0].count == 3,
                  f"hits={len(my_hits)} count={my_hits[0].count if my_hits else '-'}")
            if my_hits:
                check("A2. severity (3 hesap → 'info', 5+ → 'warn')",
                      my_hits[0].severity in ("info", "warn"), my_hits[0].severity)

        # --- Senaryo B: aynı 3 koç FARKLI IP'lerden (VPN/4G) → BYPASS ---
        with SessionLocal() as db:
            # eski oturumları sil, her koça farklı IP ver
            db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(coach_ids)))
            for i, cid in enumerate(coach_ids):
                _mk_session(db, user_id=cid, ip=f"198.51.100.{i + 10}", ua=FARM_UA)
            db.commit()

        with SessionLocal() as db:
            hits = detect_multi_account_same_device(db)
            my_hits = [h for h in hits if h.details.get("ip", "").startswith("198.51.100.")]
            check("B. Farklı IP'lerden giriş → YAKALANMADI (bypass kanıtı)",
                  len(my_hits) == 0,
                  f"beklenmedik hit={len(my_hits)}")

        # --- Senaryo C: yanlış-pozitif fix — impersonation + süper admin SAYILMAZ ---
        # Aynı cihazda 2 gerçek koç + 1 süper admin girişi + 1 impersonation oturumu.
        # Dışlama OLMASAYDI 4 distinct user → sinyal; dışlama VARSA yalnız 2 koç → sinyal YOK.
        ip_c = f"192.0.2.{secrets.randbelow(200) + 1}"
        ua_c = f"DevBrowser-{secrets.token_hex(2)}"
        sa_id = imp_target_id = None
        with SessionLocal() as db:
            db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(coach_ids)))
            # 2 gerçek koç girişi
            _mk_session(db, user_id=coach_ids[0], ip=ip_c, ua=ua_c)
            _mk_session(db, user_id=coach_ids[1], ip=ip_c, ua=ua_c)
            # süper admin'in KENDİ girişi (role=super_admin → dışlanır)
            sa = User(email=f"{PFX}_sa@test.invalid", password_hash=hash_password("x"),
                      full_name=f"{PFX} SA", role=UserRole.SUPER_ADMIN, is_active=True)
            db.add(sa); db.flush()
            sa_id = sa.id
            _mk_session(db, user_id=sa.id, ip=ip_c, ua=ua_c, role="super_admin")
            # impersonation oturumu (imp_by dolu → dışlanır)
            _mk_session(db, user_id=coach_ids[2], ip=ip_c, ua=ua_c, imp_by=sa.id)
            db.commit()

        with SessionLocal() as db:
            hits = detect_multi_account_same_device(db)
            my_hits = [h for h in hits if h.details.get("ip") == ip_c]
            check("C. impersonation + süper admin SAYILMADI (yanlış-pozitif fix)",
                  len(my_hits) == 0,
                  f"beklenmedik hit={len(my_hits)} — dışlama çalışmıyor")
        if sa_id:
            with SessionLocal() as db:
                db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id == sa_id))
                db.execute(sa_delete(User).where(User.id == sa_id))
                db.commit()

        print("\n  SONUÇ-ÖZET:")
        print("   • Aynı cihaz/IP+UA'dan çoklu hesap → güvenlik kamerası YAKALAR (sinyal üretir).")
        print("   • Farklı IP/cihaz (VPN/4G) → YAKALAMAZ. Ayrıca yakalama ADVISORY (info/warn),")
        print("     login-anında, otomatik ENGELLEME yok. Asıl önlem signup-anı (telefon/IP) gating.")
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(coach_ids)))
            db.execute(sa_delete(User).where(User.id.in_(coach_ids)))
            db.commit()
        print("\n  temizlendi")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
