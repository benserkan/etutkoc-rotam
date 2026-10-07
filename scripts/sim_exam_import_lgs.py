"""GERÇEK Gemini ile LGS karne içe aktarma testi (8. sınıf) — kayıt YAPMAZ.

Her PDF ürünün hattından geçer: analyze (çift okuma + tür tespiti + konu
normalizasyonu + kontroller) → confirm (net/ders kırılımı yeniden hesap +
kayıt) → exam_scope (genel/branş). Hepsi geçici öğrencide, sonunda rollback.

  PYTHONPATH=. python scripts/sim_exam_import_lgs.py [rapor.json] [--declared]
  --declared : sihirbazdaki gibi "8. sınıf + LGS" beyanıyla da çalıştır
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

import os
if os.name == "nt":  # yalnız geliştirme makinesi: DNS yaması (benchmark içinde)
    from scripts.sim_exam_import_benchmark import _score_result_case
else:  # sunucu: yamasız, gerçek ağ
    _src = Path(__file__).with_name("sim_exam_import_benchmark.py").read_text(encoding="utf-8")
    _a = _src.index("FAMILY = {"); _b = _src.index("def main()")
    _ns: dict = {}
    exec(_src[_a:_b], _ns)
    _score_result_case = _ns["_score_result_case"]

# Ölçüm: her Gemini çağrısının modeli + süresi + sonucu (davranış değişmez)
from app.services import gemini as _gm
_orig_call = _gm._call
CALLS: list[dict] = []


def _timed_call(model, key, parts, **kw):
    t = time.time()
    try:
        r = _orig_call(model, key, parts, **kw)
        CALLS.append({"model": model, "sec": round(time.time() - t, 1), "ok": True})
        return r
    except Exception as e:  # noqa: BLE001
        CALLS.append({"model": model, "sec": round(time.time() - t, 1), "ok": False,
                      "err": type(e).__name__ + ": " + str(e)[:80]})
        raise


_gm._call = _timed_call

from app.database import SessionLocal
from app.models import User, UserRole
from app.services import exam_import_service as svc
from app.services import exam_scope

DIR = Path(os.environ.get("LGS_PDF_DIR", r"D:\ÖĞRENCİ KOÇLUĞU\ÖĞRENCİLER\yiğit eren aydın\denemeler"))
FILES = ["gerisayım.pdf", "mozaik.pdf", "mor.pdf", "lgs-5.pdf",
         "13.03.2026-voltaj-süreç-değerlendirme4.pdf", "09.03.2026-8-4-deneme.pdf",
         "3d-lgs.pdf", "intro.pdf", "full-geri-sayım.pdf"]


def run_one(pdf: bytes, declared: bool) -> dict:
    with SessionLocal() as db:
        # GÜVENLİK: confirm kendi içinde commit eder → bu oturumda commit = flush;
        # her şey sonda rollback ile geri alınır (canlıda iz kalmaz).
        db.commit = db.flush  # type: ignore[method-assign]
        coach = db.query(User).filter(User.role == UserRole.TEACHER).first()
        st = User(email="sim-lgs-bench@t.invalid", password_hash="x", full_name="LGS Test",
                  role=UserRole.STUDENT, is_active=True, grade_level=8,
                  must_change_password=False, teacher_id=coach.id if coach else None)
        db.add(st)
        db.flush()
        try:
            kw = {"declared_section": "lgs", "declared_grade": 8} if declared else {}
            t0 = time.time()
            d = svc.analyze(db, st, pdf, **kw)
            out = _score_result_case(d, "LGS")
            out["analyze_seconds"] = round(time.time() - t0, 1)
            out["date_read"] = d.get("exam_date")
            # kayıt yolu: taslak olduğu gibi onaylanır (koçun "Kontrol ettim, kaydet")
            payload = {k: d[k] for k in ("title", "exam_date", "section", "rows", "grade_hint") if k in d}
            if not payload.get("exam_date"):  # karnede tarih yoksa koç ekranda girer
                from datetime import date as _d
                payload["exam_date"] = _d.today().isoformat()
            if d.get("parts"):
                payload["part"] = None
            ex = svc.confirm(db, st, payload, pdf_bytes=pdf, content_type="application/pdf",
                             actor=coach or st)
            sc = exam_scope.exam_scope(ex)
            out["saved"] = {
                "net": ex.net, "d": ex.total_correct, "y": ex.total_wrong, "b": ex.total_blank,
                "questions": ex.total_correct + ex.total_wrong + ex.total_blank,
                "subject_nets": json.loads(ex.subject_nets or "[]"),
                "scope": sc.kind, "series": sc.series_label,
                "doc_total_net": (d.get("summary") or {}).get("net") if isinstance(d.get("summary"), dict) else None,
            }
            out["duplicate_exam_id"] = d.get("duplicate_exam_id")
            return out
        finally:
            db.rollback()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    declared = "--declared" in sys.argv
    out_path = Path(args[0]) if args else None
    report = []
    for name in FILES:
        p = DIR / name
        t0 = time.time()
        CALLS.clear()
        print(f"\n=== {name} ({p.stat().st_size // 1024} KB){' [beyan: 8/LGS]' if declared else ''}", flush=True)
        try:
            r = run_one(p.read_bytes(), declared)
            r["file"] = name
            r["seconds"] = round(time.time() - t0, 1)
            det = r["detection"]
            print(f"  tür: {det['label']} ({det['confidence']}) · başlık: {r['title']} · tarih: {r['date_read'] or 'OKUNAMADI'} · okuma {r['analyze_seconds']} sn")
            print(f"  satır {r['rows']} · eşleşme %{r['match']['rate']} · şüpheli {r['suspects']} · "
                  f"kontrol {r['checks']['ok']}/{r['checks']['total']} · skor {r['score']} · {r['seconds']} sn")
            for s in r["subjects"]:
                doc = s.get("doc_net")
                flag = "" if doc is None else (" ✓" if abs(s["net"] - doc) <= 0.011 else f" ✗ belge {doc}")
                print(f"    {s['name']:<28} {s['q']:>3} soru  {s['d']}D {s['y']}Y {s['b']}B  net {s['net']}{flag}")
            sv = r["saved"]
            print(f"  KAYIT: net {sv['net']} ({sv['d']}D {sv['y']}Y {sv['b']}B / {sv['questions']} soru) · "
                  f"{sv['series']}")
            for f in r["checks"]["failed"]:
                print(f"  ! {f}")
            if r["unmatched_labels"]:
                print("  eşleşmeyen:", "; ".join(f"{k} ×{v}" for k, v in list(r["unmatched_labels"].items())[:8]))
        except Exception as e:  # noqa: BLE001
            r = {"file": name, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}
            print("  HATA:", r["error"])
        r["gemini_calls"] = list(CALLS)
        print("  Gemini:", " | ".join(f"{c['model'].replace('gemini-2.5-','')} {c['sec']}s {'✓' if c['ok'] else '✗ ' + c.get('err','')}" for c in CALLS))
        report.append(r)
    ok = [r for r in report if "score" in r]
    if ok:
        print(f"\nORTALAMA SKOR {round(sum(r['score'] for r in ok) / len(ok), 1)} · "
              f"başarılı {len(ok)}/{len(report)}")
    if out_path:
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
