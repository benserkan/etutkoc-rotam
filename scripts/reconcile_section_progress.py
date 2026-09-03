"""SectionProgress sayaçlarını gerçek görev verisinden yeniden hesapla (CLI).

`reserved_count` / `completed_count` drift edebilir (görev doğrudan silindiğinde,
elle SQL müdahalesinde, geçmişte düzeltilmiş bir rezerv bug'ı nedeniyle). Drift
olunca koç kitap ızgarasında "sayaç uyumsuzluğu" görür ve ölü rezerv yüzünden o
bölüme yeni test atayamaz.

HESAP MANTIĞI `app/services/section_counter_service.py` içinde — TEK MERKEZ:
aynı kuralları koçun panelden tetiklediği uç da kullanır
(`POST /api/v2/teacher/students/{id}/books/{book_id}/reconcile-counters`).
Bu dosya yalnız CLI sarmalayıcısıdır (toplu tarama / sistem geneli onarım).

  expected_reserved  = Σ max(0, planned − completed) · YALNIZ
                       reservation_released_at IS NULL + görevi COMPLETED
                       olmayan kalemler (TASLAK DAHİL — taslak da kilitler)
  expected_completed = max(kayıtlı, Σ kalem completed) — baseline korunur

Çalıştırma:
  # Önizleme (varsayılan — hiçbir şey değiştirmez):
  python -m scripts.reconcile_section_progress
  python -m scripts.reconcile_section_progress --student-id 84

  # Gerçekten uygula:
  python -m scripts.reconcile_section_progress --apply
"""
from __future__ import annotations

import argparse

from app.database import SessionLocal
from app.models import SectionProgress, StudentBook, User
from app.services.section_counter_service import apply_fixes, compute_fixes


def run(student_id: int | None = None, apply_changes: bool = False) -> int:
    db = SessionLocal()
    try:
        fixes = compute_fixes(db, student_id=student_id)

        q = db.query(SectionProgress).join(
            StudentBook, SectionProgress.student_book_id == StudentBook.id
        )
        if student_id:
            q = q.filter(StudentBook.student_id == student_id)
        scanned = q.count()

        print(f"Incelenen SectionProgress sayisi: {scanned}")
        print(f"Duzeltilecek kayit sayisi:        {len(fixes)}")
        if not fixes:
            print("Drift yok - hicbir sey degismedi.")
            return 0

        names = {
            u.id: u.full_name
            for u in db.query(User).filter(
                User.id.in_({f.student_id for f in fixes})
            ).all()
        }
        print("\n--- DEGISIKLIK LISTESI ---")
        for i, f in enumerate(fixes, 1):
            print(
                f"[{i}] {names.get(f.student_id, '?')} (id={f.student_id}) | "
                f"{f.book_name} | {f.section_label}"
            )
            print(
                f"    reserved : {f.old_reserved:>3}  ->  {f.new_reserved:>3}    "
                f"completed : {f.old_completed:>3}  ->  {f.new_completed:>3}"
            )

        if not apply_changes:
            print("\nDry-run modu (varsayilan) - hicbir sey uygulanmadi.")
            print("Gercekten uygulamak icin: --apply ekle.")
            return 0

        n = apply_fixes(db, fixes)
        db.commit()
        print(f"\n{n} SectionProgress guncellendi ve commit edildi.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int, default=None)
    ap.add_argument("--apply", action="store_true",
                    help="Gercekten uygula (default: dry-run)")
    args = ap.parse_args()
    raise SystemExit(run(student_id=args.student_id, apply_changes=args.apply))
