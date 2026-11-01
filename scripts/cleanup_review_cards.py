"""Toplu eklenmiş, HİÇ PUANLANMAMIŞ tekrar kartlarını temizle (2026-11-01).

Eski "dersten ekle" dersin tüm konularını ekliyordu (tema başlıkları, alt/üst
sınıf, hiç çalışılmamış konular). Yeni kural: kart yalnız öğrencinin çalıştığı,
denemede yanlış yaptığı, arşivde açık yanlışı olan ya da koçun kapattığı
konuya açılır (review_scheduler.topic_candidates ile AYNI kural).

Silinen kart: state=new + review_count=0 VE (tema başlığı | öğrencinin konu
kümesinde yok | önerilmeyen konu). Puanlanmış kartlara DOKUNULMAZ.

Varsayılan KURU çalışma (yalnız rapor). Uygulamak için --apply.
  python -m scripts.cleanup_review_cards                 # tüm öğrenciler, rapor
  python -m scripts.cleanup_review_cards --student 227   # tek öğrenci
  python -m scripts.cleanup_review_cards --student 227 --student 84 --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import ReviewCard, ReviewLog, Topic, User
from app.models.review import STATE_NEW
from app.services.review_scheduler import topic_candidates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int, action="append", default=[])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        q = db.query(ReviewCard.student_id).distinct()
        if args.student:
            q = q.filter(ReviewCard.student_id.in_(args.student))
        sids = [s for (s,) in q.all()]
        grand_total = grand_del = 0
        to_delete: list[int] = []
        for sid in sorted(sids):
            st = db.get(User, sid)
            if st is None:
                continue
            coach_id = st.teacher_id or 0
            cards = (
                db.query(ReviewCard, Topic)
                .join(Topic, Topic.id == ReviewCard.topic_id)
                .filter(ReviewCard.student_id == sid)
                .all()
            )
            by_subject: dict[int, list] = defaultdict(list)
            for c, t in cards:
                by_subject[t.subject_id].append((c, t))
            kill: list[int] = []
            reasons = defaultdict(int)
            for subj_id, rows in by_subject.items():
                cands = {
                    x.topic_id: x
                    for x in topic_candidates(db, student=st, coach_id=coach_id,
                                              subject_id=subj_id, now=now)
                }
                for c, t in rows:
                    if c.state != STATE_NEW or (c.review_count or 0) > 0:
                        continue
                    cand = cands.get(t.id)
                    if cand is None:
                        kill.append(c.id)
                        reasons["tema başlığı / sınıf dışı"] += 1
                    elif not cand.recommended:
                        kill.append(c.id)
                        reasons["çalışma kaydı yok"] += 1
            grand_total += len(cards)
            grand_del += len(kill)
            to_delete += kill
            print(
                f"#{sid} {st.full_name} (koç #{st.teacher_id}): {len(cards)} kart → "
                f"{len(cards) - len(kill)} kalır, {len(kill)} silinir  {dict(reasons)}"
            )
        print(f"\nTOPLAM: {grand_total} kart, {grand_del} silinecek")
        if not args.apply:
            print("Kuru çalışma — hiçbir şey değişmedi. Uygulamak için --apply.")
            return 0
        if to_delete:
            db.query(ReviewLog).filter(ReviewLog.card_id.in_(to_delete)).delete(synchronize_session=False)
            db.query(ReviewCard).filter(ReviewCard.id.in_(to_delete)).delete(synchronize_session=False)
            db.commit()
        print(f"UYGULANDI: {len(to_delete)} kart silindi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
