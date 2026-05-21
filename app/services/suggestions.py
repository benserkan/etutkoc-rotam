"""Öneri/öğrenme motoru.

Öğretmenin geçmiş planlama davranışını ve öğrencinin ilerleme verisini kullanarak
yeni gün planlaması sırasında öneri üretir.

Veri kaynağı: mevcut Task/TaskBookItem tablolar (yeni tablo yok). Öğrenme tamamen
on-demand hesaplanır.

Ana kavramlar:

- **Maturity (olgunluk)**: sistem kaç hafta gözlem yaptı. 0..1 arası ölçek;
  8 haftaya kadar lineer artar, sonra sabitlenir. Düşük maturity → "silik" öneri.
- **Pattern strength**: o haftagününde belirli (kitap, bölüm) kombosunun kullanılma sıklığı.
- **Weakness signal**: öğrencinin geride bıraktığı bölümler (düşük yüzde, uzun süredir
  dokunulmamış) daha yüksek skor alır → sistem bu bölümleri öğretmene hatırlatır.
- **Typical count**: aynı (haftagünü, kitap, bölüm) kombinasyonunun tarihteki medyan
  test sayısı → öneri kalemi için varsayılan adet.
- **Subject variety**: o haftagününde tipik olarak kaç farklı ders ve toplam kaç kalem
  olduğu da öğrenilir; öneri setinin büyüklüğü ve dağılımı buna göre ayarlanır.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median
from typing import Iterable

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    FeedbackAction,
    SectionProgress,
    StudentBook,
    SuggestionFeedback,
    Task,
    TaskBookItem,
)
from app.models.curriculum import ExamSection
from app.models.user import Track


MATURITY_WEEKS = 8          # kaç hafta sonra sistem "olgun"
MATURITY_MIN_FLOOR = 0.10   # ilk hafta bile en az %10 güven (görünür olsun)

REJECT_DECAY_DAYS = 60      # bu kadar gün sonrası ret kaydı etkisiz
REJECT_STRONG_COUNT = 3     # bu kadar veya üstü ret → öneriyi komple çıkar
REJECT_SCORE_PENALTY = 0.55 # her aktif reddin score/confidence'a oranlı cezası (decay ile çarpılır)


# ---------------------------- Veri türleri ----------------------------


@dataclass
class Suggestion:
    book_id: int
    book_name: str
    book_type: str              # "soru_bankasi" / "brans_denemesi" vb.
    section_id: int
    section_label: str
    subject_id: int
    subject_name: str
    topic_name: str | None
    planned_count: int
    remaining: int              # kalan kapasite
    confidence: float           # 0..1 — görsel ağırlık
    score: float                # sıralama için
    reasons: list[str] = field(default_factory=list)


@dataclass
class StudentModel:
    """Öğrencinin geçmiş verisinden türetilmiş öğrenme modeli."""

    student_id: int
    weeks_observed: int
    days_observed: int
    pattern_counts: dict[tuple[int, int, int], int]
        # (dow, book_id, section_id) → kaç kez geçmişte o gün atanmış
    typical_counts: dict[tuple[int, int, int], list[int]]
        # aynı anahtar → geçmiş planned_count değerleri (medyan hesabı için)
    typical_items_per_day: dict[int, int]      # dow → o günün medyan kalem sayısı
    typical_subjects_per_day: dict[int, int]   # dow → o günün medyan ders çeşitliliği
    last_completed: dict[tuple[int, int], date]  # (book_id, section_id) → son tamamlanma tarihi
    # (dow|None, book_id, section_id) → zaman-bozunumlu ret ağırlığı (0..1 * count)
    reject_weights: dict[tuple[int | None, int, int], float] = field(default_factory=dict)
    # Aynı anahtar → ham ret sayısı (eşik karşılaştırması için)
    reject_counts: dict[tuple[int | None, int, int], int] = field(default_factory=dict)


# ---------------------------- Model kurulumu ----------------------------


def build_student_model(db: Session, student_id: int, today: date | None = None) -> StudentModel:
    """Bir öğrenci için öğrenme modelini oluştur. Request başına 1 kez çağrılır."""
    if today is None:
        today = date.today()

    # Tüm planlama tarihçesini kullan — "< today" filtresi kullanmıyoruz
    # çünkü öğretmenin bugün yarın için yaptığı plan da onun planlama davranışını yansıtır.
    # (İsteyen çağıran exclude_keys ile target gününün mevcut kalemlerini dışarıda bırakabilir.)
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section),
        )
        .filter(Task.student_id == student_id)
        .all()
    )

    pattern_counts: dict[tuple[int, int, int], int] = defaultdict(int)
    typical_counts: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    items_per_day: dict[int, list[int]] = defaultdict(list)
    subjects_per_day: dict[int, list[int]] = defaultdict(list)
    last_completed: dict[tuple[int, int], date] = {}

    # Günlere göre grup
    by_date: dict[date, list[Task]] = defaultdict(list)
    for t in tasks:
        by_date[t.date].append(t)

    for d, ts in by_date.items():
        dow = d.weekday()
        distinct_subjects: set[int] = set()
        item_count = 0
        for t in ts:
            for it in t.book_items:
                key = (dow, it.book_id, it.book_section_id)
                pattern_counts[key] += 1
                typical_counts[key].append(it.planned_count)
                item_count += 1
                if it.book and it.book.subject_id:
                    distinct_subjects.add(it.book.subject_id)
                # Son tamamlanma takibi (sadece fiilen tamamlanmış olanlar)
                if it.completed_count > 0 and t.completed_at:
                    prev = last_completed.get((it.book_id, it.book_section_id))
                    if prev is None or t.date > prev:
                        last_completed[(it.book_id, it.book_section_id)] = t.date
        items_per_day[dow].append(item_count)
        subjects_per_day[dow].append(len(distinct_subjects))

    days_observed = len(by_date)
    weeks_observed = 0
    if tasks:
        oldest = min(t.date for t in tasks)
        newest = max(t.date for t in tasks)
        # hem eski hem de bugün-sonrası plan bulunabilir; aralık bazında
        span_days = max(0, (newest - oldest).days)
        weeks_observed = max(0, span_days // 7)
        # eğer öğretmen tek haftaya yayılmış plan yapmışsa en az 1 hafta say
        if days_observed >= 3 and weeks_observed == 0:
            weeks_observed = 1

    typical_items_per_day = {dow: int(round(median(v))) if v else 0 for dow, v in items_per_day.items()}
    typical_subjects_per_day = {dow: int(round(median(v))) if v else 0 for dow, v in subjects_per_day.items()}

    # Reject geribildirimleri — zaman bozunumu ile ağırlıkla
    reject_weights, reject_counts = _load_reject_signal(db, student_id, today)

    return StudentModel(
        student_id=student_id,
        weeks_observed=weeks_observed,
        days_observed=days_observed,
        pattern_counts=dict(pattern_counts),
        typical_counts=dict(typical_counts),
        typical_items_per_day=typical_items_per_day,
        typical_subjects_per_day=typical_subjects_per_day,
        last_completed=last_completed,
        reject_weights=reject_weights,
        reject_counts=reject_counts,
    )


def _load_reject_signal(
    db: Session, student_id: int, today: date
) -> tuple[dict[tuple[int | None, int, int], float], dict[tuple[int | None, int, int], int]]:
    """SuggestionFeedback REJECTED kayıtlarını zaman bozunumu ile ağırlıklı hale getirir.

    Decay: (REJECT_DECAY_DAYS - days_since) / REJECT_DECAY_DAYS, 0..1 arası.
    `count` alanı da çarpan olarak kullanılır (teacher aynı öneriyi birden fazla reddettiyse).
    """
    rejections = (
        db.query(SuggestionFeedback)
        .filter(
            SuggestionFeedback.student_id == student_id,
            SuggestionFeedback.action == FeedbackAction.REJECTED,
        )
        .all()
    )
    weights: dict[tuple[int | None, int, int], float] = {}
    counts: dict[tuple[int | None, int, int], int] = {}
    for r in rejections:
        # Bozunum hesabı
        ts = r.updated_at or r.created_at
        try:
            ts_date = ts.date() if hasattr(ts, 'date') else date.today()
        except Exception:
            ts_date = date.today()
        days_since = (today - ts_date).days
        if days_since >= REJECT_DECAY_DAYS:
            continue
        decay = max(0.0, (REJECT_DECAY_DAYS - days_since) / REJECT_DECAY_DAYS)
        key = (r.day_of_week, r.book_id, r.book_section_id)
        weights[key] = weights.get(key, 0.0) + decay * max(1, r.count)
        counts[key] = counts.get(key, 0) + r.count
    return weights, counts


def record_rejection(
    db: Session,
    student_id: int,
    book_id: int,
    section_id: int,
    day_of_week: int | None,
) -> SuggestionFeedback:
    """Tekil ret kaydı ekler veya varsa count'ını artırır."""
    existing = (
        db.query(SuggestionFeedback)
        .filter(
            SuggestionFeedback.student_id == student_id,
            SuggestionFeedback.book_id == book_id,
            SuggestionFeedback.book_section_id == section_id,
            SuggestionFeedback.day_of_week == day_of_week,
            SuggestionFeedback.action == FeedbackAction.REJECTED,
        )
        .first()
    )
    if existing:
        existing.count += 1
        return existing
    fb = SuggestionFeedback(
        student_id=student_id,
        book_id=book_id,
        book_section_id=section_id,
        day_of_week=day_of_week,
        action=FeedbackAction.REJECTED,
        count=1,
    )
    db.add(fb)
    return fb


def maturity(model: StudentModel) -> float:
    """Olgunluk 0..1 arasında. Zemin MATURITY_MIN_FLOOR."""
    if model.weeks_observed == 0 and model.days_observed == 0:
        return 0.0
    base = min(1.0, model.weeks_observed / MATURITY_WEEKS)
    if base < MATURITY_MIN_FLOOR and model.days_observed > 0:
        base = MATURITY_MIN_FLOOR
    return base


# ---------------------------- Öneri üretimi ----------------------------


_TRACK_TO_AYT: dict[Track, ExamSection] = {
    Track.SAYISAL: ExamSection.AYT_SAY,
    Track.EA: ExamSection.AYT_EA,
    Track.SOZEL: ExamSection.AYT_SOZ,
    Track.DIL: ExamSection.AYT_DIL,
}


def book_track_mismatches(db: Session, student) -> list[dict]:
    """Öğrencinin kütüphanesinde mevcut profiliyle (sınıf+alan) eşleşmeyen
    kitapları listeler.

    Faz 7+ — Track değişimi senaryosu (örn 11. sınıfta SAY→EA): kütüphanede
    eski AYT_SAY kitapları kaldıysa bunlar artık öneri çekmez ve yanıltıcı
    olabilir. Kullanıcıyı bilinçlendirmek için.

    Returns: [{"book_id", "book_name", "subject_name", "exam_section_label"}, ...]
    Boş liste = eşleşmeyen kitap yok (veya filtre uygulanmıyor).
    """
    allowed = _allowed_exam_sections(student)
    if allowed is None:
        return []
    sbs = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    mismatches = []
    for sb in sbs:
        if not sb.book or not sb.book.subject:
            continue
        es = sb.book.subject.exam_section
        if es not in allowed:
            from app.models.curriculum import EXAM_SECTION_LABELS
            mismatches.append({
                "book_id": sb.book_id,
                "book_name": sb.book.name,
                "subject_name": sb.book.subject.name,
                "exam_section_label": (
                    EXAM_SECTION_LABELS.get(es, "—") if es else "—"
                ),
            })
    return mismatches


def diagnostic_priority_subjects(
    db: Session, student, *, lookback_days: int = 28
) -> list[dict]:
    """Mezun/12.sınıf öğrenci için "henüz dokunulmamış" ders listesi.

    Mezun YKS hazırlığı başlangıcında, geniş bir kütüphane var ama hangisinden
    başlayacağı belirsiz. Bu helper son N günde Task'ta hiç kullanılmamış olan
    derslerin listesini döner — diagnostic önceliği.

    Returns: [{"subject_id", "subject_name", "exam_section_label", "book_count"}]
    """
    from app.models.curriculum import EXAM_SECTION_LABELS

    # Öğrencinin kütüphanesinde olan tüm dersler
    sbs = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(StudentBook.student_id == student.id)
        .all()
    )
    subjects_in_lib: dict[int, dict] = {}
    for sb in sbs:
        if not sb.book or not sb.book.subject:
            continue
        sid = sb.book.subject.id
        if sid not in subjects_in_lib:
            subjects_in_lib[sid] = {
                "subject_id": sid,
                "subject_name": sb.book.subject.name,
                "exam_section_label": (
                    EXAM_SECTION_LABELS.get(sb.book.subject.exam_section, "—")
                    if sb.book.subject.exam_section else "—"
                ),
                "book_count": 0,
            }
        subjects_in_lib[sid]["book_count"] += 1

    # Son N günde Task'ta dokunulmuş ders ID'leri
    cutoff = date.today() - timedelta(days=lookback_days)
    touched_q = (
        db.query(Book.subject_id)
        .join(TaskBookItem, TaskBookItem.book_id == Book.id)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(
            Task.student_id == student.id,
            Task.date >= cutoff,
        )
        .distinct()
        .all()
    )
    touched_ids = {row[0] for row in touched_q}

    # Filter: filtreden geçen + dokunulmamış
    allowed = _allowed_exam_sections(student)
    untouched = []
    for sid, info in subjects_in_lib.items():
        if sid in touched_ids:
            continue
        if allowed is not None:
            # Subject objesini tekrar bulmak yerine inline kontrol
            es = next(
                (sb.book.subject.exam_section for sb in sbs
                 if sb.book and sb.book.subject and sb.book.subject.id == sid),
                None,
            )
            if es not in allowed:
                continue
        untouched.append(info)
    untouched.sort(key=lambda x: x["subject_name"])
    return untouched


def _allowed_exam_sections(student) -> set[ExamSection | None] | None:
    """Bu öğrenciye uygun sınav bölümleri (Subject.exam_section eşleşmesi).

    None döner → filtre uygulanmaz (örn. 9-10 Maarif, henüz alan seçimi yok;
    bütün dersler aday). exam_section'ı NULL olan dersler her zaman kabul edilir
    (LGS-öncesi mevcut data + kullanıcı-tanımlı dersler için geriye uyum).

    - 5-8 (LGS): {LGS, None}
    - 11-12 ve mezun: {TYT, track→AYT_X, None}; track yoksa {TYT, None} (UI
      uyarı verir, AYT'siz çalışır)
    - 9-10: None (filtre yok — Maarif'te 9-10 tüm dersleri görmeli)
    """
    grade = student.grade_level
    is_graduate = bool(student.is_graduate)

    if not is_graduate and grade is not None and grade <= 8:
        return {ExamSection.LGS, None}

    if is_graduate or (grade is not None and grade >= 11):
        allowed: set[ExamSection | None] = {ExamSection.TYT, None}
        if student.track is not None:
            ayt = _TRACK_TO_AYT.get(student.track)
            if ayt:
                allowed.add(ayt)
        return allowed

    # 9-10 ve diğer (filtre yok)
    return None


def _progress_map(db: Session, student_id: int) -> dict[int, SectionProgress]:
    """section_id → SectionProgress (kapasite ve kalan için)."""
    sps = (
        db.query(SectionProgress)
        .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
        .options(
            joinedload(SectionProgress.section).joinedload(BookSection.topic),
            joinedload(SectionProgress.student_book)
            .joinedload(StudentBook.book)
            .joinedload(Book.subject),
        )
        .filter(StudentBook.student_id == student_id)
        .all()
    )
    return {sp.book_section_id: sp for sp in sps}


def suggest_for_date(
    db: Session,
    student_id: int,
    target_date: date,
    *,
    model: StudentModel | None = None,
    exclude_keys: Iterable[tuple[int, int]] = (),
    today: date | None = None,
    max_suggestions: int | None = None,
) -> list[Suggestion]:
    """Bir gün için öneri listesi üret.

    Phase-aware (Faz 6.4): Öğrencinin academic_year'ında target_date'i
    kapsayan bir phase varsa, phase.capacity_multiplier ile günlük öneri
    hacmi ölçeklenir. Yaz kampında 1.5x, kış tatili 1.4x, sınav hazırlık
    1.3x. Olağan dönem 1.0x.
    """
    if today is None:
        today = date.today()
    if model is None:
        model = build_student_model(db, student_id, today=today)

    mat = maturity(model)
    dow = target_date.weekday()

    # Öğrenci kaydı — phase tespit + track/sınav-bölümü filtresi için
    from app.models import User as _UserModel
    student = db.get(_UserModel, student_id)

    # Phase tespit — student.academic_year.active_phase_on(target_date)
    phase_capacity_mult = 1.0
    try:
        if student and student.academic_year:
            active_phase = student.academic_year.active_phase_on(target_date)
            if active_phase:
                phase_capacity_mult = active_phase.capacity_multiplier
    except Exception:
        # Phase tespiti başarısız olursa varsayılan davranış (1.0x)
        phase_capacity_mult = 1.0

    # Mevcut section ilerlemeleri
    progress_by_section = _progress_map(db, student_id)
    exclude_set = set(exclude_keys)

    # Faz 7: Track + sınav-bölümü filtresi
    # 11+/mezun için sadece TYT + öğrencinin AYT alanı; LGS için sadece LGS;
    # 9-10 için filtre yok. Subject.exam_section None ise filtreden geçer
    # (geriye uyum + kullanıcı-tanımlı sınav-bağımsız dersler).
    if student is not None:
        allowed_sections = _allowed_exam_sections(student)
        if allowed_sections is not None:
            progress_by_section = {
                sid: sp for sid, sp in progress_by_section.items()
                if sp.student_book.book.subject.exam_section in allowed_sections
            }

    # 1) Pattern adayları — bu haftagünü
    pattern_scores: dict[tuple[int, int], int] = defaultdict(int)
    for (d, book_id, section_id), freq in model.pattern_counts.items():
        if d != dow:
            continue
        pattern_scores[(book_id, section_id)] = max(
            pattern_scores[(book_id, section_id)], freq
        )

    # 2) Zayıflık adayları — dersten/bölümden uzaklaşma, geride kalma
    weakness_scores: dict[tuple[int, int], float] = {}
    # Review tekrar kartı sinyali — bu öğrencinin "zorlandığı" konu id'leri
    # (Stage 12 ReviewCard verisi → AI önerisine boost). Topic→Section
    # eşlemesi BookSection.topic_id üzerinden yapılır.
    try:
        from app.services.review_scheduler import struggling_topic_ids_map
        review_struggle: dict[int, float] = struggling_topic_ids_map(
            db, student_id=student_id, min_score=10.0
        )
    except Exception:
        review_struggle = {}
    review_weakness_keys: set[tuple[int, int]] = set()
    for section_id, sp in progress_by_section.items():
        section = sp.section
        if section.test_count == 0:
            continue
        remaining = section.test_count - sp.completed_count - sp.reserved_count
        if remaining <= 0:
            continue
        progress_pct = (sp.completed_count + sp.reserved_count) / section.test_count
        book_id = sp.student_book.book_id
        last = model.last_completed.get((book_id, section_id))
        days_gap = (today - last).days if last else None

        w = 0.0
        # Düşük yüzde → zayıflık
        if progress_pct < 0.5:
            w += (0.5 - progress_pct) * 0.8
        # Uzun dokunulmamış → zayıflık
        if days_gap is not None:
            if days_gap > 21:
                w += 0.45
            elif days_gap > 14:
                w += 0.30
            elif days_gap > 7:
                w += 0.15
        elif last is None and (sp.reserved_count == 0 and sp.completed_count == 0):
            # Hiç dokunulmamış
            w += 0.10
        # Review tekrar kartında zorlanan konu boost'u (Stage 12 → öneri besleme)
        topic_id = section.topic_id
        if topic_id is not None and topic_id in review_struggle:
            review_boost = review_struggle[topic_id]  # 0..1
            w += 0.50 * review_boost  # max +0.50 ekstra ağırlık
            review_weakness_keys.add((book_id, section_id))
        if w > 0:
            weakness_scores[(book_id, section_id)] = min(1.0, w)

    # Aday birleşimi
    all_keys = (set(pattern_scores.keys()) | set(weakness_scores.keys())) - exclude_set

    suggestions: list[Suggestion] = []
    for key in all_keys:
        book_id, section_id = key
        sp = progress_by_section.get(section_id)
        if not sp:
            continue
        section = sp.section
        remaining = section.test_count - sp.completed_count - sp.reserved_count
        if remaining <= 0:
            continue
        book = sp.student_book.book
        subject = book.subject

        freq = pattern_scores.get(key, 0)
        weeks = max(1, model.weeks_observed)
        pattern_strength = min(1.0, freq / weeks)  # 1x/hafta = 1.0

        weakness = weakness_scores.get(key, 0.0)

        # Ret sinyali — hem gün-bazlı hem genel
        reject_specific = model.reject_weights.get((dow, book_id, section_id), 0.0)
        reject_general = model.reject_weights.get((None, book_id, section_id), 0.0)
        reject_weight = reject_specific + 0.5 * reject_general
        reject_count_specific = model.reject_counts.get((dow, book_id, section_id), 0)
        reject_count_general = model.reject_counts.get((None, book_id, section_id), 0)
        total_rejects = reject_count_specific + reject_count_general

        # Çok reddedilmişse öneride bulunma
        if total_rejects >= REJECT_STRONG_COUNT:
            continue

        # Skorlar — sıralama için
        score = 0.55 * pattern_strength + 0.45 * weakness
        score *= max(0.0, 1.0 - REJECT_SCORE_PENALTY * min(1.0, reject_weight))

        # Güven — görsel yoğunluk için
        confidence = mat * (0.55 + 0.45 * pattern_strength) + 0.25 * weakness
        confidence *= max(0.0, 1.0 - REJECT_SCORE_PENALTY * min(1.0, reject_weight))
        confidence = max(MATURITY_MIN_FLOOR if mat > 0 else 0.0, min(1.0, confidence))

        # Tipik adet
        counts_list = model.typical_counts.get((dow, book_id, section_id), [])
        if counts_list:
            typical = int(round(median(counts_list)))
        else:
            typical = 2  # varsayılan
        typical = max(1, min(typical, remaining))

        # Açıklama
        reasons: list[str] = []
        if freq > 0:
            reasons.append(f"Bu güne {freq}× önceden atanmış")
        if key in review_weakness_keys:
            reasons.append("🧠 Tekrar kartında zorlanılan konu")
        if weakness > 0.3:
            reasons.append("Bu bölümde belirgin geride kalma var")
        elif weakness > 0:
            reasons.append("Bu bölüm dikkat gerektirebilir")
        if total_rejects > 0:
            reasons.append(f"{total_rejects}× önceden reddettiniz")
        if mat < 0.3:
            reasons.append("Sistem hâlâ öğreniyor")

        suggestions.append(Suggestion(
            book_id=book_id,
            book_name=book.name,
            book_type=book.type.value,
            section_id=section_id,
            section_label=section.label,
            subject_id=subject.id,
            subject_name=subject.name,
            topic_name=section.topic.name if section.topic else None,
            planned_count=typical,
            remaining=remaining,
            confidence=confidence,
            score=score,
            reasons=reasons,
        ))

    suggestions.sort(key=lambda s: (-s.score, -s.confidence, s.subject_name, s.book_name))

    # Ders çeşitliliği ve tipik hacim
    typical_n = max_suggestions or model.typical_items_per_day.get(dow, 0) or 5
    # Phase kapasite çarpanı uygulansın (yaz kampı 1.5x, sınav hazırlık 1.3x...)
    if phase_capacity_mult != 1.0:
        typical_n = int(round(typical_n * phase_capacity_mult))
    typical_n = max(3, min(15, typical_n))
    typical_distinct_subjects = model.typical_subjects_per_day.get(dow, 0) or 3
    typical_distinct_subjects = max(2, min(6, typical_distinct_subjects))
    max_per_subject = max(1, typical_n // max(1, typical_distinct_subjects))

    # İlk turda her ders için az sayıda, kalan yerler için ikinci turda doldur
    selected: list[Suggestion] = []
    per_subject: Counter[int] = Counter()
    for s in suggestions:
        if len(selected) >= typical_n:
            break
        if per_subject[s.subject_id] < max_per_subject:
            selected.append(s)
            per_subject[s.subject_id] += 1
    if len(selected) < typical_n:
        for s in suggestions:
            if s in selected:
                continue
            selected.append(s)
            per_subject[s.subject_id] += 1
            if len(selected) >= typical_n:
                break

    return selected


# ---------------------------- Sözel açıklama yardımcıları ----------------------------


def maturity_label(mat: float) -> str:
    if mat < 0.15:
        return "Öğrenme başlangıcı"
    if mat < 0.40:
        return "Erken aşama"
    if mat < 0.70:
        return "Gelişiyor"
    return "Olgun"


def confidence_label(c: float) -> str:
    if c < 0.30:
        return "Zayıf"
    if c < 0.60:
        return "Orta"
    if c < 0.85:
        return "Güçlü"
    return "Çok güçlü"
