"""Gerçek analytics.generate_warnings çıktısını doğrular (subject_untouched fix).

Salt-okuma. Bir öğrenci için ÜRETİLEN uyarı kodlarını listeler — subject_untouched_*
kodunun olup olmadığını gösterir.

  python -m scripts.verify_subject_untouched_fix --student-id 11
"""
from __future__ import annotations

import argparse
from datetime import date

from app.database import SessionLocal
from app.models import User
from app.services import analytics


def run(student_id: int) -> int:
    db = SessionLocal()
    try:
        s = db.query(User).filter(User.id == student_id).first()
        if not s:
            print(f"Öğrenci #{student_id} yok.")
            return 1
        today = date.today()
        proj = analytics.compute_projection(db, s, today, window_days=28, buffer_days=5)
        ws = analytics.generate_warnings(db, s, today, proj)
        print(f"=== {s.full_name} (id={s.id}) — generate_warnings çıktısı ===")
        if not ws:
            print("  (uyarı yok)")
        for w in ws:
            print(f"  [{w.level}] {w.code} :: {w.title} — {w.detail}")
        untouched = [w.code for w in ws if w.code.startswith("subject_untouched")]
        print(f"\nsubject_untouched_* uyarısı: {untouched or 'YOK ✓'}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int, required=True)
    args = ap.parse_args()
    raise SystemExit(run(student_id=args.student_id))
