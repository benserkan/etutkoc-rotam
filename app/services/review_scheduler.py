"""Stage 12 — Review scheduler / persistence layer.

DB operasyonları:
- `seed_topics_for_student`: bir öğrencinin bir Subject altındaki tüm topic'lere
  yeni ReviewCard aç (zaten varsa atla).
- `get_due_cards`: vade gelmiş (due_at <= now) + NEW kartlar.
- `record_review`: rating → FSRS hesabı + ReviewCard güncelleme + ReviewLog ekle.
- `cards_by_state`: dashboard sayıları için.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models import (
    ReviewCard,
    ReviewLog,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.models.review import (
    STATE_LEARNING,
    STATE_MASTERED,
    STATE_NEW,
    STATE_RELEARNING,
    STATE_REVIEW,
)
from app.services.fsrs import (
    VALID_RATINGS,
    FsrsResult,
    FsrsState,
    compute_next,
    is_due,
)


# ============================================================================
# Konu kartı politikası (2026-11-01, saha: Neslihan Hoca / Beren 114 kart)
# ============================================================================
# Kart bir KONU; öğrenci "bu konuyu hatırlıyor muyum" diye kendini puanlar.
# FSRS çekirdeği soru ölçeğinde düşünür (ilk "İyi" → ~1 gün sonra). Konu
# ölçeğinde bu çok sık: "Hatırlamadım" diyen öğrencinin konuyu ÇALIŞMASI için
# zaman gerekir, ertesi gün sormak anlamsızdır. Alt sınırlar yalnız bu modülün
# (konu kartlarının) vadesine uygulanır; fsrs.py ve Yanlış Soru Arşivi değişmez.
TOPIC_AGAIN_DAYS = 7      # Hatırlamadım → bir hafta çalış, sonra tekrar sor
TOPIC_HARD_MIN_DAYS = 3   # Zor → en erken 3 gün sonra
TOPIC_GOOD_MIN_DAYS = 7   # İyi / Kolay → en erken 7 gün sonra

# Kalıcı (kuyruktan çıkış): üst üste en az bu kadar ARALIKLI başarılı tekrar
# (İyi/Kolay; aynı gün alıştırması sayılmaz) VE bir sonraki tekrar en az
# MASTERY_MIN_INTERVAL_DAYS gün sonraya düşüyorsa kart "Kalıcı" olur.
MASTERY_STREAK = 3
MASTERY_MIN_INTERVAL_DAYS = 30

# Günde en fazla bu kadar YENİ kart öğrencinin önüne gelir; gerisi sırayla
# sonraki günlere kalır (toplu eklemede 100+ kartın aynı gün düşmesini önler).
NEW_CARDS_PER_DAY = 10

# Öğrenci son puanını bu süre içinde geri alabilir.
UNDO_WINDOW_MINUTES = 10

# Türkiye saati (UTC+3, sabit) — "bugün" sınırı.
_TR_OFFSET = timedelta(hours=3)


def _tr_day_start_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = (now + _TR_OFFSET).replace(hour=0, minute=0, second=0, microsecond=0)
    return local - _TR_OFFSET


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def topic_min_days(rating: int) -> int:
    if rating == 1:
        return TOPIC_AGAIN_DAYS
    if rating == 2:
        return TOPIC_HARD_MIN_DAYS
    return TOPIC_GOOD_MIN_DAYS


def new_cards_introduced_today(db: Session, *, student_id: int, now: datetime) -> int:
    """Bugün (TR) ilk kez puanlanan (NEW durumundan çıkan) kart sayısı."""
    start = _tr_day_start_utc(now)
    return int(
        db.query(func.count(ReviewLog.id))
        .filter(
            ReviewLog.student_id == student_id,
            ReviewLog.state_before == STATE_NEW,
            ReviewLog.reviewed_at >= start,
        )
        .scalar()
        or 0
    )


def new_quota_left(db: Session, *, student_id: int, now: datetime) -> int:
    return max(0, NEW_CARDS_PER_DAY - new_cards_introduced_today(db, student_id=student_id, now=now))


# ============================================================================
# Seed / kart oluşturma
# ============================================================================


@dataclass
class SeedResult:
    added: int
    skipped_existing: int
    topic_ids: list[int]


def seed_topics_for_student(
    db: Session,
    *,
    student: User,
    topic_ids: Iterable[int],
    teacher: User,
) -> SeedResult:
    """Verilen topic_ids için öğrenciye yeni ReviewCard aç (idempotent).

    Cross-tenant koruması: teacher'ın bu öğrenciye sahip olduğunu çağıran kontrol etmeli;
    burada sadece topic erişim kontrolü yapılır (Topic.is_builtin veya Topic.teacher_id).
    """
    ids = [tid for tid in topic_ids if isinstance(tid, int) and tid > 0]
    if not ids:
        return SeedResult(added=0, skipped_existing=0, topic_ids=[])

    accessible = {
        t.id for t in db.query(Topic).filter(
            Topic.id.in_(ids),
            or_(Topic.is_builtin.is_(True), Topic.teacher_id == teacher.id),
        ).all()
    }
    if not accessible:
        return SeedResult(added=0, skipped_existing=0, topic_ids=[])

    existing = {
        tid for (tid,) in db.query(ReviewCard.topic_id).filter(
            ReviewCard.student_id == student.id,
            ReviewCard.topic_id.in_(accessible),
        ).all()
    }
    to_add = accessible - existing
    for tid in to_add:
        db.add(
            ReviewCard(
                student_id=student.id,
                topic_id=tid,
                stability=0.0,
                difficulty=5.0,
                state=STATE_NEW,
            )
        )
    db.flush()
    return SeedResult(
        added=len(to_add),
        skipped_existing=len(existing),
        topic_ids=list(to_add),
    )


def seed_subject_for_student(
    db: Session, *, student: User, subject: Subject, teacher: User
) -> SeedResult:
    """Subject'in tüm erişilebilir topic'lerini öğrenci için seed et."""
    topics = (
        db.query(Topic)
        .filter(
            Topic.subject_id == subject.id,
            or_(Topic.is_builtin.is_(True), Topic.teacher_id == teacher.id),
        )
        .all()
    )
    return seed_topics_for_student(
        db, student=student, topic_ids=[t.id for t in topics], teacher=teacher
    )


# ============================================================================
# Listeleme
# ============================================================================


def _review_due_filter(now: datetime):
    """NEW olmayan, vadesi gelmiş kart (Kalıcı kartın due_at'i NULL → dışarıda)."""
    return and_(
        ReviewCard.state != STATE_NEW,
        ReviewCard.state != STATE_MASTERED,
        ReviewCard.due_at.isnot(None),
        ReviewCard.due_at <= now,
    )


def get_due_cards(
    db: Session, *, student_id: int, now: datetime, limit: int = 50
) -> list[ReviewCard]:
    """Bugün çözülecek kartlar: vadesi gelen tekrarlar (en geciken önce) +
    günlük kotayla sınırlı YENİ kartlar (müfredat sırasıyla)."""
    due = (
        db.query(ReviewCard)
        .options(joinedload(ReviewCard.topic).joinedload(Topic.subject))
        .filter(ReviewCard.student_id == student_id, _review_due_filter(now))
        .order_by(ReviewCard.due_at.asc())
        .limit(limit)
        .all()
    )
    room = max(0, limit - len(due))
    quota = min(room, new_quota_left(db, student_id=student_id, now=now))
    new_cards: list[ReviewCard] = []
    if quota > 0:
        new_cards = (
            db.query(ReviewCard)
            .join(Topic, Topic.id == ReviewCard.topic_id)
            .options(joinedload(ReviewCard.topic).joinedload(Topic.subject))
            .filter(ReviewCard.student_id == student_id, ReviewCard.state == STATE_NEW)
            .order_by(Topic.subject_id, Topic.order, Topic.id)
            .limit(quota)
            .all()
        )
    return list(due) + list(new_cards)


def _counts_for_students(
    db: Session, student_ids: list[int], now: datetime
) -> dict[int, dict[str, int]]:
    """Öğrenci başına: vadesi gelen tekrar, yeni kart, bugün tanıtılan yeni."""
    out: dict[int, dict[str, int]] = {
        sid: {"review_due": 0, "new": 0, "introduced": 0} for sid in student_ids
    }
    if not student_ids:
        return out
    for sid, cnt in (
        db.query(ReviewCard.student_id, func.count(ReviewCard.id))
        .filter(ReviewCard.student_id.in_(student_ids), _review_due_filter(now))
        .group_by(ReviewCard.student_id)
        .all()
    ):
        out[sid]["review_due"] = cnt
    for sid, cnt in (
        db.query(ReviewCard.student_id, func.count(ReviewCard.id))
        .filter(ReviewCard.student_id.in_(student_ids), ReviewCard.state == STATE_NEW)
        .group_by(ReviewCard.student_id)
        .all()
    ):
        out[sid]["new"] = cnt
    start = _tr_day_start_utc(now)
    for sid, cnt in (
        db.query(ReviewLog.student_id, func.count(ReviewLog.id))
        .filter(
            ReviewLog.student_id.in_(student_ids),
            ReviewLog.state_before == STATE_NEW,
            ReviewLog.reviewed_at >= start,
        )
        .group_by(ReviewLog.student_id)
        .all()
    ):
        out[sid]["introduced"] = cnt
    return out


def _due_from_counts(c: dict[str, int]) -> int:
    quota = max(0, NEW_CARDS_PER_DAY - c["introduced"])
    return c["review_due"] + min(c["new"], quota)


def count_due_for_student(db: Session, *, student_id: int, now: datetime) -> int:
    """Bugün öğrencinin önüne gelecek kart sayısı (yeni kart kotası dahil)."""
    return _due_from_counts(_counts_for_students(db, [student_id], now)[student_id])


@dataclass
class CardStateBreakdown:
    new: int
    learning: int
    review: int
    relearning: int
    due_now: int
    total: int
    mastered: int = 0
    new_waiting: int = 0   # bugünkü kotanın dışında sırada bekleyen yeni kart


def cards_breakdown(
    db: Session, *, student_id: int, now: datetime
) -> CardStateBreakdown:
    rows = (
        db.query(ReviewCard.state, func.count(ReviewCard.id))
        .filter(ReviewCard.student_id == student_id)
        .group_by(ReviewCard.state)
        .all()
    )
    counts = {state: cnt for state, cnt in rows}
    c = _counts_for_students(db, [student_id], now)[student_id]
    quota = max(0, NEW_CARDS_PER_DAY - c["introduced"])
    return CardStateBreakdown(
        new=counts.get(STATE_NEW, 0),
        learning=counts.get(STATE_LEARNING, 0),
        review=counts.get(STATE_REVIEW, 0),
        relearning=counts.get(STATE_RELEARNING, 0),
        due_now=_due_from_counts(c),
        total=sum(counts.values()),
        mastered=counts.get(STATE_MASTERED, 0),
        new_waiting=max(0, c["new"] - quota),
    )


def teacher_review_load(
    db: Session, *, teacher_id: int, now: datetime
) -> list[dict]:
    """Öğretmenin tüm öğrencileri için: ad, due şu an, toplam kart.

    Dönen liste sıralı: due_now azalan, sonra full_name.
    """
    students = (
        db.query(User)
        .filter(User.teacher_id == teacher_id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    if not students:
        return []
    student_ids = [s.id for s in students]
    # Tek sorgu ile due ve toplam:
    totals_rows = (
        db.query(ReviewCard.student_id, func.count(ReviewCard.id))
        .filter(ReviewCard.student_id.in_(student_ids))
        .group_by(ReviewCard.student_id)
        .all()
    )
    totals = {sid: cnt for sid, cnt in totals_rows}
    counts = _counts_for_students(db, student_ids, now)
    dues = {sid: _due_from_counts(c) for sid, c in counts.items()}
    result = []
    for s in students:
        result.append({
            "student": s,
            "total": totals.get(s.id, 0),
            "due_now": dues.get(s.id, 0),
        })
    # Due_now azalan sırala
    result.sort(key=lambda r: (-r["due_now"], r["student"].full_name.lower()))
    return result


# ============================================================================
# Tekrar kaydet (rating)
# ============================================================================


@dataclass
class ReviewOutcome:
    card: ReviewCard
    log: ReviewLog
    result: FsrsResult


def _success_streak_before(db: Session, card: ReviewCard) -> int:
    """Bu tekrardan ÖNCEKİ ardışık aralıklı başarı sayısı (İyi/Kolay). Aynı gün
    alıştırması (20 saatten kısa ara) zinciri ne kırar ne uzatır."""
    logs = (
        db.query(ReviewLog)
        .filter(ReviewLog.card_id == card.id)
        .order_by(ReviewLog.reviewed_at.desc(), ReviewLog.id.desc())
        .limit(20)
        .all()
    )
    streak = 0
    for lg in logs:
        if lg.rating < 3:
            break
        spaced = lg.state_before == STATE_NEW or (lg.elapsed_days or 0) * 24.0 >= 20
        if spaced:
            streak += 1
    return streak


def record_review(
    db: Session, *, card: ReviewCard, rating: int, now: datetime
) -> ReviewOutcome:
    """Rating → FSRS → konu politikası → kartı güncelle + log. commit çağıranda."""
    if rating not in VALID_RATINGS:
        raise ValueError(f"rating geçersiz: {rating!r}")
    if card.state == STATE_MASTERED:
        raise ValueError("Kalıcı kart puanlanamaz; önce koç yeniden açmalı.")

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    prev = FsrsState(
        stability=card.stability,
        difficulty=card.difficulty,
        state=card.state,
        last_reviewed_at=card.last_reviewed_at,
        review_count=card.review_count,
        lapse_count=card.lapse_count,
        due_at=card.due_at,
    )
    result = compute_next(prev, rating, now)

    # Konu ölçeği: vadeye alt sınır. Aynı gün alıştırmasında (başarı) FSRS
    # vadeyi korur; orada sınır uygulanmaz ki vade ileri kaçmasın.
    due_at = _aware(result.due_at) or now
    if not result.same_day_practice:
        floor = now + timedelta(days=topic_min_days(rating))
        if rating == 1:
            due_at = floor           # Hatırlamadım: tam bir hafta sonra
        elif due_at < floor:
            due_at = floor
    new_state = result.state

    # Kalıcılık: üst üste aralıklı başarılar + uzun bir sonraki aralık
    if (
        rating >= 3
        and not result.same_day_practice
        and _success_streak_before(db, card) + 1 >= MASTERY_STREAK
        and (due_at - now).total_seconds() / 86400.0 >= MASTERY_MIN_INTERVAL_DAYS
    ):
        new_state = STATE_MASTERED

    applied_days = max(0.0, (due_at - now).total_seconds() / 86400.0)

    log = ReviewLog(
        card_id=card.id,
        student_id=card.student_id,
        topic_id=card.topic_id,
        rating=rating,
        elapsed_days=result.elapsed_days,
        # GERÇEKTE uygulanan aralık — geri alma önceki vadeyi bundan kurar.
        scheduled_days=applied_days,
        stability_before=card.stability,
        stability_after=result.stability,
        difficulty_before=card.difficulty,
        difficulty_after=result.difficulty,
        state_before=card.state,
        state_after=new_state,
        reviewed_at=now,
    )
    db.add(log)

    card.stability = result.stability
    card.difficulty = result.difficulty
    card.state = new_state
    card.last_reviewed_at = now
    card.last_rating = rating
    card.due_at = None if new_state == STATE_MASTERED else due_at
    card.review_count = card.review_count + 1
    if rating == 1:
        card.lapse_count = card.lapse_count + 1
    card.updated_at = now

    db.flush()
    return ReviewOutcome(card=card, log=log, result=result)


class UndoError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def undo_last_review(db: Session, *, card: ReviewCard, now: datetime) -> ReviewCard:
    """Kartın SON puanını geri al (UNDO_WINDOW_MINUTES içinde). Kart puandan
    önceki durumuna döner, log silinir. commit çağıranda."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    logs = (
        db.query(ReviewLog)
        .filter(ReviewLog.card_id == card.id)
        .order_by(ReviewLog.reviewed_at.desc(), ReviewLog.id.desc())
        .limit(2)
        .all()
    )
    if not logs:
        raise UndoError("nothing_to_undo", "Geri alınacak bir işaretleme yok.")
    last = logs[0]
    reviewed = _aware(last.reviewed_at)
    if reviewed is None or (now - reviewed) > timedelta(minutes=UNDO_WINDOW_MINUTES):
        raise UndoError(
            "undo_window_passed",
            f"İşaretlemeyi yalnız {UNDO_WINDOW_MINUTES} dakika içinde geri alabilirsin.",
        )
    prev_log = logs[1] if len(logs) > 1 else None

    card.stability = last.stability_before
    card.difficulty = last.difficulty_before
    card.state = last.state_before
    card.review_count = max(0, (card.review_count or 0) - 1)
    if last.rating == 1:
        card.lapse_count = max(0, (card.lapse_count or 0) - 1)
    if prev_log is None or last.state_before == STATE_NEW:
        card.last_reviewed_at = None
        card.last_rating = None
        card.due_at = None
    else:
        prev_at = _aware(prev_log.reviewed_at)
        card.last_reviewed_at = prev_at
        card.last_rating = prev_log.rating
        card.due_at = prev_at + timedelta(days=float(prev_log.scheduled_days or 0.0))
    card.updated_at = now
    db.delete(last)
    db.flush()
    return card


# ============================================================================
# Koç yönetimi — sil / yeniden aç
# ============================================================================


def delete_cards(db: Session, *, student_id: int, card_ids: Iterable[int]) -> int:
    ids = [i for i in card_ids if isinstance(i, int) and i > 0]
    if not ids:
        return 0
    owned = [
        cid for (cid,) in db.query(ReviewCard.id).filter(
            ReviewCard.student_id == student_id, ReviewCard.id.in_(ids)
        ).all()
    ]
    if not owned:
        return 0
    # SQLite'ta FK kademesi kapalı olabilir → loglar açıkça silinir.
    db.query(ReviewLog).filter(ReviewLog.card_id.in_(owned)).delete(synchronize_session=False)
    db.query(ReviewCard).filter(ReviewCard.id.in_(owned)).delete(synchronize_session=False)
    db.flush()
    return len(owned)


def reopen_cards(
    db: Session, *, student_id: int, card_ids: Iterable[int], now: datetime
) -> int:
    """Kalıcı kartları yeniden tekrar kuyruğuna al (bugün vadeli)."""
    ids = [i for i in card_ids if isinstance(i, int) and i > 0]
    if not ids:
        return 0
    cards = db.query(ReviewCard).filter(
        ReviewCard.student_id == student_id,
        ReviewCard.id.in_(ids),
        ReviewCard.state == STATE_MASTERED,
    ).all()
    for c in cards:
        c.state = STATE_REVIEW
        c.due_at = now
        c.updated_at = now
    db.flush()
    return len(cards)


# ============================================================================
# Konu adayları — hangi konu kart olmalı?
# ============================================================================


@dataclass
class TopicCandidate:
    topic_id: int
    name: str
    grade_level: int | None
    unit_name: str | None
    order: int
    tests_done: int = 0
    exam_wrong: int = 0
    open_wrong: int = 0
    closed: bool = False
    card_id: int | None = None
    card_state: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def recommended(self) -> bool:
        return bool(self.tests_done or self.exam_wrong or self.open_wrong or self.closed)


EXAM_SIGNAL_DAYS = 180


def topic_candidates(
    db: Session, *, student: User, coach_id: int, subject_id: int, now: datetime,
) -> list[TopicCandidate]:
    """Bir derste öğrencinin görebileceği konular (yalnız alt konu; tema
    başlığı yok; sınıf kümülatif) + kart önerisi sinyalleri.

    Tekrar kartının amacı ÖĞRENİLMİŞ konuyu unutmamak → öneri yalnız
    öğrencinin çalıştığı (kitapta / kaynaksız görevde test çözdü), denemede
    yanlış yaptığı, Yanlış Soru Arşivi'nde açık yanlışı olan ya da koçun
    kapattığı konulara. Hiç görülmemiş konu önerilmez (koç yine seçebilir).
    """
    from app.models import (
        BookSection, ExamResult, ExamResultQuestion, SectionProgress,
        StudentBook, Task, TaskBookItem, TopicClosure, WrongQuestion,
    )
    from app.models.exam_result import EQ_RESULT_YANLIS
    from app.models.wrong_question import WQ_STATUS_ACIK
    from app.services.curriculum_progress import leaf_topics_for_student

    leaf = leaf_topics_for_student(db, student, coach_id, [subject_id])
    topics = leaf.by_subject.get(subject_id, [])
    if not topics:
        return []
    tids = [t.id for t in topics]
    cands = {
        t.id: TopicCandidate(
            topic_id=t.id,
            name=t.name,
            grade_level=t.grade_level,
            unit_name=leaf.parent_names.get(t.parent_id) if t.parent_id else None,
            order=t.order or 0,
        )
        for t in topics
    }

    # 1) Kitapta çözülen test (aktif kitaplar)
    for tid, done in (
        db.query(BookSection.topic_id, func.coalesce(func.sum(SectionProgress.completed_count), 0))
        .select_from(StudentBook)
        .join(BookSection, BookSection.book_id == StudentBook.book_id)
        .join(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),
            BookSection.topic_id.in_(tids),
        )
        .group_by(BookSection.topic_id)
        .all()
    ):
        if tid in cands:
            cands[tid].tests_done += int(done or 0)
    # 2) Kaynaksız konulu görev kalemi
    for tid, done in (
        db.query(TaskBookItem.topic_id, func.coalesce(func.sum(TaskBookItem.completed_count), 0))
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(
            Task.student_id == student.id,
            TaskBookItem.book_id.is_(None),
            TaskBookItem.topic_id.in_(tids),
        )
        .group_by(TaskBookItem.topic_id)
        .all()
    ):
        if tid in cands:
            cands[tid].tests_done += int(done or 0)
    # 3) Denemede yanlış (son 180 gün)
    since = (now - timedelta(days=EXAM_SIGNAL_DAYS)).date()
    for tid, cnt in (
        db.query(ExamResultQuestion.topic_id, func.count(ExamResultQuestion.id))
        .join(ExamResult, ExamResult.id == ExamResultQuestion.exam_result_id)
        .filter(
            ExamResult.student_id == student.id,
            ExamResult.exam_date >= since,
            ExamResultQuestion.result == EQ_RESULT_YANLIS,
            ExamResultQuestion.topic_id.in_(tids),
        )
        .group_by(ExamResultQuestion.topic_id)
        .all()
    ):
        if tid in cands:
            cands[tid].exam_wrong = int(cnt)
    # 4) Yanlış Soru Arşivi'nde açık yanlış
    for tid, cnt in (
        db.query(WrongQuestion.topic_id, func.count(WrongQuestion.id))
        .filter(
            WrongQuestion.student_id == student.id,
            WrongQuestion.status == WQ_STATUS_ACIK,
            WrongQuestion.topic_id.in_(tids),
        )
        .group_by(WrongQuestion.topic_id)
        .all()
    ):
        if tid in cands:
            cands[tid].open_wrong = int(cnt)
    # 5) Koçun kapattığı konu
    for (tid,) in db.query(TopicClosure.topic_id).filter(
        TopicClosure.student_id == student.id, TopicClosure.topic_id.in_(tids)
    ).all():
        if tid in cands:
            cands[tid].closed = True
    # 6) Mevcut kart
    for cid, tid, st in db.query(ReviewCard.id, ReviewCard.topic_id, ReviewCard.state).filter(
        ReviewCard.student_id == student.id, ReviewCard.topic_id.in_(tids)
    ).all():
        if tid in cands:
            cands[tid].card_id = cid
            cands[tid].card_state = st

    for c in cands.values():
        if c.closed:
            c.reasons.append("Koç konuyu kapattı")
        if c.tests_done:
            c.reasons.append(f"{c.tests_done} test çözdü")
        if c.exam_wrong:
            c.reasons.append(f"Denemede {c.exam_wrong} yanlış")
        if c.open_wrong:
            c.reasons.append(f"Arşivde {c.open_wrong} açık yanlış")

    return sorted(cands.values(), key=lambda c: (c.grade_level or 0, c.order, c.topic_id))


# ============================================================================
# Yardımcılar
# ============================================================================


def get_card(
    db: Session, *, card_id: int, student_id: int | None = None
) -> ReviewCard | None:
    """Tek kartı yükle. student_id verilirse cross-student koruması."""
    q = db.query(ReviewCard).options(
        joinedload(ReviewCard.topic).joinedload(Topic.subject)
    ).filter(ReviewCard.id == card_id)
    if student_id is not None:
        q = q.filter(ReviewCard.student_id == student_id)
    return q.first()


# ============================================================================
# A + C entegrasyonu — Zorlanılan konuların öğretmen önerisine sinyal olması
# ============================================================================


@dataclass
class StrugglingTopic:
    """Öğrencinin tekrar kartlarında zorlandığı konu — öğretmen önerisi için sinyal.

    Skor 0..100 normalize edilir. Yüksek skor = öğretmenin müdahale etmesi
    gereken konu. Her sinyalin neye karşılık geldiği `reasons` listesinde.
    """
    topic_id: int
    topic_name: str
    subject_id: int
    subject_name: str
    card_id: int
    state: str
    difficulty: float
    stability: float
    lapse_count: int
    review_count: int
    last_rating: int | None
    score: float           # 0..100 normalized
    reasons: list[str]


def _struggle_score(card: ReviewCard) -> tuple[float, list[str]]:
    """Tek kart için zorlanma skoru. Sinyaller:
    - RELEARNING state → kritik (öğrenci bir zamanlar pekiştirmişti, unuttu)
    - lapse_count ≥ 2 → birden fazla unutma
    - difficulty > 5.5 → algoritma zor sınıflandırmış
    - stability < 5g → bellek zayıf
    - last_rating == AGAIN/HARD → son temas negatif
    """
    score = 0.0
    reasons: list[str] = []

    # 1) State sinyali — relearning kritik
    if card.state == STATE_RELEARNING:
        score += 25
        reasons.append("Pekiştirmedeyken unutulmuş (kritik)")
    elif card.state == STATE_LEARNING and (card.review_count or 0) >= 2:
        score += 10
        reasons.append("Hâlâ öğrenme aşamasında, kalıcılaşamadı")

    # 2) Lapse — birden fazla unutma
    lapses = card.lapse_count or 0
    if lapses >= 3:
        score += 25
        reasons.append(f"{lapses}× unutma yaşandı")
    elif lapses == 2:
        score += 15
        reasons.append("2× unutma yaşandı")
    elif lapses == 1:
        score += 7
        reasons.append("1× unutma yaşandı")

    # 3) Difficulty — algoritma değerlendirmesi (1-10)
    diff = card.difficulty or 5.0
    if diff >= 7.5:
        score += 20
        reasons.append(f"Algoritma zorluk: {diff:.1f}/10 (yüksek)")
    elif diff >= 6.0:
        score += 10
        reasons.append(f"Algoritma zorluk: {diff:.1f}/10")

    # 4) Stability — bellek tutma süresi (gün)
    if card.review_count and card.review_count > 0:
        stab = card.stability or 0.0
        if stab < 2.0:
            score += 15
            reasons.append(f"Bellek tutma süresi düşük ({stab:.1f}g)")
        elif stab < 5.0:
            score += 8
            reasons.append(f"Bellek tutma süresi zayıf ({stab:.1f}g)")

    # 5) Son rating
    if card.last_rating == 1:  # AGAIN
        score += 10
        reasons.append("Son cevap: Tekrar")
    elif card.last_rating == 2:  # HARD
        score += 5
        reasons.append("Son cevap: Zor")

    return min(100.0, score), reasons


def struggling_topics_for_student(
    db: Session, *, student_id: int, limit: int = 5, min_score: float = 10.0,
) -> list[StrugglingTopic]:
    """Öğrencinin en çok zorlandığı konuları skor sırasıyla döndür.

    `min_score` altındakiler filtrelenir — alarm vermeyen kartlarla
    öğretmeni yormamak için. Default 10 → en az 1 unutma veya yüksek
    zorluk olan kartlar.

    Sıralama: skor azalan, sonra son tekrar tarihinin yakınlığı (yakın olan
    önce — taze veri).
    """
    cards = (
        db.query(ReviewCard)
        .options(joinedload(ReviewCard.topic).joinedload(Topic.subject))
        .filter(
            ReviewCard.student_id == student_id,
            ReviewCard.review_count > 0,  # Hiç çalışılmamış kartlar dahil edilmez
        )
        .all()
    )

    scored: list[StrugglingTopic] = []
    for c in cards:
        score, reasons = _struggle_score(c)
        if score < min_score:
            continue
        if not c.topic or not c.topic.subject:
            continue
        scored.append(StrugglingTopic(
            topic_id=c.topic_id,
            topic_name=c.topic.name,
            subject_id=c.topic.subject.id,
            subject_name=c.topic.subject.name,
            card_id=c.id,
            state=c.state,
            difficulty=float(c.difficulty or 0.0),
            stability=float(c.stability or 0.0),
            lapse_count=c.lapse_count or 0,
            review_count=c.review_count or 0,
            last_rating=c.last_rating,
            score=score,
            reasons=reasons,
        ))

    scored.sort(
        key=lambda s: (
            -s.score,
            # Son tekrar yakın olan önce — taze veri
        )
    )
    return scored[:limit]


def struggling_topic_ids_map(
    db: Session, *, student_id: int, min_score: float = 10.0,
) -> dict[int, float]:
    """AI öneri motoruna besleme için: topic_id → normalize zorlanma skoru (0..1).

    Suggestions servisindeki weakness_scores formatına uygun. Topic.id ile
    BookSection.topic_id eşleşmesi suggestions tarafında yapılır.
    """
    items = struggling_topics_for_student(
        db, student_id=student_id, limit=50, min_score=min_score
    )
    return {it.topic_id: it.score / 100.0 for it in items}
