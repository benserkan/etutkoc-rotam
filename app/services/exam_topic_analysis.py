"""Deneme konu analizi (Faz 2) — içe aktarılan denemelerden konu birikimi.

Girdi: öğrencinin soru-satırlı (PDF'ten aktarılmış) ExamResult kayıtları.
Çıktı (tek türe filtreli — türler karışmaz, net ölçekleri farklı):
  - konu × deneme ISI HARİTASI (hücre = o denemedeki doğruluk)
  - NET FIRSAT analizi: sıklık × hata → "bu konu kapanırsa deneme başına
    +X net" (yanlış→doğru dönüşümü ceza iadesi de kazandırır: 1 + 1/ceza)
  - UNUTULAN / GELİŞEN konular (ilk yarı ↔ son yarı doğruluk kıyası)

Salt-okuma; AI çağrısı YOK (deterministik agregasyon, kredi düşmez).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session, selectinload

from app.models import (
    EXAM_SECTION_LABELS,
    EQ_RESULT_BOS,
    EQ_RESULT_DOGRU,
    EQ_RESULT_YANLIS,
    ExamResult,
    ExamResultQuestion,
    ExamSection,
    Subject,
    Topic,
    User,
    section_penalty,
)

# analiz penceresi: son N deneme (tür bazında) — ısı haritası okunur kalsın
ANALYSIS_EXAM_LIMIT = 12
# fırsat listesi: gürültü filtresi (tek sorudan "fırsat" üretme)
_MIN_TOPIC_QUESTIONS = 2
# unutulan/gelişen eşiği: iki yarı arasındaki doğruluk farkı
_TREND_DELTA = 0.34
_TREND_MIN_SIDE = 2  # her yarıda en az bu kadar soru


def _acc(c: int, n: int) -> float:
    return round(c / n, 3) if n else 0.0


def build_exam_topic_analysis(
    db: Session, student: User, *, section: str | None = None,
) -> dict:
    """Konu bazlı deneme analizi — tek sınav türüne filtreli.

    section None → en çok soru-satırlı denemesi olan tür seçilir (varsayılan).
    Soru satırı olmayan (elle girilmiş) denemeler analize girmez.
    """
    exams_all = (
        db.query(ExamResult)
        .options(selectinload(ExamResult.questions))
        .filter(ExamResult.student_id == student.id)
        .order_by(ExamResult.exam_date.asc(), ExamResult.id.asc())
        .all()
    )
    exams_all = [e for e in exams_all if e.questions]

    # tür seçenekleri (soru-satırlı deneme sayısıyla)
    by_section: dict[ExamSection, int] = {}
    for e in exams_all:
        by_section[e.section] = by_section.get(e.section, 0) + 1
    section_options = [
        {"value": s.value, "label": EXAM_SECTION_LABELS[s], "count": n}
        for s, n in sorted(by_section.items(), key=lambda x: -x[1])
    ]

    sec: ExamSection | None = None
    if section:
        try:
            sec = ExamSection(section)
        except ValueError:
            sec = None
    if sec is None and section_options:
        sec = ExamSection(section_options[0]["value"])

    exams = [e for e in exams_all if sec is not None and e.section == sec]
    exams = exams[-ANALYSIS_EXAM_LIMIT:]

    empty = {
        "section": sec.value if sec else None,
        "section_label": EXAM_SECTION_LABELS[sec] if sec else None,
        "section_options": section_options,
        "exams": [], "topics": [], "opportunities": [],
        "forgotten": [], "improved": [],
        "unmatched_questions": 0, "analyzed_question_count": 0,
    }
    if not exams:
        return empty

    penalty = section_penalty(sec)

    # konu agregasyonu + deneme hücreleri
    topic_ids = {q.topic_id for e in exams for q in e.questions if q.topic_id}
    topics_db = (
        db.query(Topic).filter(Topic.id.in_(topic_ids)).all() if topic_ids else []
    )
    subj_names = {
        s.id: s.name
        for s in db.query(Subject).filter(
            Subject.id.in_({t.subject_id for t in topics_db})
        ).all()
    } if topics_db else {}
    topic_meta = {t.id: t for t in topics_db}

    agg: dict[int, dict] = {}
    unmatched = 0
    analyzed = 0
    for ei, e in enumerate(exams):
        for q in e.questions:
            analyzed += 1
            if q.topic_id is None or q.topic_id not in topic_meta:
                unmatched += 1
                continue
            a = agg.setdefault(q.topic_id, {
                "total": 0, "correct": 0, "wrong": 0, "blank": 0,
                "cells": {},  # exam_id → sayaçlar
                "halves": [[0, 0], [0, 0]],  # [ilk yarı, son yarı] → [doğru, toplam]
                "exam_idx": set(),
            })
            cell = a["cells"].setdefault(e.id, {"total": 0, "correct": 0,
                                                "wrong": 0, "blank": 0})
            a["total"] += 1
            cell["total"] += 1
            half = 0 if ei < len(exams) / 2 else 1
            a["halves"][half][1] += 1
            a["exam_idx"].add(ei)
            if q.result == EQ_RESULT_DOGRU:
                a["correct"] += 1
                cell["correct"] += 1
                a["halves"][half][0] += 1
            elif q.result == EQ_RESULT_YANLIS:
                a["wrong"] += 1
                cell["wrong"] += 1
            elif q.result == EQ_RESULT_BOS:
                a["blank"] += 1
                cell["blank"] += 1

    exams_out = [
        {"id": e.id, "title": e.title, "exam_date": e.exam_date.isoformat(),
         "net": e.net}
        for e in exams
    ]

    topics_out: list[dict] = []
    opportunities: list[dict] = []
    forgotten: list[dict] = []
    improved: list[dict] = []
    for tid, a in agg.items():
        tp = topic_meta[tid]
        base = {
            "topic_id": tid,
            "topic_name": tp.name,
            "subject_name": subj_names.get(tp.subject_id, "?"),
        }
        cells = [
            {"exam_id": eid, **c, "accuracy": _acc(c["correct"], c["total"])}
            for eid, c in a["cells"].items()
        ]
        topics_out.append({
            **base,
            "total": a["total"], "correct": a["correct"],
            "wrong": a["wrong"], "blank": a["blank"],
            "accuracy": _acc(a["correct"], a["total"]),
            "exams_seen": len(a["exam_idx"]),
            "cells": cells,
        })

        # NET FIRSAT: yanlış→doğru = +1 + ceza iadesi (1/penalty); boş→doğru = +1.
        # Deneme başına normalize edilir → "bu konu kapanırsa deneme başına +X net".
        if a["total"] >= _MIN_TOPIC_QUESTIONS and (a["wrong"] or a["blank"]):
            gain = (a["wrong"] * (1 + 1 / penalty) + a["blank"]) / len(exams)
            opportunities.append({
                **base,
                "total": a["total"], "wrong": a["wrong"], "blank": a["blank"],
                "accuracy": _acc(a["correct"], a["total"]),
                "net_gain_per_exam": round(gain, 2),
            })

        # UNUTULAN / GELİŞEN: iki yarı kıyası (her yarıda yeterli örnek şart)
        (c1, n1), (c2, n2) = a["halves"]
        if len(exams) >= 2 and n1 >= _TREND_MIN_SIDE and n2 >= _TREND_MIN_SIDE:
            a1, a2 = _acc(c1, n1), _acc(c2, n2)
            item = {**base, "first_accuracy": a1, "last_accuracy": a2}
            if a1 - a2 >= _TREND_DELTA and a1 >= 0.5:
                forgotten.append(item)
            elif a2 - a1 >= _TREND_DELTA and a2 >= 0.5:
                improved.append(item)

    topics_out.sort(key=lambda t: (-t["total"], t["subject_name"], t["topic_name"]))
    opportunities.sort(key=lambda o: -o["net_gain_per_exam"])
    forgotten.sort(key=lambda t: t["last_accuracy"] - t["first_accuracy"])
    improved.sort(key=lambda t: (t["first_accuracy"] - t["last_accuracy"]))

    return {
        "section": sec.value,
        "section_label": EXAM_SECTION_LABELS[sec],
        "section_options": section_options,
        "exams": exams_out,
        "topics": topics_out,
        "opportunities": opportunities[:10],
        "forgotten": forgotten,
        "improved": improved,
        "unmatched_questions": unmatched,
        "analyzed_question_count": analyzed,
    }


# ============================================================================
# Faz 3 — sinyal köprüleri (öneri motoru + KS4 içgörü)
# ============================================================================

EXAM_WEAK_WINDOW_DAYS = 90
EXAM_WEAK_FULL_MISSES = 4  # bu kadar yanlış = tam sinyal (1.0)


def exam_weak_topic_map(db: Session, student_id: int) -> dict[int, float]:
    """Deneme zayıflık haritası (Faz 3 → öneri motoru): topic_id → 0..1.

    Son 90 günün soru-satırlı denemelerinde YANLIŞ çözülen konular. Boş
    SAYILMAZ — cevaplanmayan oturum/bölüm zayıflık kanıtı değildir (Elif AYT
    vakasında 80 boş sözel satır tüm sözel konuları "zayıf" gösterirdi).
    2 yanlış = 0.5 · 4+ yanlış = 1.0; genel doğruluğu ≥ 0.6 olan konu sinyal
    üretmez (yanlışlar telafi edilmiş). Sözleşme `open_wrong_topic_map` ile
    aynı — suggestions zayıflık bileşeni olarak tüketir.
    """
    cutoff = date.today() - timedelta(days=EXAM_WEAK_WINDOW_DAYS)
    qrows = (
        db.query(ExamResultQuestion.topic_id, ExamResultQuestion.result)
        .join(ExamResult, ExamResult.id == ExamResultQuestion.exam_result_id)
        .filter(
            ExamResult.student_id == student_id,
            ExamResult.exam_date >= cutoff,
            ExamResultQuestion.topic_id.isnot(None),
        )
        .all()
    )
    agg: dict[int, dict[str, int]] = {}
    for tid, res in qrows:
        a = agg.setdefault(int(tid), {"w": 0, "c": 0, "n": 0})
        a["n"] += 1
        if res == EQ_RESULT_YANLIS:
            a["w"] += 1
        elif res == EQ_RESULT_DOGRU:
            a["c"] += 1
    out: dict[int, float] = {}
    for tid, a in agg.items():
        if a["w"] < 2:
            continue
        if a["n"] and a["c"] / a["n"] >= 0.6:
            continue
        out[tid] = min(1.0, a["w"] / EXAM_WEAK_FULL_MISSES)
    return out


def exam_insight_summary(db: Session, student: User) -> dict | None:
    """KS4 koçluk içgörüsü prompt girdisi — kompakt konu×deneme özeti.

    Varsayılan (en çok denemesi olan) tür üzerinden: en büyük 5 net fırsatı +
    unutulan konular. Deneme yoksa None (içgörü denemesiz de üretilir).
    """
    d = build_exam_topic_analysis(db, student)
    if not d["exams"]:
        return None
    return {
        "section_label": d["section_label"],
        "exams": len(d["exams"]),
        "opportunities": [
            {"subject": o["subject_name"], "topic": o["topic_name"],
             "gain": o["net_gain_per_exam"]}
            for o in d["opportunities"][:5]
        ],
        "forgotten": [
            {"subject": t["subject_name"], "topic": t["topic_name"]}
            for t in d["forgotten"][:5]
        ],
    }
