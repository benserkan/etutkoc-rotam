"""Görev miktarı öğrenme — smoke (P3, 2026-09-07).

KULLANICI KARARI: "koç genelde bir konudan 3 test 2 test şeklinde rutin
görevlendirme yapıyor; sistem bunu ders bazında öğrenmeli."

Canlı veri: ders bazında görevlerin %58-72'si aynı sayıda; aynı koç+ders
içinde öğrenciler arası fark gerçek ama küçük (1-2 test) → iki katman.

Senaryolar:
   1. Koçun ders tipiği öğrenilir (en sık değer)
   2. Ders bazında AYRIŞIR (Matematik 3, Türkçe 5)
   3. Öğrenci-özel veri yeterliyse ONA göre daralır (koç geneli 3, bu öğrenci 5)
   4. Öğrenci örneği azsa koç geneline düşer (eşik altı → ders medyanı)
   5. Hiç veri yoksa varsayılan 3
   6. Başka koçun geçmişi SIZMAZ
   7. Deneme kitabı sayılmaz (orada sayı "kaç deneme", test değil)
   8. Kitabı olmayan derste öneri KAYNAKSIZ görevlerden öğrenilir
   9. Ortalama değil EN SIK DEĞER (tek '40 test' girişi öneriyi kaydırmaz)
   9b. Mod ortancadan ayrışınca EN SIK olan kazanır (canlı veride 5 kat fark)
  10. Endpoint sahiplik: başka koçun öğrencisi → 404
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
    Subject,
    Task,
    TaskBookItem,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.services.task_quantity import DEFAULT_QUANTITY, learned_quantity

PFX = f"tq_{secrets.token_hex(3)}"
PWDH = "TaskQty!2345"

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


def main() -> int:
    print(f"\n=== görev miktarı öğrenme smoke — {PFX} ===\n")
    get_login_limiter().reset()
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWDH),
                         full_name="Miktar Koç", role=UserRole.TEACHER, is_active=True)
            other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWDH),
                         full_name="Diğer Koç", role=UserRole.TEACHER, is_active=True)
            db.add_all([coach, other])
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWDH),
                      full_name="Miktar Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12)
            st2 = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWDH),
                       full_name="İkinci Öğrenci", role=UserRole.STUDENT, is_active=True,
                       teacher_id=coach.id, grade_level=12)
            foreign_st = User(email=f"{PFX}_s3@test.invalid", password_hash=hash_password(PWDH),
                              full_name="Yabancı Öğrenci", role=UserRole.STUDENT,
                              is_active=True, teacher_id=other.id, grade_level=12)
            db.add_all([st, st2, foreign_st])
            db.flush()

            mat = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
            tur = Subject(name=f"{PFX} Türkçe", teacher_id=coach.id, order=2)
            bos = Subject(name=f"{PFX} Boş Ders", teacher_id=coach.id, order=3)
            omat = Subject(name=f"{PFX} Diğer Mat", teacher_id=other.id, order=1)
            db.add_all([mat, tur, bos, omat])
            db.flush()

            def mkbook(subject, name, btype=BookType.SORU_BANKASI, owner=None):
                b = Book(name=f"{PFX} {name}", teacher_id=(owner or coach).id,
                         subject_id=subject.id, type=btype)
                db.add(b)
                db.flush()
                sec = BookSection(book_id=b.id, label="Bölüm", order=1, test_count=999)
                db.add(sec)
                db.flush()
                return b, sec

            b_mat, s_mat = mkbook(mat, "Mat SB")
            b_tur, s_tur = mkbook(tur, "Türkçe SB")
            b_den, s_den = mkbook(mat, "Mat Deneme", BookType.BRANS_DENEMESI)
            b_other, s_other = mkbook(omat, "Diğer SB", owner=other)

            topic_mat = Topic(subject_id=mat.id, name="Türev", order=1,
                              teacher_id=coach.id)
            db.add(topic_mat)
            db.flush()

            day0 = date.today() - timedelta(days=60)
            seq = [0]

            def mktask(student, book, section, count, topic_id=None):
                seq[0] += 1
                t = Task(student_id=student.id, date=day0 + timedelta(days=seq[0]),
                         type=TaskType.TEST, title="x", is_draft=False)
                db.add(t)
                db.flush()
                db.add(TaskBookItem(
                    task_id=t.id,
                    book_id=(book.id if book else None),
                    book_section_id=(section.id if section else None),
                    topic_id=topic_id,
                    planned_count=count,
                ))
                db.flush()
                return t

            # Matematik: 2,3,3,3,3,3,3,4,4 → en sık 3 (öğrenci st2'ye, st'ye değil).
            # st2 havuzu bilerek KALABALIK: senaryo 3'te st'ye 5'lik görevler
            # eklenince koç geneli hâlâ 3 kalsın ki öğrenci-özel daralma
            # gerçekten ölçülebilsin.
            for n in (2, 3, 3, 3, 3, 3, 3, 4, 4):
                mktask(st2, b_mat, s_mat, n)
            # Türkçe: 5,5,5 → 5 (ders ayrışması)
            for n in (5, 5, 5):
                mktask(st2, b_tur, s_tur, n)
            # Deneme kitabı: 1,1,1 → SAYILMAMALI (Matematik dersinde)
            for _ in range(3):
                mktask(st2, b_den, s_den, 1)
            # Başka koç: 9,9,9 → sızmamalı
            for _ in range(3):
                mktask(foreign_st, b_other, s_other, 9)

            ids.update(coach=coach.id, other=other.id, student=st.id, student2=st2.id,
                       foreign_student=foreign_st.id, mat=mat.id, tur=tur.id,
                       bos=bos.id, omat=omat.id, b_mat=b_mat.id, b_tur=b_tur.id,
                       b_den=b_den.id, b_other=b_other.id, topic_mat=topic_mat.id)
            db.commit()

        with SessionLocal() as db:
            # ---- 1. Koç ders medyanı
            g = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["mat"])
            check("1. koçun ders tipiği öğrenildi (en sık 3)",
                  g.quantity == 3 and g.source == "coach", f"{g}")

            # ---- 2. Ders bazında ayrışma
            gt = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["tur"])
            check("2. ders bazında ayrışır (Matematik 3 · Türkçe 5)",
                  gt.quantity == 5 and g.quantity == 3, f"mat={g.quantity} tur={gt.quantity}")

            # ---- 7. Deneme kitabı sayılmadı (sayılsaydı 1'ler medyanı düşürürdü)
            check("7. deneme kitabı miktara sayılmaz (öneri 3 kaldı)",
                  g.quantity == 3, f"{g}")

            # ---- 6. Başka koçun geçmişi sızmaz
            # Örnek sayısı 9: koçun Matematik kalemleri.
            # Deneme kitabının 3 kalemi ile başka koçun 3 kalemi HARİÇ.
            check("6. başka koçun geçmişi sızmaz (9'lar Matematik'e girmedi)",
                  g.quantity == 3 and g.sample_size == 9,
                  f"quantity={g.quantity} n={g.sample_size}")

            # ---- 5. Hiç veri yok → varsayılan
            gb = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["bos"])
            check("5. geçmiş yoksa varsayılan 3 + source=default",
                  gb.quantity == DEFAULT_QUANTITY and gb.source == "default", f"{gb}")

            # ---- 4. Öğrenci örneği az → koç geneline düşer
            g4 = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["mat"],
                                  student_id=ids["student"])
            check("4. öğrenci örneği azsa koç geneline düşer",
                  g4.quantity == 3 and g4.source == "coach", f"{g4}")

        # ---- 3. Öğrenci-özel veri yeterliyse ona göre daralır
        with SessionLocal() as db:
            st_obj = db.get(User, ids["student"])
            b = db.get(Book, ids["b_mat"])
            sec = db.query(BookSection).filter(BookSection.book_id == b.id).first()
            for i, n in enumerate((5, 5, 5, 5, 5)):
                t = Task(student_id=st_obj.id, date=date.today() - timedelta(days=i + 1),
                         type=TaskType.TEST, title="x", is_draft=False)
                db.add(t)
                db.flush()
                db.add(TaskBookItem(task_id=t.id, book_id=b.id,
                                    book_section_id=sec.id, planned_count=n))
            db.commit()
        with SessionLocal() as db:
            g3 = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["mat"],
                                  student_id=ids["student"])
            gc = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["mat"])
            # Koç geneli TÜM öğrencileri kapsar: 3 altı kez, 5 beş kez → 3.
            # Bu öğrencinin KENDİ tipiği 5 → öneri ona göre daralır.
            check(
                "3. öğrenci-özel veri yeterliyse ONA göre daralır (öğrenci 5 · koç geneli 3)",
                g3.quantity == 5 and g3.source == "student"
                and gc.quantity == 3 and gc.source == "coach",
                f"ogrenci={g3.quantity}/{g3.source} koc={gc.quantity}",
            )

        # ---- 8. Kaynaksız görevler de sayılır. En temiz kanıt: HİÇ KİTABI
        #         OLMAYAN bir ders — öneri yalnızca kaynaksız kalemlerden gelir.
        #         (Kitaplı geçmişi olan derste bu kalemler havuza katılır ama
        #         mevcut alışkanlık ağır basabilir; orada ölçüm bulanıklaşır.)
        with SessionLocal() as db:
            st2_obj = db.get(User, ids["student2"])
            t_bos = Topic(subject_id=ids["bos"], name="Kaynaksız Konu", order=1,
                          teacher_id=ids["coach"])
            db.add(t_bos)
            db.flush()
            ids["topic_bos"] = t_bos.id
            for i in range(6):
                t = Task(student_id=st2_obj.id,
                         date=date.today() - timedelta(days=i + 1),
                         type=TaskType.TEST, title="x", is_draft=False)
                db.add(t)
                db.flush()
                db.add(TaskBookItem(task_id=t.id, book_id=None, book_section_id=None,
                                    topic_id=t_bos.id, planned_count=7))
            db.commit()
        with SessionLocal() as db:
            g8 = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["bos"],
                                  student_id=ids["student2"])
            g8c = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["bos"])
            check(
                "8. kitapsız derste öneri KAYNAKSIZ görevlerden öğrenilir (7)",
                g8.quantity == 7 and g8.source == "student"
                and g8c.quantity == 7 and g8c.source == "coach",
                f"ogrenci={g8} koc={g8c}",
            )

        # ---- 9. Medyan, ortalama değil: tek uç değer öneriyi kaydırmaz
        with SessionLocal() as db:
            st_obj = db.get(User, ids["student"])
            b = db.get(Book, ids["b_tur"])
            sec = db.query(BookSection).filter(BookSection.book_id == b.id).first()
            for i, n in enumerate((4, 4, 4, 4, 40)):
                t = Task(student_id=st_obj.id,
                         date=date.today() - timedelta(days=i + 1),
                         type=TaskType.TEST, title="x", is_draft=False)
                db.add(t)
                db.flush()
                db.add(TaskBookItem(task_id=t.id, book_id=b.id,
                                    book_section_id=sec.id, planned_count=n))
            db.commit()
        with SessionLocal() as db:
            g9 = learned_quantity(db, coach_id=ids["coach"], subject_id=ids["tur"],
                                  student_id=ids["student"])
            # ortalama 11.2 olurdu; medyan 4
            check("9. en sık değer kullanılır — tek '40 test' girişi öneriyi kaydırmaz",
                  g9.quantity == 4, f"{g9}")

        # ---- 9b. Mod ortancadan ayrıştığında EN SIK olan kazanmalı.
        #          Canlı veride bu fark 5 kata çıkıyordu (TYT Fizik: koç 1 ve 3
        #          veriyor, ortanca 2'yi neredeyse hiç vermiyordu).
        from app.services.task_quantity import _median, _typical
        dizi = [1, 1, 1, 2, 3, 3, 3, 3]
        check(
            "9b. mod ortancadan ayrışınca en sık değer kazanır (ortanca 2 · mod 3)",
            _median(dizi) == 2 and _typical(dizi) == 3,
            f"medyan={_median(dizi)} mod={_typical(dizi)}",
        )

        # ---- 10. Endpoint + sahiplik
        c = TestClient(app)
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWDH})
        assert r.status_code == 200, r.text
        r10a = c.get(f"/api/v2/teacher/students/{ids['student']}/task-quantity",
                     params={"subject_id": ids["mat"]})
        r10b = c.get(f"/api/v2/teacher/students/{ids['foreign_student']}/task-quantity",
                     params={"subject_id": ids["mat"]})
        body = r10a.json() if r10a.status_code == 200 else {}
        check(
            "10. endpoint gerekçe döner · başka koçun öğrencisi → 404",
            r10a.status_code == 200 and body.get("quantity") == 5
            and "genelde" in (body.get("reason") or "") and r10b.status_code == 404,
            f"{r10a.status_code}/{r10b.status_code} {body}",
        )

    finally:
        with SessionLocal() as db:
            uid = [
                v for k, v in ids.items()
                if k in ("coach", "other", "student", "student2", "foreign_student")
            ]
            if uid:
                tids = [r[0] for r in db.query(Task.id)
                        .filter(Task.student_id.in_(uid)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem)
                               .where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            bids = [v for k, v in ids.items()
                    if k in ("b_mat", "b_tur", "b_den", "b_other")]
            if bids:
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
            sids = [v for k, v in ids.items() if k in ("mat", "tur", "bos", "omat")]
            if sids:
                db.execute(sa_delete(Topic).where(Topic.subject_id.in_(sids)))
                db.execute(sa_delete(Subject).where(Subject.id.in_(sids)))
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
