"""Öneri sinyalleri — öneri motorlarının ORTAK veri katmanı (2026-11-08).

Günlük "Öneriler" şeridi (suggestions.py) her adayı bir ÖZELLİK VEKTÖRÜ ile
skorlar. Bu modül o özelliklerin ham kanıtını tek yerde toplar ve her birine
sayılı, sade Türkçe bir gerekçe üretir ("geçen hafta 3 test verilip yapılmadı").

Tasarım kuralları:
  - Zaman yolculuğu: tüm sinyaller `as_of` gününe göre, YALNIZ o günden önceki
    veriden hesaplanır → aynı kod hem canlıda hem geçmişi yeniden oynatan
    ölçüm betiğinde (backtest) çalışır; iki ayrı mantık tutarsızlaşamaz.
  - Deneme ≠ test: deneme kitapları ve kitapsız deneme kalemleri sinyallere
    girmez (gorev_stats.is_test_book).
  - Taslak (yayınlanmamış) görev "yapılmadı" sayılmaz.

Özellikler (0..1) ve anlamları:
  thread         son 7 günde verilen bölüm, kalan kapasitesi var (koçun iplik devamı)
  thread_next    son 7 günde biten bölümün kitapta sıradaki bölümü
  book_next      kitabın sırasıyla ilk açık bölümü (koç kitabı baştan sona yürür)
  neglect        son 21 günde verilip yapılmayan test (bölüm düzeyi)
  subject_neglect  dersin son 21 gündeki yapılmama oranı yüksek
  struggle       son 10 günde görevde düşük doğruluk (konu)
  subject_gap    ders 7+ gündür programda yok (kaynağı açık)
  coverage_lag   dersin kaynak ilerlemesi diğer derslerin ortalamasının belirgin altında
  exam_weak      son 90 günün denemelerinde yanlış biriken konu
  open_wrong     Yanlış Soru Arşivinde açık yanlış biriken konu
  review         tekrar kartında zorlanılan konu
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import Book, Task, TaskBookItem


NEGLECT_WINDOW_DAYS = 21
STRUGGLE_WINDOW_DAYS = 10
THREAD_WINDOW_DAYS = 7
SUBJECT_GAP_DAYS = 7
EXAM_WINDOW_DAYS = 90

STRUGGLE_MIN_ANSWERED = 6
STRUGGLE_ACC_LIMIT = 0.60
SUBJECT_NEGLECT_MIN_PLANNED = 4
SUBJECT_NEGLECT_MIN_RATIO = 0.30
COVERAGE_LAG_MIN = 0.15
EXAM_WEAK_MIN_WRONG = 2


FEATURE_LABELS_TR = {
    "curriculum": "Müfredat sırası",
    "pattern": "Koçun gün alışkanlığı",
    "started": "Başlanan konu",
    "thread": "Son günlerin devamı",
    "thread_next": "Sıradaki bölüm",
    "book_next": "Kitapta sıradaki bölüm",
    "neglect": "Yapılmayan görev",
    "subject_neglect": "Aksayan ders",
    "struggle": "Geçen hafta zorlandığı konu",
    "subject_gap": "Uzun süredir verilmeyen ders",
    "coverage_lag": "Kaynakta geride kalan ders",
    "exam_weak": "Denemede yanlış",
    "open_wrong": "Açık yanlış",
    "review": "Tekrarda zorlanma",
    "staleness": "Uzun süredir dokunulmadı",
}

FEATURE_KEYS = tuple(FEATURE_LABELS_TR.keys())


@dataclass
class ItemRec:
    """Test kalemi — sinyal hesabının tek girdi birimi."""

    date: date
    task_id: int
    is_draft: bool
    task_done: bool
    book_id: int
    section_id: int
    subject_id: int
    topic_id: int | None
    planned: int
    completed: int
    correct: int | None
    wrong: int | None


@dataclass
class SignalBundle:
    as_of: date
    # bölüm → son 21 günde verilip yapılmayan test adedi
    section_undone: dict[int, int] = field(default_factory=dict)
    # ders → (yapılmayan, verilen) son 21 gün
    subject_neglect: dict[int, tuple[int, int]] = field(default_factory=dict)
    # bölüm → (son verildiği gün, son 7 günde kaç kez verildi)
    recent_sections: dict[int, tuple[date, int]] = field(default_factory=dict)
    # konu → (doğru, yanlış) son 10 gün görev sonuçları
    topic_recent: dict[int, tuple[int, int]] = field(default_factory=dict)
    # ders → programa en son konduğu gün
    subject_last_given: dict[int, date] = field(default_factory=dict)
    # konu → (yanlış, cevaplanan) son 90 gün denemeler
    exam_topic: dict[int, tuple[int, int]] = field(default_factory=dict)
    # konu → açık yanlış adedi
    open_wrong: dict[int, int] = field(default_factory=dict)
    # konu → 0..1 tekrar kartı zorlanması
    review: dict[int, float] = field(default_factory=dict)


# ----------------------------------------------------------------- yükleme


def load_test_items(db: Session, student_id: int) -> list[ItemRec]:
    """Öğrencinin tüm KİTAPLI test kalemleri (deneme kitapları hariç)."""
    from app.services.gorev_stats import is_test_book

    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
                 joinedload(Task.book_items).joinedload(TaskBookItem.section))
        .filter(Task.student_id == student_id)
        .all()
    )
    out: list[ItemRec] = []
    for t in tasks:
        done = getattr(t.status, "value", t.status) == "completed"
        for it in t.book_items:
            if it.book_id is None or it.book_section_id is None or not is_test_book(it.book):
                continue
            out.append(ItemRec(
                date=t.date, task_id=t.id, is_draft=bool(t.is_draft), task_done=done,
                book_id=it.book_id, section_id=it.book_section_id,
                subject_id=it.book.subject_id,
                topic_id=it.section.topic_id if it.section else None,
                planned=int(it.planned_count or 0), completed=int(it.completed_count or 0),
                correct=it.correct_count, wrong=it.wrong_count,
            ))
    out.sort(key=lambda r: (r.date, r.task_id))
    return out


def load_exam_rows(db: Session, student_id: int) -> list[tuple[date, int, str]]:
    """(deneme tarihi, konu, sonuç) — zaman yolculuğu için tarihli."""
    from app.models.exam_result import ExamResult, ExamResultQuestion

    return [
        (d, int(tid), res)
        for d, tid, res in db.query(ExamResult.exam_date, ExamResultQuestion.topic_id,
                                    ExamResultQuestion.result)
        .join(ExamResult, ExamResult.id == ExamResultQuestion.exam_result_id)
        .filter(ExamResult.student_id == student_id, ExamResultQuestion.topic_id.isnot(None))
    ]


def load_open_wrong(db: Session, student_id: int) -> dict[int, int]:
    try:
        from app.services.wrong_question_service import open_wrong_topic_map
        # harita 0..1 (3 = tam); adede geri çevir
        return {tid: max(1, round(v * 3)) for tid, v in open_wrong_topic_map(db, student_id).items()}
    except Exception:
        return {}


def load_review(db: Session, student_id: int) -> dict[int, float]:
    try:
        from app.services.review_scheduler import struggling_topic_ids_map
        return struggling_topic_ids_map(db, student_id=student_id, min_score=10.0)
    except Exception:
        return {}


# ----------------------------------------------------------------- hesap


def build_signals(
    items: list[ItemRec],
    as_of: date,
    *,
    exam_rows: list[tuple[date, int, str]] = (),
    open_wrong: dict[int, int] | None = None,
    review: dict[int, float] | None = None,
    outcome_before: date | None = None,
) -> SignalBundle:
    """`as_of` gününden ÖNCEKİ veriden sinyal demeti (saf fonksiyon).

    İki kesim: "verildi mi" sinyalleri (iplik, ders boşluğu) `as_of`'a kadarki
    PLANLANMIŞ kalemleri görür — koç bu günü planlarken önceki günleri zaten
    planlamıştır. "Yapıldı mı / doğru mu" sinyalleri (yapılmayan görev, zorlanma)
    yalnız `outcome_before`'dan önceki günleri görür: sonucu henüz belli olmayan
    gün (bugün ve ileri) "yapılmadı" sayılmaz. Varsayılan outcome_before = as_of.
    """
    outcome_before = min(outcome_before or as_of, as_of)
    from app.models.exam_result import EQ_RESULT_DOGRU, EQ_RESULT_YANLIS

    b = SignalBundle(as_of=as_of, open_wrong=dict(open_wrong or {}), review=dict(review or {}))
    neg_from = as_of - timedelta(days=NEGLECT_WINDOW_DAYS)
    str_from = as_of - timedelta(days=STRUGGLE_WINDOW_DAYS)
    thr_from = as_of - timedelta(days=THREAD_WINDOW_DAYS)

    s_undone: dict[int, int] = defaultdict(int)
    subj_undone: dict[int, int] = defaultdict(int)
    subj_planned: dict[int, int] = defaultdict(int)
    t_c: dict[int, int] = defaultdict(int)
    t_w: dict[int, int] = defaultdict(int)
    for r in items:
        if r.date >= as_of:
            break  # sıralı liste
        if r.is_draft:
            continue
        prev = b.subject_last_given.get(r.subject_id)
        if prev is None or r.date > prev:
            b.subject_last_given[r.subject_id] = r.date
        if r.date >= thr_from:
            last, n = b.recent_sections.get(r.section_id, (r.date, 0))
            b.recent_sections[r.section_id] = (max(last, r.date), n + 1)
        if neg_from <= r.date < outcome_before:
            undone = max(0, r.planned - r.completed)
            subj_planned[r.subject_id] += r.planned
            if undone:
                s_undone[r.section_id] += undone
                subj_undone[r.subject_id] += undone
        if str_from <= r.date < outcome_before and r.topic_id and (r.correct or r.wrong):
            t_c[r.topic_id] += int(r.correct or 0)
            t_w[r.topic_id] += int(r.wrong or 0)

    b.section_undone = dict(s_undone)
    b.subject_neglect = {s: (subj_undone.get(s, 0), p) for s, p in subj_planned.items()}
    b.topic_recent = {t: (t_c[t], t_w[t]) for t in set(t_c) | set(t_w)}

    ex_from = as_of - timedelta(days=EXAM_WINDOW_DAYS)
    ew: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for d, tid, res in exam_rows:
        if not (ex_from <= d < as_of):
            continue
        if res == EQ_RESULT_YANLIS:
            ew[tid][0] += 1
            ew[tid][1] += 1
        elif res == EQ_RESULT_DOGRU:
            ew[tid][1] += 1
    b.exam_topic = {t: (w, n) for t, (w, n) in ew.items()}
    return b


# ----------------------------------------------------------------- özellikler


def subject_coverage_lag(universe_rows) -> dict[int, tuple[float, float]]:
    """ders → (dersin kaynak ilerlemesi, diğer derslerin ortalaması).

    universe_rows: (subject_id, total, used) — used = çözülen + rezerv.
    """
    tot: dict[int, int] = defaultdict(int)
    use: dict[int, int] = defaultdict(int)
    for sid, total, used in universe_rows:
        tot[sid] += total
        use[sid] += used
    cov = {s: use[s] / tot[s] for s in tot if tot[s] > 0}
    out: dict[int, tuple[float, float]] = {}
    for s, c in cov.items():
        others = [v for k, v in cov.items() if k != s]
        if len(others) >= 2:
            out[s] = (c, sum(others) / len(others))
    return out


def section_features(
    b: SignalBundle,
    *,
    section_id: int,
    subject_id: int,
    topic_id: int | None,
    prev_section_id: int | None,
    remaining: int,
    prev_finished: bool = True,
    coverage: tuple[float, float] | None,
) -> tuple[dict[str, float], dict[str, str]]:
    """Bir aday bölümün sinyal özellikleri (0..1) + sayılı gerekçe metinleri.

    Müfredat/desen/eskime gibi motorun kendi hesapladığı özellikler burada YOK —
    onlar suggestions.py'de eklenir; bu fonksiyon yeni sinyalleri üretir.
    """
    f: dict[str, float] = {}
    why: dict[str, str] = {}
    as_of = b.as_of

    rs = b.recent_sections.get(section_id)
    if rs and remaining > 0:
        days = (as_of - rs[0]).days
        f["thread"] = max(0.3, 1.0 - 0.12 * max(0, days - 1))
        why["thread"] = "dün verildi" if days <= 1 else f"{days} gün önce verildi, devamı"
    elif (prev_finished and prev_section_id is not None
          and prev_section_id in b.recent_sections and remaining > 0):
        days = (as_of - b.recent_sections[prev_section_id][0]).days
        f["thread_next"] = max(0.3, 0.8 - 0.1 * max(0, days - 1))
        why["thread_next"] = "son verilen bölümün ardından gelen bölüm"

    undone = b.section_undone.get(section_id, 0)
    if undone > 0 and remaining > 0:
        f["neglect"] = min(1.0, undone / 4)
        why["neglect"] = f"son 3 haftada {undone} test verilip yapılmadı"

    sn = b.subject_neglect.get(subject_id)
    if sn and sn[1] >= SUBJECT_NEGLECT_MIN_PLANNED and sn[0] / sn[1] >= SUBJECT_NEGLECT_MIN_RATIO:
        ratio = sn[0] / sn[1]
        f["subject_neglect"] = min(1.0, ratio)
        why["subject_neglect"] = f"bu derste son 3 haftada {sn[1]} testin {sn[0]}'i yapılmadı"

    if topic_id is not None:
        tr = b.topic_recent.get(topic_id)
        if tr:
            c, w = tr
            n = c + w
            if n >= STRUGGLE_MIN_ANSWERED and c / n < STRUGGLE_ACC_LIMIT:
                acc = c / n
                f["struggle"] = min(1.0, (STRUGGLE_ACC_LIMIT - acc) / STRUGGLE_ACC_LIMIT + 0.4)
                why["struggle"] = f"son günlerde bu konuda %{round(acc * 100)} doğru ({c}D {w}Y)"
        ex = b.exam_topic.get(topic_id)
        if ex and ex[0] >= EXAM_WEAK_MIN_WRONG and (ex[1] == 0 or (ex[1] - ex[0]) / ex[1] < 0.6):
            f["exam_weak"] = min(1.0, ex[0] / 4)
            why["exam_weak"] = f"denemelerde {ex[0]} yanlış"
        ow = b.open_wrong.get(topic_id, 0)
        if ow:
            f["open_wrong"] = min(1.0, ow / 3)
            why["open_wrong"] = f"arşivde {ow} açık yanlış"
        rv = b.review.get(topic_id, 0.0)
        if rv > 0:
            f["review"] = min(1.0, rv)
            why["review"] = "tekrar kartında zorlanıyor"

    last = b.subject_last_given.get(subject_id)
    if last is not None:
        gap = (as_of - last).days
        if gap >= SUBJECT_GAP_DAYS:
            f["subject_gap"] = min(1.0, 0.4 + (gap - SUBJECT_GAP_DAYS) / 14)
            why["subject_gap"] = f"bu ders {gap} gündür programda yok"

    if coverage is not None:
        own, avg = coverage
        if avg - own >= COVERAGE_LAG_MIN:
            f["coverage_lag"] = min(1.0, (avg - own) / 0.4)
            why["coverage_lag"] = (
                f"bu dersin kaynaklarının %{round(own * 100)}'i işlendi, "
                f"diğer derslerde ortalama %{round(avg * 100)}"
            )
    return f, why
