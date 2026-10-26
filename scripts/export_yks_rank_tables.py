import json, sys, os
sys.path.insert(0, '.')
from app import create_app
app = create_app()
with app.app_context():
    from services.score_rank_predictor import get_predictor, typical_obp_contribution, _OBP_TABLE
    from services import yks_score_model as sm
    p = get_predictor()
    out = {'source': 'yeniDenemeAnalizSistemi export', 'rank': {}, 'obp': {}}
    yr = p.latest_year()
    out['rank_year'] = yr
    for st in ('TYT', 'SAY', 'EA', 'SÖZ'):
        it = p._get(st, yr, mode='placement')
        out['rank'][st] = [[s, r] for s, r in zip(it.scores, it.ranks)]
        typical_obp_contribution(st, 300.0)
        out['obp'][st] = [[a, b] for a, b in _OBP_TABLE.get(st, [])]
    # Doğrulama örnekleri: orijinal motorun cevapları
    samples = []
    for st in ('TYT', 'SAY', 'EA', 'SÖZ'):
        for sc in (200, 250, 300, 350, 400, 450, 480):
            samples.append([st, sc, p.predict_population_rank(sc, st), p.predict_population_rank(sc, st, obp_contribution=48.0)])
    out['samples'] = samples
    coef = sm._coefficients()
    out['coef_year'] = {st: sm.default_year(st) for st in ('TYT', 'SAY', 'EA', 'SÖZ')}
    out['score_samples'] = []
    tyt = {'tyt_trk': 30, 'tyt_sos': 14, 'tyt_mat': 25, 'tyt_fen': 12}
    for st, ayt in (('TYT', {}), ('SAY', {'mat': 22, 'fiz': 8, 'kim': 7, 'bio': 8}), ('EA', {'mat': 22, 'tde': 15, 'trh1': 6, 'cog1': 4}),
                    ('SÖZ', {'tde': 18, 'trh1': 7, 'cog1': 4, 'trh2': 7, 'cog2': 7, 'fel': 8, 'din': 5})):
        r = sm.compute_score(st, tyt, ayt)
        out['score_samples'].append([st, tyt, ayt, r['ham']])
    dst = sys.argv[1]
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    print(yr, out['coef_year'], {k: len(v) for k, v in out['rank'].items()}, {k: len(v) for k, v in out['obp'].items()})
    print(samples[:7]); print(out['score_samples'])
