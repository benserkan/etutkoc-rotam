"""Mevcut PDF içe aktarımlarına belge parmak izi (SHA-256) yaz — idempotent.

Mükerrer koruması katman 1 (2026-09-19) yeni kayıtlarda otomatik dolar; eski
kayıtlarda PDF kanıtı zaten saklı olduğu için özet buradan hesaplanır.
Yalnız `import_pdf_sha256 IS NULL` ve PDF verisi olan satırlar; ikinci koşu 0.

Kullanım: PYTHONPATH=. python scripts/backfill_exam_pdf_sha.py [--apply]
  (bayraksız = dry-run, yalnız sayar)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy.orm import undefer

from app.database import SessionLocal
from app.models import ExamResult
from app.services import exam_duplicate


def main() -> int:
    apply = "--apply" in sys.argv
    with SessionLocal() as db:
        q = (
            db.query(ExamResult)
            .options(undefer(ExamResult.import_pdf_data))
            .filter(
                ExamResult.import_source == "pdf_import",
                ExamResult.import_pdf_sha256.is_(None),
            )
        )
        rows = q.all()
        done = skipped = 0
        for e in rows:
            sha = exam_duplicate.pdf_sha256(e.import_pdf_data)
            if not sha:
                skipped += 1
                continue
            if apply:
                e.import_pdf_sha256 = sha
            done += 1
        if apply:
            db.commit()
    mode = "UYGULANDI" if apply else "DRY-RUN"
    print(f"[{mode}] parmak izi yazıl{'dı' if apply else 'acak'}: {done} · PDF verisi yok (atlandı): {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
