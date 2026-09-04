"""Mevcut öğrencilere sınıf dönemi damgası aç (P2 geriye dönük doldurma).

Sınıf geçmişi kayıtlı olmadığı için tek seferlik TAHMİN yapılır:
  · Sınır = mevcut öğretim yılının 1 Eylül'ü.
  · Öğrencinin kaydı sınırdan ESKİYSE ve sınır öncesinde verisi VARSA
    iki dönem açılır: geçmiş (sınıf−1) + güncel.
  · Aksi halde tek dönem (kayıt tarihinden bugüne).

Tahmin yanlış çıkarsa koç öğrenci sayfasındaki dönem listesinden düzeltir
(başlangıç tarihini değiştirme / gereksiz dönemi silme).

İDEMPOTENT: zaten dönemi olan öğrenciye dokunmaz.

Çalıştırma:
  python -m scripts.backfill_grade_periods              # önizleme (dry-run)
  python -m scripts.backfill_grade_periods --apply
  python -m scripts.backfill_grade_periods --student-id 2 --apply
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import date

from app.database import SessionLocal
from app.models import Task, User, UserRole
from app.services import grade_period_service as gp


def _lbl(grade: int | None, is_grad: bool) -> str:
    if is_grad:
        return "Mezun"
    return f"{grade}. sinif" if grade is not None else "sinif belirsiz"


def run(student_id: int | None = None, apply_changes: bool = False) -> int:
    db = SessionLocal()
    try:
        q = db.query(User).filter(User.role == UserRole.STUDENT)
        if student_id:
            q = q.filter(User.id == student_id)
        students = q.order_by(User.id).all()

        today = date.today()
        boundary = gp.academic_year_start_date(today)
        print(f"Ogretim yili siniri : {boundary}")
        print(f"Taranan ogrenci     : {len(students)}")

        planned: list[tuple[User, int, str]] = []
        repairs: list = []
        for s in students:
            if gp.list_periods(db, s.id):
                # Zaten donemi var — yalniz ilk donem baslangici gecmise donuk
                # girilmis kaydi kapsamiyorsa geriye cek (idempotent onarim).
                rows = sorted(gp.list_periods(db, s.id), key=lambda p: p.started_on)
                earliest = gp.earliest_data_date(db, s.id)
                if earliest is not None and earliest < rows[0].started_on:
                    repairs.append((s, rows[0].started_on, earliest))
                continue
            has_old = (
                db.query(Task.id)
                .filter(Task.student_id == s.id, Task.date < boundary)
                .first()
                is not None
            )
            prev_grade, prev_grad = gp._previous_grade(s)
            created = getattr(s, "created_at", None)
            created_on = created.date() if created else today
            grade_changed = prev_grade != s.grade_level or prev_grad != bool(
                s.is_graduate
            )
            split = (
                has_old
                and created_on < boundary
                and (prev_grad or (prev_grade is not None and prev_grade >= 5))
                and grade_changed
            )
            if split:
                prev_label = _lbl(prev_grade, prev_grad)
                cur_label = _lbl(s.grade_level, bool(s.is_graduate))
                note = f"2 donem: {prev_label} [{created_on} - {boundary}) + {cur_label}"
                planned.append((s, 2, note))
            else:
                cur_label = _lbl(s.grade_level, bool(s.is_graduate))
                planned.append((s, 1, f"1 donem: {cur_label} [{min(created_on, today)} -]"))

        print(f"Donemi olmayan      : {len(planned)}")
        print(f"Ilk donem onarimi   : {len(repairs)}")
        if not planned and not repairs:
            print("Yapilacak bir sey yok.")
            return 0

        if repairs:
            print("\n--- ILK DONEM ONARIMI (gecmise donuk kayit kapsansin) ---")
            for s, old_start, new_start in repairs:
                print(f"  #{s.id:<5} {(s.full_name or '')[:32]:<32} {old_start} -> {new_start}")

        print("\n--- PLAN ---")
        for s, n, note in planned:
            print(f"  #{s.id:<5} {(s.full_name or '')[:32]:<32} {note}")

        if not apply_changes:
            print("\nDry-run (varsayilan) - hicbir sey yazilmadi. Uygulamak icin: --apply")
            return 0

        repaired = 0
        for s, _o, _n in repairs:
            if gp.repair_first_start(db, s.id) is not None:
                repaired += 1

        created_total = 0
        for s, _n, _note in planned:
            has_old = (
                db.query(Task.id)
                .filter(Task.student_id == s.id, Task.date < boundary)
                .first()
                is not None
            )
            created_total += gp.backfill_student(
                db, s, today=today, has_old_data=has_old
            )
        db.commit()
        print(
            f"\n{created_total} donem kaydi olusturuldu, "
            f"{repaired} ilk donem onarildi ve commit edildi."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int, default=None)
    ap.add_argument("--apply", action="store_true", help="Gercekten uygula")
    args = ap.parse_args()
    raise SystemExit(run(student_id=args.student_id, apply_changes=args.apply))
