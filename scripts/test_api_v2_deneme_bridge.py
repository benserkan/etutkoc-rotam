"""Görev denemesi → Denemeler köprüsü D3 smoke (2026-10-20).

   1. Branş (kitapsız, 2 adet): 1. satır sonuçlu → Denemeler'de kayıt (Programdan, branş serisi,
      net, ders kırılımı); 2. satır "sonra gireceğim" → kayıt YOK
   2. Koçun Denemeler listesinde görünür · seri "tyt~matematik" · scope_forced değil
   3. Sonuç değişir → aynı kayıt güncellenir · "sonra gireceğim"e dönerse kayıt silinir
   4. Sonucu eksik denemeler: öğrenci + koç uçları (sayı, gün)
   5. Genel TYT (120) → genel seri "tyt"
   6. LGS Sayısal Bölüm (40/90) genel seriye karışmaz → bölüm serisi
   7. Koç kaydı Denemeler'den düzenleyemez (409 task_linked) · koç sonuç ucu kayıt açar
   8. Görev başka güne taşınınca deneme tarihi de taşınır
   9. Geri alma (uncomplete) → kayıt silinir · görev silme → kayıt silinir
  10. PDF ile "yerine yazılmış" kayda görev dokunmaz
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ExamResult, Subject, Task, TaskBookItem, Track, User, UserRole  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dbr_{secrets.token_hex(3)}"
PWD = "DenemeBr!2345x"
today = date.today()
passed = 0
failed: list[str] = []
ids: dict = {"users": []}


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


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                     role=UserRole.TEACHER, is_active=True)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  track=Track.SAYISAL, must_change_password=False)
        lgs = User(email=f"{PFX}_l@test.invalid", password_hash=hash_password(PWD), full_name="LGS Öğrenci",
                   role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=8,
                   must_change_password=False)
        db.add_all([st, lgs]); db.flush()
        mat = Subject(name="TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(mat); db.commit()
        ids["users"] += [coach.id, st.id, lgs.id]
        return {"coach": coach.id, "st": st.id, "lgs": lgs.id, "mat": mat.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(u)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def recs(student_id):
    with SessionLocal() as db:
        rows = (db.query(ExamResult).filter(ExamResult.student_id == student_id)
                .order_by(ExamResult.id).all())
        db.expunge_all()
        return rows


def main() -> int:
    d = seed()
    print(f"\n=== deneme köprüsü D3 — {PFX} ===\n")
    try:
        c = login(f"{PFX}_t@test.invalid")
        s = login(f"{PFX}_s@test.invalid")
        sid = d["st"]
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": today.isoformat(), "kind": "brans", "subject_id": d["mat"], "count": 2,
                         "question_count": 20, "name": "Özel ders matematik", "is_draft": False})
        assert r.status_code == 200, r.text
        tid = r.json()["data"]["id"]
        i1, i2 = sorted(x["id"] for x in r.json()["data"]["items"])

        # 1
        r = s.post(f"/api/v2/student/tasks/{tid}/deneme-results",
                   json={"rows": [{"item_id": i1, "solved": True, "correct": 14, "wrong": 4, "duration_minutes": 30},
                                  {"item_id": i2, "solved": True}]})
        check("1a sonuç kaydı 200", r.status_code == 200, r.text[:200])
        inv = r.json().get("invalidate", [])
        check("1b invalidate Denemeler önekleri", "student:exams" in inv
              and any(k.endswith(f"students:{sid}:exams") for k in inv), str(inv))
        rows = recs(sid)
        check("1c tek kayıt (2. satır sonuç bekliyor)", len(rows) == 1, str([x.title for x in rows]))
        rec = rows[0] if rows else None
        if rec:
            check("1d kaynak 'task' + kalem bağı", rec.import_source == "task" and rec.task_book_item_id == i1)
            check("1e başlık 1. deneme ekli", rec.title == "Özel ders matematik · 1. deneme", rec.title)
            check("1f TYT, 14D 4Y 2B, net 13", rec.section == ExamSection.TYT
                  and (rec.total_correct, rec.total_wrong, rec.total_blank) == (14, 4, 2) and rec.net == 13.0,
                  f"{rec.section} {rec.total_correct}/{rec.total_wrong}/{rec.total_blank} {rec.net}")
            sn = json.loads(rec.subject_nets or "[]")
            check("1g ders kırılımı 'TYT Matematik'", len(sn) == 1 and sn[0]["name"] == "TYT Matematik", str(sn))
            meta = json.loads(rec.analysis_meta or "{}")
            check("1h süre + kaynak meta", meta.get("duration_minutes") == 30 and meta.get("source") == "task", str(meta))

        # 2
        r = c.get(f"/api/v2/teacher/students/{sid}/exams")
        row = next((x for x in r.json().get("program_rows", []) if x["id"] == (rec.id if rec else -1)), None)
        check("2a koç Denemeler'de AYRI 'Programdaki denemeler' bölümünde", row is not None, r.text[:200])
        check("2a2 analiz listesine/özetine KARIŞMAZ",
              all(x["id"] != (rec.id if rec else -1) for x in r.json().get("rows", []))
              and r.json()["summary"]["count"] == len(r.json().get("rows", [])), r.text[:200])
        if row:
            check("2b seri tyt~matematik, branş", row["series_key"] == "tyt~matematik" and row["scope"] == "brans",
                  f"{row['series_key']} {row['scope']}")
            check("2c kapsam zorlanmadı", row["scope_forced"] is False)
            check("2d import_source task", row["import_source"] == "task")
        r = s.get("/api/v2/student/exams")
        check("2e öğrenci Denemelerim'de ayrı bölümde",
              any(x["id"] == (rec.id if rec else -1) for x in r.json().get("program_rows", []))
              and all(x["id"] != (rec.id if rec else -1) for x in r.json().get("rows", [])), r.text[:200])

        # 3
        s.post(f"/api/v2/student/tasks/{tid}/deneme-results",
               json={"rows": [{"item_id": i1, "solved": True, "correct": 16, "wrong": 0},
                              {"item_id": i2, "solved": True}]})
        rows = recs(sid)
        check("3a güncellendi (aynı kayıt, net 16)", len(rows) == 1 and rec and rows[0].id == rec.id
              and rows[0].net == 16.0, str([(x.id, x.net) for x in rows]))
        s.post(f"/api/v2/student/tasks/{tid}/deneme-results",
               json={"rows": [{"item_id": i1, "solved": False}, {"item_id": i2, "solved": True}]})
        check("3b 'çözmedim' → kayıt silindi", recs(sid) == [])

        # 4
        r = s.get("/api/v2/student/deneme-pending")
        check("4a öğrenci: 1 deneme sonuç bekliyor", r.status_code == 200 and r.json()["count"] == 1
              and r.json()["tasks"] == 1, r.text[:200])
        r = c.get(f"/api/v2/teacher/students/{sid}/deneme-pending")
        check("4b koç: aynı liste", r.status_code == 200 and r.json()["count"] == 1
              and r.json()["rows"][0]["days_waiting"] == 0, r.text[:200])
        s.post(f"/api/v2/student/tasks/{tid}/deneme-results",
               json={"rows": [{"item_id": i1, "solved": True, "correct": 10, "wrong": 2},
                              {"item_id": i2, "solved": True, "correct": 12, "wrong": 0}]})
        rows = recs(sid)
        check("4c iki satır sonuçlu → 2 kayıt, 2. deneme ekli",
              len(rows) == 2 and sorted(x.title[-9:] for x in rows) == ["1. deneme", "2. deneme"],
              str([x.title for x in rows]))
        check("4d bekleyen kalmadı", s.get("/api/v2/student/deneme-pending").json()["count"] == 0)

        # 5 genel TYT
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": today.isoformat(), "kind": "genel", "genel_key": "tyt", "count": 1,
                         "name": "Özdebir TG-4", "is_draft": False})
        assert r.status_code == 200, r.text
        gtid = r.json()["data"]["id"]
        gi = r.json()["data"]["items"][0]["id"]
        s.post(f"/api/v2/student/tasks/{gtid}/deneme-results",
               json={"rows": [{"item_id": gi, "solved": True, "correct": 80, "wrong": 20}]})
        r = c.get(f"/api/v2/teacher/students/{sid}/exams")
        g = next((x for x in r.json()["program_rows"] if x["title"].startswith("Özdebir TG-4")), None)
        check("5a genel TYT kaydı, seri 'tyt'", g is not None and g["series_key"] == "tyt" and g["scope"] == "genel",
              str(g)[:200])
        check("5b genel net 75", g is not None and g["net"] == 75.0)
        r = c.get(f"/api/v2/teacher/students/{sid}/exam-progress")
        check("5c gelişim raporu program denemesini görmez",
              r.status_code == 200 and not r.json().get("exams") and not r.json().get("section_options"), r.text[:200])

        # 6 LGS sayısal bölüm
        lc = login(f"{PFX}_l@test.invalid")
        c = login(f"{PFX}_t@test.invalid")
        r = c.post(f"/api/v2/teacher/students/{d['lgs']}/deneme-tasks",
                   json={"date": today.isoformat(), "kind": "genel", "genel_key": "lgs_sayisal", "count": 1,
                         "is_draft": False})
        assert r.status_code == 200, r.text
        ltid = r.json()["data"]["id"]
        li = r.json()["data"]["items"][0]["id"]
        lc.post(f"/api/v2/student/tasks/{ltid}/deneme-results",
                json={"rows": [{"item_id": li, "solved": True, "correct": 30, "wrong": 6}]})
        r = c.get(f"/api/v2/teacher/students/{d['lgs']}/exams")
        lr = r.json()["program_rows"][0] if r.json().get("program_rows") else None
        check("6a LGS sayısal bölüm genel seriye karışmaz", lr is not None and lr["series_key"] != "lgs"
              and lr["scope"] == "brans", str(lr)[:250])
        check("6b LGS net 28 (3 yanlış 1 doğru)", lr is not None and lr["net"] == 28.0, str(lr and lr["net"]))

        # 7
        rec_id = recs(sid)[0].id
        r = c.post(f"/api/v2/teacher/exams/{rec_id}",
                   json={"title": "x", "exam_date": today.isoformat(), "section": "tyt",
                         "total_correct": 1, "total_wrong": 0, "total_blank": 0})
        check("7a koç Denemeler'den düzenleyemez (409)", r.status_code == 409
              and r.json()["detail"]["code"] == "task_linked", r.text[:200])
        r = c.post(f"/api/v2/teacher/tasks/{tid}/deneme-results",
                   json={"rows": [{"item_id": i1, "solved": True, "correct": 9, "wrong": 3},
                                  {"item_id": i2, "solved": True, "correct": 12, "wrong": 0}]})
        check("7b koç sonuç ucu 200 + Denemeler invalidate", r.status_code == 200
              and any(k.endswith(f"students:{sid}:exams") for k in r.json()["invalidate"]), r.text[:200])
        n1 = next(x for x in recs(sid) if x.task_book_item_id == i1)
        check("7c koçun düzeltmesi kayda yansıdı (net 8,25)", n1.net == 8.25, str(n1.net))

        # 8 tarih taşı
        new_day = today - timedelta(days=1)
        r = c.patch(f"/api/v2/teacher/tasks/{tid}", json={"date": new_day.isoformat()})
        check("8a görev taşındı", r.status_code == 200, r.text[:200])
        dates = {x.exam_date for x in recs(sid) if x.task_book_item_id in (i1, i2)}
        check("8b deneme tarihi de taşındı", dates == {new_day}, str(dates))

        # 10 PDF yerine yazılmış
        with SessionLocal() as db:
            x = db.query(ExamResult).filter(ExamResult.task_book_item_id == i2).first()
            x.import_source = "pdf_import"; x.net = 99.0
            db.commit()
        s = login(f"{PFX}_s@test.invalid")
        s.post(f"/api/v2/student/tasks/{tid}/deneme-results",
               json={"rows": [{"item_id": i1, "solved": True, "correct": 9, "wrong": 3},
                              {"item_id": i2, "solved": True, "correct": 1, "wrong": 1}]})
        x2 = next(x for x in recs(sid) if x.task_book_item_id == i2)
        check("10a PDF kaydına görev dokunmadı", x2.net == 99.0 and x2.import_source == "pdf_import", str(x2.net))

        # 9 geri al + sil
        r = s.post(f"/api/v2/student/tasks/{gtid}/uncomplete")
        check("9a geri alma 200", r.status_code == 200, r.text[:200])
        check("9b geri alınan genel deneme kaydı silindi",
              not any(x.task_book_item_id == gi for x in recs(sid)))
        r = c.delete(f"/api/v2/teacher/tasks/{tid}")
        check("9c görev silindi", r.status_code == 200, r.text[:200])
        left = [x for x in recs(sid) if x.task_book_item_id in (i1, i2) or x.import_source == "task"]
        check("9d görevin 'task' kaydı silindi (PDF kaydı kalır)",
              all(x.import_source != "task" for x in left), str([(x.title, x.import_source) for x in left]))
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
