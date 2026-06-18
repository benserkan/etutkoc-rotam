"""Odak (Pomodoro) keşif/deneme — demo doğruluğu için GERÇEK seans davranışı.

Test öğrenci → 25 dk odak bitir + 1 yarıda terk (interrupted) → bugün özeti.
SALT-DENEME; temizler.

  python -m scripts.explore_focus
"""
from __future__ import annotations
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete as sa_delete
from app.database import SessionLocal
from app.models import PomodoroSession, User, UserRole
from app.models.focus import PomodoroKind
from app.services import pomodoro
from app.services.security import hash_password

PFX = f"focus_{secrets.token_hex(3)}"
now = datetime.now(timezone.utc)


def main():
    db = SessionLocal()
    uid = None
    try:
        stu = User(email=f"{PFX}@test.invalid", password_hash=hash_password("x12345678"),
                   full_name=f"{PFX}-stu", role=UserRole.STUDENT, is_active=True, grade_level=11)
        db.add(stu); db.flush(); uid = stu.id
        db.commit()
        print(f"=== ODAK (POMODORO) DENEMESİ — {PFX} ===\n")

        s1 = pomodoro.start_session(db, student_id=uid, planned_minutes=25,
                                    kind=PomodoroKind.WORK, label="Matematik · paragraf",
                                    now=now - timedelta(minutes=25))
        pomodoro.end_session(db, session=s1, actual_minutes=25, interrupted=False, now=now - timedelta(minutes=1))
        print("1) 25 dk odak seansı (Matematik) başlatıldı + tamamlandı (Bitir).")

        s2 = pomodoro.start_session(db, student_id=uid, planned_minutes=50,
                                    kind=PomodoroKind.WORK, label="Fizik", now=now - timedelta(minutes=10))
        pomodoro.end_session(db, session=s2, actual_minutes=None, interrupted=True, now=now)  # Yarıda terk
        print("2) 50 dk odak seansı (Fizik) → 'Yarıda terk et' (interrupted=True, server süre hesapladı).")

        s3 = pomodoro.start_session(db, student_id=uid, planned_minutes=5,
                                    kind=PomodoroKind.SHORT_BREAK, now=now - timedelta(minutes=5))
        pomodoro.end_session(db, session=s3, actual_minutes=5, interrupted=False, now=now)
        print("3) 5 dk kısa mola tamamlandı.")
        db.commit()

        summ = pomodoro.today_summary(db, student_id=uid, now=now)
        wmin30 = pomodoro.total_work_minutes(db, student_id=uid, since_days=30, now=now)
        print(f"\n4) BUGÜN ÖZETİ: odak seansı={summ.work_sessions} · odak dk={summ.work_minutes} · "
              f"mola dk={summ.break_minutes} · yarıda bırakılan={summ.interrupted_count}")
        print(f"   30g toplam odak dk={wmin30}")
        s2b = db.get(PomodoroSession, s2.id)
        print(f"   (Fizik seansı: planlanan 50 / gerçek {s2b.actual_minutes} dk · interrupted={s2b.interrupted})")
        print("\n=== ÖZET: süre+tür+etiket seç → Başlat → Bitir/Yarıda terk → bugün özeti "
              "(odak dk/seri/puan); koç bunu salt-okuma izler (rozet/seri/30g) ===")
        return 0
    finally:
        try:
            if uid:
                db.execute(sa_delete(PomodoroSession).where(PomodoroSession.student_id == uid))
                db.execute(sa_delete(User).where(User.id == uid))
                db.commit()
        except Exception as e:
            print(f"(cleanup uyarı: {e})")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
