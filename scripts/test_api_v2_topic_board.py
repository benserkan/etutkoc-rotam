"""Müfredat paneli — smoke (P5, 2026-09-07).

KOÇ İHTİYACI: "hangi konuları gördük · ne kadar çözüldü · testi kaldı mı ·
ek görev mi vereyim yoksa konuyu kapatayım mı."

Kapatma ipucu KARAR DEĞİL: sistem dört sinyali birleştirir (çözülen test +
doğruluk + denemede durum + açık yanlış), koç karar verir.

Senaryolar:
   1. Konular müfredat sırasında gelir
   2. Performans konu kartında (çözülen test + D/Y + doğruluk)
   3. Kalan kapasite kartta
   4. TEMİZ konu → readiness="ready" (kapatmaya hazır)
   5. EMİR VAKASI: görevde yüksek doğruluk AMA denemede yanlış → "caution"
      (kapatmadan önce bak) — tek başına hiçbir sayı bunu söyleyemez
   6. Arşivde açık yanlış varsa da "caution"
   7. Az veriyle "ready" DENMEZ (2 testte %100 güvenilmez)
   8. D/Y girilmemişse doğruluk UYDURULMAZ (accuracy_pct None)
   9. Kapatılan konu closed=True + closed_at
  10. subject_id filtresi
  12. müfredata bağlı olmayan bölüm `unmapped_sections`te listelenir (sayıma girmez)
  13. kaynağı biten konu 'tamamlandi' (sekmeyle aynı sözlük)
  14. sınıf filtresi: 10. sınıf öğrencisi 11. sınıf konusunu GÖRMEZ, 12. sınıf görür
  11. Sahiplik: başka koçun öğrencisi → 404
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    ExamResult,
    ExamSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskType,
    Topic,
    TopicClosure,
    User,
    UserRole,
    WrongQuestion,
)
from app.models.book import BookType
from app.models.exam_result import ExamResultQuestion
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"board_{secrets.token_hex(3)}"
PWDH = "Board!234567"

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


def _topic(payload: dict, topic_id: int) -> dict | None:
    for s in payload.get("subjects", []):
        for t in s.get("topics", []):
            if t.get("topic_id") == topic_id:
                return t
    return None


def main() -> int:
    print(f"\n=== müfredat paneli smoke — {PFX} ===\n")
    get_login_limiter().reset()
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWDH),
                         full_name="Panel Koç", role=UserRole.TEACHER, is_active=True)
            other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWDH),
                         full_name="Diğer Koç", role=UserRole.TEACHER, is_active=True)
            db.add_all([coach, other])
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWDH),
                      full_name="Panel Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            foreign_st = User(email=f"{PFX}_s2@test.invalid",
                              password_hash=hash_password(PWDH),
                              full_name="Yabancı", role=UserRole.STUDENT,
                              is_active=True, teacher_id=other.id, grade_level=12)
            db.add_all([st, foreign_st])
            db.flush()

            subj = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
            other_subj = Subject(name=f"{PFX} Fizik", teacher_id=coach.id, order=2)
            db.add_all([subj, other_subj])
            db.flush()
            # 1 temiz · 2 denemede yanlış (Emir vakası) · 3 açık yanlış ·
            # 4 az veri · 5 D/Y girilmemiş · 6 kapatılmış
            t_clean = Topic(subject_id=subj.id, name="Temiz Konu", order=1,
                            teacher_id=coach.id)
            t_exam = Topic(subject_id=subj.id, name="Denemede Yanlış", order=2,
                           teacher_id=coach.id)
            t_arch = Topic(subject_id=subj.id, name="Açık Yanlışlı", order=3,
                           teacher_id=coach.id)
            t_thin = Topic(subject_id=subj.id, name="Az Veri", order=4,
                           teacher_id=coach.id)
            t_nodv = Topic(subject_id=subj.id, name="DY Girilmemiş", order=5,
                           teacher_id=coach.id)
            t_closed = Topic(subject_id=subj.id, name="Kapatılmış", order=6,
                             teacher_id=coach.id)
            t_fizik = Topic(subject_id=other_subj.id, name="Fizik Konusu",
                            order=1, teacher_id=coach.id)
            t_done = Topic(subject_id=subj.id, name="Bitmiş Konu", order=7,
                           teacher_id=coach.id)
            t_hi = Topic(subject_id=subj.id, name="Onbir Konusu", order=8,
                         teacher_id=coach.id, grade_level=11)
            # ÇOK KAYNAKLI konu (koç 2026-09-09): aynı konuya bağlı 3 bölüm —
            # "+3 test" hangisine yazacak? Bkz. senaryo 15.
            t_multi = Topic(subject_id=subj.id, name="Çok Kaynaklı Konu", order=9,
                            teacher_id=coach.id)
            db.add_all([t_clean, t_exam, t_arch, t_thin, t_nodv, t_closed, t_fizik,
                        t_done, t_hi, t_multi])
            db.flush()
            st10 = User(email=f"{PFX}_s10@test.invalid", password_hash=hash_password(PWDH),
                        full_name="Onuncu", role=UserRole.STUDENT, is_active=True,
                        teacher_id=coach.id, grade_level=10)
            db.add(st10)
            db.flush()

            book = Book(name=f"{PFX} SB", teacher_id=coach.id,
                        subject_id=subj.id, type=BookType.SORU_BANKASI)
            db.add(book)
            db.flush()
            secs = {}
            for key, topic, total, done in (
                ("clean", t_clean, 12, 6),
                ("exam", t_exam, 12, 6),
                ("arch", t_arch, 12, 6),
                ("thin", t_thin, 10, 2),
                ("nodv", t_nodv, 10, 4),
                ("closed", t_closed, 8, 0),
                ("done", t_done, 4, 4),
            ):
                sec = BookSection(book_id=book.id, label=f"{topic.name} Bölümü",
                                  order=len(secs) + 1, test_count=total,
                                  topic_id=topic.id)
                db.add(sec)
                db.flush()
                secs[key] = (sec, done)
            # Müfredata BAĞLI OLMAYAN bölüm (topic_id NULL) — sayıma girmez, listelenir
            un_sec = BookSection(book_id=book.id, label="Karma Tekrar Testi",
                                 order=99, test_count=5, topic_id=None)
            db.add(un_sec)
            db.flush()
            sb = StudentBook(student_id=st.id, book_id=book.id)
            db.add(sb)
            db.flush()
            for key, (sec, done) in secs.items():
                db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                                       reserved_count=0, completed_count=done))
            db.flush()

            # --- ÇOK KAYNAKLI konu: aynı Topic'e bağlı ÜÇ bölüm, üç ayrı kitap.
            #   A "Devam"  : 12 test, 6 çözülmüş → kalan 6   (BAŞLANMIŞ)
            #   B "Yeni"   : 20 test, 0 çözülmüş → kalan 20  (kalanı EN ÇOK)
            #   C "Biten"  :  5 test, 5 çözülmüş → kalan 0   (DOLU)
            # Eski sıra (full, -remaining) B'yi seçiyordu = hiç açılmamış kitap.
            multi_books: dict[str, int] = {}
            for tag, total, done in (("A", 12, 6), ("B", 20, 0), ("C", 5, 5)):
                b = Book(name=f"{PFX} Kaynak {tag}", teacher_id=coach.id,
                         subject_id=subj.id, type=BookType.SORU_BANKASI)
                db.add(b)
                db.flush()
                sec = BookSection(book_id=b.id, label=f"Çok Kaynaklı Bölüm {tag}",
                                  order=1, test_count=total, topic_id=t_multi.id)
                db.add(sec)
                db.flush()
                sbx = StudentBook(student_id=st.id, book_id=b.id)
                db.add(sbx)
                db.flush()
                db.add(SectionProgress(student_book_id=sbx.id,
                                       book_section_id=sec.id,
                                       reserved_count=0, completed_count=done))
                db.flush()
                multi_books[tag] = b.id

            # Performans görevleri
            def solve(sec, tests, correct, wrong, day_off=5):
                t = Task(student_id=st.id, date=date.today() - timedelta(days=day_off),
                         type=TaskType.TEST, title="x", is_draft=False)
                db.add(t)
                db.flush()
                db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                    book_section_id=sec.id, planned_count=tests,
                                    completed_count=tests, correct_count=correct,
                                    wrong_count=wrong))
                db.flush()

            solve(secs["clean"][0], 6, 55, 5)     # %92 → ready
            solve(secs["exam"][0], 6, 58, 2)      # %97 AMA denemede yanlış
            solve(secs["arch"][0], 6, 55, 5)      # %92 AMA arşivde açık yanlış
            solve(secs["thin"][0], 2, 20, 0)      # %100 ama az veri
            solve(secs["nodv"][0], 4, 0, 0)       # D/Y girilmemiş
            solve(secs["done"][0], 4, 36, 4)      # kaynak bitti → tamamlandi

            # EMİR VAKASI: görevde iyi ama denemede yanlış
            ex = ExamResult(student_id=st.id, title="Deneme", exam_date=date.today(),
                            section=ExamSection.TYT, total_correct=50,
                            total_wrong=10, total_blank=0, net=47.5,
                            created_by_id=coach.id)
            db.add(ex)
            db.flush()
            for _ in range(2):
                db.add(ExamResultQuestion(exam_result_id=ex.id,
                                          topic_id=t_exam.id, result="yanlis"))
            # Açık yanlış arşivi
            for _ in range(2):
                db.add(WrongQuestion(student_id=st.id, topic_id=t_arch.id,
                                     source_kind="diger", status="acik"))
            db.add(TopicClosure(student_id=st.id, topic_id=t_closed.id,
                                closed_by_id=coach.id))
            ids.update(coach=coach.id, other=other.id, student=st.id,
                       foreign_student=foreign_st.id, subject=subj.id,
                       other_subject=other_subj.id, book=book.id, exam=ex.id,
                       t_clean=t_clean.id, t_exam=t_exam.id, t_arch=t_arch.id,
                       t_thin=t_thin.id, t_nodv=t_nodv.id, t_closed=t_closed.id,
                       t_fizik=t_fizik.id, t_done=t_done.id, t_hi=t_hi.id,
                       student10=st10.id, un_sec=un_sec.id,
                       t_multi=t_multi.id, book_a=multi_books["A"],
                       book_b=multi_books["B"], book_c=multi_books["C"])
            db.commit()

        c = TestClient(app)
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWDH})
        assert r.status_code == 200, r.text
        sid = ids["student"]

        res = c.get(f"/api/v2/teacher/students/{sid}/topic-board",
                    params={"subject_id": ids["subject"]})
        payload = res.json() if res.status_code == 200 else {}
        subj_row = next(
            (s for s in payload.get("subjects", [])
             if s["subject_id"] == ids["subject"]), None,
        )

        # ---- 1. Müfredat sırası
        names = [t["name"] for t in (subj_row or {}).get("topics", [])]
        check(
            "1. konular müfredat sırasında gelir",
            res.status_code == 200 and names[:3] ==
            ["Temiz Konu", "Denemede Yanlış", "Açık Yanlışlı"],
            f"{res.status_code} {names}",
        )

        clean = _topic(payload, ids["t_clean"])
        # ---- 2. Performans kartta
        check(
            "2. çözülen test + D/Y + doğruluk kartta",
            clean is not None and clean["tests_solved"] == 6
            and clean["correct"] == 55 and clean["wrong"] == 5
            and clean["accuracy_pct"] == 92,
            f"{clean}",
        )

        # ---- 3. Kalan kapasite
        check("3. kalan kapasite kartta (12 - 6 = 6)",
              clean is not None and clean["remaining"] == 6, f"{clean}")

        # ---- 4. Temiz konu → ready
        check(
            "4. temiz konu → 'kapatmaya hazır' ipucu",
            clean is not None and clean["readiness"] == "ready"
            and "kapatmaya hazır" in clean["readiness_note"],
            f"{clean.get('readiness') if clean else None} / "
            f"{clean.get('readiness_note') if clean else None}",
        )

        # ---- 5. EMİR VAKASI
        exam_t = _topic(payload, ids["t_exam"])
        check(
            "5. görevde %97 AMA denemede yanlış → 'caution' (Emir vakası)",
            exam_t is not None and exam_t["accuracy_pct"] == 97
            and exam_t["exam_wrong"] == 2 and exam_t["readiness"] == "caution"
            and "kapatmadan önce bak" in exam_t["readiness_note"],
            f"{exam_t}",
        )

        # ---- 6. Açık yanlış
        arch = _topic(payload, ids["t_arch"])
        check(
            "6. arşivde açık yanlış varsa 'caution'",
            arch is not None and arch["open_wrongs"] == 2
            and arch["readiness"] == "caution",
            f"{arch}",
        )

        # ---- 7. Az veri
        thin = _topic(payload, ids["t_thin"])
        check(
            "7. az veriyle 'hazır' DENMEZ (2 testte %100 güvenilmez)",
            thin is not None and thin["accuracy_pct"] == 100
            and thin["readiness"] == "none" and "veri az" in thin["readiness_note"],
            f"{thin}",
        )

        # ---- 8. D/Y yoksa doğruluk uydurulmaz
        nodv = _topic(payload, ids["t_nodv"])
        check(
            "8. D/Y girilmemişse doğruluk UYDURULMAZ (None)",
            nodv is not None and nodv["accuracy_pct"] is None
            and nodv["tests_solved"] == 4,
            f"{nodv}",
        )

        # ---- 9. Kapatılan konu
        closed = _topic(payload, ids["t_closed"])
        check(
            "9. kapatılan konu closed=True + tarih + status 'kapali'",
            closed is not None and closed["closed"] is True
            and bool(closed["closed_at"]) and closed["status"] == "kapali",
            f"{closed}",
        )

        # ---- 10. subject_id filtresi
        check(
            "10. subject_id filtresi çalışır (Fizik gelmedi)",
            _topic(payload, ids["t_fizik"]) is None
            and len(payload.get("subjects", [])) == 1,
            f"ders={len(payload.get('subjects', []))}",
        )

        # ---- 12. eşleşmemiş bölüm listelenir, sayıma girmez
        un = (subj_row or {}).get("unmapped_sections", [])
        check(
            "12. müfredata bağlı olmayan bölüm unmapped_sections'ta (kitap adıyla), sayımda değil",
            len(un) == 1 and un[0]["label"] == "Karma Tekrar Testi"
            and un[0]["test_count"] == 5 and un[0]["book_id"] == ids["book"]
            and _topic(payload, ids["un_sec"]) is None,
            str(un),
        )

        # ---- 13. kaynağı biten konu tamamlandi
        t13 = _topic(payload, ids["t_done"]) or {}
        check("13. kaynağı biten konu status='tamamlandi' (sekmeyle aynı)",
              t13.get("status") == "tamamlandi" and t13.get("remaining") == 0,
              str({k: t13.get(k) for k in ("status", "remaining", "tests_solved")}))

        # ---- 14. sınıf filtresi (tek merkez leaf_topics_for_student)
        r14 = c.get(f"/api/v2/teacher/students/{ids['student10']}/topic-board",
                    params={"subject_id": ids["subject"]})
        p14 = r14.json() if r14.status_code == 200 else {}
        check("14. 10. sınıf öğrencisi 11. sınıf konusunu GÖRMEZ; 12. sınıf görür",
              r14.status_code == 200 and _topic(p14, ids["t_hi"]) is None
              and _topic(payload, ids["t_hi"]) is not None,
              f"{r14.status_code} st10={_topic(p14, ids['t_hi'])} st12={bool(_topic(payload, ids['t_hi']))}")

        # ---- 15. ÇOK KAYNAKLI konu: "+3 test" hangi kitaba yazacak?
        #      Koç (2026-09-09): iki kaynak varken panel sessizce seçiyordu ve
        #      sıra "kalanı en çok" olduğu için HİÇ AÇILMAMIŞ kitap kazanıyordu.
        #      Kural artık: kapasitesi olan + BAŞLANMIŞ kaynak önerilir.
        multi = _topic(payload, ids["t_multi"]) or {}
        msrc = multi.get("sources", [])
        check(
            "15a. çok kaynaklı konuda ÖNERİLEN = başlanmış kaynak "
            "(kalanı en çok olan değil)",
            len(msrc) == 3
            and msrc[0]["book_id"] == ids["book_a"]
            and msrc[0]["recommended"] is True
            and msrc[0]["completed"] == 6,
            str([(s["book_id"], s["completed"], s["remaining"], s["full"],
                  s["recommended"]) for s in msrc]),
        )
        check(
            "15b. dolu kaynak listenin SONUNDA (kapasitesi olan önce)",
            len(msrc) == 3
            and msrc[1]["book_id"] == ids["book_b"]
            and msrc[2]["book_id"] == ids["book_c"]
            and msrc[2]["full"] is True,
            str([(s["book_id"], s["full"]) for s in msrc]),
        )
        check(
            "15c. yalnız TEK kaynak 'recommended' işaretli",
            sum(1 for s in msrc if s["recommended"]) == 1,
            str([s["recommended"] for s in msrc]),
        )
        check(
            "15d. her kaynak kendi adı/bölümü/sayacıyla döner (koç seçebilsin)",
            all(
                s.get("book_name") and s.get("section_label")
                and "completed" in s and "remaining" in s
                for s in msrc
            ),
            str(msrc[:1]),
        )

        # ---- 11. Sahiplik
        r11 = c.get(
            f"/api/v2/teacher/students/{ids['foreign_student']}/topic-board"
        )
        check("11. başka koçun öğrencisi → 404", r11.status_code == 404,
              f"{r11.status_code}")

    finally:
        with SessionLocal() as db:
            uid = [
                v for k, v in ids.items()
                if k in ("coach", "other", "student", "foreign_student")
            ]
            if uid:
                db.execute(sa_delete(WrongQuestion)
                           .where(WrongQuestion.student_id.in_(uid)))
                db.execute(sa_delete(TopicClosure)
                           .where(TopicClosure.student_id.in_(uid)))
                exids = [r[0] for r in db.query(ExamResult.id)
                         .filter(ExamResult.student_id.in_(uid)).all()]
                if exids:
                    db.execute(sa_delete(ExamResultQuestion)
                               .where(ExamResultQuestion.exam_result_id.in_(exids)))
                    db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exids)))
                tids = [r[0] for r in db.query(Task.id)
                        .filter(Task.student_id.in_(uid)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem)
                               .where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            bids = [ids[k] for k in ("book", "book_a", "book_b", "book_c")
                    if ids.get(k)]
            if bids:
                sbids = [r[0] for r in db.query(StudentBook.id)
                         .filter(StudentBook.book_id.in_(bids)).all()]
                if sbids:
                    db.execute(sa_delete(SectionProgress)
                               .where(SectionProgress.student_book_id.in_(sbids)))
                    db.execute(sa_delete(StudentBook)
                               .where(StudentBook.id.in_(sbids)))
                db.execute(sa_delete(BookSection)
                           .where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
            for key in ("subject", "other_subject"):
                if ids.get(key):
                    db.execute(sa_delete(Topic).where(Topic.subject_id == ids[key]))
                    db.execute(sa_delete(Subject).where(Subject.id == ids[key]))
            if uid:
                db.execute(sa_delete(User).where(User.id.in_(uid)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
