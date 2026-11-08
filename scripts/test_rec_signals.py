# -*- coding: utf-8 -*-
"""Öneri sinyalleri (rec_signals) — saf fonksiyon testleri, veritabanı gerekmez.

Asıl korunan sözleşme: sinyaller GELECEĞİ görmez. "Verildi" sinyalleri as_of'a
kadar planlananı, "yapıldı / doğru mu" sinyalleri yalnız outcome_before'dan
önceki günleri sayar. Yanlışsa backtest şişer, canlıda bugünün açık görevi
"yapılmadı" diye cezalanır.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.models.exam_result import EQ_RESULT_DOGRU, EQ_RESULT_YANLIS  # noqa: E402
from app.services import rec_signals as rs  # noqa: E402

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


D0 = date(2026, 11, 10)  # Salı


def item(days_before, section, *, subj=1, topic=None, planned=3, done=0, c=None, w=None, draft=False, tid=0):
    return rs.ItemRec(
        date=D0 - timedelta(days=days_before), task_id=tid or (1000 - days_before), is_draft=draft,
        task_done=done >= planned, book_id=1, section_id=section, subject_id=subj, topic_id=topic,
        planned=planned, completed=done, correct=c, wrong=w,
    )


def feats(b, section, *, subj=1, topic=None, prev=None, remaining=5, prev_finished=True, coverage=None):
    return rs.section_features(b, section_id=section, subject_id=subj, topic_id=topic,
                               prev_section_id=prev, remaining=remaining,
                               prev_finished=prev_finished, coverage=coverage)


def main() -> int:
    items = sorted([
        item(1, 10, planned=3, done=3),            # dün verildi, yapıldı
        item(5, 11, planned=4, done=1),            # 5 gün önce, 3 yapılmadı
        item(12, 12, subj=2, planned=4, done=0),   # ders 2, 12 gün önce, hiç yapılmadı
        item(3, 13, topic=7, planned=2, done=2, c=4, w=8),  # konu 7'de %33 doğru
        item(2, 14, planned=5, done=0, draft=True),          # taslak — sayılmaz
        item(0, 15, planned=3, done=0),            # bugün — açık
        item(-2, 16, planned=2, done=0),           # gelecek — as_of sonrası
    ], key=lambda r: (r.date, r.task_id))

    b = rs.build_signals(items, D0, outcome_before=D0)

    f, why = feats(b, 10)
    check("1. dün verilen bölüm → iplik devamı 1.0 + 'dün verildi'",
          f.get("thread") == 1.0 and why.get("thread") == "dün verildi", f"{f} {why}")
    f, why = feats(b, 11)
    check("2. 5 gün önce verilip 3'ü yapılmayan bölüm → yapılmayan görev sinyali sayılı",
          f.get("neglect", 0) > 0 and "3 test" in why.get("neglect", ""), f"{f} {why}")
    check("3. gelecek günün kalemi as_of'tan sonra → iplik sayılmaz",
          16 not in b.recent_sections, b.recent_sections)
    check("4. taslak görev ne iplik ne yapılmayan sayılır",
          14 not in b.recent_sections and 14 not in b.section_undone, (b.recent_sections, b.section_undone))
    # Yarını planlarken: bugünün görevi verildi ama sonucu henüz belli değil
    bt = rs.build_signals(items, D0 + timedelta(days=1), outcome_before=D0)
    check("5. yarın planlanırken bugünün açık görevi 'yapılmadı' SAYILMAZ",
          15 not in bt.section_undone, bt.section_undone)
    check("6. yarın planlanırken bugünün görevi 'verildi' sayılır (iplik devamı)",
          15 in bt.recent_sections and 16 not in bt.recent_sections, bt.recent_sections)

    f, why = feats(b, 99, topic=7)
    check("7. son günlerde %33 doğru konu → zorlanma sinyali + '4D 8Y'",
          f.get("struggle", 0) > 0 and "4D 8Y" in why.get("struggle", ""), f"{f} {why}")

    f, why = feats(b, 50, subj=2)
    check("8. ders 2 son 12 gündür programda yok → ders boşluğu sinyali",
          f.get("subject_gap", 0) > 0 and "12 gün" in why.get("subject_gap", ""), f"{f} {why}")

    # outcome_before planlama gününe çekilirse: 5 gün önceki kalemin sonucu henüz yok
    b2 = rs.build_signals(items, D0, outcome_before=D0 - timedelta(days=6))
    check("9. planlama 6 gün önce yapıldıysa 5 gün önceki 'yapılmayan' görünmez",
          11 not in b2.section_undone and 11 in b2.recent_sections, (b2.section_undone, b2.recent_sections))
    check("10. zorlanma da sonucu belli günlerle sınırlı (3 gün önceki doğruluk yok)",
          7 not in b2.topic_recent, b2.topic_recent)

    f, _ = feats(b, 20, prev=10, prev_finished=True)
    check("11. biten ve dün verilen bölümün ardılı → 'sıradaki bölüm'",
          f.get("thread_next", 0) > 0, f)
    f, _ = feats(b, 20, prev=10, prev_finished=False)
    check("12. önceki bölüm BİTMEMİŞSE ardılı sıradaki sayılmaz", "thread_next" not in f, f)

    exam = [
        (D0 - timedelta(days=10), 30, EQ_RESULT_YANLIS),
        (D0 - timedelta(days=10), 30, EQ_RESULT_YANLIS),
        (D0 - timedelta(days=10), 30, EQ_RESULT_YANLIS),
        (D0 - timedelta(days=10), 31, EQ_RESULT_YANLIS),
        (D0 - timedelta(days=10), 31, EQ_RESULT_YANLIS),
        (D0 - timedelta(days=10), 31, EQ_RESULT_DOGRU),
        (D0 - timedelta(days=10), 31, EQ_RESULT_DOGRU),
        (D0 - timedelta(days=10), 31, EQ_RESULT_DOGRU),
        (D0 - timedelta(days=10), 31, EQ_RESULT_DOGRU),
        (D0 + timedelta(days=3), 32, EQ_RESULT_YANLIS),
        (D0 + timedelta(days=3), 32, EQ_RESULT_YANLIS),
    ]
    b3 = rs.build_signals([], D0, exam_rows=exam)
    f, why = feats(b3, 1, topic=30)
    check("13. denemede 3 yanlış → deneme sinyali '3 yanlış'",
          f.get("exam_weak", 0) > 0 and "3 yanlış" in why.get("exam_weak", ""), f"{f} {why}")
    f, _ = feats(b3, 1, topic=31)
    check("14. doğruluğu ≥%60 konu (2Y 4D) deneme sinyali üretmez", "exam_weak" not in f, f)
    check("15. as_of sonrası deneme yanlışı sayılmaz", 32 not in b3.exam_topic, b3.exam_topic)

    cov = rs.subject_coverage_lag([(1, 100, 20), (2, 100, 60), (3, 100, 70)])
    f, why = feats(b3, 1, subj=1, coverage=cov.get(1))
    check("16. dersin kaynağı %20, diğerleri ort. %65 → kaynakta geride kalan ders",
          f.get("coverage_lag", 0) > 0 and "%20" in why.get("coverage_lag", ""), f"{f} {why}")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
