"""Dönem-duyarlı görünümler — smoke (P3, 2026-09-04).

KULLANICI İHTİYACI (birebir): "geçen yılın deneme sonuçlarına bir yerden
ulaşılmalı ama ASIL OLAN bu yılın deneme sonuçlarının göz önünde olması."

Yani: geçen yılın verisi SİLİNMEZ, varsayılan görünümden ÇIKAR; dönem
seçicisiyle geri gelir.

Senaryolar:
   1. Koç deneme listesi: varsayılan yalnız BU dönem (geçen yıl görünmez)
   2. ?period=<önceki id> → geçen yılın denemeleri GERİ GELİR (veri duruyor)
   3. ?period=all → tüm geçmiş birlikte
   4. Özet (ortalama/en iyi) döneme göre hesaplanır — geçen yıl karışmaz
   5. period meta: seçenekler + aktif dönem etiketi UI'a gider
   6. Konu performansı: varsayılan bu dönem · ?period=all tüm geçmiş
   7. Öğrenci kendi deneme listesi de dönem-duyarlı
   8. Veli çocuğun denemelerinde de aynı varsayılan
   9. Veli konu performansı dönem-duyarlı
  10. Deneme konu analizi (ısı haritası) dönem-duyarlı
  11. DÖNEM KAYDI YOKSA filtre uygulanmaz — eski davranış birebir korunur
  12. Tek dönemli öğrencide seçici gösterilmez (options boş)
  13. Sahiplik: yabancı öğrenci 404
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    ExamResult,
    ExamSection,
    ParentStudentLink,
    SectionProgress,
    StudentBook,
    StudentGradePeriod,
    Subject,
    SuspiciousIp,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.services.security import hash_password

PFX = f"pv_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []

PREV_START = date(2026, 4, 20)
CUR_START = date(2026, 9, 1)


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Dönem Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Dönem Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Dönem Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=9)
        # dönemi OLMAYAN öğrenci (eski davranış kontrolü)
        plain = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Dönemsiz Öğrenci", role=UserRole.STUDENT,
                     is_active=True, teacher_id=coach.id, grade_level=9)
        foreign = User(email=f"{PFX}_s3@test.invalid", password_hash=hash_password(PWD),
                       full_name="Yabancı", role=UserRole.STUDENT, is_active=True,
                       teacher_id=other.id, grade_level=9)
        parent = User(email=f"{PFX}_p@test.invalid", password_hash=hash_password(PWD),
                      full_name="Dönem Veli", role=UserRole.PARENT, is_active=True)
        opened = datetime(2026, 4, 15, tzinfo=timezone.utc)
        for u in (st, plain, foreign):
            u.created_at = opened
        db.add_all([st, plain, foreign, parent])
        db.flush()
        db.add(ParentStudentLink(parent_id=parent.id, student_id=st.id))

        # --- iki dönem
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_([st.id, plain.id, foreign.id])))
        db.add(StudentGradePeriod(
            student_id=st.id, grade_level=8, is_graduate=False,
            curriculum_model="lgs", started_on=PREV_START,
            ended_on=date(2026, 8, 31)))
        db.add(StudentGradePeriod(
            student_id=st.id, grade_level=9, is_graduate=False,
            curriculum_model="maarif_lise", started_on=CUR_START))

        # --- denemeler: 2 geçen dönem (net 40/50) + 1 bu dönem (net 70)
        db.add(ExamResult(student_id=st.id, title="Gecen Yil Deneme 1",
                          exam_date=date(2026, 5, 5), section=ExamSection.LGS,
                          total_correct=40, total_wrong=0, total_blank=50, net=40.0,
                          created_by_id=coach.id))
        db.add(ExamResult(student_id=st.id, title="Gecen Yil Deneme 2",
                          exam_date=date(2026, 6, 1), section=ExamSection.LGS,
                          total_correct=50, total_wrong=0, total_blank=40, net=50.0,
                          created_by_id=coach.id))
        db.add(ExamResult(student_id=st.id, title="Bu Yil Deneme",
                          exam_date=date(2026, 9, 2), section=ExamSection.LGS,
                          total_correct=70, total_wrong=0, total_blank=20, net=70.0,
                          created_by_id=coach.id))
        # dönemsiz öğrenciye de bir deneme
        db.add(ExamResult(student_id=plain.id, title="Donemsiz Deneme",
                          exam_date=date(2026, 5, 20), section=ExamSection.LGS,
                          total_correct=30, total_wrong=0, total_blank=60, net=30.0,
                          created_by_id=coach.id))

        # --- konu performansı için görevler (geçen dönem 10 test / bu dönem 4)
        subj = Subject(name=f"Dönem Ders {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        topic = Topic(subject_id=subj.id, name=f"Konu {PFX}", order=1)
        db.add(topic)
        db.flush()
        book = Book(name=f"Kitap {PFX}", subject_id=subj.id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label="Bölüm 1", test_count=40, order=1,
                          topic_id=topic.id)
        db.add(sec)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=0, completed_count=14))
        for d, n in ((date(2026, 5, 10), 10), (date(2026, 9, 2), 4)):
            t = Task(student_id=st.id, date=d, type=TaskType.TEST,
                     title=f"Görev {d}", status=TaskStatus.COMPLETED,
                     is_draft=False, completed_at=datetime(
                         d.year, d.month, d.day, tzinfo=timezone.utc))
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=sec.id,
                                planned_count=n, completed_count=n,
                                correct_count=n * 8, wrong_count=n * 2))
        db.commit()
        return {
            "coach_id": coach.id, "other_id": other.id, "student_id": st.id,
            "plain_id": plain.id, "foreign_id": foreign.id, "parent_id": parent.id,
            "subject_id": subj.id, "book_id": book.id,
        }


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["other_id"], s["student_id"], s["plain_id"],
               s["foreign_id"], s["parent_id"]]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_(ids)))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(ids)))
        sbids = [r.id for r in db.query(StudentBook).filter(
            StudentBook.student_id.in_(ids)).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.student_book_id.in_(sbids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == s["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == s["book_id"]))
        db.execute(sa_delete(Topic).where(Topic.subject_id == s["subject_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def titles(body: dict) -> list[str]:
    return [r.get("title", "") for r in body.get("rows", [])]


def main() -> int:
    s = seed()
    sid = s["student_id"]
    print(f"\n=== Dönem-duyarlı görünümler (öğrenci #{sid}) ===\n")
    try:
        from app.services.rate_limit import get_login_limiter

        c = TestClient(app)
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        base = f"/api/v2/teacher/students/{sid}"

        # ---- 1. varsayılan: yalnız bu dönem
        cur = c.get(f"{base}/exams").json()
        cur_titles = titles(cur)
        check("1. koç deneme listesi varsayılan = YALNIZ bu dönem",
              cur_titles == ["Bu Yil Deneme"], f"{cur_titles}")

        meta = cur.get("period") or {}
        opts = meta.get("options", [])
        prev_id = next(
            (o["id"] for o in opts if not o["is_current"]), None)
        check("5. period meta: uygulandı + seçenekler + aktif etiket",
              meta.get("applied") is True and len(opts) == 2
              and prev_id is not None
              and (meta.get("active_label") or "").startswith("9. Sınıf"),
              f"{meta}")

        # ---- 2. önceki dönem → geçen yıl GERİ GELİR
        prev = c.get(f"{base}/exams?period={prev_id}").json()
        prev_titles = sorted(titles(prev))
        check("2. ?period=<önceki> → geçen yılın denemeleri GERİ GELİR",
              prev_titles == ["Gecen Yil Deneme 1", "Gecen Yil Deneme 2"],
              f"{prev_titles}")

        # ---- 3. tüm geçmiş
        allb = c.get(f"{base}/exams?period=all").json()
        check("3. ?period=all → tüm geçmiş birlikte (3 deneme)",
              len(titles(allb)) == 3, f"{titles(allb)}")

        # ---- 4. özet döneme göre
        cs, ps = cur.get("summary", {}), prev.get("summary", {})
        check("4. özet döneme göre hesaplanır (bu dönem ort 70 · geçen 45)",
              cs.get("count") == 1 and cs.get("avg_net") == 70.0
              and ps.get("count") == 2 and ps.get("avg_net") == 45.0,
              f"bu={cs} gecen={ps}")

        # ---- 6. konu performansı
        tp_cur = c.get(f"{base}/topic-performance").json()
        tp_all = c.get(f"{base}/topic-performance?period=all").json()
        check("6. konu performansı: bu dönem 4 test · tüm geçmiş 14 test",
              tp_cur["overall"]["tests_solved"] == 4
              and tp_all["overall"]["tests_solved"] == 14,
              f"cur={tp_cur['overall']['tests_solved']} "
              f"all={tp_all['overall']['tests_solved']}")

        # ---- 10. deneme konu analizi dönem-duyarlı (meta ile doğrula)
        an = c.get(f"{base}/exam-topic-analysis").json()
        check("10. deneme konu analizi dönem-duyarlı (meta uygulandı)",
              (an.get("period") or {}).get("applied") is True,
              f"{an.get('period')}")

        # ---- 11. dönem kaydı YOKSA eski davranış
        pl = c.get(
            f"/api/v2/teacher/students/{s['plain_id']}/exams").json()
        pmeta = pl.get("period") or {}
        check("11. dönem kaydı yoksa filtre UYGULANMAZ (eski davranış)",
              len(titles(pl)) == 1 and pmeta.get("applied") is False,
              f"{titles(pl)} meta={pmeta}")

        # ---- 12. tek dönemli öğrencide seçici gizli
        check("12. tek/dönemsiz öğrencide seçici gösterilmez (options boş)",
              pmeta.get("options") == [], f"{pmeta.get('options')}")

        # ---- 7. öğrenci kendi listesi
        get_login_limiter().reset()
        cst = TestClient(app)
        r = cst.post("/api/v2/auth/login",
                     json={"email": f"{PFX}_s@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        sx = cst.get("/api/v2/student/exams").json()
        sx_all = cst.get("/api/v2/student/exams?period=all").json()
        check("7. öğrenci deneme listesi de dönem-duyarlı (1 vs 3)",
              len(titles(sx)) == 1 and len(titles(sx_all)) == 3,
              f"{titles(sx)} / {len(titles(sx_all))}")

        # ---- 8/9. veli
        get_login_limiter().reset()
        cp = TestClient(app)
        r = cp.post("/api/v2/auth/login",
                    json={"email": f"{PFX}_p@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        px = cp.get(f"/api/v2/parent/students/{sid}/exams").json()
        px_prev = cp.get(
            f"/api/v2/parent/students/{sid}/exams?period={prev_id}").json()
        check("8. veli çocuğun denemelerinde de bu dönem varsayılan",
              titles(px) == ["Bu Yil Deneme"] and len(titles(px_prev)) == 2,
              f"{titles(px)} / {titles(px_prev)}")

        ptp = cp.get(f"/api/v2/parent/students/{sid}/topic-performance").json()
        ptp_all = cp.get(
            f"/api/v2/parent/students/{sid}/topic-performance?period=all").json()
        check("9. veli konu performansı dönem-duyarlı (4 vs 14)",
              ptp["overall"]["tests_solved"] == 4
              and ptp_all["overall"]["tests_solved"] == 14,
              f"{ptp['overall']['tests_solved']} / "
              f"{ptp_all['overall']['tests_solved']}")

        # ---- 13. sahiplik
        r1 = c.get(f"/api/v2/teacher/students/{s['foreign_id']}/exams")
        r2 = cp.get(f"/api/v2/parent/students/{s['foreign_id']}/exams")
        check("13. yabancı öğrenci 404 (koç + veli)",
              r1.status_code == 404 and r2.status_code == 404,
              f"{r1.status_code}/{r2.status_code}")
    finally:
        cleanup(s)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    if failed:
        for f in failed:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
