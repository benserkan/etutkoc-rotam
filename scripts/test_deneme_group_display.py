"""Birleşik branş denemesi grubu kendi başlığıyla (2026-11-08, karar A).

TYT Fen / TYT Sosyal / AYT Fen gibi denemeler tek derse bağlı değil; ızgara, gün kartı ve
ders dağılımında "DİĞER"e düşüyordu. Artık kalem `exam_group` taşır, ders dağılımına grup
satırı (is_group, negatif sabit kimlik) eklenir.
  1. Koç görevi: kalemde exam_group = "TYT Fen Bilimleri"
  2. Ders dağılımı: "TYT Fen Bilimleri" satırı, is_group, 2 deneme, kimlik < 0
  3. Derse bağlı branş denemesinde exam_group yok
  4. Öğrenci görevi de exam_group taşır
  5. Jinja yolu (include_groups=False) değişmedi
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
from app.models import ExamResult, Subject, Task, TaskBookItem, User, UserRole  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.routes.teacher_program import compute_day_subject_summary  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dgd_{secrets.token_hex(3)}"
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
            co = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                      role=UserRole.TEACHER, is_active=True)
            db.add(co); db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                      role=UserRole.STUDENT, is_active=True, teacher_id=co.id, is_graduate=True,
                      track=Track.SAYISAL, must_change_password=False)
            db.add(st); db.commit()
            uids += [co.id, st.id]
            sid = st.id
            bio = db.query(Subject).filter(Subject.is_builtin.is_(True), Subject.teacher_id.is_(None),
                                           Subject.name == "TYT Biyoloji", Subject.curriculum_model.is_(None)).first().id
        c = login(f"{PFX}_t@test.invalid")
        day = date.today().isoformat()
        t = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "group_key": "tyt_fen", "count": 2}).json()["data"]
        t2 = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                    json={"date": day, "kind": "brans", "subject_id": bio, "count": 1}).json()["data"]
        check("1 kalemde exam_group", all(i.get("exam_group") == "TYT Fen Bilimleri" for i in t["items"]),
              str([i.get("exam_group") for i in t["items"]]))
        check("3 derse bağlı denemede exam_group yok", all(i.get("exam_group") is None for i in t2["items"]))
        wk = c.get(f"/api/v2/teacher/students/{sid}/week?start={day}&end={day}").json()
        days = wk.get("days") or []
        summ = next((d.get("subject_summary") or [] for d in days if d.get("date") == day), [])
        g = next((x for x in summ if x["subject_name"] == "TYT Fen Bilimleri"), None)
        check("2 ders dağılımında grup satırı", g is not None and g.get("is_group") and g["denemeler"] == 2
              and g["subject_id"] < 0, str(g))
        with SessionLocal() as db:
            s = login(f"{PFX}_s@test.invalid")
            with SessionLocal() as db2:
                db2.get(Task, t["id"]).is_draft = False
                db2.commit()
            dd = s.get(f"/api/v2/student/day?date={day}").json()
            sit = [it for tk in dd.get("tasks", []) if tk["id"] == t["id"] for it in tk["items"]]
            check("4 öğrenci görevinde exam_group", sit and all(i.get("exam_group") == "TYT Fen Bilimleri" for i in sit),
                  str(sit[:1]))
            tasks = db.query(Task).filter(Task.student_id == sid).all()
            raw = compute_day_subject_summary(tasks, [])
            check("5 Jinja yolu grup satırı eklemez", raw == [], str(raw))
    finally:
        with SessionLocal() as db:
            if uids:
                tids = [x.id for x in db.query(Task).filter(Task.student_id.in_(uids)).all()]
                if tids:
                    db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
                    db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
                db.query(ExamResult).filter(ExamResult.student_id.in_(uids)).delete(synchronize_session=False)
                db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
                db.commit()
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
