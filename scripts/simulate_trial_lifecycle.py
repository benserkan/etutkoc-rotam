"""Bağımsız koç trial yaşam döngüsü simülasyonu (gerçek kod, geçici kullanıcılar).

Senaryolar:
  A) Ücretsiz/varsayılan signup → solo_trial (14g sınırsız öğrenci, AI yok)
  B) 14 gün dolunca expire_trials → solo_free (3 öğrenci sert sınır)

Ölçülenler:
  - Trial sırasında: plan, kalan gün, öğrenci limiti (sınırsız mı), AI açık mı,
    yeni öğrenci eklenebilir mi
  - Trial dolunca: plan düşüyor mu, öğrenciler PASİF oluyor mu (yoksa aktif mi
    kalıyor), 4./6. öğrenci eklenebiliyor mu, AI hâlâ kapalı mı
  - Trial bitmeden UYARI fırlatılıyor mu (banner/e-posta/cron)

Gerçek hesaplara dokunmaz — `simtrial_*` prefiks'li geçici kullanıcı + cleanup.
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
from app.models import User, UserRole
from app.services import plans
from app.services.security import hash_password

PFX = f"simtrial_{secrets.token_hex(3)}"
PWD = hash_password("SimTrialPass!23")
N_STUDENTS = 5


def line(s=""):
    print(s)


def run() -> int:
    now = datetime.now(timezone.utc)
    coach_id = None
    student_ids: list[int] = []
    try:
        with SessionLocal() as db:
            coach = User(
                email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Koç", role=UserRole.TEACHER,
                institution_id=None, is_active=True,
                password_changed_at=now, must_change_password=False,
            )
            db.add(coach)
            db.flush()
            coach_id = coach.id
            # Ücretsiz signup'ın yaptığı: solo_trial başlat
            plans.start_solo_trial(db, user=coach, autocommit=False)
            db.flush()

            for i in range(N_STUDENTS):
                s = User(
                    email=f"{PFX}_stu{i}@test.invalid", password_hash=PWD,
                    full_name=f"{PFX} Öğrenci {i}", role=UserRole.STUDENT,
                    teacher_id=coach.id, institution_id=None, grade_level=8,
                    is_active=True, password_changed_at=now, must_change_password=False,
                )
                db.add(s)
            db.commit()
            db.refresh(coach)
            student_ids = [
                r.id for r in db.query(User).filter(
                    User.teacher_id == coach.id, User.role == UserRole.STUDENT
                ).all()
            ]

            # ---------------- TRIAL SIRASINDA ----------------
            line("\n=== A) TRIAL SIRASINDA (ücretsiz/varsayılan signup) ===")
            line(f"  plan                = {coach.plan}")
            line(f"  trial kalan gün     = {plans.trial_days_left(owner=coach, now=now)}")
            line(f"  trial aktif mi      = {plans.is_trial_active(coach, now=now)}")
            limit = plans.solo_student_limit(coach.plan)
            line(f"  öğrenci limiti      = {limit}  ({'SINIRSIZ' if limit == -1 else limit})")
            line(f"  aktif öğrenci       = {plans.count_solo_students(db, teacher_id=coach.id)}")
            line(f"  AI açık mı          = {plans.ai_premium_allowed(db, coach)}  (beklenen: False — trial'da AI yok)")
            q = plans.check_solo_student_quota(db, teacher=coach, extra_count=1)
            line(f"  yeni öğrenci eklenebilir mi = {q.ok}  (beklenen: True — sınırsız)")

            # ---------------- 14 GÜN İLERİ SAR ----------------
            line("\n=== 14 gün ileri sarılıyor, expire_trials çalıştırılıyor ===")
            coach.trial_ends_at = now - timedelta(days=1)
            db.commit()
            future = now + timedelta(days=1)
            res = plans.expire_trials(db, now=future)
            db.refresh(coach)
            line(f"  expire_trials sonucu = {res}")

            # ---------------- TRIAL DOLUNCA ----------------
            line("\n=== B) TRIAL DOLUNCA ===")
            line(f"  plan                = {coach.plan}  (beklenen: solo_free)")
            line(f"  trial_ends_at       = {coach.trial_ends_at}  (beklenen: None)")
            active = db.query(User).filter(
                User.teacher_id == coach.id, User.role == UserRole.STUDENT,
                User.is_active.is_(True),
            ).count()
            total = db.query(User).filter(
                User.teacher_id == coach.id, User.role == UserRole.STUDENT,
            ).count()
            line(f"  öğrenci AKTİF/TOPLAM = {active}/{total}  (öğrenciler pasif oluyor mu? {'HAYIR — aktif kaldılar' if active == N_STUDENTS else 'EVET'})")
            limit2 = plans.solo_student_limit(coach.plan)
            line(f"  yeni öğrenci limiti = {limit2}  (solo_free sert sınır)")
            q2 = plans.check_solo_student_quota(db, teacher=coach, extra_count=1)
            line(f"  6. öğrenci eklenebilir mi = {q2.ok}  (beklenen: False — {q2.current}/{q2.limit} dolu, öneri: {q2.upgrade_target_code})")
            line(f"  AI açık mı          = {plans.ai_premium_allowed(db, coach)}  (beklenen: False)")

            # ---------------- UYARI MEKANİZMASI ----------------
            line("\n=== C) TRIAL BİTİŞ UYARISI ===")
            from app.services import cron_jobs
            has_warn_job = any(
                k for k in cron_jobs.JOB_REGISTRY
                if "trial" in k and k != "trial_expire"
            )
            banner = plans.compute_trial_banner(db, user=coach, now=now)  # now = trial içi
            line(f"  proaktif uyarı cron'u var mı (e-posta/bildirim) = {has_warn_job}  (beklenen: False — yok)")
            line(f"  in-app countdown banner (trial içi) = {'VAR' if banner else 'YOK'}  → {banner}")
            line("  → Sonuç: kullanıcı GİRİŞ yaparsa banner görür; giriş yapmazsa")
            line("    14 gün dolup planı düşene kadar hiçbir e-posta/bildirim almaz.")

        line("\n=== SİMÜLASYON BİTTİ ===")
        return 0
    finally:
        with SessionLocal() as db:
            if student_ids:
                db.execute(sa_delete(User).where(User.id.in_(student_ids)))
            if coach_id:
                from app.models.plan_history import PlanChangeHistory, PlanOwnerType
                db.execute(sa_delete(PlanChangeHistory).where(
                    PlanChangeHistory.owner_id == coach_id,
                    PlanChangeHistory.owner_type == PlanOwnerType.USER,
                ))
                db.execute(sa_delete(User).where(User.id == coach_id))
            db.commit()


if __name__ == "__main__":
    raise SystemExit(run())
