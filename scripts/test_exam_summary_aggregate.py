"""Karne özetinde toplu + alt ders satırı birlikte (ELİT KARMA TYT-1, Taha #84, 2026-10-18).

Özet: "TYT-MATEMATİK 40" + "MATEMATİK 31" + "GEOMETRİ 9"; satırlar Matematik 31 + Geometri 9.
Eskiden toplu satır alt Matematik ile aynı anahtara düşüp 31'le kıyaslanıyordu → yanlış
"Tyt-Matematik: soru sayısı tutmuyor (40 var 31 okundu)" uyarısı.

Çalıştır: PYTHONPATH=. python scripts/test_exam_summary_aggregate.py
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.services.exam_import_service import _summary_agreement, run_checks

ok = 0
bad: list[str] = []


def chk(label, cond, detail=""):
    global ok
    if cond:
        ok += 1; print(f"  [PASS] {label}")
    else:
        bad.append(label); print(f"  [FAIL] {label} ({detail})")


def rows(subj, n, res="dogru"):
    return [{"subject_raw": subj, "result": res, "exam_part": None} for _ in range(n)]


R = rows("Matematik", 31) + rows("Geometri", 9)
read = {"subjects": [{"name": "TYT-MATEMATİK", "questions": 40, "correct": 40},
                     {"name": "MATEMATİK", "questions": 31}, {"name": "GEOMETRİ", "questions": 9}],
        "questions": [{"subject": "Matematik"}] * 31 + [{"subject": "Geometri"}] * 9}
cs = run_checks(read, R)
chk("1 toplu + alt satırlar: üç kontrol de uyumlu", cs and all(c["ok"] for c in cs), [c["label"] for c in cs])
chk("2 okuma tutarlılık puanı 3/3", _summary_agreement(read) == 3, _summary_agreement(read))
read2 = {"subjects": [{"name": "Matematik", "questions": 40}, {"name": "Geometri", "questions": 9}]}
c2 = {c["label"].split(":")[0]: c["ok"] for c in run_checks(read2, R)}
chk("3 tek Matematik satırı + Geometri'nin kendi satırı → uyuşmazlık görünür (eski koruma)",
    c2.get("Matematik") is False and c2.get("Geometri") is True, c2)
read3 = {"subjects": [{"name": "TYT-MATEMATİK", "questions": 40}, {"name": "MATEMATİK", "questions": 31},
                      {"name": "GEOMETRİ", "questions": 9}]}
R3 = rows("Matematik", 31) + rows("Geometri", 7)
c3 = [c for c in run_checks(read3, R3) if not c["ok"]]
chk("4 gerçek eksik (Geometri 7/9) yine yakalanır", any("Geometri" in c["label"] for c in c3)
    and any("Tyt-Matematik" in c["label"] for c in c3), [c["label"] for c in c3])
print(f"\n{ok}/{ok + len(bad)} geçti")
sys.exit(1 if bad else 0)
