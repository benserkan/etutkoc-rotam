# -*- coding: utf-8 -*-
"""Öğrenci haftalık ritim analizi — iskelet F2 girdisi (SALT OKUMA).

Soru: koç bu öğrencinin programını okul/dershane düzenine göre kuruyor mu, ve
bu düzen haftadan haftaya ne kadar tekrar ediyor? (İskeletten ne kadar
otomatik kurulabilir?)

Her öğrenci için:
  1. Program haftaları (WeeklyProgram aralıkları; yoksa Pazartesi haftası)
  2. Gün × periyot ızgarası: hangi ders kaç haftada o hücredeydi
  3. Gün yükü: hafta günü başına ortalama görev / test; boş gün deseni
  4. Haftadan haftaya kararlılık: bir haftanın (gün, periyot, ders) seti bir
     sonrakini ne kadar tahmin ediyor (isabet = tahminin doğru payı,
     kapsama = gerçeğin yakalanan payı)
  5. Ders başına haftalık test ve en sık adet
  6. Ürün çiplerinin bu öğrencideki isabeti (backtest_skeleton_chips)

    python -m scripts.analyze_student_rhythm --student 84 --student 164 [--weeks 8]
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
from app.models import Book, Subject, Task, User  # noqa: E402
from app.models.weekly_program import WeeklyProgram  # noqa: E402
from app.services.gorev_stats import classify_gorev  # noqa: E402

GUN = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
PER = {"morning": "Sabah", "noon": "Öğle", "evening": "Akşam", None: "—"}


def subj_of(t: Task, books: dict[int, Book], names_lower: dict[str, int]) -> int | None:
    for it in t.book_items:
        if it.book_id and it.book_id in books:
            return books[it.book_id].subject_id
    if t.title and " · " in t.title:
        return names_lower.get(t.title.split(" · ", 1)[0].strip().lower())
    return None


def weeks_for(db, sid: int, tasks: list[Task]) -> list[tuple[date, date, str]]:
    progs = (
        db.query(WeeklyProgram).filter(WeeklyProgram.student_id == sid)
        .order_by(WeeklyProgram.start_date).all()
    )
    if progs:
        return [(p.start_date, p.end_date, p.label or "") for p in progs]
    if not tasks:
        return []
    d0 = min(t.date for t in tasks)
    d0 -= timedelta(days=d0.weekday())
    out = []
    while d0 <= max(t.date for t in tasks):
        out.append((d0, d0 + timedelta(days=6), ""))
        d0 += timedelta(days=7)
    return out


def analyse(db, sid: int, n_weeks: int) -> None:
    u = db.get(User, sid)
    print("\n" + "=" * 78)
    grade = "mezun" if u.is_graduate else f"{u.grade_level}. sınıf"
    mode = getattr(u, "graduate_mode", None)
    print(f"{u.full_name} (#{sid}) · {grade}{' · ' + str(mode.value if hasattr(mode, 'value') else mode) if mode else ''}")
    tasks = (
        db.query(Task).options(joinedload(Task.book_items))
        .filter(Task.student_id == sid, Task.is_draft.is_(False)).all()
    )
    book_ids = {it.book_id for t in tasks for it in t.book_items if it.book_id}
    books = {b.id: b for b in db.query(Book).filter(Book.id.in_(book_ids or {0}))}
    sub_names = {s.id: s.name for s in db.query(Subject)}
    names_lower = {n.lower(): i for i, n in sub_names.items()}

    weeks = weeks_for(db, sid, tasks)
    weeks = [w for w in weeks if w[0] <= date.today()][-n_weeks:]
    if not weeks:
        print("  görev yok")
        return
    print(f"  Program haftaları ({len(weeks)}): " + " · ".join(
        f"{a.strftime('%d.%m')}–{b.strftime('%d.%m')} ({GUN[a.weekday()]} başlar)" for a, b, _ in weeks))

    # hafta başına (gün, periyot, ders) kümeleri
    wk_sets: list[Counter] = []
    grid: dict[tuple[int, str | None], Counter] = defaultdict(Counter)   # (gün, periyot) → ders → hafta sayısı
    day_load: dict[int, list] = defaultdict(list)                       # gün → [(görev, test)] hafta başına
    subj_tests: dict[int, list] = defaultdict(list)
    subj_counts: dict[int, Counter] = defaultdict(Counter)
    periods_used = Counter()
    kinds = Counter()
    for a, b, _ in weeks:
        wt = [t for t in tasks if a <= t.date <= b]
        cells = Counter()
        per_day = defaultdict(lambda: [0, 0])
        wk_subj_tests = Counter()
        for t in wt:
            k = classify_gorev(t)
            kinds[k] += 1
            s = subj_of(t, books, names_lower)
            p = t.period.value if hasattr(t.period, "value") else t.period
            periods_used[p is not None] += 1
            wd = t.date.weekday()
            per_day[wd][0] += 1
            tests = sum(int(it.planned_count or 0) for it in t.book_items
                        if it.book_id in books and k == "test")
            per_day[wd][1] += tests
            if s is not None:
                cells[(wd, p, s)] += 1
                if k == "test":
                    wk_subj_tests[s] += tests
                    for it in t.book_items:
                        if it.planned_count:
                            subj_counts[s][int(it.planned_count)] += 1
        for key in cells:
            grid[(key[0], key[1])][key[2]] += 1
        for wd in range(7):
            day_load[wd].append(tuple(per_day[wd]))
        for s, n in wk_subj_tests.items():
            subj_tests[s].append(n)
        wk_sets.append(cells)

    total = sum(kinds.values())
    print(f"  Görev türleri: " + " · ".join(f"{k} {n}" for k, n in kinds.most_common())
          + f"  |  periyot girilmiş %{100 * periods_used[True] // max(1, total)}")

    print("  Gün yükü (hafta başına ort. görev / test, boş kalan hafta sayısı):")
    for wd in range(7):
        loads = day_load[wd]
        if not loads:
            continue
        g = sum(x[0] for x in loads) / len(loads)
        te = sum(x[1] for x in loads) / len(loads)
        empty = sum(1 for x in loads if x[0] == 0)
        print(f"    {GUN[wd]}: {g:4.1f} görev · {te:5.1f} test · boş {empty}/{len(loads)}")

    print("  Gün × periyot ızgarası (ders: kaç haftada o hücrede):")
    nw = len(weeks)
    for (wd, p), cnt in sorted(grid.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        items = ", ".join(f"{sub_names.get(s, s)} {n}/{nw}" for s, n in cnt.most_common())
        print(f"    {GUN[wd]} {PER.get(p, p):6s}: {items}")

    # kararlılık: hafta i → hafta i+1
    print("  Haftadan haftaya kararlılık (önceki hafta iskelet olsaydı):")
    for i in range(1, len(wk_sets)):
        prev = set(k for k in wk_sets[i - 1])
        cur = set(k for k in wk_sets[i])
        prev_np = {(w, s) for w, _p, s in prev}
        cur_np = {(w, s) for w, _p, s in cur}
        if not cur:
            continue
        hit = len(prev & cur)
        hit_np = len(prev_np & cur_np)
        print(f"    {weeks[i][0].strftime('%d.%m')}: periyotlu isabet %{100 * hit // max(1, len(prev))} "
              f"kapsama %{100 * hit // max(1, len(cur))} · periyotsuz isabet "
              f"%{100 * hit_np // max(1, len(prev_np))} kapsama %{100 * hit_np // max(1, len(cur_np))} "
              f"({len(cur_np)} gün-ders)")
    # çoğunluk iskeleti: son 3 haftanın ≥2'sinde olan (gün, ders)
    if len(wk_sets) >= 4:
        last3 = wk_sets[-4:-1]
        maj = Counter()
        for c in last3:
            for w, _p, s in set(c):
                maj[(w, s)] += 1
        maj_set = {k for k, n in maj.items() if n >= 2}
        cur_np = {(w, s) for w, _p, s in wk_sets[-1]}
        hit = len(maj_set & cur_np)
        print(f"    son hafta, önceki 3 haftanın çoğunluk iskeletine göre: isabet "
              f"%{100 * hit // max(1, len(maj_set))} kapsama %{100 * hit // max(1, len(cur_np))} "
              f"({len(maj_set)} satır)")

    print("  Ders başına haftalık test (hafta hafta) · en sık adet:")
    for s, lst in sorted(subj_tests.items(), key=lambda kv: -sum(kv[1])):
        mode_c = subj_counts[s].most_common(1)[0][0] if subj_counts[s] else "—"
        print(f"    {str(sub_names.get(s, s))[:34]:34s} {lst} · adet {mode_c}")

    # ürün çipleri
    try:
        from scripts.backtest_skeleton_chips import Replay, report

        rp = Replay(db, u, [t for t in tasks if t.date <= date.today()])
        r, subj_r = rp.run()
        if r["n"]:
            report("  Ürün çipleri (bu öğrenci)", r, subj_r, rp.subject_names)
    except Exception as e:  # noqa: BLE001
        print(f"  çip backtest'i koşulamadı: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int, action="append", required=True)
    ap.add_argument("--weeks", type=int, default=8)
    args = ap.parse_args()
    with SessionLocal() as db:
        for sid in args.student:
            analyse(db, sid, args.weeks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
