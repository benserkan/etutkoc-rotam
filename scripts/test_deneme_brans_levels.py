"""Branş denemesi SINAV DÜZEYİ (2026-11-08).

  1. Seçenekler: mezun SAYISAL → TYT + AYT düzeyi (sınıf düzeyi yok); 10. sınıf Maarif →
     "10. Sınıf" (okul dersleri, okul türü) + "TYT / 1. Aşama" (TYT dersleri); 8. sınıf → LGS
  2. Okul dersi (Maarif Fizik) branşı "okul" türüyle yazılır (eskiden AYT Sayısal)
  3. Maarif 10. sınıfa TYT Matematik branşı verilebilir (düzey listesinden) → "tyt"
  4. TYT Geometri'ye standart 40 soru düşmez
  5. Analiz: TYT Matematik + AYT Matematik ayrı seri, ayrı düzey, etiketler ayrışır,
     sonucu bekleyen sayısı düzeye göre ayrılır
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CurriculumModel, ExamResult, Subject, Task, TaskBookItem, User, UserRole  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dbl_{secrets.token_hex(3)}"
PWD = "Seviye!Deneme2345"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def builtin(db, name, model=None):
    q = db.query(Subject).filter(Subject.is_builtin.is_(True), Subject.teacher_id.is_(None),
                                 Subject.name == name)
    q = q.filter(Subject.curriculum_model == model) if model else q.filter(Subject.curriculum_model.is_(None))
    return q.first()


def main() -> int:
    uids: list[int] = []
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                         role=UserRole.TEACHER, is_active=True)
            db.add(coach); db.flush()

            def stu(tag, **kw):
                u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD),
                         full_name=tag, role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                         must_change_password=False, **kw)
                db.add(u); db.flush()
                return u

            say = stu("say", is_graduate=True, track=Track.SAYISAL)
            ten = stu("ten", grade_level=10)
            lgs = stu("lgs", grade_level=8)
            db.commit()
            uids += [coach.id, say.id, ten.id, lgs.id]
            sid, tid, lid = say.id, ten.id, lgs.id
            tyt_mat = builtin(db, "TYT Matematik").id
            ayt_mat = builtin(db, "AYT Matematik").id
            tyt_geo = builtin(db, "TYT Geometri").id
            m_fiz = builtin(db, "Fizik", CurriculumModel.MAARIF_LISE).id

        c = login(f"{PFX}_t@test.invalid")
        lv = {x["key"]: x for x in c.get(f"/api/v2/teacher/students/{sid}/deneme-options").json()["brans_levels"]}
        check("1a mezun: TYT + AYT, sınıf düzeyi yok", {"tyt", "ayt"} <= set(lv) and "sinif" not in lv, str(list(lv)))
        geo = next((s for s in lv["tyt"]["subjects"] if s["id"] == tyt_geo), None)
        check("4 TYT Geometri standart soru yok (40 düşmez)", geo and geo["standard_question_count"] is None, str(geo))
        lv10 = {x["key"]: x for x in c.get(f"/api/v2/teacher/students/{tid}/deneme-options").json()["brans_levels"]}
        check("1b 10. sınıf: '10. Sınıf' + 'TYT / 1. Aşama'",
              lv10.get("sinif", {}).get("label") == "10. Sınıf" and "tyt" in lv10
              and "1. Aşama" in lv10["tyt"]["label"] and "ayt" not in lv10, str({k: v["label"] for k, v in lv10.items()}))
        check("1c sınıf düzeyi dersleri okul türünde",
              lv10.get("sinif") and all(s["exam_section"] == "okul" for s in lv10["sinif"]["subjects"]),
              str(lv10.get("sinif", {}).get("subjects", [])[:3]))
        lvl = [x["key"] for x in c.get(f"/api/v2/teacher/students/{lid}/deneme-options").json()["brans_levels"]]
        check("1d 8. sınıf: yalnız LGS", lvl == ["lgs"], str(lvl))

        day = date.today().isoformat()
        r = c.post(f"/api/v2/teacher/students/{tid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "subject_id": m_fiz, "count": 1, "question_count": 20})
        check("2 Maarif Fizik branşı 'okul' türünde",
              r.status_code == 200 and r.json()["data"]["items"][0]["exam_section"] == "okul", r.text[:300])
        r = c.post(f"/api/v2/teacher/students/{tid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "subject_id": tyt_mat, "count": 1})
        check("3 10. sınıfa TYT Matematik verilebilir → tyt",
              r.status_code == 200 and r.json()["data"]["items"][0]["exam_section"] == "tyt", r.text[:300])

        t1 = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                    json={"date": day, "kind": "brans", "subject_id": tyt_mat, "count": 2}).json()["data"]
        t2 = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                    json={"date": day, "kind": "brans", "subject_id": ayt_mat, "count": 2}).json()["data"]
        with SessionLocal() as db:
            for t in (t1, t2):
                db.get(Task, t["id"]).is_draft = False
            db.commit()
        s = login(f"{PFX}_say@test.invalid")
        for t, (cc, ww) in ((t1, (30, 4)), (t2, (20, 8))):
            r = s.post(f"/api/v2/student/tasks/{t['id']}/deneme-results",
                       json={"rows": [{"item_id": t["items"][0]["id"], "solved": True, "correct": cc, "wrong": ww},
                                      {"item_id": t["items"][1]["id"], "solved": True}]})
            assert r.status_code == 200, r.text
        a = c.get(f"/api/v2/teacher/students/{sid}/deneme-analysis").json()
        br = {x["key"]: x for x in a["series"] if x["kind"] == "brans"}
        levels = sorted(x["level"] for x in br.values())
        check("5a iki ayrı seri: tyt + ayt", levels == ["ayt", "tyt"], str(levels))
        labels = sorted(x["label"] for x in br.values())
        check("5b etiketler ayrışır, AYT'de alan yazmaz",
              labels == ["AYT · Matematik branş", "TYT · Matematik branş"], str(labels))
        pend = {x["level"]: x["pending"] for x in br.values()}
        check("5c bekleyen düzeye göre ayrı (1 + 1)", pend == {"tyt": 1, "ayt": 1}, str(pend))
        check("5d sıralama TYT önce", [x["level"] for x in a["series"] if x["kind"] == "brans"] == ["tyt", "ayt"],
              str([x["level"] for x in a["series"]]))
    finally:
        with SessionLocal() as db:
            if uids:
                tids = [x.id for x in db.query(Task).filter(Task.student_id.in_(uids)).all()]
                if tids:
                    iids = [x.id for x in db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).all()]
                    if iids:
                        db.query(ExamResult).filter(ExamResult.task_book_item_id.in_(iids)).delete(synchronize_session=False)
                    db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
                    db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
                db.query(ExamResult).filter(ExamResult.student_id.in_(uids)).delete(synchronize_session=False)
                db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
                db.commit()
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
