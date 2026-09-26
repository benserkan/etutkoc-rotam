# -*- coding: utf-8 -*-
"""Haftalık İskelet — Adım 0 / İPLİK MODELİ ölçümü (SALT OKUMA, hiçbir şey yazmaz).

İplik = bir derste son 7 günde üzerinde çalışılan bölüm. Her iplik kendi
kitabında ilerler: bölümde test kaldıysa aynı bölüm, bittiyse kitabın sıradaki
KONULU bölümü (dolu/kapatılmış olanlar atlanır).

İki senaryo ölçülür:
  ANLIK     — çip, koç hücreye tıkladığı an hesaplanır (o ana kadarki her şey bilinir)
  HAFTA BAŞI — tüm hafta program açılırken bir kerede doldurulur; durum hafta başında
               DONAR. Her iplik iki çip verir: şimdiki bölüm + ardından gelen bölüm
               (hafta içinde konu bitip sıradakine geçilebilsin diye).
Çipler son kullanım sırasına dizilir → ilk 1 / ilk 2 / ilk 3 / tümü isabeti.
Kaçanlar için "yeni iplik" yedeği: dersin kitaplarından birinde sıradaki
başlanmamış konu bölümü mü? (koça "yeni konu aç" çipi olarak sunulabilir)
Test sayısı: ipliğin son adedi vs dersteki en sık adet.

    python -m scripts.backtest_threads [--student N] [--weeks 16]
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
from app.models import Book, BookSection, BookType, Subject, Task, User  # noqa: E402
from app.models.topic_closure import TopicClosure  # noqa: E402
from app.services.gorev_stats import is_test_book  # noqa: E402

WINDOW_DAYS = 7


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def pct(a, b) -> str:
    return "  —" if not b else f"%{100 * a / b:3.0f}"


class Ctx:
    def __init__(self, book_sections, closures):
        self.book_sections = book_sections
        self.closures = closures

    def open_(self, sec, consumed, d) -> bool:
        if int(sec.test_count or 0) - consumed[sec.id] <= 0:
            return False
        ca = self.closures.get(sec.topic_id) if sec.topic_id else None
        return not (ca and ca.date() <= d)

    def advance(self, sec, consumed, d, skip_current=False):
        """Bölümde test kaldıysa kendisi; yoksa kitaptaki sıradaki açık konulu bölüm."""
        if not skip_current and self.open_(sec, consumed, d):
            return sec
        for c in self.book_sections.get(sec.book_id, []):
            if c.order > sec.order and c.topic_id and self.open_(c, consumed, d):
                return c
        return None


def match(cand, sec) -> bool:
    return cand.id == sec.id or bool(cand.topic_id and cand.topic_id == sec.topic_id)


def rank_of(cands, sec):
    for i, c in enumerate(cands):
        if match(c, sec):
            return i
    return None


def analyse(sid, tasks, books, sections, ctx: Ctx):
    items = []
    for t in tasks:
        for it in t.book_items:
            if not it.book_id or not it.book_section_id:
                continue
            bk, sec = books.get(it.book_id), sections.get(it.book_section_id)
            if bk is None or sec is None or not is_test_book(bk):
                continue
            items.append((t.date, t.id, it.id, bk.subject_id, bk.id, sec, int(it.planned_count or 0)))
    items.sort(key=lambda r: (r[0], r[1], r[2]))
    if not items:
        return None
    first_week = monday(items[0][0])

    r = Counter()
    subj_r: dict[int, Counter] = defaultdict(Counter)
    consumed = Counter()
    recent: dict[int, list] = defaultdict(list)       # subj -> [(date, sec)] en eski → en yeni
    subj_books: dict[int, set] = defaultdict(set)
    counts_hist: dict[int, list] = defaultdict(list)
    thread_last_count: dict[int, int] = {}          # section_id -> son verilen adet
    # hafta başı dondurulmuş durum
    frozen: dict[date, dict] = {}

    def threads(subj, d, cons):
        live = [(dd, ss) for dd, ss in recent[subj] if (d - dd).days <= WINDOW_DAYS]
        live.sort(key=lambda x: x[0], reverse=True)   # en son kullanılan önde
        return live

    for d, _tid, _iid, subj, bid, sec, planned in items:
        wk = monday(d)
        if wk not in frozen:
            snap_cons = Counter(consumed)
            snap = {}
            for s_, lst in recent.items():
                live = [(dd, ss) for dd, ss in lst if (wk - dd).days <= WINDOW_DAYS]
                live.sort(key=lambda x: x[0], reverse=True)
                chips = []
                for _dd, ss in live:
                    cur = ctx.advance(ss, snap_cons, wk)
                    if cur is None:
                        continue
                    nxt = ctx.advance(cur, snap_cons, wk, skip_current=True)
                    for c in (cur, nxt):
                        if c is not None and all(c.id != x.id for x in chips):
                            chips.append(c)
                snap[s_] = chips
            frozen[wk] = snap

        if wk > first_week:
            r["n"] += 1
            sr = subj_r[subj]
            sr["n"] += 1
            # ANLIK
            chips = []
            for _dd, ss in threads(subj, d, consumed):
                c = ctx.advance(ss, consumed, d)
                if c is not None and all(c.id != x.id for x in chips):
                    chips.append(c)
            rk = rank_of(chips, sec)
            r["a_size"] += len(chips)
            if chips:
                r["a_has"] += 1
            if rk is not None:
                for k in (1, 2, 3):
                    if rk < k:
                        r[f"a_top{k}"] += 1
                        sr[f"a_top{k}"] += 1
                r["a_all"] += 1
                sr["a_all"] += 1
            # HAFTA BAŞI
            fchips = frozen[wk].get(subj, [])
            frk = rank_of(fchips, sec)
            r["w_size"] += len(fchips)
            if frk is not None:
                r["w_all"] += 1
                sr["w_all"] += 1
                for k in (2, 4):
                    if frk < k:
                        r[f"w_top{k}"] += 1
            # yeni iplik yedeği (her iki senaryoda da kaçan kalem)
            if rk is None:
                starts = []
                for b_ in subj_books[subj]:
                    for c in ctx.book_sections.get(b_, []):
                        if c.topic_id and consumed[c.id] == 0 and ctx.open_(c, consumed, d):
                            starts.append(c)
                            break
                if any(match(c, sec) for c in starts):
                    r["new_thread"] += 1
                    sr["new_thread"] += 1
                elif consumed[sec.id] == 0:
                    r["miss_fresh"] += 1   # hiç başlanmamış ama kitap sırasında değil
                else:
                    r["miss_old"] += 1     # eski (7 günden önce) bir bölüme dönüş
            # test sayısı
            hist = counts_hist[subj][-20:]
            mode = Counter(hist).most_common(1)[0][0] if len(hist) >= 3 else 3
            guess = thread_last_count.get(sec.id, mode)
            r["cnt_n"] += 1
            r["cnt_mode"] += int(mode == planned)
            r["cnt_thread"] += int(guess == planned)
            r["cnt_thread_pm1"] += int(abs(guess - planned) <= 1)

        consumed[sec.id] += planned
        subj_books[subj].add(bid)
        counts_hist[subj].append(planned)
        thread_last_count[sec.id] = planned
        recent[subj] = [(dd, ss) for dd, ss in recent[subj] if ss.id != sec.id] + [(d, sec)]
    return r, subj_r, len(items)


def report(title, r, subj_r=None, names=None):
    n = r["n"]
    print(f"\n=== {title} — değerlendirilen test görevi: {n} ===")
    print("  ANLIK (koç hücreye tıkladığı an çip hesaplanır)")
    print(f"    doğru konu 1. çipte {pct(r['a_top1'], n)} · ilk 2 çipte {pct(r['a_top2'], n)} · "
          f"ilk 3 çipte {pct(r['a_top3'], n)} · tüm çiplerde {pct(r['a_all'], n)}  "
          f"(ort. {r['a_size'] / n if n else 0:.1f} çip)")
    print("  HAFTA BAŞI (hafta bir kerede doldurulur, her iplik şimdiki + sıradaki bölüm)")
    print(f"    doğru konu çiplerde {pct(r['w_all'], n)} · ilk 2 çipte {pct(r['w_top2'], n)} · "
          f"ilk 4 çipte {pct(r['w_top4'], n)}  (ort. {r['w_size'] / n if n else 0:.1f} çip)")
    miss = n - r["a_all"]
    print(f"  ÇİPTE OLMAYAN {miss} görevin nedeni: kitapta sıradaki yeni konu (\"yeni konu aç\" "
          f"çipi yakalar) {r['new_thread']} · kitap sırası dışı yeni konu {r['miss_fresh']} · "
          f"7 günden eski konuya dönüş {r['miss_old']}")
    print(f"    → iplik + \"yeni konu aç\" çipi birlikte: {pct(r['a_all'] + r['new_thread'], n)}")
    print(f"  TEST SAYISI: ipliğin son adedi birebir {pct(r['cnt_thread'], r['cnt_n'])} "
          f"(±1 {pct(r['cnt_thread_pm1'], r['cnt_n'])}) · dersin en sık adedi {pct(r['cnt_mode'], r['cnt_n'])}")
    if subj_r:
        print("  Ders kırılımı: görev · 1. çip · tüm çipler (anlık) · hafta başı · +yeni konu çipi")
        for subj, c in sorted(subj_r.items(), key=lambda kv: -kv[1]["n"]):
            if c["n"] < 3:
                continue
            print(f"    {names.get(subj, subj)[:30]:30s} {c['n']:4d} · {pct(c['a_top1'], c['n'])} · "
                  f"{pct(c['a_all'], c['n'])} · {pct(c['w_all'], c['n'])} · "
                  f"{pct(c['a_all'] + c['new_thread'], c['n'])}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int, action="append")
    ap.add_argument("--weeks", type=int, default=16)
    ap.add_argument("--min-items", type=int, default=40)
    args = ap.parse_args()
    since = monday(date.today()) - timedelta(days=7 * args.weeks)
    with SessionLocal() as db:
        q = db.query(Task).options(joinedload(Task.book_items)).filter(
            Task.is_draft.is_(False), Task.date >= since)
        if args.student:
            q = q.filter(Task.student_id.in_(args.student))
        tasks = q.all()
        by_student = defaultdict(list)
        for t in tasks:
            by_student[t.student_id].append(t)
        book_ids = {it.book_id for t in tasks for it in t.book_items if it.book_id}
        books = {b.id: b for b in db.query(Book).filter(
            Book.id.in_(book_ids), Book.type.in_(list(BookType))).all()} if book_ids else {}
        secs = db.query(BookSection).filter(BookSection.book_id.in_(book_ids)).all() if book_ids else []
        sections = {s.id: s for s in secs}
        book_sections = defaultdict(list)
        for s in secs:
            book_sections[s.book_id].append(s)
        for lst in book_sections.values():
            lst.sort(key=lambda s: (s.order, s.id))
        names = {s.id: s.name for s in db.query(Subject).all()}
        closures = defaultdict(dict)
        for c in db.query(TopicClosure).all():
            closures[c.student_id][c.topic_id] = c.closed_at

        tot = Counter()
        tot_subj: dict[str, Counter] = defaultdict(Counter)
        k = 0
        for sid, ts in sorted(by_student.items()):
            if not args.student and sum(len(t.book_items) for t in ts) < args.min_items:
                continue
            res = analyse(sid, ts, books, sections, Ctx(book_sections, closures[sid]))
            if not res or not res[0]["n"]:
                continue
            r, subj_r, n_items = res
            k += 1
            tot.update(r)
            for s_, c in subj_r.items():
                tot_subj[s_].update(c)
            u = db.get(User, sid)
            report(f"{u.full_name} (#{sid}) · {n_items} test görevi", r, subj_r, names)
        if k > 1:
            report(f"TOPLAM — {k} öğrenci, son {args.weeks} hafta", tot, tot_subj, names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
