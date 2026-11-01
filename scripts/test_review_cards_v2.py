"""Tekrar kartları v2 (2026-11-01) — seçici ekleme, günlük sınır, konu ölçeği
zamanlama, Kalıcı, geri alma, sil / yeniden aç.

Saha: Neslihan Hoca "dersten ekle" dedi → 8. sınıf öğrenciye 114 kart (tema
başlıkları + 5-7. sınıf + hiç çalışılmamış konular), hepsi aynı gün kuyrukta.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, ReviewCard, ReviewLog, SectionProgress,
    StudentBook, Subject, Topic, TopicClosure, User, UserRole,
)
from app.models.review import STATE_MASTERED, STATE_NEW, STATE_REVIEW
from app.services import review_scheduler as rs
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"rv2_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _days(a: datetime, b: datetime) -> float:
    a = a if a.tzinfo else a.replace(tzinfo=timezone.utc)
    b = b if b.tzinfo else b.replace(tzinfo=timezone.utc)
    return (a - b).total_seconds() / 86400.0


def seed() -> dict:
    with SessionLocal() as db:
        t = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PASSWORD),
                 full_name="RV2 Koç", role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        t2 = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PASSWORD),
                  full_name="RV2 Diğer Koç", role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PASSWORD),
                 full_name="RV2 Öğrenci", role=UserRole.STUDENT, is_active=True,
                 grade_level=8, teacher_id=t.id)
        s2 = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PASSWORD),
                  full_name="RV2 Diğer Öğrenci", role=UserRole.STUDENT, is_active=True,
                  grade_level=8, teacher_id=t2.id)
        db.add_all([s, s2]); db.flush()
        subj = Subject(name=f"RV2 Ders {PFX}", order=999, is_builtin=False, teacher_id=t.id)
        db.add(subj); db.flush()

        def topic(name, grade, order, parent=None):
            x = Topic(subject_id=subj.id, name=name, order=order, grade_level=grade,
                      is_builtin=False, teacher_id=t.id, parent_id=parent)
            db.add(x); db.flush()
            return x

        parent = topic("1. Tema: Sayılar", 8, 0)
        l1 = topic("Çarpanlar", 8, 1, parent.id)
        l2 = topic("Üslü İfadeler", 8, 2, parent.id)
        l3 = topic("Kesirler (6)", 6, 3)
        l4 = topic("Fonksiyonlar (9)", 9, 4)
        extra = [topic(f"Ek Konu {i}", 8, 10 + i) for i in range(15)]

        book = Book(name=f"RV2 Kitap {PFX}", subject_id=subj.id,
                    type=BookType.SORU_BANKASI, teacher_id=t.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Çarpanlar", test_count=10, order=0, topic_id=l1.id)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=s.id, book_id=book.id)
        db.add(sb); db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               completed_count=3, reserved_count=0))
        db.add(TopicClosure(student_id=s.id, topic_id=l2.id, closed_by_id=t.id))
        db.commit()
        return dict(t=t.id, t2=t2.id, s=s.id, s2=s2.id, subj=subj.id, parent=parent.id,
                    l1=l1.id, l2=l2.id, l3=l3.id, l4=l4.id, extra=[e.id for e in extra],
                    book=book.id)


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        sids = [ids["s"], ids["s2"]]
        db.query(ReviewLog).filter(ReviewLog.student_id.in_(sids)).delete(synchronize_session=False)
        db.query(ReviewCard).filter(ReviewCard.student_id.in_(sids)).delete(synchronize_session=False)
        db.query(TopicClosure).filter(TopicClosure.student_id.in_(sids)).delete(synchronize_session=False)
        sb_ids = [x for (x,) in db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids)).all()]
        if sb_ids:
            db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sb_ids)).delete(synchronize_session=False)
        db.query(StudentBook).filter(StudentBook.student_id.in_(sids)).delete(synchronize_session=False)
        db.query(BookSection).filter(BookSection.book_id == ids["book"]).delete(synchronize_session=False)
        db.query(Book).filter(Book.id == ids["book"]).delete(synchronize_session=False)
        db.query(Topic).filter(Topic.subject_id == ids["subj"]).delete(synchronize_session=False)
        db.query(Subject).filter(Subject.id == ids["subj"]).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(sids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([ids["t"], ids["t2"]])).delete(synchronize_session=False)
        db.commit()


def login(client: TestClient, email: str) -> None:
    get_login_limiter().reset()
    client.cookies.clear()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text


def main() -> int:
    ids = seed()
    try:
        client = TestClient(app)
        login(client, f"{PFX}_t@test.invalid")
        base = f"/api/v2/teacher/students/{ids['s']}/review"

        # 1) Aday listesi
        r = client.get(f"{base}/candidates", params={"subject_id": ids["subj"]})
        body = r.json()
        tids = {x["topic_id"]: x for x in body.get("topics", [])}
        check("1a. candidates 200", r.status_code == 200, r.text[:200])
        check("1b. tema başlığı listede YOK", ids["parent"] not in tids)
        check("1c. üst sınıf (9) konusu YOK", ids["l4"] not in tids)
        check("1d. alt sınıf (6) konusu listede ama önerilmez",
              ids["l3"] in tids and not tids[ids["l3"]]["recommended"])
        check("1e. çalışılan konu önerilir + neden '3 test çözdü'",
              tids.get(ids["l1"], {}).get("recommended") is True
              and "3 test çözdü" in tids[ids["l1"]]["reasons"])
        check("1f. koçun kapattığı konu önerilir",
              tids.get(ids["l2"], {}).get("recommended") is True
              and "Koç konuyu kapattı" in tids[ids["l2"]]["reasons"])
        check("1g. recommended_count = 2", body.get("recommended_count") == 2,
              str(body.get("recommended_count")))

        # 2) Eski istemci: yalnız subject_id → yalnız önerilenler
        r = client.post(f"{base}/seed", json={"subject_id": ids["subj"]})
        d = r.json().get("data", {})
        check("2a. subject-only seed → yalnız 2 önerilen eklenir",
              r.status_code == 200 and d.get("added") == 2 and d.get("used_recommended") is True,
              str(d))

        # 3) Seçili konular: geçersizler elenir
        r = client.post(f"{base}/seed", json={"subject_id": ids["subj"],
                                              "topic_ids": [ids["l3"], ids["parent"], ids["l4"]]})
        d = r.json().get("data", {})
        check("3a. seçili seed: alt sınıf eklenir, tema+üst sınıf reddedilir",
              d.get("added") == 1 and d.get("skipped_invalid") == 2, str(d))

        # 4) Günlük yeni kart sınırı
        r = client.post(f"{base}/seed", json={"subject_id": ids["subj"], "topic_ids": ids["extra"]})
        check("4a. 15 ek kart eklendi", r.json().get("data", {}).get("added") == 15)
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            due = rs.get_due_cards(db, student_id=ids["s"], now=now, limit=100)
            bd = rs.cards_breakdown(db, student_id=ids["s"], now=now)
            check("4b. 18 yeni kartın yalnız 10'u bugün gelir",
                  len(due) == 10 and bd.due_now == 10 and bd.new == 18 and bd.new_waiting == 8,
                  f"due={len(due)} due_now={bd.due_now} new={bd.new} waiting={bd.new_waiting}")
            for c in due[:3]:
                rs.record_review(db, card=c, rating=3, now=now)
            db.commit()
            due2 = rs.get_due_cards(db, student_id=ids["s"], now=now, limit=100)
            check("4c. 3 kart puanlanınca bugün kalan 7 (kota tükeniyor, yenisi gelmiyor)",
                  len(due2) == 7 and rs.count_due_for_student(db, student_id=ids["s"], now=now) == 7,
                  f"{len(due2)}")
            load = {x["student"].id: x for x in rs.teacher_review_load(db, teacher_id=ids["t"], now=now)}
            check("4d. koç filo ekranı da sınırı uygular",
                  load[ids["s"]]["due_now"] == 7, str(load[ids["s"]]["due_now"]))
            tomorrow = now + timedelta(days=1)
            check("4e. ertesi gün yeni kota açılır (10)",
                  rs.count_due_for_student(db, student_id=ids["s"], now=tomorrow) == 10)

        # 5) Konu ölçeği zamanlama
        with SessionLocal() as db:
            cards = db.query(ReviewCard).filter(ReviewCard.student_id == ids["s"],
                                                ReviewCard.state == STATE_NEW).limit(3).all()
            t0 = datetime.now(timezone.utc)
            for c, rating, lo, hi in [(cards[0], 1, 6.99, 7.01), (cards[1], 2, 2.99, 99),
                                      (cards[2], 3, 6.99, 99)]:
                rs.record_review(db, card=c, rating=rating, now=t0)
                gap = _days(c.due_at, t0)
                check(f"5. puan {rating} → {gap:.2f} gün sonra", lo <= gap <= hi)
            db.commit()

            # 6) Hatırlamadım sonrası 1 hafta kuyrukta görünmez
            again_card = cards[0]
            check("6a. Hatırlamadım kartı 6. gün kuyrukta YOK",
                  again_card.id not in [x.id for x in rs.get_due_cards(db, student_id=ids["s"], now=t0 + timedelta(days=6), limit=200)])
            check("6b. 7. günde kuyrukta",
                  again_card.id in [x.id for x in rs.get_due_cards(db, student_id=ids["s"], now=t0 + timedelta(days=7, minutes=1), limit=200)])

            # 7) Hep İyi → aralıklar ve Kalıcı
            c = cards[2]
            t = t0
            gaps = [round(_days(c.due_at, t), 1)]
            for _ in range(8):
                t = c.due_at + timedelta(minutes=1)
                rs.record_review(db, card=c, rating=3, now=t)
                if c.state == STATE_MASTERED:
                    break
                gaps.append(round(_days(c.due_at, t), 1))
            db.commit()
            print(f"     İyi-İyi-İyi aralıkları (gün): {gaps} → {c.state}")
            check("7a. hep İyi → kart Kalıcı olur", c.state == STATE_MASTERED, c.state)
            check("7b. aralıklar artan, ilki 7 gün",
                  gaps[0] >= 7 and all(b >= a for a, b in zip(gaps, gaps[1:])), str(gaps))
            check("7c. Kalıcı kart kuyrukta değil (1 yıl sonra bile)",
                  c.id not in [x.id for x in rs.get_due_cards(db, student_id=ids["s"], now=t + timedelta(days=365), limit=500)])
            mastered_id = c.id

            # 8) Aynı gün alıştırması vadeyi oynatmaz
            c = cards[1]
            before_due = c.due_at
            rs.record_review(db, card=c, rating=3, now=t0 + timedelta(hours=2))
            check("8. aynı gün ikinci puan vadeyi değiştirmez",
                  abs(_days(c.due_at, before_due)) < 1e-6)
            db.commit()

        # 9) Kalıcı karta puan → 409; koç yeniden açar
        login(client, f"{PFX}_s@test.invalid")
        r = client.post(f"/api/v2/student/review/{mastered_id}/rate", json={"rating": 3})
        check("9a. Kalıcı karta puan → 409 card_mastered",
              r.status_code == 409 and r.json().get("detail", {}).get("code") == "card_mastered", r.text[:150])

        # 10) Geri alma (gerçek saat)
        with SessionLocal() as db:
            fresh = db.query(ReviewCard).filter(ReviewCard.student_id == ids["s"],
                                                ReviewCard.state == STATE_NEW).first()
            fid = fresh.id
        r = client.post(f"/api/v2/student/review/{fid}/rate", json={"rating": 1})
        check("10a. puan verildi", r.status_code == 200)
        r = client.post(f"/api/v2/student/review/{fid}/undo")
        dd = r.json().get("data", {})
        check("10b. geri al → kart yeniden Yeni, sayaçlar sıfır",
              r.status_code == 200 and dd.get("state") == "new" and dd.get("review_count") == 0
              and dd.get("lapse_count") == 0 and dd.get("due_at") is None, str(dd)[:200])
        with SessionLocal() as db:
            check("10c. log silindi", db.query(ReviewLog).filter(ReviewLog.card_id == fid).count() == 0)
        r = client.post(f"/api/v2/student/review/{fid}/undo")
        check("10d. ikinci geri al → 409 nothing_to_undo",
              r.status_code == 409 and r.json()["detail"]["code"] == "nothing_to_undo")

        # 10e) ikinci tekrar geri alınınca önceki vade geri gelir
        with SessionLocal() as db:
            c = db.get(ReviewCard, fid)
            past = datetime.now(timezone.utc) - timedelta(days=10)
            rs.record_review(db, card=c, rating=3, now=past)
            db.commit()
            prev_due = c.due_at
        r = client.post(f"/api/v2/student/review/{fid}/rate", json={"rating": 2})
        r = client.post(f"/api/v2/student/review/{fid}/undo")
        with SessionLocal() as db:
            c = db.get(ReviewCard, fid)
            check("10e. önceki vade + durum geri geldi",
                  c.state == STATE_REVIEW and c.review_count == 1 and abs(_days(c.due_at, prev_due)) < 1e-4,
                  f"{c.state} {c.review_count} {c.due_at} {prev_due}")
            # pencere dışı
            lg = db.query(ReviewLog).filter(ReviewLog.card_id == fid).first()
            lg.reviewed_at = datetime.now(timezone.utc) - timedelta(minutes=11)
            db.commit()
        r = client.post(f"/api/v2/student/review/{fid}/undo")
        check("10f. 10 dakika geçince geri alma kapalı (409)",
              r.status_code == 409 and r.json()["detail"]["code"] == "undo_window_passed")

        # 11) Koç: yeniden aç + sil + izolasyon
        login(client, f"{PFX}_t@test.invalid")
        r = client.post(f"{base}/cards/reopen", json={"card_ids": [mastered_id]})
        with SessionLocal() as db:
            c = db.get(ReviewCard, mastered_id)
            check("11a. yeniden aç → Pekiştirme + bugün vadeli",
                  r.json()["data"]["count"] == 1 and c.state == STATE_REVIEW and c.due_at is not None)
            two = [x for (x,) in db.query(ReviewCard.id).filter(ReviewCard.student_id == ids["s"]).limit(2).all()]
        r = client.post(f"{base}/cards/delete", json={"card_ids": two})
        with SessionLocal() as db:
            check("11b. 2 kart silindi (geçmişiyle)",
                  r.json()["data"]["count"] == 2
                  and db.query(ReviewCard).filter(ReviewCard.id.in_(two)).count() == 0
                  and db.query(ReviewLog).filter(ReviewLog.card_id.in_(two)).count() == 0)
        r = client.post(f"/api/v2/teacher/students/{ids['s2']}/review/cards/delete", json={"card_ids": [1]})
        check("11c. başka koçun öğrencisi → 404", r.status_code == 404)
        r = client.get(base)
        check("11d. GET review breakdown yeni alanlar",
              r.status_code == 200 and "new_waiting" in r.json()["breakdown"]
              and r.json()["breakdown"]["new_per_day"] == 10)
    finally:
        cleanup(ids)

    print(f"\n{passed} passed, {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
