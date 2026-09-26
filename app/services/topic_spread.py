"""Konuyu günlere yay (İskelet F2-3, 2026-09-26).

Koç açıklaması: okul/dershane öğrencisinde günün ~1/4'ü o gün İŞLENEN ders
(çapa — iskelette sabit gün), ~3/4'ü o hafta işlenen konunun kalan testlerinin
boş günlere dağıtılması. Dağıtımın kalıbı yok ("programda boşluk nerede ise
oraya") → tahmin değil HESAP: koça önizleme sunulur, koç onaylar/düzeltir.

KURALLAR (koç onaylı):
  · Birim KONU: kalan testler öğrencinin o konudaki TÜM test kitaplarından bir
    havuz. Devam edilen kitap önce (başlanmış → ilerlemesi yüksek → kalanı
    bol). Günün hedef adedi bir kitapta yetmezse aynı konudaki başka kitaptan
    tamamlanır → o gün kitap başına ayrı görev ("Bilgi Sarmal — Oran Orantı: 2
    test" · "345 — Oran Orantı: 1 test"). Aynı konu aynı güne birden çok
    kaynaktan girebilir; yalnız o konu O GÜN zaten verilmişse gün atlanır.
  · ÇAPAYA ÖNCELİK: bir günün boşluğu = kapasite − o güne yazılmış testler −
    o günün henüz yazılmamış çapa derslerinin payı. Çapa ders her zaman kazanır.
  · Yayma bir sonraki AYNI DERSİN çapa gününden önce biter (o gün yeni konu
    başlar); sığmayan kısım önizlemede açıkça "sığmadı" olarak söylenir.
  · Kapasite geçmişten öğrenilir (hafta günü başına tipik test sayısı, geçerli
    dönemin içinden), koç iskelet penceresinden düzeltir.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import Book, Subject, Task, User
from app.models.weekly_skeleton import WeeklySkeleton
from app.services import skeleton_suggest as sk
from app.services import topic_closure
from app.services.gorev_stats import is_test_book

SPREAD_MAX_DAYS = 14
CAPACITY_LOOKBACK_DAYS = 28
CAPACITY_PERCENTILE = 0.9
GUN = sk.GUN


# ---------------------------------------------------------------- kapasite


def _tests_by_date(db: Session, student_id: int, start: date, end: date) -> dict[date, int]:
    """Güne yazılmış TEST adedi (taslaklar dahil; deneme/etkinlik hariç)."""
    tasks = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.student_id == student_id, Task.date >= start, Task.date <= end)
        .all()
    )
    book_ids = {it.book_id for t in tasks for it in t.book_items if it.book_id}
    test_books = {
        b.id for b in db.query(Book).filter(Book.id.in_(book_ids or {0})) if is_test_book(b)
    }
    out: dict[date, int] = defaultdict(int)
    for t in tasks:
        for it in t.book_items:
            if it.book_id in test_books:
                out[t.date] += int(it.planned_count or 0)
    return out


def learned_capacity(
    db: Session, student: User, skel: WeeklySkeleton | None, today: date | None = None,
) -> dict[int, int]:
    """Hafta günü → sığan test sayısı: o günün yüklerinin %90'lık dilimi. Son 4
    hafta + bu haftanın planı; dönem başlangıcından eskisi alınmaz (yaz ritmi
    okula karışmasın). Test yazılmamış günler örnek sayılmaz.

    Neden %90'lık (F2-3c ölçümü, prod Taha+Zeynep+Emir, 130 konu bölümü):
    medyan koçun gerçek yayma günlerini %46 yakalıyor, 118 test sığmıyordu
    (koç günlere tipik günden fazla test koyabiliyor) · %75'lik %59 · %90'lık
    %75 (±1 gün %85), 14 test sığmıyor · en yüksek gün %79 ama tek aşırı günden
    etkilenir. scripts/backtest_topic_spread.py --cap ile yeniden ölçülür."""
    today = today or date.today()
    lo = today - timedelta(days=CAPACITY_LOOKBACK_DAYS)
    if skel is not None and skel.valid_from and skel.valid_from > lo:
        lo = skel.valid_from
    hi = today + timedelta(days=6)
    per_day = _tests_by_date(db, student.id, lo, hi)
    by_wd: dict[int, list[int]] = defaultdict(list)
    for d, n in per_day.items():
        if n > 0:
            by_wd[d.weekday()].append(n)
    return {wd: _percentile(v, CAPACITY_PERCENTILE) for wd, v in by_wd.items()}


def _percentile(values: list[int], p: float) -> int:
    v = sorted(values)
    return int(v[min(len(v) - 1, int(round(p * (len(v) - 1))))])


def capacity_overrides(skel: WeeklySkeleton | None) -> dict[int, int]:
    if skel is None or not skel.day_capacity:
        return {}
    try:
        raw = json.loads(skel.day_capacity)
    except (ValueError, TypeError):
        return {}
    out = {}
    for k, v in (raw or {}).items():
        try:
            if v is not None:
                out[int(k)] = max(0, int(v))
        except (ValueError, TypeError):
            continue
    return out


def capacity_table(db: Session, student: User, skel: WeeklySkeleton | None) -> list[dict]:
    learned = learned_capacity(db, student, skel)
    over = capacity_overrides(skel)
    return [
        {"weekday": wd, "learned": learned.get(wd), "override": over.get(wd),
         "effective": over.get(wd, learned.get(wd))}
        for wd in range(7)
    ]


def set_capacity_overrides(skel: WeeklySkeleton, values: dict[int, int | None]) -> None:
    over = capacity_overrides(skel)
    for wd, v in values.items():
        wd = int(wd)
        if not 0 <= wd <= 6:
            continue
        if v is None:
            over.pop(wd, None)
        else:
            over[wd] = max(0, min(200, int(v)))
    skel.day_capacity = json.dumps({str(k): v for k, v in sorted(over.items())}) if over else None


# ---------------------------------------------------------------- plan


def _rank_pool(pool: list[sk._Sec]) -> list[sk._Sec]:
    """Devam edilen kaynak önce: başlanmış → ilerlemesi yüksek → kalanı bol."""
    def key(s: sk._Sec):
        started = (s.completed + s.reserved) > 0
        prog = (s.completed + s.reserved) / s.total if s.total else 0
        return (not started, -prog, -s.remaining, s.book_name, s.order)
    return sorted(pool, key=key)


def plan_spread(
    db: Session, *, student: User, coach_id: int, start: date, per_day: int,
    topic_id: int | None = None, section_id: int | None = None,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    start = max(start, today)
    per_day = max(1, min(int(per_day), 50))
    secs = sk._load_sections(db, student.id)
    closed = topic_closure.closed_topic_ids(db, student.id)
    if topic_id is None and section_id in secs and secs[section_id].topic_id:
        # Bölüm konuya bağlıysa havuz KONU olur (diğer kitaplardan tamamlama)
        topic_id = secs[section_id].topic_id
    if topic_id is not None:
        if topic_id in closed:
            pool = []
        else:
            pool = [s for s in secs.values() if s.topic_id == topic_id and s.remaining > 0]
    elif section_id is not None and section_id in secs:
        s0 = secs[section_id]
        pool = [s0] if s0.remaining > 0 else []
    else:
        pool = []
    pool = _rank_pool(pool)
    base = {
        "topic_id": topic_id, "section_id": section_id, "per_day": per_day,
        "start": start.isoformat(), "days": [], "skipped": [], "leftover": 0,
        "total_remaining": sum(s.remaining for s in pool),
        "window_end": None, "stop_reason": None,
        "subject_id": pool[0].subject_id if pool else None,
    }
    if not pool:
        return base
    subject_id = pool[0].subject_id
    pool_secs = {s.id for s in pool}
    pool_topics = {s.topic_id for s in pool if s.topic_id}

    # --- pencere: bir sonraki AYNI dersin çapa gününden önce biter
    skels = sk.list_skeletons(db, student.id)
    end = start + timedelta(days=SPREAD_MAX_DAYS - 1)
    d = start + timedelta(days=1)
    while d <= start + timedelta(days=SPREAD_MAX_DAYS - 1):
        cur = sk.skeleton_for_date(skels, d)
        if cur and any(
            s.is_anchor and s.subject_id == subject_id and s.weekday == d.weekday()
            for s in cur.slots
        ):
            end = d - timedelta(days=1)
            subj = db.get(Subject, subject_id)
            base["stop_reason"] = (
                f"{GUN[d.weekday()]} {d.strftime('%d.%m')} bir sonraki "
                f"{subj.name if subj else ''} dersi — konu o güne kadar bitmeli"
            )
            break
        d += timedelta(days=1)
    base["window_end"] = end.isoformat()

    # --- günlerin mevcut yükü, o konunun zaten olduğu günler, çapa payı
    planned = _tests_by_date(db, student.id, start, end)
    topic_days: set[date] = set()
    for t in (
        db.query(Task).options(joinedload(Task.book_items))
        .filter(Task.student_id == student.id, Task.date >= start, Task.date <= end)
    ):
        for it in t.book_items:
            sec = secs.get(it.book_section_id) if it.book_section_id else None
            if it.book_section_id in pool_secs or (sec and sec.topic_id and sec.topic_id in pool_topics):
                topic_days.add(t.date)
    reserve: dict[date, int] = defaultdict(int)
    try:
        g = sk.build_ghosts(db, student=student, coach_id=coach_id, start=start, end=end, today=today)
        for day in g["days"]:
            dd = date.fromisoformat(day["date"])
            for gh in day["ghosts"]:
                if gh.get("is_anchor") and gh["subject_id"] != subject_id:
                    reserve[dd] += gh["chips"][0]["count"] if gh["chips"] else per_day
    except Exception:  # noqa: BLE001 — çapa payı yan bilgi; plan yine üretilir
        sk.log.warning("topic_spread: çapa payı hesaplanamadı", exc_info=True)

    left = {s.id: s.remaining for s in pool}
    cap_cache: dict[int | None, tuple[dict, dict]] = {}
    d = start
    while d <= end:
        pool_left = sum(left.values())
        need = min(per_day, pool_left)
        if need <= 0:
            break
        cur = sk.skeleton_for_date(skels, d)
        ck = cur.id if cur else None
        if ck not in cap_cache:
            cap_cache[ck] = (learned_capacity(db, student, cur, today), capacity_overrides(cur))
        learned, over = cap_cache[ck]
        cap = over.get(d.weekday(), learned.get(d.weekday()))
        load = planned.get(d, 0)
        rsv = reserve.get(d, 0)
        info = {"date": d.isoformat(), "capacity": cap, "planned": load, "anchor_reserve": rsv}
        if d in topic_days:
            base["skipped"].append({**info, "reason": "bu konu o gün zaten var"})
        elif cap is not None and cap - load - rsv < need:
            base["skipped"].append({
                **info,
                "reason": f"yer yok (kapasite {cap} · yazılı {load}"
                          + (f" · dershane payı {rsv}" if rsv else "") + ")",
            })
        else:
            items = []
            want = need
            for s in pool:
                if want == 0:
                    break
                n = min(left[s.id], want)
                if n > 0:
                    items.append({
                        "section_id": s.id, "section_label": s.label, "book_id": s.book_id,
                        "book_name": s.book_name, "count": n,
                    })
                    left[s.id] -= n
                    want -= n
            base["days"].append({
                **info, "free": None if cap is None else cap - load - rsv, "items": items,
            })
        d += timedelta(days=1)
    base["leftover"] = sum(left.values())
    return base
