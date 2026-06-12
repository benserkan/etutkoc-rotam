"""Anket motoru — skorlama + sonuç inşası (Faz 1, 2026-06-11).

Tek merkez: tüm yüzeyler (koç sonuç ekranı, öğrenci sonuç görünümü, ileride
AI Kariyer Sentezi) skorları buradan okur.

Skorlama tipleri:
  - dimensions: likert5 maddeleri boyut bazında ortalanır → 0-100 normalize.
    reverse madde 6-değer; pct = (avg-1)/4*100.
  - wheel: her slider10 sorusu kendi dilimi → pct = (değer-1)/9*100.
  - qualitative: skor yok; açık uç cevaplar boyut (kadran) altında gruplanır.

Yorum bandı: pct >= 70 "high" · >= 40 "mid" · altı "low". Boyutun
`high_is_good=False` ise (örn. sınav kaygısı) frontend ton/etiketi ters çevirir.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.survey import (
    ASSIGNMENT_CANCELLED,
    ASSIGNMENT_COMPLETED,
    ASSIGNMENT_IN_PROGRESS,
    ASSIGNMENT_PENDING,
    QTYPE_CHOICE,
    QTYPE_LIKERT5,
    QTYPE_OPEN,
    QTYPE_SLIDER10,
    SCORING_QUALITATIVE,
    SCORING_WHEEL,
    SURVEY_DISCLAIMER_TR,
    SurveyAssignment,
    SurveyQuestion,
    SurveyTemplate,
)


def parse_dimensions(template: SurveyTemplate) -> list[dict]:
    try:
        dims = json.loads(template.dimensions_json or "[]")
        return dims if isinstance(dims, list) else []
    except Exception:
        return []


def parse_answers(assignment: SurveyAssignment) -> dict[str, Any]:
    try:
        data = json.loads(assignment.answers_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_options(question: SurveyQuestion) -> list[dict]:
    if not question.options_json:
        return []
    try:
        opts = json.loads(question.options_json)
        return opts if isinstance(opts, list) else []
    except Exception:
        return []


def _level_for(pct: float) -> str:
    if pct >= 70:
        return "high"
    if pct >= 40:
        return "mid"
    return "low"


_LEVEL_LABELS_TR = {"high": "Yüksek", "mid": "Orta", "low": "Düşük"}


def _coerce_numeric(value: Any, lo: int, hi: int) -> int | None:
    """Cevabı tam sayıya çevir + aralık doğrula; geçersizse None."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return None
    if v < lo or v > hi:
        return None
    return v


def validate_answers(
    questions: list[SurveyQuestion], answers: dict[str, Any]
) -> list[int]:
    """Tamamlama için eksik/geçersiz ZORUNLU soruların id listesi.

    Sayısal sorular (likert5/slider10/choice) zorunlu; open opsiyonel.
    """
    missing: list[int] = []
    for q in questions:
        raw = answers.get(str(q.id))
        if q.qtype == QTYPE_OPEN:
            continue
        if q.qtype == QTYPE_LIKERT5:
            if _coerce_numeric(raw, 1, 5) is None:
                missing.append(q.id)
        elif q.qtype == QTYPE_SLIDER10:
            if _coerce_numeric(raw, 1, 10) is None:
                missing.append(q.id)
        elif q.qtype == QTYPE_CHOICE:
            if raw is None or str(raw).strip() == "":
                missing.append(q.id)
    return missing


def compute_scores(
    template: SurveyTemplate,
    questions: list[SurveyQuestion],
    answers: dict[str, Any],
) -> dict:
    """Tamamlanan ankete skor sözlüğü üret (scores_json içeriği)."""
    dims = parse_dimensions(template)

    if template.scoring_type == SCORING_QUALITATIVE:
        blocks: dict[str, list[dict]] = {}
        for q in questions:
            key = q.dimension_key or "genel"
            raw = answers.get(str(q.id))
            text = str(raw).strip() if raw is not None else ""
            blocks.setdefault(key, []).append({"question": q.text, "answer": text})
        return {"type": SCORING_QUALITATIVE, "qualitative": blocks}

    # dimensions + wheel — sayısal toplama
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for q in questions:
        if not q.dimension_key:
            continue
        raw = answers.get(str(q.id))
        if q.qtype == QTYPE_LIKERT5:
            v = _coerce_numeric(raw, 1, 5)
            if v is None:
                continue
            if q.reverse:
                v = 6 - v
            pct = (v - 1) / 4 * 100
        elif q.qtype == QTYPE_SLIDER10:
            v = _coerce_numeric(raw, 1, 10)
            if v is None:
                continue
            pct = (v - 1) / 9 * 100
        else:
            continue
        sums[q.dimension_key] = sums.get(q.dimension_key, 0.0) + pct
        counts[q.dimension_key] = counts.get(q.dimension_key, 0) + 1

    dim_scores: list[dict] = []
    # Boyut sırası dimensions_json sırasını izler (rapor tutarlılığı)
    ordered_keys = [d["key"] for d in dims if d.get("key")] or list(sums.keys())
    for key in ordered_keys:
        n = counts.get(key, 0)
        if n == 0:
            continue
        pct = round(sums[key] / n, 1)
        dim_scores.append({
            "key": key,
            "score_pct": pct,
            "answered": n,
            "level": _level_for(pct),
        })

    # Açık uç cevapları rapora taşı (yaşam çarkı yansıtma soruları vb.)
    open_answers: list[dict] = []
    for q in questions:
        if q.qtype != QTYPE_OPEN:
            continue
        raw = answers.get(str(q.id))
        text = str(raw).strip() if raw is not None else ""
        if text:
            open_answers.append({"question": q.text, "answer": text})

    payload: dict = {"type": template.scoring_type, "dimensions": dim_scores}
    if open_answers:
        payload["open_answers"] = open_answers
    return payload


def build_result(
    template: SurveyTemplate, assignment: SurveyAssignment
) -> dict | None:
    """Tamamlanmış atamanın rapor payload'u (koç + öğrenci yüzeyleri ortak)."""
    if assignment.status != ASSIGNMENT_COMPLETED or not assignment.scores_json:
        return None
    try:
        scores = json.loads(assignment.scores_json)
    except Exception:
        return None

    dim_meta = {d.get("key"): d for d in parse_dimensions(template) if d.get("key")}

    dimensions: list[dict] = []
    for row in scores.get("dimensions", []) or []:
        meta = dim_meta.get(row.get("key"), {})
        level = row.get("level", "mid")
        high_is_good = bool(meta.get("high_is_good", True))
        dimensions.append({
            "key": row.get("key"),
            "label": meta.get("label", row.get("key")),
            "description": meta.get("description", ""),
            "score_pct": row.get("score_pct", 0),
            "level": level,
            "level_label": _LEVEL_LABELS_TR.get(level, level),
            "high_is_good": high_is_good,
            # Banda göre yorum metni — yüksekse high_text, düşükse low_text
            "comment": (
                meta.get("high_text", "") if level == "high"
                else meta.get("low_text", "") if level == "low"
                else ""
            ),
        })

    # En belirgin boyutlar (profil özeti) — skor sırasına göre ilk 3
    top = sorted(dimensions, key=lambda d: d["score_pct"], reverse=True)[:3]

    qualitative_blocks: list[dict] = []
    for key, rows in (scores.get("qualitative") or {}).items():
        meta = dim_meta.get(key, {})
        qualitative_blocks.append({
            "key": key,
            "label": meta.get("label", key),
            "description": meta.get("description", ""),
            "entries": rows,
        })
    # Kadran sırası dimensions_json sırasını izlesin
    order = {d: i for i, d in enumerate(dim_meta.keys())}
    qualitative_blocks.sort(key=lambda b: order.get(b["key"], 99))

    return {
        "scoring_type": scores.get("type", template.scoring_type),
        "dimensions": dimensions,
        "top_dimensions": [d["key"] for d in top],
        "qualitative": qualitative_blocks,
        "open_answers": scores.get("open_answers", []),
        "report_note": template.report_note or "",
        "source_attribution": template.source_attribution or "",
        "disclaimer": SURVEY_DISCLAIMER_TR,
    }


def save_answers(
    db: Session,
    assignment: SurveyAssignment,
    template: SurveyTemplate,
    questions: list[SurveyQuestion],
    answers: dict[str, Any],
    complete: bool,
) -> tuple[bool, list[int]]:
    """Cevapları kaydet; complete=True ise doğrula + skorla + tamamla.

    Dönüş: (completed_now, missing_question_ids). commit ÇAĞIRANA aittir.
    """
    existing = parse_answers(assignment)
    # Yalnız bu şablonun sorularına ait anahtarları kabul et
    valid_ids = {str(q.id) for q in questions}
    for k, v in (answers or {}).items():
        if k in valid_ids:
            existing[k] = v
    assignment.answers_json = json.dumps(existing, ensure_ascii=False)

    now = datetime.now(timezone.utc)
    if assignment.status == ASSIGNMENT_PENDING:
        assignment.status = ASSIGNMENT_IN_PROGRESS
        assignment.started_at = assignment.started_at or now

    if not complete:
        return False, []

    missing = validate_answers(questions, existing)
    if missing:
        return False, missing

    scores = compute_scores(template, questions, existing)
    assignment.scores_json = json.dumps(scores, ensure_ascii=False)
    assignment.status = ASSIGNMENT_COMPLETED
    assignment.completed_at = now
    return True, []


def has_open_assignment(
    db: Session, student_id: int, template_id: int
) -> bool:
    """Aynı şablon için bekleyen/devam eden atama var mı (mükerrer önleme)."""
    return (
        db.query(SurveyAssignment.id)
        .filter(
            SurveyAssignment.student_id == student_id,
            SurveyAssignment.template_id == template_id,
            SurveyAssignment.status.in_(
                [ASSIGNMENT_PENDING, ASSIGNMENT_IN_PROGRESS]
            ),
        )
        .first()
        is not None
    )
