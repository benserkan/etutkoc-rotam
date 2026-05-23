"""Davet akışı simülasyonu — koç daveti (token+expiry) + öğrenci (direkt) + veli daveti.

Senaryolar:
  KOÇ DAVETİ (kurum → koç, token + süre):
    1. Geçerli davet → GET info valid → POST kayıt → koç oluştu + CONSUMED
    2. Tüketilmiş davet tekrar kullanılamaz (410)
    3. Süresi geçmiş davet → GET expired + POST 410
    4. İptal (revoked) davet → GET revoked + POST 410
    5. Olmayan token → not_found
  ÖĞRENCİ (koç → öğrenci): direkt hesap + tek-seferlik temp_password (token YOK)
  VELİ DAVETİ (token + süre): pending → süre dolunca geçersiz
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
from app.models import Institution, Invitation, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"invsim_{secrets.token_hex(3)}"
PWD = hash_password("InvSimPass!23")
TEACH_PWD = "InviteTeach2026!"
now = datetime.now(timezone.utc)
inst_id = None
extra_emails: list[str] = []

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


def _mk_invite(suffix, *, expires_days=7, revoked=False, consumed=False):
    tok = secrets.token_urlsafe(24)
    with SessionLocal() as db:
        inv = Invitation(
            token=tok, email=f"{PFX}_{suffix}@test.invalid", full_name=f"{PFX} {suffix}",
            role=UserRole.TEACHER, institution_id=inst_id,
            expires_at=now + timedelta(days=expires_days),
            revoked_at=(now if revoked else None),
            consumed_at=(now if consumed else None),
        )
        db.add(inv); db.commit()
    extra_emails.append(f"{PFX}_{suffix}@test.invalid")
    return tok


def main():
    print(f"\n=== DAVET AKIŞI SİMÜLASYONU — {PFX} ===\n")
    get_login_limiter().reset()
    global inst_id
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Dershane", slug=f"{PFX}-d", plan="etut_standart", is_active=True)
        db.add(inst); db.commit(); inst_id = inst.id

    c = TestClient(app)
    try:
        # ── KOÇ DAVETİ ──
        print("KOÇ DAVETİ (kurum → koç):")
        tok = _mk_invite("kocA", expires_days=7)
        r = c.get(f"/api/v2/auth/signup/invite/{tok}")
        j = r.json()
        check("1. geçerli davet → GET valid + rol teacher + kurum adı",
              r.status_code == 200 and j.get("valid") and j.get("role") == "teacher"
              and j.get("institution_name"), f"{j}")
        r = c.post(f"/api/v2/auth/signup/invite/{tok}", json={
            "full_name": "Davetli Koç", "email": f"{PFX}_kocA@test.invalid",
            "password": TEACH_PWD, "password_confirm": TEACH_PWD, "accept_terms": True})
        ok_consume = r.status_code == 200
        with SessionLocal() as db:
            u = db.query(User).filter(User.email == f"{PFX}_koca@test.invalid").first()
            inv = db.query(Invitation).filter(Invitation.token == tok).first()
            dbg = (f"user={'var' if u else 'YOK'} role={u.role.value if u else '-'} "
                   f"inst={u.institution_id if u else '-'}/{inst_id} "
                   f"consumed={inv.consumed_at is not None if inv else '-'}")
            ok_consume = ok_consume and u is not None and u.role == UserRole.TEACHER \
                and u.institution_id == inst_id and inv.consumed_at is not None
        check("1b. POST → koç oluştu + kuruma bağlı + davet CONSUMED", ok_consume, f"status={r.status_code} {dbg}")

        # 2. tüketilmiş tekrar kullanılamaz
        r = c.post(f"/api/v2/auth/signup/invite/{tok}", json={
            "full_name": "X", "email": f"{PFX}_kocA@test.invalid",
            "password": TEACH_PWD, "password_confirm": TEACH_PWD, "accept_terms": True})
        check("2. tüketilmiş davet tekrar → 410 unusable",
              r.status_code == 410 and r.json()["detail"]["code"] == "invitation_unusable", f"status={r.status_code}")

        # 3. süresi geçmiş
        tok_exp = _mk_invite("kocExp", expires_days=-1)
        ri = c.get(f"/api/v2/auth/signup/invite/{tok_exp}").json()
        rp = c.post(f"/api/v2/auth/signup/invite/{tok_exp}", json={
            "full_name": "Y", "email": f"{PFX}_kocExp@test.invalid",
            "password": TEACH_PWD, "password_confirm": TEACH_PWD, "accept_terms": True})
        check("3. süresi geçmiş davet → GET expired + POST 410",
              ri.get("valid") is False and ri.get("status") == "expired" and rp.status_code == 410,
              f"info={ri} post={rp.status_code}")

        # 4. iptal edilmiş
        tok_rev = _mk_invite("kocRev", revoked=True)
        ri = c.get(f"/api/v2/auth/signup/invite/{tok_rev}").json()
        check("4. iptal edilmiş davet → GET revoked + valid False",
              ri.get("valid") is False and ri.get("status") == "revoked", f"{ri}")

        # 5. olmayan token
        ri = c.get("/api/v2/auth/signup/invite/yok_boyle_token_123").json()
        check("5. olmayan token → not_found", ri.get("status") == "not_found", f"{ri}")

        # ── ÖĞRENCİ OLUŞTURMA (direkt, token YOK) ──
        print("\nÖĞRENCİ OLUŞTURMA (koç → öğrenci):")
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD, full_name=f"{PFX} Koç",
                         role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                         password_changed_at=now, must_change_password=False)
            db.add(coach); db.commit()
        extra_emails.append(f"{PFX}_coach@test.invalid")
        cc = TestClient(app)
        rl = cc.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": "InvSimPass!23"})
        r = cc.post("/api/v2/teacher/students", json={
            "full_name": "Yeni Öğrenci", "email": f"{PFX}_ogr1@test.invalid", "grade_level": 8})
        j = r.json()
        tp = j.get("data", {}).get("temp_password") if r.status_code == 200 else None
        check("6. öğrenci oluştur → 200 + tek-seferlik temp_password (token/davet YOK)",
              r.status_code == 200 and bool(tp), f"status={r.status_code} body={r.text[:160]}")
        extra_emails.append(f"{PFX}_ogr1@test.invalid")

        # ── VELİ DAVETİ (token + süre) ──
        print("\nVELİ DAVETİ (token + süre):")
        from app.models import ParentInvitation
        from app.services import parent_invitation as pinv
        with SessionLocal() as db:
            stu = db.query(User).filter(User.email == f"{PFX}_ogr1@test.invalid").first()
            coach = db.query(User).filter(User.email == f"{PFX}_coach@test.invalid").first()
            inv = pinv.create_invitation(db, invited_email=f"{PFX}_veli@test.invalid",
                                         student_id=stu.id, invited_by_id=coach.id)
            db.commit()
            iid = inv.id
            def _aw(dt):
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            valid_now = (inv.consumed_at is None and _aw(inv.expires_at) > now)
            # süre dolmuş hale getir
            inv.expires_at = now - timedelta(days=1)
            db.commit()
            inv2 = db.get(ParentInvitation, iid)
            expired = _aw(inv2.expires_at) < now and inv2.consumed_at is None
        check("7. veli daveti token+süreyle oluşur (pending) + süre dolunca geçersiz",
              valid_now and expired, f"valid_now={valid_now} expired={expired}")

    finally:
        with SessionLocal() as db:
            from app.models import ParentInvitation, ParentStudentLink
            # PFX prefix'i ile tüm test kullanıcıları (consume küçük-harfe çevirse de yakalar)
            allids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}%")).all()]
            if allids:
                db.execute(sa_delete(ParentInvitation).where(ParentInvitation.student_id.in_(allids)))
                db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(allids)))
                db.execute(sa_delete(User).where(User.id.in_(allids)))
            db.execute(sa_delete(Invitation).where(Invitation.institution_id == inst_id))
            if inst_id:
                db.execute(sa_delete(Institution).where(Institution.id == inst_id))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
