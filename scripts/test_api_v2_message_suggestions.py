# -*- coding: utf-8 -*-
"""Bugünün mesajları (WhatsApp mesaj önerileri) smoke — 2026-11-14."""
from __future__ import annotations

import json
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import ParentStudentLink, Task, User, UserRole
from app.models.curriculum import ExamSection
from app.models.exam_parent_report import ExamParentReport
from app.models.exam_result import ExamResult
from app.models.message_suggestion import MessageSuggestionAction
from app.models.task import TaskStatus, TaskType
from app.models.whatsapp_dispatch_log import WhatsAppDispatchLog
from app.services import message_suggestions as ms
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"msg_{secrets.token_hex(3)}"
PWD = "MsgSugg!2345"
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


def seed():
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    today = ms._tr_today()
    with SessionLocal() as db:
        def u(tag, role, **kw):
            x = User(email=f"{PFX}_{tag}@test.invalid", password_hash=pwd, full_name=f"Emre {tag}",
                     role=role, is_active=True, password_changed_at=now, must_change_password=False,
                     created_at=now - timedelta(days=60), **kw)
            db.add(x); db.flush(); return x
        t = u("t", UserRole.TEACHER)
        t2 = u("t2", UserRole.TEACHER)
        s = u("s", UserRole.STUDENT, teacher_id=t.id, grade_level=8, phone="905321110001")
        p = u("p", UserRole.PARENT, phone="905321110002")
        db.add(ParentStudentLink(parent_id=p.id, student_id=s.id, is_primary=True))
        y = today - timedelta(days=1)
        for i in range(3):
            db.add(Task(student_id=s.id, date=y, type=TaskType.OTHER, title=f"Görev {i}",
                        status=TaskStatus.PENDING, is_draft=False))
        ex = ExamResult(student_id=s.id, created_by_id=t.id, title="LGS Deneme 4", exam_date=y,
                        section=ExamSection.LGS, total_correct=60, total_wrong=12, total_blank=18, net=56.0,
                        subject_nets=json.dumps([]))
        db.add(ex); db.commit()
        return {"t": t.id, "t2": t2.id, "s": s.id, "p": p.id, "ex": ex.id}


def cleanup(d):
    with SessionLocal() as db:
        db.execute(delete(MessageSuggestionAction).where(MessageSuggestionAction.student_id == d["s"]))
        db.execute(delete(WhatsAppDispatchLog).where(WhatsAppDispatchLog.sender_user_id.in_([d["t"], d["t2"]])))
        db.execute(delete(ExamParentReport).where(ExamParentReport.student_id == d["s"]))
        db.execute(delete(ExamResult).where(ExamResult.student_id == d["s"]))
        db.execute(delete(Task).where(Task.student_id == d["s"]))
        db.execute(delete(ParentStudentLink).where(ParentStudentLink.student_id == d["s"]))
        db.execute(delete(User).where(User.id.in_([d["t"], d["t2"], d["s"], d["p"]])))
        db.commit()


def login(c, tag):
    get_login_limiter().reset()
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{tag}@test.invalid", "password": PWD})
    assert r.status_code == 200, r.text


def main():
    d = seed()
    try:
        c = TestClient(app)
        login(c, "t")
        r = c.get("/api/v2/teacher/message-suggestions")
        check("1 liste 200", r.status_code == 200, r.text[:200])
        items = r.json().get("items", [])
        mine = [i for i in items if i["student_id"] == d["s"]]
        keys = {(i["audience"], i["key"].split(":")[0]) for i in mine}
        check("2 öğrenciye işaretleme hatırlatması", ("student", "remind_mark") in keys, str(keys))
        check("3 veliye deneme analizi", ("parent", "report_exam") in keys, str(keys))
        check("4 öğrenciye deneme analizi", ("student", "report_exam") in keys, str(keys))
        check("5 veri güvenilirliği listede yok",
              not any(k[1] in ("bulk_marking", "dy_missing") for k in keys), str(keys))
        rep = next(i for i in mine if i["audience"] == "parent" and i["key"].startswith("report_exam"))
        check("6 rapor metninde bağlantı yer tutucusu", ms.LINK_TOKEN in rep["text"])
        check("7 veli hedefi telefonlu", rep["targets"] and rep["targets"][0]["can_message"], str(rep["targets"]))
        check("8 bugün gönderilen 0", r.json()["sent_today"] == 0)

        r = c.post("/api/v2/teacher/message-suggestions/send", json={
            "student_id": d["s"], "audience": "parent", "key": rep["key"], "text": rep["text"],
            "target_user_id": d["p"]})
        check("9 gönder 200", r.status_code == 200, r.text[:200])
        body = r.json()
        check("10 wa.me bağlantısı velinin numarasıyla", "wa.me/905321110002" in body.get("wa_url", ""),
              body.get("wa_url", "")[:80])
        check("11 metinde gerçek rapor bağlantısı", "%2Frapor%2F" in body.get("wa_url", ""), "")
        check("12 sayaç 1", body.get("sent_today") == 1, str(body))

        r = c.get("/api/v2/teacher/message-suggestions", params={"student_id": d["s"]})
        after = r.json()["items"]
        check("13 gönderilen öneri listeden düştü",
              not any(i["audience"] == "parent" and i["key"] == rep["key"] for i in after))
        check("14 aynı raporun öğrenci önerisi duruyor",
              any(i["audience"] == "student" and i["key"] == rep["key"] for i in after))
        rem = next(i for i in after if i["key"].startswith("remind_mark"))
        r = c.post("/api/v2/teacher/message-suggestions/skip",
                   json={"student_id": d["s"], "audience": "student", "key": rem["key"]})
        check("15 atla 200", r.status_code == 200, r.text[:120])
        after2 = c.get("/api/v2/teacher/message-suggestions", params={"student_id": d["s"]}).json()
        check("16 atlanan düştü, sayaç değişmedi",
              not any(i["key"] == rem["key"] for i in after2["items"]) and after2["sent_today"] == 1)
        r = c.post("/api/v2/teacher/message-suggestions/send", json={
            "student_id": d["s"], "audience": "parent", "key": "yok:1", "text": "x", "target_user_id": d["p"]})
        check("17 geçersiz öneri 409", r.status_code == 409, str(r.status_code))
        r = c.post("/api/v2/teacher/message-suggestions/send", json={
            "student_id": d["s"], "audience": "student", "key": rep["key"], "text": rep["text"],
            "target_user_id": d["p"]})
        check("18 öğrenci önerisini veliye gönderme 404", r.status_code == 404, str(r.status_code))

        par = [i for i in after if i["audience"] == "parent"]
        check("21 veli mesajında Rotam panel bağlantısı",
              all(f"/parent/students/{d['s']}" in i["text"] or ms.LINK_TOKEN in i["text"] for i in par), str(len(par)))
        with SessionLocal() as db:
            st = db.get(User, d["s"]); st.is_paused = True; db.commit()
        r = c.get("/api/v2/teacher/message-suggestions", params={"student_id": d["s"]})
        check("22 moladaki öğrenciye öneri yok", r.status_code in (200, 404) and not (r.json().get("items") if r.status_code == 200 else []),
              r.text[:120])
        with SessionLocal() as db:
            st = db.get(User, d["s"]); st.is_paused = False; db.commit()

        c2 = TestClient(app)
        login(c2, "t2")
        r = c2.get("/api/v2/teacher/message-suggestions", params={"student_id": d["s"]})
        check("19 başka koç 404", r.status_code == 404, str(r.status_code))
        r = c2.post("/api/v2/teacher/message-suggestions/skip",
                    json={"student_id": d["s"], "audience": "parent", "key": rep["key"]})
        check("20 başka koç atlayamaz 404", r.status_code == 404, str(r.status_code))
    finally:
        cleanup(d)
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
