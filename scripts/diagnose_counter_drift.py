"""Sayaç uyumsuzluğu boyut + neden teşhisi (SALT OKUMA, 2026-09-27).

1) Sistem geneli: section_counter_service.compute_fixes → sapma sayısı,
   öğrenci/kitap kırılımı, fazla/eksik rezerv toplamı.
2) --student N: sapan her bölüm için TÜM görev kalemleri (released/tamamlanmış
   dahil) + ilgili audit izleri → rezervin nereden geldiği.

python -m scripts.diagnose_counter_drift [--student 164]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import BookSection, SectionProgress, StudentBook, Task, TaskBookItem, User
from app.services.section_counter_service import compute_fixes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int)
    a = ap.parse_args()
    with SessionLocal() as db:
        fixes = compute_fixes(db)
        print(f"SİSTEM: sapan bölüm {len(fixes)}")
        by_student: dict[int, list] = defaultdict(list)
        for f in fixes:
            by_student[f.student_id].append(f)
        over = sum(max(0, f.old_reserved - f.new_reserved) for f in fixes)
        under = sum(max(0, f.new_reserved - f.old_reserved) for f in fixes)
        comp = sum(1 for f in fixes if f.old_completed != f.new_completed)
        print(f"  fazla rezerv toplam {over} · eksik rezerv toplam {under} · completed farkı {comp} bölüm")
        for sid, fs in sorted(by_student.items(), key=lambda x: -len(x[1])):
            u = db.get(User, sid)
            books = Counter(f.book_name for f in fs)
            ov = sum(f.old_reserved - f.new_reserved for f in fs)
            print(f"  öğrenci #{sid} {u.full_name if u else '?'} (koç {u.teacher_id if u else '?'}): "
                  f"{len(fs)} bölüm, net rezerv farkı {ov:+d} · kitaplar {dict(books)}")

        if a.student:
            print(f"\n=== AYRINTI öğrenci #{a.student} ===")
            for f in [x for x in fixes if x.student_id == a.student]:
                print(f"\n[{f.book_name}] {f.section_label} (sec {f.section_id}) "
                      f"kayıtlı rez {f.old_reserved} → gerçek {f.new_reserved}; "
                      f"çöz {f.old_completed} → {f.new_completed}")
                items = (db.query(TaskBookItem, Task)
                         .join(Task, TaskBookItem.task_id == Task.id)
                         .filter(TaskBookItem.book_section_id == f.section_id,
                                 Task.student_id == a.student)
                         .order_by(Task.date).all())
                for it, t in items:
                    print(f"   task {t.id} {t.date} {t.status.value} draft={t.is_draft} "
                          f"plan {it.planned_count} done {it.completed_count} "
                          f"released={it.reservation_released_at} created={t.created_at} "
                          f"title={t.title[:60]!r}")
                if not items:
                    print("   (bu bölümde HİÇ görev kalemi yok — rezerv sahipsiz)")
            # Kitap-dışı bölüme işaret eden kalem var mı? (book_id ≠ section.book_id)
            bad = (db.query(TaskBookItem, BookSection)
                   .join(BookSection, TaskBookItem.book_section_id == BookSection.id)
                   .join(Task, TaskBookItem.task_id == Task.id)
                   .filter(Task.student_id == a.student,
                           TaskBookItem.book_id != BookSection.book_id).count())
            print(f"\nkitap/bölüm uyumsuz kalem: {bad}")
            # Silinmiş görevden kalan izler: audit
            try:
                from app.models import AuditLog
                logs = (db.query(AuditLog)
                        .filter(AuditLog.target_user_id == a.student)
                        .order_by(AuditLog.created_at.desc()).limit(40).all())
                print("\nson audit:")
                for l in logs:
                    print(f"   {l.created_at} {l.action.value} {str(l.details)[:160]}")
            except Exception as e:  # noqa: BLE001
                print("audit okunamadı:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
