"""Analitik sekmesi — KAYNAK AYRIMLI çalışma özeti (2026-10-15).

Koç: "havuz sisteminde kaynaklı ve kaynaksız çalışmalar analize katılıyor mu?" Bu servis
son N günde çözülen testleri üç kaynağa böler ve ders bazında müfredat ilerlemesiyle birleştirir:

  · kitaplı   — kitap bölümüne bağlı test kalemi (soru bankası; deneme kitabı HARİÇ)
  · kaynaksız — kitapsız ama KONUYA bağlı kalem (havuz / müfredattan verilen görev)
  · seansta   — koçun havuz seansında işaretlediği test (görev günü yok, sonuç yok)

Deneme (branş/genel deneme kitabı + kitapsız tam deneme) bu hesaba girmez (DENEME≠TEST).
Görev günü `Task.date` (plan günü) — trend/tempo ile aynı pencere kuralı.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import PoolItem, Subject, Task, TaskBookItem, Topic, User
from app.services import gorev_stats


@dataclass
class SourceTotals:
    planned: int = 0
    completed: int = 0


@dataclass
class SubjectWork:
    subject_id: int
    name: str
    book_tests: int = 0
    sourceless_tests: int = 0
    session_tests: int = 0
    planned: int = 0
    correct: int = 0
    wrong: int = 0
    blank: int = 0
    tests_with_result: int = 0
    # müfredat (odak sınıf — curriculum_progress ile aynı)
    coverage_pct: int | None = None
    started_topics: int = 0
    total_topics: int = 0
    next_topic: str | None = None
    last_topic: str | None = None

    @property
    def total(self) -> int:
        return self.book_tests + self.sourceless_tests + self.session_tests

    @property
    def accuracy_pct(self) -> int | None:
        a = self.correct + self.wrong
        return round(100 * self.correct / a) if a else None


@dataclass
class DowRow:
    weekday: int
    avg_completed: float
    hit_pct: int | None      # programlı günlerde çözülen / planlanan
    programmed_days: int


@dataclass
class StudyMix:
    window_days: int
    book: SourceTotals
    sourceless: SourceTotals
    session_tests: int
    correct: int
    wrong: int
    blank: int
    tests_with_result: int
    subjects: list[SubjectWork] = field(default_factory=list)
    dow: list[DowRow] = field(default_factory=list)

    @property
    def total_tests(self) -> int:
        return self.book.completed + self.sourceless.completed + self.session_tests

    @property
    def result_coverage_pct(self) -> int | None:
        enterable = self.book.completed + self.sourceless.completed
        return round(100 * self.tests_with_result / enterable) if enterable else None

    @property
    def accuracy_pct(self) -> int | None:
        a = self.correct + self.wrong
        return round(100 * self.correct / a) if a else None


def _as_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return (v.astimezone(timezone.utc) + timedelta(hours=3)).date()
    return v


def compute_study_mix(db: Session, student: User, *, today: date | None = None, days: int = 30) -> StudyMix:
    today = today or date.today()
    start = today - timedelta(days=days - 1)
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.topic),
        )
        .filter(Task.student_id == student.id, Task.date >= start, Task.date <= today,
                Task.is_draft.is_(False))
        .all()
    )
    mix = StudyMix(window_days=days, book=SourceTotals(), sourceless=SourceTotals(), session_tests=0,
                   correct=0, wrong=0, blank=0, tests_with_result=0)
    subj: dict[int, SubjectWork] = {}
    names: dict[int, str] = {}

    def _sw(sid: int, name: str) -> SubjectWork:
        if sid not in subj:
            subj[sid] = SubjectWork(subject_id=sid, name=name)
        return subj[sid]

    for t in tasks:
        for it in t.book_items:
            if gorev_stats.item_is_book_test(it):
                kind = "book"
                sid = it.book.subject_id
                if sid not in names:
                    s = db.get(Subject, sid)
                    names[sid] = s.name if s else "—"
            elif (it.book_id is None and it.topic_id is not None and it.topic is not None
                  and gorev_stats.item_unit(it) == "test"):
                kind = "sourceless"
                sid = it.topic.subject_id
                if sid not in names:
                    s = db.get(Subject, sid)
                    names[sid] = s.name if s else "—"
            else:
                continue  # deneme / konusuz etiket kalemi
            tot = mix.book if kind == "book" else mix.sourceless
            done = int(it.completed_count or 0)
            tot.planned += int(it.planned_count or 0)
            tot.completed += done
            w = _sw(sid, names[sid])
            w.planned += int(it.planned_count or 0)
            if kind == "book":
                w.book_tests += done
            else:
                w.sourceless_tests += done
            has_res = it.correct_count is not None or it.wrong_count is not None or it.blank_count is not None
            if done > 0 and has_res:
                w.tests_with_result += done
                mix.tests_with_result += done
            for attr, src in (("correct", it.correct_count), ("wrong", it.wrong_count), ("blank", it.blank_count)):
                v = int(src or 0)
                setattr(w, attr, getattr(w, attr) + v)
                setattr(mix, attr, getattr(mix, attr) + v)

    # Havuz seans işaretleri (pencere = işaret günü)
    for pi in (db.query(PoolItem)
               .filter(PoolItem.student_id == student.id, PoolItem.removed_at.is_(None),
                       PoolItem.session_marked > 0, PoolItem.unit == "test").all()):
        d = _as_date(pi.session_marked_at)
        if d is None or d < start or d > today:
            continue
        if pi.book is not None and pi.book.type in gorev_stats.DENEME_BOOK_TYPES:
            continue
        topic = pi.topic if pi.topic_id else (pi.section.topic if pi.section is not None else None)
        s = topic.subject if topic is not None else pi.subject
        if s is None:
            continue
        n = int(pi.session_marked or 0)
        _sw(s.id, s.name).session_tests += n
        mix.session_tests += n

    # Müfredat ilerlemesi (odak sınıf) — ders kartına
    try:
        from app.services.curriculum_progress import compute_curriculum_progress

        cpr = compute_curriculum_progress(db, student, student.teacher_id)
        for s in cpr.subjects:
            if s.subject_id in subj or s.started_topics > 0:
                w = _sw(s.subject_id, s.name)
                w.coverage_pct = s.coverage_pct if s.total_topics else None
                w.started_topics = s.started_topics
                w.total_topics = s.total_topics
                w.next_topic = s.next_topic_name
                w.last_topic = s.last_topic_name
    except Exception:  # noqa: BLE001 — müfredat best-effort
        pass

    mix.subjects = sorted(subj.values(), key=lambda w: (-w.total, w.name.lower()))
    mix.dow = _dow(db, student, today)
    return mix


def _dow(db: Session, student: User, today: date, window: int = 56) -> list[DowRow]:
    """Haftanın günleri — TÜM test kalemleri (kitaplı + kaynaksız). Pencere öğrencinin ilk
    yayınlanmış görevinden başlar (yeni öğrencide boş haftalar ortalamayı sulandırmasın)."""
    from sqlalchemy import func

    from app.services.analytics import daily_completed_series, daily_planned_series

    first = (db.query(func.min(Task.date))
             .filter(Task.student_id == student.id, Task.is_draft.is_(False)).scalar())
    comp = daily_completed_series(db, student.id, today, window, tests_only=True)
    plan = daily_planned_series(db, student.id, today, window, tests_only=True)
    rows: list[DowRow] = []
    for wd in range(7):
        days = [d for d in comp if d.weekday() == wd and (first is None or d >= first) and d < today]
        if not days:
            rows.append(DowRow(wd, 0.0, None, 0))
            continue
        avg = sum(comp[d] for d in days) / len(days)
        prog = [d for d in days if plan.get(d, 0) > 0]
        p = sum(plan[d] for d in prog)
        c = sum(comp[d] for d in prog)
        rows.append(DowRow(wd, round(avg, 1), (min(100, round(100 * c / p)) if p else None), len(prog)))
    return rows
