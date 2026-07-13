"""Yanlış Soru Arşivi — GERÇEK KULLANIM senaryosu (kullanıcı testi taklidi).

Kullanıcı 14.07'de "kendini dene"ye iki kez bastı ve "hiçbir şey olmadı" dedi.
Kök neden UI'daydı (butonlar ekran dışında kalıyordu) — ama davranışın DOĞRU
olduğunu uçtan uca kanıtlamak için bu senaryo yazıldı:

  Gün 1: yanlış eklenir → HEMEN çözülebilir (due) → öğrenci "Çözdüm" → seri 1/2,
         soru AÇIK kalır, vade ileriye atılır (aynı gün ikinci basış seriyi
         ŞİŞİRMEZ — kapanış aralık ister).
  Gün 2: vade gelir → "Çözdüm" → seri 2/2 → KAPANIR.
  Gün 5: kapalı soruya "Yine yanlış" → YENİDEN AÇILIR (seri sıfırlanır).
  Ayrıca: "Zor çözdüm" seriyi ilerletmez; koç özeti kapanışı sayar.

HTTP üzerinden (öğrenci uçları), zaman ilerlemesi servis katmanında `now` ile.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    StudentBook,
    Subject,
    SuspiciousIp,
    Topic,
    User,
    UserRole,
    WrongQuestion,
    WrongQuestionImage,
)
from app.services import wrong_question_service as svc
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"wql{secrets.token_hex(3)}"
PASSWORD = "Wrong!2026X"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def state(db, wq_id):
    w = db.get(WrongQuestion, wq_id)
    return w.status, w.correct_streak, w.attempts_count


def main() -> int:
    print(f"\n=== yanlış soru YAŞAM DÖNGÜSÜ (gerçek kullanım) — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_free", must_change_password=False)
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True,
                       grade_level=12, must_change_password=False)
        db.add_all([coach, student]); db.flush()
        student.teacher_id = coach.id
        subj = Subject(name=f"{PFX} TYT Matematik", order=999, is_builtin=False,
                       teacher_id=coach.id)
        db.add(subj); db.flush()
        topic = Topic(name="Bölme ve Bölünebilme", order=1, subject_id=subj.id)
        db.add(topic); db.flush()
        book = Book(name=f"{PFX} Bilgi Sarmal", subject_id=subj.id,
                    type=BookType.SORU_BANKASI, teacher_id=coach.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Bölme ve Bölünebilme",
                          test_count=20, order=1, topic_id=topic.id)
        db.add(sec); db.flush()
        db.add(StudentBook(student_id=student.id, book_id=book.id))
        db.commit()
        ids = {"coach": coach.id, "student": student.id, "subj": subj.id,
               "topic": topic.id, "book": book.id, "sec": sec.id}

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    try:
        cs = TestClient(app)
        ct = TestClient(app)
        cs.post("/api/v2/auth/login",
                json={"email": f"{PFX}-s@t.invalid", "password": PASSWORD})
        ct.post("/api/v2/auth/login",
                json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})

        # === GÜN 1: yanlışı fotoğrafla ekle (kitap bölümü bağlamıyla) ===
        r = cs.post("/api/v2/student/wrong-questions",
                    data={"book_section_id": str(ids["sec"]),
                          "error_type": "yorum"},
                    files=[("photos", ("soru.png", PNG, "image/png"))])
        wq = r.json()["data"]
        ids["wq"] = wq["id"]
        check("G1.1 yanlış eklendi + konu otomatik etiketlendi",
              r.status_code == 200 and wq["topic_id"] == ids["topic"]
              and wq["subject_name"].endswith("TYT Matematik"), r.text[:150])
        check("G1.2 yeni kart HEMEN çözülebilir (kullanıcı 'Kendini dene'ye basabilir)",
              wq["is_due"] is True and wq["status"] == "acik" and wq["correct_streak"] == 0,
              f"is_due={wq['is_due']}")

        # Öğrenci "Kendini dene" → Çözdüm
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/attempt",
                    json={"rating": 3})
        d = r.json()["data"]
        check("G1.3 'Çözdüm' → seri 1/2, soru AÇIK, vade ileriye atıldı",
              d["correct_streak"] == 1 and d["status"] == "acik"
              and d["is_due"] is False and d["attempts_count"] == 1,
              f"streak={d['correct_streak']} is_due={d['is_due']}")

        # Kullanıcının yaptığı: hemen İKİNCİ kez bas
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/attempt",
                    json={"rating": 3})
        d = r.json()["data"]
        check("G1.4 AYNI GÜN ikinci 'Çözdüm' seriyi ŞİŞİRMEZ (kapanış aralık ister)",
              d["correct_streak"] == 1 and d["status"] == "acik"
              and d["attempts_count"] == 2,
              f"streak={d['correct_streak']} status={d['status']}")

        # "Zor çözdüm" seriyi ilerletmemeli
        with SessionLocal() as db:
            w = db.get(WrongQuestion, ids["wq"])
            svc.record_attempt(db, w, 2,
                               now=datetime.now(timezone.utc) + timedelta(days=1))
            db.commit()
            st, streak, att = state(db, ids["wq"])
            check("G2.1 'Zor çözdüm' seriyi İLERLETMEZ (açık kalır)",
                  st == "acik" and streak == 1 and att == 3,
                  f"status={st} streak={streak}")

            # === GÜN 2: aralıklı ikinci başarı → KAPANIR ===
            svc.record_attempt(db, w, 3,
                               now=datetime.now(timezone.utc) + timedelta(days=2))
            db.commit()
            st, streak, att = state(db, ids["wq"])
            check("G2.2 aralıklı 2. 'Çözdüm' → soru KAPANDI (seri 2/2)",
                  st == "kapandi" and streak == 2 and w.closed_at is not None,
                  f"status={st} streak={streak}")

        r = cs.get("/api/v2/student/wrong-questions")
        c = r.json()["counts"]
        check("G2.3 sayaçlar: açık 0 · kapanan 1",
              c["open"] == 0 and c["closed"] == 1 and c["due"] == 0, f"counts={c}")

        # Koç panosu kapanışı görüyor mu
        r = ct.get(f"/api/v2/teacher/students/{ids['student']}/wrong-questions/summary")
        s = r.json()
        check("G2.4 koç panosu: 'son 30 günde KAPANAN' = 1",
              s["closed_last_30d"] == 1 and s["counts"]["open"] == 0,
              f"closed30={s['closed_last_30d']}")

        # === GÜN 5: unutma → kapalı soru yeniden açılır ===
        with SessionLocal() as db:
            w = db.get(WrongQuestion, ids["wq"])
            svc.record_attempt(db, w, 1,
                               now=datetime.now(timezone.utc) + timedelta(days=5))
            db.commit()
            st, streak, att = state(db, ids["wq"])
            check("G5.1 kapalı soruya 'Yine yanlış' → YENİDEN AÇILIR + seri sıfır",
                  st == "acik" and streak == 0 and w.closed_at is None,
                  f"status={st} streak={streak}")
            check("G5.2 yeniden açılan soru kısa vadede tekrar sorulur",
                  w.due_at is not None, f"due={w.due_at}")

        r = ct.get(f"/api/v2/teacher/students/{ids['student']}/wrong-questions/summary")
        s = r.json()
        check("G5.3 koç panosu güncel: açık 1 (unutulan soru geri döndü)",
              s["counts"]["open"] == 1 and s["counts"]["closed"] == 0,
              f"counts={s['counts']}")
        check("G5.4 koç 'en çok biriken konu' listesinde konu görünür",
              any(t["topic_id"] == ids["topic"] and t["open_count"] == 1
                  for t in s["by_topic"]), f"by_topic={s['by_topic']}")
    finally:
        with SessionLocal() as db:
            wq_ids = [r[0] for r in db.query(WrongQuestion.id).filter(
                WrongQuestion.student_id == ids["student"]).all()]
            if wq_ids:
                db.execute(sa_delete(WrongQuestionImage).where(
                    WrongQuestionImage.wrong_question_id.in_(wq_ids)))
                db.execute(sa_delete(WrongQuestion).where(WrongQuestion.id.in_(wq_ids)))
            db.execute(sa_delete(StudentBook).where(
                StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.id == ids["sec"]))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.execute(sa_delete(User).where(
                User.id.in_([ids["student"], ids["coach"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
