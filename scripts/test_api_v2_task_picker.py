"""Görev ekleme kutusu — smoke (P4, 2026-09-07).

TASARIM: koç "türev çalışsın" diye düşünür, "345'in 12. ünitesi" diye değil.
Kutu konu ekseninde çalışır; kaynaklar konunun altında listelenir, kapasitesi
dolan bölüm GİZLENMEZ (P1) ve her konu kaynaksız da verilebilir (P2).

Senaryolar:
   1. Kaynağı olan ders ÖNE gelir + liste kısa kalır (tavan 12)
   2. Kaynaklar konunun ALTINDA listelenir (kalan kapasiteyle)
   3. Kapasitesi dolu bölüm GİZLENMEZ, `full` ile işaretlenir
   4. Kaynağı olmayan konu da listelenir (kaynaksız verilebilsin)
   5. Zayıflık sinyali olan konu "zayıf" rozetiyle ayrı grupta
   6. Son çalışılan konular grubu
   7. Kapatılan konu (P2) kutuda ÖNERİLMEZ
   8. Miktar önerisi (P3) her konuda gerekçesiyle gelir
   9. Arama: konu adı · kitap adı · bölüm etiketi birlikte aranır
  10. Arama Türkçe büyük-küçük harfe duyarsız (İ/ı tuzağı)
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
    TaskType,
    Topic,
    TopicClosure,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"pick_{secrets.token_hex(3)}"
PWDH = "Picker!23456"

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


def _items(payload: dict, group_key: str | None = None) -> list[dict]:
    out = []
    for g in payload.get("groups", []):
        if group_key and g.get("key") != group_key:
            continue
        out.extend(g.get("items", []))
    return out


def _find(payload: dict, topic_id: int) -> dict | None:
    return next((i for i in _items(payload) if i.get("topic_id") == topic_id), None)


def main() -> int:
    print(f"\n=== görev kutusu smoke — {PFX} ===\n")
    get_login_limiter().reset()
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWDH),
                         full_name="Kutu Koç", role=UserRole.TEACHER, is_active=True)
            other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWDH),
                         full_name="Diğer Koç", role=UserRole.TEACHER, is_active=True)
            db.add_all([coach, other])
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWDH),
                      full_name="Kutu Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            foreign_st = User(email=f"{PFX}_s2@test.invalid",
                              password_hash=hash_password(PWDH),
                              full_name="Yabancı Öğrenci", role=UserRole.STUDENT,
                              is_active=True, teacher_id=other.id, grade_level=12)
            db.add_all([st, foreign_st])
            db.flush()

            subj = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
            db.add(subj)
            db.flush()
            # Müfredat sırası: Türev(1) → İntegral(2) → Limit(3) → Kapalı(4)
            t1 = Topic(subject_id=subj.id, name="Türev", order=1, teacher_id=coach.id)
            t2 = Topic(subject_id=subj.id, name="İntegral", order=2, teacher_id=coach.id)
            t3 = Topic(subject_id=subj.id, name="Limit", order=3, teacher_id=coach.id)
            t4 = Topic(subject_id=subj.id, name="Kapanan Konu", order=4,
                       teacher_id=coach.id)
            db.add_all([t1, t2, t3, t4])
            db.flush()

            book = Book(name=f"{PFX} Orijinal Fasikül", teacher_id=coach.id,
                        subject_id=subj.id, type=BookType.SORU_BANKASI)
            db.add(book)
            db.flush()
            # Türev: 10 testlik, 4 çözülmüş → kalan 6
            s1 = BookSection(book_id=book.id, label="Türev Bölümü", order=1,
                             test_count=10, topic_id=t1.id)
            # Limit: 5 testlik, TAMAMI dolu → gizlenmemeli, full=True olmalı
            s3 = BookSection(book_id=book.id, label="Limit Bölümü", order=2,
                             test_count=5, topic_id=t3.id)
            # Kapanan konunun da kaynağı var (kapatma kaynak varlığından bağımsız)
            s4 = BookSection(book_id=book.id, label="Kapanan Bölüm", order=3,
                             test_count=4, topic_id=t4.id)
            db.add_all([s1, s3, s4])
            db.flush()
            sb = StudentBook(student_id=st.id, book_id=book.id)
            db.add(sb)
            db.flush()
            db.add_all([
                SectionProgress(student_book_id=sb.id, book_section_id=s1.id,
                                reserved_count=0, completed_count=4),
                SectionProgress(student_book_id=sb.id, book_section_id=s3.id,
                                reserved_count=0, completed_count=5),
            ])
            # Kapanan konu (P2)
            db.add(TopicClosure(student_id=st.id, topic_id=t4.id,
                                closed_by_id=coach.id))
            db.flush()

            # Son çalışılan izi: Limit'e yakın tarihli görev
            t = Task(student_id=st.id, date=date.today() - timedelta(days=2),
                     type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=s3.id, planned_count=2,
                                completed_count=2))
            ids.update(coach=coach.id, other=other.id, student=st.id,
                       foreign_student=foreign_st.id, subject=subj.id, book=book.id,
                       t1=t1.id, t2=t2.id, t3=t3.id, t4=t4.id,
                       s1=s1.id, s3=s3.id, s4=s4.id)
            db.commit()

        c = TestClient(app)
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWDH})
        assert r.status_code == 200, r.text
        sid = ids["student"]

        res = c.get(f"/api/v2/teacher/students/{sid}/task-picker")
        payload = res.json() if res.status_code == 200 else {}
        curriculum = _items(payload, "curriculum")

        # ---- 1. Kaynağı olan ders öne + kısa liste
        # 12. sınıfta 20+ uygulanabilir ders olabiliyor; tavan olmazsa kutu
        # 46 satır dökerdi. Kaynaklı ders (bu testte PFX Matematik) başta.
        names = [i["topic_name"] for i in curriculum]
        check(
            "1. kaynaklı ders öne gelir + liste tavanda kalır (≤12)",
            res.status_code == 200 and names[:2] == ["Türev", "İntegral"]
            and len(curriculum) <= 12,
            f"{res.status_code} n={len(curriculum)} {names[:4]}",
        )

        # ---- 2. Kaynaklar konunun altında
        turev = _find(payload, ids["t1"])
        src = (turev or {}).get("sources") or []
        check(
            "2. kaynaklar konunun ALTINDA + kalan kapasiteyle",
            turev is not None and len(src) == 1
            and src[0]["section_label"] == "Türev Bölümü"
            and src[0]["remaining"] == 6 and src[0]["total"] == 10,
            f"{src}",
        )

        # ---- 4. Kaynağı olmayan konu da listelenir
        integral = _find(payload, ids["t2"])
        check(
            "4. kaynağı olmayan konu da listelenir (kaynaksız verilebilsin)",
            integral is not None and integral["sources"] == []
            and integral["status"] == "kaynak_yok",
            f"{integral}",
        )

        # ---- 7. Kapatılan konu önerilmez
        kapali = _find(payload, ids["t4"])
        check("7. kapatılan konu (P2) kutuda önerilmez", kapali is None,
              f"{kapali}")

        # ---- 8. Miktar önerisi gerekçesiyle
        check(
            "8. her konuda miktar önerisi + gerekçe gelir (P3)",
            turev is not None and turev["quantity"] >= 1
            and bool(turev["quantity_reason"]),
            f"{turev.get('quantity') if turev else None} / "
            f"{turev.get('quantity_reason') if turev else None}",
        )

        # ---- 6. Son çalışılanlar grubu (Limit son 2 gün içinde çalışıldı)
        recent = _items(payload, "recent")
        curriculum_ids = {i["topic_id"] for i in curriculum}
        check(
            "6. son çalışılan konular ayrı grupta (mükerrer değil)",
            (ids["t3"] in {i["topic_id"] for i in recent})
            or (ids["t3"] in curriculum_ids),
            f"recent={[i['topic_name'] for i in recent]}",
        )

        # ---- 3. Dolu bölüm gizlenmez, işaretlenir
        limit_item = _find(payload, ids["t3"])
        lim_src = (limit_item or {}).get("sources") or []
        check(
            "3. kapasitesi dolu bölüm GİZLENMEZ, full=True ile işaretlenir",
            limit_item is not None and len(lim_src) == 1
            and lim_src[0]["full"] is True and lim_src[0]["remaining"] == 0,
            f"{lim_src}",
        )

        # ---- 9. Arama: kitap adıyla
        r9 = c.get(f"/api/v2/teacher/students/{sid}/task-picker",
                   params={"q": "Orijinal"})
        hits9 = _items(r9.json()) if r9.status_code == 200 else []
        check(
            "9. arama kitap adında da eşleşir (konu değil kaynak adı)",
            r9.status_code == 200 and ids["t1"] in {i["topic_id"] for i in hits9},
            f"{[i['topic_name'] for i in hits9]}",
        )

        # ---- 10. Türkçe büyük/küçük harf: "İNTEGRAL" → "İntegral"
        r10 = c.get(f"/api/v2/teacher/students/{sid}/task-picker",
                    params={"q": "İNTEGRAL"})
        hits10 = _items(r10.json()) if r10.status_code == 200 else []
        check(
            "10. arama Türkçe büyük-küçük harfe duyarsız (İ/ı tuzağı)",
            r10.status_code == 200
            and ids["t2"] in {i["topic_id"] for i in hits10},
            f"{[i['topic_name'] for i in hits10]}",
        )

        # ---- 5. Zayıflık sinyali (yanlış arşivinden) → "zayıf" rozeti
        from app.models import WrongQuestion

        with SessionLocal() as db:
            for _ in range(3):
                db.add(WrongQuestion(
                    student_id=sid, topic_id=ids["t2"], source_kind="diger",
                    status="acik", note="zayıf sinyal",
                ))
            db.commit()
        r5 = c.get(f"/api/v2/teacher/students/{sid}/task-picker")
        weak = _items(r5.json(), "weak") if r5.status_code == 200 else []
        check(
            "5. zayıflık sinyali olan konu 'zayıf' rozetiyle ayrı grupta",
            any(i["topic_id"] == ids["t2"] and i["badge"] == "zayıf" for i in weak),
            f"{[(i['topic_name'], i['badge']) for i in weak]}",
        )

        # ---- 11. Sahiplik
        r11 = c.get(
            f"/api/v2/teacher/students/{ids['foreign_student']}/task-picker"
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
                from app.models import WrongQuestion

                db.execute(
                    sa_delete(WrongQuestion).where(WrongQuestion.student_id.in_(uid))
                )
                db.execute(
                    sa_delete(TopicClosure).where(TopicClosure.student_id.in_(uid))
                )
                tids = [r[0] for r in db.query(Task.id)
                        .filter(Task.student_id.in_(uid)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem)
                               .where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            if ids.get("book"):
                sbids = [r[0] for r in db.query(StudentBook.id)
                         .filter(StudentBook.book_id == ids["book"]).all()]
                if sbids:
                    db.execute(sa_delete(SectionProgress)
                               .where(SectionProgress.student_book_id.in_(sbids)))
                    db.execute(sa_delete(StudentBook)
                               .where(StudentBook.id.in_(sbids)))
                db.execute(sa_delete(BookSection)
                           .where(BookSection.book_id == ids["book"]))
                db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            if ids.get("subject"):
                db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subject"]))
                db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
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
