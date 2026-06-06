"""Ders → Konu performans agregasyonu.

Öğrencinin çözdüğü testlerden (TaskBookItem) ders ve konu (BookSection.label)
bazında: çözülen test sayısı + doğru/yanlış soru sayısı + doğruluk yüzdesi.

Veri kaynağı MEVCUT: TaskBookItem.completed_count (çözülen test) +
correct_count/wrong_count (doğru/yanlış SORU sayısı, öğrenci girer). DENEME
kitapları HARİÇ (deneme ayrı yüzeyde — DENEME≠TEST standardı, bkz. gorev_stats).

Koç / öğrenci / veli yüzeyleri AYNI servisi kullanır (tek kaynak).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Book, BookSection, Subject, Task, TaskBookItem
from app.services import gorev_stats


@dataclass
class TopicPerf:
    topic_id: int | None
    topic_name: str
    tests_solved: int          # Σ completed_count (test sayısı)
    correct: int               # Σ correct_count (soru)
    wrong: int                 # Σ wrong_count (soru)
    answered: int              # correct + wrong (D/Y girilmiş soru)
    accuracy_pct: int | None   # correct / answered * 100 (girilmişse)
    last_solved_at: datetime | None = None


@dataclass
class SubjectPerf:
    subject_id: int
    subject_name: str
    order: int
    tests_solved: int
    correct: int
    wrong: int
    answered: int
    accuracy_pct: int | None
    topics: list[TopicPerf] = field(default_factory=list)


def _acc(correct: int, wrong: int) -> int | None:
    ans = correct + wrong
    return int(round(100 * correct / ans)) if ans > 0 else None


def compute_topic_performance(db: Session, student_id: int) -> list[SubjectPerf]:
    """Öğrencinin ders → konu test performansı (çözülen test + D/Y + doğruluk).

    Yalnız çözülmüş (completed_count > 0) test-kitabı kalemleri. Aynı isimli konular
    (farklı kitaplarda) ders içinde BİRLEŞTİRİLİR (konu = ders içi etiket/topic_id).
    """
    rows = (
        db.query(
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Subject.order.label("subject_order"),
            BookSection.topic_id.label("topic_id"),
            BookSection.label.label("topic_label"),
            TaskBookItem.completed_count,
            TaskBookItem.correct_count,
            TaskBookItem.wrong_count,
            Task.completed_at,
        )
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Book, Book.id == TaskBookItem.book_id)
        .join(Subject, Subject.id == Book.subject_id)
        .join(BookSection, BookSection.id == TaskBookItem.book_section_id)
        .filter(Task.student_id == student_id)
        .filter(TaskBookItem.book_section_id.isnot(None))
        .filter(TaskBookItem.completed_count > 0)
        .filter(Book.type.notin_(gorev_stats.DENEME_BOOK_TYPES))
        .all()
    )

    # subject_id → {meta, order, topics: {topic_key → agg}}
    subjects: dict[int, dict] = {}
    for r in rows:
        subj = subjects.setdefault(
            r.subject_id,
            {"name": r.subject_name, "order": r.subject_order or 0, "topics": {}},
        )
        # Konu anahtarı: topic_id varsa onu, yoksa etiket adını kullan
        # (aynı isimli konular ders içinde birleşsin).
        key = ("t", r.topic_id) if r.topic_id else ("l", (r.topic_label or "—").strip().lower())
        topic = subj["topics"].setdefault(
            key,
            {"topic_id": r.topic_id, "name": (r.topic_label or "—").strip(),
             "tests": 0, "correct": 0, "wrong": 0, "last": None},
        )
        topic["tests"] += int(r.completed_count or 0)
        topic["correct"] += int(r.correct_count or 0)
        topic["wrong"] += int(r.wrong_count or 0)
        if r.completed_at is not None:
            if topic["last"] is None or r.completed_at > topic["last"]:
                topic["last"] = r.completed_at

    out: list[SubjectPerf] = []
    for sid, sd in subjects.items():
        topics: list[TopicPerf] = []
        s_tests = s_correct = s_wrong = 0
        for t in sd["topics"].values():
            s_tests += t["tests"]
            s_correct += t["correct"]
            s_wrong += t["wrong"]
            topics.append(
                TopicPerf(
                    topic_id=t["topic_id"],
                    topic_name=t["name"],
                    tests_solved=t["tests"],
                    correct=t["correct"],
                    wrong=t["wrong"],
                    answered=t["correct"] + t["wrong"],
                    accuracy_pct=_acc(t["correct"], t["wrong"]),
                    last_solved_at=t["last"],
                )
            )
        # Konuları: en çok çözülen üstte (test sayısı), sonra ada göre
        topics.sort(key=lambda x: (-x.tests_solved, x.topic_name.lower()))
        out.append(
            SubjectPerf(
                subject_id=sid,
                subject_name=sd["name"],
                order=sd["order"],
                tests_solved=s_tests,
                correct=s_correct,
                wrong=s_wrong,
                answered=s_correct + s_wrong,
                accuracy_pct=_acc(s_correct, s_wrong),
                topics=topics,
            )
        )
    out.sort(key=lambda x: (x.order, x.subject_name.lower()))
    return out
