# -*- coding: utf-8 -*-
"""Haftalık İskelet — Adım 0 geriye dönük isabet ölçümü (SALT OKUMA).

Hiçbir şey yazmaz. Geçmiş haftalarda "sistem ne önerirdi?" hesaplanır ve koçun
gerçekte verdiğiyle karşılaştırılır.

Katman A — ders yerleşimi: bir önceki haftadan (ve son 3 haftanın çoğunluğundan)
çıkarılan (gün, ders) iskeleti, o haftanın gerçek (gün, ders) kümesini ne kadar
tutturuyor? (isabet = önerilenin yüzde kaçı gerçekten verildi · kapsama =
verilenlerin yüzde kaçını iskelet öngördü)

Katman B — konu önerisi, her gerçek test kalemi için, o ANA KADAR olanlara
bakarak kural (kullanıcı onaylı sıra):
  1) bu derste son verilen bölüm; kaynağında test kaldıysa ve konu kapatılmadıysa → aynı bölüm
  2) yoksa aynı kitabın sıradaki KONULU bölümü (dolu olanlar atlanır)
  3) yoksa (müfredat adımı — bu ölçümde simüle edilmez) → öneri yok
Test sayısı: öğrencinin o dersteki son 20 kalemindeki en sık adet (≥3 örnek), yoksa 3.

Kapasite yaklaşık: bölüm test sayısı − o ana kadar planlanan toplam (bağımsız
çalışma/önceden çözülmüş girişler hesaba katılmaz → "kaldı" tahmini iyimserdir).

Kullanım:
    python -m scripts.backtest_skeleton                 # tüm öğrenciler
    python -m scripts.backtest_skeleton --student 113   # tek öğrenci + ders kırılımı
    python -m scripts.backtest_skeleton --weeks 16
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
from app.models import Book, BookType, BookSection, Subject, Task, TaskBookItem, User  # noqa: E402
from app.models.topic_closure import TopicClosure  # noqa: E402
from app.services.gorev_stats import is_test_book  # noqa: E402

WEEKDAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def pct(a: float, b: float) -> str:
    return "—" if not b else f"%{100 * a / b:.0f}"


def load(db, student_ids, since):
    q = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.is_draft.is_(False), Task.date >= since)
    )
    if student_ids:
        q = q.filter(Task.student_id.in_(student_ids))
    return q.all()


def analyse(db, sid: int, tasks: list[Task], books, sections, book_sections, closures,
            subj_names, verbose: bool):
    # --- test kalemleri (kronolojik)
    items = []  # (date, task_id, item_id, period, subject_id, book_id, section, planned)
    for t in tasks:
        for it in t.book_items:
            if not it.book_id or not it.book_section_id:
                continue
            bk = books.get(it.book_id)
            sec = sections.get(it.book_section_id)
            if bk is None or sec is None or not is_test_book(bk):
                continue
            items.append((t.date, t.id, it.id, t.period or "-", bk.subject_id, bk.id, sec,
                          int(it.planned_count or 0)))
    items.sort(key=lambda r: (r[0], r[1], r[2]))
    if not items:
        return None

    # --- KATMAN A: haftalık (gün, ders) kümeleri
    weeks: dict[date, set] = defaultdict(set)
    weeks_p: dict[date, set] = defaultdict(set)
    for d, _tid, _iid, per, subj, *_ in items:
        weeks[monday(d)].add((d.weekday(), subj))
        weeks_p[monday(d)].add((d.weekday(), per, subj))
    wk = sorted(weeks)
    a = Counter()
    for i, w in enumerate(wk):
        prev = w - timedelta(days=7)
        actual = weeks[w]
        if len(actual) < 4 or prev not in weeks or len(weeks[prev]) < 4:
            continue
        pred = weeks[prev]
        a["weeks"] += 1
        a["pred"] += len(pred)
        a["act"] += len(actual)
        a["hit"] += len(pred & actual)
        pp, ap = weeks_p[prev], weeks_p[w]
        a["pred_p"] += len(pp)
        a["act_p"] += len(ap)
        a["hit_p"] += len(pp & ap)
        # çoğunluk iskeleti: son 3 haftanın ≥2'sinde olan slotlar
        prev3 = [w - timedelta(days=7 * k) for k in (1, 2, 3) if (w - timedelta(days=7 * k)) in weeks]
        if len(prev3) >= 2:
            cnt = Counter(s for pw in prev3 for s in weeks[pw])
            maj = {s for s, c in cnt.items() if c >= 2}
            a["weeks_m"] += 1
            a["pred_m"] += len(maj)
            a["act_m"] += len(actual)
            a["hit_m"] += len(maj & actual)
        # gün bazında ders listesi birebir aynı mı
        for wd in range(7):
            ps = {s for d_, s in pred if d_ == wd}
            as_ = {s for d_, s in actual if d_ == wd}
            if as_:
                a["days"] += 1
                if ps == as_:
                    a["days_exact"] += 1

    # --- KATMAN B: konu önerisi (her kalem, o ana kadarki geçmişle)
    b = Counter()
    per_subj = defaultdict(Counter)
    consumed = Counter()  # section_id -> planlanan toplam (o ana kadar)
    last_sec: dict[int, BookSection] = {}
    last_in_book: dict[int, BookSection] = {}
    recent: dict[int, list] = defaultdict(list)  # subject -> [(date, section)] açık iplikler
    slot_book: dict[tuple, tuple] = {}  # (weekday, subject) -> (monday, book_id) son görülen
    counts_hist: dict[int, list[int]] = defaultdict(list)
    first_week = wk[0] if wk else None
    for d, _tid, _iid, _per, subj, bid, sec, planned in items:
        eligible = first_week is not None and monday(d) > first_week  # ilk hafta ısınma
        if eligible:
            b["items"] += 1
            per_subj[subj]["items"] += 1
            last = last_sec.get(subj)
            pred = None
            how = None
            if last is not None:
                closed_at = closures.get(last.topic_id) if last.topic_id else None
                rem = int(last.test_count or 0) - consumed[last.id]
                if rem > 0 and not (closed_at and closed_at.date() <= d):
                    pred, how = last, "devam"
                else:
                    for cand in book_sections.get(last.book_id, []):
                        if cand.order <= last.order or not cand.topic_id:
                            continue
                        if int(cand.test_count or 0) - consumed[cand.id] <= 0:
                            continue
                        ca = closures.get(cand.topic_id)
                        if ca and ca.date() <= d:
                            continue
                        pred, how = cand, "sonraki"
                        break
            if pred is None:
                b["none"] += 1
                per_subj[subj]["none"] += 1
            else:
                b["pred"] += 1
                b[f"pred_{how}"] += 1
                per_subj[subj]["pred"] += 1
                same_sec = pred.id == sec.id
                same_topic = bool(pred.topic_id) and pred.topic_id == sec.topic_id
                if same_sec:
                    b["sec"] += 1
                    b[f"sec_{how}"] += 1
                    per_subj[subj]["sec"] += 1
                if same_sec or same_topic:
                    b["topic"] += 1
                    per_subj[subj]["topic"] += 1
                if pred.book_id == bid:
                    b["book"] += 1
            # tanı: konu geçen seferkiyle aynı mı + KİTAP bilinirse kitap-imleci isabeti
            if last is not None and sec.topic_id and last.topic_id == sec.topic_id:
                b["same_topic_as_last"] += 1
            lb = last_in_book.get(bid)
            if lb is not None:
                b["bk_n"] += 1
                rem_b = int(lb.test_count or 0) - consumed[lb.id]
                pb = lb if rem_b > 0 else next(
                    (c for c in book_sections.get(bid, [])
                     if c.order > lb.order and c.topic_id
                     and int(c.test_count or 0) - consumed[c.id] > 0), None)
                if pb is not None and (pb.id == sec.id or (pb.topic_id and pb.topic_id == sec.topic_id)):
                    b["bk_hit"] += 1
                if sec.id == lb.id or sec.order >= lb.order:
                    b["bk_forward"] += 1
            # VARYANT: slot kitabı hatırlar (geçen haftanın aynı günü + aynı ders → aynı kitap)
            sb = slot_book.get((d.weekday(), subj))
            vb = sb[1] if sb and sb[0] < monday(d) else (last.book_id if last is not None else None)
            if vb is not None:
                b["sb_n"] += 1
                if vb == bid:
                    b["sb_book"] += 1
                lb2 = last_in_book.get(vb)
                pb2 = None
                if lb2 is not None:
                    pb2 = lb2 if int(lb2.test_count or 0) - consumed[lb2.id] > 0 else next(
                        (c for c in book_sections.get(vb, [])
                         if c.order > lb2.order and c.topic_id
                         and int(c.test_count or 0) - consumed[c.id] > 0), None)
                if pb2 is not None and (pb2.id == sec.id or (pb2.topic_id and pb2.topic_id == sec.topic_id)):
                    b["sb_topic"] += 1
                    per_subj[subj]["sb_topic"] += 1
            # VARYANT İPLİK: son 7 günde bu derste açık tüm bölümler (her biri kendi
            # kitabında devam/sonraki) → aday kümesi; gerçek kalem kümede mi?
            cands = {}
            for dd, ss in recent[subj]:
                if (d - dd).days > 7:
                    continue
                if int(ss.test_count or 0) - consumed[ss.id] > 0:
                    nxt = ss
                else:
                    nxt = next((c for c in book_sections.get(ss.book_id, [])
                                if c.order > ss.order and c.topic_id
                                and int(c.test_count or 0) - consumed[c.id] > 0), None)
                if nxt is not None:
                    cands[nxt.id] = nxt
            if cands:
                b["th_n"] += 1
                b["th_size"] += len(cands)
                if sec.id in cands or (sec.topic_id and any(c.topic_id == sec.topic_id for c in cands.values())):
                    b["th_hit"] += 1
                    per_subj[subj]["th_hit"] += 1
            hist = counts_hist[subj][-20:]
            guess = Counter(hist).most_common(1)[0][0] if len(hist) >= 3 else 3
            b["cnt_n"] += 1
            if guess == planned:
                b["cnt_exact"] += 1
            if abs(guess - planned) <= 1:
                b["cnt_pm1"] += 1
        consumed[sec.id] += planned
        last_sec[subj] = sec
        last_in_book[bid] = sec
        slot_book[(d.weekday(), subj)] = (monday(d), bid)
        recent[subj] = [(dd, ss) for dd, ss in recent[subj] if ss.id != sec.id] + [(d, sec)]
        counts_hist[subj].append(planned)

    if verbose:
        name = db.get(User, sid).full_name
        print(f"\n=== {name} (#{sid}) — {len(items)} test kalemi, {len(wk)} hafta ===")
        _print(a, b)
        print("  Ders kırılımı (konu isabeti = aynı bölüm ya da aynı müfredat konusu):")
        rows = sorted(per_subj.items(), key=lambda kv: -kv[1]["items"])
        for subj, c in rows:
            print(f"    {subj_names.get(subj, subj)[:34]:34s} kalem {c['items']:3d} · "
                  f"öneri {pct(c['pred'], c['items']):>4s} · aynı bölüm {pct(c['sec'], c['pred']):>4s} · "
                  f"aynı konu {pct(c['topic'], c['pred']):>4s} · slot-kitaplı {pct(c['sb_topic'], c['items']):>4s} · iplik {pct(c['th_hit'], c['items']):>4s}")
    return a, b


def _print(a: Counter, b: Counter):
    print("  KATMAN A — ders yerleşimi (gün × ders)")
    print(f"    geçen haftayı iskelet yap : {a['weeks']} hafta · isabet {pct(a['hit'], a['pred'])} · "
          f"kapsama {pct(a['hit'], a['act'])}")
    print(f"    son 3 haftanın çoğunluğu  : {a['weeks_m']} hafta · isabet {pct(a['hit_m'], a['pred_m'])} · "
          f"kapsama {pct(a['hit_m'], a['act_m'])}")
    print(f"    periyotla birlikte (gün×periyot×ders): isabet {pct(a['hit_p'], a['pred_p'])} · "
          f"kapsama {pct(a['hit_p'], a['act_p'])}")
    print(f"    gün ders listesi birebir aynı: {pct(a['days_exact'], a['days'])} ({a['days']} gün)")
    print("  KATMAN B — konu önerisi (her test kalemi)")
    print(f"    kalem {b['items']} · öneri üretildi {pct(b['pred'], b['items'])} "
          f"(devam {b['pred_devam']} · sonraki bölüm {b['pred_sonraki']} · öneri yok {b['none']})")
    print(f"    önerilenlerde: aynı BÖLÜM {pct(b['sec'], b['pred'])} · aynı KONU {pct(b['topic'], b['pred'])} · "
          f"aynı KİTAP {pct(b['book'], b['pred'])}")
    print(f"      'devam' dalı doğruluğu {pct(b['sec_devam'], b['pred_devam'])} · "
          f"'sonraki bölüm' dalı doğruluğu {pct(b['sec_sonraki'], b['pred_sonraki'])}")
    print(f"    tüm kalemlere göre doğru konu: {pct(b['topic'], b['items'])}")
    print(f"    tanı: konu bu dersteki bir önceki kalemle aynı {pct(b['same_topic_as_last'], b['items'])}")
    print(f"    tanı: KİTAP bilinseydi kitap-imleci konu isabeti {pct(b['bk_hit'], b['bk_n'])} · "
          f"kitapta ileri/aynı yerde {pct(b['bk_forward'], b['bk_n'])} ({b['bk_n']} kalem)")
    print(f"    VARYANT slot kitabı hatırlar: doğru kitap {pct(b['sb_book'], b['sb_n'])} · "
          f"doğru konu {pct(b['sb_topic'], b['items'])} (tüm kalemlere göre)")
    print(f"    VARYANT İPLİK (son 7 günün açık bölümleri): aday kümesinde {pct(b['th_hit'], b['items'])} "
          f"(tüm kalemlere göre) · ort. aday {b['th_size'] / b['th_n'] if b['th_n'] else 0:.1f}")
    print(f"    test sayısı: birebir {pct(b['cnt_exact'], b['cnt_n'])} · ±1 içinde {pct(b['cnt_pm1'], b['cnt_n'])}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--student", type=int, action="append")
    ap.add_argument("--weeks", type=int, default=20)
    ap.add_argument("--min-items", type=int, default=40)
    args = ap.parse_args()
    since = monday(date.today()) - timedelta(days=7 * args.weeks)
    with SessionLocal() as db:
        tasks = load(db, args.student, since)
        by_student = defaultdict(list)
        for t in tasks:
            by_student[t.student_id].append(t)
        book_ids = {it.book_id for t in tasks for it in t.book_items if it.book_id}
        books = {b.id: b for b in db.query(Book).filter(Book.id.in_(book_ids), Book.type.in_(list(BookType))).all()} if book_ids else {}
        secs = db.query(BookSection).filter(BookSection.book_id.in_(book_ids)).all() if book_ids else []
        sections = {s.id: s for s in secs}
        book_sections = defaultdict(list)
        for s in secs:
            book_sections[s.book_id].append(s)
        for lst in book_sections.values():
            lst.sort(key=lambda s: (s.order, s.id))
        subj_names = {s.id: s.name for s in db.query(Subject).all()}
        closures_all = defaultdict(dict)
        for c in db.query(TopicClosure).all():
            closures_all[c.student_id][c.topic_id] = c.closed_at

        tot_a, tot_b, n = Counter(), Counter(), 0
        for sid, ts in sorted(by_student.items()):
            n_items = sum(len(t.book_items) for t in ts)
            if not args.student and n_items < args.min_items:
                continue
            res = analyse(db, sid, ts, books, sections, book_sections, closures_all[sid],
                          subj_names, verbose=bool(args.student) or True)
            if res:
                n += 1
                tot_a.update(res[0])
                tot_b.update(res[1])
        if n > 1:
            print(f"\n######## TOPLAM ({n} öğrenci, son {args.weeks} hafta) ########")
            _print(tot_a, tot_b)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
