"""Ders → Konu performans agregasyonu.

Öğrencinin çözdüğü testlerden (TaskBookItem) ders ve konu (BookSection.label)
bazında: çözülen test sayısı + doğru/yanlış/boş soru sayısı + doğruluk yüzdesi.

Veri kaynağı MEVCUT: TaskBookItem.completed_count (çözülen test) +
correct_count/wrong_count/blank_count (SORU sayısı, öğrenci girer). DENEME
kitapları HARİÇ (deneme ayrı yüzeyde — DENEME≠TEST standardı, bkz. gorev_stats).

2026-10-14 genişlemesi (koç: "sayfa önemini yansıtmıyor"):
  · boş sayısı + SONUÇ GİRİLMİŞ test oranı (veri kalitesi — "17 testin 0'ına sonuç girilmiş")
  · HAVUZ: koçun seansta işaretlediği testler (sonuçsuz) konuya sayılır
  · son 90 gün deneme sonucu (aynı konuda denemede doğruluk) — görev ↔ deneme karşılaştırması
  · seviye (zayıf/dikkat/iyi/veri yok) + "nerede kaybediyor" kayıp puanı
    (yalnız denemede zayıf görünen, görevi olmayan konular da listeye girer)

Koç / öğrenci / veli yüzeyleri AYNI servisi kullanır (tek kaynak).
"""
from __future__ import annotations

from datetime import date  # noqa: F401  (tip ipucu)

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Book, BookSection, PoolItem, Subject, Task, TaskBookItem, Topic
from app.services import gorev_stats

# Seviye eşikleri — bir konuda yargı için en az bu kadar D/Y girilmiş SORU (görev) gerekir;
# denemede en az EXAM_MIN_ANSWERED cevaplanmış soru.
MIN_ANSWERED = 8
EXAM_MIN_ANSWERED = 3
WEAK_PCT = 50       # < → zayıf
WATCH_PCT = 70      # < → dikkat
EXAM_WEAK_PCT = 40  # denemede bunun altı (ve yeterli soru) → en az "dikkat"


@dataclass
class TopicPerf:
    topic_id: int | None
    topic_name: str
    tests_solved: int          # Σ completed_count (test sayısı) + seansta işaretlenen
    correct: int               # Σ correct_count (soru)
    wrong: int                 # Σ wrong_count (soru)
    answered: int              # correct + wrong (D/Y girilmiş soru)
    accuracy_pct: int | None   # correct / answered * 100 (girilmişse)
    last_solved_at: datetime | None = None
    blank: int = 0                     # Σ blank_count (soru)
    tests_with_result: int = 0         # sonucu (D/Y/B) girilmiş kalemlerin test sayısı
    session_tests: int = 0             # koçun seansta işaretlediği test (sonuçsuz)
    exam_answered: int = 0             # son 90g denemede bu konuda cevaplanan soru (boş hariç)
    exam_correct: int = 0
    exam_accuracy_pct: int | None = None
    level: str = "veri_yok"            # zayif | dikkat | iyi | veri_yok
    loss_score: int = 0                # kaybedilen soru: yanlış + boş + 2 × deneme yanlışı
    subject_id: int | None = None
    subject_name: str | None = None
    exam_only: bool = False            # görevi yok, yalnız denemede görünen konu


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
    blank: int = 0
    tests_with_result: int = 0
    session_tests: int = 0
    weak_topics: int = 0       # zayıf + dikkat


def _acc(correct: int, wrong: int) -> int | None:
    ans = correct + wrong
    return int(round(100 * correct / ans)) if ans > 0 else None


def topic_level(acc: int | None, answered: int, exam_acc: int | None, exam_answered: int) -> str:
    """Konu seviyesi — görev doğruluğu (yeterli veriyle) + deneme doğruluğu."""
    task_ok = acc is not None and answered >= MIN_ANSWERED
    exam_ok = exam_acc is not None and exam_answered >= EXAM_MIN_ANSWERED
    if not task_ok and not exam_ok:
        return "veri_yok"
    lvl = "iyi"
    if task_ok:
        if acc < WEAK_PCT:
            lvl = "zayif"
        elif acc < WATCH_PCT:
            lvl = "dikkat"
    if exam_ok and exam_acc < EXAM_WEAK_PCT:
        # görevde iyi ama denemede düşük → "dikkat"; görevde de düşükse zayıf kalır
        lvl = "zayif" if lvl == "zayif" or not task_ok else "dikkat"
    return lvl


def _task_rows(db: Session, student_id: int, start, end):
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
            TaskBookItem.blank_count,
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
    )
    # KAYNAKSIZ KONU kalemleri (2026-09-07): book_id NULL + topic_id dolu. Ders KONUDAN gelir.
    topic_rows = (
        db.query(
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Subject.order.label("subject_order"),
            Topic.id.label("topic_id"),
            Topic.name.label("topic_label"),
            TaskBookItem.completed_count,
            TaskBookItem.correct_count,
            TaskBookItem.wrong_count,
            TaskBookItem.blank_count,
            Task.completed_at,
            TaskBookItem.unit,
        )
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Topic, Topic.id == TaskBookItem.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .filter(Task.student_id == student_id)
        .filter(TaskBookItem.book_id.is_(None))
        .filter(TaskBookItem.completed_count > 0)
        # Sayfa birimli kalem soru sonucu taşımaz → konu performansına girmez (2026-10-22).
        .filter(or_(TaskBookItem.unit.is_(None), TaskBookItem.unit != "sayfa"))
    )
    if start is not None:
        rows = rows.filter(Task.date >= start)
        topic_rows = topic_rows.filter(Task.date >= start)
    if end is not None:
        rows = rows.filter(Task.date <= end)
        topic_rows = topic_rows.filter(Task.date <= end)
    return rows.all() + topic_rows.all()


def _session_rows(db: Session, student_id: int, start, end) -> list[dict]:
    """HAVUZ: koçun seansta işaretlediği TEST birimleri (sonuçsuz). Kitaplı kalemin işareti kitap
    sayacına da yazılır ama TaskBookItem'a girmez → burada bir kez sayılır (çift sayım yok)."""
    q = (
        db.query(PoolItem)
        .filter(
            PoolItem.student_id == student_id,
            PoolItem.removed_at.is_(None),
            PoolItem.session_marked > 0,
            PoolItem.unit == "test",
        )
    )
    out: list[dict] = []
    for it in q.all():
        at = it.session_marked_at
        if at is not None and start is not None and at.date() < start:
            continue
        if at is not None and end is not None and at.date() > end:
            continue
        topic = it.topic if it.topic_id else (it.section.topic if it.section is not None else None)
        if it.book is not None and it.book.type in gorev_stats.DENEME_BOOK_TYPES:
            continue
        subj = topic.subject if topic is not None else it.subject
        if subj is None:
            continue
        label = topic.name if topic is not None else (
            (it.section.label if it.section is not None else None) or it.label or "—")
        out.append({
            "subject_id": subj.id, "subject_name": subj.name, "subject_order": subj.order,
            "topic_id": topic.id if topic is not None else None, "topic_label": label,
            "tests": int(it.session_marked or 0), "at": at,
        })
    return out


def compute_topic_performance(
    db: Session,
    student_id: int,
    *,
    start: "date | None" = None,
    end: "date | None" = None,
    with_exams: bool = True,
) -> list[SubjectPerf]:
    """Öğrencinin ders → konu test performansı.

    Yalnız çözülmüş (completed_count > 0) test-kitabı ve kaynaksız konulu kalemler + havuz seans
    işaretleri. Aynı isimli konular (farklı kitaplarda) ders içinde BİRLEŞTİRİLİR.

    P3: `start`/`end` verilirse yalnız o SINIF DÖNEMİNİN görevleri sayılır.
    Deneme karşılaştırması daima son 90 gündür (`with_exams=False` kapatır).
    """
    subjects: dict[int, dict] = {}

    def _topic(sid, sname, sorder, tid, tlabel) -> dict:
        subj = subjects.setdefault(sid, {"name": sname, "order": sorder or 0, "topics": {}})
        key = ("t", tid) if tid else ("l", (tlabel or "—").strip().lower())
        return subj["topics"].setdefault(
            key,
            {"topic_id": tid, "name": (tlabel or "—").strip(), "tests": 0, "correct": 0,
             "wrong": 0, "blank": 0, "with_result": 0, "session": 0, "last": None},
        )

    for r in _task_rows(db, student_id, start, end):
        t = _topic(r.subject_id, r.subject_name, r.subject_order, r.topic_id, r.topic_label)
        # Soru birimli kaynaksız kalem: D/Y/B konu performansına girer ama TEST sayılmaz.
        n = 0 if getattr(r, "unit", None) == "soru" else int(r.completed_count or 0)
        t["tests"] += n
        t["correct"] += int(r.correct_count or 0)
        t["wrong"] += int(r.wrong_count or 0)
        t["blank"] += int(r.blank_count or 0)
        if r.correct_count is not None or r.wrong_count is not None or r.blank_count is not None:
            t["with_result"] += n
        if r.completed_at is not None and (t["last"] is None or r.completed_at > t["last"]):
            t["last"] = r.completed_at

    for r in _session_rows(db, student_id, start, end):
        t = _topic(r["subject_id"], r["subject_name"], r["subject_order"], r["topic_id"], r["topic_label"])
        t["tests"] += r["tests"]
        t["session"] += r["tests"]
        if r["at"] is not None and (t["last"] is None or r["at"] > t["last"]):
            t["last"] = r["at"]

    exam: dict[int, dict] = {}
    if with_exams:
        try:
            from app.services.exam_consistency import topic_exam_stats

            exam = topic_exam_stats(db, student_id)
        except Exception:  # noqa: BLE001 — deneme kıyası best-effort
            exam = {}

    seen_topic_ids: set[int] = set()
    out: list[SubjectPerf] = []
    for sid, sd in subjects.items():
        topics: list[TopicPerf] = []
        agg = {"tests": 0, "correct": 0, "wrong": 0, "blank": 0, "with": 0, "session": 0, "weak": 0}
        for t in sd["topics"].values():
            ex = exam.get(t["topic_id"]) if t["topic_id"] else None
            if t["topic_id"]:
                seen_topic_ids.add(t["topic_id"])
            tp = _make_topic(t, ex, sid, sd["name"])
            topics.append(tp)
            agg["tests"] += t["tests"]
            agg["correct"] += t["correct"]
            agg["wrong"] += t["wrong"]
            agg["blank"] += t["blank"]
            agg["with"] += t["with_result"]
            agg["session"] += t["session"]
            agg["weak"] += int(tp.level in ("zayif", "dikkat"))
        topics.sort(key=lambda x: (-x.tests_solved, x.topic_name.lower()))
        out.append(SubjectPerf(
            subject_id=sid, subject_name=sd["name"], order=sd["order"],
            tests_solved=agg["tests"], correct=agg["correct"], wrong=agg["wrong"],
            answered=agg["correct"] + agg["wrong"], accuracy_pct=_acc(agg["correct"], agg["wrong"]),
            topics=topics, blank=agg["blank"], tests_with_result=agg["with"],
            session_tests=agg["session"], weak_topics=agg["weak"],
        ))
    out.sort(key=lambda x: (x.order, x.subject_name.lower()))
    return out


def _make_topic(t: dict, ex: dict | None, sid: int, sname: str) -> TopicPerf:
    acc = _acc(t["correct"], t["wrong"])
    answered = t["correct"] + t["wrong"]
    ex_ans = int(ex["answered"]) if ex else 0
    ex_cor = int(ex["correct"]) if ex else 0
    ex_acc = int(round(100 * ex_cor / ex_ans)) if ex_ans else None
    return TopicPerf(
        topic_id=t["topic_id"], topic_name=t["name"], tests_solved=t["tests"],
        correct=t["correct"], wrong=t["wrong"], answered=answered, accuracy_pct=acc,
        last_solved_at=t["last"], blank=t["blank"], tests_with_result=t["with_result"],
        session_tests=t["session"], exam_answered=ex_ans, exam_correct=ex_cor,
        exam_accuracy_pct=ex_acc, level=topic_level(acc, answered, ex_acc, ex_ans),
        loss_score=t["wrong"] + t["blank"] + 2 * (ex_ans - ex_cor),
        subject_id=sid, subject_name=sname,
    )


def loss_focus(
    db: Session, student_id: int, subjects: list[SubjectPerf], *, limit: int = 8,
) -> list[TopicPerf]:
    """"Nerede kaybediyor" — zayıf/dikkat seviyesindeki konular kayıp puanına göre.

    Görevi olmayan ama son 90 gün denemede yeterli soruda düşük doğruluklu konular da girer
    (`exam_only`): görevde hiç çalışılmamış zayıf konu en önemli uyarıdır."""
    picked = [t for s in subjects for t in s.topics if t.level in ("zayif", "dikkat")]
    seen = {t.topic_id for s in subjects for t in s.topics if t.topic_id}
    try:
        from app.services.exam_consistency import topic_exam_stats

        exam = topic_exam_stats(db, student_id)
    except Exception:  # noqa: BLE001
        exam = {}
    missing = [tid for tid in exam if tid not in seen]
    if missing:
        topics = {t.id: t for t in db.query(Topic).filter(Topic.id.in_(missing)).all()}
        for tid in missing:
            tp = topics.get(tid)
            if tp is None:
                continue
            ex = exam[tid]
            ans, cor = int(ex["answered"]), int(ex["correct"])
            ex_acc = int(round(100 * cor / ans)) if ans else None
            lvl = topic_level(None, 0, ex_acc, ans)
            if lvl not in ("zayif", "dikkat"):
                continue
            picked.append(TopicPerf(
                topic_id=tid, topic_name=tp.name, tests_solved=0, correct=0, wrong=0, answered=0,
                accuracy_pct=None, exam_answered=ans, exam_correct=cor, exam_accuracy_pct=ex_acc,
                level=lvl, loss_score=2 * (ans - cor),
                subject_id=tp.subject_id, subject_name=(tp.subject.name if tp.subject else None),
                exam_only=True,
            ))
    picked.sort(key=lambda t: (0 if t.level == "zayif" else 1, -t.loss_score, t.topic_name.lower()))
    return picked[:limit]
