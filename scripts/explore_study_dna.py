"""Çalışma DNA keşif/deneme — demo doğruluğu için GERÇEK profil + burnout çıktısı.

Gece çalışan bir test öğrencisi üretir (tamamlamalar TR 23:00 + hafta sonu dahil),
compute_profile + compute_burnout çağırır, chronotype/peak/saat bandı/sinyaller/
risk skorunu yazdırır. Sonunda temizler. SALT-DENEME.

  python -m scripts.explore_study_dna
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
from app.models import (
    Book, BookSection, BookType, Subject, Task, TaskBookItem, TaskStatus,
    TaskType, User, UserRole,
)
from app.services import study_dna, burnout
from app.services.security import hash_password

PFX = f"dna_{secrets.token_hex(3)}"
now = datetime.now(timezone.utc)
ids = {"users": [], "subject": None, "book": None, "section": None, "tasks": []}


def main():
    db = SessionLocal()
    try:
        coach = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x12345678"),
                     full_name=f"{PFX}-coach", role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add(coach); db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x12345678"),
                   full_name=f"{PFX}-stu", role=UserRole.STUDENT, teacher_id=coach.id,
                   is_active=True, grade_level=11)
        db.add(stu); db.flush()
        ids["users"] = [coach.id, stu.id]
        subj = Subject(name=f"{PFX} Mat", teacher_id=coach.id); db.add(subj); db.flush()
        ids["subject"] = subj.id
        book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} SB", type=BookType.SORU_BANKASI)
        db.add(book); db.flush(); ids["book"] = book.id
        sec = BookSection(book_id=book.id, label="Ü1", test_count=500); db.add(sec); db.flush()
        ids["section"] = sec.id

        # Son 16 gün: her gün TR 23:00 (UTC 20:00) tamamlama — gece kuşu + hafta sonu dahil
        def mk(day_offset, utc_hour, planned=20):
            d = (now - timedelta(days=day_offset))
            comp = d.replace(hour=utc_hour, minute=0, second=0, microsecond=0)
            t = Task(student_id=stu.id, date=comp.date(), type=TaskType.TEST, title="P",
                     is_draft=False, published_at=comp, status=TaskStatus.COMPLETED, completed_at=comp)
            db.add(t); db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id,
                                planned_count=planned, completed_count=planned,
                                correct_count=planned - 3, wrong_count=3))
            ids["tasks"].append(t.id)

        for off in range(0, 16):
            mk(off, 20)              # TR 23:00 (gece) — her gün, hafta sonu dahil
        for off in [2, 5, 9]:
            mk(off, 5)               # TR 08:00 (sabah) — birkaç kontrast
        db.commit()

        print(f"=== ÇALIŞMA DNA DENEMESİ — {PFX} (11. sınıf, gece çalışan) ===\n")

        prof = study_dna.compute_profile(db, student_id=stu.id, window_days=28, now=now)
        print("1) PROFİL (compute_profile):")
        print(f"   yeterli veri: {prof.has_enough_data}  · pencere: {prof.window_days} gün")
        print(f"   chronotype: {prof.chronotype}  · peak saat: {prof.peak_hour}:00  · peak gün: {prof.peak_day_name}")
        print(f"   saat bandı → Sabah={prof.morning_count} Öğle={prof.afternoon_count} "
              f"Akşam={prof.evening_count} Gece={prof.night_count}")
        print(f"   hafta içi={prof.weekday_count} hafta sonu={prof.weekend_count}")
        print(f"   görev: {prof.display_gorev_done}/{prof.display_gorev_total} · "
              f"test: {prof.display_test_completed}/{prof.display_test_planned}")
        print(f"   saat verisi güveni: %{prof.hour_data_confidence}  (batch={prof.batch_completion_count})")
        # heatmap özeti — en yoğun 3 hücre
        cells = [(prof.heatmap[d][h], d, h) for d in range(7) for h in range(24) if prof.heatmap[d][h] > 0]
        cells.sort(reverse=True)
        days = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"]
        top = ", ".join(f"{days[d]} {h:02d}:00→{v}" for v, d, h in cells[:4])
        print(f"   heatmap en yoğun: {top}")

        print("\n2) TÜKENMİŞLİK (compute_burnout):")
        rep = burnout.compute_burnout(db, student_id=stu.id, window_days=21, now=now)
        print(f"   risk skoru: {rep.risk_score}/100  → seviye: {rep.risk_level}")
        if not rep.signals:
            print("   (sinyal yok)")
        for s in rep.signals:
            print(f"   • {s.emoji} {s.label} [{s.severity}] — {s.detail}")

        print("\n=== ÖZET: gece tamamlamaları → chronotype 'night/gececi', peak 23:00, "
              "night_owl sinyali + risk skoru; koç bunu DNA panelinde görür, veliye mesajlar ===")
        return 0
    finally:
        try:
            if ids["tasks"]:
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(ids["tasks"])))
                db.execute(sa_delete(Task).where(Task.id.in_(ids["tasks"])))
            if ids["section"]:
                db.execute(sa_delete(BookSection).where(BookSection.id == ids["section"]))
            if ids["book"]:
                db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            if ids["subject"]:
                db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
            if ids["users"]:
                db.execute(sa_delete(User).where(User.id.in_(ids["users"])))
            db.commit()
        except Exception as e:
            print(f"(cleanup uyarı: {e})")
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
