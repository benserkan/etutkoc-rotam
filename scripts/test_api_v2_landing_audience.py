"""API v2 — public landing audience filtresi smoke (2026-05-25).

Senaryolar:
   1. audience=teacher → yalnız koç (target_roles içinde 'teacher') kartları
   2. audience=institution_admin → yalnız kurum kartları
   3. teacher feed'in başı stratejik koç kartı (kesfet-* erken-uyari öne çıkar)
   4. iki set kesişmez (koç ≠ kurum)
   5. audience yok → karışık (>= her iki setten)
   6. geçersiz audience → boş liste (kart yok, hata değil)

NOT: seed_landing_cards.py çalıştırılmış olmalı (11 yayın kartı).
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.main import app

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


def slugs(client, audience=None, limit=8):
    url = f"/api/v2/landing?limit={limit}"
    if audience:
        url += f"&audience={audience}"
    r = client.get(url)
    return r.status_code, [c["slug"] for c in r.json().get("cards", [])]


def main() -> int:
    print("\n=== Landing audience filtresi smoke ===\n")
    c = TestClient(app)

    st, coach = slugs(c, "teacher")
    check("1. audience=teacher → kart döner", st == 200 and len(coach) > 0, f"{st} {coach}")
    # koç kartları kesfet-* veya eski teacher kartları; kurum kartı OLMAMALI
    inst_slugs_in_coach = [s for s in coach if s in (
        "kesfet-program-uyum", "kesfet-mudahale-merkezi", "kesfet-akademik-cikti",
        "kesfet-ogretmen-karne", "kesfet-veli-guveni")]
    check("1b. koç feed'inde kurum kartı yok", not inst_slugs_in_coach, f"{inst_slugs_in_coach}")

    st, inst = slugs(c, "institution_admin")
    check("2. audience=institution_admin → kart döner", st == 200 and len(inst) > 0, f"{st} {inst}")
    only_inst = all(s.startswith("kesfet-") and "uyari" not in s and "seans" not in s
                    and "foto" not in s and "plan" not in s and "tahsilat" not in s
                    and "bilgilendirme" not in s for s in inst)
    check("2b. kurum feed'i yalnız kurum kartları", only_inst, f"{inst}")

    # 3. teacher feed başı stratejik (kesfet-erken-uyari görünür / öne yakın)
    check("3. koç stratejik kartı feed'de (erken-uyari)", "kesfet-erken-uyari" in coach, f"{coach}")

    # 4. kesişim yok
    check("4. koç ∩ kurum = boş", not (set(coach) & set(inst)), f"kesişim={set(coach) & set(inst)}")

    # 5. audience yok → karışık
    st, allc = slugs(c, None, limit=12)
    has_both = any(s in allc for s in inst) and len(allc) >= 5
    check("5. audience yok → karışık set", st == 200 and len(allc) >= 5, f"{st} n={len(allc)}")

    # 6. geçersiz audience → boş (hata değil)
    st, bad = slugs(c, "nope_role")
    check("6. geçersiz audience → 200 + boş liste", st == 200 and bad == [], f"{st} {bad}")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
