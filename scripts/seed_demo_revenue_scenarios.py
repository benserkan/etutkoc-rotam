"""Kalıcı örnek ticari senaryolar — UI'da inceleme için (idempotent).

Çalıştır:  PYTHONPATH=. python scripts/seed_demo_revenue_scenarios.py

Oluşturur (hepsi bağımsız koç, @etutkoc.test):
  A — solo_free, 20 öğrenci  → deneme bitti, limit aşımı (paywall)
  B — solo_free, 2 öğrenci   → limit altı (sorun yok)
  C — solo_pro, past_due, 10 öğrenci → dönem geçti, ödeme duvarı
  D — solo_pro, canceled (dönem ileride), 10 öğrenci → iptal edildi, hâlâ aktif
  E — solo_pro aktif + 2 SENT teklif (biri açılmış, biri açılmamış) → teklif izleme

Tekrar çalıştırılınca durumları yeniden kurar. Silmek için:
  scripts/seed_demo_revenue_scenarios.py --delete
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Offer, OfferStatus, User, UserRole
from app.services.security import hash_password

PWD_PLAIN = "DemoRevenue2026!"
EMAILS = {k: f"demo.{k.lower()}@etutkoc.test" for k in ["A", "B", "C", "D", "E"]}
STU_PREFIX = "demo.rev.stu"


def _student_email(coach_key: str, i: int) -> str:
    return f"{STU_PREFIX}.{coach_key.lower()}.{i}@etutkoc.test"


def _ensure_students(db, coach: User, key: str, n: int) -> None:
    existing = db.query(User).filter(
        User.teacher_id == coach.id, User.role == UserRole.STUDENT,
    ).count()
    now = datetime.now(timezone.utc)
    for i in range(existing, n):
        db.add(User(
            email=_student_email(key, i), password_hash=hash_password(PWD_PLAIN),
            full_name=f"Demo Öğrenci {key}{i + 1}", role=UserRole.STUDENT,
            teacher_id=coach.id, institution_id=None, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        ))


def _upsert_coach(db, key: str, *, plan, sub_status, period_end, trial_ends_at, n_students) -> User:
    now = datetime.now(timezone.utc)
    c = db.query(User).filter(User.email == EMAILS[key]).first()
    if c is None:
        c = User(email=EMAILS[key], password_hash=hash_password(PWD_PLAIN),
                 full_name=f"Demo Koç {key}", role=UserRole.TEACHER, institution_id=None,
                 is_active=True, password_changed_at=now, must_change_password=False)
        db.add(c); db.flush()
    c.role = UserRole.TEACHER
    c.institution_id = None
    c.is_active = True
    c.plan = plan
    c.subscription_status = sub_status
    c.subscription_period_end = period_end
    c.subscription_cycle = "monthly" if sub_status else None
    c.trial_ends_at = trial_ends_at
    c.post_trial_plan = "solo_free"
    db.flush()
    _ensure_students(db, c, key, n_students)
    db.commit(); db.refresh(c)
    return c


def _first_super_admin_id(db) -> int | None:
    row = db.query(User.id).filter(User.role == UserRole.SUPER_ADMIN).order_by(User.id).first()
    return row[0] if row else None


def _delete_all() -> None:
    with SessionLocal() as db:
        coaches = db.query(User).filter(User.email.in_(list(EMAILS.values()))).all()
        cids = [c.id for c in coaches]
        if cids:
            db.execute(sa_delete(Offer).where(Offer.user_id.in_(cids)))
        db.execute(sa_delete(User).where(User.email.like(f"{STU_PREFIX}%")))
        db.execute(sa_delete(User).where(User.email.in_(list(EMAILS.values()))))
        db.commit()
    print("Demo senaryolar silindi.")


def main() -> int:
    if "--delete" in sys.argv:
        _delete_all()
        return 0
    now = datetime.now(timezone.utc)
    out = []
    with SessionLocal() as db:
        a = _upsert_coach(db, "A", plan="solo_free", sub_status=None, period_end=None,
                          trial_ends_at=None, n_students=20)
        b = _upsert_coach(db, "B", plan="solo_free", sub_status=None, period_end=None,
                          trial_ends_at=None, n_students=2)
        c = _upsert_coach(db, "C", plan="solo_pro", sub_status="past_due",
                          period_end=now - timedelta(days=2), trial_ends_at=None, n_students=10)
        d = _upsert_coach(db, "D", plan="solo_pro", sub_status="canceled",
                          period_end=now + timedelta(days=20), trial_ends_at=None, n_students=10)
        e = _upsert_coach(db, "E", plan="solo_pro", sub_status="active",
                          period_end=now + timedelta(days=25), trial_ends_at=None, n_students=6)

        # E için 2 SENT teklif (biri açılmış)
        admin_id = _first_super_admin_id(db)
        db.execute(sa_delete(Offer).where(Offer.user_id == e.id))
        db.commit()
        from app.services.offers import create_offer, send_offer
        if admin_id:
            o1 = create_offer(db, user_id=e.id, kind="plan_upgrade", title="Solo Elite'e geç — özel",
                              by_user_id=admin_id, new_plan="solo_elite",
                              public_message="Daha fazla kredi + öncelikli destek. Size özel.",
                              expires_in_days=14, autocommit=True)
            if o1:
                send_offer(db, offer_id=o1.id)
                o1b = db.get(Offer, o1.id)
                o1b.viewed_at = now - timedelta(hours=3)  # AÇILMIŞ
                db.commit()
            o2 = create_offer(db, user_id=e.id, kind="discount_percent", title="%20 indirim (3 ay)",
                              by_user_id=admin_id, value=20, duration_months=3,
                              public_message="3 ay boyunca %20 indirim.",
                              expires_in_days=14, autocommit=True)
            if o2:
                send_offer(db, offer_id=o2.id)  # AÇILMAMIŞ (viewed_at None)

        for key, u, desc in [
            ("A", a, "solo_free · 20 öğrenci → deneme bitti, LİMİT AŞIMI (paywall, koçluk kilitli)"),
            ("B", b, "solo_free · 2 öğrenci → limit altı, sorun yok"),
            ("C", c, "solo_pro · PAST_DUE (dönem 2g önce geçti) → ödeme duvarı"),
            ("D", d, "solo_pro · İPTAL edilmiş (20g sonra biter) → hâlâ aktif"),
            ("E", e, "solo_pro aktif · 2 SENT teklif (1 açılmış / 1 açılmamış) → teklif izleme"),
        ]:
            out.append((key, u.id, EMAILS[key], desc))

    print("\n=== DEMO TİCARİ SENARYOLAR (kalıcı) ===")
    print(f"  Şifre (hepsi): {PWD_PLAIN}\n")
    for key, uid, email, desc in out:
        print(f"  [{key}] {email}  (id={uid})")
        print(f"       {desc}")
        print(f"       Ticari 360 : /admin/revenue/users/{uid}")
        print(f"       Kullanıcı  : /admin/users/{uid}  (Abonelik aktivasyon kartı)")
    print("\n  Koç olarak giriş + /teacher/plan ile de inceleyebilirsin.")
    print("  Silmek için: PYTHONPATH=. python scripts/seed_demo_revenue_scenarios.py --delete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
