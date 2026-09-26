"""Haftalık İskelet F2-2 — dönemli iskelet (smoke, 2026-09-26).

Saha: Taha okul başlayınca ritim değiştirdi (yaz iskeleti okula taşınmaz).
Bir öğrencinin birden çok dönemi olur; her gün O GÜN geçerli dönemden öneri alır.

Senaryolar:
   1. İlk "bu haftayı iskelet yap" (replace) → başlangıçsız ilk dönem (Yaz)
   2. İkinci hafta mode=new → o haftanın başından yeni dönem (Okul); Yaz silinmez
   3. Dönem listesi: başlangıç/bitiş hesaplı, bugün geçerli = Okul
   4. Kopya dönem (Yaz → Tatil, bugün+3'ten) → dönem değişen hafta BÖLÜNÜR:
      bugün..+2 Okul dersinin hayaleti, +3.. Yaz dersinin hayaleti
   5. GET ?skeleton_id= belirli dönem · ?at= o günün dönemi
   6. Aynı başlangıçlı ikinci dönem → 409
   7. Dönem başlangıcını kaydır (+5) → +3/+4 yeniden Okul
   8. skeleton_id ile kaydet yalnız o dönemi değiştirir
   9. Dönem sil → sonraki günler önceki döneme döner
  10. Başka öğrencinin / olmayan dönem → 404
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import Subject, Task, TaskType, User, UserRole
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"skp_{secrets.token_hex(3)}"
PWD = "SkelP!234567xy"
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
    print(f"\n=== iskelet dönem smoke — {PFX} ===\n")
    get_login_limiter().reset()
    today = date.today()
    w1 = [today - timedelta(days=i) for i in range(21, 14, -1)]  # 3 hafta önce: yaz
    w2 = [today - timedelta(days=i) for i in range(7, 0, -1)]    # geçen hafta: okul
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="Dönem Koç", role=UserRole.TEACHER, is_active=True)
            db.add(coach)
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                      full_name="Dönem Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            db.add(st)
            db.flush()
            yaz = Subject(name=f"{PFX} YazDers", teacher_id=coach.id, order=1)
            okul = Subject(name=f"{PFX} OkulDers", teacher_id=coach.id, order=2)
            db.add_all([yaz, okul])
            db.flush()
            for d in w1:
                db.add(Task(student_id=st.id, date=d, type=TaskType.OTHER,
                            title=f"{yaz.name} · yaz işi", is_draft=False))
            for d in w2:
                db.add(Task(student_id=st.id, date=d, type=TaskType.OTHER,
                            title=f"{okul.name} · okul işi", is_draft=False))
            ids.update(coach=coach.id, st=st.id, yaz=yaz.id, okul=okul.id)
            db.commit()

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{ids['st']}/skeleton"

        def ghosts_subjects(d):
            g = c.get(f"{base}/ghosts", params={"start": d.isoformat(), "end": d.isoformat()}).json()
            return {x["subject_id"] for day in g["days"] for x in day["ghosts"]}

        # 1
        r1 = c.post(f"{base}/from-week", json={"start": w1[0].isoformat(), "end": w1[-1].isoformat(),
                                               "name": "Yaz"})
        d1 = r1.json()["data"]
        check("1. ilk dönem: başlangıçsız, adı Yaz",
              r1.status_code == 200 and d1["valid_from"] is None and d1["name"] == "Yaz"
              and len(d1["periods"]) == 1, r1.text[:200])
        ids["A"] = d1["id"]

        # 2
        r2 = c.post(f"{base}/from-week", json={"start": w2[0].isoformat(), "end": w2[-1].isoformat(),
                                               "mode": "new", "name": "Okul dönemi"})
        d2 = r2.json()["data"]
        ids["B"] = d2["id"]
        check("2. mode=new: yeni dönem haftanın başından, Yaz silinmedi",
              r2.status_code == 200 and d2["valid_from"] == w2[0].isoformat()
              and len(d2["periods"]) == 2 and d2["id"] != ids["A"], r2.text[:200])

        # 3
        per = {p["id"]: p for p in d2["periods"]}
        check("3. dönem listesi: Yaz bitişi = Okul başlangıcı − 1 · bugün geçerli Okul",
              per[ids["A"]]["valid_until"] == (w2[0] - timedelta(days=1)).isoformat()
              and per[ids["B"]]["valid_until"] is None and per[ids["B"]]["is_current"]
              and not per[ids["A"]]["is_current"], str(per))

        # 4
        t3 = today + timedelta(days=3)
        r4 = c.post(f"{base}/periods", json={"valid_from": t3.isoformat(), "name": "Tatil",
                                             "copy_from_id": ids["A"]})
        ids["C"] = r4.json()["data"]["id"]
        before = [ghosts_subjects(today + timedelta(days=i)) for i in range(0, 5)]
        check("4. kopya dönem + hafta bölünür: bugün..+2 Okul, +3.. Yaz",
              r4.status_code == 200 and r4.json()["data"]["slots"]
              and all(ids["okul"] in s and ids["yaz"] not in s for s in before[:3])
              and all(ids["yaz"] in s and ids["okul"] not in s for s in before[3:]),
              str(before))

        # 5
        gA = c.get(base, params={"skeleton_id": ids["A"]}).json()
        gAt = c.get(base, params={"at": (today + timedelta(days=4)).isoformat()}).json()
        gNow = c.get(base).json()
        check("5. skeleton_id / at / varsayılan doğru dönemi döner",
              gA["id"] == ids["A"] and gAt["id"] == ids["C"] and gNow["id"] == ids["B"],
              f"{gA['id']} {gAt['id']} {gNow['id']}")

        # 6
        r6 = c.post(f"{base}/periods", json={"valid_from": t3.isoformat(), "name": "Çakışan"})
        check("6. aynı başlangıçlı ikinci dönem 409",
              r6.status_code == 409 and r6.json()["detail"]["code"] == "period_start_taken",
              r6.text[:200])

        # 7
        t5 = today + timedelta(days=5)
        r7 = c.post(f"{base}/periods/{ids['C']}", json={"valid_from": t5.isoformat(),
                                                        "name": "Yarıyıl"})
        s3, s5 = ghosts_subjects(t3), ghosts_subjects(t5)
        check("7. başlangıç +5'e kaydı: +3 yeniden Okul, +5 Yaz · ad değişti",
              r7.status_code == 200 and r7.json()["data"]["name"] == "Yarıyıl"
              and ids["okul"] in s3 and ids["yaz"] in s5, f"{s3} {s5}")

        # 8
        nA = len(gA["slots"])
        nB = len(c.get(base, params={"skeleton_id": ids["B"]}).json()["slots"])
        r8 = c.post(base, json={"skeleton_id": ids["A"], "slots": [
            {"weekday": 0, "period": None, "subject_id": ids["yaz"], "position": 0,
             "is_routine": False, "default_count": None}]})
        nA2 = len(c.get(base, params={"skeleton_id": ids["A"]}).json()["slots"])
        nB2 = len(c.get(base, params={"skeleton_id": ids["B"]}).json()["slots"])
        check("8. skeleton_id ile kaydet yalnız o dönemi değiştirir",
              r8.status_code == 200 and nA2 == 1 and nA != 1 and nB2 == nB,
              f"A {nA}->{nA2} B {nB}->{nB2}")

        # 9
        r9 = c.post(f"{base}/delete", json={"skeleton_id": ids["C"]})
        s5b = ghosts_subjects(t5)
        check("9. dönem silinince sonraki günler önceki döneme döner",
              r9.status_code == 200 and len(r9.json()["data"]["periods"]) == 2
              and ids["okul"] in s5b and ids["yaz"] not in s5b, str(s5b))

        # 10
        r10a = c.get(base, params={"skeleton_id": 99999999})
        r10b = c.post(f"{base}/periods/99999999", json={"name": "x"})
        check("10. olmayan dönem 404", r10a.status_code == 404 and r10b.status_code == 404,
              f"{r10a.status_code} {r10b.status_code}")
    finally:
        with SessionLocal() as db:
            if ids.get("st"):
                db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id == ids["st"]))
                for x in db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id == ids["st"]):
                    db.delete(x)
                db.execute(sa_delete(Task).where(Task.student_id == ids["st"]))
                db.execute(sa_delete(Subject).where(Subject.id.in_([ids["yaz"], ids["okul"]])))
                db.execute(sa_delete(User).where(User.id.in_([ids["st"], ids["coach"]])))
                db.commit()
    print(f"\n=== {passed}/{passed + len(failed)} geçti ===")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
