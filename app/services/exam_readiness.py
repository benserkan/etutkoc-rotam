"""Sınava yetişme — ders bazlı, AKTİF kaynak modeli (2026-09-29, koç onaylı).

Eski hesap: tüm atanmış kitaplardaki tüm testler ÷ kalan gün. Zeynep'te hiç görev
verilmeyen 800 testlik "Fen Bilimleri" serisi ve iki kez atanmış kitaplar da "kalan
iş" sayılıyordu; tek bir genel "sınava yetişmeyecek" cümlesi çıkıyordu.

Yeni model — her ders ayrı:
  • AKTİF kaynak = son ACTIVE_BACK_DAYS günde ya da önümüzdeki ACTIVE_AHEAD_DAYS
    günde görev verilen test kitapları. Dinamik: öğrenci yeni bir kaynaktan görev
    almaya başlayınca kendiliğinden girer; ACTIVE_BACK_DAYS gündür görev verilmeyen
    kaynak "bırakıldı" sayılıp düşer; bitmiş kaynak kalan işe katkı vermez.
  • Kalan iş = aktif kaynaklardaki çözülmemiş testler (koçun kapattığı konular hariç).
  • Hız = o dersin son PACE_DAYS günde gerçekten çözülen test / gün (öğrencinin o
    dersteki geçmişi daha kısaysa kendi başlangıcından).
  • Hedef = sınavdan REVIEW_WEEKS hafta önce (son haftalar deneme + tekrar).
  • Bitiş = bugün + kalan ÷ hız. Hedeften sonraysa ders geride.
  • Geçmiş MIN_HISTORY_DAYS günden kısaysa "tahmin için erken" — uyarı üretilmez.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Book, BookSection, SectionProgress, StudentBook, Subject, Task, TaskBookItem, User
from app.models.topic_closure import TopicClosure
from app.services import gorev_stats

ACTIVE_BACK_DAYS = 21
ACTIVE_AHEAD_DAYS = 14
PACE_DAYS = 21
REVIEW_WEEKS = 6
MIN_HISTORY_DAYS = 14
# Hedefi "en az BİR kaynağı bitirmek" olan dersler (koç kararı 2026-09-29):
# kalan iş = bitmeye en yakın aktif kaynağın kalanı (diğer kaynaklar ek çalışma).
SINGLE_SOURCE_KEYWORDS = ("geometri",)


@dataclass
class SubjectReadiness:
    subject_id: int
    subject_name: str
    active_books: list[dict] = field(default_factory=list)    # {name, remaining}
    dropped_books: list[str] = field(default_factory=list)
    finished_books: list[str] = field(default_factory=list)
    remaining_tests: int = 0
    remaining_topics: int = 0
    solved_window: int = 0
    pace_days: int = 0
    pace: float = 0.0                    # test/gün
    finish_date: date | None = None
    target_date: date | None = None
    days_late: int | None = None         # >0 geride, <=0 yetişiyor
    status: str = "ok"                   # ok | late | stalled | early | done
    goal: str = "Tüm aktif kaynaklar"    # hedefin tanımı (ekranda yazılır)
    confidence: str = "ok"               # ok | early


@dataclass
class ReadinessReport:
    exam_date: date | None
    target_date: date | None
    subjects: list[SubjectReadiness] = field(default_factory=list)


def compute_readiness(db: Session, student: User, today: date) -> ReadinessReport:
    from app.services.analytics import get_exam_date

    exam = get_exam_date(db, student)
    rep = ReadinessReport(exam_date=exam, target_date=None)
    if exam is None or exam <= today:
        return rep
    target = exam - timedelta(weeks=REVIEW_WEEKS)
    if target <= today:
        target = exam - timedelta(days=5)
    rep.target_date = target

    rows = (
        db.query(Task.date, TaskBookItem.book_id, TaskBookItem.completed_count, Book.subject_id, Book.type)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Book, Book.id == TaskBookItem.book_id)
        .filter(Task.student_id == student.id, Task.is_draft.is_(False),
                Task.date >= today - timedelta(days=60),
                Task.date <= today + timedelta(days=ACTIVE_AHEAD_DAYS))
        .all()
    )
    rows = [r for r in rows if r.type not in gorev_stats.DENEME_BOOK_TYPES]
    active_from = today - timedelta(days=ACTIVE_BACK_DAYS)
    active: dict[int, set[int]] = {}
    seen: dict[int, set[int]] = {}
    solved: dict[int, int] = {}
    first_day: dict[int, date] = {}
    for r in rows:
        seen.setdefault(r.subject_id, set()).add(r.book_id)
        if r.date >= active_from:
            active.setdefault(r.subject_id, set()).add(r.book_id)
        if r.date < today:
            first_day[r.subject_id] = min(first_day.get(r.subject_id, r.date), r.date)
            if r.date >= today - timedelta(days=PACE_DAYS):
                solved[r.subject_id] = solved.get(r.subject_id, 0) + int(r.completed_count or 0)
    if not active:
        return rep

    book_ids = {b for bs in active.values() for b in bs} | {b for bs in seen.values() for b in bs}
    books = {b.id: b for b in db.query(Book).filter(Book.id.in_(book_ids)).all()}
    subjects = {s.id: s.name for s in db.query(Subject).filter(Subject.id.in_(active.keys())).all()}
    closed = {r[0] for r in db.query(TopicClosure.topic_id).filter(TopicClosure.student_id == student.id)}
    # Kitap başına kalan (aynı kitap iki kez atanmışsa TEK sayılır — max tamamlanan)
    prog = (
        db.query(BookSection.book_id, BookSection.id, BookSection.test_count, BookSection.topic_id)
        .filter(BookSection.book_id.in_(book_ids))
        .all()
    )
    # Yalnız bu öğrencinin ilerlemesi; aynı kitap iki kez atanmışsa bölüm başına EN
    # YÜKSEK tamamlanan alınır (kitap tek sayılır).
    mine: dict[int, int] = {}
    for sec_id, comp in (
        db.query(SectionProgress.book_section_id, SectionProgress.completed_count)
        .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
        .filter(StudentBook.student_id == student.id, StudentBook.book_id.in_(book_ids))
    ):
        mine[sec_id] = max(mine.get(sec_id, 0), int(comp or 0))
    remaining_by_book: dict[int, int] = {}
    topics_by_book: dict[int, set] = {}
    for book_id, sec_id, tc, topic_id in prog:
        if topic_id is not None and topic_id in closed:
            continue
        left = max(0, int(tc or 0) - mine.get(sec_id, 0))
        if left > 0:
            remaining_by_book[book_id] = remaining_by_book.get(book_id, 0) + left
            if topic_id is not None:
                topics_by_book.setdefault(book_id, set()).add(topic_id)

    for sid, bset in active.items():
        sr = SubjectReadiness(subject_id=sid, subject_name=subjects.get(sid, "?"), target_date=target)
        topics: set = set()
        # Aynı adla iki ayrı kitap kaydı (katalog + elle oluşturma) TEK kaynak
        # sayılır: kalan = aralarındaki en küçük kalan (en çok ilerlenmiş kopya).
        groups: dict[str, list[int]] = {}
        for b in bset:
            key = " ".join((books[b].name if b in books else f"#{b}").lower().split())
            groups.setdefault(key, []).append(b)
        for key in sorted(groups):
            members = groups[key]
            left = min(remaining_by_book.get(b, 0) for b in members)
            best = min(members, key=lambda b: remaining_by_book.get(b, 0))
            name = books[best].name if best in books else f"#{best}"
            if len(members) > 1:
                name += f" ({len(members)} kayıt tek sayıldı)"
            if left == 0:
                sr.finished_books.append(name)
                continue
            sr.active_books.append({"name": name, "remaining": left})
            sr.remaining_tests += left
            topics |= topics_by_book.get(best, set())
        sr.remaining_topics = len(topics)
        if any(k in sr.subject_name.lower() for k in SINGLE_SOURCE_KEYWORDS) and len(sr.active_books) > 1:
            closest = min(sr.active_books, key=lambda b: b["remaining"])
            sr.remaining_tests = closest["remaining"]
            sr.goal = f"En az bir kaynağı bitirmek — en yakın: {closest['name']}"
            sr.remaining_topics = 0
        elif any(k in sr.subject_name.lower() for k in SINGLE_SOURCE_KEYWORDS):
            sr.goal = "En az bir kaynağı bitirmek"
        sr.dropped_books = sorted(
            books[b].name for b in (seen.get(sid, set()) - bset) if b in books)
        start = max(first_day.get(sid, today), today - timedelta(days=PACE_DAYS))
        sr.pace_days = max(1, (today - start).days)
        sr.solved_window = solved.get(sid, 0)
        sr.pace = sr.solved_window / sr.pace_days
        history = (today - first_day[sid]).days if sid in first_day else 0
        if sr.remaining_tests == 0:
            sr.status = "done"
        elif history < MIN_HISTORY_DAYS:
            sr.status, sr.confidence = "early", "early"
        elif sr.pace <= 0:
            sr.status = "stalled"
        else:
            sr.finish_date = today + timedelta(days=math.ceil(sr.remaining_tests / sr.pace))
            sr.days_late = (sr.finish_date - target).days
            sr.status = "late" if sr.days_late > 0 else "ok"
        rep.subjects.append(sr)
    order = {"late": 0, "stalled": 1, "ok": 2, "early": 3, "done": 4}
    rep.subjects.sort(key=lambda s: (order.get(s.status, 9), -(s.days_late or 0), s.subject_name))
    return rep
