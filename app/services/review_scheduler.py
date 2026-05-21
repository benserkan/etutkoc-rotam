"""Stage 12 — Review scheduler / persistence layer.

DB operasyonları:
- `seed_topics_for_student`: bir öğrencinin bir Subject altındaki tüm topic'lere
  yeni ReviewCard aç (zaten varsa atla).
- `get_due_cards`: vade gelmiş (due_at <= now) + NEW kartlar.
- `record_review`: rating → FSRS hesabı + ReviewCard güncelleme + ReviewLog ekle.
- `cards_by_state`: dashboard sayıları için.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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


def get_due_cards(
    db: Session, *, student_id: int, now: datetime, limit: int = 50
) -> list[ReviewCard]:
    """Vadesi gelmiş kartlar: state=NEW veya due_at <= now."""
    q = (
        db.query(ReviewCard)
        .options(joinedload(ReviewCard.topic).joinedload(Topic.subject))
        .filter(ReviewCard.student_id == student_id)
        .filter(
            or_(
                ReviewCard.state == STATE_NEW,
                and_(
                    ReviewCard.due_at.isnot(None),
                    ReviewCard.due_at <= now,
                ),
            )
        )
        .order_by(
            # NEW kartlar önce, sonra en geciken (due_at küçük)
            (ReviewCard.state == STATE_NEW).desc(),
            ReviewCard.due_at.asc().nulls_first(),
        )
        .limit(limit)
    )
    return list(q.all())


def count_due_for_student(db: Session, *, student_id: int, now: datetime) -> int:
    return (
        db.query(func.count(ReviewCard.id))
        .filter(ReviewCard.student_id == student_id)
        .filter(
            or_(
                ReviewCard.state == STATE_NEW,
                and_(
                    ReviewCard.due_at.isnot(None),
                    ReviewCard.due_at <= now,
                ),
            )
        )
        .scalar()
        or 0
    )


@dataclass
class CardStateBreakdown:
    new: int
    learning: int
    review: int
    relearning: int
    due_now: int
    total: int


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
    return CardStateBreakdown(
        new=counts.get(STATE_NEW, 0),
        learning=counts.get(STATE_LEARNING, 0),
        review=counts.get(STATE_REVIEW, 0),
        relearning=counts.get(STATE_RELEARNING, 0),
        due_now=count_due_for_student(db, student_id=student_id, now=now),
        total=sum(counts.values()),
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
    due_rows = (
        db.query(ReviewCard.student_id, func.count(ReviewCard.id))
        .filter(ReviewCard.student_id.in_(student_ids))
        .filter(
            or_(
                ReviewCard.state == STATE_NEW,
                and_(
                    ReviewCard.due_at.isnot(None),
                    ReviewCard.due_at <= now,
                ),
            )
        )
        .group_by(ReviewCard.student_id)
        .all()
    )
    dues = {sid: cnt for sid, cnt in due_rows}
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


def record_review(
    db: Session, *, card: ReviewCard, rating: int, now: datetime
) -> ReviewOutcome:
    """Rating → FSRS → kartı güncelle + log oluştur. db.commit() çağıran sorumlu."""
    if rating not in VALID_RATINGS:
        raise ValueError(f"rating geçersiz: {rating!r}")

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Mevcut state'i FsrsState'e indir
    prev = FsrsState(
        stability=card.stability,
        difficulty=card.difficulty,
        state=card.state,
        last_reviewed_at=card.last_reviewed_at,
        review_count=card.review_count,
        lapse_count=card.lapse_count,
    )

    result = compute_next(prev, rating, now)

    # Log
    log = ReviewLog(
        card_id=card.id,
        student_id=card.student_id,
        topic_id=card.topic_id,
        rating=rating,
        elapsed_days=result.elapsed_days,
        scheduled_days=result.scheduled_days,
        stability_before=card.stability,
        stability_after=result.stability,
        difficulty_before=card.difficulty,
        difficulty_after=result.difficulty,
        state_before=card.state,
        state_after=result.state,
        reviewed_at=now,
    )
    db.add(log)

    # Kart güncelle
    card.stability = result.stability
    card.difficulty = result.difficulty
    card.state = result.state
    card.last_reviewed_at = now
    card.last_rating = rating
    card.due_at = result.due_at
    card.review_count = card.review_count + 1
    if rating == 1:
        card.lapse_count = card.lapse_count + 1
    card.updated_at = now

    db.flush()
    return ReviewOutcome(card=card, log=log, result=result)


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
