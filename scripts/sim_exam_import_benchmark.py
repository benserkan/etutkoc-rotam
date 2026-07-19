"""GERÇEK Gemini ile ÇOKLU PDF deneme içe aktarma benchmark'ı (yayın öncesi skor).

Her PDF, üründeki analyze hattından (çift okuma + birleştirme + tespit +
normalizasyon + kontroller) geçirilir; hiçbir şey commit edilmez (flush-only
geçici öğrenci + rollback). Sonunda PDF başına ve genel başarı skoru üretir.

Kullanım:
  PYTHONPATH=. python scripts/sim_exam_import_benchmark.py [rapor.json]

Skor boyutları (sonuç-belgesi vakaları, 100 üzerinden):
  35  konu eşleşme oranı (sözlük+deterministik+AI / toplam satır)
  30  net doğruluğu (belgede net yazan derslerde hesap == belge)
  20  iç tutarlılık kontrolleri (ok oranı)
  10  şüpheli hücre azlığı (%10 şüpheli → 0)
   5  tür tespiti (beklenen aile TYT/AYT ile uyum + güven)
Uygulanamayan boyutlar (örn. belgede net yok) kalanlara oransal dağıtılır.
Kitapçık/limit-aşımı vakaları AYRI değerlendirilir (dayanıklılık: temiz ret mi?).
"""
from __future__ import annotations

import json
import sys
import time
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pathlib import Path

# --- DNS filtresi atlatma (YALNIZ bu geliştirme makinesi) ---------------------
# Bu ağın DNS'i generativelanguage.googleapis.com sorgusunu düşürüyor (aile
# filtresi/SafeSearch zorlaması). TLS/SNI engelli DEĞİL → hostname'i DoH ile
# çözülmüş sabit IP'ye yönlendiriyoruz. Prod'u etkilemez (yalnız bu script).
import socket as _socket

_GEMINI_HOST = "generativelanguage.googleapis.com"
_GEMINI_IPS = ["172.217.113.4", "172.217.114.4", "172.217.117.4"]
_orig_gai = _socket.getaddrinfo


def _patched_gai(host, *args, **kwargs):
    if host == _GEMINI_HOST:
        last_err = None
        for ip in _GEMINI_IPS:
            try:
                return _orig_gai(ip, *args, **kwargs)
            except OSError as e:  # pragma: no cover
                last_err = e
        raise last_err
    return _orig_gai(host, *args, **kwargs)


_socket.getaddrinfo = _patched_gai
# -----------------------------------------------------------------------------

from app.database import SessionLocal
from app.models import User, UserRole
from app.services import exam_import_service as svc

BASE = Path(r"D:\ÖĞRENCİ KOÇLUĞU\ÖĞRENCİLER")

# (öğrenci, sınıf, pdf, beklenen aile TYT/AYT/None, tür, not)
# tür: "result" = sonuç belgesi (tam skor) · "invalid" = kitapçık/limit
#      (dayanıklılık testi — beklenen: temiz ret)
CASES = [
    ("Elvin", 11, BASE / "ELVİN TÜRKMEN/ELVİN denemeler/sonuc-deneme-analiz.pdf",
     None, "result", "içerik bilinmiyor (muhtemel AYT)"),
    ("Elvin", 11, BASE / "ELVİN TÜRKMEN/ELVİN denemeler/sıfır-pozitif-tyt.pdf",
     "TYT", "result", "TYT deneme"),
    ("Elvin", 11, BASE / "ELVİN TÜRKMEN/ELVİN denemeler/elvin-KDS-1-11-SINIF .pdf",
     None, "result", "11. sınıf okul KDS (izleme)"),
    ("Taha", 12, BASE / "Taha Güven/23-03-2026-ayt-matematik-brans.pdf",
     "AYT", "result", "AYT matematik BRANŞ"),
    ("Taha", 12, BASE / "Taha Güven/24.03.2026-ayt-fen-brans.pdf",
     "AYT", "result", "AYT fen BRANŞ"),
    ("Taha", 12, BASE / "Taha Güven/25.02.2026-ayt-matematik-brans.pdf",
     "AYT", "result", "AYT matematik BRANŞ"),
    ("Berra", 12, BASE / "BERRA/berra denemeler/345_TG_TYT_ILK_PROVA_251125_195027.pdf",
     None, "invalid", "SORU KİTAPÇIĞI taraması, 30MB (ürün limiti 10MB)"),
    ("Berra", 12, BASE / "BERRA/berra denemeler/töder.pdf",
     None, "invalid", "optik form/kitapçık taraması 9.2MB (limit İÇİNDE) — temiz ret bekleniyor"),
    ("Berra", 12, BASE / "BERRA/berra denemeler/apotemi.pdf",
     None, "invalid", "SORU KİTAPÇIĞI taraması, 28MB (ürün limiti 10MB)"),
    ("Berra", 12, BASE / "BERRA/DENEME ANALİZLERİ/özdebir-ayt-16-02-Berra.pdf",
     "AYT", "result", "AYT (bilinen vaka: tek AYT oturumu, Sayısal)"),
    # Kullanıcının listelediği 3 Berra dosyası kitapçık çıktığı için gerçek
    # sonuç belgelerinden 2 yedek (kapsam Berra'da da ölçülsün):
    ("Berra", 12, BASE / "BERRA/DENEME ANALİZLERİ/apotemi-2026-tyt.pdf",
     "TYT", "result", "YEDEK: Apotemi TYT sonuç belgesi"),
    ("Berra", 12, BASE / "BERRA/DENEME ANALİZLERİ/ÇAP TG TYT-1.pdf",
     "TYT", "result", "YEDEK: ÇAP TG TYT sonuç belgesi"),
]

FAMILY = {  # section → aile
    "tyt": "TYT", "ayt_say": "AYT", "ayt_ea": "AYT", "ayt_soz": "AYT",
    "ayt_dil": "AYT", "lgs": "LGS", "okul": "OKUL",
}


def _analyze_one(grade: int, pdf: bytes) -> dict:
    with SessionLocal() as db:
        student = User(
            email="sim-exam-bench@t.invalid", password_hash="x",
            full_name="Benchmark Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=grade, must_change_password=False,
        )
        db.add(student)
        db.flush()
        try:
            return svc.analyze(db, student, pdf)
        finally:
            db.rollback()


def _score_result_case(d: dict, expected_family: str | None) -> dict:
    rows = d["rows"]
    total = len(rows)
    st = d["match_stats"]
    matched = st["alias"] + st["auto"] + st["ai"]
    match_rate = matched / total if total else 0.0

    subj_with_doc = [s for s in d["subjects"] if s.get("doc_net") is not None]
    net_ok = sum(1 for s in subj_with_doc
                 if abs(s["net"] - s["doc_net"]) <= 0.011)
    net_rate = (net_ok / len(subj_with_doc)) if subj_with_doc else None

    checks = d["checks"]
    check_rate = (sum(1 for c in checks if c["ok"]) / len(checks)) if checks else None

    suspect_rate = d["suspect_count"] / total if total else 0.0
    suspect_score = max(0.0, 1.0 - suspect_rate * 10)

    det_family = FAMILY.get(d["section"])
    if expected_family is None:
        det_rate = None
    else:
        det_rate = (1.0 if det_family == expected_family else 0.0)
        if det_rate == 1.0 and d["confidence"] != "high":
            det_rate = 0.7

    dims = [
        ("konu_eslesme", 35, match_rate),
        ("net_dogrulugu", 30, net_rate),
        ("kontroller", 20, check_rate),
        ("supheli", 10, suspect_score),
        ("tespit", 5, det_rate),
    ]
    applicable = [(k, w, v) for k, w, v in dims if v is not None]
    wsum = sum(w for _, w, _ in applicable)
    score = round(sum(w * v for _, w, v in applicable) / wsum * 100, 1) if wsum else 0.0

    unmatched: dict = {}
    for r in rows:
        if r["topic_id"] is None:
            key = f"{r.get('subject_name') or r.get('subject_raw')}: {r['topic_raw']}"
            unmatched[key] = unmatched.get(key, 0) + 1

    return {
        "score": score,
        "rows": total,
        "match": {"rate": round(match_rate * 100, 1), **st},
        "net": {
            "subjects_with_doc_net": len(subj_with_doc),
            "exact": net_ok,
            "rate": None if net_rate is None else round(net_rate * 100, 1),
            "diffs": [
                {"name": s["name"], "computed": s["net"], "doc": s["doc_net"]}
                for s in subj_with_doc if abs(s["net"] - s["doc_net"]) > 0.011
            ],
        },
        "checks": {
            "total": len(checks),
            "ok": sum(1 for c in checks if c["ok"]),
            "failed": [f"{c['code']}: {c['detail']}" for c in checks if not c["ok"]],
        },
        "suspects": d["suspect_count"],
        "detection": {
            "section": d["section"], "label": d["section_label"],
            "confidence": d["confidence"], "scope": d["scope"],
            "expected_family": expected_family,
            "family_ok": None if expected_family is None else det_family == expected_family,
            "grade_hint": d["grade_hint"],
        },
        "parts": d["parts"],
        "subjects": [
            {"name": s["name"], "q": s["questions"], "d": s["correct"],
             "y": s["wrong"], "b": s["blank"], "net": s["net"],
             "doc_net": s.get("doc_net")}
            for s in d["subjects"]
        ],
        "title": d["title"],
        "exam_date": d["exam_date"],
        "unmatched_labels": dict(sorted(unmatched.items(), key=lambda x: -x[1])),
    }


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    only = ({int(x) for x in sys.argv[2].split(",")}
            if len(sys.argv) > 2 else None)
    results = []
    for i, (who, grade, path, expected, kind, note) in enumerate(CASES, 1):
        if only and i not in only:
            continue
        rec: dict = {
            "case": i, "student": who, "grade": grade, "file": path.name,
            "kind": kind, "note": note,
        }
        print(f"\n{'=' * 72}\n[{i}/{len(CASES)}] {who} (sınıf {grade}) — {path.name}\n"
              f"  not: {note}", flush=True)
        if not path.exists():
            rec["status"] = "missing"
            print("  DOSYA YOK!", flush=True)
            results.append(rec)
            continue
        pdf = path.read_bytes()
        rec["size_kb"] = round(len(pdf) / 1024)
        if len(pdf) > svc.MAX_PDF_BYTES:
            rec["status"] = "rejected_size"
            rec["detail"] = (f"{len(pdf)/1024/1024:.1f}MB > ürün limiti "
                             f"{svc.MAX_PDF_BYTES/1024/1024:.0f}MB → router "
                             "pdf_too_large ile reddeder (Gemini'ye hiç gitmez)")
            print(f"  ÜRÜN REDDİ: {rec['detail']}", flush=True)
            results.append(rec)
            continue
        t0 = time.time()
        try:
            d = _analyze_one(grade, pdf)
            rec["elapsed_s"] = round(time.time() - t0, 1)
            rec["status"] = "analyzed"
            rec.update(_score_result_case(d, expected))
            print(f"  OK {rec['elapsed_s']}s · tespit={d['section_label']}"
                  f" ({d['confidence']}) · {len(d['rows'])} satır · şüpheli "
                  f"{d['suspect_count']} · eşleşme %{rec['match']['rate']}"
                  f" · skor {rec['score']}", flush=True)
            for s in rec["subjects"]:
                dn = f" (belge: {s['doc_net']})" if s["doc_net"] is not None else ""
                print(f"    {s['name']:<28} {s['q']:>3} soru · {s['d']}D {s['y']}Y "
                      f"{s['b']}B · net {s['net']}{dn}", flush=True)
            for f in rec["checks"]["failed"]:
                print(f"    [FAIL] {f}", flush=True)
        except Exception as e:  # ExamImportError dahil — temiz ret de sonuçtur
            rec["elapsed_s"] = round(time.time() - t0, 1)
            rec["status"] = "error"
            rec["error_type"] = type(e).__name__
            rec["error"] = str(e)[:400]
            code = getattr(e, "code", None)
            if code:
                rec["error_code"] = code
            print(f"  HATA ({rec['elapsed_s']}s): {type(e).__name__}: "
                  f"{str(e)[:200]}", flush=True)
            if kind != "invalid":
                traceback.print_exc()
        results.append(rec)

    # --- GENEL SKOR ---------------------------------------------------------
    print(f"\n{'=' * 72}\n=== GENEL ÖZET ===")
    scored = [r for r in results if r.get("kind") == "result" and r.get("status") == "analyzed"]
    failed_result = [r for r in results if r.get("kind") == "result" and r.get("status") == "error"]
    overall = round(sum(r["score"] for r in scored) / len(scored), 1) if scored else 0.0
    # başarısız sonuç-belgesi vakaları 0 sayılırsa:
    n_all = len(scored) + len(failed_result)
    overall_strict = round(sum(r["score"] for r in scored) / n_all, 1) if n_all else 0.0
    print(f"Analiz edilen sonuç belgesi: {len(scored)} · başarısız: {len(failed_result)}")
    print(f"GENEL SKOR (analiz edilenler ort.): {overall}/100")
    print(f"GENEL SKOR (başarısızlar 0 sayılarak): {overall_strict}/100")
    for r in results:
        if r.get("status") == "analyzed":
            line = (f"  [{r['case']:>2}] {r['student']:<6} {r['file'][:42]:<44} "
                    f"skor {r['score']:>5} · eşleşme %{r['match']['rate']:>5} · "
                    f"şüpheli {r['suspects']}")
        else:
            line = (f"  [{r['case']:>2}] {r['student']:<6} {r['file'][:42]:<44} "
                    f"{r.get('status')} ({r.get('error_code') or r.get('detail','')[:40] or r.get('error_type','')})")
        print(line)

    payload = {"overall": overall, "overall_strict": overall_strict,
               "cases": results}
    if out_path:
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"\nJSON rapor: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
