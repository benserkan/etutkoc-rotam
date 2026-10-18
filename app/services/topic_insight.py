"""Hafta ızgarası konu özeti — görevin konusunda öğrenci nerede? (2026-10-18)

Koç ızgarada bir görevin üzerine gelince o görevin MÜFREDAT KONUSU için kısa özet:
  · konu ilerlemesi (Müfredat sekmesiyle aynı hesap: durum + %)
  · kaynak kaynak çözülen/toplam test + kaynaksız çözülen
  · doğru / yanlış / boş performansı + doğruluk + seviye (Konu Performansı ile aynı)
  · son 90 gün denemede bu konudaki doğruluk

Yeni hesap YOK: `curriculum_progress.compute_curriculum_progress` ve
`topic_performance.compute_topic_performance` aynen kullanılır → sayılar o iki
ekranla birebir. Müfredat görünümünde olmayan konu (ör. öğrencinin ders kümesi
dışında kalan) için kitap bölümlerinden yalın yedek hesap yapılır.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Book, BookSection, StudentBook, Topic, User
from app.models.book import BookType

STATUS_LABELS = {
    "tamamlandi": "Tamamlandı",
    "devam": "Devam ediyor",
    "planlandi": "Planlandı",
    "baslanmadi": "Başlanmadı",
    "kaynak_yok": "Kaynak yok",
}
LEVEL_LABELS = {"zayif": "Zayıf", "dikkat": "Dikkat", "iyi": "İyi", "veri_yok": None}


def build_topic_insights(db: Session, student: User, coach_id: int, topic_ids: list[int]) -> dict[int, dict]:
    from app.services.curriculum_progress import compute_curriculum_progress
    from app.services.topic_performance import compute_topic_performance

    want = set(topic_ids)
    out: dict[int, dict] = {}
    if not want:
        return out

    prog = compute_curriculum_progress(db, student, coach_id)
    for subj in prog.subjects:
        for t in subj.topics:
            if t.topic_id not in want:
                continue
            out[t.topic_id] = {
                "topic_id": t.topic_id, "name": t.name, "subject": subj.name,
                "status": t.status, "status_label": "Koç kapattı" if t.closed else STATUS_LABELS.get(t.status, t.status),
                "pct": t.pct, "closed": t.closed,
                "test_total": t.test_total, "completed": t.completed, "reserved": t.reserved,
                "sourceless_completed": t.sourceless_completed,
                "sources": [{"book": b, "solved": c, "total": tt} for (b, c, tt) in t.sources],
                "perf": None,
            }

    missing = want - out.keys()
    if missing:
        _fallback(db, student.id, missing, out)

    for subj in compute_topic_performance(db, student.id):
        for tp in subj.topics:
            if tp.topic_id in out:
                out[tp.topic_id]["perf"] = {
                    "tests_solved": tp.tests_solved, "correct": tp.correct, "wrong": tp.wrong,
                    "blank": tp.blank, "accuracy_pct": tp.accuracy_pct,
                    "tests_with_result": tp.tests_with_result,
                    "level": tp.level, "level_label": LEVEL_LABELS.get(tp.level),
                    "exam_answered": tp.exam_answered, "exam_accuracy_pct": tp.exam_accuracy_pct,
                    "last_solved_at": tp.last_solved_at,
                }
    return out


def _fallback(db: Session, student_id: int, topic_ids: set[int], out: dict[int, dict]) -> None:
    """Müfredat görünümünde olmayan konu: öğrencinin atanmış test kitaplarındaki bölümlerinden."""
    from app.models.progress import SectionProgress

    rows = (
        db.query(BookSection.topic_id, Book.name, func.sum(BookSection.test_count),
                 func.coalesce(func.sum(SectionProgress.completed_count), 0),
                 func.coalesce(func.sum(SectionProgress.reserved_count), 0))
        .join(Book, Book.id == BookSection.book_id)
        .join(StudentBook, (StudentBook.book_id == Book.id) & (StudentBook.student_id == student_id))
        .outerjoin(SectionProgress, (SectionProgress.book_section_id == BookSection.id)
                   & (SectionProgress.student_book_id == StudentBook.id))
        .filter(BookSection.topic_id.in_(topic_ids), Book.type == BookType.SORU_BANKASI,
                StudentBook.archived_at.is_(None))
        .group_by(BookSection.topic_id, Book.name)
        .all()
    )
    agg: dict[int, list] = {}
    for tid, book, total, comp, res in rows:
        agg.setdefault(tid, []).append((book, int(comp or 0), int(total or 0), int(res or 0)))
    for t in db.query(Topic).filter(Topic.id.in_(topic_ids)).all():
        srcs = agg.get(t.id, [])
        total = sum(x[2] for x in srcs)
        comp = sum(x[1] for x in srcs)
        status = "kaynak_yok" if total == 0 else ("tamamlandi" if comp >= total else ("devam" if comp else "baslanmadi"))
        out[t.id] = {
            "topic_id": t.id, "name": t.name, "subject": t.subject.name if t.subject else None,
            "status": status, "status_label": STATUS_LABELS[status],
            "pct": round(comp * 100 / total) if total else 0, "closed": False,
            "test_total": total, "completed": comp, "reserved": sum(x[3] for x in srcs),
            "sourceless_completed": 0,
            "sources": [{"book": b, "solved": c, "total": tt} for (b, c, tt, _r) in srcs if tt > 0],
            "perf": None,
        }
