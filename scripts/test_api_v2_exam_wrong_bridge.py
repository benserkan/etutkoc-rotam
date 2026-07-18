"""Faz 3 sinyal köprüleri smoke — deneme→YSA tek-tık + öneri/KS4 sinyalleri.

PYTHONPATH=. python scripts/test_api_v2_exam_wrong_bridge.py
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
    WrongQuestion,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = "ewb-smoke"
PASSWORD = "Passw0rd!ewb"

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


def add_exam(db, student_id, coach_id, title, d, rows):
    """rows: [(topic_id|None, question_no, result, label)]"""
    c = sum(1 for r in rows if r[2] == "dogru")
    y = sum(1 for r in rows if r[2] == "yanlis")
    b = sum(1 for r in rows if r[2] == "bos")
    e = ExamResult(
        student_id=student_id, created_by_id=coach_id, title=title,
        exam_date=d, section=ExamSection.TYT, total_correct=c, total_wrong=y,
        total_blank=b, net=round(max(c - y / 4, 0), 2), import_source="pdf_import",
    )
    db.add(e)
    db.flush()
    for tid, no, res, label in rows:
        db.add(ExamResultQuestion(
            exam_result_id=e.id, question_no=no, subject_name_raw="X",
            topic_id=tid, topic_label_raw=label, result=res, is_suspect=False,
        ))
    return e.id


def main() -> int:
    print(f"\n=== Deneme→YSA köprüsü + sinyaller smoke — {PFX} ===\n")
    with SessionLocal() as db:
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False)
        other = User(email=f"{PFX}-t2@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Yabancı", role=UserRole.TEACHER, is_active=True,
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
        }
        R, P, T = ids["rasyonel"], ids["paragraf"], ids["temel"]
        # E1: R 2Y + 1D · P 1Y(konulu) + 1 KONUSUZ yanlış + 1 boş ·
        #     T 2Y + 4D (doğruluk .667 → öneri sinyali ÜRETMEZ)
        ids["exam1"] = add_exam(db, student.id, coach.id, f"{PFX} TYT-1",
                                date(2026, 7, 1), [
            (R, 1, "yanlis", "Rasyonel Sayılar"),
            (R, 2, "yanlis", "Rasyonel Sayılar"),
            (R, 3, "dogru", "Rasyonel Sayılar"),
            (P, 4, "yanlis", "Paragraf"),
            (None, 5, "yanlis", "Gizemli Konu"),
            (P, 6, "bos", "Paragraf"),
            (T, 7, "yanlis", "Temel Kavramlar"),
            (T, 8, "yanlis", "Temel Kavramlar"),
            (T, 9, "dogru", "Temel Kavramlar"),
            (T, 10, "dogru", "Temel Kavramlar"),
            (T, 11, "dogru", "Temel Kavramlar"),
            (T, 12, "dogru", "Temel Kavramlar"),
        ])
        # E2: R 2Y daha → R toplam 4 yanlış = tam sinyal (1.0)
        ids["exam2"] = add_exam(db, student.id, coach.id, f"{PFX} TYT-2",
                                date(2026, 7, 10), [
            (R, 1, "yanlis", "Rasyonel Sayılar"),
            (R, 2, "yanlis", "Rasyonel Sayılar"),
            (P, 3, "dogru", "Paragraf"),
        ])
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

        url1 = f"/api/v2/teacher/exams/{ids['exam1']}/wrong-to-archive"
        wr1 = f"/api/v2/teacher/exams/{ids['exam1']}/wrong-rows"

        r = anon.post(url1)
        check("1. anonim → 401", r.status_code == 401, r.text[:100])

        r = ct.get(wr1)
        d = r.json() if r.status_code == 200 else {}
        rows = d.get("rows", [])
        by_no = {x["question_no"]: x for x in rows}
        check("2. seçici liste: 6 yanlış (1 konusuz) · hepsi arşivsiz · 6 hata türü",
              r.status_code == 200 and len(rows) == 6
              and sum(1 for x in rows if x["topic_id"] is None) == 1
              and all(not x["archived"] for x in rows)
              and len(d.get("error_types", [])) == 6, r.text[:250])

        # SEÇİCİ aktarım (2026-07-19 kararı: tümünü yığma YOK — kullanıcı seçer)
        items = [
            {"question_id": by_no[1]["question_id"], "error_type": "dikkat"},
            {"question_id": by_no[2]["question_id"]},
            {"question_id": by_no[5]["question_id"]},  # konusuz — atlanmalı
        ]
        r = ct.post(url1, json={"items": items})
        d = (r.json().get("data") or {}) if r.status_code == 200 else {}
        check("3. yalnız SEÇİLENLER aktarıldı (2 yeni · 1 konusuz atlandı)",
              r.status_code == 200 and d.get("created") == 2
              and d.get("skipped_no_topic") == 1 and d.get("total_wrong") == 3,
              r.text[:250])

        with SessionLocal() as db:
            wqs = db.query(WrongQuestion).filter(
                WrongQuestion.student_id == ids["student"]).all()
            ok_shape = (
                len(wqs) == 2
                and all(w.source_kind == "deneme" for w in wqs)
                and all(w.exam_result_id == ids["exam1"] for w in wqs)
                and all(w.subject_id is not None and w.topic_id is not None
                        for w in wqs)
                and sum(1 for w in wqs if w.error_type == "dikkat") == 1
            )
        check("4. kayıt şekli doğru + seçilen hata türü atandı (1× dikkat)",
              ok_shape, f"n={len(wqs)}")

        r = ct.get(wr1)
        rows2 = (r.json().get("rows") or []) if r.status_code == 200 else []
        arch = {x["question_no"] for x in rows2 if x["archived"]}
        check("5. arşiv işaretleri güncellendi (yalnız 1 ve 2)",
              arch == {1, 2}, str(arch))

        r = ct.post(url1, json={"items": items})
        d = (r.json().get("data") or {}) if r.status_code == 200 else {}
        check("6. idempotent: aynı seçim mükerrer üretmez (0 yeni · 2 atlandı)",
              r.status_code == 200 and d.get("created") == 0
              and d.get("skipped_existing") == 2, r.text[:200])

        r1b = co.get(wr1)
        r2b = cs.post(url1)
        check("7. yabancı koç 404 + öğrenci koç ucuna 403",
              r1b.status_code == 404 and r2b.status_code == 403,
              f"{r1b.status_code}/{r2b.status_code}")

        r = cs.get(f"/api/v2/student/exams/{ids['exam2']}/wrong-rows")
        n_rows = len((r.json().get("rows") or [])) if r.status_code == 200 else -1
        r = cs.post(f"/api/v2/student/exams/{ids['exam2']}/wrong-to-archive")
        d = (r.json().get("data") or {}) if r.status_code == 200 else {}
        check("8. öğrenci kendi listesi (2) + gövdesiz POST tümünü aktarır (geriye uyum)",
              n_rows == 2 and r.status_code == 200 and d.get("created") == 2
              and "student:wrong-questions" in (r.json().get("invalidate") or []),
              f"rows={n_rows} {r.text[:150]}")

        r = cs.post(f"/api/v2/student/exams/{ids['exam1'] + 999999}/wrong-to-archive")
        check("9. olmayan/yabancı deneme → 404", r.status_code == 404, r.text[:100])

        # --- sinyal köprüleri (servis düzeyi) ---
        from app.services.exam_topic_analysis import (
            exam_insight_summary,
            exam_weak_topic_map,
        )
        with SessionLocal() as db:
            wm = exam_weak_topic_map(db, student_id=ids["student"])
            check("10. öneri sinyali: Rasyonel 4Y → 1.0 · Paragraf 1Y → yok · "
                  "Temel acc≥.6 → yok",
                  wm.get(ids["rasyonel"]) == 1.0
                  and ids["paragraf"] not in wm
                  and ids["temel"] not in wm, str(wm))
            stu = db.get(User, ids["student"])
            es = exam_insight_summary(db, stu)
            top = (es or {}).get("opportunities", [{}])[0]
            check("11. KS4 girdisi: özet üretildi + en büyük fırsat Temel/Rasyonel",
                  es is not None and es.get("exams") == 2
                  and top.get("topic") in ("Temel Kavramlar", "Rasyonel Sayılar"),
                  str(es)[:250])

    finally:
        with SessionLocal() as db:
            uids = [ids["coach"], ids["other"], ids["student"]]
            db.execute(sa_delete(WrongQuestion).where(
                WrongQuestion.student_id.in_(uids)))
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
