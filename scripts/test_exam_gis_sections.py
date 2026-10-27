"""Gelişim İzleme / Aşama tür tespiti (2026-10-27) — saf fonksiyon testi, DB yok.

Koç + yayınevi takvimleri (Özdebir "9/10. SINIF GİS", "12. SINIF GİS-1-TYT",
Bilgi Sarmal "Maarif İlk Aşama"):
  9/10/11 GİS → o sınıfın gelişim izleme türü · 12/mezun GİS → GIS_12 (AYT evreni)
  GİS + TYT → TYT · "İlk/Birinci Aşama" → Maarif 1. Aşama · "İkinci Aşama" → 2. Aşama
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection  # noqa: E402
from app.services.curriculum_mapping import normalize  # noqa: E402
from app.services.exam_import_service import (  # noqa: E402
    EXAM_UNIVERSE_AYT, _gis_section_for, _maarif_section_for, universe_for_section,
)

ok = 0
bad: list[str] = []


def check(label, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {label}")
    else:
        bad.append(label)
        print(f"  [FAIL] {label} ({detail})")


def st(grade, graduate=False):
    return SimpleNamespace(grade_level=grade, is_graduate=graduate)


def gis(title, student, hint=None):
    return _gis_section_for(normalize(title), {"grade_hint": hint, "questions": []}, student)


check("1 başlıkta GİS yoksa karışmaz", gis("TYT Deneme 3", st(12)) is None)
check("2 9. sınıf GİS", gis("ÖZDEBİR 9. SINIF GİS-1", st(9)) == ExamSection.MAARIF_9)
check("3 10. sınıf gelişim izleme", gis("10. Sınıf Gelişim İzleme Sınavı", st(10)) == ExamSection.MAARIF_10)
check("4 11. sınıf GİS (öğrenci sınıfından)", gis("Gelişim İzleme Sınavı 2", st(11)) == ExamSection.MAARIF_11)
check("5 12. sınıf GİS → GIS_12", gis("ÖZDEBİR 12. SINIF GİS-2", st(12)) == ExamSection.GIS_12)
check("6 mezun GİS → GIS_12", gis("Gelişim İzleme 4", st(None, True)) == ExamSection.GIS_12)
check("7 12. sınıf GİS-TYT → TYT", gis("12. SINIF GİS-1-TYT", st(12)) == ExamSection.TYT)
check("8 GIS_12 AYT evreninde", universe_for_section(ExamSection.GIS_12) == EXAM_UNIVERSE_AYT)


def maarif(title, grade):
    return _maarif_section_for({"exam_title": title, "questions": []}, st(grade))


check("9 Maarif İlk Aşama → 1. Aşama", maarif("Bilgi Sarmal Maarif İlk Aşama TG-1", 11) == ExamSection.MAARIF_1)
check("10 Birinci Aşama → 1. Aşama", maarif("Birinci Aşama Deneme", 11) == ExamSection.MAARIF_1)
check("11 İkinci Aşama → 2. Aşama", maarif("İkinci Aşama Maarif TG-4", 11) == ExamSection.MAARIF_2)
check("12 eski 'Birinci Basamak' adı hâlâ tanınır", maarif("ÇAP Maarif Model Birinci Basamak", 11) == ExamSection.MAARIF_1)
check("13 etiketler", EXAM_SECTION_LABELS[ExamSection.MAARIF_1] == "Maarif 1. Aşama (TYT)"
      and EXAM_SECTION_LABELS[ExamSection.MAARIF_10] == "10. Sınıf Gelişim İzleme"
      and EXAM_SECTION_LABELS[ExamSection.GIS_12].startswith("12. Sınıf Gelişim İzleme"))

print(f"\n{ok} geçti, {len(bad)} kaldı")
raise SystemExit(1 if bad else 0)
