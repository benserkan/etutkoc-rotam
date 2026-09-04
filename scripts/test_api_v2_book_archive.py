"""Kitap arşivi — smoke (P4, 2026-09-04).

SAHA İHTİYACI: sınıf atlayınca geçen yılın kitapları kütüphanede kalıyor
(8→9 geçen Yiğit'te 58 kitap ataması). Silme YANLIŞ — yaz tekrarı için kitap
gerekebilir ve görev geçmişi kitaba bağlı. Arşiv = SOFT + GERİ ALINABİLİR.

Bu smoke iki yönü birden korur:
  · GİZLENMESİ GEREKENLER (ileriye dönük): kitap paneli, öğrenci "Kitaplarım",
    görev kaynak seçici, müfredat kapsama, bağımsız çalışma, yeni görev atama
  · KORUNMASI GEREKENLER (geçmiş): görevler, TaskBookItem, SectionProgress
    sayaçları, kaydın kendisi — arşiv veri SİLMEZ

Senaryolar:
   1. Arşivle → koç panelinde YOK, archived_count=1
   2. ?include_archived=true → görünür + is_archived işaretli
   3. GÖREV GEÇMİŞİ + SAYAÇLAR KORUNDU (arşiv veri silmez)
   4. Arşivli kitaba yeni görev atanamaz → 422 book_archived
   5. Öğrenci "Kitaplarım"da görünmez
   6. Görev ekleme kaynak seçicisinde (hafta planı) görünmez
   7. Müfredat kapsamada "kaynak" sayılmaz
   8. Bağımsız çalışma seçeneklerinde yok
   9. İdempotent: ikinci arşivleme changed=0
  10. Arşivden çıkar → hepsi geri gelir
  11. Yeniden atama arşivden ÇIKARIR (koç ayrıca "geri al" demesin)
  12. Arşiv adayları = güncel dönem başlamadan atanmış kitaplar (P2 bağı)
  13. Kapılar: yabancı öğrenci 404 · boş liste 422
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
    CurriculumModel,
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

PFX = f"ba_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


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
                     full_name="Arşiv Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Arşiv Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Arşiv Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=9)
        st2 = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWD),
                   full_name="Yabancı Öğrenci", role=UserRole.STUDENT, is_active=True,
                   teacher_id=other.id, grade_level=9)
        db.add_all([st, st2])
        db.flush()

        # Maarif 9 dersi + konu (müfredat kapsama testi için)
        subj = Subject(name=f"Arşiv Ders {PFX}", teacher_id=coach.id,
                       curriculum_model=CurriculumModel.MAARIF_LISE,
                       min_grade_level=9, max_grade_level=12)
        db.add(subj)
        db.flush()
        topic = Topic(subject_id=subj.id, name=f"Arşiv Konu {PFX}", order=1)
        db.add(topic)
        db.flush()

        # ESKİ kitap (arşivlenecek) + YENİ kitap (aktif kalacak)
        old_book = Book(name=f"Gecen Yil Kitabi {PFX}", subject_id=subj.id,
                        teacher_id=coach.id, type=BookType.SORU_BANKASI)
        new_book = Book(name=f"Bu Yil Kitabi {PFX}", subject_id=subj.id,
                        teacher_id=coach.id, type=BookType.SORU_BANKASI)
        db.add_all([old_book, new_book])
        db.flush()
        old_sec = BookSection(book_id=old_book.id, label="Eski Bölüm",
                              test_count=20, order=1, topic_id=topic.id)
        new_sec = BookSection(book_id=new_book.id, label="Yeni Bölüm",
                              test_count=20, order=1, topic_id=topic.id)
        db.add_all([old_sec, new_sec])
        db.flush()

        # Eski kitap GEÇEN dönemde atandı (arşiv adayı), yenisi bu dönemde
        sb_old = StudentBook(student_id=st.id, book_id=old_book.id,
                             assigned_at=datetime(2026, 4, 20, tzinfo=timezone.utc))
        sb_new = StudentBook(student_id=st.id, book_id=new_book.id,
                             assigned_at=datetime(2026, 9, 2, tzinfo=timezone.utc))
        db.add_all([sb_old, sb_new])
        db.flush()
        db.add(SectionProgress(student_book_id=sb_old.id, book_section_id=old_sec.id,
                               reserved_count=0, completed_count=7))

        # Geçen yılın TAMAMLANMIŞ görevi — arşivden sonra da durmalı
        t = Task(student_id=st.id, date=date(2026, 5, 10), type=TaskType.TEST,
                 title="Geçen yıl görevi", status=TaskStatus.COMPLETED, is_draft=False)
        db.add(t)
        db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=old_book.id,
                            book_section_id=old_sec.id,
                            planned_count=7, completed_count=7))

        # P2 dönemi: güncel dönem 1 Eylül'de başladı (arşiv adayı sınırı)
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_([st.id, st2.id])))
        db.add(StudentGradePeriod(
            student_id=st.id, grade_level=8, is_graduate=False,
            curriculum_model="lgs", started_on=date(2026, 4, 20),
            ended_on=date(2026, 8, 31)))
        db.add(StudentGradePeriod(
            student_id=st.id, grade_level=9, is_graduate=False,
            curriculum_model="maarif_lise", started_on=date(2026, 9, 1)))
        db.commit()
        return {
            "coach_id": coach.id, "other_id": other.id,
            "student_id": st.id, "student2_id": st2.id,
            "subject_id": subj.id, "topic_id": topic.id,
            "old_book": old_book.id, "new_book": new_book.id,
            "old_sec": old_sec.id, "new_sec": new_sec.id,
            "task_id": t.id,
        }


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["other_id"], s["student_id"], s["student2_id"]]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(StudentGradePeriod).where(
            StudentGradePeriod.student_id.in_(ids)))
        sbids = [r.id for r in db.query(StudentBook).filter(
            StudentBook.student_id.in_(ids)).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.student_book_id.in_(sbids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
        for bid in (s["old_book"], s["new_book"]):
            db.execute(sa_delete(BookSection).where(BookSection.book_id == bid))
            db.execute(sa_delete(Book).where(Book.id == bid))
        db.execute(sa_delete(Topic).where(Topic.subject_id == s["subject_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def main() -> int:
    s = seed()
    sid, old_b, new_b = s["student_id"], s["old_book"], s["new_book"]
    print(f"\n=== Kitap arşivi (öğrenci #{sid}) ===\n")
    try:
        c = TestClient(app)
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        # ---- 12. arşiv adayları (P2 dönem sınırı) — arşivlemeden ÖNCE
        r = c.get(f"/api/v2/teacher/students/{sid}/books/archive-candidates")
        cd = r.json() if r.text else {}
        cand_ids = [x["book_id"] for x in cd.get("candidates", [])]
        check("12. arşiv adayları = güncel dönem başlamadan atanmış kitaplar",
              r.status_code == 200 and cand_ids == [old_b]
              and cd.get("period_started_on") == "2026-09-01",
              f"status={r.status_code} adaylar={cand_ids} {cd.get('period_started_on')}")

        # ---- 1. arşivle
        r = c.post(f"/api/v2/teacher/students/{sid}/books/archive",
                   json={"book_ids": [old_b], "archived": True})
        arch = r.json().get("data", {}) if r.text else {}
        rl = c.get(f"/api/v2/teacher/students/{sid}/books").json()
        ids_active = [i["book_id"] for i in rl.get("items", [])]
        check("1. arşivlenen kitap koç panelinde YOK + archived_count=1",
              r.status_code == 200 and arch.get("changed") == 1
              and old_b not in ids_active and new_b in ids_active
              and rl.get("archived_count") == 1,
              f"status={r.status_code} aktif={ids_active} arch={rl.get('archived_count')}")

        rl2 = c.get(
            f"/api/v2/teacher/students/{sid}/books?include_archived=true").json()
        arch_item = next(
            (i for i in rl2.get("items", []) if i["book_id"] == old_b), None)
        check("2. ?include_archived=true ile görünür + is_archived işaretli",
              arch_item is not None and arch_item.get("is_archived") is True
              and arch_item.get("archived_on"),
              f"{arch_item}")

        # ---- 3. VERİ KORUNDU MU (arşiv silmez)
        with SessionLocal() as db:
            task_alive = db.get(Task, s["task_id"]) is not None
            items = db.query(TaskBookItem).filter(
                TaskBookItem.task_id == s["task_id"]).count()
            sp = (db.query(SectionProgress)
                  .join(StudentBook,
                        SectionProgress.student_book_id == StudentBook.id)
                  .filter(StudentBook.student_id == sid,
                          SectionProgress.book_section_id == s["old_sec"])
                  .first())
            sb_alive = (db.query(StudentBook)
                        .filter(StudentBook.student_id == sid,
                                StudentBook.book_id == old_b).first() is not None)
        check("3. görev + kalem + sayaç + atama kaydı KORUNDU (arşiv silmez)",
              task_alive and items == 1 and sb_alive
              and sp is not None and sp.completed_count == 7,
              f"task={task_alive} kalem={items} sb={sb_alive} "
              f"completed={getattr(sp,'completed_count',None)}")

        # ---- 4. arşivli kitaba yeni görev atanamaz
        r = c.post(f"/api/v2/teacher/students/{sid}/tasks",
                   json={"date": date.today().isoformat(), "type": "test",
                         "title": "Arşivliye görev", "is_draft": False,
                         "items": [{"book_id": old_b, "section_id": s["old_sec"],
                                    "planned_count": 2}]})
        code = (r.json().get("detail", {}) or {}).get("code") if r.text else None
        check("4. arşivli kitaba yeni görev atanamaz → 422 book_archived",
              r.status_code == 422 and code == "book_archived",
              f"status={r.status_code} code={code}")

        # ---- 5. öğrenci Kitaplarım
        get_login_limiter().reset()
        cs = TestClient(app)
        r = cs.post("/api/v2/auth/login",
                    json={"email": f"{PFX}_s@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        sb_resp = cs.get("/api/v2/student/books").json()
        names = [
            b.get("book_name", "")
            for subj in sb_resp.get("subjects", [])
            for b in subj.get("books", [])
        ]
        check("5. öğrenci 'Kitaplarım'da arşivli kitap görünmez",
              not any("Gecen Yil" in n for n in names)
              and any("Bu Yil" in n for n in names),
              f"{names}")

        # ---- 8. bağımsız çalışma seçenekleri
        ss = cs.get("/api/v2/student/self-study/options").json()
        ss_ids = [b.get("book_id") for b in ss.get("books", [])]
        check("8. bağımsız çalışma seçeneklerinde arşivli kitap yok",
              old_b not in ss_ids and new_b in ss_ids, f"{ss_ids}")

        # ---- 6. görev ekleme kaynak seçicisi (hafta planı)
        r = c.get(f"/api/v2/teacher/students/{sid}/books-by-subject")
        if r.status_code != 200:
            r = c.get(f"/api/v2/teacher/weekly-plan/{sid}/books-by-subject")
        body = r.json() if r.text else {}
        raw = str(body)
        check("6. görev ekleme kaynak seçicisinde arşivli kitap yok",
              r.status_code == 200 and "Gecen Yil" not in raw
              and "Bu Yil" in raw,
              f"status={r.status_code} {raw[:180]}")

        # ---- 7. envanter/projeksiyon: arşivli kitap "kalan test"e girmez
        # (iki kitap 20+20=40 test; biri arşivli → 20 kalmalı, 7 çözülmüş düşmeli).
        # Geçen yılın kitabı bu yılın "sınava yetişir mi" hesabını şişirmemeli.
        from app.services.analytics import inventory_totals
        with SessionLocal() as db:
            total, completed, _res = inventory_totals(db, sid)
        check("7. envanter/projeksiyon arşivliyi saymaz (40→20 test, 7→0 çözüldü)",
              total == 20 and completed == 0,
              f"total={total} completed={completed}")

        # ---- 7b. müfredat kaynak tespiti: her iki kitap arşivliyse ders kaynaksız
        from app.services.curriculum_progress import _student_resource_subject_ids
        c.post(f"/api/v2/teacher/students/{sid}/books/archive",
               json={"book_ids": [new_b], "archived": True})
        with SessionLocal() as db:
            st_obj = db.get(User, sid)
            res_ids = _student_resource_subject_ids(db, st_obj)
        c.post(f"/api/v2/teacher/students/{sid}/books/archive",
               json={"book_ids": [new_b], "archived": False})
        check("7b. tüm kitapları arşivli ders 'kaynaklı' sayılmaz",
              s["subject_id"] not in res_ids,
              f"kaynak dersler={sorted(res_ids)} bizimki={s['subject_id']}")

        # ---- 9. idempotent
        r = c.post(f"/api/v2/teacher/students/{sid}/books/archive",
                   json={"book_ids": [old_b], "archived": True})
        check("9. idempotent — ikinci arşivleme changed=0",
              r.status_code == 200 and r.json()["data"]["changed"] == 0,
              f"{r.json().get('data')}")

        # ---- 10. arşivden çıkar
        r = c.post(f"/api/v2/teacher/students/{sid}/books/archive",
                   json={"book_ids": [old_b], "archived": False})
        rl3 = c.get(f"/api/v2/teacher/students/{sid}/books").json()
        back = [i["book_id"] for i in rl3.get("items", [])]
        check("10. arşivden çıkarınca kitap geri gelir",
              r.status_code == 200 and old_b in back
              and rl3.get("archived_count") == 0, f"{back}")

        # ---- 11. yeniden atama arşivden çıkarır
        c.post(f"/api/v2/teacher/students/{sid}/books/archive",
               json={"book_ids": [old_b], "archived": True})
        r = c.post(f"/api/v2/teacher/students/{sid}/books",
                   json={"book_id": old_b})
        rl4 = c.get(f"/api/v2/teacher/students/{sid}/books").json()
        check("11. arşivli kitabı yeniden atamak arşivden ÇIKARIR (409 değil)",
              r.status_code == 200
              and old_b in [i["book_id"] for i in rl4.get("items", [])],
              f"status={r.status_code} {r.text[:140]}")

        # ---- 13. kapılar
        r1 = c.post(
            f"/api/v2/teacher/students/{s['student2_id']}/books/archive",
            json={"book_ids": [old_b], "archived": True})
        r2 = c.post(f"/api/v2/teacher/students/{sid}/books/archive",
                    json={"book_ids": [], "archived": True})
        check("13. yabancı öğrenci 404 + boş liste 422",
              r1.status_code == 404 and r2.status_code == 422,
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
