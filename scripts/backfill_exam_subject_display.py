"""Kayıtlı PDF içe-aktarımlarının ders kırılımını (subject_nets) güncel sunum
kurallarıyla yeniden kur — okul-müfredat sınavında sınıf dersinin adıyla
BİRLEŞİK ("Türk Dili ve Edebiyatı 30" — "TDE 21 + TYT Türkçe 9" değil).

Sunum birleştirme 2026-07-18'de geldi; ondan önce kaydedilen içe-aktarımların
kırılımı karma kalmıştı. İdempotent: değişiklik gerekmeyen kayıt atlanır.
Toplamlar/net/soru satırları DEĞİŞMEZ — yalnız görünüm JSON'u.

Kullanım: PYTHONPATH=. python -m scripts.backfill_exam_subject_display
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models import ExamResult, User
from app.services import exam_import_service as svc


def main() -> int:
    changed = 0
    skipped = 0
    with SessionLocal() as db:
        exams = (
            db.query(ExamResult)
            .filter(ExamResult.import_source == "pdf_import")
            .order_by(ExamResult.id.asc())
            .all()
        )
        for e in exams:
            student = db.get(User, e.student_id)
            if student is None:
                skipped += 1
                continue
            try:
                if svc.rebuild_subject_nets(db, e, student):
                    changed += 1
                    print(f"  ~ exam #{e.id} ({e.title[:50]}) — kırılım yeniden kuruldu")
                else:
                    skipped += 1
            except Exception as ex:  # noqa: BLE001 — tek kayıt hatası taramayı durdurmasın
                skipped += 1
                print(f"  ! exam #{e.id} atlandı: {ex}")
        db.commit()
    print(f"Bitti: {changed} güncellendi · {skipped} değişmedi/atlandı "
          f"(toplam {len(exams)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
