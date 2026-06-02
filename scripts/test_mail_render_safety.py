# -*- coding: utf-8 -*-
"""Veli mail şablonları render güvenliği — YENİ + ESKİ payload'la patlamamalı.

Bug (2026-06-02): sessiz-saat ertelemeli yeni-program bildirimi, dün ESKİ
producer'la kuyruğa girip bugün YENİ şablonla render edilince patladı
(template_render_failed) — yeni şablon eski payload'da olmayan alanları arıyordu.
Bu test o sınıfı kalıcı yakalar: şablonlar eksik-alanlı (eski) payload'da da
render edilmeli (graceful degrade), asla exception fırlatmamalı.

KURAL: veli mail şablonuna yeni alan eklenince bu test güncellenir; eski payload
hâlâ render olmalı.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.email_service import render_template_safe

PASS = FAIL = 0
def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  [PASS] {name}")
    else:
        FAIL += 1; print(f"  [FAIL] {name}")

# YENİ payload — tam alanlı gün (Faz B sonrası yapı)
new_day = {
    "day_iso": "2026-06-02", "day_name": "Sal", "day_label": "02 Haz", "has_tasks": True,
    "subject_groups": [{"subject": "Mat", "rows": [{"book": "SB", "section": "B1", "planned": 5, "completed": 3}],
                        "total_planned": 5, "total_completed": 3}],
    "denemeler": [{"title": "Deneme X", "planned": 1, "completed": 1, "is_tam": False, "is_done": True}],
    "activities": [{"title": "Video", "type": "video"}],
    "gorev_total": 3, "gorev_done": 2, "test_planned": 5, "test_completed": 3,
    "deneme_count": 1, "etkinlik_count": 1, "total_planned": 5, "total_completed": 3,
}
# ESKİ payload — Faz B ÖNCESİ yapı: 'items' anahtarı, görev/test/deneme alanları YOK
old_day = {
    "day_iso": "2026-06-01", "day_name": "Pzt", "day_label": "01 Haz", "has_tasks": True,
    "subject_groups": [{"subject": "Mat", "items": [{"book": "SB", "section": "B1", "planned": 5, "completed": 3}],
                        "total_planned": 5, "total_completed": 3}],
    "activities": [],
    "total_planned": 5, "total_completed": 3,
    # gorev_total / test_planned / deneme_count / denemeler / etkinlik_count YOK (eski)
}

base = {"student_id": 1, "student_name": "Test", "week_start": "2026-06-01",
        "week_end": "2026-06-07", "total_tasks": 3, "unsubscribe_token": "T",
        "recent_exams": [], "latest_exam": None}

for label, day in [("YENİ(tam alan)", new_day), ("ESKİ(eksik alan)", old_day)]:
    for tname in ("parent_new_program", "parent_weekly_report"):
        p = dict(base, daily_breakdown=[day])
        if tname == "parent_weekly_report":
            # weekly_report top-level alanları: YENİ'de dolu, ESKİ'de None/eksik
            if label.startswith("YENİ"):
                p.update({"completed": 0, "planned": 0, "rate_pct": 0,
                          "gorev_total": 3, "gorev_done": 2, "gorev_rate": 67,
                          "test_planned": 5, "test_completed": 3, "deneme_count": 1, "etkinlik_count": 1})
            else:
                # eski weekly payload: yalnız completed/planned/rate_pct vardı
                p.update({"completed": 5, "planned": 8, "rate_pct": 62})
        res = render_template_safe(tname, p)
        check(f"{label} · {tname} render edilir (exception YOK)", res is not None and len(res[1]) > 100)

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
