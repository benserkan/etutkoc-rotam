"""Deneme görevleri D1 — tanıma + koç ekleme smoke (2026-10-20).

Kural: deneme kalemi (exam_kind dolu) = 1 deneme; "×2" = 1 görev, 2 kalem.

Senaryolar:
   1. Seçenekler: ders (standart soru) + deneme kitabı (sıradaki denemeler) + genel türler
   2. Kaynaklı branş ×2 → 2 kalem, sıradaki bölümler, soru sayısı standarttan, rezerv 1'er
   3. Kitap biterse kapasite aşımı UYARI ile atanır (engel değil)
   4. Koçun girdiği soru sayısı kitaba yazılır (bir dahaki sefere hazır gelir)
   5. Kaynaksız branş ×3 (özel ders hocası, 20 soru) → 3 kalem, dersli, kitapsız
   6. Genel deneme (TYT) → tam_deneme kategorisi, 120 soru
   7. Görev kutusu yolu: deneme kitabından planned=2 kalem → otomatik 2 deneme kalemine açılır
   8. Sınıflandırma + deneme adedi (gorev_stats / week_test_deneme_for) kalem başına sayar
   9. Öğrenci girişi esnek: 7 soruluk denemede 8 doğru girilebilir (zorlama yok)
  10. Yay (spread) kitapsız branş denemesinin deneme alanlarını korur
  11. Koç kalıpları (şablon çipleri) geçmişten öğrenilir
  12. Hatalar: ders yok 422 · atanmamış kitap 404 · deneme kaleminde planned≠1 422
  13. Koç ve öğrenci görev yanıtında exam_kind / question_count görünür
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, SectionProgress, StudentBook, Subject, Task, TaskBookItem, User, UserRole,
)
from app.models.book import BookType
from app.models.curriculum import ExamSection
from app.services import gorev_stats
from app.services.analytics import week_test_deneme_for
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"dn_{secrets.token_hex(3)}"
PWD = "DenemeTest!2345"
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


def login(c: TestClient, email: str) -> None:
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text


def main() -> int:
    print(f"\n=== deneme görevleri D1 — {PFX} ===\n")
    get_login_limiter().reset()
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="Deneme Koç", role=UserRole.TEACHER, is_active=True)
            db.add(coach); db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                      full_name="Deneme Öğrenci", role=UserRole.STUDENT, is_active=True,
                      teacher_id=coach.id, grade_level=12, must_change_password=False)
            other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD),
                         full_name="Diğer Öğrenci", role=UserRole.STUDENT, is_active=True,
                         teacher_id=coach.id, grade_level=12)
            db.add_all([st, other]); db.flush()
            bio = Subject(name="TYT Biyoloji", teacher_id=coach.id, order=1,
                          exam_section=ExamSection.TYT)
            mat = Subject(name="TYT Matematik", teacher_id=coach.id, order=2,
                          exam_section=ExamSection.TYT)
            db.add_all([bio, mat]); db.flush()
            book = Book(name=f"{PFX} Biyoloji Branş", teacher_id=coach.id, subject_id=bio.id,
                        type=BookType.BRANS_DENEMESI)
            mbook = Book(name=f"{PFX} Matematik Branş", teacher_id=coach.id, subject_id=mat.id,
                         type=BookType.BRANS_DENEMESI)
            unassigned = Book(name=f"{PFX} Atanmamış", teacher_id=coach.id, subject_id=bio.id,
                              type=BookType.BRANS_DENEMESI)
            db.add_all([book, mbook, unassigned]); db.flush()
            secs = [BookSection(book_id=book.id, label=f"DENEME {i}", order=i, test_count=1)
                    for i in range(1, 4)]
            msec = BookSection(book_id=mbook.id, label="Deneme", order=1, test_count=10)
            usec = BookSection(book_id=unassigned.id, label="Deneme 1", order=1, test_count=1)
            db.add_all(secs + [msec, usec]); db.flush()
            db.add_all([StudentBook(student_id=st.id, book_id=book.id),
                        StudentBook(student_id=st.id, book_id=mbook.id)])
            db.commit()
            ids.update(coach=coach.id, st=st.id, other=other.id, bio=bio.id, mat=mat.id,
                       book=book.id, mbook=mbook.id, unassigned=unassigned.id,
                       s1=secs[0].id, s2=secs[1].id, s3=secs[2].id, msec=msec.id)

        c = TestClient(app)
        login(c, f"{PFX}_t@test.invalid")
        sid = ids["st"]
        day = (date.today() + timedelta(days=1)).isoformat()

        # 1
        r = c.get(f"/api/v2/teacher/students/{sid}/deneme-options")
        check("1a. seçenekler 200", r.status_code == 200, r.text[:300])
        opt = r.json()
        sb = next((s for s in opt["subjects"] if s["id"] == ids["bio"]), None)
        check("1b. TYT Biyoloji standart 6 soru", sb and sb["standard_question_count"] == 6, str(sb))
        bk = next((b for b in opt["books"] if b["book_id"] == ids["book"]), None)
        check("1c. kitap 3 sıradaki deneme", bk and len(bk["next_sections"]) == 3, str(bk))
        check("1d. 12. sınıf genel türleri TYT içerir",
              any(p["key"] == "tyt" for p in opt["genel_presets"]), str(opt["genel_presets"]))

        # 2
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "book_id": ids["book"], "count": 2})
        check("2a. kaynaklı ×2 200", r.status_code == 200, r.text[:300])
        t = r.json()["data"]
        its = t["items"]
        check("2b. 2 kalem, her biri 1 deneme", len(its) == 2 and all(i["planned_count"] == 1 for i in its),
              str([i["planned_count"] for i in its]))
        check("2c. sıradaki bölümler (DENEME 1, 2)",
              [i["section_id"] for i in its] == [ids["s1"], ids["s2"]], str([i["section_id"] for i in its]))
        check("2d. exam_kind brans + 6 soru",
              all(i["exam_kind"] == "brans" and i["question_count"] == 6 for i in its), str(its[0]))
        check("2e. başlık deneme adlarını ve soru sayısını taşır",
              "DENEME 1, DENEME 2" in t["title"] and "(6 soru)" in t["title"], t["title"])
        with SessionLocal() as db:
            sp = db.query(SectionProgress).join(StudentBook).filter(
                StudentBook.student_id == sid,
                SectionProgress.book_section_id.in_([ids["s1"], ids["s2"]])).all()
            check("2f. her bölümde rezerv 1", sorted(p.reserved_count for p in sp) == [1, 1],
                  str([p.reserved_count for p in sp]))

        # 3
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "book_id": ids["book"], "count": 2})
        check("3a. kitap biterken 200 (engel yok)", r.status_code == 200, r.text[:300])
        check("3b. kapasite aşımı uyarısı", any("üstünde" in w for w in r.json().get("warnings", [])),
              str(r.json().get("warnings")))
        check("3c. ilk kalem DENEME 3", r.json()["data"]["items"][0]["section_id"] == ids["s3"])

        # 4
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "book_id": ids["mbook"], "count": 1,
                         "question_count": 30})
        check("4a. koç sayısıyla 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            check("4b. kitaba 30 yazıldı", db.get(Book, ids["mbook"]).avg_questions_per_test == 30)
        r = c.get(f"/api/v2/teacher/students/{sid}/deneme-options")
        mb = next(b for b in r.json()["books"] if b["book_id"] == ids["mbook"])
        check("4c. bir sonraki seferde 30 hazır gelir",
              mb["question_count"] == 30 and mb["question_source"] == "book", str(mb))

        # 5
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "subject_id": ids["mat"], "count": 3,
                         "question_count": 20, "name": "Özel ders matematik denemesi"})
        check("5a. kaynaksız ×3 200", r.status_code == 200, r.text[:300])
        t5 = r.json()["data"]
        check("5b. 3 kalem kitapsız + dersli",
              len(t5["items"]) == 3 and all(i["book_id"] is None and i["subject_id"] == ids["mat"]
                                            for i in t5["items"]), str(t5["items"][0]))
        check("5c. başlık ×3 (20 soru)", "×3" in t5["title"] and "(20 soru)" in t5["title"], t5["title"])
        brans_free_task = t5["id"]

        # 6
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "genel", "genel_key": "tyt", "count": 1,
                         "name": "Özdebir TG-4"})
        check("6a. genel TYT 200", r.status_code == 200, r.text[:300])
        t6 = r.json()["data"]
        check("6b. 120 soru + genel", t6["items"][0]["question_count"] == 120
              and t6["items"][0]["exam_kind"] == "genel", str(t6["items"][0]))
        check("6c. başlık ad + tür", "Özdebir TG-4" in t6["title"] and "TYT" in t6["title"], t6["title"])

        # 7 (görev kutusu / test formu yolu)
        with SessionLocal() as db:
            db.add(BookSection(book_id=ids["book"], label="DENEME 4 (7 soru)", order=4, test_count=2))
            db.commit()
            s4 = db.query(BookSection).filter(BookSection.book_id == ids["book"],
                                              BookSection.order == 4).one().id
        r = c.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": day, "type": "test", "title": "Görev",
            "items": [{"book_id": ids["book"], "section_id": s4, "planned_count": 2}]})
        check("7a. görev kutusu yolu 200", r.status_code == 200, r.text[:300])
        t7 = r.json()["data"]
        check("7b. 2 deneme kalemine açıldı", len(t7["items"]) == 2
              and all(i["exam_kind"] == "brans" and i["planned_count"] == 1 for i in t7["items"]),
              str([(i["planned_count"], i["exam_kind"]) for i in t7["items"]]))
        check("7c. soru sayısı bölüm adından (7)", t7["items"][0]["question_count"] == 7)
        check("7d. başlık placeholder değil", "Görev" != t7["title"] and "7 soru" in t7["title"], t7["title"])

        # 8
        with SessionLocal() as db:
            tasks = db.query(Task).filter(Task.student_id == sid).all()
            cats = {t.id: gorev_stats.classify_gorev(t) for t in tasks}
            check("8a. kaynaksız branş → deneme", cats[brans_free_task] == "deneme", cats[brans_free_task])
            check("8b. genel → tam_deneme", cats[t6["id"]] == "tam_deneme", cats[t6["id"]])
            summ = gorev_stats.summarize(tasks)
            # 2 + 2 + 1 + 3 + 1 + 2 = 11 deneme
            check("8c. deneme adedi kalem başına (11)", summ.deneme_planned == 11, str(summ.deneme_planned))
            check("8d. test hacmine girmez", summ.test_planned == 0, str(summ.test_planned))
            for tk in tasks:
                tk.is_draft = False
            db.commit()
            w = week_test_deneme_for(db, sid, date.today() + timedelta(days=1))
            check("8e. kurum deneme adedi 11", w.deneme_planned == 11, str(w.deneme_planned))
            ders = gorev_stats.primary_subject(db.get(Task, brans_free_task))
            check("8f. kitapsız branşın dersi bulunur", ders is not None and ders.id == ids["mat"])

        # 9 — öğrenci esnek giriş
        c2 = TestClient(app)
        login(c2, f"{PFX}_s@test.invalid")
        item_id = t7["items"][0]["id"]
        with SessionLocal() as db:
            tk = db.get(Task, t7["id"]); tk.date = date.today(); tk.is_draft = False; db.commit()
        day = date.today().isoformat()
        r = c2.post(f"/api/v2/student/tasks/{t7['id']}/items/{item_id}/set-completed",
                    json={"completed": 1, "correct": 8, "wrong": 0, "blank": 0})
        check("9a. 7 soruluk denemede 8 doğru girilebilir", r.status_code == 200, r.text[:300])
        r = c2.get(f"/api/v2/student/day?date={day}")
        if r.status_code == 200:
            flat = [i for tk in r.json().get("tasks", []) for i in tk.get("items", [])]
            ex = next((i for i in flat if i["id"] == item_id), None)
            check("9b. öğrenci yanıtında deneme alanları", ex and ex["exam_kind"] == "brans"
                  and ex["question_count"] == 7 and ex["is_test_unit"] is True, str(ex))
        else:
            check("9b. öğrenci gün ucu", False, r.text[:200])

        # 10 — yay
        r = c.post(f"/api/v2/teacher/tasks/{brans_free_task}/spread",
                   json={"dates": [(date.today() + timedelta(days=2)).isoformat()]})
        check("10a. yay 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            copies = (db.query(Task).filter(Task.student_id == sid,
                                            Task.date == date.today() + timedelta(days=2)).all())
            its10 = [i for tk in copies for i in tk.book_items]
            check("10b. kopya deneme alanlarını korur", len(its10) == 3 and all(
                i.exam_kind == "brans" and i.subject_id == ids["mat"] and i.question_count == 20
                for i in its10), str([(i.exam_kind, i.subject_id) for i in its10]))

        # 11
        r = c.get(f"/api/v2/teacher/students/{ids['other']}/deneme-options")
        tpls = r.json()["templates"]
        check("11a. başka öğrencide kalıp önerisi (TYT Matematik ×3 · 20)",
              any(t["subject_id"] == ids["mat"] and t["count"] == 3 and t["question_count"] == 20
                  for t in tpls), str(tpls))
        check("11b. öğrenciye atanmamış kitabın kalıbı kitapsız önerilir",
              all(t["book_id"] is None for t in tpls), str(tpls))

        # 12
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "count": 1})
        check("12a. ders yok 422", r.status_code == 422 and r.json()["detail"]["code"] == "subject_required")
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": day, "kind": "brans", "book_id": ids["unassigned"], "count": 1})
        check("12b. atanmamış kitap 404", r.status_code == 404, r.text[:200])
        r = c.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": day, "type": "other", "title": "x",
            "items": [{"planned_count": 3, "exam_kind": "brans", "subject_id": ids["mat"]}]})
        check("12c. deneme kaleminde planned≠1 422",
              r.status_code == 422 and r.json()["detail"]["code"] == "deneme_item_count", r.text[:200])

        # 13
        r = c.get(f"/api/v2/teacher/students/{sid}/week?start={day}")
        ok13 = False
        if r.status_code == 200:
            flat = [i for d in r.json().get("days", []) for tk in d.get("tasks", []) for i in tk["items"]]
            ok13 = any(i.get("exam_kind") == "genel" and i.get("question_count") == 120 for i in flat)
        check("13. koç hafta yanıtında deneme alanları", ok13, r.text[:200])
    finally:
        with SessionLocal() as db:
            uids = [v for k, v in ids.items() if k in ("coach", "st", "other")]
            if uids:
                tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(uids)).all()]
                if tids:
                    db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
                    db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
                sbs = [s.id for s in db.query(StudentBook).filter(StudentBook.student_id.in_(uids)).all()]
                if sbs:
                    db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbs)).delete(synchronize_session=False)
                    db.query(StudentBook).filter(StudentBook.id.in_(sbs)).delete(synchronize_session=False)
                bids = [b.id for b in db.query(Book).filter(Book.teacher_id == ids.get("coach")).all()]
                if bids:
                    db.query(BookSection).filter(BookSection.book_id.in_(bids)).delete(synchronize_session=False)
                    db.query(Book).filter(Book.id.in_(bids)).delete(synchronize_session=False)
                db.query(Subject).filter(Subject.teacher_id == ids.get("coach")).delete(synchronize_session=False)
                db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
                db.commit()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
