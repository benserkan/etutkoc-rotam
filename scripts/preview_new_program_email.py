"""Yeni program mailini örnek verilerle üretip HTML dosyasına yazar.

Çıktı:
  - scripts/preview_new_program_with_exams.html  (3 deneme dolu)
  - scripts/preview_new_program_no_exams.html    (deneme yok — amber not)

Bu script DB'ye DOKUNMAZ — yalnız payload kurar + Jinja2 ile render eder.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


TR_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def render(payload: dict, out_path: Path) -> None:
    env = Environment(
        loader=FileSystemLoader("app/templates/emails"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("parent_new_program.html")
    payload.setdefault("app_base_url", "https://rotam.etutkoc.com")
    payload.setdefault("unsubscribe_token", "ornek-token-123abc")
    html = template.render(**payload)

    # İlk satırdaki "Subject: …" başlığını ayır — tarayıcıda görmesin diye HTML
    # olmayanı atla (mail client'larında Subject header'a giderdi).
    if html.startswith("Subject:"):
        idx = html.find("\n")
        if idx >= 0:
            html = html[idx + 1:].lstrip()

    out_path.write_text(html, encoding="utf-8")
    print(f"  → {out_path}")


def main() -> int:
    print("Yeni program mail önizlemeleri üretiliyor...\n")

    # Yeni format: gün × görev × kalem (ders · konu · planlanan soru)
    def _day(day_name, day_label, tasks):
        total = sum(
            sum(r["planned"] for r in t.get("rows", [])) + (t.get("total_planned", 0) if not t.get("rows") else 0)
            for t in tasks
        )
        return {
            "day_iso": "2026-05-30",
            "day_name": day_name,
            "day_label": day_label,
            "tasks": tasks,
            "total_planned": total,
            "total_completed": 0,
            "has_tasks": len(tasks) > 0,
        }

    # =========== Dolu durum ===========
    payload_full = {
        "student_id": 4,
        "student_name": "Berra Demirbaş",
        "week_start": "2026-05-30",
        "week_end": "2026-06-05",
        "total_tasks": 24,
        "daily_breakdown": [
            _day("Cmt", "30 May", [
                {"title": "Görev", "type": "test", "rows": [
                    {"book": "Karekök LGS Türkçe SB", "section": "Sözcükte Anlam", "planned": 15, "completed": 0},
                    {"book": "Karekök LGS Matematik", "section": "Üçgenler", "planned": 20, "completed": 0},
                ], "total_planned": 35, "total_completed": 0},
            ]),
            _day("Paz", "31 May", [
                {"title": "Görev", "type": "test", "rows": [
                    {"book": "Limit Yayınları Fen", "section": "Basit Makineler", "planned": 10, "completed": 0},
                    {"book": "Limit Yayınları Sosyal", "section": "Türk-İslam Devletleri", "planned": 12, "completed": 0},
                ], "total_planned": 22, "total_completed": 0},
                {"title": "Türev konu özeti çıkar", "type": "ozet", "rows": [], "total_planned": 0, "total_completed": 0},
            ]),
            _day("Pzt", "1 Haz", [
                {"title": "Görev", "type": "test", "rows": [
                    {"book": "Karekök LGS Matematik", "section": "Eşitsizlikler", "planned": 25, "completed": 0},
                ], "total_planned": 25, "total_completed": 0},
                {"title": "LGS Tam Deneme 8", "type": "other", "rows": [
                    {"book": "Deneme", "section": "", "planned": 90, "completed": 0},
                ], "total_planned": 90, "total_completed": 0},
            ]),
            _day("Sal", "2 Haz", [
                {"title": "Görev", "type": "test", "rows": [
                    {"book": "Karekök LGS Türkçe SB", "section": "Cümlenin Ögeleri", "planned": 15, "completed": 0},
                    {"book": "Karekök İngilizce", "section": "Friendship", "planned": 10, "completed": 0},
                ], "total_planned": 25, "total_completed": 0},
            ]),
            _day("Çar", "3 Haz", [
                {"title": "Görev", "type": "test", "rows": [
                    {"book": "Limit Yayınları Fen", "section": "DNA ve Genetik", "planned": 15, "completed": 0},
                    {"book": "Limit Yayınları Sosyal", "section": "Beylikten Devlete", "planned": 12, "completed": 0},
                    {"book": "Karekök LGS Matematik", "section": "Cebirsel İfadeler", "planned": 18, "completed": 0},
                ], "total_planned": 45, "total_completed": 0},
            ]),
            _day("Per", "4 Haz", []),
            _day("Cum", "5 Haz", []),
        ],
        "recent_exams": [
            {
                "title": "LGS Tam Deneme 7",
                "date_iso": "2026-05-28",
                "section": "lgs",
                "net": 78.33,
                "correct": 84,
                "wrong": 5,
                "blank": 1,
            },
            {
                "title": "LGS Sözel Bölüm",
                "date_iso": "2026-05-21",
                "section": "lgs",
                "net": 42.0,
                "correct": 45,
                "wrong": 3,
                "blank": 2,
            },
            {
                "title": "LGS Sayısal Bölüm",
                "date_iso": "2026-05-14",
                "section": "lgs",
                "net": 36.67,
                "correct": 38,
                "wrong": 4,
                "blank": 3,
            },
            {
                "title": "MEB Örnek Soru Denemesi",
                "date_iso": "2026-04-30",
                "section": "lgs",
                "net": 71.0,
                "correct": 76,
                "wrong": 5,
                "blank": 4,
            },
            {
                "title": "LGS Tam Deneme 6",
                "date_iso": "2026-04-15",
                "section": "lgs",
                "net": 74.67,
                "correct": 80,
                "wrong": 4,
                "blank": 1,
            },
            {
                "title": "Türkçe Bölüm Sınavı",
                "date_iso": "2026-03-25",
                "section": "lgs",
                "net": 18.0,
                "correct": 19,
                "wrong": 1,
                "blank": 0,
            },
        ],
    }
    render(payload_full, Path("scripts/preview_new_program_with_exams.html"))

    # =========== Boş durum (deneme yok) ===========
    payload_empty = dict(payload_full)
    payload_empty["student_name"] = "Ada Yılmaz"
    payload_empty["student_id"] = 99
    payload_empty["recent_exams"] = []
    render(payload_empty, Path("scripts/preview_new_program_no_exams.html"))

    print("\nTarayıcıda açmak için:")
    print("  start scripts\\preview_new_program_with_exams.html")
    print("  start scripts\\preview_new_program_no_exams.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
