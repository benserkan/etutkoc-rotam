"""Şube (class_group) — öğrenci listesi süzme + toplu atama (2026-09-28, kurum toplu kurulumu 4/4).

  1. liste class_group alanını döner
  2. class_group=10-A süzgeci yalnız o şubeyi getirir
  3. class_group=__none__ şubesizleri getirir
  4. class_groups sayımları şube süzgecinden BAĞIMSIZ (seçici daralmaz)
  5. toplu atama: seçilenler şubeye alınır; yabancı öğrenci skipped_invalid
  6. boşluk normalize ("  10   B ") → "10 B"
  7. "" → şube kaldırılır
  8. create + PATCH class_group; PATCH alanı yoksa değişmez
  9. 500+ öğrenci → 422
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"scg_{secrets.token_hex(3)}"
PWD = "ClassGrp!234xy"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Şube Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_unlimited", subscription_status="active")
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Diğer Koç", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        ids = {}
        for key, grp, t in [("a1", "10-A", coach), ("a2", "10-A", coach), ("b1", "10-B", coach),
                            ("n1", None, coach), ("x", None, other)]:
            u = User(email=f"{PFX}_{key}@test.invalid", password_hash=hash_password(PWD),
                     full_name=f"Öğrenci {key}", role=UserRole.STUDENT, is_active=True,
                     teacher_id=t.id, grade_level=10, class_group=grp)
            db.add(u)
            db.flush()
            ids[key] = u.id
        db.commit()
        return {"coach": coach.id, "other": other.id, "email": coach.email, **ids}


def cleanup(d, extra: list[int]):
    with SessionLocal() as db:
        sids = [d[k] for k in ("a1", "a2", "b1", "n1", "x")] + extra
        db.execute(sa_delete(User).where(User.id.in_(sids + [d["coach"], d["other"]])))
        db.commit()


def grp(uid):
    with SessionLocal() as db:
        return db.get(User, uid).class_group


def main() -> int:
    print(f"\n=== Şube smoke — {PFX} ===\n")
    get_login_limiter().reset()
    d = seed()
    extra: list[int] = []
    try:
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": d["email"], "password": PWD}).status_code == 200
        L = "/api/v2/teacher/students"

        r = c.get(L, params={"status": "aktif", "page_size": 100}).json()
        by = {x["id"]: x for x in r["items"]}
        check("1. liste class_group döner", by[d["a1"]]["class_group"] == "10-A"
              and by[d["n1"]]["class_group"] is None)

        r = c.get(L, params={"status": "aktif", "class_group": "10-A", "page_size": 100}).json()
        check("2. 10-A süzgeci", {x["id"] for x in r["items"]} == {d["a1"], d["a2"]},
              str([x["id"] for x in r["items"]]))
        counts = {g["class_group"]: g["count"] for g in r["class_groups"]}
        check("4. sayımlar süzgeçten bağımsız", counts == {"10-A": 2, "10-B": 1, None: 1}, str(counts))
        order = [g["class_group"] for g in r["class_groups"]]
        check("4b. sıralama 10-A,10-B,şubesiz", order == ["10-A", "10-B", None], str(order))

        r = c.get(L, params={"status": "aktif", "class_group": "__none__", "page_size": 100}).json()
        check("3. şubesizler", {x["id"] for x in r["items"]} == {d["n1"]})

        r = c.post(f"{L}/class-group", json={"student_ids": [d["n1"], d["b1"]],
                                              "class_group": "11 A"})
        det = r.json().get("detail", {}) if r.status_code == 409 else {}
        check("5a. 10. sınıfı '11 A' şubesine → 409 grade_mismatch",
              r.status_code == 409 and det.get("code") == "grade_mismatch"
              and len(det.get("details", {}).get("students", [])) == 2, r.text[:200])
        check("5a2. uyuşmazlıkta hiçbir şey yazılmadı", grp(d["n1"]) is None)
        r = c.post(f"{L}/class-group", json={"student_ids": [d["n1"]], "class_group": "Mezun grubu"})
        check("5a3. mezun olmayana 'Mezun…' → 409", r.status_code == 409, str(r.status_code))
        r = c.post(f"{L}/class-group", json={"student_ids": [d["n1"]], "class_group": "a"})
        check("5a4. yalnız harf → sınıf öğrenciden: 'a' → 10-A", r.status_code == 200 and grp(d["n1"]) == "10-A",
              str(grp(d["n1"])))
        r = c.post(f"{L}/class-group", json={"student_ids": [d["n1"]], "class_group": "10 - b"})
        check("5a4b. yazım farkı tek biçime: '10 - b' → 10-B", r.status_code == 200 and grp(d["n1"]) == "10-B",
              str(grp(d["n1"])))
        r = c.post(f"{L}/class-group", json={"student_ids": [d["n1"]], "class_group": "10-D"})
        check("5a5. aynı sınıf serbest", r.status_code == 200 and grp(d["n1"]) == "10-D")
        r = c.post(f"{L}/class-group", json={"student_ids": [d["n1"], d["b1"], d["x"]],
                                              "class_group": "  11   A ", "force": True})
        body = r.json()["data"] if r.status_code == 200 else {}
        check("5. toplu atama (force)", r.status_code == 200 and body.get("updated_count") == 2
              and body.get("skipped_invalid_ids") == [d["x"]], r.text[:200])
        check("6. normalize '11 A' → 11-A", grp(d["n1"]) == "11-A" and grp(d["b1"]) == "11-A")
        check("5b. yabancı öğrenci dokunulmadı", grp(d["x"]) is None)
        check("5c. invalidate öğrenci listesi",
              f"teacher:{d['coach']}:students" in r.json().get("invalidate", []))

        r = c.post(f"{L}/class-group", json={"student_ids": [d["n1"]], "class_group": ""})
        check("7. boş → kaldır", r.status_code == 200 and grp(d["n1"]) is None)

        r = c.post(L, json={"full_name": "Yeni Şubeli", "email": f"{PFX}_new@test.invalid",
                             "grade_level": 10, "class_group": " 10-C "})
        new_id = None
        if r.status_code in (200, 201):
            data = r.json().get("data", {})
            new_id = data.get("student_id") or (data.get("student") or {}).get("id") or data.get("id")
        if new_id:
            extra.append(new_id)
        check("8. create class_group", new_id is not None and grp(new_id) == "10-C", r.text[:300])

        r = c.patch(f"{L}/{d['a1']}", json={"class_group": "12-A"})
        check("8b. PATCH class_group", r.status_code == 200 and grp(d["a1"]) == "12-A", r.text[:200])
        r = c.patch(f"{L}/{d['a1']}", json={"full_name": "Öğrenci a1 yeni"})
        check("8c. PATCH alan yok → korunur", r.status_code == 200 and grp(d["a1"]) == "12-A")
        det = c.get(f"{L}/{d['a1']}").json()
        prof = det.get("profile") or det.get("student") or {}
        check("8d. detay profili class_group", prof.get("class_group") == "12-A", str(list(det))[:200])

        r = c.post(f"{L}/class-group", json={"student_ids": list(range(1, 503)), "class_group": "X"})
        check("9. 500+ → 422", r.status_code == 422, str(r.status_code))
    finally:
        cleanup(d, extra)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
