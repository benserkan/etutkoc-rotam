"""Konu × deneme analizi (Faz 2) smoke — ısı haritası + fırsat + unutulan.

PYTHONPATH=. python scripts/test_api_v2_exam_topic_analysis.py
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, ".")

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.services.security import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import (
    ExamResult,
    ExamResultQuestion,
    ExamSection,
    Subject,
    SuspiciousIp,
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter

PFX = "eta-smoke"
PASSWORD = "Passw0rd!eta"

passed = 0
failed: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name} — {detail}")


def topic_id(db, subject_name: str, topic_name: str) -> int:
    t = (
        db.query(Topic).join(Subject, Subject.id == Topic.subject_id)
        .filter(Subject.is_builtin.is_(True), Subject.name == subject_name,
                Topic.name == topic_name)
        .first()
    )
    assert t is not None, f"builtin konu yok: {subject_name} / {topic_name}"
    return t.id


def add_exam(db, student_id, coach_id, title, d, section, rows):
    """rows: [(topic_id|None, result)] — sayaçlar satırlardan türetilir."""
    c = sum(1 for _, r in rows if r == "dogru")
    y = sum(1 for _, r in rows if r == "yanlis")
    b = sum(1 for _, r in rows if r == "bos")
    pen = 3 if section == ExamSection.LGS else 4
    e = ExamResult(
        student_id=student_id, created_by_id=coach_id, title=title,
        exam_date=d, section=section, total_correct=c, total_wrong=y,
        total_blank=b, net=round(max(c - y / pen, 0), 2),
        import_source="pdf_import",
    )
    db.add(e)
    db.flush()
    for i, (tid, res) in enumerate(rows, start=1):
        db.add(ExamResultQuestion(
            exam_result_id=e.id, question_no=i, subject_name_raw="X",
            topic_id=tid, topic_label_raw="etiket", result=res,
            is_suspect=False,
        ))
    return e.id


def main() -> int:
    print(f"\n=== Konu × deneme analizi smoke — {PFX} ===\n")
    with SessionLocal() as db:
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False)
        other = User(email=f"{PFX}-t2@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Yabancı Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False)
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True,
                       grade_level=12, must_change_password=False)
        db.add_all([coach, other, student])
        db.flush()
        student.teacher_id = coach.id
        db.commit()
        ids = {
            "coach": coach.id, "other": other.id, "student": student.id,
            "rasyonel": topic_id(db, "TYT Matematik", "Rasyonel Sayılar"),
            "paragraf": topic_id(db, "TYT Türkçe", "Paragraf"),
            "temel": topic_id(db, "TYT Matematik", "Temel Kavramlar"),
            "trig": topic_id(db, "AYT Matematik", "Trigonometri"),
        }
        R, P, T = ids["rasyonel"], ids["paragraf"], ids["temel"]
        # 3 TYT denemesi (tarih artan) — Rasyonel önce iyi sonra bozuk (unutulan),
        # Paragraf sürekli kötü (en büyük fırsat), Temel karışık + 1 konusuz satır
        add_exam(db, student.id, coach.id, "TYT-1", date(2026, 3, 1),
                 ExamSection.TYT,
                 [(R, "dogru"), (R, "dogru"), (P, "dogru"), (P, "yanlis"),
                  (T, "bos"), (None, "dogru")])
        add_exam(db, student.id, coach.id, "TYT-2", date(2026, 4, 1),
                 ExamSection.TYT,
                 [(R, "dogru"), (R, "dogru"), (P, "yanlis"), (P, "yanlis"),
                  (T, "dogru"), (T, "bos")])
        add_exam(db, student.id, coach.id, "TYT-3", date(2026, 5, 1),
                 ExamSection.TYT,
                 [(R, "yanlis"), (R, "yanlis"), (P, "yanlis"), (P, "bos"),
                  (T, "dogru")])
        # 1 AYT denemesi (tür filtresi) + 1 satırsız manuel deneme (analize girmez)
        add_exam(db, student.id, coach.id, "AYT-1", date(2026, 5, 10),
                 ExamSection.AYT_SAY, [(ids["trig"], "dogru"), (ids["trig"], "yanlis")])
        db.add(ExamResult(student_id=student.id, created_by_id=coach.id,
                          title="Manuel", exam_date=date(2026, 5, 12),
                          section=ExamSection.TYT, total_correct=10,
                          total_wrong=5, total_blank=5, net=8.75))
        db.commit()

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    try:
        ct = TestClient(app)
        cs = TestClient(app)
        co = TestClient(app)
        anon = TestClient(app)
        for cli, mail in ((ct, f"{PFX}-t@t.invalid"), (cs, f"{PFX}-s@t.invalid"),
                          (co, f"{PFX}-t2@t.invalid")):
            r = cli.post("/api/v2/auth/login", json={"email": mail, "password": PASSWORD})
            assert r.status_code == 200, r.text

        url = f"/api/v2/teacher/students/{ids['student']}/exam-topic-analysis"

        r = anon.get(url)
        check("1. anonim → 401", r.status_code == 401, r.text[:100])

        r = ct.get(url)
        d = r.json() if r.status_code == 200 else {}
        check("2. varsayılan tür = TYT (en çok deneme) + 3 deneme + 17 soru",
              r.status_code == 200 and d.get("section") == "tyt"
              and len(d.get("exams", [])) == 3
              and d.get("analyzed_question_count") == 17
              and d.get("unmatched_questions") == 1, r.text[:200])

        opts = {o["value"]: o["count"] for o in d.get("section_options", [])}
        check("3. tür seçenekleri soru-satırlı denemelerden (tyt 3 · ayt_say 1; manuel yok)",
              opts == {"tyt": 3, "ayt_say": 1}, str(opts))

        rows = {t["topic_id"]: t for t in d.get("topics", [])}
        ras = rows.get(ids["rasyonel"], {})
        check("4. ısı haritası satırı: Rasyonel 6 soru · 4D 2Y · acc .667 · 3 hücre",
              ras.get("total") == 6 and ras.get("correct") == 4
              and ras.get("wrong") == 2 and ras.get("exams_seen") == 3
              and len(ras.get("cells", [])) == 3
              and abs(ras.get("accuracy", 0) - 0.667) < 0.01, str(ras)[:200])

        opp = d.get("opportunities", [])
        check("5. net fırsat sıralı: 1) Paragraf (+2.0 net/deneme)",
              len(opp) >= 2 and opp[0]["topic_id"] == ids["paragraf"]
              and abs(opp[0]["net_gain_per_exam"] - 2.0) < 0.01,
              str(opp[:2])[:250])

        fg = {t["topic_id"] for t in d.get("forgotten", [])}
        check("6. UNUTULAN yakalandı (Rasyonel: ilk yarı %100 → son %0)",
              ids["rasyonel"] in fg, str(d.get("forgotten"))[:200])

        r = ct.get(url + "?section=ayt_say")
        d2 = r.json() if r.status_code == 200 else {}
        check("7. tür filtresi: ayt_say → 1 deneme · Trigonometri satırı",
              r.status_code == 200 and len(d2.get("exams", [])) == 1
              and len(d2.get("topics", [])) == 1
              and d2["topics"][0]["topic_id"] == ids["trig"], r.text[:200])

        r = co.get(url)
        check("8. yabancı koç → 404", r.status_code == 404, r.text[:100])

        r = cs.get("/api/v2/student/exam-topic-analysis")
        d3 = r.json() if r.status_code == 200 else {}
        check("9. öğrenci kendi analizini görür (aynı veri)",
              r.status_code == 200 and d3.get("analyzed_question_count") == 17,
              r.text[:150])

        r = cs.get(url)
        check("10. öğrenci koç ucuna erişemez → 403",
              r.status_code == 403, r.text[:100])

    finally:
        with SessionLocal() as db:
            uids = [ids["coach"], ids["other"], ids["student"]]
            exam_ids = [e.id for e in db.query(ExamResult).filter(
                ExamResult.student_id.in_(uids)).all()]
            if exam_ids:
                db.execute(sa_delete(ExamResultQuestion).where(
                    ExamResultQuestion.exam_result_id.in_(exam_ids)))
                db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exam_ids)))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAILED: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
