"""YKS herkese açık simülasyon — orijinal deneme analiz motoruyla birebir sınama + davranış testleri."""
import json, os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services import yks_public_sim as sim

ok = fail = 0
def check(name, cond, info=""):
    global ok, fail
    if cond: ok += 1; print("  ✓", name)
    else: fail += 1; print("  ✗", name, info)

ref = json.load(open(os.path.join(os.path.dirname(__file__), "data_yks_reference_samples.json"), encoding="utf-8"))
print("1) Sıra tahmini orijinal motorla aynı")
for st, sc, r_typ, r_obp48 in ref["samples"]:
    a, b = sim.predict_rank(sc, st), sim.predict_rank(sc, st, 48.0)
    check(f"{st} {sc}: {a}={r_typ} · {b}={r_obp48}", a == r_typ and b == r_obp48)
print("2) Puan modeli orijinal motorla aynı")
for st, tyt, ayt, ham in ref["score_samples"]:
    r = sim.compute_score(st, tyt, ayt if st != "TYT" else {})
    check(f"{st}: {r['ham']} = {ham}", abs(r["ham"] - ham) < 1e-6)
print("3) Net hesabı")
check("40D 8Y = 38", sim.compute_net(40, 8) == 38.0)
check("negatife düşmez", sim.compute_net(2, 20) == 0.0)
today = date(2026, 10, 26)
base = {"tyt_trk": 30, "tyt_sos": 14, "tyt_mat": 25, "tyt_fen": 12, "mat": 22, "fiz": 8, "kim": 7, "bio": 8}
print("4) Simülasyon")
r = sim.simulate([{"date": today, "nets": base}], "SAY", as_of=today)
check("bugünkü SAY puanı modelle aynı", abs(r["now"]["SAY"]["score"] - ref["score_samples"][1][3]) < 0.01, r["now"])
check("sınav 2027-06-19", r["exam_date"] == "2027-06-19")
f = r["forecast"]["SAY"]
check("aralık sıralı p10<p50<p90", f["score"]["p10"] < f["score"]["p50"] < f["score"]["p90"], f)
check("sıra: en iyi < medyan < en kötü", f["rank"]["best"] < f["rank"]["p50"] < f["rank"]["worst"], f["rank"])
check("Fen grubu simüle edildi", any(l["key"] == "fen" for l in r["lessons"]))
r2 = sim.simulate([{"date": today, "nets": base}], "SAY", as_of=today)
check("deterministik (aynı tohum)", r2["forecast"] == r["forecast"])
# yükselen gidişat → tahmin bugünden yüksek
trend = []
for i, w in enumerate((-20, -15, -10, -5, 0)):
    n = dict(base); n["tyt_mat"] = 15 + i * 3 + (0.5 if i % 2 else -0.5); n["mat"] = 12 + i * 3 + (0.75 if i % 2 else 0)
    trend.append({"date": today + timedelta(weeks=w), "nets": n})
r3 = sim.simulate(trend, "SAY", as_of=today)
mat = next(l for l in r3["lessons"] if l["key"] == "mat")
check("yükselen gidişat pozitif eğilim", mat["weekly_trend"] > 0, mat)
check("diploma verilince yerleştirme puanı", sim.simulate([{"date": today, "nets": base}], "SAY", diploma=85, as_of=today)["now"]["SAY"]["placement_score"] is not None)
print("5) Girdi kontrolleri")
for bad, desc in (({"tyt_trk": 41}, "soru sayısı aşımı"), ({"tyt_trk": 30}, "eksik TYT testi")):
    try: sim.simulate([{"date": today, "nets": bad}], None, as_of=today); check(desc, False)
    except sim.SimulationInputError: check(desc + " reddedildi", True)
try: sim.simulate([{"date": today + timedelta(days=3), "nets": base}], "SAY", as_of=today); check("ileri tarih", False)
except sim.SimulationInputError: check("ileri tarih reddedildi", True)
rt = sim.simulate([{"date": today, "nets": {k: base[k] for k in sim.TYT_VARS}}], None, as_of=today)
check("yalnız TYT çalışır", "TYT" in rt["forecast"] and len(rt["forecast"]) == 1)
re = sim.simulate([{"date": today, "nets": {**{k: base[k] for k in sim.TYT_VARS}, "mat": 20, "tde": 15, "trh1": 6, "cog1": 4}}], "EA", as_of=today)
check("EA çalışır", "EA" in re["forecast"], re["warnings"])
rs = sim.simulate([{"date": today, "nets": {**{k: base[k] for k in sim.TYT_VARS}, "tde": 18, "trh1": 7, "cog1": 4, "trh2": 7, "cog2": 7, "fel": 8, "din": 5}}], "SÖZ", as_of=today)
check("SÖZ çalışır", "SÖZ" in rs["forecast"])
print(f"\n{ok}/{ok+fail} geçti"); sys.exit(1 if fail else 0)
