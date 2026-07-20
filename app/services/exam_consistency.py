# -*- coding: utf-8 -*-
"""Deneme çapraz doğrulaması (self-study Faz 3).

"Çözüldü işaretli konu <-> denemede düşük doğruluk" tutarsızlığını bulur:
kitap ilerlemesinde önemli ölçüde işlenmiş görünen bir konuda, son denemelerin
soru-satırlı verisi (exam_result_questions) düşük doğruluk gösteriyorsa konu
işaretlenir. İki değeri var:

- PEDAGOJİK: "çözmüş ama öğrenememiş" — koç müfredat panelinde rozet
  (elle giriş olmasa da değerli sinyal).
- DENETİM: işlenmişliğin çoğu ELLE/bağımsız girişse (manual_count ağırlıklı)
  kurum raporunda "elle işlendi ama denemeler doğrulamıyor" satırı — Faz 2
  görünürlüğünün deneme-gerçekliğiyle çapraz kontrolü. Denemeler manipüle
  edilemeyen veri olduğundan her tür şişirmeyi (elle giriş VE görev
  işaretleme) yakalar.

Boş cevap SAYILMAZ (exam_weak_topic_map ilkesi — cevaplanmayan oturum
zayıflık/tutarsızlık kanıtı değildir; Elif AYT 80-boş-sözel vakası).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import (
    BookSection,
    ExamResult,
    ExamResultQuestion,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
)
from app.models.exam_result import EQ_RESULT_DOGRU, EQ_RESULT_YANLIS

# Pencere + eşikler
MISMATCH_WINDOW_DAYS = 90       # son N günün denemeleri
MISMATCH_MIN_ANSWERED = 3       # konuda en az N cevaplanmış soru (boş hariç)
MISMATCH_MAX_ACCURACY = 0.40    # bunun ALTI "denemeler doğrulamıyor"
MISMATCH_MIN_COMPLETED = 5      # konuda en az N test işlenmiş olmalı
MISMATCH_MIN_RATIO = 0.5        # işlenen / konunun toplam test kapasitesi
MANUAL_HEAVY_SHARE = 0.5        # işlenmişin >= %50'si elle → "elle ağırlıklı"


def topic_exam_stats(
    db: Session, student_id: int, *, days: int = MISMATCH_WINDOW_DAYS
) -> dict[int, dict]:
    """topic_id → {answered, correct, accuracy} (son N gün, boş HARİÇ)."""
    cutoff = date.today() - timedelta(days=days)
    rows = (
        db.query(ExamResultQuestion.topic_id, ExamResultQuestion.result)
        .join(ExamResult, ExamResult.id == ExamResultQuestion.exam_result_id)
        .filter(
            ExamResult.student_id == student_id,
            ExamResult.exam_date >= cutoff,
            ExamResultQuestion.topic_id.isnot(None),
        )
        .all()
    )
    agg: dict[int, dict] = {}
    for tid, res in rows:
        if res not in (EQ_RESULT_DOGRU, EQ_RESULT_YANLIS):
            continue  # boş sayılmaz
        a = agg.setdefault(int(tid), {"answered": 0, "correct": 0})
        a["answered"] += 1
        if res == EQ_RESULT_DOGRU:
            a["correct"] += 1
    for a in agg.values():
        a["accuracy"] = (a["correct"] / a["answered"]) if a["answered"] else 0.0
    return agg


def topic_progress_agg(db: Session, student_id: int) -> dict[int, dict]:
    """topic_id → {completed, manual, total} — öğrencinin kitaplarındaki
    konu-eşli bölümlerin agregasyonu (SectionProgress'siz bölümler total'e
    girer, completed=0)."""
    rows = (
        db.query(
            BookSection.topic_id,
            func.coalesce(func.sum(SectionProgress.completed_count), 0),
            func.coalesce(func.sum(SectionProgress.manual_count), 0),
            func.coalesce(func.sum(BookSection.test_count), 0),
        )
        .select_from(StudentBook)
        .join(BookSection, BookSection.book_id == StudentBook.book_id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(
            StudentBook.student_id == student_id,
            BookSection.topic_id.isnot(None),
        )
        .group_by(BookSection.topic_id)
        .all()
    )
    return {
        int(tid): {"completed": int(c or 0), "manual": int(m or 0), "total": int(t or 0)}
        for tid, c, m, t in rows
    }


def curriculum_exam_mismatches(
    db: Session, student_id: int, *, days: int = MISMATCH_WINDOW_DAYS
) -> list[dict]:
    """Tutarsız konular: işlenmiş görünüyor + denemede düşük doğruluk.

    Satır: {topic_id, topic_name, subject_name, completed, total, manual,
    manual_share_pct, manual_heavy, answered, correct, accuracy_pct}
    """
    progress = topic_progress_agg(db, student_id)
    if not progress:
        return []
    stats = topic_exam_stats(db, student_id, days=days)
    flagged: list[dict] = []
    for tid, p in progress.items():
        if p["completed"] < MISMATCH_MIN_COMPLETED:
            continue
        if p["total"] > 0 and (p["completed"] / p["total"]) < MISMATCH_MIN_RATIO:
            continue
        s = stats.get(tid)
        if not s or s["answered"] < MISMATCH_MIN_ANSWERED:
            continue
        if s["accuracy"] >= MISMATCH_MAX_ACCURACY:
            continue
        manual_share = (p["manual"] / p["completed"]) if p["completed"] else 0.0
        flagged.append({
            "topic_id": tid,
            "completed": p["completed"],
            "total": p["total"],
            "manual": p["manual"],
            "manual_share_pct": round(manual_share * 100),
            "manual_heavy": manual_share >= MANUAL_HEAVY_SHARE,
            "answered": s["answered"],
            "correct": s["correct"],
            "accuracy_pct": round(s["accuracy"] * 100),
        })
    if not flagged:
        return []
    # Konu + ders adları (tek sorgu)
    tids = [f["topic_id"] for f in flagged]
    names = {
        t.id: (t.name, subj_name)
        for t, subj_name in (
            db.query(Topic, Subject.name)
            .join(Subject, Subject.id == Topic.subject_id)
            .filter(Topic.id.in_(tids))
            .all()
        )
    }
    for f in flagged:
        nm = names.get(f["topic_id"])
        f["topic_name"] = nm[0] if nm else "—"
        f["subject_name"] = nm[1] if nm else "—"
    flagged.sort(key=lambda f: (f["accuracy_pct"], -f["completed"]))
    return flagged


def mismatch_map(
    db: Session, student_id: int, *, days: int = MISMATCH_WINDOW_DAYS
) -> dict[int, dict]:
    """Müfredat paneli işaretleme haritası: topic_id → mismatch satırı."""
    return {f["topic_id"]: f for f in curriculum_exam_mismatches(db, student_id, days=days)}
