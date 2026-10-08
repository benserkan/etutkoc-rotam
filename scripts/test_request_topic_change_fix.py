"""Talepte konu değişikliği kaybolması — 3 düzeltme (2026-10-08 saha).

Saha (Zeynep Ela #164): öğrenci 6 ve 7 Ekim'de "Sayıyı değiştir" talebiyle
3 → 3 istedi, konu değişikliğini yalnız mesaja yazdı ("karışım çözüyorum",
"grafik çözücem"). Koç onayladı ama program hiç değişmedi; görevler
tamamlanınca çözülenler YANLIŞ konuya yazıldı ve tamamlanmış görevde konu
değiştirilemiyordu (422 source_change_with_completed).

Senaryolar:
  1. Öğrenci aynı sayıyla "sayı değiştir" talebi gönderemez (Kaynağı değiştir'e yönlendirilir)
  2. Farklı sayıyla talep yine çalışır
  3. Koç listesinde/detayında aynı sayılı bekleyen talep `no_effect=True` işaretli
  4. Tamamlanmış görevde konu değişikliği move_completed'sız hâlâ 422 (eski sözleşme)
  5. move_completed=True → çözülenler eski bölümden düşer, yeni bölüme yazılır
  6. Yeni sayı çözülenin altındaysa çözülen yeni sayıya kırpılır (Grafik 3→2 vakası)
  7. Eski bölümdeki elle girilmiş (bağımsız çalışma) kısım korunur
  8. Yeni bölümde yer yoksa 422; allow_over_capacity ile uyarıyla taşınır
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
from app.models.task_request import RequestStatus, RequestType, TaskRequest
from app.services.security import hash_password

PFX = f"rtc_{secrets.token_hex(3)}"
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
    t = Task(student_id=st.id, date=day, type=TaskType.TEST, title="Görev",
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
                     full_name="Rtc Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Rtc Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        subj = Subject(name=f"Rtc Ders {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"Rtc Kitap {PFX}", subject_id=subj.id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        yuzde = BookSection(book_id=book.id, label="Yüzde", test_count=12, order=1)
        karisim = BookSection(book_id=book.id, label="Karışım", test_count=4, order=2)
        grafik = BookSection(book_id=book.id, label="Grafik", test_count=2, order=3)
        dar = BookSection(book_id=book.id, label="Dar", test_count=2, order=4)
        db.add_all([yuzde, karisim, grafik, dar])
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        done = TaskStatus.COMPLETED
        # 6 Ekim benzeri: Yüzde'ye girilmiş, Karışım çözülmüş (3/3)
        t1 = _task(db, st, book, yuzde, today - timedelta(days=2), 3, 3, done)
        # 7 Ekim benzeri: Karışım'a girilmiş, Grafik çözülmüş (3/3, Grafik 2 test)
        t2 = _task(db, st, book, karisim, today - timedelta(days=1), 3, 3, done)
        # kapasite senaryosu: Yüzde'de 3/3 tamamlanmış ikinci görev
        t3 = _task(db, st, book, yuzde, today - timedelta(days=3), 3, 3, done)
        # bekleyen görev (talep için)
        t4 = _task(db, st, book, yuzde, today + timedelta(days=1), 3, 0, TaskStatus.PENDING)
        # Yüzde: 1 elle (bağımsız) + 3 (t1) + 3 (t3) = 7 çözüldü, 3 rezerv (t4) → tam dolu
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=yuzde.id,
                               reserved_count=3, completed_count=7, manual_count=1))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=karisim.id,
                               reserved_count=0, completed_count=3))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=grafik.id,
                               reserved_count=0, completed_count=0))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=dar.id,
                               reserved_count=0, completed_count=0))
        # koçun gördüğü bekleyen aynı-sayı talebi
        req = TaskRequest(student_id=st.id, teacher_id=coach.id, task_id=t4.id,
                          type=RequestType.CHANGE, status=RequestStatus.PENDING,
                          proposed_count=3, message="karışım çözüyorum")
        db.add(req)
        db.commit()
        return {"coach_id": coach.id, "student_id": st.id, "book_id": book.id,
                "subject_id": subj.id, "sb_id": sb.id, "req_id": req.id,
                "yuzde": yuzde.id, "karisim": karisim.id, "grafik": grafik.id,
                "dar": dar.id, "t1": t1.id, "t2": t2.id, "t3": t3.id, "t4": t4.id}


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["student_id"]]
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id == s["student_id"]))
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id == s["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == s["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == s["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == s["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def comp(sb_id: int, sec_id: int) -> int:
    with SessionLocal() as db:
        sp = (db.query(SectionProgress)
              .filter(SectionProgress.student_book_id == sb_id,
                      SectionProgress.book_section_id == sec_id).first())
        return sp.completed_count if sp else -1


def item_of(task_id: int):
    with SessionLocal() as db:
        t = db.get(Task, task_id)
        it = t.book_items[0]
        return it.book_section_id, it.planned_count, it.completed_count, t.status, t.title


def login(email: str) -> TestClient:
    from app.services.rate_limit import get_login_limiter
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main() -> int:
    s = seed()
    sb = s["sb_id"]
    print(f"\n=== Talep konu değişikliği smoke (öğrenci #{s['student_id']}) ===\n")
    try:
        # Bekleyen talebi önce koç görsün (öğrenci tarafı ayrı görev ister)
        tc = login(f"{PFX}_t@test.invalid")
        r = tc.get("/api/v2/teacher/requests?status=pending")
        rows = [x for x in r.json().get("items", []) if x["id"] == s["req_id"]]
        check("3a. koç listesinde aynı-sayı talebi no_effect=True",
              r.status_code == 200 and rows and rows[0].get("no_effect") is True,
              f"{r.status_code} {rows}")
        r = tc.get(f"/api/v2/teacher/requests/{s['req_id']}")
        check("3b. koç detayında no_effect=True",
              r.status_code == 200 and r.json().get("no_effect") is True,
              f"{r.status_code} {r.text[:200]}")

        # Öğrenci: bekleyen talep olmayan yeni görev üzerinde dene
        with SessionLocal() as db:
            db.execute(sa_delete(TaskRequest).where(TaskRequest.id == s["req_id"]))
            db.commit()
        sc = login(f"{PFX}_s@test.invalid")
        r = sc.post(f"/api/v2/student/tasks/{s['t4']}/requests/change",
                    json={"proposed_count": 3, "message": "karışım çözüyorum"})
        check("1. aynı sayıyla 'sayı değiştir' reddedilir + Kaynağı değiştir'e yönlendirir",
              r.status_code >= 400 and "Kaynağı değiştir" in r.text,
              f"{r.status_code} {r.text[:200]}")
        r = sc.post(f"/api/v2/student/tasks/{s['t4']}/requests/change",
                    json={"proposed_count": 2})
        check("2. farklı sayıyla talep çalışır", r.status_code == 200,
              f"{r.status_code} {r.text[:200]}")
        r = tc.get("/api/v2/teacher/requests?status=pending")
        rows = [x for x in r.json().get("items", []) if x["task_id"] == s["t4"]]
        check("2b. gerçek değişiklikte no_effect=False",
              rows and rows[0].get("no_effect") is False, f"{rows}")

        def patch(task_id, sec, count, **extra):
            body = {"date": (date.today()).isoformat(), "scheduled_hour": None,
                    "type": "test", "book_id": s["book_id"], "section_id": sec,
                    "planned_count": count}
            with SessionLocal() as db:
                body["date"] = db.get(Task, task_id).date.isoformat()
            body.update(extra)
            return tc.patch(f"/api/v2/teacher/tasks/{task_id}/single-item", json=body)

        r = patch(s["t1"], s["karisim"], 3)
        check("4. move_completed'sız konu değişikliği hâlâ 422",
              r.status_code == 422 and "source_change_with_completed" in r.text,
              f"{r.status_code} {r.text[:200]}")

        # 6 Ekim: Yüzde → Karışım. Ama Karışım'da 3 zaten çözülmüş (t2'den),
        # 4 kapasite → önce 7 Ekim'i (t2) Grafik'e taşı.
        r = patch(s["t2"], s["grafik"], 2, move_completed=True)
        sec, planned, done, st_, title = item_of(s["t2"])
        check("6a. Karışım→Grafik (3→2): görev Grafik, 2/2 tamamlanmış",
              r.status_code == 200 and sec == s["grafik"] and planned == 2 and done == 2
              and st_ == TaskStatus.COMPLETED and "Grafik" in title,
              f"{r.status_code} {r.text[:200]} {(sec, planned, done, st_, title)}")
        check("6b. sayaçlar: Karışım 3→0, Grafik 0→2",
              comp(sb, s["karisim"]) == 0 and comp(sb, s["grafik"]) == 2,
              f"karışım={comp(sb, s['karisim'])} grafik={comp(sb, s['grafik'])}")

        r = patch(s["t1"], s["karisim"], 3, move_completed=True)
        sec, planned, done, st_, title = item_of(s["t1"])
        check("5a. Yüzde→Karışım: görev Karışım 3/3",
              r.status_code == 200 and sec == s["karisim"] and done == 3
              and st_ == TaskStatus.COMPLETED,
              f"{r.status_code} {r.text[:200]} {(sec, planned, done, st_)}")
        check("5b. sayaçlar: Yüzde 7→4, Karışım 0→3",
              comp(sb, s["yuzde"]) == 4 and comp(sb, s["karisim"]) == 3,
              f"yüzde={comp(sb, s['yuzde'])} karışım={comp(sb, s['karisim'])}")

        # 8. Dar bölüm 2 test; t3'ün 3 çözülmüşü sığmaz
        r = patch(s["t3"], s["dar"], 3, move_completed=True)
        check("8a. yeni bölümde yer yok → hata, sayaçlar değişmez",
              r.status_code >= 400 and comp(sb, s["dar"]) == 0 and comp(sb, s["yuzde"]) == 4,
              f"{r.status_code} dar={comp(sb, s['dar'])} yüzde={comp(sb, s['yuzde'])}")
        r = patch(s["t3"], s["dar"], 3, move_completed=True, allow_over_capacity=True)
        warns = r.json().get("warnings") if r.status_code == 200 else None
        check("8b. allow_over_capacity → taşındı + uyarı",
              r.status_code == 200 and comp(sb, s["dar"]) == 3 and bool(warns),
              f"{r.status_code} {r.text[:200]} dar={comp(sb, s['dar'])}")
        check("7. Yüzde'de elle girilen 1 test korunur (7 → 1)",
              comp(sb, s["yuzde"]) == 1, f"yüzde={comp(sb, s['yuzde'])}")
    finally:
        cleanup(s)

    print(f"\n{passed} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
