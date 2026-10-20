"""Deneme analizi ölçüleri — canlı veriyle BAĞIMSIZ doğrulama (SALT OKUMA, prod'da koşulur).

Her gerçek öğrenci (demo/silinmiş hariç) ve her seri için servisin ürettiği değerleri ham
kayıtlardan yeniden hesaplanan "kâhin" değerlerle kıyaslar; ayrıca kod incelemesinde
işaretlenen şüpheli durumların canlıda GERÇEKTEN oluşup oluşmadığını sayar.

  M1  Konu Analizi varsayılan serisi ≠ panelin varsayılan serisi (seri kayması)
  M2  Konu Analizi kâhin: konu D/Y/B + net fırsatı ham soru satırından birebir mi
  M3  Gelişim raporu kâhin: sayı/ilk/son/en iyi/ort/son-3 ort/eğim
  M4  Puan tahmini: genel LGS varken sonraki TYT/AYT genel denemesi tahmini engelliyor mu
  M5  Puan tahmini: ders kırılımı olmayan TYT genel → ~100 puan uyarısız mı
  M6  Ders neti 0'a kırpılmış (negatif olmalıydı) → ders toplamı ≠ toplam net
  M7  TYT seçmeli blok (Din / Seçmeli Felsefe) %100 boş satır kırılımda kalmış mı
  M8  Eşleşmeyen soru ayrı "ders" satırı olmuş mu (unmatched=true)
  M9  Gelişim raporu "son deneme N gün önce" — güncel dönemde deneme yokken

  python -m scripts.audit_exam_metrics
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.models.exam_result import (  # noqa: E402
    EQ_RESULT_BOS, EQ_RESULT_DOGRU, EQ_RESULT_YANLIS, ExamResult, ExamSection, section_penalty,
)
try:  # D3b sonrası; canlıda henüz yoksa (programdan deneme kaydı da yok) filtre boş geçer
    from app.models.exam_result import analysis_exam_filter  # noqa: E402
except ImportError:  # pragma: no cover
    from sqlalchemy import true as _true

    def analysis_exam_filter():
        return _true()
from app.services import exam_import_service, exam_scope  # noqa: E402
from app.services.exam_faz3 import score_estimate  # noqa: E402
from app.services.exam_progress import build_progress_report  # noqa: E402
from app.services.exam_topic_analysis import build_exam_topic_analysis  # noqa: E402

findings: dict[str, list[str]] = defaultdict(list)
checks = Counter()


def ok(code: str, cond: bool, msg: str) -> None:
    checks[code + (" ✓" if cond else " ✗")] += 1
    if not cond:
        findings[code].append(msg)


def slope(vals):
    n = len(vals)
    if n < 2:
        return None
    xm = (n - 1) / 2
    ym = sum(vals) / n
    den = sum((i - xm) ** 2 for i in range(n))
    return round(sum((i - xm) * (v - ym) for i, v in enumerate(vals)) / den, 2) if den else None


def main() -> None:
    db = SessionLocal()
    sids = [r[0] for r in db.query(ExamResult.student_id).filter(analysis_exam_filter()).distinct()]
    students = [u for u in db.query(User).filter(User.id.in_(sids)).all()
                if "demo" not in (u.full_name or "").lower() and not (u.email or "").endswith(".local")
                and not getattr(u, "is_demo", False)]
    print(f"Gerçek öğrenci: {len(students)}")
    for st in students:
        tag = f"öğr#{st.id} {st.full_name}"
        exams = (db.query(ExamResult).filter(ExamResult.student_id == st.id, analysis_exam_filter())
                 .order_by(ExamResult.exam_date.asc(), ExamResult.id.asc()).all())

        # ---- M3 gelişim raporu (varsayılan seri) + M1 seri kayması + M9
        rep = build_progress_report(db, st)
        ta = build_exam_topic_analysis(db, st)
        if rep.get("series") and ta.get("section") and rep["series"] != ta["section"]:
            findings["M1"].append(f"{tag}: panel serisi {rep['series']} · konu analizi {ta['section']}")
        checks["M1 kontrol"] += 1
        for opt in rep.get("section_options") or []:
            r = build_progress_report(db, st, section=opt["value"])
            series_ex = [e for e in exams if exam_scope.in_series(e, opt["value"])]
            stats = r.get("stats")
            if not stats:
                continue
            # rapor dönem penceresini kullanır → kâhin de aynı sayıda son denemeyi alır
            ex = series_ex[-stats["count"]:]
            nets = [round(e.net, 2) for e in ex]
            exp = {"count": len(nets), "first_net": nets[0], "last_net": nets[-1], "best_net": max(nets),
                   "avg_net": round(sum(nets) / len(nets), 2), "avg_last3": round(sum(nets[-3:]) / len(nets[-3:]), 2),
                   "slope": slope(nets[-5:])}
            for k, v in exp.items():
                got = stats.get(k)
                ok("M3", got == v or (isinstance(v, float) and got is not None and abs(got - v) < 0.011),
                   f"{tag} {opt['value']} {k}: rapor {got} · kâhin {v}")
            if stats.get("days_since_last", 0) > 60:
                findings["M9"].append(f"{tag} {opt['value']}: son deneme {stats['days_since_last']} gün önce "
                                      f"(rapor yine de ritim uyarısı üretir mi: "
                                      f"{any('gün önce' in (c.get('text') or '') for c in r.get('commentary', []))})")

        # ---- M2 konu analizi kâhini (her seri)
        for opt in ta.get("section_options") or []:
            t = build_exam_topic_analysis(db, st, section=opt["value"])
            ids = [x["id"] for x in t["exams"]]
            if not ids:
                continue
            sec = ExamSection(exam_scope.section_of_key(opt["value"]))
            pen = section_penalty(sec)
            agg: dict[int, Counter] = defaultdict(Counter)
            for e in [e for e in exams if e.id in ids]:
                skip = exam_import_service.untaken_optional_block_ids(e.questions, section=e.section, track=st.track)
                for q in e.questions:
                    if q.id in skip or q.topic_id is None:
                        continue
                    a = agg[q.topic_id]
                    a["total"] += 1
                    a[q.result] += 1
            got = {x["topic_id"]: x for x in t["topics"]}
            for tid, a in agg.items():
                g = got.get(tid)
                ok("M2", g is not None and (g["total"], g["correct"], g["wrong"], g["blank"]) ==
                   (a["total"], a[EQ_RESULT_DOGRU], a[EQ_RESULT_YANLIS], a[EQ_RESULT_BOS]),
                   f"{tag} {opt['value']} konu {tid}: servis {g and (g['total'], g['correct'], g['wrong'], g['blank'])} "
                   f"· kâhin {(a['total'], a[EQ_RESULT_DOGRU], a[EQ_RESULT_YANLIS], a[EQ_RESULT_BOS])}")
            for o in t["opportunities"]:
                a = agg[o["topic_id"]]
                expg = round((a[EQ_RESULT_YANLIS] * (1 + 1 / pen) + a[EQ_RESULT_BOS]) / len(ids), 2)
                ok("M2", abs(o["net_gain_per_exam"] - expg) < 0.011,
                   f"{tag} fırsat {o['topic_name']}: {o['net_gain_per_exam']} · kâhin {expg}")

        # ---- M4/M5 puan tahmini
        se = score_estimate(db, st)
        genel = [e for e in exams if exam_scope.classify(e) == "genel"]
        lgs = [e for e in genel if e.section == ExamSection.LGS]
        yks = [e for e in genel if e.section != ExamSection.LGS and e.section.value.startswith(("tyt", "ayt"))]
        if lgs and yks and max(e.exam_date for e in yks) > max(e.exam_date for e in lgs):
            findings["M4"].append(f"{tag}: son LGS {max(e.exam_date for e in lgs)}, son YKS {max(e.exam_date for e in yks)} "
                                  f"→ tahmin türü {se.get('kind')}")
        tyt = [e for e in genel if e.section == ExamSection.TYT]
        if tyt and not tyt[-1].subject_nets:
            findings["M5"].append(f"{tag}: son TYT genel #{tyt[-1].id} ders kırılımsız → puanlar "
                                  f"{[(s['key'], s['score']) for s in se['scores']]} · uyarı {se['warnings']}")
        checks["M4/M5 kontrol"] += 1

        # ---- M6/M7/M8 ders kırılımı
        for e in exams:
            if not e.subject_nets:
                continue
            try:
                rows = json.loads(e.subject_nets)
            except Exception:
                continue
            pen = section_penalty(e.section)
            for r in rows:
                c, w = int(r.get("correct") or 0), int(r.get("wrong") or 0)
                raw = round(c - w / pen, 2)
                if raw < 0 and float(r.get("net") or 0) == 0:
                    findings["M6"].append(f"{tag} #{e.id} {r.get('name')}: {c}D {w}Y → net 0 (olması gereken {raw})")
                if r.get("unmatched"):
                    findings["M8"].append(f"{tag} #{e.id} '{r.get('name')}' {c}D {w}Y {r.get('blank')}B (eşleşmeyen satır)")
                nm = (r.get("name") or "").lower()
                if e.section == ExamSection.TYT and c == 0 and w == 0 and int(r.get("blank") or 0) > 0 \
                        and ("din" in nm or "felsefe" in nm):
                    findings["M7"].append(f"{tag} #{e.id} '{r.get('name')}' tamamı boş ({r.get('blank')}) kırılımda")
            checks["M6-8 deneme"] += 1

    print("Kontroller:", dict(sorted(checks.items())))
    for code in sorted(findings):
        print(f"\n== {code} ({len(findings[code])})")
        for m in findings[code][:25]:
            print("  ", m)


if __name__ == "__main__":
    main()
