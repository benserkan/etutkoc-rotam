# -*- coding: utf-8 -*-
"""Öğrenci Gelişim sayfası uçları (2026-10-21): /student/analytics + /student/weekly-progress.

Koçun analitik ucuyla AYNI hesap (build_student_analytics) — sayılar birebir; koça yönelik
uyarılar/önlemler öğrenciye gönderilmez; koç/veli rolü 403.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import test_api_v2_teacher_analytics_rich as base  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    print(f"\n=== student progress smoke — {base.PFX} ===\n")
    get_login_limiter().reset()
    seed = base._seed()
    try:
        t = base._login(f"{base.PFX}_t@test.invalid")
        s = base._login(f"{base.PFX}_s@test.invalid")
        tr = t.get(f"/api/v2/teacher/students/{seed['s_id']}/analytics").json()
        r = s.get("/api/v2/student/analytics")
        b = r.json() if r.status_code == 200 else {}
        check("1 öğrenci analytics 200", r.status_code == 200, r.text[:200])
        check("2 tempo/projeksiyon koçla birebir",
              b.get("summary") == tr.get("summary") and b.get("projection") == tr.get("projection"),
              f"{b.get('summary')} vs {tr.get('summary')}")
        check("3 haftalık trend + takvim + deneme koçla birebir",
              b.get("weekly_trend") == tr.get("weekly_trend")
              and b.get("activity_calendar") == tr.get("activity_calendar")
              and b.get("exam_trend") == tr.get("exam_trend"), "")
        check("4 koç uyarıları öğrenciye gitmez", b.get("warnings") == [], str(b.get("warnings"))[:120])
        r = s.get("/api/v2/student/weekly-progress")
        w = r.json() if r.status_code == 200 else {}
        check("5 öğrenci weekly-progress 200 + has_program", r.status_code == 200 and "has_program" in w, r.text[:200])
        check("6 'Seansa ekle' önlemleri öğrenciye gitmez", w.get("actions") == [], str(w.get("actions"))[:120])
        # PDF bağlantısı (mobil)
        from fastapi.testclient import TestClient
        from app.main import app
        anon = TestClient(app)
        for kind in ("week", "day", "exams"):
            r = s.post("/api/v2/student/pdf-link", json={"kind": kind})
            url = r.json().get("url", "") if r.status_code == 200 else ""
            g = anon.get(url) if url else None
            check(f"8 {kind} PDF: imzalı bağlantı çerezsiz açılır + gerçek PDF",
                  g is not None and g.status_code == 200 and g.content[:5] == b"%PDF-"
                  and g.headers.get("content-type") == "application/pdf", (r.status_code, g and g.status_code))
        check("9 geçersiz tür 422", s.post("/api/v2/student/pdf-link", json={"kind": "x"}).status_code == 422)
        check("10 bozuk token 404", anon.get("/api/v2/pdf/abc.def.ghi").status_code == 404)
        import jwt as _j
        from datetime import datetime, timedelta, timezone
        from app.config import settings
        old = _j.encode({"sub": str(seed["s_id"]), "typ": "student_pdf", "k": "week",
                         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, settings.session_secret, algorithm="HS256")
        check("11 süresi dolan bağlantı 410", anon.get(f"/api/v2/pdf/{old}").status_code == 410)
        other = _j.encode({"sub": str(seed["s_id"]), "typ": "oauth", "k": "week",
                           "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, settings.session_secret, algorithm="HS256")
        check("12 başka amaçlı imza kabul edilmez (404)", anon.get(f"/api/v2/pdf/{other}").status_code == 404)
        check("13 koç pdf-link alamaz (403)", t.post("/api/v2/student/pdf-link", json={"kind": "week"}).status_code == 403)
        check("7 koç bu uçlara erişemez (403)",
              t.get("/api/v2/student/analytics").status_code == 403
              and t.get("/api/v2/student/weekly-progress").status_code == 403, "")
    finally:
        base._cleanup(seed)
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
