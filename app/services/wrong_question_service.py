"""Yanlış Soru Arşivi servisi — yakalama, etiketleme, yeniden çözme (FSRS),
kapanış ve koç analitiği. TEK MERKEZ: router'lar yalnız bu servisi çağırır.

Yaşam döngüsü:
  ekle (foto + bağlam) → [AI/elle etiket] → FSRS kuyruğu (due) →
  yeniden çöz (rating 1-4) → aralıklı WQ_CLOSE_STREAK başarılı → KAPANDI
  (tekrar yanlış → yeniden AÇIK + sıklaşan tekrar)

Erişim modeli:
  - Öğrenci: yalnız kendi kayıtları (sahiplik dışı → None → router 404).
  - Koç: yalnız kendi AKTİF öğrencisinin kayıtları (student.teacher_id).
  - Veli: erişemez (bilinçli — özel çalışma alanı).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    ExamResult,
    StudentBook,
    Subject,
    Task,
    Topic,
    User,
    WQ_CLOSE_STREAK,
    WQ_ERROR_TYPES,
    WQ_IMAGE_KINDS,
    WQ_IMAGE_QUESTION,
    WQ_SOURCE_DENEME,
    WQ_SOURCE_DIGER,
    WQ_SOURCE_GOREV,
    WQ_SOURCES,
    WQ_STATUS_ACIK,
    WQ_STATUS_KAPANDI,
    WQ_STREAK_MIN_GAP_HOURS,
    WrongQuestion,
    WrongQuestionImage,
)
from app.services.fsrs import (
    RATING_GOOD,
    VALID_RATINGS,
    FsrsState,
    compute_next,
)

# Fotoğraf sınırları (support_attachments deseninden; soru fotoğrafı için
# istemci zaten küçültme yapar — sunucu tavanı savunmadır)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024   # 6 MB / fotoğraf
MAX_IMAGES_PER_QUESTION = 4         # soru + çözüm dahil toplam


class WrongQuestionError(Exception):
    """Kod + kullanıcı mesajı taşıyan servis hatası (router HTTP'ye çevirir)."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(dt: datetime | None) -> datetime | None:
    """SQLite naive datetime'ı UTC-aware'e normalize et (fsrs.compute_next deseni)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ============================================================================
# Erişim çözümleri
# ============================================================================


def get_for_student(db: Session, student: User, wq_id: int) -> WrongQuestion | None:
    wq = db.get(WrongQuestion, wq_id)
    if wq is None or wq.student_id != student.id:
        return None
    return wq


def get_for_coach(db: Session, coach: User, wq_id: int) -> WrongQuestion | None:
    wq = db.get(WrongQuestion, wq_id)
    if wq is None:
        return None
    student = db.get(User, wq.student_id)
    if student is None or student.teacher_id != coach.id:
        return None
    return wq


# ============================================================================
# Oluşturma / etiketleme
# ============================================================================


def _resolve_context(
    db: Session,
    student: User,
    *,
    book_section_id: int | None,
    task_id: int | None,
    exam_result_id: int | None,
    subject_id: int | None,
    topic_id: int | None,
) -> dict:
    """Bağlam referanslarını doğrula + subject/topic'i otomatik türet.

    Öncelik: açık topic_id/subject_id > bölümden türetme. Bölüm verildiyse
    kitabın öğrenciye atanmış olması şart (yabancı kitap sızıntısı yok).
    """
    out: dict = {
        "book_id": None, "book_section_id": None, "task_id": None,
        "exam_result_id": None, "subject_id": subject_id, "topic_id": topic_id,
    }
    if book_section_id is not None:
        sec = db.get(BookSection, book_section_id)
        if sec is None:
            raise WrongQuestionError("section_not_found", "Bölüm bulunamadı.", 404)
        assigned = (
            db.query(StudentBook)
            .filter(StudentBook.student_id == student.id,
                    StudentBook.book_id == sec.book_id)
            .first()
        )
        if assigned is None:
            raise WrongQuestionError(
                "book_not_assigned", "Bu kitap öğrenciye atanmamış.", 404)
        out["book_section_id"] = sec.id
        out["book_id"] = sec.book_id
        # Bağlamdan otomatik etiket (sıfır sürtünme): bölüm konuya eşliyse
        # konu + ders kendiliğinden dolar; açık değer verildiyse o kazanır.
        if out["topic_id"] is None and sec.topic_id is not None:
            out["topic_id"] = sec.topic_id
        if out["subject_id"] is None:
            book = db.get(Book, sec.book_id)
            out["subject_id"] = book.subject_id if book else None
    if task_id is not None:
        t = db.get(Task, task_id)
        if t is None or t.student_id != student.id:
            raise WrongQuestionError("task_not_found", "Görev bulunamadı.", 404)
        out["task_id"] = t.id
    if exam_result_id is not None:
        er = db.get(ExamResult, exam_result_id)
        if er is None or er.student_id != student.id:
            raise WrongQuestionError("exam_not_found", "Deneme bulunamadı.", 404)
        out["exam_result_id"] = er.id
    # topic verildiyse subject'i topic'ten tamamla
    if out["topic_id"] is not None and out["subject_id"] is None:
        tp = db.get(Topic, out["topic_id"])
        out["subject_id"] = tp.subject_id if tp else None
    return out


def create_wrong_question(
    db: Session,
    student: User,
    *,
    created_by: User,
    source_kind: str = WQ_SOURCE_DIGER,
    book_section_id: int | None = None,
    task_id: int | None = None,
    exam_result_id: int | None = None,
    subject_id: int | None = None,
    topic_id: int | None = None,
    error_type: str | None = None,
    note: str | None = None,
) -> WrongQuestion:
    if source_kind not in WQ_SOURCES:
        source_kind = WQ_SOURCE_DIGER
    if error_type is not None and error_type not in WQ_ERROR_TYPES:
        raise WrongQuestionError("invalid_error_type", "Geçersiz hata türü.")
    ctx = _resolve_context(
        db, student,
        book_section_id=book_section_id, task_id=task_id,
        exam_result_id=exam_result_id, subject_id=subject_id, topic_id=topic_id,
    )
    # Kaynak türünü bağlamdan sağlamlaştır
    if ctx["task_id"] is not None and source_kind == WQ_SOURCE_DIGER:
        source_kind = WQ_SOURCE_GOREV
    if ctx["exam_result_id"] is not None and source_kind == WQ_SOURCE_DIGER:
        source_kind = WQ_SOURCE_DENEME
    now = _now()
    wq = WrongQuestion(
        student_id=student.id,
        created_by_id=created_by.id,
        source_kind=source_kind,
        error_type=error_type,
        note=(note or "").strip() or None,
        status=WQ_STATUS_ACIK,
        # Yeni kart HEMEN çözülebilir (standart aralıklı-tekrar davranışı).
        # Aralık işini FSRS ilk çözümden SONRA yapar; kapanış zaten aralıklı
        # (≥WQ_STREAK_MIN_GAP_HOURS) iki başarı ister → aynı gün seri şişmez.
        # (Eski hâli vadeyi yarına kuruyordu; öğrenci yeni eklediği yanlışla hiç
        # çalışamıyor, özellik ilk kullanımda ölü görünüyordu.)
        due_at=now,
        **{k: ctx[k] for k in (
            "book_id", "book_section_id", "task_id", "exam_result_id",
            "subject_id", "topic_id",
        )},
    )
    db.add(wq)
    db.flush()
    return wq


def update_tags(
    db: Session,
    wq: WrongQuestion,
    *,
    subject_id: int | None = None,
    topic_id: int | None = None,
    error_type: str | None = None,
    note: str | None = None,
    clear_note: bool = False,
) -> WrongQuestion:
    """Elle etiket düzeltme (AI önerisini onaylama/değiştirme dahil)."""
    if error_type is not None:
        if error_type not in WQ_ERROR_TYPES:
            raise WrongQuestionError("invalid_error_type", "Geçersiz hata türü.")
        wq.error_type = error_type
    if topic_id is not None:
        tp = db.get(Topic, topic_id)
        if tp is None:
            raise WrongQuestionError("topic_not_found", "Konu bulunamadı.", 404)
        wq.topic_id = tp.id
        wq.subject_id = tp.subject_id
    elif subject_id is not None:
        if db.get(Subject, subject_id) is None:
            raise WrongQuestionError("subject_not_found", "Ders bulunamadı.", 404)
        wq.subject_id = subject_id
    if clear_note:
        wq.note = None
    elif note is not None:
        wq.note = note.strip() or None
    return wq


def add_image(
    db: Session,
    wq: WrongQuestion,
    *,
    kind: str,
    content_type: str,
    data: bytes,
) -> WrongQuestionImage:
    if kind not in WQ_IMAGE_KINDS:
        kind = WQ_IMAGE_QUESTION
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_IMAGE_TYPES:
        raise WrongQuestionError(
            "invalid_image_type",
            "Yalnız JPEG/PNG/WebP fotoğraf yüklenebilir.")
    if not data:
        raise WrongQuestionError("empty_image", "Boş dosya yüklenemez.")
    if len(data) > MAX_IMAGE_BYTES:
        raise WrongQuestionError(
            "image_too_large",
            f"Fotoğraf {MAX_IMAGE_BYTES // (1024*1024)} MB'ı aşamaz.")
    count = (
        db.query(func.count(WrongQuestionImage.id))
        .filter(WrongQuestionImage.wrong_question_id == wq.id)
        .scalar()
    ) or 0
    if count >= MAX_IMAGES_PER_QUESTION:
        raise WrongQuestionError(
            "too_many_images",
            f"Bir soruya en fazla {MAX_IMAGES_PER_QUESTION} fotoğraf eklenebilir.")
    img = WrongQuestionImage(
        wrong_question_id=wq.id, kind=kind, content_type=ct,
        size_bytes=len(data), data=data,
    )
    db.add(img)
    db.flush()
    return img


# ============================================================================
# Yeniden çözme (FSRS) + kapanış
# ============================================================================


def record_attempt(
    db: Session,
    wq: WrongQuestion,
    rating: int,
    *,
    now: datetime | None = None,
) -> WrongQuestion:
    """Öğrencinin yeniden çözme sonucunu işle.

    rating (FSRS 1-4): 1=yine yanlış · 2=zor çözdüm · 3=çözdüm · 4=kolay çözdüm.
    Kapanış: aralıklı (≥ WQ_STREAK_MIN_GAP_HOURS) en az WQ_CLOSE_STREAK başarılı
    (rating ≥ 3) çözüm → KAPANDI. rating=1 → streak sıfırlanır; kapalıysa
    YENİDEN AÇILIR (unutulmuş demektir) ve FSRS tekrarı sıklaştırır.
    Aynı gün art arda basmak (gap < eşik) streak'i ŞİŞİRMEZ — FSRS yine işler.
    """
    if rating not in VALID_RATINGS:
        raise WrongQuestionError("invalid_rating", "Geçersiz değerlendirme (1-4).")
    if now is None:
        now = _now()

    prev_attempt = as_aware(wq.last_attempt_at)
    state = FsrsState(
        stability=wq.fsrs_stability,
        difficulty=wq.fsrs_difficulty,
        state=wq.fsrs_state,
        last_reviewed_at=wq.last_reviewed_at,
    )
    res = compute_next(state, rating, now)
    wq.fsrs_stability = res.stability
    wq.fsrs_difficulty = res.difficulty
    wq.fsrs_state = res.state
    wq.due_at = res.due_at
    wq.last_reviewed_at = now

    wq.attempts_count += 1
    wq.last_attempt_at = now

    if rating == 1:
        wq.correct_streak = 0
        if wq.status == WQ_STATUS_KAPANDI:
            wq.status = WQ_STATUS_ACIK   # unutulmuş → yeniden açılır
            wq.closed_at = None
    elif rating >= RATING_GOOD:
        gap_ok = (
            prev_attempt is None
            or (now - prev_attempt) >= timedelta(hours=WQ_STREAK_MIN_GAP_HOURS)
        )
        if gap_ok:
            wq.correct_streak += 1
        if wq.status == WQ_STATUS_ACIK and wq.correct_streak >= WQ_CLOSE_STREAK:
            wq.status = WQ_STATUS_KAPANDI
            wq.closed_at = now
    # rating == 2 (zor çözdüm): doğru ama pekişmemiş — streak değişmez, açık kalır
    return wq


# ============================================================================
# Listeleme / özet
# ============================================================================


@dataclass
class WrongQuestionCounts:
    total: int = 0
    open: int = 0
    closed: int = 0
    due: int = 0


def list_for_student(
    db: Session,
    student_id: int,
    *,
    status: str | None = None,
    subject_id: int | None = None,
    topic_id: int | None = None,
    error_type: str | None = None,
    source_kind: str | None = None,
    due_only: bool = False,
    q: str | None = None,
    limit: int = 200,
) -> tuple[list[WrongQuestion], WrongQuestionCounts]:
    base = db.query(WrongQuestion).filter(WrongQuestion.student_id == student_id)

    now = _now()
    counts = WrongQuestionCounts(
        total=base.count(),
        open=base.filter(WrongQuestion.status == WQ_STATUS_ACIK).count(),
        closed=base.filter(WrongQuestion.status == WQ_STATUS_KAPANDI).count(),
        due=base.filter(
            WrongQuestion.status == WQ_STATUS_ACIK,
            WrongQuestion.due_at.isnot(None),
            WrongQuestion.due_at <= now,
        ).count(),
    )

    qry = base.options(
        joinedload(WrongQuestion.topic),
        joinedload(WrongQuestion.subject),
        joinedload(WrongQuestion.book),
        joinedload(WrongQuestion.section),
    )
    if status in (WQ_STATUS_ACIK, WQ_STATUS_KAPANDI):
        qry = qry.filter(WrongQuestion.status == status)
    if subject_id is not None:
        qry = qry.filter(WrongQuestion.subject_id == subject_id)
    if topic_id is not None:
        qry = qry.filter(WrongQuestion.topic_id == topic_id)
    if error_type is not None:
        qry = qry.filter(WrongQuestion.error_type == error_type)
    if source_kind is not None:
        qry = qry.filter(WrongQuestion.source_kind == source_kind)
    if due_only:
        qry = qry.filter(
            WrongQuestion.status == WQ_STATUS_ACIK,
            WrongQuestion.due_at.isnot(None),
            WrongQuestion.due_at <= now,
        )
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(
            (WrongQuestion.ai_question_text.ilike(like))
            | (WrongQuestion.note.ilike(like))
        )
    rows = (
        qry.order_by(WrongQuestion.created_at.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return rows, counts


@dataclass
class TopicAccumulation:
    topic_id: int
    topic_name: str
    subject_name: str | None
    open_count: int
    closed_count: int


@dataclass
class CoachSummary:
    counts: WrongQuestionCounts = field(default_factory=WrongQuestionCounts)
    by_topic: list[TopicAccumulation] = field(default_factory=list)
    by_error_type: dict[str, int] = field(default_factory=dict)
    closed_last_30d: int = 0
    added_last_30d: int = 0


def coach_summary(db: Session, student_id: int) -> CoachSummary:
    """Koç tanı özeti: en çok biriken konular + hata türü dağılımı + kapanış."""
    _, counts = list_for_student(db, student_id, limit=1)
    out = CoachSummary(counts=counts)

    # Konu bazlı birikim (açık yanlışlar öncelikli sıralanır)
    rows = (
        db.query(
            WrongQuestion.topic_id,
            Topic.name,
            Subject.name,
            func.count(WrongQuestion.id),
        )
        .join(Topic, Topic.id == WrongQuestion.topic_id)
        .outerjoin(Subject, Subject.id == WrongQuestion.subject_id)
        .filter(
            WrongQuestion.student_id == student_id,
            WrongQuestion.topic_id.isnot(None),
        )
        .group_by(WrongQuestion.topic_id, Topic.name, Subject.name)
        .all()
    )
    # Açık/kapalı kırılımını ayrı say (dialect-bağımsız, küçük veri)
    open_map: dict[int, int] = {}
    closed_map: dict[int, int] = {}
    for tid, st, cnt in (
        db.query(WrongQuestion.topic_id, WrongQuestion.status, func.count(WrongQuestion.id))
        .filter(WrongQuestion.student_id == student_id,
                WrongQuestion.topic_id.isnot(None))
        .group_by(WrongQuestion.topic_id, WrongQuestion.status)
        .all()
    ):
        if st == WQ_STATUS_ACIK:
            open_map[tid] = int(cnt)
        else:
            closed_map[tid] = int(cnt)
    for tid, tname, sname, _total in rows:
        out.by_topic.append(TopicAccumulation(
            topic_id=tid, topic_name=tname, subject_name=sname,
            open_count=open_map.get(tid, 0), closed_count=closed_map.get(tid, 0),
        ))
    out.by_topic.sort(key=lambda x: (-x.open_count, -x.closed_count, x.topic_name))

    for et, cnt in (
        db.query(WrongQuestion.error_type, func.count(WrongQuestion.id))
        .filter(WrongQuestion.student_id == student_id,
                WrongQuestion.error_type.isnot(None))
        .group_by(WrongQuestion.error_type)
        .all()
    ):
        out.by_error_type[et] = int(cnt)

    month_ago = _now() - timedelta(days=30)
    out.closed_last_30d = (
        db.query(func.count(WrongQuestion.id))
        .filter(WrongQuestion.student_id == student_id,
                WrongQuestion.status == WQ_STATUS_KAPANDI,
                WrongQuestion.closed_at.isnot(None),
                WrongQuestion.closed_at >= month_ago)
        .scalar()
    ) or 0
    out.added_last_30d = (
        db.query(func.count(WrongQuestion.id))
        .filter(WrongQuestion.student_id == student_id,
                WrongQuestion.created_at >= month_ago)
        .scalar()
    ) or 0
    return out


def candidate_topics(db: Session, student: User, coach_id: int) -> list[dict]:
    """AI konu eşlemesi için ADAY konular — öğrencinin GERÇEK müfredat konuları.

    Kaynak: müfredat omurgası (curriculum_progress._applicable_subjects → sıralı
    leaf topic'ler). Model yalnız bu listeden id seçebilir → uydurma konu adı
    sisteme giremez. Kaynağı olan (kitap bölümüne eşli) konular ÖNCE gelir;
    liste MAX_CANDIDATE_TOPICS ile kırpılır.
    """
    from app.services.curriculum_progress import compute_curriculum_progress

    prog = compute_curriculum_progress(db, student, coach_id)
    with_res: list[dict] = []
    without_res: list[dict] = []
    for s in prog.subjects:
        for t in s.topics:
            row = {"id": t.topic_id, "name": t.name, "subject_name": s.name}
            (with_res if t.has_resource else without_res).append(row)
    return with_res + without_res


def apply_ai_tags(
    db: Session,
    wq: WrongQuestion,
    result: dict,
    *,
    overwrite_topic: bool = False,
) -> WrongQuestion:
    """AI çıktısını kayda uygula (öğrenci sonradan elle düzeltebilir).

    Konu: yalnız BOŞSA doldurulur (öğrencinin/koçun elle seçtiği konu ezilmez);
    `overwrite_topic=True` ile açıkça yeniden etiketlenebilir.
    """
    tid = result.get("topic_id")
    if tid is not None and (overwrite_topic or wq.topic_id is None):
        tp = db.get(Topic, int(tid))
        if tp is not None:
            wq.topic_id = tp.id
            wq.subject_id = tp.subject_id
    qt = (result.get("question_text") or "").strip()
    if qt:
        wq.ai_question_text = qt
    hint = (result.get("hint") or "").strip()
    if hint:
        wq.ai_hint = hint
    diff = (result.get("difficulty") or "").strip() or None
    if diff:
        wq.difficulty_guess = diff
    wq.ai_tagged_at = _now()
    return wq


def primary_question_image(db: Session, wq: WrongQuestion) -> WrongQuestionImage | None:
    """AI'a gönderilecek soru fotoğrafı (ilk 'question' karesi)."""
    return (
        db.query(WrongQuestionImage)
        .filter(
            WrongQuestionImage.wrong_question_id == wq.id,
            WrongQuestionImage.kind == WQ_IMAGE_QUESTION,
        )
        .order_by(WrongQuestionImage.id.asc())
        .first()
    )


def open_wrong_topic_map(db: Session, student_id: int) -> dict[int, float]:
    """Öneri motoru beslemesi: topic_id → normalize 'yanlış birikimi' skoru (0..1).

    review_scheduler.struggling_topic_ids_map ile aynı sözleşme — Faz 3'te
    suggestions motoruna ek sinyal olarak bağlanır. 3+ açık yanlış = tam sinyal.
    """
    rows = (
        db.query(WrongQuestion.topic_id, func.count(WrongQuestion.id))
        .filter(WrongQuestion.student_id == student_id,
                WrongQuestion.status == WQ_STATUS_ACIK,
                WrongQuestion.topic_id.isnot(None))
        .group_by(WrongQuestion.topic_id)
        .all()
    )
    return {tid: min(1.0, int(cnt) / 3.0) for tid, cnt in rows}
