"""AI konu eşleme — Gemini anahtarı METİN döndürse de eşleşmeler kaybolmaz (2026-10-07).

Saha: LGS karnelerinde Gemini bazen {"key": "40", "topic_id": 13} döndürüyordu;
kod yalnız sayı kabul ettiği için 40 satırlık parti sessizce eşleşmesiz kalıyordu.
  PYTHONPATH=. python scripts/test_exam_ai_match_keys.py
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import exam_import_service as svc  # noqa: E402
from app.services import gemini  # noqa: E402

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    PASS, FAIL = (PASS + 1, FAIL) if cond else (PASS, FAIL + 1)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {'' if cond else extra}")


topics = [SimpleNamespace(id=10 + i, name=n, subject_id=1) for i, n in
          enumerate(["Paragrafta Anlam", "Fiilimsiler", "Metin Türleri"])]
labels = [{"key": i, "subject": "Türkçe", "label": l} for i, l in
          enumerate(["Metnin ana fikrini belirler.", "Fiilimsileri kavrar.", "Metin türlerini ayırt eder."])]


def run(payload):
    orig = gemini.generate
    gemini.generate = lambda *a, **k: json.dumps(payload)
    try:
        return svc._ai_match_labels(labels, topics, {1: "Türkçe"})
    finally:
        gemini.generate = orig


r = run({"mappings": [{"key": 0, "topic_id": 10}, {"key": 1, "topic_id": 11}, {"key": 2, "topic_id": 12}]})
check("sayı anahtar → 3 eşleşme", r == {0: 10, 1: 11, 2: 12}, r)
r = run({"mappings": [{"key": "0", "topic_id": "10"}, {"key": "1", "topic_id": 11}, {"key": "2", "topic_id": 12}]})
check("METİN anahtar → yine 3 eşleşme", r == {0: 10, 1: 11, 2: 12}, r)
r = run({"mappings": [{"key": "0", "topic_id": 999}, {"key": "x", "topic_id": 10}, {"key": 2, "topic_id": None}]})
check("liste dışı / bozuk / null → düşer", r == {}, r)
check("sayı işareti temizliği", svc._clean_kazanim_label("[1] A.[2] B.") == "A.; B.")

print(f"\n  Sonuç: {PASS} PASS / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
