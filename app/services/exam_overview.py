"""Deneme analizi · GENEL BAKIŞ — tek merkez (2026-10-20, yeniden tasarım).

Koç toplantısının soru sırasıyla tek paket: son deneme (kaçan net ayrıştırması) →
gidişat (normal aralık, eğim, tahmin, yorum) → ders × deneme tablosu (tam puana oran +
satır okuması) → net fırsatı / unutulan / gelişen (konu analizi) → konu × deneme ısı
haritası → sınav davranışı → puan tahmini → seans gündemi.

Hesap YENİ DEĞİL: net/seri/konu/puan mevcut servislerden (exam_scope,
build_progress_report, build_exam_topic_analysis, score_estimate) gelir; burada yalnız
birleştirilir ve kural tabanlı Türkçe okumalar üretilir (yapay zekâ YOK, kredi düşmez).
Canlı veriyle doğrulama: scripts/test_exam_overview.py (canlı fikstür).
"""
from __future__ import annotations

from statistics import median

from sqlalchemy.orm import Session

from app.models import ExamResult, User
from app.models.curriculum import EXAM_SECTION_LABELS
from app.models.exam_result import ExamSection, analysis_exam_filter, section_penalty
from app.services import exam_scope

TOP_OPPORTUNITIES = 6
HEATMAP_TOPICS = 10
MAX_AGENDA = 4
BAND_MIN_EXAMS = 4       # normal aralık (çeyrekler arası bant) için en az deneme
DROP_EXPLAIN_MIN = 3.0   # bu kadar net düşüşte "neden" cümlesi kurulur
TRIM_OTHERS_AFTER = 4    # kaçan net listesinde ilk N ders, gerisi "diğer"


def _fmt(v: float | None, plus: bool = False) -> str:
    if v is None:
        return "—"
    s = f"{v:+.2f}" if plus else f"{v:.2f}"
    s = s.rstrip("0").rstrip(".") if "." in s else s
    return s.replace(".", ",").replace("-", "−")


def _short_date(iso: str) -> str:
    months = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
    y, m, d = iso.split("-")
    return f"{int(d)} {months[int(m) - 1]}"


# ---------------------------------------------------------------- Türkçe ekler
_VOW = "aıoueiöü"
_HARD = "fstkçşhp"
_DIG = {1: "bir", 2: "iki", 3: "üç", 4: "dört", 5: "beş", 6: "altı", 7: "yedi", 8: "sekiz", 9: "dokuz"}
_TENS = {1: "on", 2: "yirmi", 3: "otuz", 4: "kırk", 5: "elli", 6: "altmış", 7: "yetmiş", 8: "seksen", 9: "doksan"}


def _spoken_tail(text: str) -> str:
    """Ekin uyacağı son okunuş: "39" → "dokuz", "%40" → "kırk", "Fizik" → "fizik"."""
    import re
    m = re.search(r"(\d+)(?:[.,](\d+))?\D*$", text)
    if m and text.rstrip()[-1:].isdigit():
        if m.group(2):
            return _spoken_tail(m.group(2))
        n = int(m.group(1))
        if n == 0:
            return "sıfır"
        if n % 1000 == 0:
            return "bin"
        if n % 100 == 0:
            return "yüz"
        if n % 10 == 0:
            return _TENS[(n % 100) // 10]
        return _DIG[n % 10]
    return text.lower()


def tr_ek(text: str, kind: str) -> str:
    """Kesme işaretli ek: tr_ek("39", "acc") → "39'u"; tr_ek("Geometri", "loc") → "Geometri'de".
    kind: acc (-ı), loc (-de), dat (-e)."""
    w = _spoken_tail(text)
    last_v = next((ch for ch in reversed(w) if ch in _VOW), "e")
    ends_vowel = w[-1:] in _VOW
    hard = w[-1:] in _HARD
    if kind == "loc":
        sfx = ("t" if hard else "d") + ("a" if last_v in "aıou" else "e")
    elif kind == "dat":
        sfx = ("y" if ends_vowel else "") + ("a" if last_v in "aıou" else "e")
    else:
        v = {"a": "ı", "ı": "ı", "o": "u", "u": "u", "e": "i", "i": "i", "ö": "ü", "ü": "ü"}[last_v]
        sfx = ("y" if ends_vowel else "") + v
    return f"{text}'{sfx}"


def _quartiles(vals: list[float]) -> tuple[float, float]:
    s = sorted(vals)
    n = len(s)
    return float(median(s[: n // 2])), float(median(s[(n + 1) // 2:]))


def _subject_rows(exam: ExamResult) -> list[dict]:
    from app.services.exam_progress import _subject_rows as rows
    return rows(exam)


def _clean_name(name: str) -> str:
    for p in ("TYT ", "AYT ", "LGS "):
        if name.startswith(p):
            return name[len(p):]
    return name


def _is_optional(name: str) -> str | None:
    k = name.lower()
    if "seçmeli" in k or "secmeli" in k:
        return "secmeli"
    if "din" in k:
        return "din"
    return None


def _effective_rows(exam: ExamResult) -> list[dict]:
    """Ders satırları; TYT seçmeli blokta (Din ↔ Seçmeli Felsefe) GİRİLMEYEN, tamamı boş
    taraf düşer — 5 bilinçli boş davranış ve kayıp analizini şişirmesin (canlı denetim:
    Yağmur, 2 denemede "Seçmeli Felsefe 5 boş")."""
    rows = _subject_rows(exam)
    if exam.section != ExamSection.TYT:
        return rows
    opt = {_is_optional(r["name"]): r for r in rows if _is_optional(r["name"])}
    if len(opt) < 2:
        return rows
    drop = [r for r in opt.values()
            if int(r.get("correct") or 0) == 0 and int(r.get("wrong") or 0) == 0 and int(r.get("blank") or 0) > 0]
    if len(drop) == 1:
        return [r for r in rows if r is not drop[0]]
    return rows


def build_exam_overview(db: Session, student: User, *, series: str | None = None,
                        period: str | None = None) -> dict:
    from app.services import grade_period_service
    from app.services.exam_faz3 import score_estimate
    from app.services.exam_progress import build_progress_report
    from app.services.exam_topic_analysis import build_exam_topic_analysis

    win = grade_period_service.resolve_window(db, student.id, period)
    q = db.query(ExamResult).filter(ExamResult.student_id == student.id, analysis_exam_filter())
    if win.start is not None:
        q = q.filter(ExamResult.exam_date >= win.start)
    if win.end is not None:
        q = q.filter(ExamResult.exam_date <= win.end)
    all_exams = q.order_by(ExamResult.exam_date.asc(), ExamResult.id.asc()).all()
    options = exam_scope.series_options(all_exams)
    skey = exam_scope.resolve_series(series, options)
    opt = next((o for o in options if o["value"] == skey), None)
    exams = [e for e in all_exams if exam_scope.in_series(e, skey)]
    out: dict = {
        "series": skey, "series_label": opt["label"] if opt else None, "series_options": options,
        "is_general": exam_scope.is_general_key(skey), "count": len(exams),
        "period": grade_period_service.build_filter_meta(db, student.id, win),
        "last": None, "loss": None, "trend": None, "subjects": [], "topics": None,
        "behavior": None, "score": None, "agenda": [],
    }
    if not exams:
        return out
    sec = exams[-1].section
    pen = section_penalty(sec)
    last = exams[-1]
    prev = exams[-2] if len(exams) >= 2 else None

    # ---------------------------------------------------------------- 1 son deneme
    qn_last = last.total_correct + last.total_wrong + last.total_blank
    prev_best = max((e.net for e in exams[:-1]), default=None)
    out["last"] = {
        "id": last.id, "title": last.title, "date": last.exam_date.isoformat(),
        "section_label": EXAM_SECTION_LABELS[sec], "net": round(last.net, 2),
        "correct": last.total_correct, "wrong": last.total_wrong, "blank": last.total_blank,
        "questions": qn_last, "penalty": pen,
        "delta": round(last.net - prev.net, 2) if prev else None,
        "prev_net": round(prev.net, 2) if prev else None,
        "is_record": prev_best is not None and last.net > prev_best,
        "avg_last3": round(sum(e.net for e in exams[-3:]) / len(exams[-3:]), 2),
        "karne_score": None, "estimate": None, "calibration_mae": None,
    }

    # Kaçan net: tam puana göre — yanlış = 1 + 1/ceza, boş = 1
    wrong_cost = 1 + 1 / pen
    per = []
    for r in _effective_rows(last):
        c, w, b = int(r.get("correct") or 0), int(r.get("wrong") or 0), int(r.get("blank") or 0)
        lw, lb = round(w * wrong_cost, 2), float(b)
        if lw + lb <= 0:
            continue
        per.append({"name": _clean_name(r["name"]), "lost_wrong": lw, "lost_blank": lb,
                    "lost": round(lw + lb, 2), "wrong": w, "blank": b, "questions": c + w + b})
    per.sort(key=lambda x: (-x["lost"], x["name"]))
    lost_w = round(last.total_wrong * wrong_cost, 2)
    lost_b = float(last.total_blank)
    loss = {"total": round(lost_w + lost_b, 2), "from_wrong": lost_w, "from_blank": lost_b,
            "wrong_cost": round(wrong_cost, 4), "subjects": per[:TRIM_OTHERS_AFTER], "others": None,
            "note": None}
    rest = per[TRIM_OTHERS_AFTER:]
    if rest:
        loss["others"] = {"count": len(rest), "lost_wrong": round(sum(x["lost_wrong"] for x in rest), 2),
                          "lost_blank": round(sum(x["lost_blank"] for x in rest), 2),
                          "lost": round(sum(x["lost"] for x in rest), 2)}
    if per and loss["total"] > 0:
        top = per[0]
        share = round(100 * top["lost"] / loss["total"])
        note = f"Kaybın {tr_ek('%' + str(share), 'acc')} {tr_ek(top['name'], 'loc')}"
        blank_topics = _blank_topics(last, top["name"])
        if top["blank"] and blank_topics:
            note += f"; boşlar: {', '.join(blank_topics[:3])}."
        elif top["blank"]:
            note += f"; {top['blank']} soru boş."
        else:
            note += "; kayıp yanlıştan."
        loss["note"] = note
    out["loss"] = loss

    # ---------------------------------------------------------------- 2 gidişat
    rep = build_progress_report(db, student, section=skey, period=period)
    stats = rep.get("stats") or {}
    nets = [round(e.net, 2) for e in exams]
    points = [{"id": e.id, "date": e.exam_date.isoformat(), "label": _short_date(e.exam_date.isoformat()),
               "net": round(e.net, 2), "correct": e.total_correct, "wrong": e.total_wrong,
               "blank": e.total_blank, "title": e.title} for e in exams]
    band = _quartiles(nets) if len(nets) >= BAND_MIN_EXAMS else (None, None)
    slope = stats.get("slope")
    projection = round(nets[-1] + slope, 2) if slope is not None else None
    if projection is not None and qn_last:
        projection = min(projection, float(qn_last))
    readings = _trend_readings(exams, nets, slope, pen)
    out["trend"] = {
        "points": points, "first_net": nets[0], "last_net": nets[-1], "best_net": max(nets),
        "worst_net": min(nets), "avg_net": round(sum(nets) / len(nets), 2), "slope": slope,
        "projection": projection, "band_low": band[0], "band_high": band[1],
        "target": (rep.get("target") or {}).get("target_net") if rep.get("target") else None,
        "readings": readings,
    }

    # ---------------------------------------------------------------- 3 ders × deneme
    out["subjects"] = _subject_matrix(exams, pen)

    # ---------------------------------------------------------------- 4/5 konu analizi
    ta = build_exam_topic_analysis(db, student, section=skey, period=period)
    if ta.get("exams"):
        opps = ta["opportunities"][:TOP_OPPORTUNITIES]
        ids = [x["id"] for x in ta["exams"]]
        heat = []
        for t in ta["topics"][:HEATMAP_TOPICS]:
            cells = {c["exam_id"]: c for c in t["cells"]}
            heat.append({"topic_id": t["topic_id"], "topic_name": t["topic_name"],
                         "subject_name": _clean_name(t["subject_name"]), "total": t["total"],
                         "accuracy": t["accuracy"],
                         "cells": [({"correct": cells[i]["correct"], "total": cells[i]["total"],
                                     "accuracy": cells[i]["accuracy"]} if i in cells else None) for i in ids]})
        out["topics"] = {
            "exams": [{"id": x["id"], "label": _short_date(x["exam_date"]), "date": x["exam_date"]}
                      for x in ta["exams"]],
            "opportunities": [{**o, "subject_name": _clean_name(o["subject_name"])} for o in opps],
            "opportunities_sum": round(sum(o["net_gain_per_exam"] for o in opps), 2),
            "opportunities_total": len(ta["opportunities"]),
            "forgotten": [{k: v for k, v in f.items() if k != "evidence"} | {"subject_name": _clean_name(f["subject_name"])}
                          for f in ta["forgotten"][:5]],
            "improved": [{k: v for k, v in f.items() if k != "evidence"} | {"subject_name": _clean_name(f["subject_name"])}
                         for f in ta["improved"][:5]],
            "heatmap": heat, "analyzed": ta["analyzed_question_count"], "unmatched": ta["unmatched_questions"],
            "pdf_exams": len(ids),
        }

    # ---------------------------------------------------------------- 6 davranış
    out["behavior"] = _behavior(exams)

    # ---------------------------------------------------------------- 7 puan
    if out["is_general"]:
        se = score_estimate(db, student)
        cal = se.get("calibration") or []
        row = next((c for c in cal if c["exam_id"] == last.id), None)
        if row:
            out["last"]["karne_score"] = row["karne_score"]
        if cal:
            out["last"]["calibration_mae"] = round(sum(abs(c["diff"]) for c in cal) / len(cal), 2)
        score = next((s for s in se.get("scores", []) if last.id in s.get("based_on", [])), None)
        if score:
            out["last"]["estimate"] = score["score"]
        out["score"] = {"scores": se.get("scores", []), "calibration": cal, "warnings": se.get("warnings", []),
                        "kind": se.get("kind")}

    # ---------------------------------------------------------------- 8 gündem
    out["agenda"] = _agenda(out)
    return out


def _blank_topics(exam: ExamResult, subject: str) -> list[str]:
    from app.models.exam_result import EQ_RESULT_BOS
    names: list[str] = []
    for q in exam.questions or []:
        if q.result != EQ_RESULT_BOS or q.topic is None:
            continue
        sn = _clean_name(q.topic.subject.name) if q.topic.subject else ""
        if sn == subject and q.topic.name not in names:
            names.append(q.topic.name)
    return names


def _trend_readings(exams: list[ExamResult], nets: list[float], slope: float | None, pen: int) -> list[dict]:
    out: list[dict] = []
    if len(nets) >= 2:
        if slope is not None and slope >= 1:
            out.append({"tone": "good", "title": "Yükseliş düzenli.",
                        "text": f"Son denemelerin eğilimi deneme başına {_fmt(slope, True)} net; böyle sürerse "
                                f"sonraki deneme ~{_fmt(round(nets[-1] + slope))} net."})
        elif slope is not None and slope <= -1:
            out.append({"tone": "warn", "title": "Düşüş eğilimi.",
                        "text": f"Son denemelerde deneme başına {_fmt(slope, True)} net."})
        elif slope is not None:
            out.append({"tone": "info", "title": "Yatay seyir.",
                        "text": f"Netler {_fmt(min(nets))}–{_fmt(max(nets))} aralığında; belirgin eğim yok."})
        # en büyük düşüş + nedeni
        drops = [(nets[i - 1] - nets[i], i) for i in range(1, len(nets)) if nets[i - 1] - nets[i] >= DROP_EXPLAIN_MIN]
        if drops:
            d, i = max(drops)
            a, b = exams[i - 1], exams[i]
            why = _drop_reason(a, b)
            out.append({"tone": "warn", "title": f"{_short_date(b.exam_date.isoformat())} düşüşü {why['kind']}.",
                        "text": f"Net {_fmt(nets[i - 1])} → {_fmt(nets[i])}. {why['text']}"})
        # en çok gelişen dersler
        gains = []
        first_rows = {_clean_name(r['name']): r for r in _effective_rows(exams[0])}
        for r in _effective_rows(exams[-1]):
            n = _clean_name(r["name"])
            if n in first_rows:
                gains.append((float(r.get("net") or 0) - float(first_rows[n].get("net") or 0), n,
                              float(first_rows[n].get("net") or 0), float(r.get("net") or 0)))
        gains = [g for g in sorted(gains, reverse=True) if g[0] >= 3][:2]
        if gains:
            out.append({"tone": "info", "title": "En çok gelişen:",
                        "text": ", ".join(f"{n} {_fmt(f)} → {_fmt(t)} net" for _, n, f, t in gains) + "."})
    return out


def _drop_reason(a: ExamResult, b: ExamResult) -> dict:
    ra = {_clean_name(r["name"]): r for r in _effective_rows(a)}
    best = None
    for r in _effective_rows(b):
        n = _clean_name(r["name"])
        if n not in ra:
            continue
        db_ = int(r.get("blank") or 0) - int(ra[n].get("blank") or 0)
        dw = int(r.get("wrong") or 0) - int(ra[n].get("wrong") or 0)
        dn = float(ra[n].get("net") or 0) - float(r.get("net") or 0)
        if best is None or dn > best[0]:
            best = (dn, n, db_, dw, int(r.get("blank") or 0), int(r.get("wrong") or 0))
    if best is None or best[0] <= 0:
        return {"kind": "genel", "text": "Belirli bir derste yoğunlaşmıyor."}
    dn, n, db_, dw, b, w = best
    if db_ >= dw and db_ > 0:
        return {"kind": "boştan", "text": f"En çok {n} düştü ({_fmt(dn)} net): {b} boş (bir önceki denemede {b - db_}). "
                                          "Bilgi değil süre ya da çekingenlik olabilir."}
    return {"kind": "yanlıştan", "text": f"En çok {n} düştü ({_fmt(dn)} net): {w} yanlış (bir önceki denemede {w - dw})."}


def _subject_matrix(exams: list[ExamResult], pen: int) -> list[dict]:
    order: list[str] = []
    data: dict[str, list[dict | None]] = {}
    qmax: dict[str, int] = {}
    for i, e in enumerate(exams):
        for r in _effective_rows(e):
            n = _clean_name(r["name"])
            if n not in data:
                data[n] = [None] * len(exams)
                order.append(n)
            c, w, b = int(r.get("correct") or 0), int(r.get("wrong") or 0), int(r.get("blank") or 0)
            qn = c + w + b
            qmax[n] = max(qmax.get(n, 0), qn)
            data[n][i] = {"net": round(float(r.get("net") or 0), 2), "correct": c, "wrong": w, "blank": b,
                          "questions": qn, "ratio": round(float(r.get("net") or 0) / qn, 3) if qn else None}
    rows = []
    for n in order:
        cells = data[n]
        present = [c for c in cells if c]
        first, lastc = present[0], present[-1]
        rows.append({
            "name": n, "questions": qmax[n], "cells": cells,
            "change": round(lastc["net"] - first["net"], 2) if len(present) >= 2 else None,
            "reading": _subject_reading(present),
            "blank_share": round(sum(c["blank"] for c in present) / max(1, sum(c["questions"] for c in present)), 3),
            "chronic_blank": (_subject_reading(present) or "").startswith("Her denemede"),
            "total_wrong": sum(c["wrong"] for c in present), "total_blank": sum(c["blank"] for c in present),
        })
    rows.sort(key=lambda r: (-r["questions"], r["name"]))
    return rows


def _subject_reading(cells: list[dict]) -> str:
    """Ders satırının tek cümlelik okuması (kural tabanlı; öncelik sırasıyla)."""
    if not cells:
        return ""
    blanks = [c["blank"] for c in cells]
    wrongs = [c["wrong"] for c in cells]
    qns = [c["questions"] for c in cells]
    ratios = [c["ratio"] for c in cells if c["ratio"] is not None]
    n = len(cells)
    blank_share = sum(blanks) / max(1, sum(qns))
    if n >= 3 and sum(1 for b in blanks if b > 0) >= n - 1 and blank_share >= 0.12:
        pos = sorted(b for b in blanks if b > 0)
        if pos[-1] - pos[0] <= 2:
            rng = f"{pos[0]}–{pos[-1]}" if pos[0] != pos[-1] else f"{pos[0]}"
            return f"Her denemede {rng} boş: girilmeyen konular."
        return (f"Her denemede boş var (ortalama {round(sum(blanks) / n)}, en çok {pos[-1]}): "
                "girilmeyen konular.")
    if sum(blanks) == 0 and sum(wrongs) > 0:
        return "Boş yok, kayıp hep yanlıştan."
    trend = None
    if n >= 4 and len(ratios) >= 4:
        first3, last3 = sum(ratios[:3]) / 3, sum(ratios[-3:]) / 3
        trend = "up" if last3 - first3 >= 0.15 else "down" if first3 - last3 >= 0.15 else None
    spread = (max(ratios) - min(ratios)) if ratios else 0
    if spread >= 0.5:
        if trend == "up":
            return "Dalgalı ama yükselişte."
        if trend == "down":
            return "Dalgalı ve düşüşte; konu bazında bakılmalı."
        lo_i = min(range(len(cells)), key=lambda i: cells[i]["ratio"] if cells[i]["ratio"] is not None else 9)
        return f"Dalgalı; en düşük {_fmt(cells[lo_i]['net'])} net."
    if trend == "up":
        return "Belirgin yükseliş."
    if trend == "down":
        return "Düşüşte; konu bazında bakılmalı."
    if ratios and sum(ratios) / len(ratios) >= 0.8:
        return "Yüksek bantta."
    if spread >= 0.35:
        return "İnişli çıkışlı."
    return "İstikrarlı." if n >= 2 else ""


def _behavior(exams: list[ExamResult]) -> dict:
    agg: dict[str, list[int]] = {}
    for e in exams:
        for r in _effective_rows(e):
            n = _clean_name(r["name"])
            a = agg.setdefault(n, [0, 0, 0])
            a[0] += int(r.get("wrong") or 0)
            a[1] += int(r.get("blank") or 0)
            a[2] += int(r.get("correct") or 0) + int(r.get("wrong") or 0) + int(r.get("blank") or 0)
    rows = []
    for n, (w, b, qn) in agg.items():
        miss = w + b
        if miss == 0:
            continue
        share = w / miss
        tendency = None
        if miss >= 3:
            tendency = "riskli" if share > 0.7 else "cekingen" if share < 0.35 else "dengeli"
        rows.append({"name": n, "wrong": w, "blank": b, "questions": qn, "wrong_share": round(share, 3),
                     "tendency": tendency})
    rows.sort(key=lambda r: (-(r["wrong"] + r["blank"]), r["name"]))
    series = [{"label": _short_date(e.exam_date.isoformat()), "date": e.exam_date.isoformat(),
               "wrong": e.total_wrong, "blank": sum(int(r.get("blank") or 0) for r in _effective_rows(e))
               if _subject_rows(e) else e.total_blank} for e in exams]
    tot_w = sum(r["wrong"] for r in rows)
    tot_b = sum(r["blank"] for r in rows)
    reading = None
    if len(series) >= 2:
        w0, w1 = series[0]["wrong"], series[-1]["wrong"]
        b0, b1 = series[0]["blank"], series[-1]["blank"]
        peak = max(series, key=lambda s: s["blank"])
        reading = f"Yanlış {w0} → {w1}, boş {b0} → {b1}."
        if peak["blank"] > max(b0, b1) + 5:
            reading += f" Boş {peak['label']} tarihinde {tr_ek(str(peak['blank']), 'dat')} çıktı."
    return {"subjects": rows, "series": series, "total_wrong": tot_w, "total_blank": tot_b, "reading": reading}


def _agenda(ov: dict) -> list[dict]:
    items: list[dict] = []
    t = ov.get("topics") or {}
    opps = t.get("opportunities") or []
    wrong_heavy = next((o for o in opps if o["wrong"] >= o["blank"]), None)
    blank_heavy = next((o for o in opps if o["blank"] > o["wrong"] and o is not wrong_heavy), None)
    for o, kind in ((wrong_heavy, "wrong"), (blank_heavy, "blank")):
        if not o:
            continue
        if kind == "wrong":
            text = (f"{o['total']} sorunun {tr_ek(str(o['wrong']), 'acc')} yanlış. Kapanırsa deneme başına "
                    f"{_fmt(o['net_gain_per_exam'], True)} net.")
        else:
            text = (f"{o['total']} sorudan {tr_ek(str(o['blank']), 'acc')} boş: konuya giremiyor. "
                    f"{_fmt(o['net_gain_per_exam'], True)} net/deneme.")
        items.append({"key": f"opp:{o['topic_id']}", "title": o["topic_name"], "subject": o["subject_name"],
                      "text": text, "agenda": f"{o['subject_name']} · {o['topic_name']}: {text}"})
    chronic = max((s for s in ov.get("subjects") or [] if s.get("chronic_blank")),
                  key=lambda s: s["blank_share"], default=None)
    if chronic:
        text = f"{chronic['reading']} Hangi konular olduğunu soru soru göster."
        items.append({"key": f"blank:{chronic['name']}", "title": f"{tr_ek(chronic['name'], 'loc')} girilmeyen konular",
                      "subject": chronic["name"], "text": text, "agenda": f"{chronic['name']}: {text}"})
    if t.get("forgotten"):
        f = t["forgotten"][0]
        text = (f"İlk denemelerde %{round(f['first_accuracy'] * 100)}, son denemelerde "
                f"%{round(f['last_accuracy'] * 100)}. Tekrar programına al.")
        items.append({"key": f"forgot:{f['topic_id']}", "title": f"{f['topic_name']} unutuluyor",
                      "subject": f["subject_name"], "text": text, "agenda": f"{f['topic_name']}: {text}"})
    return items[:MAX_AGENDA]
