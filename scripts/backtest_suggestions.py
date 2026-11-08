# -*- coding: utf-8 -*-
"""Günlük öneri motoru — geçmişi yeniden oynatan ölçüm (SALT OKUMA).

Her öğrencinin son N haftasında koçun test verdiği her gün, o günü planladığı
andaki durum geçmişten kurulur ve ÜRÜNÜN sıralayıcısı (`suggestions.
rank_candidates`) çalıştırılır. Soru: koçun o gün gerçekten verdiği bölümler
önerilerin kaçıncı sırasında? Zaman yolculuğu kuralları `rec_learning`'de.

Varyantlar: eski formül (LEGACY_WEIGHTS) · varsayılan (DEFAULT_WEIGHTS) ·
--fit ile ilk %60 günden öğrenilen ağırlık (son %40'ta ölçülür) ·
--coaches ile koç başına gece işinin kararı (kaydetmez).

    python -m scripts.backtest_suggestions [--student N] [--weeks 12] [--fit] [--diag] [--coaches]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal  # noqa: E402
from app.models import Task, User  # noqa: E402
from app.services import rec_learning as rl  # noqa: E402
from app.services import suggestions as sg  # noqa: E402


def pct(a, b) -> str:
    return "   —" if not b else f"%{100 * a / b:3.0f}"


def line(title: str, r: Counter) -> str:
    n = r["n"]
    return (f"{title:28s} kalem {n:4d} · 1. sıra {pct(r['top1'], n)} · ilk 3 {pct(r['top3'], n)} · "
            f"ilk 5 {pct(r['top5'], n)} · ilk 10 {pct(r['top10'], n)} · ekranda {pct(r['shown'], n)} "
            f"(ort. {r['shown_size'] / max(1, r['days']):.1f} öneri) · havuzda {pct(r['pool'], n)}")


def diagnose(cases, weights) -> Counter:
    """Havuza girmeyen gerçek kalemlerin nedeni."""
    out = Counter()
    for c in cases:
        ranked = {s.section_id for s in sg.rank_candidates(
            universe=c.universe, model=c.model, signals=c.signals, target_date=c.day,
            today=c.day, weights=weights, select=False)}
        cur = sg._curriculum_signal(c.universe)
        for sec in c.truth:
            if sec in ranked:
                continue
            ctx = c.universe.get(sec)
            if ctx is None:
                out["evrende yok"] += 1
            elif ctx.remaining <= 0:
                out["kapasite dolu (koç fazla verdi)"] += 1
            else:
                rank = cur.rank_by_section.get(sec)
                if rank is None:
                    out["konuya eşsiz, sinyalsiz"] += 1
                elif rank >= sg.CURRICULUM_FAR_RANK:
                    out["müfredatta ileride (rank>=3), sinyalsiz"] += 1
                else:
                    out[f"rank {rank}, sinyalsiz"] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int, action="append")
    ap.add_argument("--weeks", type=int, default=12)
    ap.add_argument("--min-days", type=int, default=8)
    ap.add_argument("--fit", action="store_true", help="ilk %60 günde ağırlık öğren, kalanında ölç")
    ap.add_argument("--diag", action="store_true", help="havuza girmeyen kalemlerin nedeni")
    ap.add_argument("--coaches", action="store_true", help="koç başına öğrenme kararı (kaydetmez)")
    args = ap.parse_args()
    since = date.today() - timedelta(days=7 * args.weeks)
    with SessionLocal() as db:
        if args.coaches:
            coach_ids = sorted({cid for (cid,) in db.query(User.teacher_id).filter(
                User.teacher_id.isnot(None), User.is_active.is_(True))})
            for cid in coach_ids:
                res = rl.assess_coach(db, cid)
                coach = db.get(User, cid)
                print(f"{(coach.full_name if coach else cid)!s:28s} {res['status']:12s} "
                      f"kalem {res['n_items']:4d} · öğrenci {res['n_students']} · ekranda varsayılan "
                      f"{res['shown_default']} → öğrenilen {res['shown_learned']} · ilk3 "
                      f"{res['top3_default']} → {res['top3_learned']}")
            return 0

        sids = args.student or [sid for (sid,) in db.query(Task.student_id).filter(Task.date >= since).distinct()]
        all_cases = []
        tot_l, tot_d = Counter(), Counter()
        for sid in sorted(sids):
            u = db.get(User, sid)
            if u is None or getattr(u.role, "value", u.role) != "student":
                continue
            rp = rl.StudentReplay(db, u, since)
            if len(rp.days) < args.min_days:
                continue
            cases = rp.cases()
            r_old, r_def = rl.evaluate(cases, sg.LEGACY_WEIGHTS), rl.evaluate(cases, sg.DEFAULT_WEIGHTS)
            tot_l.update(r_old)
            tot_d.update(r_def)
            all_cases.extend(cases)
            print(f"\n{u.full_name} (#{sid}) — {len(cases)} gün")
            print("  " + line("eski formül", r_old))
            print("  " + line("varsayılan", r_def))
        print("\n=== TOPLAM ===")
        print("  " + line("eski formül", tot_l))
        print("  " + line("varsayılan", tot_d))
        if args.diag and all_cases:
            print("\n=== HAVUZA GİRMEYEN KALEMLER (varsayılan) ===")
            for k, v in diagnose(all_cases, sg.DEFAULT_WEIGHTS).most_common():
                print(f"  {k:42s} {v}")
        if args.fit and all_cases:
            all_cases.sort(key=lambda c: c.day)
            cut = int(len(all_cases) * 0.6)
            train, test = all_cases[:cut], all_cases[cut:]
            w = rl.fit(rl.precompute(train), sg.DEFAULT_WEIGHTS)
            print("\n=== ÖĞRENİLEN AĞIRLIK (eğitim %60, ölçüm son %40) ===")
            print("  " + line("eski formül (ölçüm)", rl.evaluate(test, sg.LEGACY_WEIGHTS)))
            print("  " + line("varsayılan (ölçüm)", rl.evaluate(test, sg.DEFAULT_WEIGHTS)))
            print("  " + line("öğrenilen (ölçüm)", rl.evaluate(test, w)))
            print("  ağırlıklar:", {k: v for k, v in sorted(w.items()) if v})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
