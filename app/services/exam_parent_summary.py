"""Deneme sonucu — veli e-postası için konuşma dilinde özet (2026-09-05).

Koç "Veliye duyur" düğmesine basınca üretilir. KURAL TABANLI ve KREDİSİZ:
her deneme için AI harcanmaz ve koçun paketi ne olursa olsun çalışır.

VELİ DİLİ İLKELERİ (weekly_parent_report ile aynı çizgi):
  · Suçlayıcı değil, somut. "Kötü" / "başarısız" gibi sözcük yok.
  · Sayı verilir ama yorum sade: "geçen denemeye göre 4,5 net artmış".
  · Tek bir odak önerisi — liste hâlinde eleştiri yok.
  · Koça özel notlar, soru-satırı detayları GİRMEZ (yalnız ders bazı + net).
  · Karşılaştırma AYNI SINAV TÜRÜ içinde yapılır (TYT 120 soru ile AYT 80
    soruyu kıyaslamak yanıltıcı olur — 2026-07-17'de yaşanan tuzak).
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from app.models import ExamResult

# Bir dersi "öne çıkan" saymak için en az bu kadar soru olmalı — 2 soruluk
# bir dersten "en güçlü dersi" çıkarmak yanıltıcı olur.
MIN_QUESTIONS_FOR_HIGHLIGHT = 5


def _subjects(exam: ExamResult) -> list[dict]:
    if not exam.subject_nets:
        return []
    try:
        rows = json.loads(exam.subject_nets) or []
    except (ValueError, TypeError):
        return []
    out = []
    for r in rows:
        try:
            c = int(r.get("correct", 0))
            w = int(r.get("wrong", 0))
            b = int(r.get("blank", 0))
            out.append({
                "name": str(r.get("name", "")).strip() or "—",
                "correct": c, "wrong": w, "blank": b,
                "net": float(r.get("net", 0.0)),
                "questions": c + w + b,
                # Müfredata bağlanmamış satır (ham belge başlığı) — veliye
                # "ders" diye sunulmaz, yalnız tabloda görünür.
                "unmatched": bool(r.get("unmatched", False)),
            })
        except (TypeError, ValueError):
            continue
    return out


def _previous_same_section(db: Session, exam: ExamResult) -> ExamResult | None:
    """Aynı sınav TÜRÜNDEKİ bir önceki deneme (kıyas ancak böyle anlamlı)."""
    return (
        db.query(ExamResult)
        .filter(
            ExamResult.student_id == exam.student_id,
            ExamResult.section == exam.section,
            ExamResult.id != exam.id,
            ExamResult.exam_date <= exam.exam_date,
        )
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .first()
    )


def _fmt(n: float) -> str:
    """Türkçe ondalık: 102.75 → '102,75'."""
    return f"{n:.2f}".replace(".", ",")


def _wilson_lower(correct: int, total: int, z: float = 1.96) -> float:
    """Doğruluk için Wilson %95 alt sınırı — az soruyla gelen yüksek oranı
    cezalandırır (5/5 = 0.57 iken 36/40 = 0.77). Veliye "en güçlü ders"
    söylerken tesadüfi bir %100'ü öne çıkarmamak için."""
    if total <= 0:
        return 0.0
    p = correct / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5)
    return max(0.0, (centre - margin) / denom)


def build_parent_exam_summary(db: Session, exam: ExamResult) -> dict:
    """Veli e-postasının içeriği: sayılar + konuşma dilinde cümleler."""
    subjects = _subjects(exam)
    total_q = exam.total_correct + exam.total_wrong + exam.total_blank

    prev = _previous_same_section(db, exam)
    delta: float | None = None
    if prev is not None and prev.net is not None and exam.net is not None:
        delta = round(float(exam.net) - float(prev.net), 2)

    # --- konuşma dilinde cümleler
    lines: list[str] = []
    name = (exam.student.full_name if exam.student else "Öğrencimiz").split(" ")[0]

    lines.append(
        f"{name}, {exam.title} denemesinde {total_q} sorunun "
        f"{exam.total_correct} tanesini doğru yanıtladı ve "
        f"{_fmt(float(exam.net or 0))} net çıkardı."
    )

    if delta is None:
        lines.append(
            "Bu, bu türdeki ilk denemesi. Bundan sonraki denemelerle "
            "karşılaştırarak gidişatı birlikte takip edeceğiz."
        )
    elif delta > 0.5:
        lines.append(
            f"Bir önceki denemesine göre {_fmt(delta)} net artış var — "
            "emeğinin karşılığını almaya başlamış."
        )
    elif delta < -0.5:
        lines.append(
            f"Bir önceki denemesine göre {_fmt(abs(delta))} net geride kaldı. "
            "Tek bir deneme tek başına gidişatı göstermez; hangi konularda "
            "zorlandığını birlikte inceliyoruz."
        )
    else:
        lines.append(
            "Bir önceki denemesine göre neti aşağı yukarı aynı — "
            "istikrarlı bir tablo."
        )

    # En güçlü ders + odaklanılacak ders (yeterli soru sayısı olanlardan)
    ranked = [
        s for s in subjects
        if not s["unmatched"] and s["questions"] >= MIN_QUESTIONS_FOR_HIGHLIGHT
    ]
    best = worst = None
    if ranked:
        # HAM ORAN YETMEZ: 5 soruda %100, 40 soruda %90'dan güçlü kanıt değil
        # (küçük örneklem tesadüfü). Wilson alt sınırı az soruyu cezalandırır:
        #   5/5  → 0.57   ·   36/40 → 0.77   ·   3/5 → 0.23
        # Böylece "en rahat olduğu bölüm" gerçekten istikrarlı olanı gösterir.
        def acc(s: dict) -> float:
            answered = s["correct"] + s["wrong"]
            if not answered:
                return 0.0
            return _wilson_lower(s["correct"], answered)

        ranked_sorted = sorted(ranked, key=acc)
        worst = ranked_sorted[0]
        best = ranked_sorted[-1]
        if best is worst or acc(best) - acc(worst) < 0.15:
            # Dersler birbirine yakınsa "en zayıf" demek haksızlık olur.
            worst = None

    if best is not None:
        lines.append(
            f"En rahat olduğu bölüm {best['name']} "
            f"({best['correct']} doğru / {best['questions']} soru)."
        )
    if worst is not None:
        lines.append(
            f"Önümüzdeki dönemde {worst['name']} bölümüne ağırlık vereceğiz; "
            "programına bu konudan çalışma ekleyeceğiz."
        )

    return {
        "student_name": exam.student.full_name if exam.student else "",
        "exam_title": exam.title,
        "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
        "section_label": _section_label(exam),
        "net": float(exam.net or 0),
        "net_text": _fmt(float(exam.net or 0)),
        "correct": exam.total_correct,
        "wrong": exam.total_wrong,
        "blank": exam.total_blank,
        "total_questions": total_q,
        "delta": delta,
        "delta_text": (_fmt(abs(delta)) if delta is not None else None),
        "delta_direction": (
            None if delta is None else ("up" if delta > 0.5 else "down" if delta < -0.5 else "flat")
        ),
        "prev_title": prev.title if prev is not None else None,
        "prev_net_text": (
            _fmt(float(prev.net)) if prev is not None and prev.net is not None else None
        ),
        "prev_date": (
            prev.exam_date.isoformat() if prev is not None and prev.exam_date else None
        ),
        "subjects": subjects,
        "narrative": lines,
    }


def _section_label(exam: ExamResult) -> str:
    from app.models.curriculum import EXAM_SECTION_LABELS

    return EXAM_SECTION_LABELS.get(exam.section, "—")


def format_tr_date(iso: str | None) -> str:
    """'2026-09-02' → '02.09.2026' (şablonda okunur tarih)."""
    if not iso:
        return "—"
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return d.strftime("%d.%m.%Y")
