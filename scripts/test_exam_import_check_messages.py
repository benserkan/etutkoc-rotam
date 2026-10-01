"""Smoke: deneme içe aktarma uyarıları — karne özetiyle düzeltme + sade mesajlar.

- Boş-cevap korumasının boş saydığı sorular, karnenin özet tablosu tam o kadar
  fazla doğru / eksik boş gösteriyorsa DOĞRU'ya geri çevrilir.
- Fark belirsizse (özet 1 diyor, korumalı 2 satır var) hiçbir satıra dokunulmaz.
- Özet uyuşmazlığı mesajı ne olduğunu ve bakılacak soru numaralarını söyler.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.models.exam_result import EQ_RESULT_BOS, EQ_RESULT_DOGRU, EQ_RESULT_YANLIS
from app.services.exam_import_service import reconcile_with_summary, run_checks

FAILS: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(("  OK   " if cond else "  FAIL ") + label + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(label)


def row(subj, no, dc, oc, res, alt=None):
    return {"exam_part": None, "subject_raw": subj, "question_no": no, "correct_answer": dc,
            "student_answer": oc, "result": res, "is_suspect": False, "_guard_alt": alt}


def fizik_rows(guards: int) -> list[dict]:
    rows = [row("FİZİK", 1, "A", "A", EQ_RESULT_DOGRU), row("FİZİK", 2, "B", "B", EQ_RESULT_DOGRU),
            row("FİZİK", 3, "C", None, EQ_RESULT_BOS)]
    for i in range(guards):
        rows.append(row("FİZİK", 4 + i, "D", None, EQ_RESULT_BOS, alt="D"))
    return rows


# 1) özet kesin çözüyor → geri yüklenir
rows = fizik_rows(2)
read = {"subjects": [{"name": "FİZİK", "questions": 5, "correct": 4, "wrong": 0, "blank": 1}]}
restored = reconcile_with_summary(read, rows)
checks = run_checks(read, rows)
check("1a 2 korumalı soru doğruya çevrildi", len(restored) == 2
      and all(r["result"] == EQ_RESULT_DOGRU and r["student_answer"] == "D" for r in restored))
check("1b ders artık karneyle uyumlu", all(c["ok"] for c in checks), str(checks))
check("1c geri yüklenen satırda koruma izi kalmadı", all(r.get("_guard_alt") is None for r in rows))

# 2) belirsiz → dokunulmaz
rows = fizik_rows(2)
read = {"subjects": [{"name": "FİZİK", "questions": 5, "correct": 3, "wrong": 0, "blank": 2}]}
restored = reconcile_with_summary(read, rows)
check("2a özet 1 fark, korumalı 2 satır → hiçbiri çevrilmedi", restored == []
      and sum(1 for r in rows if r.get("_guard_alt")) == 2)
c = run_checks(read, rows)[0]
check("2b uyuşmazlık mesajı sade ve korumalı soruları gösteriyor",
      not c["ok"] and "karnedeki özetle uyuşmuyor" in c["label"]
      and "Karnenin özetinde 3 doğru · 0 yanlış · 2 boş yazıyor" in c["detail"]
      and "Bakılacak sorular: 3, 4, 5" in c["detail"], str(c))

# 3) yanlış okunmuş boş (Coğrafya vakası)
rows = [row("COĞRAFYA", 1, "A", "A", EQ_RESULT_DOGRU), row("COĞRAFYA", 2, "B", "c", EQ_RESULT_YANLIS),
        row("COĞRAFYA", 3, "C", "C", EQ_RESULT_DOGRU)]
read = {"subjects": [{"name": "COĞRAFYA", "questions": 3, "correct": 2, "wrong": 0, "blank": 1}]}
c = run_checks(read, rows)[0]
check("3a ders adı düzgün yazılır + ne olduğu söylenir",
      c["label"].startswith("Coğrafya:") and "boş olması gerekirken yanlış okundu" in c["detail"], str(c))
check("3b bakılacak soru = yanlış okunan satır", "Bakılacak sorular: 2 " in c["detail"], c["detail"])
check("3c satır şüpheli boyanmaz (alarm körlüğü)", not any(r["is_suspect"] for r in rows))

# 4) soru sayısı farkı
c = run_checks({"subjects": [{"name": "KİMYA", "questions": 7, "correct": 7}]},
               [row("KİMYA", i, "A", "A", EQ_RESULT_DOGRU) for i in range(1, 6)])[0]
check("4 soru sayısı mesajı", "Karnede bu derste 7 soru var, okunan 5 soru" in c["detail"], str(c))

print(f"\n{9 - len(FAILS)}/9 passed")
raise SystemExit(1 if FAILS else 0)
