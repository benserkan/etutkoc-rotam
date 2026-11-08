"""Öneri motoru — geçmişi yeniden oynatarak ölçme ve koç başına öğrenme.

Tek merkez: ölçüm betiği (`scripts/backtest_suggestions.py`) ve gece işi
(`rec_weights_train`) bu modülü kullanır; canlı sıralayıcı `suggestions.
rank_candidates` ile aynı koddur.

Öğrenme sinyali: koçun her gün GERÇEKTE verdiği bölümler. Kabul/ret düğmesi
seyrek basılır; görev yazımı ise her gün olur → koçun tercihi en zengin buradan
okunur. Ret kayıtları ayrıca sıralayıcıda ceza olarak kalır.

Zaman yolculuğu kuralları (geleceği görmemek):
  - planlama günü P = o günün görevlerinin en erken oluşturulma günü
  - kitap kapasitesi: P'den önce sonucu belli kalemlerde ÇÖZÜLEN, P..gün arası
    kalemlerde PLANLANAN tutulur (sayaç mantığı: yapılmayanın rezervi serbest)
  - "verildi" sinyalleri gün öncesine kadar, "yapıldı / doğru mu" sinyalleri P öncesi
"""
from __future__ import annotations

import json
import logging
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Book, BookSection, BookType, SectionProgress, StudentBook, Task, TaskBookItem, User
from app.models.rec_weights import (
    REC_STATUS_DEFAULT,
    REC_STATUS_INSUFFICIENT,
    REC_STATUS_LEARNED,
    CoachRecWeights,
)
from app.services import rec_signals as rs

logger = logging.getLogger(__name__)

TRAIN_WEEKS = 12
MIN_ITEMS = 80          # koç başına öğrenmeye yetecek test kalemi
MIN_DAYS = 6            # öğrenci başına değerlendirilecek en az gün
HOLDOUT = 0.30          # son %30 gün ölçüme ayrılır
ACCEPT_GAIN = 1.03      # öğrenilen hedef varsayılanı en az %3 geçmeli
KS = (1, 3, 5, 10)


@dataclass
class Case:
    day: date
    universe: dict
    model: object
    signals: rs.SignalBundle
    truth: set[int]


class StudentReplay:
    """Bir öğrencinin geçmişini gün gün yeniden kurar (salt okuma)."""

    def __init__(self, db: Session, user: User, since: date, until: date | None = None):
        from app.services import suggestions as sg
        from app.services.gorev_stats import is_test_book

        until = until or date.today()
        self.user = user
        self.tasks = (
            db.query(Task)
            .options(joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
                     joinedload(Task.book_items).joinedload(TaskBookItem.section))
            .filter(Task.student_id == user.id)
            .all()
        )
        book_ids = {it.book_id for t in self.tasks for it in t.book_items if it.book_id}
        book_ids |= {b for (b,) in db.query(StudentBook.book_id).filter(StudentBook.student_id == user.id)}
        books = {
            b.id: b for b in db.query(Book).options(joinedload(Book.subject))
            .filter(Book.id.in_(book_ids or {0}), Book.type.in_(list(BookType)))
            if is_test_book(b)
        }
        allowed = sg._allowed_exam_sections(user)
        if allowed is not None:
            books = {k: b for k, b in books.items() if b.subject.exam_section in allowed}
        self.books = books
        self.sections = {
            s.id: s for s in db.query(BookSection).options(joinedload(BookSection.topic))
            .filter(BookSection.book_id.in_(books or {0}))
        }
        item_done = Counter()
        for t in self.tasks:
            for it in t.book_items:
                if it.book_section_id:
                    item_done[it.book_section_id] += int(it.completed_count or 0)
        self.baseline = Counter()
        for sec_id, comp in (
            db.query(SectionProgress.book_section_id, SectionProgress.completed_count)
            .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
            .filter(StudentBook.student_id == user.id)
        ):
            self.baseline[sec_id] = max(0, int(comp or 0) - item_done[sec_id])
        self.items = rs.load_test_items(db, user.id)
        self.exam_rows = rs.load_exam_rows(db, user.id)
        days: dict[date, set[int]] = defaultdict(set)
        created: dict[date, date] = {}
        for t in self.tasks:
            if t.date < since or t.date > until:
                continue
            for it in t.book_items:
                if it.book_section_id in self.sections:
                    days[t.date].add(it.book_section_id)
                    c = t.created_at.date() if t.created_at else t.date
                    created[t.date] = min(created.get(t.date, c), c)
        self.days = dict(days)
        self.created = created

    def case_at(self, d: date) -> Case:
        from app.services import suggestions as sg

        plan_day = min(self.created.get(d, d), d)
        consumed = Counter()
        for r in self.items:
            if r.date >= d:
                break
            consumed[r.section_id] += r.completed if r.date < plan_day else r.planned
        universe = {}
        for s in self.sections.values():
            universe[s.id] = sg._SectionCtx(
                section=s, book=self.books[s.book_id],
                completed=consumed[s.id] + self.baseline[s.id], reserved=0)
        model = sg.model_from_tasks(self.user.id, [t for t in self.tasks if t.date < d])
        signals = rs.build_signals(self.items, d, exam_rows=self.exam_rows, outcome_before=plan_day)
        return Case(d, universe, model, signals, self.days[d])

    def cases(self) -> list[Case]:
        return [self.case_at(d) for d in sorted(self.days)]


# ----------------------------------------------------------------- ölçüm


def evaluate(cases: list[Case], weights: dict[str, float]) -> Counter:
    """Gerçek sıralayıcıyla ölçüm: kaçıncı sırada, ekrandaki önerilerde mi."""
    from app.services import suggestions as sg

    r = Counter()
    for c in cases:
        kw = dict(universe=c.universe, model=c.model, signals=c.signals,
                  target_date=c.day, today=c.day, weights=weights)
        ranked = sg.rank_candidates(select=False, **kw)
        pos = {s.section_id: i for i, s in enumerate(ranked)}
        shown = {s.section_id for s in sg.rank_candidates(**kw)}
        for sec in c.truth:
            r["n"] += 1
            p = pos.get(sec)
            if p is not None:
                r["pool"] += 1
                for k in KS:
                    if p < k:
                        r[f"top{k}"] += 1
            if sec in shown:
                r["shown"] += 1
        r["days"] += 1
        r["shown_size"] += len(shown)
    return r


def _all_on() -> dict[str, float]:
    return {k: 1.0 for k in rs.FEATURE_KEYS}


def precompute(cases: list[Case]) -> list[tuple[list, int, int]]:
    """Her gün için aday özelliklerini BİR KEZ çıkar (ağırlıktan bağımsız geniş havuz)."""
    from app.services import suggestions as sg

    out = []
    for c in cases:
        ranked = sg.rank_candidates(universe=c.universe, model=c.model, signals=c.signals,
                                    target_date=c.day, today=c.day, weights=_all_on(), select=False)
        n_show = max(3, min(15, c.model.typical_items_per_day.get(c.day.weekday(), 0) or 5))
        out.append(([(s.section_id in c.truth, s.features) for s in ranked], len(c.truth), n_show))
    return out


def fast_scores(pre, w: dict[str, float]) -> Counter:
    r = Counter()
    for cands, n_truth, n_show in pre:
        r["n"] += n_truth
        scored = sorted(cands, key=lambda c: -sum(w.get(k, 0.0) * v for k, v in c[1].items()))
        for i, (is_t, _f) in enumerate(scored[:max(5, n_show)]):
            if is_t:
                r["top1"] += i < 1
                r["top3"] += i < 3
                r["top5"] += i < 5
                r["shown"] += i < n_show
    return r


def objective(r: Counter) -> float:
    return (r["top1"] + 0.6 * r["top3"] + 0.4 * r["top5"] + 0.3 * r["shown"]) / max(1, r["n"])


def fit(pre, start: dict[str, float], rounds: int = 4, seed: int = 7) -> dict[str, float]:
    """Koordinat araması: eğitim günlerinde hedefi büyüten ağırlıklar."""
    rnd = random.Random(seed)
    w = dict(start)
    best = objective(fast_scores(pre, w))
    keys = list(rs.FEATURE_KEYS)
    for _ in range(rounds):
        rnd.shuffle(keys)
        for k in keys:
            for mult in (0.0, 0.3, 0.6, 1.5, 2.5, 4.0):
                cand = dict(w)
                cand[k] = round(max(0.0, (w.get(k, 0.0) or 0.05) * mult), 3)
                sc = objective(fast_scores(pre, cand))
                if sc > best + 1e-6:
                    best, w = sc, cand
    return w


# ----------------------------------------------------------------- koç başına


def coach_cases(db: Session, coach_id: int, *, weeks: int = TRAIN_WEEKS) -> tuple[list[Case], int]:
    since = date.today() - timedelta(days=7 * weeks)
    students = (
        db.query(User)
        .filter(User.teacher_id == coach_id, User.is_active.is_(True))
        .all()
    )
    cases: list[Case] = []
    n_students = 0
    for u in students:
        rp = StudentReplay(db, u, since)
        if len(rp.days) < MIN_DAYS:
            continue
        n_students += 1
        cases.extend(rp.cases())
    cases.sort(key=lambda c: c.day)
    return cases, n_students


def assess_coach(db: Session, coach_id: int) -> dict:
    """Koçun ağırlığını öğren + ayrılmış son günlerde ölç (YAZMAZ)."""
    from app.services import suggestions as sg

    cases, n_students = coach_cases(db, coach_id)
    n_items = sum(len(c.truth) for c in cases)
    out = {"status": REC_STATUS_INSUFFICIENT, "weights": None, "n_items": n_items,
           "n_students": n_students, "shown_default": None, "shown_learned": None,
           "top3_default": None, "top3_learned": None}
    if n_items < MIN_ITEMS or len(cases) < 10:
        return out
    cut = int(len(cases) * (1 - HOLDOUT))
    learned = fit(precompute(cases[:cut]), sg.DEFAULT_WEIGHTS)
    pre_test = precompute(cases[cut:])
    r_def = fast_scores(pre_test, sg.DEFAULT_WEIGHTS)
    r_lrn = fast_scores(pre_test, learned)
    n = max(1, r_def["n"])
    out.update(
        shown_default=round(r_def["shown"] / n, 4), shown_learned=round(r_lrn["shown"] / n, 4),
        top3_default=round(r_def["top3"] / n, 4), top3_learned=round(r_lrn["top3"] / n, 4),
    )
    if objective(r_lrn) > 0 and objective(r_lrn) >= objective(r_def) * ACCEPT_GAIN:
        out["status"] = REC_STATUS_LEARNED
        out["weights"] = {k: v for k, v in learned.items() if v}
    else:
        out["status"] = REC_STATUS_DEFAULT
    return out


def train_coach(db: Session, coach_id: int) -> CoachRecWeights:
    """assess_coach sonucunu koç satırına yazar."""
    res = assess_coach(db, coach_id)
    row = db.query(CoachRecWeights).filter(CoachRecWeights.coach_id == coach_id).one_or_none()
    if row is None:
        row = CoachRecWeights(coach_id=coach_id)
        db.add(row)
    row.status = res["status"]
    row.weights_json = json.dumps(res["weights"], sort_keys=True) if res["weights"] else None
    for k in ("n_items", "n_students", "shown_default", "shown_learned", "top3_default", "top3_learned"):
        setattr(row, k, res[k])
    row.trained_at = datetime.now(timezone.utc)
    return row


def train_all(db: Session) -> dict:
    """Gece işi: öğrencisi olan tüm koçlar."""
    coach_ids = [
        cid for (cid,) in db.query(User.teacher_id)
        .filter(User.teacher_id.isnot(None), User.is_active.is_(True)).distinct()
    ]
    out = Counter()
    for cid in coach_ids:
        try:
            row = train_coach(db, cid)
            db.commit()
            out[row.status] += 1
        except Exception:
            db.rollback()
            logger.exception("rec_weights_train: koç %s öğrenilemedi", cid)
            out["error"] += 1
    return dict(out)


def weights_for_coach(db: Session, coach_id: int | None) -> dict[str, float] | None:
    """Öğrenilmiş ağırlık varsa döner; yoksa None (varsayılan kullanılır)."""
    if not coach_id:
        return None
    row = db.query(CoachRecWeights).filter(CoachRecWeights.coach_id == coach_id).one_or_none()
    if row is None or row.status != REC_STATUS_LEARNED or not row.weights_json:
        return None
    try:
        data = json.loads(row.weights_json)
        return {k: float(v) for k, v in data.items() if k in rs.FEATURE_KEYS}
    except Exception:
        return None
