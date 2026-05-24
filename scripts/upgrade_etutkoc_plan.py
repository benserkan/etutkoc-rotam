"""ETUTKOC kurumunu Etüt Standart'a yükseltir (kullanıcı onayıyla, 2026-05-24).

Free (2 öğretmen) limit aşımı (3/2) çözümü. change_plan ile yapılır →
PlanChangeHistory + audit kaydı düşer. Geri almak için new_plan='free' ile
tekrar çalıştır. İdempotent: zaten etut_standart ise no-op.

Çalıştır:  python scripts/upgrade_etutkoc_plan.py
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import Institution, PlanChangeReason, PlanOwnerType, User, UserRole
from app.services.plans import change_plan, get_plan_info
from app.services.quotas import PLAN_QUOTAS

TARGET = "etut_standart"


def main() -> int:
    with SessionLocal() as db:
        inst = db.query(Institution).filter(Institution.slug == "etutkoc").first()
        if not inst:
            print("ETUTKOC bulunamadı."); return 1

        teachers = (
            db.query(User)
            .filter(User.institution_id == inst.id, User.role == UserRole.TEACHER, User.is_active.is_(True))
            .count()
        )
        print(f"ETUTKOC mevcut plan={inst.plan!r} · aktif öğretmen={teachers}")
        if inst.plan == TARGET:
            print("Zaten Etüt Standart — değişiklik yok.")
            return 0

        actor = (
            db.query(User)
            .filter(User.institution_id == inst.id, User.role == UserRole.INSTITUTION_ADMIN)
            .first()
        )
        change_plan(
            db,
            owner_type=PlanOwnerType.INSTITUTION,
            owner_id=inst.id,
            new_plan=TARGET,
            reason=PlanChangeReason.UPGRADE,
            actor_user_id=actor.id if actor else None,
            note="Limit aşımı çözümü — kullanıcı onayıyla Etüt Standart (3/2 → 3/10)",
            autocommit=True,
        )
        db.refresh(inst)
        info = get_plan_info(inst.plan)
        q = PLAN_QUOTAS.get(inst.plan, {})
        print(f"YENİ plan={inst.plan!r} ({info.label if info else '?'})")
        print(f"Yeni limitler: öğretmen={q.get('teachers')} · öğrenci={q.get('students')} · yönetici={q.get('institution_admins')}")
        print(f"Sonuç: öğretmen {teachers}/{q.get('teachers')} (limit aşımı giderildi).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
