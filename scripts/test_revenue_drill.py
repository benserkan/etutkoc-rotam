"""Sprint A (Faz A) — Ticari Pano drill-down smoke test.

Yol haritası başarı kriteri: "her sayı tıklanabilir, kurum listesi açılıyor".

Test ettiği:
  - Ana revenue sayfası 200 + drill-host + macro butonlar render
  - 17 farklı drill key route'u 200 dönüyor
  - Geçersiz drill key graceful fallback dönüyor (200 + "Bilinmeyen kategori")
  - drill_for_key servisi tutarlı dict shape döner
  - HTML render: kurum adı + plan_label + reason + detail_url
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import User, UserRole
from app.services.revenue_panel import DRILL_REGISTRY, drill_for_key


passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    print("=== Sprint A (Faz A) — Ticari Pano Drill-Down smoke ===")

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if not sa:
            print("  (super admin yok — testler atlandı)")
            return 0
        sa_id = sa.id

    def _ov():
        def factory():
            db2 = SessionLocal()
            try:
                u = (
                    db2.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == sa_id).first()
                )
                _ = u.institution
                db2.expunge_all()
                return u
            finally:
                db2.close()
        return factory

    app.dependency_overrides[require_super_admin] = _ov()
    app.dependency_overrides[require_user] = _ov()
    app.dependency_overrides[get_current_user] = _ov()
    try:
        c = TestClient(app)

        # ---- 1) Service: drill_for_key tüm registry key'leri için tutarlı çıktı ----
        with SessionLocal() as db:
            for key in DRILL_REGISTRY.keys():
                d = drill_for_key(db, key=key)
                check(
                    f"service: '{key}' dict shape",
                    isinstance(d, dict) and "title" in d and "rows" in d
                    and "count" in d and isinstance(d["rows"], list),
                    str(d)[:120],
                )
                check(
                    f"service: '{key}' rows count tutarlı",
                    d["count"] == len(d["rows"]),
                )

        # ---- 2) Plan kodu için dinamik anahtar ----
        with SessionLocal() as db:
            d = drill_for_key(db, key="plan:free")
            check("plan:free → satır var", len(d["rows"]) > 0)
            check("plan:free rows hepsi 'free' plan",
                  all(r["plan"] == "free" for r in d["rows"]))

            d_unknown = drill_for_key(db, key="plan:nonexistent_zzz")
            check("plan:nonexistent → 0 satır", d_unknown["count"] == 0)

        # ---- 3) Geçersiz key fallback ----
        with SessionLocal() as db:
            d = drill_for_key(db, key="bogus_key_xyz")
            check("invalid key → fallback dict",
                  d["count"] == 0 and d.get("error") == "unknown_key")

        # ---- 4) Ana sayfa: 200 + drill macro + drill-host ----
        r = c.get("/admin/security-monitor/revenue")
        check("ana sayfa GET 200", r.status_code == 200)
        check("ana sayfada drill-host var", 'id="drill-host"' in r.text)
        check("ana sayfada macro link var",
              "/admin/security-monitor/revenue/drill?key=" in r.text)
        check("HTMX attribute (hx-get) var", "hx-get" in r.text)

        # ---- 5) Drill route: tüm registry key'leri 200 + partial render ----
        for key in DRILL_REGISTRY.keys():
            rr = c.get(f"/admin/security-monitor/revenue/drill?key={key}")
            check(f"drill route '{key}' → 200",
                  rr.status_code == 200, f"got {rr.status_code}")
            # Partial — base.html extend etmemeli (drill-host olmamalı)
            check(f"drill route '{key}' partial (not full page)",
                  "<html" not in rr.text.lower())

        # ---- 6) plan:<code> route ----
        rr = c.get("/admin/security-monitor/revenue/drill?key=plan:free")
        check("plan:free route → 200", rr.status_code == 200)
        check("plan:free içerikte 'kurum' kelimesi geçer",
              "kurum" in rr.text.lower())

        # ---- 7) Geçersiz key route graceful ----
        rr = c.get("/admin/security-monitor/revenue/drill?key=garbage_xyz")
        check("invalid key route → 200", rr.status_code == 200)
        check("invalid key route içerikte 'Bilinmeyen' var",
              "Bilinmeyen" in rr.text)

        # ---- 8) Render edilen satırlarda doğru alanlar ----
        with SessionLocal() as db:
            d = drill_for_key(db, key="free")
            rows = d["rows"]
        if rows:
            rr = c.get("/admin/security-monitor/revenue/drill?key=free")
            sample = rows[0]
            check("partial: kurum adı render",
                  sample["institution_name"] in rr.text,
                  f"{sample['institution_name']!r} not in body")
            check("partial: detail_url render",
                  f"/admin/institutions/{sample['institution_id']}" in rr.text)
            check("partial: plan_label render",
                  sample["plan_label"] in rr.text)
        else:
            print("  (free liste boş — render alan testleri atlandı)")

    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
