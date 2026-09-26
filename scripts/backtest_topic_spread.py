# -*- coding: utf-8 -*-
"""İskelet F2-3c — "konuyu yay" kuralı koçun gerçek yerleşimine ne kadar yakın? (SALT OKUMA)

Her KONU BÖLÜMÜ (öğrenci × konu; son 7 günde görülmemiş konu yeni başlar):
  · başlangıç günü d0 = konunun ilk görevi
  · gerçek yayılım = sonraki 13 gün içinde o konuya verilen görevlerin günleri + adetleri
  · öneri = aynı toplam adedi, gün başına koçun o konudaki en sık adediyle,
    d0+1'den itibaren KAPASİTESİ YETEN ilk günlere dağıt (ürün kuralı:
    boşluk = kapasite − o günün DİĞER testleri; konu o gün zaten varsa atla)
  · kapasite = hafta günü başına o öğrencinin test yüklerinin %90'lık dilimi
    (ürün varsayılanı; --cap ile median/p75/max/none karşılaştırılır)

Ölçülen: gerçek günlerin önerideki payı (kapsama) · önerinin gerçekteki payı
(isabet) · ±1 gün toleransla · önerinin ortalama kaç gün önde/geride kaldığı.
Çapa (dershane) payı canlıda henüz girilmediği için bu ölçümde YOK.

    python -m scripts.backtest_topic_spread --student 84 --student 164 [--weeks 10]
"""
from __future__ import annotations

import argparse
import statistics
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
from app.models import Book, BookSection, Task, User  # noqa: E402
from app.services.gorev_stats import is_test_book  # noqa: E402

HORIZON = 13
NEW_GAP = 7


def pct(a, b) -> str:
    return "  —" if not b else f"%{100 * a / b:3.0f}"


def _q(v, mode):
    v = sorted(v)
    if mode == "median":
        return statistics.median(v)
    if mode == "max":
        return v[-1]
    p = {"p75": 0.75, "p90": 0.9}[mode]
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def analyse(db, sid: int, weeks: int, cap_mode: str = "median") -> Counter:
    since = date.today() - timedelta(days=7 * weeks)
    tasks = (
        db.query(Task).options(joinedload(Task.book_items))
        .filter(Task.student_id == sid, Task.date >= since).all()
    )
    book_ids = {it.book_id for t in tasks for it in t.book_items if it.book_id}
    books = {b.id: b for b in db.query(Book).filter(Book.id.in_(book_ids or {0})) if is_test_book(b)}
    secs = {s.id: s for s in db.query(BookSection).filter(BookSection.book_id.in_(books or {0}))}
    # günlük toplam test + konu bazlı kalemler
    day_total: dict[date, int] = defaultdict(int)
    topic_days: dict[object, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    topic_counts: dict[object, Counter] = defaultdict(Counter)
    for t in tasks:
        for it in t.book_items:
            if it.book_id not in books or it.book_section_id not in secs:
                continue
            n = int(it.planned_count or 0)
            day_total[t.date] += n
            sec = secs[it.book_section_id]
            key = ("t", sec.topic_id) if sec.topic_id else ("s", sec.id)
            topic_days[key][t.date] += n
            topic_counts[key][n] += 1
    by_wd: dict[int, list[int]] = defaultdict(list)
    for d, n in day_total.items():
        if n > 0:
            by_wd[d.weekday()].append(n)
    cap = {wd: (_q(v, cap_mode) if cap_mode != "none" else None) for wd, v in by_wd.items()}

    r = Counter()
    for key, days in topic_days.items():
        ds = sorted(days)
        episodes = []
        for d in ds:
            if not episodes or (d - episodes[-1][-1]).days > NEW_GAP:
                episodes.append([d])
            else:
                episodes[-1].append(d)
        for ep in episodes:
            d0 = ep[0]
            follow = [d for d in ep[1:] if (d - d0).days <= HORIZON]
            if not follow:
                continue
            total = sum(days[d] for d in follow)
            per_day = topic_counts[key].most_common(1)[0][0] or 3
            prop: list[date] = []
            left = total
            d = d0 + timedelta(days=1)
            while left > 0 and (d - d0).days <= HORIZON:
                need = min(per_day, left)
                other = day_total.get(d, 0) - days.get(d, 0)
                c = cap.get(d.weekday())
                if c is None or c - other >= need:
                    prop.append(d)
                    left -= need
                d += timedelta(days=1)
            fs, ps = set(follow), set(prop)
            r["ep"] += 1
            r["real_days"] += len(fs)
            r["prop_days"] += len(ps)
            r["hit"] += len(fs & ps)
            r["hit1"] += sum(1 for x in fs if any(abs((x - p).days) <= 1 for p in ps))
            r["same_first"] += int(min(fs) == min(ps)) if ps else 0
            if ps:
                r["shift_n"] += 1
                r["shift_sum"] += (statistics.mean([(p - d0).days for p in ps])
                                   - statistics.mean([(x - d0).days for x in fs]))
            r["left_over"] += left
    return r


def report(title: str, r: Counter) -> None:
    print(f"\n=== {title} — konu bölümü: {r['ep']} ===")
    print(f"  koçun gerçek yayma günlerinin önerideki payı (kapsama) {pct(r['hit'], r['real_days'])}"
          f" · ±1 gün {pct(r['hit1'], r['real_days'])}")
    print(f"  önerilen günlerin gerçekte kullanılma payı (isabet) {pct(r['hit'], r['prop_days'])}")
    print(f"  ilk yayma günü aynı {pct(r['same_first'], r['ep'])}")
    if r["shift_n"]:
        print(f"  öneri ortalama {r['shift_sum'] / r['shift_n']:+.1f} gün (− = koçtan erken bitirir)")
    print(f"  sığmayan test (13 gün içinde) {r['left_over']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int, action="append", required=True)
    ap.add_argument("--weeks", type=int, default=10)
    ap.add_argument("--cap", default="p90", choices=["median", "p75", "p90", "max", "none"])
    args = ap.parse_args()
    tot = Counter()
    with SessionLocal() as db:
        for sid in args.student:
            u = db.get(User, sid)
            r = analyse(db, sid, args.weeks, args.cap)
            tot.update(r)
            report(f"{u.full_name if u else sid} (#{sid})", r)
    if len(args.student) > 1:
        report(f"TOPLAM (kapasite={args.cap})", tot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
