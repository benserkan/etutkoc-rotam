# -*- coding: utf-8 -*-
"""Haftalık İskelet — F1c: backtest ÜRÜN KODUNA bağlı (SALT OKUMA).

`backtest_threads.py` iplik modelini kendi kopyasıyla ölçmüştü. Bu betik geçmişi
gün gün yeniden oynatır ve her test kaleminde, koç o hücreye tıkladığı an
ÜRÜNÜN GERÇEK `skeleton_suggest.build_chips` fonksiyonunun ne önereceğini
hesaplar. Böylece ölçüm = canlıda koçun gördüğü çipler (kod kayarsa rakam da
kayar; iki ayrı mantık tutarsızlaşamaz).

O anki durum geçmişten kurulur:
  - bölüm ilerlemesi = o ana kadar verilmiş test adedi (kitap kalan kapasitesi)
  - iplik geçmişi = son 7 gün (aynı gün önceki görevler dahil)
  - aynı gün aynı derse konmuş bölümler çip dışı (ürün kuralı)
  - kapatılmış konu = o tarihte kapatılmış olanlar
  - "tekrar" çipi = o tarihten önceki 90 günün denemelerindeki yanlışlar

Ölçülen: doğru konu 1. çipte / ilk 3'te / tüm çiplerde · çip türü kırılımı
(devam/sıradaki/yeni/tekrar) · kabul edilen çipte adet birebir.

    python -m scripts.backtest_skeleton_chips [--student N] [--weeks 16]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy.orm import joinedload  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Book, BookSection, BookType, StudentBook, Subject, Task, Topic, User  # noqa: E402
from app.models.exam_result import EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion  # noqa: E402
from app.models.topic_closure import TopicClosure  # noqa: E402
from app.services import skeleton_suggest as sk  # noqa: E402
from app.services.exam_topic_analysis import EXAM_WEAK_WINDOW_DAYS  # noqa: E402
from app.services.gorev_stats import is_test_book  # noqa: E402


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def pct(a, b) -> str:
    return "  —" if not b else f"%{100 * a / b:3.0f}"


def _matches(chip: dict, sec: BookSection) -> bool:
    return chip["section_id"] == sec.id or bool(
        sec.topic_id and chip.get("topic_id") == sec.topic_id
    )


class Replay:
    """Bir öğrencinin geçmişini zaman içinde oynatır."""

    def __init__(self, db, student: User, tasks: list[Task]):
        self.db = db
        self.student = student
        book_ids = {it.book_id for t in tasks for it in t.book_items if it.book_id}
        book_ids |= {
            b for (b,) in db.query(StudentBook.book_id).filter(StudentBook.student_id == student.id)
        }
        books = {
            b.id: b for b in db.query(Book).filter(
                Book.id.in_(book_ids or {0}), Book.type.in_(list(BookType))
            )
            if is_test_book(b)
        }
        self.books = books
        self.sections = {
            s.id: s for s in db.query(BookSection).filter(BookSection.book_id.in_(books or {0}))
        }
        self.topic_names = {
            int(i): n for i, n in db.query(Topic.id, Topic.name).filter(
                Topic.id.in_({s.topic_id for s in self.sections.values() if s.topic_id} or {0})
            )
        }
        self.subject_names = {int(i): n for i, n in db.query(Subject.id, Subject.name)}
        self.closures = {
            c.topic_id: c.closed_at.date() if hasattr(c.closed_at, "date") else c.closed_at
            for c in db.query(TopicClosure).filter(TopicClosure.student_id == student.id)
        }
        self.exam_wrongs = [
            (d, int(tid))
            for d, tid in db.query(ExamResult.exam_date, ExamResultQuestion.topic_id)
            .join(ExamResult, ExamResult.id == ExamResultQuestion.exam_result_id)
            .filter(
                ExamResult.student_id == student.id,
                ExamResultQuestion.topic_id.isnot(None),
                ExamResultQuestion.result == EQ_RESULT_YANLIS,
            )
        ]
        # zaman sıralı test kalemleri
        items = []
        for t in tasks:
            for it in t.book_items:
                if it.book_id in books and it.book_section_id in self.sections:
                    items.append((t.date, t.id, it.id, self.sections[it.book_section_id],
                                  int(it.planned_count or 0)))
        items.sort(key=lambda r: (r[0], r[1], r[2]))
        self.items = items
        self.qcache: dict[int, int] = {}

    def ctx_at(self, d: date, consumed: Counter, history, day_secs) -> sk._Ctx:
        secs: dict[int, sk._Sec] = {}
        for s in self.sections.values():
            b = self.books[s.book_id]
            secs[s.id] = sk._Sec(
                id=s.id, book_id=s.book_id, book_name=b.name, subject_id=b.subject_id,
                label=s.label or "", order=s.order or 0, topic_id=s.topic_id,
                total=int(s.test_count or 0), completed=int(consumed[s.id]), reserved=0,
            )
        by_book: dict[int, list] = defaultdict(list)
        books_by_subject: dict[int, list] = defaultdict(list)
        for s in secs.values():
            by_book[s.book_id].append(s)
        for bid, lst in by_book.items():
            lst.sort(key=lambda x: (x.order, x.id))
            books_by_subject[lst[0].subject_id].append(bid)
        cutoff = d - timedelta(days=EXAM_WEAK_WINDOW_DAYS)
        ew = Counter(tid for ed, tid in self.exam_wrongs if cutoff <= ed < d)
        ctx = sk._Ctx(
            student=self.student, coach_id=self.student.teacher_id or 0,
            secs=secs, by_book=dict(by_book), books_by_subject=dict(books_by_subject),
            closed={tid for tid, cd in self.closures.items() if cd and cd <= d},
            topic_names=self.topic_names, subject_names=self.subject_names,
            history=history, day_tasks={}, day_sections=day_secs,
            exam_wrong=dict(ew), open_wrong={}, forgotten=set(), perf={},
        )
        ctx.quantity_cache = self.qcache  # öğrenci başına tek sorgu
        return ctx

    def run(self) -> tuple[Counter, dict[int, Counter]]:
        r = Counter()
        subj_r: dict[int, Counter] = defaultdict(Counter)
        if not self.items:
            return r, subj_r
        first_week = monday(self.items[0][0])
        consumed = Counter()
        history: dict[int, list] = defaultdict(list)
        day_secs: dict[date, dict[int, set]] = defaultdict(lambda: defaultdict(set))
        for d, tid, _iid, sec, planned in self.items:
            subj = self.books[sec.book_id].subject_id
            if monday(d) > first_week:
                ctx = self.ctx_at(d, consumed, history, day_secs)
                chips = sk.build_chips(self.db, ctx, subject_id=subj, d=d)
                r["n"] += 1
                sr = subj_r[subj]
                sr["n"] += 1
                r["size"] += len(chips)
                hit = next((c for c in chips if _matches(c, sec)), None)
                if hit is not None:
                    rk = hit["rank"]
                    for k in (1, 2, 3):
                        if rk <= k:
                            r[f"top{k}"] += 1
                            sr[f"top{k}"] += 1
                    r["all"] += 1
                    sr["all"] += 1
                    r[f"kind_{hit['kind']}"] += 1
                    r["cnt_n"] += 1
                    r["cnt_exact"] += int(hit["count"] == planned)
                    r["cnt_pm1"] += int(abs(hit["count"] - planned) <= 1)
                elif consumed[sec.id] == 0:
                    r["miss_fresh"] += 1
                else:
                    r["miss_old"] += 1
            consumed[sec.id] += planned
            history[subj].append((d, tid, sec.id, planned))
            day_secs[d][subj].add(sec.id)
        return r, subj_r


def report(title: str, r: Counter, subj_r=None, names=None) -> None:
    n = r["n"]
    print(f"\n=== {title} — değerlendirilen test kalemi: {n} ===")
    print(f"  doğru konu 1. çipte {pct(r['top1'], n)} · ilk 2 {pct(r['top2'], n)} · "
          f"ilk 3 {pct(r['top3'], n)} · tüm çiplerde {pct(r['all'], n)}  "
          f"(ort. {r['size'] / n if n else 0:.1f} çip)")
    print(f"  isabet eden çip türü: devam {r['kind_thread']} · sıradaki {r['kind_next']} · "
          f"yeni konu {r['kind_new']} · tekrar {r['kind_weak']}")
    print(f"  kaçan: hiç başlanmamış (kitap sırası dışı) {r['miss_fresh']} · "
          f"daha önce çalışılmış konuya dönüş {r['miss_old']}")
    print(f"  adet (isabet eden çipte): birebir {pct(r['cnt_exact'], r['cnt_n'])} · "
          f"±1 {pct(r['cnt_pm1'], r['cnt_n'])}")
    if subj_r:
        print("  Ders: kalem · 1. çip · ilk 3 · tüm çipler")
        for s_, c in sorted(subj_r.items(), key=lambda kv: -kv[1]["n"]):
            if c["n"] < 5:
                continue
            print(f"    {str(names.get(s_, s_))[:32]:32s} {c['n']:4d} · {pct(c['top1'], c['n'])} · "
                  f"{pct(c['top3'], c['n'])} · {pct(c['all'], c['n'])}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int, action="append")
    ap.add_argument("--weeks", type=int, default=16)
    ap.add_argument("--min-items", type=int, default=40)
    ap.add_argument("--quiet", action="store_true", help="yalnız TOPLAM satırı")
    ap.add_argument("--new-chips", type=int, default=None,
                    help="deneme: ders başına 'yeni konu' çipi sayısı (ürün varsayılanını ezer)")
    args = ap.parse_args()
    if args.new_chips is not None:
        sk.NEW_TOPIC_CHIPS = args.new_chips
    since = monday(date.today()) - timedelta(days=7 * args.weeks)
    with SessionLocal() as db:
        q = db.query(Task).options(joinedload(Task.book_items)).filter(
            Task.is_draft.is_(False), Task.date >= since, Task.date <= date.today())
        if args.student:
            q = q.filter(Task.student_id.in_(args.student))
        by_student: dict[int, list] = defaultdict(list)
        for t in q.all():
            by_student[t.student_id].append(t)
        tot = Counter()
        k = 0
        for sid, ts in sorted(by_student.items()):
            if not args.student and sum(len(t.book_items) for t in ts) < args.min_items:
                continue
            u = db.get(User, sid)
            if u is None:
                continue
            rp = Replay(db, u, ts)
            r, subj_r = rp.run()
            if not r["n"]:
                continue
            k += 1
            tot.update(r)
            if not args.quiet:
                report(f"{u.full_name} (#{sid})", r, subj_r, rp.subject_names)
        if k:
            report(f"TOPLAM — {k} öğrenci, son {args.weeks} hafta (ÜRÜN build_chips, yeni konu çipi={sk.NEW_TOPIC_CHIPS})", tot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
