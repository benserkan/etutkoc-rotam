# -*- coding: utf-8 -*-
"""Haftalık raporun VELİ SÜRÜMÜ (2026-08-25) — aynı CoachingReport verisinden
sade, olumlu dilli görünüm.

İlkeler (parent_commentary ile aynı): sade Türkçe, suçlayıcı değil, somut.
Koç gündemi / öğrenci-koç yazışmaları / YSA eleştirisi / "D-Y girilmedi" listesi /
çalışma-ritmi sorgusu veli sürümüne GİRMEZ. Deneme netleri paylaşılır
(2026-06-01 kararı). Tamamlanamayan görevler tek yumuşak cümleye iner.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from app.services.weekly_coach_report import (
    SUBJ_ORDER, _TEMPLATE, _band, _bar, _chip, _esc, d_tr, derive, pct,
)


def build_parent_highlights(d: dict, m: dict | None = None) -> dict:
    """Veli raporunun 'iyi gidenler / birlikte çalışacaklarımız / odak' blokları."""
    m = m or derive(d)
    good = [r for r in m["topics_sorted"] if r["acc"] is not None and r["acc"] >= 85 and r["answered"] >= 20]
    good = sorted(good, key=lambda r: -(r["acc"] or 0))[:4]
    work = [r for r in m["topics_sorted"] if r["acc"] is not None and r["acc"] < 80 and r["answered"] >= 20][:4]
    nxt = [f"{s['name']}: {s.get('next_topic_name')}" for s in m["cur_subj"] if s.get("next_topic_name")][:3]
    carry = len(m["pending"])
    best_day = None
    scored = [((pct(v.get("gorev_done") or 0, v.get("gorev_total") or 0) or 0,
                v.get("gorev_done") or 0), k)
              for k, v in m["days"] if (v.get("gorev_total") or 0) > 0]
    if scored:
        best_day = max(scored)[1]
    return {"good": good, "work": work, "next_topics": nxt, "carry": carry, "best_day": best_day}


def render_parent_html(d: dict) -> str:
    """Veli sürümü HTML'i — koç raporuyla aynı görsel dil, sade içerik."""
    m = derive(d)
    st = d.get("student") or {}
    summ = m["summ"]
    hl = build_parent_highlights(d, m)
    first, last = m["first"], m["last"]
    week_label = f"{d_tr(first, False)} – {d_tr(last, False)} {date.fromisoformat(last).year}"
    coach_name = (st.get("coach") or {}).get("full_name", "")
    first_name = (st.get("full_name") or "Öğrencimiz").split(" ")[0]
    H: list[str] = []

    def stat(label, value, sub="", kind="neutral"):
        return (f'<div class="stat s-{kind}"><div class="stat-l">{_esc(label)}</div><div class="stat-v">{value}</div>'
                f'<div class="stat-s">{_esc(sub)}</div></div>')

    H.append(f"""
<header class="top">
  <div class="eyebrow">Haftalık Veli Raporu</div>
  <h1>{_esc(st.get('full_name'))}</h1>
  <div class="meta">
    <span>Hafta: <b>{_esc(week_label)}</b></span><span class="dot">·</span>
    <span>Koç: {_esc(coach_name)}</span>
  </div>
</header>""")

    gp = m["gorev_pct"]
    worked_txt = ("her gün çalıştı" if m["worked_days"] == len(m["days"])
                  else f"{m['worked_days']} gün çalıştı")
    H.append('<section class="stats">')
    H.append(stat("Program tamamlama", f'<b>%{gp if gp is not None else 0}</b>',
                  f'{summ.get("gorev_done", 0)} / {summ.get("gorev_total", 0)} görev', _band(gp)))
    H.append(stat("Çözülen test", f'<b>{summ.get("test_completed", 0)}</b>',
                  "soru bankası testleri", "good" if summ.get("test_completed", 0) else "neutral"))
    if summ.get("deneme_planned", 0):
        H.append(stat("Branş denemesi", f'<b>{summ.get("deneme_completed", 0)}</b> / {summ.get("deneme_planned", 0)}',
                      " · ".join(sorted({x["subject"] for x in m["denemeler"]})),
                      _band(pct(summ.get("deneme_completed", 0), summ.get("deneme_planned", 0)))))
    if m["acc_all"] is not None:
        H.append(stat("Soru başarısı", f'<b>%{m["acc_all"]}</b>',
                      f'{m["D"]} doğru · {m["Y"]} yanlış', _band(m["acc_all"])))
    H.append(stat("Çalışılan gün", f'<b>{m["worked_days"]}</b> / {len(m["days"])}', worked_txt,
                  "good" if m["worked_days"] == len(m["days"]) else "neutral"))
    H.append('</section>')

    # Bu hafta nasıl geçti? (sıcak özet)
    parts = []
    if gp is not None and gp >= 85:
        parts.append(f"{first_name} bu hafta programına büyük ölçüde sadık kaldı (%{gp})")
    elif gp is not None and gp >= 60:
        parts.append(f"{first_name} bu hafta programının önemli bölümünü tamamladı (%{gp})")
    else:
        parts.append(f"{first_name} bu hafta programının bir kısmını tamamlayabildi (%{gp if gp is not None else 0})")
    if summ.get("test_completed", 0):
        parts.append(f"{summ['test_completed']} test çözdü")
    if m["acc_all"] is not None:
        parts.append(f"çözdüğü sorularda %{m['acc_all']} doğruluk yakaladı")
    if hl["best_day"]:
        parts.append(f"en verimli günü {d_tr(hl['best_day'])} oldu")
    carry_txt = ""
    if hl["carry"]:
        carry_txt = (f" Tamamlanamayan {hl['carry']} görev planlanarak önümüzdeki haftaya "
                     "taşınıyor — bu, sürecin doğal bir parçası.")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Bu hafta nasıl geçti?</h2></div>
  <p class="lede">{_esc("; ".join(parts))}.{_esc(carry_txt)}</p>
</section>""")

    # Haftanın seyri (sade)
    rows = []
    for k, v in m["days"]:
        gt, gd = v.get("gorev_total") or 0, v.get("gorev_done") or 0
        if gt == 0:
            continue
        p = pct(gd, gt)
        extra = f" · {v.get('deneme_completed', 0)} deneme" if v.get("deneme_completed", 0) else ""
        rows.append(f"""<tr><td class="day">{_esc(d_tr(k))}</td><td class="num">{gd} / {gt}</td>
  <td class="barcell">{_bar(p, 'acc', f'%{p}' if p is not None else '—')}</td>
  <td class="num">{v.get('test_completed', 0)} test{_esc(extra)}</td></tr>""")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Haftanın seyri</h2><p>Gün gün görev tamamlama ve çözülen test/deneme.</p></div>
  <div class="tablewrap"><table class="t">
    <thead><tr><th>Gün</th><th class="num">Görev</th><th>Tamamlama</th><th class="num">Çözülen</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table></div>
</section>""")

    # Ders bazlı (sade)
    rows = []
    for name in sorted(m["subj"].keys(), key=lambda n: SUBJ_ORDER.index(n) if n in SUBJ_ORDER else 99):
        s = m["subj"][name]
        rows.append(f"""<tr><td class="lbl">{_esc(name)}</td><td class="num">{s['gorev_done']} / {s['gorev_total']}</td>
  <td class="num">{s['test_completed']} / {s['test_planned']}</td>
  <td class="barcell">{_bar(s['acc'], 'acc', f"%{s['acc']}" if s['acc'] is not None else '—')}</td></tr>""")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Ders bazlı çalışma</h2><p>Soru bankası testleri. "Başarı" = çözülen sorulardaki doğru oranı.</p></div>
  <div class="tablewrap"><table class="t">
    <thead><tr><th>Ders</th><th class="num">Görev</th><th class="num">Test</th><th>Başarı</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="4" class="muted">Bu hafta test çalışması yok.</td></tr>'}</tbody></table></div>
</section>""")

    # Branş denemeleri (netler)
    den_rows = []
    for x in m["denemeler"]:
        if not x["n"]:
            continue
        den_rows.append(f"""<tr><td>{_esc(d_tr(x['date']))}</td><td class="lbl">{_esc(x['subject'])}</td>
  <td class="num">{x['n']}</td><td class="num"><b>{x['net']:.2f}</b></td>
  <td class="barcell">{_bar(x['net_pct'], 'acc', f"%{x['net_pct']}")}</td></tr>""")
    if den_rows:
        trend = []
        by_s: dict = defaultdict(list)
        for x in m["denemeler"]:
            if x["n"]:
                by_s[x["subject"]].append(x)
        for sname, xs in by_s.items():
            if len(xs) >= 2:
                a, b = xs[0], xs[-1]
                delta = b["net"] - a["net"]
                if delta > 0.5:
                    trend.append(f"<li><b>{_esc(sname)}</b> netleri yükselişte: {a['net']:.2f} → {b['net']:.2f}.</li>")
                elif delta < -0.5:
                    trend.append(f"<li><b>{_esc(sname)}</b> bu hafta dalgalandı ({a['net']:.2f} → {b['net']:.2f}); birlikte üzerinde çalışıyoruz.</li>")
        H.append(f"""
<section class="card">
  <div class="card-h"><h2>Branş denemeleri</h2><p>Küçük deneme setlerinin net sonuçları (net = doğru − yanlışın dörtte biri).</p></div>
  <div class="tablewrap"><table class="t">
    <thead><tr><th>Gün</th><th>Ders</th><th class="num">Soru</th><th class="num">Net</th><th>Net oranı</th></tr></thead>
    <tbody>{''.join(den_rows)}</tbody></table></div>
  <ul class="notes">{''.join(trend)}</ul>
</section>""")

    # İyi gidenler / birlikte çalışacaklarımız
    good_chips = "".join(_chip(f"{r['subject']} · {r['topic']} %{r['acc']}", "good") for r in hl["good"])
    work_chips = "".join(_chip(f"{r['subject']} · {r['topic']}", "warn") for r in hl["work"])
    nxt_html = ("<p class='muted small' style='margin-top:8px'>Sırada: "
                + " · ".join(_esc(x) for x in hl["next_topics"]) + "</p>") if hl["next_topics"] else ""
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>İyi gidenler ve odağımız</h2><p>Bu haftanın verisine göre güçlü konular ve önümüzdeki dönemde birlikte güçlendireceğimiz konular.</p></div>
  <h3>Güçlü konular</h3>
  <div class="chips">{good_chips or '<span class="muted">Bu hafta yeterli veri oluşmadı.</span>'}</div>
  <h3>Birlikte çalışacaklarımız</h3>
  <div class="chips">{work_chips or '<span class="muted">Belirgin zayıf konu görülmedi.</span>'}</div>
  {nxt_html}
</section>""")

    # Kapanış
    H.append(f"""
<section class="card agenda">
  <div class="card-h"><h2>Koçunuzdan</h2></div>
  <p class="lede">{_esc(first_name)}'in haftalık programını, çözdüğü her testi ve deneme sonuçlarını
  düzenli olarak takip ediyorum; program her hafta bu veriye göre güncelleniyor.
  Sorularınız için bana her zaman ulaşabilirsiniz.</p>
  <p class="muted small">Bu rapor, öğrencimizin sistemine işlenen gerçek çalışma verilerinden otomatik hazırlanmıştır.</p>
</section>""")

    title = f"{_esc(st.get('full_name'))} · Veli Raporu · {_esc(d_tr(first, False))}–{_esc(d_tr(last, False))}"
    out = _TEMPLATE.replace("{{TITLE}}", title).replace("{{BODY}}", "\n".join(H))
    # veli sürümüne ek stil
    return out.replace("</style>", ".lede{font-size:15.5px;line-height:1.6;color:var(--ink);max-width:75ch;margin:0}\n</style>")
