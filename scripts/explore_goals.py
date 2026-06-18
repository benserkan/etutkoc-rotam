"""Hedefler keşif/deneme — demo doğruluğu için GERÇEK ağaç + aggregate + tohumlama.

Koç bir öğrenciye haftalık hedef + alt hedef ekler, ilerleme girer, alt hedefi
'tamamlandı' yapar (üst hedefe yansıma), sonra 'sınav hedefinden otomatik ağaç'
tohumlar ve ne ürettiğini + panelde görünüp görünmediğini gösterir. SALT-DENEME.

  python -m scripts.explore_goals
"""
from __future__ import annotations
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import secrets
from sqlalchemy import delete as sa_delete
from app.database import SessionLocal
from app.models import StudentGoal, User, UserRole
from app.models.student_goal import GoalKind
from app.services import goals, goals_auto
from app.services.security import hash_password

PFX = f"goal_{secrets.token_hex(3)}"


def show_tree(nodes, depth=0):
    for n in nodes:
        g = n.goal
        pct = f"%{n.aggregated_pct}" if n.aggregated_pct is not None else "—"
        auto = " [otomatik]" if g.is_auto_generated else ""
        cnt = f" ({n.achieved_count}/{n.total_count} alt tamam)" if n.children else ""
        print(f"   {'  '*depth}• {g.kind.value:11} {g.title[:34]:34} {g.status.value:9} "
              f"ilerleme={pct}{cnt}{auto}")
        if n.children:
            show_tree(n.children, depth + 1)


def main():
    db = SessionLocal()
    uids = []
    try:
        coach = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x12345678"),
                     full_name=f"{PFX}-coach", role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add(coach); db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x12345678"),
                   full_name=f"{PFX}-stu", role=UserRole.STUDENT, teacher_id=coach.id,
                   is_active=True, grade_level=11)
        # YKS + AYT sayısal alan (otomatik tohum için)
        for attr, val in [("exam_target", "YKS"), ("track", "sayisal"), ("ayt_track", "sayisal")]:
            if hasattr(stu, attr):
                setattr(stu, attr, val)
        db.add(stu); db.flush()
        uids = [coach.id, stu.id]
        db.commit()
        print(f"=== HEDEFLER DENEMESİ — {PFX} (11/YKS) ===\n")

        # 1) Koç haftalık hedef + 2 alt hedef ekler
        parent = goals.create_goal(db, student=stu, kind=GoalKind.WEEKLY,
                                   title="Bu hafta 50 test çöz", target_value=50,
                                   current_value=0, unit="test", created_by_user_id=coach.id)
        c1 = goals.create_goal(db, student=stu, kind=GoalKind.TOPIC, parent_id=parent.id,
                               title="Türev 20 test", target_value=20, current_value=0,
                               unit="test", created_by_user_id=coach.id)
        c2 = goals.create_goal(db, student=stu, kind=GoalKind.TOPIC, parent_id=parent.id,
                               title="İntegral 30 test", target_value=30, current_value=0,
                               unit="test", created_by_user_id=coach.id)
        print("1) Koç ekledi: 'Bu hafta 50 test çöz' (haftalık) + 2 alt hedef (Türev/İntegral).")

        # 2) Öğrenci ilerleme girer
        goals.update_goal(db, goal=c1, current_value=10)   # Türev 10/20
        goals.update_goal(db, goal=c2, current_value=15)   # İntegral 15/30
        db.commit()
        print("2) Öğrenci ilerleme girdi: Türev 10/20, İntegral 15/30.")
        print("\n   Ağaç (alt ilerlemeler üst hedefe yansır):")
        show_tree(goals.build_tree(db, student_id=stu.id))

        # 3) Alt hedef tamamlandı
        goals.mark_achieved(db, goal=c1)
        db.commit()
        print("\n3) 'Türev 20 test' → Tamamlandı işaretlendi:")
        show_tree(goals.build_tree(db, student_id=stu.id))

        # 4) Otomatik sınav hedefi ağacı tohumla
        res = goals_auto.seed_for_exam_target(db, student=stu, created_by_user_id=coach.id)
        db.commit()
        print(f"\n4) 'Sınav hedefinden otomatik ağaç türet' → {res}")
        all_goals = goals.list_student_goals(db, student_id=stu.id)
        auto = [g for g in all_goals if g.is_auto_generated]
        print(f"   Üretilen otomatik hedef: {len(auto)} → " +
              ", ".join(f"{g.kind.value}:{g.title}" for g in auto[:8]))

        # 5) Özet
        summ = goals.student_goal_summary(db, student_id=stu.id)
        print(f"\n5) ÖZET (özet kartları): toplam={summ['total']} aktif={summ['active']} "
              f"tamam={summ['achieved']} genel=%{summ['overall_pct']}")
        print("\n=== ÖZET: hiyerarşik hedef (üst↔alt), alt ilerleme üste yansır, "
              "tamamla→sayım; otomatik sınav ağacı koç tek tıkla tohumlar ===")
        return 0
    finally:
        try:
            if uids:
                db.execute(sa_delete(StudentGoal).where(StudentGoal.student_id.in_(uids)))
                db.execute(sa_delete(User).where(User.id.in_(uids)))
                db.commit()
        except Exception as e:
            print(f"(cleanup uyarı: {e})")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
