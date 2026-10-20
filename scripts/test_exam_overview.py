"""Deneme analizi GENEL BAKIŞ — canlı veriyle modellenmiş doğrulama.

Ön koşul: canlıdan dökülmüş anonim fikstür yüklü olmalı
  python -m scripts.import_exam_fixture <exam_fixture.json>   ("Canlı Örnek N" öğrencileri)

Her Canlı Örnek öğrencinin HER serisi için `build_exam_overview` çıktısı ham kayıtlardan
bağımsız hesaplanan değerlerle kıyaslanır (kâhin). Ayrıca Türkçe ek yardımcısı ve uç
(HTTP + sahiplik) sınanır.
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.models.exam_result import ExamResult, section_penalty  # noqa: E402
from app.services import exam_scope  # noqa: E402
from app.services.exam_overview import _effective_rows, build_exam_overview, tr_ek  # noqa: E402
from app.services.exam_topic_analysis import build_exam_topic_analysis  # noqa: E402

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
    else:
        failed.append(f"{label} ({detail})")
        print(f"  [FAIL] {label}  ({detail})")


def close(a, b, eps=0.011):
    return a is not None and b is not None and abs(a - b) <= eps


def main() -> int:
    # --- Türkçe ekler
    for t, k, exp in [("39", "acc", "39'u"), ("10", "acc", "10'u"), ("6", "acc", "6'yı"), ("15", "acc", "15'i"),
                      ("%40", "acc", "%40'ı"), ("Matematik", "loc", "Matematik'te"), ("Geometri", "loc", "Geometri'de"),
                      ("Kimya", "loc", "Kimya'da"), ("21", "dat", "21'e"), ("100", "acc", "100'ü")]:
        check(f"ek {t}/{k}", tr_ek(t, k) == exp, tr_ek(t, k))

    db = SessionLocal()
    students = db.query(User).filter(User.email.like("canli-ornek-%")).order_by(User.id).all()
    check("fikstür yüklü (≥9 öğrenci)", len(students) >= 9, str(len(students)))
    series_checked = 0
    for st in students:
        exams_all = (db.query(ExamResult).filter(ExamResult.student_id == st.id)
                     .order_by(ExamResult.exam_date, ExamResult.id).all())
        for opt in exam_scope.series_options(exams_all):
            key = opt["value"]
            tag = f"{st.full_name} {key}"
            o = build_exam_overview(db, st, series=key, period="all")
            ex = [e for e in exams_all if exam_scope.in_series(e, key)]
            series_checked += 1
            check(f"{tag}: seri", o["series"] == key and o["count"] == len(ex), f"{o['series']} {o['count']}")
            last, prev = ex[-1], (ex[-2] if len(ex) > 1 else None)
            pen = section_penalty(last.section)
            L = o["last"]
            check(f"{tag}: son net", close(L["net"], round(last.net, 2)), str(L["net"]))
            check(f"{tag}: fark", (prev is None and L["delta"] is None) or close(L["delta"], round(last.net - prev.net, 2)),
                  str(L["delta"]))
            check(f"{tag}: rekor", L["is_record"] == (prev is not None and last.net > max(e.net for e in ex[:-1])), "")
            # kaçan net = yanlış×(1+1/ceza) + boş ; toplam net 0'a kırpılmadıysa = soru − net
            exp_loss = round(last.total_wrong * (1 + 1 / pen) + last.total_blank, 2)
            check(f"{tag}: kaçan net formülü", close(o["loss"]["total"], exp_loss, 0.02), f"{o['loss']['total']} vs {exp_loss}")
            if last.net > 0:
                qn = last.total_correct + last.total_wrong + last.total_blank
                check(f"{tag}: kaçan = soru − net", close(o["loss"]["total"], qn - last.net, 0.02),
                      f"{o['loss']['total']} vs {qn - last.net}")
            rows = _effective_rows(last)
            if rows and sum(int(r.get("wrong") or 0) for r in rows) == last.total_wrong \
                    and sum(int(r.get("blank") or 0) for r in rows) == last.total_blank:
                parts = sum(s["lost"] for s in o["loss"]["subjects"]) + ((o["loss"]["others"] or {}).get("lost") or 0)
                check(f"{tag}: ders kayıpları toplamı", close(parts, o["loss"]["total"], 0.05), f"{parts} vs {o['loss']['total']}")
            # gidişat
            t = o["trend"]
            nets = [round(e.net, 2) for e in ex]
            check(f"{tag}: grafik noktaları", [p["net"] for p in t["points"]] == nets, "")
            if len(nets) >= 4:
                s = sorted(nets)
                from statistics import median
                check(f"{tag}: normal bant", close(t["band_low"], median(s[: len(s) // 2]))
                      and close(t["band_high"], median(s[(len(s) + 1) // 2:])), f"{t['band_low']}–{t['band_high']}")
            else:
                check(f"{tag}: <4 denemede bant yok", t["band_low"] is None, "")
            if t["slope"] is not None:
                qn = last.total_correct + last.total_wrong + last.total_blank
                check(f"{tag}: tahmin = son + eğim", close(t["projection"], min(nets[-1] + t["slope"], qn), 0.02), "")
            # ders × deneme: hücreler ham ders netleriyle aynı
            for srow in o["subjects"]:
                for i, cell in enumerate(srow["cells"]):
                    if cell is None:
                        continue
                    raw = next((r for r in _effective_rows(ex[i])
                                if r["name"].endswith(srow["name"])), None)
                    check(f"{tag}: hücre {srow['name']} #{i}", raw is not None and close(cell["net"], float(raw["net"])), "")
            # konu analizi: fırsatlar servisle birebir
            ta = build_exam_topic_analysis(db, st, section=key, period="all")
            if o["topics"]:
                check(f"{tag}: fırsatlar", [x["topic_id"] for x in o["topics"]["opportunities"]]
                      == [x["topic_id"] for x in ta["opportunities"][:6]], "")
                check(f"{tag}: ısı haritası sütunları = konu analizi denemeleri",
                      [x["id"] for x in o["topics"]["exams"]] == [x["id"] for x in ta["exams"]], "")
            else:
                check(f"{tag}: soru satırı yoksa konu bloğu yok", not ta["exams"], "")
            # davranış toplamları
            b = o["behavior"]
            tw = sum(int(r.get("wrong") or 0) for e in ex for r in _effective_rows(e))
            check(f"{tag}: davranış yanlış toplamı", b["total_wrong"] == tw, f"{b['total_wrong']} vs {tw}")
            check(f"{tag}: gündem ≤4", len(o["agenda"]) <= 4, "")
    check("en az 12 seri sınandı", series_checked >= 12, str(series_checked))

    # --- HTTP uç + sahiplik
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.jwt_auth import issue_token_pair
    from app.config import settings
    coach = db.query(User).filter(User.email == "ogretmen@lgs.local").first()
    tp = issue_token_pair(coach)
    c = TestClient(app)
    c.cookies.set(settings.auth_cookie_access_name, tp.access_token)
    st = students[2]
    r = c.get(f"/api/v2/teacher/students/{st.id}/exam-overview?series=tyt&period=all")
    check("HTTP 200", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        check("HTTP son net", r.json()["last"]["net"] == 99.25, str(r.json()["last"]["net"]))
    other = db.query(User).filter(User.role == "teacher", User.id != coach.id).first()
    if other:
        c2 = TestClient(app)
        c2.cookies.set(settings.auth_cookie_access_name, issue_token_pair(other).access_token)
        check("başka koç 404", c2.get(f"/api/v2/teacher/students/{st.id}/exam-overview").status_code == 404, "")

    print(f"\n{passed} passed · {len(failed)} failed  (seri: {series_checked})")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
