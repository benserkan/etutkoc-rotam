"""Konu kapatma + kaynaksız (konuya bağlı) görev — smoke (P2, 2026-09-07).

KULLANICI KARARLARI:
  · "Koç öğrenciyle görüşmesinde konu bitti mi sorsun; bittiğinde müfredat
    panelinden işaretlenerek konunun bittiği belirlensin." → müfredat
    tamamlanmasının kaynağı kitabın sayacı DEĞİL koçun kararı.
  · "Koç sıkıştığında test sayısı kısıtına takılmadan devam edebilmeli" →
    kaynaksız görev: kitap yok, rezerv yok, ama KONU bağı var; müfredat
    takibi ve konu performansı kaybolmuyor.

Senaryolar:
   1. Kaynaksız görev oluşur (kitapsız + topic_id) ve rezerv TUTMAZ
   2. Kaynaksız görev DENEME değil TEST sayılır (gorev_stats)
   3. Çözülünce konu performansına GİRER (doğruluk birikir)
   4. Kaynağı olmayan konu artık "kaynak_yok" değil "devam" görünür
   5. Konu kapatma → müfredat panelinde "tamamlandi" + pct 100
   6. Kapatma kitapta test kalsa DA geçerli (koç kararı otoritedir)
   7. Kapatma idempotent (iki kez basmak güvenli)
   8. Yeniden açma → eski duruma döner
   9. Kapatılan konu "sıradaki konu" olarak önerilmez
  9b. Kapatılan konu "Sıradaki üniteler" panelinde de ÖNERİLMEZ
  10. Yabancı konu enjeksiyonu → 422 topic_not_found
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
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    Topic,
    TopicClosure,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.suspicious_ip import SuspiciousIp
from app.services import gorev_stats
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"tclose_{secrets.token_hex(3)}"
PWDH = "TopicClose!234"

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


def _find_topic(payload: dict, topic_id: int) -> dict | None:
    for s in payload.get("subjects", []):
        for t in s.get("topics", []):
            if t.get("topic_id") == topic_id:
                return t
    return None


def main() -> int:
    print(f"\n=== konu kapatma + kaynaksız görev smoke — {PFX} ===\n")
    get_login_limiter().reset()
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            coach = User(
                email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWDH),
                full_name="Konu Koç", role=UserRole.TEACHER, is_active=True,
            )
            other = User(
                email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWDH),
                full_name="Yabancı Koç", role=UserRole.TEACHER, is_active=True,
            )
            db.add_all([coach, other])
            db.flush()
            st = User(
                email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWDH),
                full_name="Konu Öğrenci", role=UserRole.STUDENT, is_active=True,
                teacher_id=coach.id, grade_level=12,
            )
            foreign_st = User(
                email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWDH),
                full_name="Yabancı Öğrenci", role=UserRole.STUDENT, is_active=True,
                teacher_id=other.id, grade_level=12,
            )
            db.add_all([st, foreign_st])
            db.flush()

            # Koçun kendi dersi + 3 konu (müfredat omurgası)
            subj = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
            db.add(subj)
            db.flush()
            t_res = Topic(subject_id=subj.id, name="Türev", order=1, teacher_id=coach.id)
            t_free = Topic(subject_id=subj.id, name="İntegral", order=2, teacher_id=coach.id)
            t_next = Topic(subject_id=subj.id, name="Limit", order=3, teacher_id=coach.id)
            db.add_all([t_res, t_free, t_next])
            db.flush()

            # Yabancı koçun konusu — enjeksiyon denemesi için
            osubj = Subject(name=f"{PFX} Yabancı Ders", teacher_id=other.id, order=1)
            db.add(osubj)
            db.flush()
            t_alien = Topic(subject_id=osubj.id, name="Yabancı Konu", order=1,
                            teacher_id=other.id)
            db.add(t_alien)
            db.flush()

            # Türev + Limit'in kaynağı var, İntegral'in YOK (kaynaksız senaryo)
            book = Book(name=f"{PFX} Soru Bankası", teacher_id=coach.id,
                        subject_id=subj.id, type=BookType.SORU_BANKASI)
            db.add(book)
            db.flush()
            sec_res = BookSection(book_id=book.id, label="Türev", order=1,
                                  test_count=10, topic_id=t_res.id)
            sec_next = BookSection(book_id=book.id, label="Limit", order=2,
                                   test_count=8, topic_id=t_next.id)
            db.add_all([sec_res, sec_next])
            db.flush()
            sb = StudentBook(student_id=st.id, book_id=book.id)
            db.add(sb)
            db.flush()
            ids.update(
                coach=coach.id, other=other.id, student=st.id,
                foreign_student=foreign_st.id, subject=subj.id, osubject=osubj.id,
                book=book.id, t_res=t_res.id, t_free=t_free.id, t_next=t_next.id,
                t_alien=t_alien.id, sec_res=sec_res.id, sec_next=sec_next.id,
            )
            db.commit()

        c = TestClient(app)
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWDH})
        assert r.status_code == 200, r.text
        sid = ids["student"]
        day = (date.today() + timedelta(days=1)).isoformat()

        # ---- 1. Kaynaksız görev: kitapsız + topic_id, rezerv TUTMAZ
        r1 = c.post(
            f"/api/v2/teacher/students/{sid}/tasks",
            json={
                "date": day, "type": "test", "title": "İntegral çalışması",
                "is_draft": False,
                "items": [{
                    "book_id": None, "section_id": None,
                    "topic_id": ids["t_free"], "planned_count": 3,
                }],
            },
        )
        free_task_id = (r1.json().get("data") or {}).get("id") if r1.status_code == 200 else None
        with SessionLocal() as db:
            item = (
                db.query(TaskBookItem)
                .filter(TaskBookItem.task_id == free_task_id)
                .first()
            ) if free_task_id else None
            res_rows = (
                db.query(SectionProgress)
                .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
                .filter(StudentBook.student_id == sid,
                        SectionProgress.reserved_count > 0)
                .count()
            )
        check(
            "1. kaynaksız görev oluştu (topic bağlı) ve REZERV TUTMADI",
            r1.status_code == 200 and item is not None
            and item.topic_id == ids["t_free"] and item.book_id is None
            and res_rows == 0,
            f"{r1.status_code} item={bool(item)} rezervli_bolum={res_rows}",
        )

        # ---- 2. DENEME değil TEST sayılmalı
        with SessionLocal() as db:
            task = db.get(Task, free_task_id) if free_task_id else None
            kind = gorev_stats.classify_gorev(task) if task else "?"
        check("2. kaynaksız konu görevi TEST sayılır (deneme değil)",
              kind == "test", f"kategori={kind}")

        # ---- 3. Çözülünce konu performansına girer
        with SessionLocal() as db:
            it = (db.query(TaskBookItem)
                  .filter(TaskBookItem.task_id == free_task_id).first())
            it.completed_count = 3
            it.correct_count = 24
            it.wrong_count = 6
            db.commit()
        from app.services.topic_performance import compute_topic_performance
        with SessionLocal() as db:
            perf = compute_topic_performance(db, sid)
        found = None
        for s in perf:
            for t in s.topics:
                if t.topic_id == ids["t_free"]:
                    found = t
        check(
            "3. kaynaksız çalışma konu performansına GİRER (%80 doğruluk)",
            found is not None and found.tests_solved == 3
            and found.accuracy_pct == 80,
            f"{found}",
        )

        # ---- 4. Kaynağı olmayan konu artık 'kaynak_yok' değil
        cur = c.get(f"/api/v2/teacher/students/{sid}/curriculum").json()
        row_free = _find_topic(cur, ids["t_free"])
        check(
            "4. kaynaksız çalışılan konu 'kaynak_yok' değil 'devam' görünür",
            row_free is not None and row_free["status"] == "devam"
            and row_free["sourceless_completed"] == 3,
            f"{row_free}",
        )

        # ---- 5-6. Konu kapatma: kitapta 10 test DURUYOR ama koç kapatıyor
        r5 = c.post(f"/api/v2/teacher/students/{sid}/topics/{ids['t_res']}/close",
                    json={"note": "Görüşmede bitti dedi"})
        cur = c.get(f"/api/v2/teacher/students/{sid}/curriculum").json()
        row_res = _find_topic(cur, ids["t_res"])
        check(
            "5. kapatma → müfredatta 'tamamlandi' + pct 100",
            r5.status_code == 200 and row_res is not None
            and row_res["status"] == "tamamlandi" and row_res["pct"] == 100
            and row_res["closed"] is True and row_res["closed_at"],
            f"{r5.status_code} {row_res}",
        )
        check(
            "6. kitapta 10 test kalsa DA kapalı sayılır (koç kararı otoritedir)",
            row_res is not None and row_res["test_total"] == 10
            and row_res["completed"] == 0 and row_res["status"] == "tamamlandi",
            f"{row_res}",
        )

        # ---- 7. İdempotent
        r7 = c.post(f"/api/v2/teacher/students/{sid}/topics/{ids['t_res']}/close",
                    json={})
        with SessionLocal() as db:
            n = (db.query(TopicClosure)
                 .filter(TopicClosure.student_id == sid,
                         TopicClosure.topic_id == ids["t_res"]).count())
        check("7. kapatma idempotent (iki kez basmak tek kayıt)",
              r7.status_code == 200 and n == 1, f"{r7.status_code} kayit={n}")

        # ---- 9. Kapatılan konu 'sıradaki' olarak önerilmez
        #        (Türev kapalı, İntegral kaynaksız çalışılmış → sıradaki Limit)
        subj_row = next(
            (s for s in cur.get("subjects", []) if s.get("subject_id") == ids["subject"]),
            None,
        )
        check(
            "9. kapatılan konu 'sıradaki' olarak önerilmez (sıradaki: Limit)",
            subj_row is not None and subj_row.get("next_topic_name") == "Limit",
            f"sıradaki={subj_row.get('next_topic_name') if subj_row else None}",
        )

        # ---- 9b. Kapatma her iki yüzeyde de geçerli olmalı: "Sıradaki üniteler"
        #          paneli de kapatılan konuyu önermemeli (tek karar, tek gerçek)
        nu = c.get(f"/api/v2/teacher/students/{sid}/next-units")
        nu_topics = [
            u.get("topic_id") for u in (nu.json().get("units") or [])
        ] if nu.status_code == 200 else []
        check(
            "9b. kapatılan konu 'Sıradaki üniteler'de de önerilmez",
            nu.status_code == 200 and ids["t_res"] not in nu_topics
            and ids["t_next"] in nu_topics,
            f"{nu.status_code} onerilen={nu_topics}",
        )

        # ---- 8. Yeniden açma → eski duruma döner
        r8 = c.post(f"/api/v2/teacher/students/{sid}/topics/{ids['t_res']}/reopen")
        cur2 = c.get(f"/api/v2/teacher/students/{sid}/curriculum").json()
        row_res2 = _find_topic(cur2, ids["t_res"])
        check(
            "8. yeniden açma → 'baslanmadi'ya döner, closed False",
            r8.status_code == 200 and row_res2 is not None
            and row_res2["closed"] is False and row_res2["status"] == "baslanmadi",
            f"{r8.status_code} {row_res2}",
        )

        # ---- 10. Yabancı konu enjeksiyonu
        r10a = c.post(
            f"/api/v2/teacher/students/{sid}/tasks",
            json={
                "date": day, "type": "test", "title": "Enjeksiyon",
                "is_draft": False,
                "items": [{
                    "book_id": None, "section_id": None,
                    "topic_id": ids["t_alien"], "planned_count": 2,
                }],
            },
        )
        r10b = c.post(
            f"/api/v2/teacher/students/{sid}/topics/{ids['t_alien']}/close", json={},
        )
        check(
            "10. yabancı koçun konusu → 422 topic_not_found (görevde ve kapatmada)",
            r10a.status_code == 422 and r10b.status_code == 422,
            f"{r10a.status_code}/{r10b.status_code}",
        )

        # ---- 11. Sahiplik
        r11 = c.post(
            f"/api/v2/teacher/students/{ids['foreign_student']}"
            f"/topics/{ids['t_res']}/close", json={},
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
                db.execute(
                    sa_delete(TopicClosure).where(TopicClosure.student_id.in_(uid))
                )
                tids = [
                    r[0] for r in db.query(Task.id)
                    .filter(Task.student_id.in_(uid)).all()
                ]
                if tids:
                    db.execute(
                        sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids))
                    )
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            if ids.get("book"):
                sbids = [
                    r[0] for r in db.query(StudentBook.id)
                    .filter(StudentBook.book_id == ids["book"]).all()
                ]
                if sbids:
                    db.execute(
                        sa_delete(SectionProgress)
                        .where(SectionProgress.student_book_id.in_(sbids))
                    )
                    db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids)))
                db.execute(
                    sa_delete(BookSection).where(BookSection.book_id == ids["book"])
                )
                db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            for key in ("subject", "osubject"):
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
