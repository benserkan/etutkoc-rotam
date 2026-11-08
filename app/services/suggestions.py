"""Öneri/öğrenme motoru.

Öğretmenin geçmiş planlama davranışını ve öğrencinin ilerleme verisini kullanarak
yeni gün planlaması sırasında öneri üretir.

Veri kaynağı: mevcut Task/TaskBookItem tablolar (yeni tablo yok). Öğrenme tamamen
on-demand hesaplanır.

Ana kavramlar:

- **Maturity (olgunluk)**: sistem kaç hafta gözlem yaptı. 0..1 arası ölçek;
  8 haftaya kadar lineer artar, sonra sabitlenir. Düşük maturity → "silik" öneri.
- **Curriculum priority (müfredat önceliği — ANA sinyal)**: bölümün eşli olduğu
  konunun, o dersin AÇIK (kalan kapasiteli) konuları içindeki resmi sırası
  (Topic.order). Frontier (sıradaki konu) = rank 0 → en yüksek öncelik; müfredatta
  ilerideki konular rank arttıkça cezalanır; çok ilerideki (rank ≥ 3) konular
  desen/tekrar sinyali yoksa hiç önerilmez. Başlanan (kısmen tamamlanmış) konuya
  bitirme bonusu verilir. Konuya eşlenmemiş bölüm nötr kalır.
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

from sqlalchemy import and_, func
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

# --- Müfredat önceliği (curriculum-first skorlama) ---
CURRICULUM_W = 0.45         # skor bileşeni ağırlıkları: müfredat ANA sinyal
WEAKNESS_W = 0.30
PATTERN_W = 0.25
CURRICULUM_NEUTRAL = 0.30   # konuya eşlenmemiş bölüm — ne öne çıkar ne cezalanır
CURRICULUM_RANK_DECAY = 0.30  # frontier'dan ileri her açık konu için ceza
CURRICULUM_FAR_RANK = 3     # bu ve ötesi "müfredatta çok ileride"
CURRICULUM_STARTED_BONUS = 0.15  # başlanan (kısmen çözülmüş) konuyu bitirme bonusu
FRONTIER_POOL_RANK = 1      # rank ≤ bu olan bölümler desen/zayıflık olmasa da aday


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
    curriculum_rank: int | None = None  # dersin açık konuları içinde 0=sıradaki; None=eşlenmemiş
    features: dict[str, float] = field(default_factory=dict)  # özellik vektörü (öğrenme kaydı)


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
    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section),
        )
        .filter(Task.student_id == student_id)
        .all()
    )
    reject_weights, reject_counts = _load_reject_signal(db, student_id, today)
    return model_from_tasks(student_id, tasks, reject_weights, reject_counts)


def model_from_tasks(
    student_id: int,
    tasks: list[Task],
    reject_weights: dict | None = None,
    reject_counts: dict | None = None,
) -> StudentModel:
    """Görev listesinden öğrenme modeli (saf — backtest geçmişi keserek çağırır)."""
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

    return StudentModel(
        student_id=student_id,
        weeks_observed=weeks_observed,
        days_observed=days_observed,
        pattern_counts=dict(pattern_counts),
        typical_counts=dict(typical_counts),
        typical_items_per_day=typical_items_per_day,
        typical_subjects_per_day=typical_subjects_per_day,
        last_completed=last_completed,
        reject_weights=dict(reject_weights or {}),
        reject_counts=dict(reject_counts or {}),
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
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),   # P4: arşivliden öneri gelmez
        )
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
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),   # P4: arşivliden öneri gelmez
        )
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


@dataclass
class _SectionCtx:
    """Öğrencinin bir kitap bölümü için öneri bağlamı (SectionProgress kaydı
    olmasa bile var — coalesce 0)."""

    section: BookSection
    book: Book
    completed: int
    reserved: int

    @property
    def remaining(self) -> int:
        return max(0, (self.section.test_count or 0) - self.completed - self.reserved)


def _section_universe(db: Session, student_id: int) -> dict[int, _SectionCtx]:
    """section_id → bağlam. Öğrencinin ATANMIŞ tüm kitaplarının TÜM bölümleri.

    Eski `_progress_map` yalnız SectionProgress satırı olan bölümleri görüyordu →
    hiç dokunulmamış (hiç rezerv edilmemiş) yeni kitabın bölümleri önerilere hiç
    giremiyordu. Bu sorgu outerjoin ile tam evreni kapsar.
    """
    rows = (
        db.query(
            BookSection,
            Book,
            func.coalesce(SectionProgress.completed_count, 0),
            func.coalesce(SectionProgress.reserved_count, 0),
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .options(joinedload(BookSection.topic), joinedload(Book.subject))
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.archived_at.is_(None),   # P4: arşivliden öneri gelmez
        )
        .all()
    )
    return {
        sec.id: _SectionCtx(section=sec, book=book, completed=int(c or 0), reserved=int(r or 0))
        for sec, book, c, r in rows
    }


@dataclass
class _CurriculumSignal:
    """Bölüm → müfredat sırası sinyali (frontier rank)."""

    rank_by_section: dict[int, int]     # section_id → dersin AÇIK konuları içinde 0-tabanlı sıra
    started_topic_sections: set[int]    # konusu başlanmış (kısmen çözülmüş) + bitmemiş bölümler


def _curriculum_signal(universe: dict[int, _SectionCtx]) -> _CurriculumSignal:
    """Her bölümün konusunun (Topic) müfredat sırasındaki yerini hesapla.

    Ders bazında: konuya eşli bölümlerin kalan kapasitesi konu düzeyinde
    toplanır; kalanı > 0 olan (AÇIK) konular resmi sıraya (grade_level, order)
    dizilir; rank = bu listede 0-tabanlı pozisyon. rank 0 = "müfredatta sıradaki
    konu" (frontier). Tamamı çözülmüş/rezervli konu listeden düşer → frontier
    otomatik ilerler. Konuya eşlenmemiş bölümler sinyal dışıdır (nötr skorlanır).
    """
    topic_secs: dict[int, list[int]] = {}
    topic_meta: dict[int, tuple] = {}       # topic_id → (subject_id, order_key)
    topic_remaining: dict[int, int] = {}
    topic_completed: dict[int, int] = {}
    for sid, ctx in universe.items():
        t = ctx.section.topic
        if t is None:
            continue
        topic_secs.setdefault(t.id, []).append(sid)
        topic_meta[t.id] = (
            t.subject_id,
            (
                t.grade_level if t.grade_level is not None else 99,
                t.order if t.order is not None else 9999,
                t.id,
            ),
        )
        topic_remaining[t.id] = topic_remaining.get(t.id, 0) + ctx.remaining
        topic_completed[t.id] = topic_completed.get(t.id, 0) + ctx.completed

    by_subject: dict[int, list[int]] = {}
    for tid, (subj_id, _key) in topic_meta.items():
        if topic_remaining.get(tid, 0) > 0:
            by_subject.setdefault(subj_id, []).append(tid)
    rank_by_topic: dict[int, int] = {}
    for tids in by_subject.values():
        tids.sort(key=lambda x: topic_meta[x][1])
        for i, tid in enumerate(tids):
            rank_by_topic[tid] = i

    rank_by_section: dict[int, int] = {}
    started_topic_sections: set[int] = set()
    for tid, sids in topic_secs.items():
        r = rank_by_topic.get(tid)
        started = topic_completed.get(tid, 0) > 0 and topic_remaining.get(tid, 0) > 0
        for sid in sids:
            if r is not None:
                rank_by_section[sid] = r
            if started:
                started_topic_sections.add(sid)
    return _CurriculumSignal(rank_by_section, started_topic_sections)


# ---------------------------- Özellik ağırlıkları ----------------------------
#
# Her aday bölüm bir özellik vektörüyle (0..1) tanımlanır; skor = Σ ağırlık × özellik.
# LEGACY_WEIGHTS 2026-11-08 öncesi formülün doğrusal karşılığıdır (müfredat 0.45 ·
# desen 0.25 · zayıflık 0.30 [eskime + tekrar + açık yanlış + deneme]); ölçüm
# betiği eski/yeni karşılaştırmasını bununla yapar. DEFAULT_WEIGHTS yeni sinyalleri
# (iplik devamı, yapılmayan görev, geçen haftanın zorlandığı konu, geride kalan
# ders) de katar. Koç başına öğrenilen ağırlıklar (Faz 2) bu sözlüğün üstüne yazılır.

LEGACY_WEIGHTS: dict[str, float] = {
    "curriculum": CURRICULUM_W,
    "started": CURRICULUM_W * CURRICULUM_STARTED_BONUS,
    "pattern": PATTERN_W,
    "staleness": WEAKNESS_W,
    "review": WEAKNESS_W * 0.50,
    "open_wrong": WEAKNESS_W * 0.55,
    "exam_weak": WEAKNESS_W * 0.45,
}

# 2026-11-08 canlı ölçümü (scripts/backtest_suggestions.py --fit): 12 hafta, 1.991
# test kalemi; ilk %60 günde öğrenildi, son %40'ta ölçüldü → koçun gerçekte verdiği
# bölüm ekrandaki önerilerde eski formülde %8, bu ağırlıklarla %50. Koçu en iyi
# açıklayan sinyal iplik devamı + kitap sırası; resmi müfredat sırası neredeyse hiç.
# Zayıflık sinyalleri küçük ağırlıkla kalır: sıralamayı bozmaz, gerekçe olarak görünür.
DEFAULT_WEIGHTS: dict[str, float] = {
    "thread": 8.0,
    "thread_next": 7.5,
    "book_next": 0.70,
    "coverage_lag": 0.30,
    "pattern": 0.20,
    "struggle": 0.20,
    "open_wrong": 0.16,
    "exam_weak": 0.12,
    "review": 0.12,
    "neglect": 0.08,
    "subject_gap": 0.05,
    "subject_neglect": 0.03,
    "curriculum": 0.05,
    "started": 0.05,
    "staleness": 0.01,
}

# Müfredatta çok ileride olsa da adayı tutan sinyaller (koç neden önerildiğini görür)
_FAR_RANK_EXEMPT = ("thread", "thread_next", "book_next", "neglect", "struggle", "open_wrong", "review", "exam_weak")


def _curriculum_reason(rank: int | None) -> str | None:
    if rank == 0:
        return "Müfredatta sıradaki konu"
    if rank == 1:
        return "Müfredatta yaklaşan konu"
    if rank is not None and rank >= CURRICULUM_FAR_RANK:
        return "Müfredatta ileride"
    return None


def _staleness(ctx: _SectionCtx, last: date | None, today: date) -> float:
    """Eski 'zayıflık' bileşeninin ilerleme/eskime kısmı (0..1)."""
    section = ctx.section
    if not section.test_count:
        return 0.0
    progress_pct = (ctx.completed + ctx.reserved) / section.test_count
    w = 0.0
    if progress_pct < 0.5:
        w += (0.5 - progress_pct) * 0.8
    if last is not None:
        gap = (today - last).days
        if gap > 21:
            w += 0.45
        elif gap > 14:
            w += 0.30
        elif gap > 7:
            w += 0.15
    elif ctx.reserved == 0 and ctx.completed == 0:
        w += 0.10
    return min(1.0, w)


def rank_candidates(
    *,
    universe: dict[int, _SectionCtx],
    model: StudentModel,
    signals,
    target_date: date,
    today: date,
    weights: dict[str, float] | None = None,
    exclude_set: set[tuple[int, int]] = frozenset(),
    phase_capacity_mult: float = 1.0,
    max_suggestions: int | None = None,
    select: bool = True,
) -> list[Suggestion]:
    """Saf sıralayıcı — canlı uç ve geçmişi yeniden oynatan ölçüm aynı kodu kullanır.

    `signals` = rec_signals.SignalBundle (target_date'e göre hesaplanmış).
    `select=False` → ders çeşitliliği seçimi yapılmadan tüm sıralı liste döner.
    """
    from app.services import rec_signals

    w = dict(DEFAULT_WEIGHTS if weights is None else weights)
    mat = maturity(model)
    dow = target_date.weekday()
    curriculum = _curriculum_signal(universe)

    # bölüm → kitapta bir önceki bölüm (iplik "sıradaki" özelliği için)
    by_book: dict[int, list[_SectionCtx]] = defaultdict(list)
    for ctx in universe.values():
        by_book[ctx.book.id].append(ctx)
    prev_of: dict[int, int] = {}
    book_next: dict[int, float] = {}   # bölüm → kitabın ilk açık bölümü mü (1.0 süren / 0.5 başlanmamış kitap)
    for lst in by_book.values():
        lst.sort(key=lambda c: (c.section.order or 0, c.section.id))
        for i in range(1, len(lst)):
            prev_of[lst[i].section.id] = lst[i - 1].section.id
        started_book = any(c.completed > 0 for c in lst)
        first_open = next((c for c in lst if c.section.test_count and c.remaining > 0), None)
        if first_open is not None:
            book_next[first_open.section.id] = 1.0 if started_book else 0.5

    coverage = rec_signals.subject_coverage_lag(
        (c.book.subject_id, int(c.section.test_count or 0), c.completed + c.reserved)
        for c in universe.values()
    )

    pattern_freq: dict[tuple[int, int], int] = defaultdict(int)
    for (d, book_id, section_id), freq in model.pattern_counts.items():
        if d == dow:
            pattern_freq[(book_id, section_id)] = max(pattern_freq[(book_id, section_id)], freq)

    suggestions: list[Suggestion] = []
    weeks = max(1, model.weeks_observed)
    for section_id, ctx in universe.items():
        section = ctx.section
        book = ctx.book
        key = (book.id, section_id)
        if key in exclude_set or not section.test_count or ctx.remaining <= 0:
            continue
        rank = curriculum.rank_by_section.get(section_id)
        freq = pattern_freq.get(key, 0)
        feats, why = rec_signals.section_features(
            signals,
            section_id=section_id,
            subject_id=book.subject_id,
            topic_id=section.topic_id,
            prev_section_id=prev_of.get(section_id),
            remaining=ctx.remaining,
            prev_finished=(
                prev_of.get(section_id) in universe
                and universe[prev_of[section_id]].remaining <= 0
            ),
            coverage=coverage.get(book.subject_id),
        )
        feats["curriculum"] = (
            CURRICULUM_NEUTRAL if rank is None else max(0.05, 1.0 - CURRICULUM_RANK_DECAY * rank)
        )
        if section_id in curriculum.started_topic_sections:
            feats["started"] = 1.0
        if section_id in book_next:
            feats["book_next"] = book_next[section_id]
            why.setdefault("book_next", "kitabın sırayla ilk açık bölümü")
        if freq:
            feats["pattern"] = min(1.0, freq / weeks)
        st = _staleness(ctx, model.last_completed.get(key), today)
        if st:
            feats["staleness"] = st

        # Aday havuzu: müfredat dışında en az bir pozitif sinyal ya da frontier
        side = sum(w.get(k, 0.0) * v for k, v in feats.items() if k != "curriculum")
        if side <= 0 and not (rank is not None and rank <= FRONTIER_POOL_RANK):
            continue
        # Müfredatta çok ileride + o güne desen yok + istisna sinyal yok → önerme
        if (
            rank is not None
            and rank >= CURRICULUM_FAR_RANK
            and not freq
            and not any(feats.get(k) and w.get(k, 0.0) > 0 for k in _FAR_RANK_EXEMPT)
        ):
            continue

        reject_weight = (
            model.reject_weights.get((dow, book.id, section_id), 0.0)
            + 0.5 * model.reject_weights.get((None, book.id, section_id), 0.0)
        )
        total_rejects = (
            model.reject_counts.get((dow, book.id, section_id), 0)
            + model.reject_counts.get((None, book.id, section_id), 0)
        )
        if total_rejects >= REJECT_STRONG_COUNT:
            continue
        penalty = max(0.0, 1.0 - REJECT_SCORE_PENALTY * min(1.0, reject_weight))

        contrib = {k: w.get(k, 0.0) * v for k, v in feats.items()}
        score = sum(contrib.values()) * penalty

        weakness_like = min(1.0, sum(feats.get(k, 0.0) for k in (
            "staleness", "neglect", "struggle", "exam_weak", "open_wrong", "review")))
        confidence = (
            mat * (0.40 + 0.35 * feats.get("pattern", 0.0) + 0.35 * max(
                feats.get("thread", 0.0), feats.get("thread_next", 0.0)))
            + 0.20 * weakness_like
            + 0.30 * feats["curriculum"]
        ) * penalty
        confidence = max(MATURITY_MIN_FLOOR if mat > 0 else 0.0, min(1.0, confidence))

        counts_list = model.typical_counts.get((dow, book.id, section_id), [])
        typical = int(round(median(counts_list))) if counts_list else 2
        typical = max(1, min(typical, ctx.remaining))

        # Gerekçeler: katkısı en büyük sinyaller önce, sayılı metinle
        reasons: list[str] = []
        ordered = sorted(
            (k for k, c in contrib.items() if c > 0 and k in why),
            key=lambda k: -contrib[k],
        )
        for k in ordered[:3]:
            reasons.append(f"{rec_signals.FEATURE_LABELS_TR[k]}: {why[k]}")
        cr = _curriculum_reason(rank)
        if cr:
            reasons.append(cr)
        if "started" in feats:
            reasons.append("Başlanan konuyu tamamlama")
        if freq:
            reasons.append(f"Bu güne {freq}× önceden atanmış")
        if feats.get("staleness", 0) > 0.3:
            reasons.append("Bu bölümde belirgin geride kalma var")
        if total_rejects:
            reasons.append(f"{total_rejects}× önceden reddettiniz")
        if mat < 0.3:
            reasons.append("Sistem hâlâ öğreniyor")

        suggestions.append(Suggestion(
            book_id=book.id,
            book_name=book.name,
            book_type=book.type.value,
            section_id=section_id,
            section_label=section.label,
            subject_id=book.subject_id,
            subject_name=book.subject.name,
            topic_name=section.topic.name if section.topic else None,
            planned_count=typical,
            remaining=ctx.remaining,
            confidence=confidence,
            score=score,
            reasons=reasons,
            curriculum_rank=rank,
            features={k: round(v, 3) for k, v in feats.items()},
        ))

    suggestions.sort(key=lambda s: (
        -s.score,
        s.curriculum_rank if s.curriculum_rank is not None else 999,
        -s.confidence,
        s.subject_name,
        s.book_name,
    ))
    if not select:
        return suggestions

    typical_n = max_suggestions or model.typical_items_per_day.get(dow, 0) or 5
    if phase_capacity_mult != 1.0:
        typical_n = int(round(typical_n * phase_capacity_mult))
    typical_n = max(3, min(15, typical_n))
    typical_distinct_subjects = model.typical_subjects_per_day.get(dow, 0) or 3
    typical_distinct_subjects = max(2, min(6, typical_distinct_subjects))
    max_per_subject = max(1, typical_n // max(1, typical_distinct_subjects))

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
            if len(selected) >= typical_n:
                break
    return selected


def suggest_for_date(
    db: Session,
    student_id: int,
    target_date: date,
    *,
    model: StudentModel | None = None,
    exclude_keys: Iterable[tuple[int, int]] = (),
    today: date | None = None,
    max_suggestions: int | None = None,
    weights: dict[str, float] | None = None,
    cache: dict | None = None,
) -> list[Suggestion]:
    """Bir gün için öneri listesi üret (veriyi yükler, `rank_candidates`'a verir).

    `cache`: aynı istekte birden çok gün hesaplanıyorsa (haftalık görünüm 7 gün)
    çağıran boş bir dict verir; öğrenci verisi bir kez yüklenip paylaşılır.

    Phase-aware (Faz 6.4): öğrencinin academic_year'ında target_date'i kapsayan
    dönem varsa capacity_multiplier ile günlük öneri hacmi ölçeklenir.
    """
    from app.models import User as _UserModel
    from app.services import rec_signals

    if today is None:
        today = date.today()
    if model is None:
        model = build_student_model(db, student_id, today=today)

    student = db.get(_UserModel, student_id)
    phase_capacity_mult = 1.0
    try:
        if student and student.academic_year:
            active_phase = student.academic_year.active_phase_on(target_date)
            if active_phase:
                phase_capacity_mult = active_phase.capacity_multiplier
    except Exception:
        phase_capacity_mult = 1.0

    c = cache if cache is not None else {}
    if "universe" not in c:
        universe = _section_universe(db, student_id)
        if student is not None:
            allowed_sections = _allowed_exam_sections(student)
            if allowed_sections is not None:
                universe = {
                    sid: ctx for sid, ctx in universe.items()
                    if ctx.book.subject.exam_section in allowed_sections
                }
        c["universe"] = universe
        c["items"] = rec_signals.load_test_items(db, student_id)
        c["exam"] = rec_signals.load_exam_rows(db, student_id)
        c["open_wrong"] = rec_signals.load_open_wrong(db, student_id)
        c["review"] = rec_signals.load_review(db, student_id)
        if student is not None:
            from app.services.rec_learning import weights_for_coach
            c["weights"] = weights_for_coach(db, student.teacher_id)
        else:
            c["weights"] = None
    universe = c["universe"]

    # "Verildi" sinyalleri hedef güne kadar planlananı görür; "yapıldı mı"
    # sinyalleri yalnız bugünden önceki günleri (sonucu belli olanları)
    signals = rec_signals.build_signals(
        c["items"],
        target_date,
        outcome_before=today,
        exam_rows=c["exam"],
        open_wrong=c["open_wrong"],
        review=c["review"],
    )
    if weights is None:
        # Koç başına öğrenilmiş ağırlık (gece işi); yoksa DEFAULT_WEIGHTS
        weights = c["weights"]
    return rank_candidates(
        universe=universe,
        model=model,
        signals=signals,
        target_date=target_date,
        today=today,
        weights=weights,
        exclude_set=set(exclude_keys),
        phase_capacity_mult=phase_capacity_mult,
        max_suggestions=max_suggestions,
    )


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
