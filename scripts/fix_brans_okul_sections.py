"""Okul dersinden verilen branş denemelerinin sınav türünü düzelt (2026-11-08).

Sorun: Maarif/Klasik lise dersleri (Fizik, Kimya, Tarih…) seed'de TYT/AYT sınav türü
taşıyordu; deneme görevi bu türü kaleme yazdı → 10. sınıfın "Fizik branş denemesi"
AYT Sayısal serisine, "Matematik" TYT serisine düştü. Artık okul dersi "okul" (sınıf
düzeyi) sayılır (deneme_service.exam_section_for_subject). Bu betik eski kalemleri
aynı kurala çeker; köprü (deneme_bridge) bağlı deneme kaydını flush'ta yeniden kurar.

Kapsam: görev kalemleri + havuz kalemleri; YALNIZ dersi okul dersi olan, branş/genel
deneme kalemleri. Kitaplı genel deneme (türü koçun seçtiği hazır türden gelir) atlanır.
Kuru çalışma varsayılan; --apply yazar. İdempotent.

    python -m scripts.fix_brans_okul_sections
    python -m scripts.fix_brans_okul_sections --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from app.database import SessionLocal
from app.models import TaskBookItem, User
from app.models.pool import PoolItem
from app.services.deneme_service import EXAM_KIND_BRANS, exam_section_for_subject, item_subject


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    db = SessionLocal()
    report: Counter[tuple] = Counter()
    n = 0

    items = db.query(TaskBookItem).filter(TaskBookItem.exam_kind == EXAM_KIND_BRANS).all()
    for it in items:
        subj = item_subject(it)
        want = exam_section_for_subject(subj)
        if want != "okul" or (it.exam_section or "") == "okul":
            continue
        st = db.get(User, it.task.student_id) if it.task else None
        report[("gorev", st.full_name if st else "?", st.grade_level if st else None,
                subj.name, it.exam_section, "sonuçlu" if it.correct_count is not None else "sonuçsuz")] += 1
        n += 1
        if args.apply:
            it.exam_section = "okul"

    pools = db.query(PoolItem).filter(PoolItem.exam_kind == EXAM_KIND_BRANS).all()
    for p in pools:
        subj = p.subject
        if exam_section_for_subject(subj) != "okul" or (p.exam_section or "") == "okul":
            continue
        report[("havuz", "", None, subj.name if subj else "?", p.exam_section, "")] += 1
        n += 1
        if args.apply:
            p.exam_section = "okul"

    for (kind, who, grade, subj, old, state), c in sorted(report.items(), key=str):
        print(f"[{kind}] {who} ({grade}. sınıf) · {subj}: {old} → okul · {state} (x{c})")
    print(f"\nÖZET: {n} kalem")
    if args.apply:
        db.commit()
        print("UYGULANDI.")
    else:
        db.rollback()
        print("(kuru çalışma — yazmak için --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
