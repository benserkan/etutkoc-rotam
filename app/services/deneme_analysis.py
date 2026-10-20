"""D4 — Program denemesi analizi (TEK MERKEZ, salt okuma, AI yok, kredi yok).

Kaynaklar:
  · Program denemeleri — görevde sonucu girilen her deneme köprüyle bir ExamResult
    (import_source="task") olur; seri/kapsam `exam_scope` ile (Denemeler ile aynı kural).
    Süre ve soru sayısı kalemden (TaskBookItem) okunur.
  · Eski toplu kayıtlar (D1 öncesi: deneme kitabı kalemi, exam_kind NULL, birden çok deneme
    tek satırda) seriye GİRMEZ (net grafiğini bozar) — yalnız ders doğruluğuna katılır.
  · Kıyas: aynı dersin soru bankası test doğruluğu + karne/elle girilen genel denemelerdeki
    o dersin doğruluğu (son KIYAS_GUN gün).

Ölçüler (seri başına):
  net, net % (net ÷ soru — farklı soru sayılı denemeler kıyaslanabilsin), doğruluk
  D/(D+Y), boş oranı B/soru, soru başı dakika (süre girilmişse).
  · Normal aralık = net %'nin çeyrekler arası bandı (≥4 deneme) — ortalama DEĞİL;
    son denemenin konumu: altında / içinde / üstünde.
  · Üst üste düşüş: sondan geriye kesintisiz azalan net % sayısı (3+ → işaret).
  · Eğilim: son en çok 8 denemeye en küçük kareler doğrusu (deneme başına net % değişimi);
    ≥4 denemede 4 deneme sonrası tahmini net % (0–100'e kırpılır).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import median

from sqlalchemy.orm import Session, joinedload

from app.models import Book, Task, TaskBookItem, User
from app.models.book import BookType
from app.models.exam_result import SOURCE_TASK, ExamResult, analysis_exam_filter
from app.services import exam_scope
from app.services.deneme_service import DENEME_BOOK_TYPES, item_subject, result_pending

KIYAS_GUN = 90
MIN_NORMAL_POINTS = 4
MIN_TREND_POINTS = 4
TREND_WINDOW = 8
PROJECT_AHEAD = 4
DECLINE_FLAG = 3
FLAT_SLOPE = 0.75          # deneme başına net % değişimi bu kadarsa "yatay"
GAP_FLAG = 15.0            # test ↔ deneme doğruluk farkı (puan) işaret eşiği
BLANK_FLAG = 0.25          # boş oranı işaret eşiği
MIN_COMPARE_ANSWERED = 10  # kıyas için en az D+Y


def _pct(a: float, b: float) -> float | None:
    return round(100.0 * a / b, 1) if b else None


def _quartiles(vals: list[float]) -> tuple[float, float]:
    s = sorted(vals)
    n = len(s)
    lower = s[: n // 2]
    upper = s[(n + 1) // 2:]
    return round(median(lower), 1), round(median(upper), 1)


def _slope(ys: list[float]) -> float:
    n = len(ys)
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0


def _decline_run(vals: list[float]) -> int:
    run = 0
    for i in range(len(vals) - 1, 0, -1):
        if vals[i] < vals[i - 1]:
            run += 1
        else:
            break
    return run


def _canon(name: str | None) -> str:
    return exam_scope._canon_subject(name or "")


def _accuracy_by_subject_tests(db: Session, student_id: int, since: date) -> dict[str, dict]:
    """Soru bankası test kalemlerinden ders doğruluğu (D/Y girilenler)."""
    from app.services.gorev_stats import item_is_test

    items = (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
             .options(joinedload(TaskBookItem.book).joinedload(Book.subject),
                      joinedload(TaskBookItem.topic))
             .filter(Task.student_id == student_id, Task.is_draft.is_(False), Task.date >= since,
                     TaskBookItem.exam_kind.is_(None),
                     (TaskBookItem.correct_count.isnot(None)) | (TaskBookItem.wrong_count.isnot(None)))
             .all())
    out: dict[str, dict] = defaultdict(lambda: {"correct": 0, "wrong": 0})
    for it in items:
        if not item_is_test(it):
            continue
        subj = it.book.subject if it.book is not None else (it.topic.subject if it.topic else None)
        if subj is None:
            continue
        b = out[_canon(subj.name)]
        b["correct"] += int(it.correct_count or 0)
        b["wrong"] += int(it.wrong_count or 0)
    return out


def _accuracy_by_subject_karne(db: Session, student_id: int, since: date) -> dict[str, dict]:
    """Karne/elle girilen GENEL denemelerin ders kırılımından ders doğruluğu."""
    import json

    exams = (db.query(ExamResult)
             .filter(ExamResult.student_id == student_id, analysis_exam_filter(),
                     ExamResult.exam_date >= since).all())
    out: dict[str, dict] = defaultdict(lambda: {"correct": 0, "wrong": 0, "exams": 0})
    for e in exams:
        if exam_scope.classify(e) != "genel":
            continue
        try:
            rows = json.loads(e.subject_nets) if e.subject_nets else []
        except ValueError:
            rows = []
        seen: set[str] = set()
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or not r.get("name"):
                continue
            key = _canon(str(r["name"]))
            b = out[key]
            b["correct"] += int(r.get("correct") or 0)
            b["wrong"] += int(r.get("wrong") or 0)
            if key not in seen:
                b["exams"] += 1
                seen.add(key)
    return out


def _legacy_by_subject(db: Session, student_id: int) -> dict[str, dict]:
    """D1 öncesi toplu deneme kalemleri (exam_kind NULL, deneme kitabı) — yalnız doğruluk."""
    items = (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
             .join(Book, Book.id == TaskBookItem.book_id)
             .options(joinedload(TaskBookItem.book).joinedload(Book.subject))
             .filter(Task.student_id == student_id, Task.is_draft.is_(False),
                     TaskBookItem.exam_kind.is_(None), Book.type.in_(list(DENEME_BOOK_TYPES)),
                     (TaskBookItem.correct_count.isnot(None)) | (TaskBookItem.wrong_count.isnot(None)))
             .all())
    out: dict[str, dict] = defaultdict(lambda: {"correct": 0, "wrong": 0, "rows": 0})
    for it in items:
        if it.book is None or it.book.type != BookType.BRANS_DENEMESI or it.book.subject is None:
            continue
        b = out[_canon(it.book.subject.name)]
        b["correct"] += int(it.correct_count or 0)
        b["wrong"] += int(it.wrong_count or 0)
        b["rows"] += 1
    return out


def _stdev(vals: list[float]) -> float:
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return (sum((v - m) ** 2 for v in vals) / (n - 1)) ** 0.5


def _penalty(section: str | None) -> int:
    return 3 if (section or "").lower() == "lgs" else 4


def _series_metrics(points: list[dict], section: str | None = None) -> dict:
    """points: kronolojik (eski → yeni)."""
    pcts = [p["net_pct"] for p in points if p["net_pct"] is not None]
    c = sum(p["correct"] for p in points)
    w = sum(p["wrong"] for p in points)
    b = sum(p["blank"] for p in points)
    q = sum(p["questions"] for p in points if p["questions"])
    timed = [p for p in points if p["duration_minutes"] and p["questions"]]
    out: dict = {
        "count": len(points),
        "correct": c, "wrong": w, "blank": b,
        "accuracy_pct": _pct(c, c + w),
        "blank_rate_pct": _pct(b, q),
        "avg_net_pct": round(sum(pcts) / len(pcts), 1) if pcts else None,
        "last_net_pct": pcts[-1] if pcts else None,
        "min_per_question": (round(sum(p["duration_minutes"] for p in timed)
                                   / sum(p["questions"] for p in timed), 2) if timed else None),
        "timed_count": len(timed),
        "normal_low": None, "normal_high": None, "last_position": None,
        "decline_run": _decline_run(pcts),
        "slope": None, "direction": None, "projected_net_pct": None,
    }
    # --- Ek açılar (2026-10-20, branş analizi yeniden tasarımı) ---
    pen = _penalty(section)
    n = len(points)
    with_pct = [p for p in points if p["net_pct"] is not None]
    if with_pct:
        best = max(with_pct, key=lambda p: p["net_pct"])
        worst = min(with_pct, key=lambda p: p["net_pct"])
        out["best_net_pct"], out["best_date"] = best["net_pct"], best["date"]
        out["worst_net_pct"], out["worst_date"] = worst["net_pct"], worst["date"]
    else:
        out["best_net_pct"] = out["best_date"] = out["worst_net_pct"] = out["worst_date"] = None
    # İstikrar: eğilim doğrusundan sapmaların standart sapması (≥3 deneme). Yükselen ya da
    # düşen ama düzenli giden seri "tutarlı" sayılır; zikzak çizen seri "dalgalı".
    if len(pcts) >= 3:
        sl_all = _slope(pcts)
        mean_x = (len(pcts) - 1) / 2
        mean_y = sum(pcts) / len(pcts)
        resid = [y - (mean_y + sl_all * (x - mean_x)) for x, y in enumerate(pcts)]
        sd = round(_stdev(resid), 1)
        out["stdev_net_pct"] = sd
        out["consistency"] = "high" if sd < 6 else ("mid" if sd < 12 else "low")
    else:
        out["stdev_net_pct"] = None
        out["consistency"] = None
    # İvme: son k (en çok 3) denemenin ortalaması − ondan önceki k denemenin ortalaması
    if len(pcts) >= 4:
        k = min(3, len(pcts) // 2)
        recent, prev = pcts[-k:], pcts[-2 * k:-k]
        out["momentum"] = round(sum(recent) / k - sum(prev) / k, 1)
        out["momentum_window"] = k
    else:
        out["momentum"] = None
        out["momentum_window"] = None
    # Kaçan net: tam puan (soru) − net = yanlış × (1 + 1/ceza) + boş
    out["penalty"] = pen
    out["avg_net"] = round(sum(p["net"] for p in points) / n, 2) if n else None
    out["avg_questions"] = round(q / n, 1) if n and q else None
    out["lost_wrong_per_exam"] = round(w * (1 + 1 / pen) / n, 2) if n else None
    out["lost_blank_per_exam"] = round(b / n, 2) if n else None
    # Sıklık
    dates = sorted(date.fromisoformat(p["date"]) for p in points)
    out["first_date"] = dates[0].isoformat() if dates else None
    out["last_date"] = dates[-1].isoformat() if dates else None
    out["avg_gap_days"] = (round((dates[-1] - dates[0]).days / (len(dates) - 1), 1)
                           if len(dates) >= 2 else None)

    if len(pcts) >= MIN_NORMAL_POINTS:
        lo, hi = _quartiles(pcts)
        out["normal_low"], out["normal_high"] = lo, hi
        last = pcts[-1]
        out["last_position"] = "below" if last < lo else ("above" if last > hi else "within")
    if len(pcts) >= 2:
        window = pcts[-TREND_WINDOW:]
        sl = _slope(window)
        out["slope"] = round(sl, 2)
        out["direction"] = "flat" if abs(sl) < FLAT_SLOPE else ("up" if sl > 0 else "down")
        if len(pcts) >= MIN_TREND_POINTS:
            base = sum(window) / len(window) + sl * ((len(window) - 1) / 2 + PROJECT_AHEAD)
            out["projected_net_pct"] = round(max(0.0, min(100.0, base)), 1)
    return out


WEEKS_BACK = 8


def _overview(branch: list[dict], today: date) -> dict:
    """Branş serilerinin tümü üzerinden kuşbakışı: toplamlar, sıralamalar, haftalık sıklık."""
    c = sum(r["correct"] for r in branch)
    w = sum(r["wrong"] for r in branch)
    b = sum(r["blank"] for r in branch)
    q = sum((p["questions"] or 0) for r in branch for p in r["points"])
    lost_w = sum(r["wrong"] * (1 + 1 / r["penalty"]) for r in branch)
    ranked = [r for r in branch if r["avg_net_pct"] is not None and r["count"] >= 2]

    def pick(rows: list[dict], key, reverse: bool) -> dict | None:
        rows = [r for r in rows if key(r) is not None]
        if not rows:
            return None
        r = sorted(rows, key=key, reverse=reverse)[0]
        return {"key": r["key"], "label": r["label"], "value": key(r)}

    trending = [r for r in branch if r["count"] >= 3]
    steady = [r for r in branch if r["stdev_net_pct"] is not None]
    monday = today - timedelta(days=today.weekday())
    weeks = []
    for i in range(WEEKS_BACK - 1, -1, -1):
        ws = monday - timedelta(days=7 * i)
        we = ws + timedelta(days=6)
        hits = [(r["key"], p) for r in branch for p in r["points"]
                if ws <= date.fromisoformat(p["date"]) <= we]
        pcts = [p["net_pct"] for _, p in hits if p["net_pct"] is not None]
        weeks.append({
            "week_start": ws.isoformat(), "count": len(hits),
            "subjects": len({k for k, _ in hits}),
            "avg_net_pct": round(sum(pcts) / len(pcts), 1) if pcts else None,
        })
    return {
        "exams": sum(r["count"] for r in branch),
        "subjects": len(branch),
        "questions": q,
        "correct": c, "wrong": w, "blank": b,
        "accuracy_pct": _pct(c, c + w),
        "blank_rate_pct": _pct(b, q),
        "avg_net_pct": (round(sum(r["avg_net_pct"] for r in ranked) / len(ranked), 1) if ranked else None),
        "lost_wrong": round(lost_w, 1),
        "lost_blank": b,
        "strongest": pick(ranked, lambda r: r["avg_net_pct"], True),
        "weakest": pick(ranked, lambda r: r["avg_net_pct"], False) if len(ranked) >= 2 else None,
        "rising": pick([r for r in trending if (r["slope"] or 0) >= FLAT_SLOPE], lambda r: r["slope"], True),
        "falling": pick([r for r in trending if (r["slope"] or 0) <= -FLAT_SLOPE], lambda r: r["slope"], False),
        "steadiest": pick(steady, lambda r: r["stdev_net_pct"], False),
        "weeks": weeks,
    }


def build_deneme_analysis(db: Session, student: User, *, today: date | None = None) -> dict:
    today = today or date.today()
    since = today - timedelta(days=KIYAS_GUN)

    recs = (db.query(ExamResult)
            .filter(ExamResult.student_id == student.id, ExamResult.import_source == SOURCE_TASK)
            .all())
    # Aynı gündeki denemeler "1., 2. deneme" sırasıyla: kalem id'si (köprü kayıtları
    # flush sırasına göre rastgele id alabilir — kayıt id'sine güvenilmez).
    recs.sort(key=lambda r: (r.exam_date, r.task_book_item_id or 0, r.id))
    item_ids = [r.task_book_item_id for r in recs if r.task_book_item_id]
    items = ({it.id: it for it in db.query(TaskBookItem).filter(TaskBookItem.id.in_(item_ids)).all()}
             if item_ids else {})

    series: dict[str, dict] = {}
    for r in recs:
        sc = exam_scope.exam_scope(r)
        it = items.get(r.task_book_item_id)
        qn = (it.question_count if it is not None and it.question_count else None) \
            or (r.total_correct + r.total_wrong + r.total_blank) or None
        s = series.setdefault(sc.series_key, {
            "key": sc.series_key, "label": sc.series_label, "kind": sc.kind,
            "subject": sc.subject, "section": exam_scope.section_of_key(sc.series_key), "points": [],
        })
        s["points"].append({
            "exam_id": r.id, "date": r.exam_date.isoformat(), "title": r.title,
            "net": round(r.net, 2), "questions": qn,
            "net_pct": _pct(r.net, qn) if qn else None,
            "correct": r.total_correct, "wrong": r.total_wrong, "blank": r.total_blank,
            "duration_minutes": it.duration_minutes if it is not None else None,
        })

    # Sonucu bekleyen (çözüldü, D/Y yok) — ders bazında
    pend_items = (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
                  .options(joinedload(TaskBookItem.book).joinedload(Book.subject),
                           joinedload(TaskBookItem.exam_subject))
                  .filter(Task.student_id == student.id, Task.is_draft.is_(False),
                          TaskBookItem.exam_kind.isnot(None), TaskBookItem.completed_count > 0)
                  .all())
    pending_by_subject: dict[str, int] = defaultdict(int)
    pending_total = 0
    for it in pend_items:
        if not result_pending(it):
            continue
        pending_total += 1
        subj = item_subject(it)
        pending_by_subject[_canon(subj.name) if subj else "Genel"] += 1

    tests = _accuracy_by_subject_tests(db, student.id, since)
    karne = _accuracy_by_subject_karne(db, student.id, since)
    legacy = _legacy_by_subject(db, student.id)

    out_series: list[dict] = []
    flags: list[dict] = []
    for s in series.values():
        m = _series_metrics(s["points"], s["section"])
        m["days_since_last"] = ((today - date.fromisoformat(m["last_date"])).days
                                if m.get("last_date") else None)
        row = {k: s[k] for k in ("key", "label", "kind", "subject", "section")}
        row.update(m)
        row["points"] = s["points"]
        canon = s["subject"] if s["kind"] == "brans" else None
        row["pending"] = pending_by_subject.get(canon, 0) if canon else 0
        if canon:
            t = tests.get(canon)
            if t and t["correct"] + t["wrong"] >= MIN_COMPARE_ANSWERED:
                row["test_accuracy_pct"] = _pct(t["correct"], t["correct"] + t["wrong"])
                row["test_answered"] = t["correct"] + t["wrong"]
            g = karne.get(canon)
            if g and g["correct"] + g["wrong"] >= MIN_COMPARE_ANSWERED:
                row["genel_accuracy_pct"] = _pct(g["correct"], g["correct"] + g["wrong"])
                row["genel_exams"] = g["exams"]
            lg = legacy.get(canon)
            if lg and lg["correct"] + lg["wrong"] > 0:
                row["legacy_rows"] = lg["rows"]
                row["legacy_accuracy_pct"] = _pct(lg["correct"], lg["correct"] + lg["wrong"])
                cc, ww = m["correct"] + lg["correct"], m["wrong"] + lg["wrong"]
                row["combined_accuracy_pct"] = _pct(cc, cc + ww)
        row.setdefault("test_accuracy_pct", None)
        row.setdefault("genel_accuracy_pct", None)
        row.setdefault("legacy_accuracy_pct", None)
        out_series.append(row)

        # İşaretler — yargılamaz, koçun bakacağı yeri söyler
        if m["decline_run"] >= DECLINE_FLAG:
            flags.append({"code": "decline", "series": row["key"], "level": "warn",
                          "text": f"{row['label']}: son {m['decline_run'] + 1} denemede net üst üste düştü."})
        if m["last_position"] == "below":
            flags.append({"code": "below_normal", "series": row["key"], "level": "info",
                          "text": f"{row['label']}: son deneme öğrencinin normal aralığının altında "
                                  f"(%{m['last_net_pct']} · normal %{m['normal_low']}–%{m['normal_high']})."})
        if (row["test_accuracy_pct"] is not None and m["accuracy_pct"] is not None
                and row["test_accuracy_pct"] - m["accuracy_pct"] >= GAP_FLAG):
            flags.append({"code": "test_gap", "series": row["key"], "level": "info",
                          "text": f"{row['label']}: testlerde %{row['test_accuracy_pct']} doğru, denemede "
                                  f"%{m['accuracy_pct']} — süre baskısı ya da karma soruda zorlanma olabilir."})
        if m["blank_rate_pct"] is not None and m["blank_rate_pct"] >= BLANK_FLAG * 100 and m["count"] >= 2:
            flags.append({"code": "blank", "series": row["key"], "level": "info",
                          "text": f"{row['label']}: soruların %{m['blank_rate_pct']}'i boş bırakılıyor."})

    out_series.sort(key=lambda r: (r["kind"] != "brans", -r["count"], r["label"]))
    return {
        "overview": _overview([r for r in out_series if r["kind"] == "brans"], today),
        "generated_for": today.isoformat(),
        "compare_days": KIYAS_GUN,
        "summary": {
            "with_result": len(recs),
            "pending": pending_total,
            "series_count": len(out_series),
            "branch_series": sum(1 for r in out_series if r["kind"] == "brans"),
        },
        "series": out_series,
        "flags": flags,
    }
