"""Deneme analizi Faz 3 — genel ortalama, çeldirici analizi, birleşik puan tahmini.

TEK MERKEZ (koç + öğrenci + yazdırma aynı hesabı kullanır). AI YOK, kredi YOK.

1. Genel ortalama  — karnede katılımcıların ders bazında ortalama neti varsa
   okumada `score_info.averages` olarak gelir (ham ders adıyla); gösterimde
   soru satırlarından öğrencinin ders adlarına eşlenir. Karnede yoksa koç elle
   girer (`analysis_meta.averages_manual`, öncelikli).
2. Çeldirici analizi — (a) öğrencinin kendi işaretleme dağılımı (şık eğilimi,
   yanlışlarda seçilen şık), (b) koçun AYNI denemeye giren öğrencileri (aynı
   tür + tarih + normalize ad) arasında soru bazında en çok seçilen yanlış şık.
3. Puan tahmini — son netlerden YAKLAŞIK ham puan (ÖSYM/MEB katsayı yapısıyla;
   standart puan + OBP hesaba girmez). Karnede puan yazan denemelerde karne
   puanıyla kıyas verilir. Her yüzeyde "tahmini" ibaresi zorunlu.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ExamResult, User
from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection
from app.models.exam_result import (
    EQ_RESULT_BOS,
    EQ_RESULT_DOGRU,
    EQ_RESULT_YANLIS,
    ExamResultQuestion,
)

# ---------------------------------------------------------------- yardımcılar

_TR = str.maketrans("İIÇĞÖŞÜÂÎÛ", "iıçğöşüâîû")


def _key(s: str | None) -> str:
    low = (s or "").translate(_TR).lower()
    low = low.translate(str.maketrans("çğıöşüâîû", "cgiosuaiu"))
    return re.sub(r"[^a-z0-9]+", " ", low).strip()


def _meta(exam: ExamResult) -> dict:
    try:
        m = json.loads(exam.analysis_meta) if exam.analysis_meta else {}
    except ValueError:
        m = {}
    return m if isinstance(m, dict) else {}


def _subject_rows(exam: ExamResult) -> list[dict]:
    try:
        data = json.loads(exam.subject_nets) if exam.subject_nets else []
    except ValueError:
        data = []
    return [d for d in data if isinstance(d, dict) and d.get("name")]


def _num(v) -> float | None:
    try:
        return round(float(str(v).replace(",", ".")), 2) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


# ================================================================ 1. genel ortalama

class Faz3Error(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def averages_for_exam(exam: ExamResult, questions: list[ExamResultQuestion] | None = None) -> dict | None:
    """{label, total, source, subjects: {öğrencinin ders adı: ortalama net}} ya da None."""
    meta = _meta(exam)
    manual = meta.get("averages_manual")
    if isinstance(manual, dict) and (manual.get("subjects") or manual.get("total") is not None):
        return {"label": manual.get("label") or "Genel ortalama", "total": _num(manual.get("total")),
                "source": "manual",
                "subjects": {k: _num(v) for k, v in (manual.get("subjects") or {}).items() if _num(v) is not None}}
    auto = (meta.get("score_info") or {}).get("averages") if isinstance(meta.get("score_info"), dict) else None
    if not isinstance(auto, dict):
        return None
    raw = {k: _num(v) for k, v in (auto.get("subjects") or {}).items() if _num(v) is not None}
    names = [d["name"] for d in _subject_rows(exam)]
    by_key = {_key(n): n for n in names}
    qs = questions if questions is not None else list(exam.questions or [])
    # ham ders adı → öğrencinin ders adı (soru satırlarındaki nihai ders)
    raw_to: dict[str, Counter] = defaultdict(Counter)
    for q in qs:
        final = q.subject.name if q.subject is not None else None
        if final:
            raw_to[_key(q.subject_name_raw)][final] += 1
    out: dict[str, float] = {}
    for rname, val in raw.items():
        target = None
        c = raw_to.get(_key(rname))
        if c:
            cand = c.most_common(1)[0][0]
            target = cand if cand in names else by_key.get(_key(cand))
        target = target or by_key.get(_key(rname))
        if target is None:
            # "Matematik-2" ↔ "AYT Matematik": ad içinde geçen ilk eşleşme
            rk = _key(re.sub(r"[-\d]+$", "", rname))
            target = next((n for n in names if rk and rk in _key(n)), None)
        if target is None:
            continue
        out[target] = round(out.get(target, 0.0) + val, 2)
    if not out and auto.get("total") is None:
        return None
    return {"label": auto.get("label") or "Genel ortalama", "total": _num(auto.get("total")),
            "source": "auto", "subjects": out}


def set_manual_averages(exam: ExamResult, *, label: str | None, total: float | None,
                        subjects: dict[str, float | None] | None) -> dict | None:
    meta = _meta(exam)
    clean = {}
    names = {d["name"] for d in _subject_rows(exam)}
    for k, v in (subjects or {}).items():
        f = _num(v)
        if f is None:
            continue
        if k not in names:
            raise Faz3Error(422, "unknown_subject", f"Bu denemede '{k}' dersi yok.")
        if f < 0 or f > 120:
            raise Faz3Error(422, "invalid_average", "Ortalama net 0-120 arasında olmalı.")
        clean[k] = f
    tot = _num(total)
    if tot is not None and (tot < 0 or tot > 200):
        raise Faz3Error(422, "invalid_average", "Toplam ortalama 0-200 arasında olmalı.")
    if not clean and tot is None:
        meta.pop("averages_manual", None)
    else:
        meta["averages_manual"] = {"label": (label or "").strip()[:60] or "Genel ortalama",
                                   "total": tot, "subjects": clean}
    exam.analysis_meta = json.dumps(meta, ensure_ascii=False)
    return averages_for_exam(exam)


# ================================================================ 2. çeldirici analizi

LETTERS = ["A", "B", "C", "D", "E"]
PEER_MIN = 2          # aynı denemeye giren en az bu kadar BAŞKA öğrenci
PEER_DATE_SLACK = 3   # gün — okul aynı denemeyi farklı günlerde uygulayabilir


def _norm_title(t: str | None) -> str:
    return _key(t)


def _peer_exams(db: Session, exam: ExamResult, coach_id: int | None) -> list[ExamResult]:
    if not coach_id:
        return []
    from datetime import timedelta
    cands = (
        db.query(ExamResult)
        .join(User, User.id == ExamResult.student_id)
        .filter(User.teacher_id == coach_id, ExamResult.id != exam.id,
                ExamResult.student_id != exam.student_id, ExamResult.section == exam.section,
                ExamResult.exam_date >= exam.exam_date - timedelta(days=PEER_DATE_SLACK),
                ExamResult.exam_date <= exam.exam_date + timedelta(days=PEER_DATE_SLACK))
        .all()
    )
    nt = _norm_title(exam.title)
    return [e for e in cands if _norm_title(e.title) == nt and e.questions]


def distractor_analysis(db: Session, exam: ExamResult, *, coach_id: int | None,
                        include_peers: bool = True) -> dict:
    qs = sorted(exam.questions or [], key=lambda q: q.id)
    answered = [q for q in qs if q.student_answer and q.result in (EQ_RESULT_DOGRU, EQ_RESULT_YANLIS)]
    chosen = Counter(q.student_answer.upper() for q in answered if q.student_answer.upper() in LETTERS)
    keyd = Counter(q.correct_answer.upper() for q in qs
                   if q.correct_answer and q.correct_answer.upper() in LETTERS)
    wrong = [q for q in qs if q.result == EQ_RESULT_YANLIS and q.student_answer]
    wrong_chosen = Counter(q.student_answer.upper() for q in wrong if q.student_answer.upper() in LETTERS)
    n_ans = sum(chosen.values())
    n_key = sum(keyd.values())
    letter_rows = []
    for L in LETTERS:
        c, k = chosen.get(L, 0), keyd.get(L, 0)
        letter_rows.append({
            "letter": L, "chosen": c, "key": k, "wrong_chosen": wrong_chosen.get(L, 0),
            "chosen_pct": round(c / n_ans * 100, 1) if n_ans else 0.0,
            "key_pct": round(k / n_key * 100, 1) if n_key else 0.0,
        })
    notes: list[str] = []
    if n_ans >= 20:
        top = max(letter_rows, key=lambda r: r["chosen_pct"] - r["key_pct"])
        if top["chosen_pct"] - top["key_pct"] >= 8:
            notes.append(f"{top['letter']} şıkkını cevap anahtarındaki payından belirgin fazla işaretlemiş "
                         f"(%{str(top['chosen_pct']).replace('.', ',')} ↔ anahtar "
                         f"%{str(top['key_pct']).replace('.', ',')}) — emin olmadığında aynı şıkka yöneliyor olabilir.")
    if len(wrong) >= 5:
        wl, wc = wrong_chosen.most_common(1)[0]
        if wc / len(wrong) >= 0.4:
            notes.append(f"Yanlışlarının %{round(wc / len(wrong) * 100)}'i {wl} şıkkında toplanıyor.")
    # ardışık aynı şık (≥4) — tahmin/rastgele işaretleme izi
    streak, best, best_at = 1, 1, None
    seq = [(q.subject_name_raw, q.question_no, (q.student_answer or "").upper()) for q in qs]
    for i in range(1, len(seq)):
        if seq[i][2] and seq[i][2] == seq[i - 1][2] and seq[i][0] == seq[i - 1][0]:
            streak += 1
            if streak > best:
                best, best_at = streak, seq[i]
        else:
            streak = 1
    if best >= 4 and best_at:
        notes.append(f"{best_at[0]} bölümünde {best} soru üst üste {best_at[2]} işaretlenmiş — "
                     "süre baskısında rastgele işaretleme olabilir.")

    peers = _peer_exams(db, exam, coach_id) if include_peers else []
    questions_out = []
    if peers:
        pmap: dict[tuple[str, int | None], list[ExamResultQuestion]] = defaultdict(list)
        for pe in peers:
            for pq in pe.questions:
                pmap[(_key(pq.subject_name_raw), pq.question_no)].append(pq)
        for q in qs:
            if q.result == EQ_RESULT_DOGRU:
                continue
            pl = pmap.get((_key(q.subject_name_raw), q.question_no), [])
            if not pl:
                continue
            correct_n = sum(1 for p in pl if p.result == EQ_RESULT_DOGRU)
            wrong_opts = Counter((p.student_answer or "").upper() for p in pl
                                 if p.result == EQ_RESULT_YANLIS and p.student_answer)
            top_opt, top_n = (wrong_opts.most_common(1)[0] if wrong_opts else (None, 0))
            questions_out.append({
                "subject": q.subject.name if q.subject else (q.subject_name_raw or ""),
                "question_no": q.question_no,
                "topic": q.topic.name if q.topic else (q.topic_label_raw or None),
                "correct_answer": q.correct_answer,
                "student_answer": q.student_answer,
                "result": q.result,
                "peer_count": len(pl),
                "peer_correct_pct": round(correct_n / len(pl) * 100),
                "top_wrong_option": top_opt,
                "top_wrong_count": top_n,
                "same_as_student": bool(top_opt and q.student_answer and top_opt == q.student_answer.upper()),
            })
        questions_out.sort(key=lambda r: (r["peer_correct_pct"], -(r["top_wrong_count"] or 0)))
    common_traps = [r for r in questions_out if r["same_as_student"] and r["top_wrong_count"] >= 2]
    if common_traps:
        notes.append(f"{len(common_traps)} soruda öğrenci, aynı denemeye giren diğer öğrencilerin de "
                     "en çok düştüğü çeldiriciyi seçmiş — sınıfça konuşulabilecek tuzaklar.")
    return {
        "exam_id": exam.id,
        "answered": n_ans,
        "wrong_count": len(wrong),
        "letters": letter_rows,
        "notes": notes,
        "peer_count": len(peers) if len(peers) >= PEER_MIN else 0,
        "peer_min": PEER_MIN,
        "questions": questions_out if len(peers) >= PEER_MIN else [],
    }


# ================================================================ 3. puan tahmini

# YKS — ÖSYM ham puan yapısı: 100 taban + net × katsayı. TYT puanı tek başına
# TYT netleriyle; alan puanlarında TYT %40, AYT %60 ağırlık (katsayılar bu
# oranla ölçeklenmiştir; her türde tam net = 500). Gerçek puan STANDART
# puandır (ortalama/sapma) + OBP — bu tahmin YAKLAŞIKTIR.
TYT_GROUPS = {"turkce": 3.3, "sosyal": 3.4, "mat": 3.3, "fen": 3.4}
TYT_MAX = {"turkce": 40, "sosyal": 20, "mat": 40, "fen": 20}
AYT_COEF = {
    "SAY": {"mat": 3.0, "fizik": 2.85, "kimya": 3.07, "biyoloji": 3.07},
    "EA": {"mat": 3.0, "edebiyat": 3.0, "tarih": 2.8, "cografya": 3.33},
    "SOZ": {"edebiyat": 3.0, "tarih": 2.85, "cografya": 3.1, "felsefe": 3.0, "din": 3.33},
    "DIL": {"dil": 3.0},
}
AYT_SECTION = {ExamSection.AYT_SAY: "SAY", ExamSection.AYT_EA: "EA",
               ExamSection.AYT_SOZ: "SOZ", ExamSection.AYT_DIL: "DIL"}
AREA_LABEL = {"TYT": "TYT puanı", "SAY": "Sayısal (SAY)", "EA": "Eşit Ağırlık (EA)",
              "SOZ": "Sözel (SÖZ)", "DIL": "Dil (DİL)"}
# LGS — MEB: Türkçe/Mat/Fen katsayı 4, İnkılap/Din/İngilizce 1; 270 ağırlıklı net → 500.
LGS_COEF = {"turkce": 4, "mat": 4, "fen": 4, "inkilap": 1, "din": 1, "ingilizce": 1}
LGS_MAX_WEIGHTED = 270


def _tyt_group(name: str) -> str | None:
    k = _key(name)
    if any(w in k for w in ("turkce", "turk dili", "edebiyat", "paragraf")):
        return "turkce"
    if any(w in k for w in ("matematik", "geometri")):
        return "mat"
    if any(w in k for w in ("fizik", "kimya", "biyoloji", "fen")):
        return "fen"
    if any(w in k for w in ("tarih", "cografya", "felsefe", "din", "sosyal", "mantik", "psikoloji")):
        return "sosyal"
    return None


def _ayt_group(name: str) -> str | None:
    k = _key(name)
    for w, g in (("matematik", "mat"), ("geometri", "mat"), ("fizik", "fizik"), ("kimya", "kimya"),
                 ("biyoloji", "biyoloji"), ("edebiyat", "edebiyat"), ("turk dili", "edebiyat"),
                 ("tarih", "tarih"), ("cografya", "cografya"), ("felsefe", "felsefe"),
                 ("mantik", "felsefe"), ("psikoloji", "felsefe"), ("sosyoloji", "felsefe"),
                 ("din", "din"), ("ingilizce", "dil"), ("almanca", "dil"), ("yabanci", "dil"),
                 ("dil", "dil")):
        if w in k:
            return g
    return None


def _lgs_group(name: str) -> str | None:
    k = _key(name)
    for w, g in (("turkce", "turkce"), ("matematik", "mat"), ("fen", "fen"), ("inkilap", "inkilap"),
                 ("tarih", "inkilap"), ("din", "din"), ("ingilizce", "ingilizce"), ("yabanci", "ingilizce")):
        if w in k:
            return g
    return None


def _group_nets(exam: ExamResult, fn) -> tuple[dict[str, float], list[str]]:
    nets: dict[str, float] = defaultdict(float)
    unknown: list[str] = []
    for d in _subject_rows(exam):
        g = fn(d["name"])
        if g is None:
            unknown.append(d["name"])
            continue
        nets[g] += float(d.get("net") or 0)
    return dict(nets), unknown


def _karne_score(exam: ExamResult) -> float | None:
    info = _meta(exam).get("score_info")
    return _num(info.get("score")) if isinstance(info, dict) else None


def _exam_brief(e: ExamResult) -> dict:
    return {"id": e.id, "title": e.title, "exam_date": e.exam_date.isoformat(),
            "section_label": EXAM_SECTION_LABELS[e.section], "net": round(e.net, 2),
            "karne_score": _karne_score(e)}


def _tyt_score(nets: dict[str, float]) -> float:
    return 100 + sum(min(nets.get(g, 0.0), TYT_MAX[g]) * c for g, c in TYT_GROUPS.items())


def score_estimate(db: Session, student: User) -> dict:
    exams = (db.query(ExamResult).filter(ExamResult.student_id == student.id)
             .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc()).all())
    # 2026-10-06: puan YALNIZ GENEL denemelerden — 20 soruluk branş denemesi tüm
    # sınavın puanını temsil etmez (exam_scope).
    from app.services import exam_scope
    branch_only = {e.section for e in exams if exam_scope.classify(e) == "brans"}
    exams = [e for e in exams if exam_scope.classify(e) == "genel"]
    branch_only -= {e.section for e in exams}
    latest: dict[ExamSection, ExamResult] = {}
    for e in exams:
        latest.setdefault(e.section, e)
    out = {"generated_at": datetime.now(timezone.utc).isoformat(), "kind": None,
           "scores": [], "inputs": [], "calibration": [], "warnings": [],
           "disclaimer": ("Tahmini ham puandır: son denemelerin netleri, ÖSYM/MEB katsayı yapısıyla "
                          "hesaplanır. Gerçek puan standart puan (o yılki ortalama ve sapma) ile "
                          "hesaplanır; YKS'de diploma notu (OBP) da eklenir. Yön göstermek içindir.")}
    if branch_only:
        out["warnings"].append(
            "Branş denemeleri puan tahminine katılmaz; tahmin için "
            + ", ".join(EXAM_SECTION_LABELS[s] for s in sorted(branch_only, key=lambda x: x.value))
            + " genel denemesi girilmeli.")

    if ExamSection.LGS in latest:
        e = latest[ExamSection.LGS]
        nets, unknown = _group_nets(e, _lgs_group)
        weighted = sum(nets.get(g, 0.0) * c for g, c in LGS_COEF.items())
        score = 100 + weighted / LGS_MAX_WEIGHTED * 400
        out["kind"] = "lgs"
        out["scores"].append({"key": "LGS", "label": "LGS puanı", "score": round(min(score, 500), 2),
                              "max": 500, "based_on": [e.id],
                              "detail": f"Ağırlıklı net {weighted:.2f} / {LGS_MAX_WEIGHTED}".replace(".", ",")})
        out["inputs"].append(_exam_brief(e))
        if unknown:
            out["warnings"].append(f"Puana katılamayan dersler: {', '.join(unknown)}.")
        _calibrate(out, exams, ExamSection.LGS, lambda x: 100 + sum(
            _group_nets(x, _lgs_group)[0].get(g, 0.0) * c for g, c in LGS_COEF.items()) / LGS_MAX_WEIGHTED * 400)
        return out

    tyt = latest.get(ExamSection.TYT)
    if tyt is None:
        if any(s in latest for s in AYT_SECTION):
            out["warnings"].append("Alan puanı için TYT denemesi gerekir (puanın %40'ı TYT'den gelir).")
        return out
    out["kind"] = "yks"
    tnets, unknown = _group_nets(tyt, _tyt_group)
    out["inputs"].append(_exam_brief(tyt))
    tscore = _tyt_score(tnets)
    out["scores"].append({"key": "TYT", "label": AREA_LABEL["TYT"], "score": round(tscore, 2), "max": 500,
                          "based_on": [tyt.id],
                          "detail": " · ".join(f"{lbl} {tnets.get(g, 0.0):.2f}".replace(".", ",")
                                               for g, lbl in (("turkce", "Türkçe"), ("sosyal", "Sosyal"),
                                                              ("mat", "Matematik"), ("fen", "Fen")))})
    if unknown:
        out["warnings"].append(f"TYT'de puana katılamayan dersler: {', '.join(unknown)}.")
    _calibrate(out, exams, ExamSection.TYT, lambda x: _tyt_score(_group_nets(x, _tyt_group)[0]))

    tyt_part = (tscore - 100) * 0.4
    track_area = {"sayisal": "SAY", "ea": "EA", "sozel": "SOZ", "dil": "DIL"}.get(
        getattr(student.track, "value", None) or "", "")
    for sec, area in AYT_SECTION.items():
        e = latest.get(sec)
        if e is None:
            continue
        anets, aunk = _group_nets(e, _ayt_group)
        ayt_part = sum(anets.get(g, 0.0) * c for g, c in AYT_COEF[area].items())
        out["inputs"].append(_exam_brief(e))
        out["scores"].append({
            "key": area, "label": AREA_LABEL[area], "score": round(min(100 + tyt_part + ayt_part, 500), 2),
            "max": 500, "based_on": [tyt.id, e.id],
            "detail": f"TYT katkısı {tyt_part:.2f} + AYT katkısı {ayt_part:.2f}".replace(".", ","),
            "is_student_track": track_area == area,
        })
        if aunk:
            out["warnings"].append(f"{EXAM_SECTION_LABELS[sec]} içinde puana katılamayan dersler: {', '.join(aunk)}.")
    if len(out["scores"]) == 1:
        out["warnings"].append("Alan puanı (SAY/EA/SÖZ/DİL) için AYT denemesi girildiğinde birleşik puan hesaplanır.")
    if tyt and any(latest.get(s) for s in AYT_SECTION):
        gap = max(abs((latest[s].exam_date - tyt.exam_date).days) for s in AYT_SECTION if latest.get(s))
        if gap > 45:
            out["warnings"].append(f"Birleşik puandaki TYT ve AYT denemeleri arasında {gap} gün var — "
                                   "yakın tarihli denemelerle daha anlamlı olur.")
    return out


def _calibrate(out: dict, exams: list[ExamResult], section: ExamSection, fn) -> None:
    """Karnede puan yazan denemelerde tahmin ↔ karne puanı kıyası (son 5)."""
    rows = []
    for e in exams:
        if e.section != section:
            continue
        ks = _karne_score(e)
        if ks is None:
            continue
        est = round(fn(e), 2)
        rows.append({"exam_id": e.id, "title": e.title, "exam_date": e.exam_date.isoformat(),
                     "karne_score": ks, "estimate": est, "diff": round(est - ks, 2)})
        if len(rows) >= 5:
            break
    out["calibration"].extend(rows)
