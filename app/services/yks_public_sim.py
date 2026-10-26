"""Herkese açık YKS net, puan ve sıralama simülasyonu (üyelik gerektirmez).

Kaynak: Etütkoç deneme analiz sistemindeki "YKS Simülasyonu v4"
(yeniDenemeAnalizSistemi/services/yks_simulation.py + yks_score_model.py +
score_rank_predictor.py). Burada veritabanı yerine dışa aktarılmış veriler kullanılır:

  data/yks/yks_score_coefficients.json — netten ÖSYM ham puanı (YÖK Atlas'ta taban puanla
      yerleşen adayların gerçek netleri + OBP'sinden kalibre; 2025 SAY medyan hata 0,5 puan)
  data/yks/yks_rank_tables.json        — yerleştirme puanı → başarı sırası (YÖK Atlas program
      tabanları) + puan düzeyine göre yerleşenlerin medyan OBP katkısı
  data/yks/yks_growth_priors.json      — ders bazında haftalık net eğilimi ve oynaklık (kohort)
  data/yks/yks_calendar.json           — sınav tarihleri

Hesap üç katmandır:
  1. Bugünkü durum: girilen netlerle ham puan ve Türkiye sırası (sınav bugün olsaydı).
  2. Sınav günü tahmini: her ders için seviye + eğim (zaman ağırlıklı, kohort ön bilgisine
     büzülmüş) → sınav gününe projeksiyon → Monte Carlo (4.000 senaryo) → puan ve sıra ARALIĞI.
  3. Belirsizlik: seviye, eğim × kalan hafta, sınav günü oynaklığı, deneme ↔ ÖSYM farkı.

Orijinal motorla birebir aynı sonucu verdiği scripts/test_yks_public_sim.py ile sınanır
(scripts/data_yks_reference_samples.json orijinal motorun cevaplarıdır).
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, timedelta
from functools import lru_cache
from typing import Optional

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "yks")

SCORE_MIN, SCORE_MAX = 100.0, 500.0
OBP_MULTIPLIER = 0.12
DEFAULT_OBP_CONTRIBUTION = 54.0
HALF_LIFE_WEEKS = 8.0
N_SIMS = 4000
DEFAULT_CORRELATION = 0.05
CALIBRATION_SD = {"tyt": 2.5, "ayt": 3.0}
DEFAULT_PRIOR = {"slope": 0.0, "tau": 0.25, "sigma": 4.0}
MAX_DENEMES = 8

TYT_VARS = ("tyt_trk", "tyt_sos", "tyt_mat", "tyt_fen")
GROUPS = {
    "fen": ("fiz", "kim", "bio"),
    "sb1": ("trh1", "cog1"),
    "tdesos1": ("tde", "trh1", "cog1"),
    "sos2": ("trh2", "cog2", "fel", "din"),
}
FIELD_ATOMS = {
    "SAY": ("mat", "fiz", "kim", "bio"),
    "EA": ("mat", "tde", "trh1", "cog1"),
    "SÖZ": ("tde", "trh1", "cog1", "trh2", "cog2", "fel", "din"),
}
FIELD_FEATURE_SETS = {
    "TYT": [()],
    "SAY": [("mat", "fiz", "kim", "bio"), ("mat", "fen")],
    "EA": [("mat", "tde", "trh1", "cog1"), ("mat", "tde", "sb1"), ("mat", "tdesos1")],
    "SÖZ": [
        ("tde", "trh1", "cog1", "trh2", "cog2", "fel", "din"),
        ("tde", "sb1", "trh2", "cog2", "fel", "din"),
        ("tdesos1", "trh2", "cog2", "fel", "din"),
        ("tde", "trh1", "cog1", "sos2"),
        ("tde", "sb1", "sos2"),
        ("tdesos1", "sos2"),
    ],
}
# Simülasyonda kullanılan ders grupları: kohort ön bilgisi (eğim/oynaklık) bu düzeyde ölçülü.
# 13-14 soruluk tek testlere 40 soruluk testin oynaklığını yüklememek için Fizik/Kimya/Biyoloji
# "Fen", Edebiyat + Tarih-1 + Coğrafya-1 "TDE-Sosyal 1", Sosyal-2 testleri "Sosyal 2" olarak
# birlikte simüle edilir (puan modelinde bu ayrıntı düzeyleri de ayrı kalibre).
SIM_GROUPS = {
    "SAY": ("mat", "fen"),
    "EA": ("mat", "tdesos1"),
    "SÖZ": ("tdesos1", "sos2"),
}

# Kullanıcının girdiği testler: kod → (etiket, soru sayısı, oturum)
TESTS = {
    "tyt_trk": ("Türkçe", 40, "TYT"),
    "tyt_sos": ("Sosyal Bilimler", 20, "TYT"),
    "tyt_mat": ("Temel Matematik", 40, "TYT"),
    "tyt_fen": ("Fen Bilimleri", 20, "TYT"),
    "mat": ("Matematik", 40, "AYT"),
    "fiz": ("Fizik", 14, "AYT"),
    "kim": ("Kimya", 13, "AYT"),
    "bio": ("Biyoloji", 13, "AYT"),
    "tde": ("Türk Dili ve Edebiyatı", 24, "AYT"),
    "trh1": ("Tarih-1", 10, "AYT"),
    "cog1": ("Coğrafya-1", 6, "AYT"),
    "trh2": ("Tarih-2", 11, "AYT"),
    "cog2": ("Coğrafya-2", 11, "AYT"),
    "fel": ("Felsefe Grubu", 12, "AYT"),
    "din": ("Din Kültürü ve Ahlak Bilgisi", 6, "AYT"),
}
GROUP_LABELS = {"fen": "Fen Bilimleri (Fizik + Kimya + Biyoloji)",
                "tdesos1": "Edebiyat-Sosyal 1", "sos2": "Sosyal Bilimler 2", "mat": "Matematik"}
FIELD_LABELS = {"TYT": "TYT", "SAY": "Sayısal", "EA": "Eşit Ağırlık", "SÖZ": "Sözel"}


# ─────────────────────────────────────────────────────────────────────────────
# Veri
# ─────────────────────────────────────────────────────────────────────────────

def _load(name: str):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _coefficients():
    return _load("yks_score_coefficients.json")


@lru_cache(maxsize=1)
def _priors_file():
    return _load("yks_growth_priors.json")


@lru_cache(maxsize=1)
def _rank_tables():
    return _load("yks_rank_tables.json")


def atoms_of(var: str) -> set[str]:
    return set(GROUPS.get(var, (var,)))


def max_questions(var: str) -> int:
    if var in TESTS:
        return TESTS[var][1]
    return sum(TESTS[a][1] for a in GROUPS[var])


def compute_net(correct: int, wrong: int) -> float:
    """ÖSYM: dört yanlış bir doğruyu götürür."""
    return max(0.0, correct - wrong / 4.0)


# ─────────────────────────────────────────────────────────────────────────────
# Puan modeli (yks_score_model.compute_score birebir)
# ─────────────────────────────────────────────────────────────────────────────

def _default_year(score_type: str) -> Optional[int]:
    years = sorted(int(y) for y, d in _coefficients()["years"].items() if score_type in d)
    return years[-1] if years else None


def _assign_to_model(inputs: dict, features) -> Optional[dict]:
    assigned = {f: 0.0 for f in features}
    for var, val in inputs.items():
        target = [f for f in features if atoms_of(var) <= atoms_of(f)]
        if len(target) != 1:
            return None
        assigned[target[0]] += val
    return assigned


def _select_model(score_type: str, ayt_inputs: dict, year: int):
    models = _coefficients()["years"].get(str(year), {}).get(score_type, {})
    for fs in FIELD_FEATURE_SETS[score_type]:
        key = "+".join(fs) if fs else "tyt"
        if key not in models:
            continue
        assigned = _assign_to_model(ayt_inputs, fs) if fs else {}
        if assigned is not None:
            return models[key], assigned, key
    return None, None, None


def compute_score(score_type: str, tyt_inputs: dict, ayt_inputs: dict, year: Optional[int] = None):
    year = year or _default_year(score_type)
    if year is None:
        return None
    if score_type != "TYT":
        field = set(FIELD_ATOMS[score_type])
        ayt_inputs = {k: v for k, v in ayt_inputs.items() if atoms_of(k) <= field}
        if sum(v for v in ayt_inputs.values() if v) <= 0:
            return None
    model, assigned, key = _select_model(score_type, ayt_inputs, year)
    if not model:
        return None
    coef = model["coef"]
    tyt_part = sum(coef[v] * float(tyt_inputs.get(v, 0) or 0) for v in TYT_VARS)
    ayt_part = sum(coef[v] * assigned[v] for v in assigned)
    ham = model["intercept"] + tyt_part + ayt_part
    return {"ham": round(min(SCORE_MAX, max(SCORE_MIN, ham)), 5), "base": model["intercept"],
            "coef": coef, "assigned": assigned, "year": year, "model": key,
            "median_abs_err": model["median_abs_err"]}


# ─────────────────────────────────────────────────────────────────────────────
# Puan → sıra (score_rank_predictor population modu birebir)
# ─────────────────────────────────────────────────────────────────────────────

def typical_obp_contribution(score_type: str, ham: float) -> float:
    table = _rank_tables()["obp"].get(score_type) or []
    if not table:
        return DEFAULT_OBP_CONTRIBUTION
    if ham <= table[0][0]:
        return table[0][1]
    if ham >= table[-1][0]:
        return table[-1][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x0 <= ham <= x1:
            return y0 + (y1 - y0) * (ham - x0) / (x1 - x0)
    return DEFAULT_OBP_CONTRIBUTION


def _placement_rank(score_type: str, placement_score: float) -> Optional[int]:
    pts = _rank_tables()["rank"].get(score_type) or []
    if not pts:
        return None
    if placement_score >= pts[0][0]:
        return pts[0][1]
    if placement_score <= pts[-1][0]:
        return pts[-1][1]
    for (s_hi, r_lo), (s_lo, r_hi) in zip(pts, pts[1:]):
        if s_lo <= placement_score <= s_hi:
            if r_lo <= 0 or r_hi <= 0 or s_hi == s_lo:
                return int(r_lo)
            ratio = (s_hi - placement_score) / (s_hi - s_lo)
            return int(round(math.exp(math.log(r_lo) + ratio * (math.log(r_hi) - math.log(r_lo)))))
    return pts[-1][1]


def predict_rank(ham: float, score_type: str, obp_contribution: Optional[float] = None) -> Optional[int]:
    obp = obp_contribution if obp_contribution is not None else typical_obp_contribution(score_type, float(ham))
    return _placement_rank(score_type, float(ham) + obp)


# ─────────────────────────────────────────────────────────────────────────────
# Takvim + ders bazlı seviye/eğim (yks_simulation._fit_var / _project birebir)
# ─────────────────────────────────────────────────────────────────────────────

def _third_saturday_of_june(year: int) -> date:
    d = date(year, 6, 1)
    return d + timedelta(days=(5 - d.weekday()) % 7) + timedelta(days=14)


def next_exam(as_of: date) -> dict:
    for e in sorted(_load("yks_calendar.json")["exams"], key=lambda e: e["date"]):
        d = date.fromisoformat(e["date"])
        if d > as_of:
            return {**e, "date": d}
    year = as_of.year if as_of < _third_saturday_of_june(as_of.year) else as_of.year + 1
    return {"year": year, "date": _third_saturday_of_june(year), "official": False}


def _fit_var(points, as_of: date, prior: dict) -> dict:
    t = np.array([(d - as_of).days / 7.0 for d, _ in points])
    y = np.array([v for _, v in points], float)
    w = 0.5 ** (-t / HALF_LIFE_WEEKS)
    n = len(y)
    p_slope, tau = prior.get("slope", 0.0), max(prior.get("tau", 0.25), 0.05)
    p_sigma = prior.get("sigma", DEFAULT_PRIOR["sigma"])

    def wls(mask):
        W = w[mask]
        X = np.vstack([np.ones(mask.sum()), t[mask]]).T
        XtW = X.T * W
        try:
            return np.linalg.solve(XtW @ X, XtW @ y[mask])
        except np.linalg.LinAlgError:
            return None

    keep = np.ones(n, bool)
    span = (t.max() - t.min()) if n else 0
    beta = None
    if n >= 4 and span >= 6:
        beta = wls(keep)
        if beta is not None:
            res = y - (beta[0] + beta[1] * t)
            mad = np.median(np.abs(res - np.median(res))) * 1.4826
            if mad > 0:
                keep = np.abs(res) <= max(3 * mad, 4.0)
        beta = wls(keep)
    W = w[keep]
    n_eff = float(W.sum() ** 2 / (W ** 2).sum()) if W.sum() > 0 else 0.0
    if beta is None:
        level = float(np.average(y[keep], weights=W)) if keep.any() else 0.0
        resid = y[keep] - level
        dof = max(keep.sum() - 1, 1)
        sigma_own = float(np.sqrt(np.average(resid ** 2, weights=W) * keep.sum() / dof)) if keep.sum() > 1 else p_sigma
        slope, slope_se = p_slope, tau
    else:
        level = float(beta[0])
        resid = y[keep] - (beta[0] + beta[1] * t[keep])
        dof = max(keep.sum() - 2, 1)
        sigma_own = float(np.sqrt(np.average(resid ** 2, weights=W) * keep.sum() / dof))
        tw = np.average(t[keep], weights=W)
        sxx = float(np.sum(W * (t[keep] - tw) ** 2))
        se_raw = sigma_own / math.sqrt(sxx * keep.sum() / W.sum()) if sxx > 0 else 9.9
        se_raw = max(se_raw, 1e-3)  # kusursuz doğrusal veride sıfıra bölmeyi önler
        k = tau ** 2 / (tau ** 2 + se_raw ** 2)
        slope = k * float(beta[1]) + (1 - k) * p_slope
        slope_se = math.sqrt(1 / (1 / tau ** 2 + 1 / se_raw ** 2))
    m = min(keep.sum(), 8)
    sigma = math.sqrt((m * sigma_own ** 2 + 3 * p_sigma ** 2) / (m + 3)) if m else p_sigma
    level_se = sigma / math.sqrt(max(n_eff, 1.0))
    return {"level": level, "slope": slope, "slope_se": slope_se, "sigma": sigma, "level_se": level_se, "n": int(n)}


def _project(level: float, slope: float, weeks: float, max_q: float) -> float:
    gain = slope * weeks
    if gain > 0:
        headroom = max(max_q - level, 0.5)
        gain = headroom * (1 - math.exp(-gain / headroom))
    return min(max_q, max(0.0, level + gain))


# ─────────────────────────────────────────────────────────────────────────────
# Ana fonksiyon
# ─────────────────────────────────────────────────────────────────────────────

class SimulationInputError(ValueError):
    pass


def _clean_nets(nets: dict) -> dict:
    out = {}
    for k, v in (nets or {}).items():
        if k not in TESTS or v is None:
            continue
        v = float(v)
        mq = TESTS[k][1]
        if v < 0 or v > mq:
            raise SimulationInputError(f"{TESTS[k][0]} neti 0 ile {mq} arasında olmalı")
        out[k] = v
    return out


def _sim_vars(nets: dict, score_type: Optional[str]) -> dict:
    """Atom netlerini simülasyon gruplarına topla (TYT + alanın grupları)."""
    out = {v: nets[v] for v in TYT_VARS if v in nets}
    if score_type in SIM_GROUPS:
        for g in SIM_GROUPS[score_type]:
            atoms = atoms_of(g)
            if all(a in nets for a in atoms):
                out[g] = sum(nets[a] for a in atoms)
    return out


def simulate(denemeler: list[dict], score_type: Optional[str], diploma: Optional[float] = None,
             as_of: Optional[date] = None, n_sims: int = N_SIMS, seed: int = 20260619) -> dict:
    """
    denemeler: [{'date': date|None, 'nets': {test_kodu: net}}] — en az bir deneme; tarih yoksa bugün.
    score_type: None (yalnız TYT) | 'SAY' | 'EA' | 'SÖZ'
    diploma: diploma notu (50–100); yoksa aynı puandaki yerleşenlerin tipik OBP'si kullanılır.
    """
    as_of = as_of or date.today()
    if score_type and score_type not in SIM_GROUPS:
        raise SimulationInputError("Alan SAY, EA ya da SÖZ olmalı")
    if not denemeler:
        raise SimulationInputError("En az bir deneme gir")
    if len(denemeler) > MAX_DENEMES:
        raise SimulationInputError(f"En fazla {MAX_DENEMES} deneme girilebilir")
    if diploma is not None and not (50 <= diploma <= 100):
        raise SimulationInputError("Diploma notu 50 ile 100 arasında olmalı")

    rows = []
    for d in denemeler:
        dt = d.get("date") or as_of
        if dt > as_of:
            raise SimulationInputError("Deneme tarihi bugünden ileri olamaz")
        nets = _clean_nets(d.get("nets") or {})
        if nets:
            rows.append((dt, nets))
    if not rows:
        raise SimulationInputError("Netlerini gir")
    rows.sort(key=lambda r: r[0])
    last = rows[-1][1]
    if not all(v in last for v in TYT_VARS):
        raise SimulationInputError("Son denemede dört TYT testinin de netini gir")

    exam = next_exam(as_of)
    weeks = max(0.0, (exam["date"] - as_of).days / 7.0)
    obp_c = round(diploma * 5 * OBP_MULTIPLIER, 2) if diploma else None
    warnings = []

    # 1) Bugünkü durum — son denemenin netleri, en ayrıntılı puan modeli
    tyt_now = {v: last[v] for v in TYT_VARS}
    ayt_now = {k: v for k, v in last.items() if not k.startswith("tyt_")}
    now = {}
    for st in ["TYT"] + ([score_type] if score_type else []):
        r = compute_score(st, tyt_now, ayt_now if st != "TYT" else {})
        if not r:
            if st != "TYT":
                warnings.append(f"{FIELD_LABELS[st]} puanı için AYT netlerini gir")
            continue
        now[st] = {"score": round(r["ham"], 2), "rank": predict_rank(r["ham"], st, obp_c),
                   "placement_score": round(r["ham"] + obp_c, 2) if obp_c else None}

    # 2) Sınav günü — ders bazlı seviye/eğim + Monte Carlo
    priors = _priors_file().get("vars", {})
    corr_cfg = _priors_file().get("corr", {})
    series: dict[str, list] = {}
    for dt, nets in rows:
        for v, val in _sim_vars(nets, score_type).items():
            series.setdefault(v, []).append((dt, val))
    fits, means, sds = {}, {}, {}
    for v, pts in series.items():
        part = "tyt" if v.startswith("tyt_") else "ayt"
        f = _fit_var(pts, as_of, priors.get(v, DEFAULT_PRIOR))
        mq = max_questions(v)
        mu = _project(f["level"], f["slope"], weeks, mq)
        sd = math.sqrt(f["level_se"] ** 2 + (f["slope_se"] * weeks) ** 2 + f["sigma"] ** 2 + CALIBRATION_SD[part] ** 2)
        fits[v], means[v], sds[v] = {**f, "max": mq}, mu, sd

    var_list = list(means)
    k = len(var_list)
    corr = np.eye(k)
    for i in range(k):
        for j in range(k):
            pi = "tyt" if var_list[i].startswith("tyt_") else "ayt"
            pj = "tyt" if var_list[j].startswith("tyt_") else "ayt"
            if i != j and pi == pj:
                val = corr_cfg.get(pi)
                corr[i, j] = DEFAULT_CORRELATION if val is None else max(-0.3, min(0.6, val))
    cov = corr * np.outer([sds[v] for v in var_list], [sds[v] for v in var_list])
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal([means[v] for v in var_list], cov, size=n_sims)
    for i, v in enumerate(var_list):
        draws[:, i] = np.clip(draws[:, i], 0, fits[v]["max"])
    col = {v: draws[:, i] for i, v in enumerate(var_list)}

    def summarize(st):
        tyt_mean = {v: means[v] for v in var_list if v.startswith("tyt_")}
        ayt_mean = {v: means[v] for v in var_list if not v.startswith("tyt_")}
        ref = compute_score(st, tyt_mean, ayt_mean if st != "TYT" else {})
        if not ref:
            return None
        coef = ref["coef"]
        total = np.full(n_sims, ref["base"])
        for v in var_list:
            if v.startswith("tyt_"):
                total = total + coef.get(v, 0) * col[v]
        if st != "TYT":
            for mv in ref["assigned"]:
                for v in var_list:
                    if not v.startswith("tyt_") and atoms_of(v) <= atoms_of(mv):
                        total = total + coef[mv] * col[v]
        sc = np.clip(total, SCORE_MIN, SCORE_MAX)
        q = {p: float(np.percentile(sc, p)) for p in (10, 50, 90)}
        ranks = {p: predict_rank(q[p], st, obp_c) for p in (10, 50, 90)}
        return {"score": {"p10": round(q[10], 1), "p50": round(q[50], 1), "p90": round(q[90], 1)},
                "rank": {"best": ranks[90], "p50": ranks[50], "worst": ranks[10]},
                "score_model_year": ref["year"]}

    forecast = {}
    for st in ["TYT"] + ([score_type] if score_type and score_type in now else []):
        s = summarize(st)
        if s:
            forecast[st] = s

    lessons = []
    for v in var_list:
        f = fits[v]
        lessons.append({
            "key": v, "label": TESTS[v][0] if v in TESTS else GROUP_LABELS.get(v, v), "max": f["max"],
            "current": round(series[v][-1][1], 2), "level": round(f["level"], 1),
            "predicted": round(means[v], 1),
            "p10": round(float(np.percentile(col[v], 10)), 1),
            "p90": round(float(np.percentile(col[v], 90)), 1),
            "weekly_trend": round(f["slope"], 2), "n": f["n"],
        })

    if not exam.get("official"):
        warnings.append(f"Sınav tarihi tahmini ({exam['date'].strftime('%d.%m.%Y')}); ÖSYM takvimi açıklanınca güncellenecek.")
    if not diploma:
        warnings.append("Diploma notu girilmedi: sıralama, aynı puanla yerleşen adayların tipik diploma puanıyla hesaplandı.")
    if len(rows) == 1:
        warnings.append("Tek deneme girildi: tahmin aralığı geniş. Birkaç denemeyi tarihleriyle girersen kendi gidişatın hesaba katılır.")

    return {
        "as_of": as_of.isoformat(),
        "exam_date": exam["date"].isoformat(),
        "exam_year": exam["year"],
        "exam_official": bool(exam.get("official")),
        "weeks_remaining": round(weeks, 1),
        "score_type": score_type,
        "score_type_label": FIELD_LABELS.get(score_type or "TYT"),
        "now": now,
        "forecast": forecast,
        "lessons": lessons,
        "obp_contribution": obp_c,
        "n_denemeler": len(rows),
        "rank_year": _rank_tables()["rank_year"],
        "warnings": warnings,
    }
