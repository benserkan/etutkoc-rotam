"""Öğrenci Gelişim Raporu (360°) — haftalık performans + geçmiş haftalarla kıyas +
deneme gelişimi + mevcut durum / güçlü yanlar / fırsatlar / riskler + aksiyon planı.

TEK MERKEZ, salt okuma, yapay zekâ yok, kredi yok. Rapor SAKLANMAZ: her istekte o anki
veriden yeniden kurulur (görev işaretlenince, deneme girilince, hedef değişince rapor da
değişir). Kendi hesabını yapmaz — mevcut servislerin çıktısını birleştirir:

  · haftalık performans + hafta hafta tablo : weekly_progress.build_weekly_progress(full_history)
  · deneme gelişimi + konu fırsatları       : exam_progress.build_progress_report
  · program (branş) denemeleri              : TaskBookItem.exam_kind (görevden verilenler)

Her bulgu ve aksiyon `key` + `agenda` (seans gündemi cümlesi) taşır; koç seçtiklerini
exam_progress.add_to_queue ile sıradaki seansın gündemine ekler. Anahtarlar veriden
türer (konu id, ölçü adı) → rapor yenilense de "Seans gündeminde" işareti tutar.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from statistics import mean

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Task, TaskBookItem, User

COVERAGE_LOW = 0.5        # sonuç girilen test payı bunun altındaysa doğruluk ölçülemez
COVERAGE_MIN_TESTS = 6    # ölçüm için en az bu kadar çözülen test
BRANCH_WINDOW_DAYS = 28
PHASE_WEEKS = 3           # "başlangıç" ve "son dönem" kıyası: ilk/son 3 hafta


def _num(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "—"
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") if s else "0"


def _signed(v: float) -> str:
    return ("+" if v > 0 else "−" if v < 0 else "") + _num(abs(v))


def _pct(v: float | None) -> str:
    return "—" if v is None else f"%{round(v)}"


def _avg(vals: list[float]) -> float | None:
    return round(mean(vals), 1) if vals else None


def _item(key: str, tone: str, title: str, text: str, *, agenda: str | None = None,
          source: str = "report", priority: int = 2, cta_label: str | None = None,
          cta_href: str | None = None) -> dict:
    return {"key": key, "tone": tone, "title": title, "text": text,
            "agenda": agenda or f"{title} — {text}", "source": source, "priority": priority,
            "cta_label": cta_label, "cta_href": cta_href, "queued": False}


# ---------------------------------------------------------------- veri kalitesi

def _program_deneme_stats(db: Session, student_id: int, today: date) -> dict:
    """Son 4 haftada programdan verilen denemeler: verilen / çözülen / sonucu girilen."""
    since = today - timedelta(days=BRANCH_WINDOW_DAYS)
    rows = (db.query(TaskBookItem)
            .join(Task, Task.id == TaskBookItem.task_id)
            .filter(Task.student_id == student_id, Task.is_draft.is_(False),
                    Task.date >= since, Task.date < today,
                    TaskBookItem.exam_kind.isnot(None)).all())
    out = {"brans": {"given": 0, "solved": 0, "result": 0}, "genel": {"given": 0, "solved": 0, "result": 0}}
    for it in rows:
        b = out.get(it.exam_kind)
        if b is None:
            continue
        b["given"] += 1
        if int(it.completed_count or 0) > 0:
            b["solved"] += 1
            if it.correct_count is not None or it.wrong_count is not None:
                b["result"] += 1
    return out


def _last_activity(db: Session, student_id: int) -> dict:
    from app.models.exam_result import ExamResult

    last_tick = (db.query(func.max(Task.completed_at))
                 .filter(Task.student_id == student_id).scalar())
    last_exam = (db.query(func.max(ExamResult.created_at))
                 .filter(ExamResult.student_id == student_id).scalar())
    return {"last_tick_at": last_tick.isoformat() if last_tick else None,
            "last_exam_at": last_exam.isoformat() if last_exam else None}


# ---------------------------------------------------------------- ana

def build_development_report(db: Session, student: User, *, series: str | None = None,
                             period: str | None = None, today: date | None = None) -> dict:
    from app.services.exam_progress import build_progress_report
    from app.services.weekly_progress import build_weekly_progress

    today = today or date.today()
    sid = student.id
    week_href = f"/teacher/students/{sid}/week"

    wp = build_weekly_progress(db, student, today=today, full_history=True)
    ep = build_progress_report(db, student, section=series, period=period)

    has_program = bool(wp.get("has_program"))
    weeks = wp.get("weeks_table") or []
    cards = {c["key"]: c for c in wp.get("cards", [])} if has_program else {}
    week = wp.get("week") if has_program else None
    if week:
        week_href = f"/teacher/students/{sid}/week?start={week['start']}"

    # ----- deneme netlerini haftalara yerleştir (genel seri)
    exams = ep.get("exams") or []
    for w in weeks:
        inw = [e for e in exams if w["start"] <= e["exam_date"] <= w["end"]]
        w["exam_nets"] = [e["net"] for e in inw]
        w["exam_titles"] = [e["title"] for e in inw]

    # ----- bu hafta
    this_week = None
    if week:
        cur_row = next((w for w in weeks if w["current"]), None)
        compare = []
        for key in ("gorev_pct", "test_done", "ontime_pct", "empty_days", "night_pct",
                    "accuracy_pct", "new_topics", "load", "exam_net"):
            c = cards.get(key)
            if not c:
                continue
            compare.append({k: c.get(k) for k in ("key", "name", "hint", "unit", "direction", "value",
                                                  "value_label", "prev", "prev_label", "status", "low",
                                                  "high", "trend", "trend_run", "verdict")})
        cr = cur_row or {}
        if cr.get("tests_done_items") and cr["tests_with_result"] < cr["tests_done_items"] * COVERAGE_LOW:
            for c in compare:
                if c["key"] == "accuracy_pct":
                    c["status"] = "insufficient"
                    c["verdict"] = (f"Çözülen {cr['tests_done_items']} testin yalnız {cr['tests_with_result']} tanesinde "
                                    "doğru/yanlış girildi; bu oran güvenilir bir ölçüm değil.")
        this_week = {
            "week": week, "row": cur_row, "days": wp.get("days", []),
            "projection": wp.get("projection"), "compare": compare,
        }

    # ----- gelişim döneminde gelinen nokta
    full = [w for w in weeks if not w["current"] and not w["cut"] and w["days"] >= 4
            and w["gorev_pct"] is not None]
    journey = None
    if full or exams:
        first_ph, last_ph = full[:PHASE_WEEKS], full[-PHASE_WEEKS:]
        tests_total = sum(w["test_done"] for w in weeks)
        journey = {
            "weeks": len(full),
            "first_week": full[0]["label"] if full else None,
            "start_gorev_pct": _avg([w["gorev_pct"] for w in first_ph]),
            "recent_gorev_pct": _avg([w["gorev_pct"] for w in last_ph]),
            "start_tests_per_week": _avg([w["test_done"] for w in first_ph]),
            "recent_tests_per_week": _avg([w["test_done"] for w in last_ph]),
            "tests_total": tests_total,
            "median_gorev_pct": (wp.get("period_summary") or {}).get("median"),
            "best_week": (wp.get("period_summary") or {}).get("best"),
            "worst_week": (wp.get("period_summary") or {}).get("worst"),
            "slope_per_week": (wp.get("projection") or {}).get("slope_per_week"),
            "exam": ep.get("stats"),
            "exam_label": ep.get("section_label"),
            "target": ep.get("target"),
        }

    # ----- veri kalitesi
    recent_rows = [w for w in weeks if not w["cut"]][-4:]
    tests_done = sum(w["tests_done_items"] for w in recent_rows)
    tests_res = sum(w["tests_with_result"] for w in recent_rows)
    coverage = round(100 * tests_res / tests_done) if tests_done else None
    pdn = _program_deneme_stats(db, sid, today)
    data_quality = {
        "tests_done": tests_done, "tests_with_result": tests_res, "result_coverage_pct": coverage,
        "program_deneme": pdn, "exam_count": len(exams),
        "exam_with_subjects": sum(1 for s in (ep.get("subjects") or []) if s.get("last") is not None) > 0,
    }

    # ----- 360: durum / güçlü / fırsat / risk
    state: list[dict] = []
    strengths: list[dict] = []
    opportunities: list[dict] = []
    risks: list[dict] = []

    gp = cards.get("gorev_pct")
    if this_week and gp:
        row = this_week["row"] or {}
        txt = (f"{row.get('gorev_done', 0)}/{row.get('gorev_total', 0)} görev ({_pct(gp['value'])}). "
               f"{gp['verdict']}")
        wk_title = (f"Son program haftası ({week['label']})" if week["ended"]
                    else f"Bu hafta ({week['label']}, {week['day_index']}/{week['days']}. gün)")
        state.append(_item("state:week", "info", wk_title,
                           txt, agenda=f"Bu haftanın uyumu {_pct(gp['value'])} — {gp['verdict']}"))
    if journey and journey["start_gorev_pct"] is not None and journey["recent_gorev_pct"] is not None \
            and journey["weeks"] >= PHASE_WEEKS * 2:
        d = journey["recent_gorev_pct"] - journey["start_gorev_pct"]
        tone = "good" if d >= 5 else "warn" if d <= -5 else "info"
        txt = (f"İlk {PHASE_WEEKS} haftada görev uyumu ortalama {_pct(journey['start_gorev_pct'])}, "
               f"son {PHASE_WEEKS} haftada {_pct(journey['recent_gorev_pct'])}. "
               f"Haftalık test: {_num(journey['start_tests_per_week'], 0)} → {_num(journey['recent_tests_per_week'], 0)}.")
        it = _item("state:journey", tone, f"{journey['weeks']} haftalık gidişat", txt)
        state.append(it)
        if tone == "good":
            strengths.append(_item("good:journey", "good", "Programa bağlılık artıyor", txt))
        elif tone == "warn":
            risks.append(_item("risk:journey", "warn", "Programa bağlılık başlangıca göre düştü", txt,
                               priority=1, cta_label="Haftalık programı aç", cta_href=week_href))
    st = ep.get("stats")
    if st:
        lbl = ep.get("section_label") or "Deneme"
        txt = (f"{st['count']} denemede net {_num(st['first_net'])} → {_num(st['last_net'])} "
               f"({_signed(st['change'])}); son 3 ortalama {_num(st['avg_last3'])}, en iyi {_num(st['best_net'])}.")
        state.append(_item("state:exam", "info", f"{lbl} denemeleri", txt))
    tgt = ep.get("target")
    if tgt and tgt.get("gap") is not None:
        if tgt["gap"] <= 0:
            strengths.append(_item("good:target", "good", "Hedef net tuttu",
                                   f"Hedef {_num(tgt['target_net'])}, {tgt['basis']} {_num(tgt['basis_net'])}."))
        else:
            txt = f"Hedef {_num(tgt['target_net'])} nete {_num(tgt['gap'])} net var ({tgt['basis']}: {_num(tgt['basis_net'])})."
            if tgt.get("per_week_needed"):
                txt += f" Hedef tarihe kadar haftada {_num(tgt['per_week_needed'])} net artış gerekiyor."
            state.append(_item("state:target", "info", "Hedefe uzaklık", txt))

    # haftalık ölçüler → güçlü / risk. Sonuç (D/Y/B) girme oranı düşükse doğruluk ve boş soru
    # birkaç testten hesaplanır → yanıltıcı; bulgu üretmez (veri girişi riski ayrıca söylenir).
    low_cov = tests_done >= COVERAGE_MIN_TESTS and (coverage or 0) < COVERAGE_LOW * 100
    cur_row = next((w for w in weeks if w["current"]), None)
    last_full = next((w for w in reversed(weeks) if not w["current"] and not w["cut"] and w["days"] >= 4), None)
    for key, c in cards.items():
        if key in ("balance", "wrong_archive", "requests"):
            continue
        if low_cov and key in ("accuracy_pct", "blank_pct"):
            continue
        name = c["name"]
        if key == "test_done" and c["status"] in ("below", "critical") and cur_row and cur_row["test_planned"]:
            # Az test çözülmesi, koçun az test vermesinden olabilir: verilene oranla da kıyasla.
            ratios = [w["test_done"] / w["test_planned"] for w in weeks
                      if w["in_baseline"] and w["test_planned"]]
            cur_ratio = cur_row["test_done"] / cur_row["test_planned"]
            if ratios and cur_ratio >= sorted(ratios)[len(ratios) // 2] - 0.05:
                state.append(_item(
                    "state:tests_planned", "info", "Bu hafta daha az test verildi",
                    f"{cur_row['test_planned']} test verildi, {cur_row['test_done']} çözüldü (%{round(cur_ratio * 100)}). "
                    f"Çözülen test genelin altında ({c['value_label']}, genelde {round(c['low'])}–{round(c['high'])}) "
                    "ama verilene oranla tamamlama her zamanki düzeyde — düşüş yükten, öğrenciden değil."))
                continue
        if c.get("trend") and c["status"] not in ("below", "critical") and last_full and cur_row:
            cv, lv = cur_row.get(key), last_full.get(key)
            if cv is not None and lv is not None and (cv - lv) * (c["direction"] or 1) > 0:
                continue  # bu hafta eğilim tersine döndü; artık kötüleşme yok
        if c["status"] == "above" and key != "exam_net":
            strengths.append(_item(f"good:wk:{key}", "good", f"{name}: normalinden iyi",
                                   f"Bu hafta {c['value_label']}. {c['verdict']}"))
        elif c["status"] in ("below", "critical") and key != "exam_net":
            risks.append(_item(f"risk:wk:{key}", "bad" if c["status"] == "critical" else "warn",
                               f"{name} {'geçmişin en kötüsü' if c['status'] == 'critical' else 'normalin altında'}",
                               f"Bu hafta {c['value_label']}. {c['verdict']}",
                               priority=1 if c["status"] == "critical" else 2,
                               cta_label="Haftalık programı aç", cta_href=week_href))
        elif c.get("trend") and c["status"] not in ("below", "critical"):
            risks.append(_item(f"risk:trend:{key}", "warn", f"{name}: {c['trend_run']} hafta üst üste kötüleşme",
                               c["verdict"], priority=2))
    bal = cards.get("balance")
    if bal and bal["status"] == "below":
        risks.append(_item("risk:balance", "warn", "Kaçınılan ders", bal["verdict"], priority=1,
                           cta_label="Haftalık programı aç", cta_href=week_href))

    # deneme yorumları → güçlü / risk / durum
    for i, c in enumerate(ep.get("commentary") or []):
        t = c["text"]
        if " denemede net " in t and "→" in t:
            continue  # ilk→son deneme "Mevcut durum"da; ilk deneme uç değerse yanıltıcı ayrıca söylenmez
        title = _exam_title(t)
        if c["tone"] == "good":
            strengths.append(_item(f"good:exam:{i}", "good", title, t))
        elif c["tone"] == "warn":
            risks.append(_item(f"risk:exam:{i}", "warn", title, t, priority=2,
                               cta_label="Deneme analizi", cta_href=f"/teacher/students/{sid}#exams"))
    if st and st["count"] >= 4:
        nets_all = [e["net"] for e in exams]
        if st["last_net"] <= min(nets_all[:-1]):
            risks.append(_item(
                "risk:exam_low", "bad", "Son deneme serinin en düşüğü",
                f"{exams[-1]['title']} ({fmt_date(exams[-1]['exam_date'])}): {_num(st['last_net'])} net — "
                f"{st['count']} denemenin en düşüğü; son 3 ortalama {_num(st['avg_last3'])}, önceki deneme "
                f"{_num(nets_all[-2])}.",
                agenda=f"Son deneme {_num(st['last_net'])} net (serinin en düşüğü): o gün ne oldu — süre, uyku, hangi derste kaybetti?",
                priority=1, cta_label="Deneme analizi", cta_href=f"/teacher/students/{sid}#exams"))

    # fırsatlar: konu net fırsatı + ders hedef farkı + tempo
    for o in (ep.get("opportunities") or [])[:5]:
        opportunities.append(_item(
            f"topic:{o['topic_id']}", "info", f"{o['topic_name']} ({o['subject_name']})",
            f"Denemelerde {o['total']} soruda {o['wrong']} yanlış, {o['blank']} boş; kapanırsa deneme başına "
            f"yaklaşık {_signed(o['net_gain_per_exam'])} net.",
            agenda=f"{o['topic_name']} konusunu kapat — deneme başına ~{_signed(o['net_gain_per_exam'])} net.",
        ))
    for s in sorted([s for s in (ep.get("subjects") or []) if s.get("gap") and s["gap"] > 0],
                    key=lambda x: -x["gap"])[:3]:
        opportunities.append(_item(f"subjgap:{s['name'].lower()}", "info", f"{s['name']} hedefi",
                                   f"Hedef {_num(s['target'])}, son deneme {_num(s['last'])} net — {_num(s['gap'])} net açık."))
    ups = [s for s in (ep.get("subjects") or []) if s.get("slope") is not None and s["slope"] >= 0.5]
    for s in ups[:2]:
        strengths.append(_item(f"good:subj:{s['name'].lower()}", "good", f"{s['name']} yükselişte",
                               f"Son denemelerde deneme başına {_signed(s['slope'])} net; son net {_num(s['last'])}."))
    if st and not tgt and ep.get("target_allowed", True) and st["count"] >= 2:
        opportunities.append(_item(
            "opp:set_target", "info", "Hedef net belirle",
            f"{ep.get('section_label')} için hedef yok. Son 3 deneme ortalaması {_num(st['avg_last3'])}, "
            f"en iyi {_num(st['best_net'])}; hedef girilince gereken haftalık tempo ve ders hedefleri bu rapora eklenir.",
            agenda=f"Öğrenciyle {ep.get('section_label')} hedef netini birlikte belirle (şu an son 3 ort. {_num(st['avg_last3'])}).",
            cta_label="Deneme raporu", cta_href=f"/teacher/students/{sid}#exams"))
    if st and st.get("slope") is not None and st["slope"] > 0 and st["best_net"] > st["avg_last3"]:
        opportunities.append(_item(
            "opp:best_net", "info", "En iyi neti kalıcı kılma fırsatı",
            f"En iyi denemesi {_num(st['best_net'])} net; son 3 ortalaması {_num(st['avg_last3'])}. "
            f"Aradaki {_num(st['best_net'] - st['avg_last3'])} net, o denemedeki koşulların (süre, sıra, uyku) tekrarlanmasıyla kapanabilir."))
    if journey and journey.get("best_week") and journey.get("median_gorev_pct") is not None             and journey["best_week"]["value"] - journey["median_gorev_pct"] >= 8:
        bw = journey["best_week"]
        opportunities.append(_item(
            "opp:best_week", "info", "En iyi haftasının düzeni",
            f"{bw['label']} haftasında uyum %{round(bw['value'])} (ortanca %{round(journey['median_gorev_pct'])}). "
            "O haftanın yükü ve gün dağılımı örnek alınabilir.",
            cta_label="Haftalık programı aç", cta_href=week_href))
    proj = (this_week or {}).get("projection") or {}
    if proj.get("slope_per_week") is not None and proj["slope_per_week"] >= 2:
        strengths.append(_item("good:slope", "good", "Haftalık uyum yükseliyor",
                               f"Son 4 tam haftada uyum haftada ortalama +{_num(proj['slope_per_week'], 1)} puan artıyor."))
    elif proj.get("slope_per_week") is not None and proj["slope_per_week"] <= -2:
        risks.append(_item("risk:slope", "warn", "Haftalık uyum düşüyor",
                           f"Son 4 tam haftada uyum haftada ortalama {_num(abs(proj['slope_per_week']), 1)} puan azalıyor.",
                           priority=1, cta_label="Haftalık programı aç", cta_href=week_href))

    # veri kalitesi riskleri
    if tests_done >= COVERAGE_MIN_TESTS and (coverage or 0) < COVERAGE_LOW * 100:
        risks.append(_item(
            "data:results", "warn", "Doğru/yanlış/boş girilmiyor",
            f"Son 4 haftada çözülen {tests_done} testin yalnız {tests_res} tanesinde sonuç girildi (%{coverage or 0}). "
            "Konu doğruluğu ve zorlandığı konular bu yüzden ölçülemiyor.",
            agenda="Testlerde doğru/yanlış/boş girmeyi alışkanlık yap — zorlandığı konular ancak böyle görünür.",
            priority=1, cta_label="Konu performansı", cta_href=f"/teacher/students/{sid}#topics"))
    b = pdn["brans"]
    if b["given"] >= 2 and b["solved"] < b["given"] / 2:
        risks.append(_item(
            "data:brans", "warn", "Branş denemelerinden kaçınıyor",
            f"Son 4 haftada programa {b['given']} branş denemesi kondu, {b['solved']} tanesi çözüldü"
            f"{f', {b['result']} tanesinin sonucu girildi' if b['solved'] else ''}.",
            agenda="Branş denemeleri neden çözülmüyor? Süre/zorluk mu, kaynak mı — birlikte planla.",
            priority=1, cta_label="Branş denemeleri", cta_href=f"/teacher/students/{sid}#program-exams"))
    elif b["solved"] >= 2 and b["result"] < b["solved"] / 2:
        risks.append(_item(
            "data:brans_result", "warn", "Branş denemesi sonuçları girilmiyor",
            f"Çözülen {b['solved']} branş denemesinin {b['result']} tanesinde doğru/yanlış girildi.",
            agenda="Branş denemesi sonuçlarını girmesini iste — ders bazlı gidişat ancak böyle izlenir.",
            priority=2, cta_label="Branş denemeleri", cta_href=f"/teacher/students/{sid}#program-exams"))
    if not exams:
        risks.append(_item("data:noexam", "info", "Genel deneme sonucu yok",
                           "Deneme gelişimi izlenemiyor; karne PDF'i ya da elle sonuç girilmeli.", priority=3))

    # ----- aksiyon planı (haftalık önlemler + deneme aksiyonları; anahtar tekil)
    actions: list[dict] = []
    wk_prio = {"carry": 1, "avoid": 1, "load": 2, "rhythm": 2, "accuracy": 2}
    for a in wp.get("actions", []) if has_program else []:
        if a["key"] == "carry" and week and week["ended"]:
            n = a["title"].split()[1] if a["title"].startswith("Kalan ") else ""
            a = {**a, "title": f"Geçen haftadan kalan {n} görevi yeni haftaya devret".replace("  ", " "),
                 "agenda": f"Geçen hafta yapılmayan {n} görevi konuş; gerekenleri yeni haftaya devret.",
                 "cta_label": "Haftalık programı aç (Devret)"}
        actions.append({
            "key": f"wp:{a['key']}", "title": a["title"], "detail": a["why"], "source": "weekly",
            "priority": wk_prio.get(a["key"], 2), "agenda": a.get("agenda") or a["title"],
            "cta_label": a.get("cta_label"), "cta_href": a.get("cta_href"), "queued": False,
        })
    for a in ep.get("actions") or []:
        actions.append({
            "key": a["key"], "title": a["title"], "detail": a["detail"], "source": "exam",
            "priority": a["priority"], "agenda": f"{a['title']} — {a['detail']}",
            "cta_label": None, "cta_href": None, "queued": False, "exam_id": a.get("exam_id"),
        })
    for r in risks:
        if r["key"].startswith("data:") and r["key"] != "data:noexam":
            actions.append({
                "key": f"act:{r['key']}", "title": r["title"], "detail": r["text"], "source": "data",
                "priority": r["priority"], "agenda": r["agenda"],
                "cta_label": r["cta_label"], "cta_href": r["cta_href"], "queued": False,
            })
    seen: set[str] = set()
    actions = [a for a in actions if not (a["key"] in seen or seen.add(a["key"]))]
    actions.sort(key=lambda a: a["priority"])

    risks.sort(key=lambda r: r["priority"])
    tone_counts = {"good": len(strengths), "risk": len(risks), "opportunity": len(opportunities)}
    headline = _headline(this_week, journey, risks, strengths)

    return {
        "student_name": student.full_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "activity": _last_activity(db, sid),
        "has_program": has_program,
        "headline": headline,
        "this_week": this_week,
        "weeks": weeks,
        "journey": journey,
        "exam": {
            "series": ep.get("series"), "section_label": ep.get("section_label"),
            "section_options": ep.get("section_options") or [], "exams": exams,
            "subjects": [x for x in (ep.get("subjects") or []) if sum(v is not None for v in x["nets"]) >= 2],
            "stats": st, "target": tgt,
        },
        "state": state, "strengths": strengths, "opportunities": opportunities, "risks": risks,
        "actions": actions[:14],
        "data_quality": data_quality,
        "counts": tone_counts,
    }


_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def fmt_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {_MONTHS[d.month - 1]}"


def _exam_title(text: str) -> str:
    """exam_progress yorum cümlesine kısa başlık (hepsi 'Deneme gidişatı' görünmesin)."""
    t = text.lower()
    for needle, title in (("gelişen ders", "En çok gelişen ders"), ("gerileyen ders", "En çok gerileyen ders"),
                          ("hedef", "Hedefe göre tempo"), ("boş kaldı", "Boş bırakılan soru"),
                          ("yanlış", "Yanlış oranı"), ("ritmi", "Deneme ritmi"), ("ilk deneme", "İlk deneme"),
                          ("yükseliş", "Deneme eğilimi: yükseliş"), ("düşüş", "Deneme eğilimi: düşüş"),
                          ("yatay", "Deneme eğilimi: yatay")):
        if needle in t:
            return title
    return "Deneme"


def _headline(this_week: dict | None, journey: dict | None, risks: list[dict], strengths: list[dict]) -> dict:
    """Tek cümlelik genel durum (raporun en üstü)."""
    bad = [r for r in risks if r["priority"] == 1]
    if bad:
        level, text = "risk", f"{len(bad)} öncelikli konu var: " + ", ".join(r["title"].lower() for r in bad[:3]) + "."
    elif risks:
        level, text = "watch", f"Genel gidişat dengede; {len(risks)} izlenecek nokta var."
    else:
        level, text = "good", "Ölçülen her alanda öğrenci kendi normalinde ya da üstünde."
    if strengths:
        text += f" {len(strengths)} güçlü yan öne çıkıyor."
    return {"level": level, "text": text}
