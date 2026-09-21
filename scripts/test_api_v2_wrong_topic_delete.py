"""Yanlış konuya girilen tamamlanmış görev — geri alma yolları (2026-09-20 saha).

Saha (Emir #113, 3D TYT Biyoloji): koç görevleri "Hücre Zarında Gerçekleşen
Olaylar"a girdi, öğrenci aslında "Hücre Organelleri"ni çözüp görevi tamamladı.
Koç görevi SİLDİ → silme completed'ı geri almadığından Hücre Zarı'nda 3 test
"çözüldü" kaldı; görev artık olmadığından geri alınamıyor, elle düşürme de
422 manual_reduce_exceeds veriyordu (manual_count=0) → ÇIKMAZ.

Senaryolar:
  1. Varsayılan silme çözülenleri KORUR (eski davranış — gerçekten çözülen test)
  2. ÇIKMAZIN ÇÖZÜMÜ: görevi silinmiş sahipsiz 'çözüldü' elle 0'a düşürülebilir
  3. Öğrenci çözmediği testi işaretlemiş: koç panelden gerçek sayıyı yazar →
     fark görevden geri alınır (görev silinmez, kısmi/bekliyor olur) + uyarı
  4. revert_completed=true → çözülenler de geri alınır, rezerv de sıfırlanır
  5. revert sonrası bölüm kapasitesi tam geri döner (yeniden atanabilir)
  6. Kısmi tamamlanmış görevde revert: çözülen + bekleyen rezerv birlikte iade
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    SectionProgress,
    SelfStudyEntry,
    StudentBook,
    Subject,
    SuspiciousIp,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.security import hash_password

PFX = f"wtd_{secrets.token_hex(3)}"
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


def _task(db, st, book, sec, day, planned, done, status):
    t = Task(student_id=st.id, date=day, type=TaskType.TEST, title="Yanlış konu",
             status=status, is_draft=False)
    db.add(t)
    db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id,
                        planned_count=planned, completed_count=done))
    return t


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Wtd Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Wtd Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=11)
        db.add(st)
        db.flush()
        subj = Subject(name=f"Wtd Ders {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"Wtd Kitap {PFX}", subject_id=subj.id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        secs = [BookSection(book_id=book.id, label=f"Bölüm {i}", test_count=7, order=i)
                for i in (1, 2, 3, 4, 5, 6)]
        db.add_all(secs)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        a, b, c_, d, e, f = secs
        done = TaskStatus.COMPLETED
        t_a = _task(db, st, book, a, today - timedelta(days=2), 3, 3, done)
        t_b = _task(db, st, book, b, today - timedelta(days=2), 3, 3, done)
        t_c = _task(db, st, book, c_, today - timedelta(days=1), 3, 3, done)
        for sec in (a, b, c_):
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                                   reserved_count=0, completed_count=3))
        # kısmi: 4 planlı, 1 çözülmüş → rezerv 3
        t_d = _task(db, st, book, d, today, 4, 1, TaskStatus.PENDING)
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=d.id,
                               reserved_count=3, completed_count=1))
        # SAHA-3 (Direnç): GEÇMİŞ haftada 2/2 'çözdüm' işaretli ama çözülmemiş
        t_e = _task(db, st, book, e, today - timedelta(days=20), 2, 2, done)
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=e.id,
                               reserved_count=0, completed_count=2))
        # göreve bağlı olmayan 'önceden çözülmüş' (baseline) 3 test
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=f.id,
                               reserved_count=0, completed_count=3, manual_count=3))
        db.commit()
        return {"e": e.id, "f": f.id, "t_e": t_e.id, "coach_id": coach.id, "student_id": st.id, "book_id": book.id,
                "subject_id": subj.id, "sb_id": sb.id,
                "a": a.id, "b": b.id, "c": c_.id, "d": d.id,
                "t_a": t_a.id, "t_b": t_b.id, "t_c": t_c.id, "t_d": t_d.id}


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["student_id"]]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(SelfStudyEntry).where(
            SelfStudyEntry.student_book_id == s["sb_id"]))
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id == s["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == s["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == s["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == s["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def counters(sb_id: int, sec_id: int) -> tuple[int, int]:
    with SessionLocal() as db:
        sp = (db.query(SectionProgress)
              .filter(SectionProgress.student_book_id == sb_id,
                      SectionProgress.book_section_id == sec_id).first())
        return (sp.reserved_count, sp.completed_count) if sp else (-1, -1)


def main() -> int:
    s = seed()
    sid, sb = s["student_id"], s["sb_id"]
    print(f"\n=== Yanlış konu görevi geri alma smoke (öğrenci #{sid}) ===\n")
    try:
        c = TestClient(app)
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        def set_abs(sec: int, n: int):
            return c.post(
                f"/api/v2/teacher/students/{sid}/books/{sb}/sections/{sec}/completed",
                json={"completed_count": n})

        r = c.delete(f"/api/v2/teacher/tasks/{s['t_a']}")
        check("1. varsayılan silme: çözülen 3 test KORUNUR",
              r.status_code == 200 and counters(sb, s["a"]) == (0, 3),
              f"{r.status_code} {counters(sb, s['a'])}")

        r = set_abs(s["a"], 0)
        check("2. SAHA: görevi silinmiş sahipsiz 'çözüldü' elle 0'a düşürülebiliyor",
              r.status_code == 200 and counters(sb, s["a"]) == (0, 0),
              f"{r.status_code} {r.text[:200]} {counters(sb, s['a'])}")

        # 3. SAHA-2: öğrenci 3 işaretlemiş ama 1 çözmüş → koç panelden 1 yazar
        r = set_abs(s["b"], 1)
        with SessionLocal() as db:
            tb = db.get(Task, s["t_b"])
            it = tb.book_items[0]
            t_state = (tb.status, it.completed_count, tb.completed_at)
        warns = (r.json().get("warnings") or []) if r.status_code == 200 else []
        check("3a. panelden 3→1: sayaç çözüldü 1, fark rezerve döndü (2)",
              r.status_code == 200 and counters(sb, s["b"]) == (2, 1),
              f"{r.status_code} {r.text[:200]} {counters(sb, s['b'])}")
        check("3b. görev SİLİNMEDİ: kısmi (1/3) olarak yeniden açıldı",
              t_state[0] == TaskStatus.PARTIAL and t_state[1] == 1 and t_state[2] is None,
              f"{t_state}")
        check("3c. koça hangi görevin düzeltildiği bildirildi (warnings)",
              len(warns) == 1 and "3→1" in warns[0], f"{warns}")
        r = set_abs(s["b"], 0)
        with SessionLocal() as db:
            st_b = db.get(Task, s["t_b"]).status
        check("3d. 1→0: görev tamamen 'bekliyor'a döndü, rezerv 3",
              r.status_code == 200 and counters(sb, s["b"]) == (3, 0)
              and st_b == TaskStatus.PENDING, f"{counters(sb, s['b'])} {st_b}")

        r = c.delete(f"/api/v2/teacher/tasks/{s['t_c']}?revert_completed=true")
        check("4. revert_completed: çözülenler geri alındı, rezerv 0",
              r.status_code == 200 and counters(sb, s["c"]) == (0, 0),
              f"{r.status_code} {counters(sb, s['c'])}")

        r = c.post(f"/api/v2/teacher/students/{sid}/tasks",
                   json={"date": date.today().isoformat(), "type": "test",
                         "title": "Yeniden", "is_draft": False,
                         "items": [{"book_id": s["book_id"], "section_id": s["c"],
                                    "planned_count": 7}]})
        check("5. revert sonrası bölümün 7 testi de yeniden atanabiliyor",
              r.status_code == 200, f"{r.status_code} {r.text[:160]}")

        r = c.delete(f"/api/v2/teacher/tasks/{s['t_d']}?revert_completed=true")
        check("6. kısmi görevde revert: çözülen 1 + bekleyen 3 birlikte iade",
              r.status_code == 200 and counters(sb, s["d"]) == (0, 0),
              f"{r.status_code} {counters(sb, s['d'])}")

        # 7-10. KOLTUK IZGARASI: yeşil koltuktan geri al (geçmiş hafta görevi)
        def grid_revert(sec, task_id, count):
            return c.post(
                f"/api/v2/teacher/students/{sid}/books/{s['book_id']}"
                f"/sections/{sec}/revert-completed",
                json={"task_id": task_id, "count": count})

        r = grid_revert(s["e"], s["t_e"], 1)
        with SessionLocal() as db:
            te = db.get(Task, s["t_e"])
            st_e, it_e = te.status, te.book_items[0].completed_count
        d_ = r.json().get("data", {}) if r.status_code == 200 else {}
        check("7. ızgara: 1 test geri alındı — görev SİLİNMEDİ, kısmi (1/2)",
              r.status_code == 200 and d_.get("reverted") == 1
              and st_e == TaskStatus.PARTIAL and it_e == 1,
              f"{r.status_code} {r.text[:200]} {st_e} {it_e}")
        check("8. geçmiş hafta: dönen rezerv ANINDA serbest → atanabilir 6/7",
              counters(sb, s["e"]) == (0, 1) and d_.get("section_remaining") == 6,
              f"{counters(sb, s['e'])} {d_}")
        r = grid_revert(s["e"], s["t_e"], 5)
        with SessionLocal() as db:
            st_e2 = db.get(Task, s["t_e"]).status
        check("9. kalan da geri alındı (count kırpılır): bekliyor, 7/7 atanabilir",
              r.status_code == 200 and r.json()["data"]["reverted"] == 1
              and st_e2 == TaskStatus.PENDING and counters(sb, s["e"]) == (0, 0),
              f"{r.status_code} {st_e2} {counters(sb, s['e'])}")
        r = grid_revert(s["e"], s["t_e"], 1)
        check("10. geri alınacak bir şey yok → 422 nothing_to_revert",
              r.status_code == 422, f"{r.status_code}")
        r = grid_revert(s["f"], None, 1)
        check("11. göreve bağlı olmayan koltuk (önceden çözülmüş) da geri alınır",
              r.status_code == 200 and counters(sb, s["f"]) == (0, 2),
              f"{r.status_code} {r.text[:160]} {counters(sb, s['f'])}")
        r = c.post(f"/api/v2/teacher/students/999999/books/{s['book_id']}"
                   f"/sections/{s['e']}/revert-completed",
                   json={"task_id": None, "count": 1})
        check("12. yabancı öğrenci 404", r.status_code == 404, f"{r.status_code}")
    finally:
        cleanup(s)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
