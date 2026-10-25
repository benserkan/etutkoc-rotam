"""Birleşik branş denemeleri (TYT Fen / TYT Sosyal / AYT Fen / AYT Edebiyat-Sosyal 1 /
AYT Sosyal 2) — 2026-10-25.

  1. Seçenekler: SAYISAL mezunda TYT Fen + TYT Sosyal + AYT Fen var, AYT sözel grupları yok;
     EA öğrencide AYT Edebiyat-Sosyal 1 var, AYT Fen yok; 8. sınıfta hiç yok
  2. TYT Fen ×2 → 2 kalem, ders yok, etiket "TYT Fen Bilimleri 1/2", 20 soru, TYT
  3. Görev deneme sayılır, test hacmine girmez
  4. Uygun olmayan grup 422
  5. Öğrenci sonucu girince Denemeler kaydı "TYT Fen Bilimleri" branş serisi
  6. Sık verdiklerin kalıbı group_key taşır
"""
from __future__ import annotations

import json
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
from app.models import ExamResult, Task, TaskBookItem, User, UserRole  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.services import gorev_stats  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dbg_{secrets.token_hex(3)}"
PWD = "Grup!Deneme2345"
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
            ea = stu("ea", grade_level=12, track=Track.EA)
            lgs = stu("lgs", grade_level=8)
            db.commit()
            uids += [coach.id, say.id, ea.id, lgs.id]
            sid, eid, lid = say.id, ea.id, lgs.id

        c = login(f"{PFX}_t@test.invalid")
        g = {x["key"] for x in c.get(f"/api/v2/teacher/students/{sid}/deneme-options").json()["brans_groups"]}
        check("1a SAYISAL: TYT Fen + TYT Sosyal + AYT Fen", {"tyt_fen", "tyt_sosyal", "ayt_fen"} <= g, str(g))
        check("1b SAYISAL: AYT sözel grupları yok", not ({"ayt_edebiyat_sos1", "ayt_sos2"} & g), str(g))
        g2 = {x["key"] for x in c.get(f"/api/v2/teacher/students/{eid}/deneme-options").json()["brans_groups"]}
        check("1c EA: Edebiyat-Sosyal 1 var, AYT Fen yok", "ayt_edebiyat_sos1" in g2 and "ayt_fen" not in g2, str(g2))
        g3 = c.get(f"/api/v2/teacher/students/{lid}/deneme-options").json()["brans_groups"]
        check("1d 8. sınıf: grup yok", g3 == [], str(g3))

        day = date.today().isoformat()
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "group_key": "tyt_fen", "count": 2})
        check("2a TYT Fen ×2 200", r.status_code == 200, r.text[:300])
        t = r.json()["data"]
        its = t["items"]
        check("2b 2 kalem, ders yok, 20 soru, TYT",
              len(its) == 2 and all(i["exam_kind"] == "brans" and i["question_count"] == 20
                                    and i["exam_section"] == "tyt" for i in its),
              str([(i["exam_kind"], i["question_count"], i["exam_section"]) for i in its]))
        check("2c başlık", "TYT Fen Bilimleri branş denemesi" in t["title"], t["title"])

        with SessionLocal() as db:
            task = db.get(Task, t["id"])
            check("2d etiket", sorted(i.label for i in task.book_items)
                  == ["TYT Fen Bilimleri 1/2", "TYT Fen Bilimleri 2/2"])
            check("3a deneme sayılır", gorev_stats.classify_gorev(task) == "deneme", gorev_stats.classify_gorev(task))
            s = gorev_stats.summarize([task])
            check("3b test hacmine girmez", s.test_planned == 0 and s.deneme_planned == 2, f"{s.test_planned}/{s.deneme_planned}")
            task.is_draft = False
            db.commit()

        r = c.post(f"/api/v2/teacher/students/{eid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "group_key": "ayt_fen", "count": 1})
        check("4 uygun olmayan grup 422", r.status_code == 422, r.text[:200])

        s = login(f"{PFX}_say@test.invalid")
        r = s.post(f"/api/v2/student/tasks/{t['id']}/deneme-results",
                   json={"rows": [{"item_id": its[0]["id"], "solved": True, "correct": 14, "wrong": 4}]})
        check("5a sonuç 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            rec = db.query(ExamResult).filter(ExamResult.task_book_item_id == its[0]["id"]).first()
            nets = json.loads(rec.subject_nets) if rec and rec.subject_nets else []
            check("5b Denemeler kaydı TYT Fen Bilimleri serisi",
                  rec is not None and nets and nets[0]["name"] == "TYT Fen Bilimleri", str(nets))
            check("5c net 14 − 4/4 = 13", rec is not None and rec.net == 13, str(rec and rec.net))

        tp = c.get(f"/api/v2/teacher/students/{sid}/deneme-options").json()["templates"]
        check("6 kalıp group_key taşır",
              any(x.get("group_key") == "tyt_fen" and x["count"] == 2 and x["question_count"] == 20 for x in tp), str(tp))
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
