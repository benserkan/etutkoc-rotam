"""Sınıf geçişi önizlemesi — smoke (P5, 2026-09-05).

KULLANICI SORUSU (birebir): "8'den 9'a geçme ile 9'dan 10'a geçme arasındaki
farkı gözeterek ele al." Fark: 8→9'da müfredat MODELİ değişir (LGS → Maarif);
9→10'da değişmez. Sihirbaz YALNIZ model değiştiğinde gerekir — koçu gereksiz
adımdan geçirmeyiz.

Bu uç YALNIZ ÖNİZLEME üretir; yazma yapmaz (uygulama promote + books/archive
uçlarıyla). Test bunu da doğrular.

Senaryolar:
   1. 8→9: model LGS → Maarif DEĞİŞİR → needs_wizard=True
   2. 9→10: model AYNI (Maarif) → needs_wizard=False (sihirbaz gerekmez)
   3. Dönem sınırı P2 kuralıyla hesaplanır (bugün ≥ 1 Eylül → 1 Eylül)
   4. Geçen döneme yazılacak görev/deneme sayısı doğru
   5. Arşiv adayları = güncel dönem başlamadan atanmış kitaplar
   6. Açıklama notları model değişimini ve veri korunumunu anlatır
   7. ÖNİZLEME HİÇBİR ŞEY DEĞİŞTİRMEZ (profil + dönem + kitap aynı kalır)
   8. 12→mezun: model kohorttan türetilir, sınıf etiketi "Mezun"
   9. Geçersiz sınıf → 422 · yabancı öğrenci → 404 · yabancı akademik yıl → 422
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
    AcademicYear,
    Book,
    BookSection,
    BookType,
    ExamResult,
    ExamSection,
    SectionProgress,
    StudentBook,
    StudentGradePeriod,
    Subject,
    SuspiciousIp,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.security import hash_password

PFX = f"tr_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []

PREV_START = date(2026, 4, 20)
BOUNDARY = date(2026, 9, 1)


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
                     full_name="Geçiş Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Geçiş Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()

        year = AcademicYear(teacher_id=coach.id, name=f"2026-2027 {PFX}",
                            start_year=2026)
        other_year = AcademicYear(teacher_id=other.id, name=f"2026-2027 {PFX}b",
                                  start_year=2026)
        db.add_all([year, other_year])
        db.flush()

        opened = datetime(2026, 4, 15, tzinfo=timezone.utc)
        # Yiğit deseni: 8. sınıf (LGS), geçen öğretim yılında açılmış hesap
        s8 = User(email=f"{PFX}_s8@test.invalid", password_hash=hash_password(PWD),
                  full_name="Sekizinci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=8, academic_year_id=year.id)
        s9 = User(email=f"{PFX}_s9@test.invalid", password_hash=hash_password(PWD),
                  full_name="Dokuzuncu", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=9, academic_year_id=year.id)
        s12 = User(email=f"{PFX}_s12@test.invalid", password_hash=hash_password(PWD),
                   full_name="Onikinci", role=UserRole.STUDENT, is_active=True,
                   teacher_id=coach.id, grade_level=12, academic_year_id=year.id)
        foreign = User(email=f"{PFX}_sf@test.invalid", password_hash=hash_password(PWD),
                       full_name="Yabancı", role=UserRole.STUDENT, is_active=True,
                       teacher_id=other.id, grade_level=8)
        for u in (s8, s9, s12, foreign):
            u.created_at = opened
        db.add_all([s8, s9, s12, foreign])
        db.flush()

        # Dönem: güncel dönem 1 Eylül'de başladı (P2 damgası)
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_([s8.id, s9.id, s12.id])))
        for st, grade, model in ((s8, 8, "lgs"), (s9, 9, "maarif_lise"),
                                 (s12, 12, "maarif_lise")):
            db.add(StudentGradePeriod(
                student_id=st.id, grade_level=grade, is_graduate=False,
                curriculum_model=model, started_on=PREV_START))

        # 8. sınıfın geçen dönem verisi (sınır ÖNCESİ) + kitap
        subj = Subject(name=f"Geçiş Ders {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"LGS Kitabı {PFX}", subject_id=subj.id,
                    teacher_id=coach.id, type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label="Bölüm 1", test_count=30, order=1)
        db.add(sec)
        db.flush()
        sb = StudentBook(student_id=s8.id, book_id=book.id,
                         assigned_at=datetime(2026, 4, 25, tzinfo=timezone.utc))
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=0, completed_count=9))
        for i in range(5):
            db.add(Task(student_id=s8.id, date=date(2026, 5, 4 + i),
                        type=TaskType.TEST, title=f"Geçen yıl {i}",
                        status=TaskStatus.COMPLETED, is_draft=False))
        db.add(ExamResult(student_id=s8.id, title="LGS Deneme",
                          exam_date=date(2026, 5, 9), section=ExamSection.LGS,
                          total_correct=60, total_wrong=15, total_blank=15,
                          net=55.0))
        db.commit()
        return {
            "coach_id": coach.id, "other_id": other.id,
            "s8": s8.id, "s9": s9.id, "s12": s12.id, "foreign": foreign.id,
            "year_id": year.id, "other_year_id": other_year.id,
            "subject_id": subj.id, "book_id": book.id,
        }


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["other_id"], s["s8"], s["s9"], s["s12"],
               s["foreign"]]
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_(ids)))
        sbids = [r.id for r in db.query(StudentBook).filter(
            StudentBook.student_id.in_(ids)).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.student_book_id.in_(sbids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == s["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == s["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(AcademicYear).where(
            AcademicYear.id.in_([s["year_id"], s["other_year_id"]])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def snapshot(sid: int) -> tuple:
    """Önizlemenin hiçbir şeyi değiştirmediğini kanıtlamak için."""
    with SessionLocal() as db:
        u = db.get(User, sid)
        periods = db.query(StudentGradePeriod).filter(
            StudentGradePeriod.student_id == sid).count()
        archived = db.query(StudentBook).filter(
            StudentBook.student_id == sid,
            StudentBook.archived_at.isnot(None)).count()
        return (u.grade_level, bool(u.is_graduate), periods, archived)


def main() -> int:
    s = seed()
    print(f"\n=== Sınıf geçişi önizlemesi (8. sınıf #{s['s8']}) ===\n")
    try:
        c = TestClient(app)
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        before = snapshot(s["s8"])

        # ---- 1. 8→9: model DEĞİŞİR
        r = c.get(f"/api/v2/teacher/students/{s['s8']}/transition-preview"
                  f"?grade=9&academic_year_id={s['year_id']}")
        p89 = r.json() if r.text else {}
        check("1. 8→9 müfredat modeli DEĞİŞİR (LGS → Maarif) → sihirbaz gerekli",
              r.status_code == 200
              and p89.get("current_curriculum") == "lgs"
              and p89.get("target_curriculum") == "maarif_lise"
              and p89.get("model_changes") is True
              and p89.get("needs_wizard") is True,
              f"status={r.status_code} {str(p89)[:220]}")

        # ---- 2. 9→10: model AYNI
        r = c.get(f"/api/v2/teacher/students/{s['s9']}/transition-preview"
                  f"?grade=10&academic_year_id={s['year_id']}")
        p910 = r.json() if r.text else {}
        check("2. 9→10 model AYNI (Maarif) → sihirbaz GEREKMEZ",
              r.status_code == 200
              and p910.get("current_curriculum") == "maarif_lise"
              and p910.get("target_curriculum") == "maarif_lise"
              and p910.get("model_changes") is False
              and p910.get("needs_wizard") is False,
              f"{str(p910)[:200]}")

        # ---- 3. dönem sınırı (P2 kuralı)
        check("3. dönem sınırı P2 kuralıyla hesaplandı (1 Eylül)",
              p89.get("period_boundary") == BOUNDARY.isoformat(),
              f"{p89.get('period_boundary')}")

        # ---- 4. geçen döneme yazılacak veri
        check("4. geçen döneme yazılacak görev/deneme sayısı doğru (5 / 1)",
              p89.get("previous_task_count") == 5
              and p89.get("previous_exam_count") == 1,
              f"gorev={p89.get('previous_task_count')} "
              f"deneme={p89.get('previous_exam_count')}")

        # ---- 5. arşiv adayları
        cands = p89.get("archive_candidates", [])
        check("5. arşiv adayı = geçen dönemde atanmış kitap (1 adet, 9 çözülmüş)",
              len(cands) == 1 and cands[0]["book_id"] == s["book_id"]
              and cands[0]["completed_tests"] == 9,
              f"{cands}")

        # ---- 6. açıklama notları
        notes = " ".join(p89.get("notes", []))
        check("6. notlar model değişimini + veri korunumunu anlatıyor",
              "Müfredat modeli değişiyor" in notes
              and "SİLİNMEZ" in notes and "geçen döneme yazılacak" in notes,
              f"{notes[:200]}")

        # ---- 7. ÖNİZLEME YAZMA YAPMAZ
        after = snapshot(s["s8"])
        check("7. önizleme HİÇBİR ŞEYİ değiştirmedi (profil/dönem/arşiv aynı)",
              before == after, f"önce={before} sonra={after}")

        # ---- 8. 12 → mezun
        r = c.get(f"/api/v2/teacher/students/{s['s12']}/transition-preview"
                  f"?grade=graduate&academic_year_id={s['year_id']}")
        pg = r.json() if r.text else {}
        check("8. 12→mezun: etiket 'Mezun' + model kohorttan türetilir",
              r.status_code == 200
              and pg.get("target_grade_label") == "Mezun"
              and pg.get("target_curriculum") in ("maarif_lise", "klasik_lise"),
              f"{str(pg)[:180]}")

        # ---- 9. kapılar
        r1 = c.get(f"/api/v2/teacher/students/{s['s8']}/transition-preview?grade=abc")
        r2 = c.get(f"/api/v2/teacher/students/{s['foreign']}/transition-preview?grade=9")
        r3 = c.get(f"/api/v2/teacher/students/{s['s8']}/transition-preview"
                   f"?grade=9&academic_year_id={s['other_year_id']}")
        check("9. geçersiz sınıf 422 · yabancı öğrenci 404 · yabancı yıl 422",
              r1.status_code == 422 and r2.status_code == 404
              and r3.status_code == 422,
              f"{r1.status_code}/{r2.status_code}/{r3.status_code}")
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
