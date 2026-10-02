"""Smoke: deneme analizi Faz 1 — puan/sıralama satırda + soru listesi ucu.

  GET /api/v2/teacher/students/{id}/exams     → satırda score (analysis_meta.score_info)
  GET /api/v2/teacher/exams/{id}/questions    → soru satırları (sahiplik 404)
  GET /api/v2/student/exams/{id}/questions    → yalnız kendi denemesi
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, ExamResult, User, UserRole
from app.models.exam_result import ExamResultQuestion, ExamSection
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"exf1_{secrets.token_hex(3)}"
PW = "ExamFaz1!@xyz"
FAILS: list[str] = []
N = 0


def check(label, cond, detail=""):
    global N
    N += 1
    print(("  OK   " if cond else "  FAIL ") + label + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(label)


def login(c, email):
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text


def main() -> int:
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    ids = {}
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        mk = lambda e, n, role, **kw: User(email=e, password_hash=hash_password(PW), full_name=n, role=role,
                                          is_active=True, password_changed_at=now,
                                          must_change_password=False, email_verified_at=now, **kw)
        t = mk(f"{PFX}_t@test.invalid", "Faz1 Koç", UserRole.TEACHER)
        t2 = mk(f"{PFX}_t2@test.invalid", "Faz1 Koç2", UserRole.TEACHER)
        db.add_all([t, t2]); db.flush()
        s = mk(f"{PFX}_s@test.invalid", "Faz1 Öğrenci", UserRole.STUDENT, teacher_id=t.id, grade_level=12)
        s2 = mk(f"{PFX}_s2@test.invalid", "Faz1 Öğrenci2", UserRole.STUDENT, teacher_id=t.id, grade_level=12)
        db.add_all([s, s2]); db.flush()
        e1 = ExamResult(student_id=s.id, created_by_id=t.id, title="Deneme A", exam_date=date(2026, 9, 1),
                        section=ExamSection.TYT, total_correct=2, total_wrong=1, total_blank=1, net=1.75,
                        subject_nets=json.dumps([{"name": "Türkçe", "correct": 2, "wrong": 1, "blank": 1, "net": 1.75}]),
                        import_source="pdf_import",
                        analysis_meta=json.dumps({"score_info": {"score": 363.22, "rank_overall": 1234,
                                                                 "participants": "20000", "extra": None}}))
        e2 = ExamResult(student_id=s.id, created_by_id=t.id, title="Elle", exam_date=date(2026, 9, 8),
                        section=ExamSection.TYT, total_correct=10, total_wrong=0, total_blank=0, net=10.0)
        e3 = ExamResult(student_id=s2.id, created_by_id=t.id, title="Başkası", exam_date=date(2026, 9, 8),
                        section=ExamSection.TYT, total_correct=1, total_wrong=0, total_blank=0, net=1.0,
                        import_source="pdf_import")
        db.add_all([e1, e2, e3]); db.flush()
        for no, dc, oc, res in ((1, "A", "A", "dogru"), (2, "B", "C", "yanlis"), (3, "C", None, "bos"), (4, "D", "D", "dogru")):
            db.add(ExamResultQuestion(exam_result_id=e1.id, question_no=no, subject_name_raw="TÜRKÇE",
                                      topic_label_raw="Paragraf", correct_answer=dc, student_answer=oc, result=res))
        db.commit()
        ids = dict(t=t.id, t2=t2.id, s=s.id, s2=s2.id, e1=e1.id, e2=e2.id, e3=e3.id)
    try:
        c = TestClient(app); login(c, f"{PFX}_t@test.invalid")
        rows = c.get(f"/api/v2/teacher/students/{ids['s']}/exams?period=all").json()["rows"]
        r1 = next(r for r in rows if r["id"] == ids["e1"])
        r2 = next(r for r in rows if r["id"] == ids["e2"])
        check("1 puan/sıralama satırda (katılımcı metinden sayıya)",
              r1["score"] == {"score": 363.22, "rank_overall": 1234, "participants": 20000, "extra": None}, str(r1.get("score")))
        check("2 puanı olmayan denemede score null", r2.get("score") is None, str(r2.get("score")))
        r = c.get(f"/api/v2/teacher/exams/{ids['e1']}/questions")
        items = r.json().get("items", [])
        check("3 soru listesi 4 satır, sırayla", r.status_code == 200 and [i["question_no"] for i in items] == [1, 2, 3, 4], r.text[:200])
        check("4 satır alanları (ders, konu, anahtar, öğrenci, sonuç)",
              items and items[2] == {"subject": "TÜRKÇE", "question_no": 3, "topic_label": "Paragraf", "topic_name": None,
                                     "correct_answer": "C", "student_answer": None, "result": "bos"}, str(items[2] if items else None))
        r = c.get(f"/api/v2/teacher/exams/{ids['e2']}/questions")
        check("5 elle girilen deneme → boş liste", r.status_code == 200 and r.json()["items"] == [])
        c2 = TestClient(app); login(c2, f"{PFX}_t2@test.invalid")
        check("6 başka koç → 404", c2.get(f"/api/v2/teacher/exams/{ids['e1']}/questions").status_code == 404)
        cs = TestClient(app); login(cs, f"{PFX}_s@test.invalid")
        r = cs.get(f"/api/v2/student/exams/{ids['e1']}/questions")
        check("7 öğrenci kendi denemesinin sorularını görür", r.status_code == 200 and len(r.json()["items"]) == 4)
        check("8 öğrenci başkasının denemesine → 404", cs.get(f"/api/v2/student/exams/{ids['e3']}/questions").status_code == 404)
        check("9 öğrenci koç ucuna → 403", cs.get(f"/api/v2/teacher/exams/{ids['e1']}/questions").status_code == 403)
        srows = cs.get("/api/v2/student/exams?period=all").json()["rows"]
        check("10 öğrenci listesinde de score", any(x.get("score") and x["score"]["rank_overall"] == 1234 for x in srows))
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_([ids["e1"], ids["e2"], ids["e3"]])))
            db.execute(sa_delete(ExamResult).where(ExamResult.id.in_([ids["e1"], ids["e2"], ids["e3"]])))
            uids = [ids["s"], ids["s2"], ids["t"], ids["t2"]]
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
    print(f"\n{N - len(FAILS)}/{N} passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
