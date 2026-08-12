"""POST /teacher/tasks/{id}/spread smoke — rutin görev dağıtımı (2026-08-12).

Senaryolar (14):
   1. 6 güne yay (devam AÇIK): kaynak bitene dek gün gün rezerv; 5 gün oluşur,
      6. gün source_exhausted + uyarı
   2. ...bölüm-devam kanıtı: bir kopya İKİ bölümden kalem taşır
   3. ...rezerv muhasebesi: 3 bölümün tamamı rezerve edildi
   4. ...kopyalar TASLAK
   5. Mükerrer koruması: aynı yayılım tekrar → created=0
   6. Devam KAPALI: yalnız kaynak bölüm; kısmi gün partial'da + uyarı
   7. Etkinlik görevi yayılır (kalemsiz kopyalar)
   8. Etkinlik mükerrer: başlık+tip eşleşmesi → duplicate
   9. Kitapsız deneme kalemi aynen kopyalanır (rezervsiz)
  10. Geçmiş tarih → past_date; bozuk tarih → invalid_date
  11. Periyot override: period="noon" ile kopyalar noon
  12. Yabancı öğretmenin görevi → 404
  13. Kaynak gün listede → sessizce atlanır (kendi üstüne kopya yok)
  14. invalidate prefix'leri hafta+gün anahtarlarını taşır
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
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"spr_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
T1 = f"{PFX}_t1@test.invalid"
T2 = f"{PFX}_t2@test.invalid"
S1 = f"{PFX}_s1@test.invalid"
S2 = f"{PFX}_s2@test.invalid"

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


def _seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        t1 = User(email=T1, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Koç1", role=UserRole.TEACHER, is_active=True)
        t2 = User(email=T2, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([t1, t2])
        db.flush()
        s1 = User(email=S1, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Öğr1", role=UserRole.STUDENT,
                  teacher_id=t1.id, is_active=True, grade_level=8)
        s2 = User(email=S2, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Öğr2", role=UserRole.STUDENT,
                  teacher_id=t1.id, is_active=True, grade_level=8)
        db.add_all([s1, s2])
        db.flush()
        subj = Subject(name=f"{PFX} Matematik", teacher_id=t1.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"{PFX} Soru Bankası", subject_id=subj.id,
                    teacher_id=t1.id, type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        secs = []
        for i, cnt in enumerate((5, 4, 3), start=1):
            sec = BookSection(book_id=book.id, label=f"Bölüm {i}",
                              order=i, test_count=cnt)
            db.add(sec)
            db.flush()
            secs.append(sec.id)
        sb_map = {}
        for st in (s1, s2):
            sb = StudentBook(student_id=st.id, book_id=book.id)
            db.add(sb)
            db.flush()
            sb_map[st.id] = sb.id

        def mk_task(student, sec_id, planned, title="Kaynak Görev"):
            t = Task(student_id=student.id, title=title, type=TaskType.TEST,
                     date=today, status=TaskStatus.PENDING, is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=sec_id, planned_count=planned))
            sb_id = sb_map[student.id]
            prog = (db.query(SectionProgress)
                    .filter(SectionProgress.student_book_id == sb_id,
                            SectionProgress.book_section_id == sec_id).first())
            if prog is None:
                prog = SectionProgress(student_book_id=sb_id,
                                       book_section_id=sec_id,
                                       reserved_count=0, completed_count=0)
                db.add(prog)
            prog.reserved_count += planned
            db.flush()
            return t.id

        src1 = mk_task(s1, secs[0], 2)                      # s1: bölüm1 ×2
        src2 = mk_task(s2, secs[0], 2, title="Kaynak2")     # s2: bölüm1 ×2 (devam-kapalı testi)
        # etkinlik görevi (s1)
        act = Task(student_id=s1.id, title="Matematik · Paragraf çöz",
                   type=TaskType.OTHER, date=today, status=TaskStatus.PENDING,
                   is_draft=False, period="morning")
        db.add(act)
        db.flush()
        # kitapsız deneme görevi (s2)
        dt = Task(student_id=s2.id, title="TYT Genel Deneme",
                  type=TaskType.OTHER, date=today, status=TaskStatus.PENDING,
                  is_draft=False)
        db.add(dt)
        db.flush()
        db.add(TaskBookItem(task_id=dt.id, book_id=None, book_section_id=None,
                            label="TYT Genel Deneme", planned_count=120))
        db.commit()
        return {"t1": t1.id, "t2": t2.id, "s1": s1.id, "s2": s2.id,
                "secs": secs, "src1": src1, "src2": src2,
                "act": act.id, "deneme": dt.id, "today": today}


def _cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uids = [ids["t1"], ids["t2"], ids["s1"], ids["s2"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uids)).all()]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        sb_ids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(uids)).all()]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sb_ids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sb_ids)))
        db.execute(sa_delete(BookSection).where(BookSection.id.in_(ids["secs"])))
        db.execute(sa_delete(Book).where(Book.teacher_id.in_(uids)))
        db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def main() -> int:
    ids = _seed()
    client = TestClient(app)
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": T1, "password": PASSWORD})
    assert r.status_code == 200, f"login {r.status_code}"

    today = ids["today"]
    days = [(today + timedelta(days=i)).isoformat() for i in range(1, 7)]

    try:
        # ---- 1-4: 6 güne yay, devam AÇIK
        r = client.post(f"/api/v2/teacher/tasks/{ids['src1']}/spread",
                        json={"dates": days, "continue_sections": True})
        check("0. spread 200", r.status_code == 200, str(r.status_code)[:200])
        d = r.json()["data"]
        check("1. 5 gün oluştu + 6. gün source_exhausted + uyarı",
              len(d["created"]) == 5
              and any(x["reason"] == "source_exhausted" for x in d["skipped"])
              and d["warning"],
              str(d)[:300])
        with SessionLocal() as db:
            new_tasks = (db.query(Task)
                         .filter(Task.student_id == ids["s1"],
                                 Task.date > today, Task.type == TaskType.TEST)
                         .all())
            multi = [t for t in new_tasks if len(t.book_items) >= 2]
            check("2. bölüm-devam: en az bir kopya iki bölümden kalem taşır",
                  len(multi) >= 1, f"{[(len(t.book_items)) for t in new_tasks]}")
            sb1 = db.query(StudentBook).filter(StudentBook.student_id == ids["s1"]).first()
            progs = {p.book_section_id: p for p in
                     db.query(SectionProgress).filter(SectionProgress.student_book_id == sb1.id).all()}
            fully = all(
                (progs.get(sec_id).reserved_count if progs.get(sec_id) else 0) == cnt
                for sec_id, cnt in zip(ids["secs"], (5, 4, 3))
            )
            check("3. rezerv muhasebesi: 3 bölüm tamamen rezerve", fully,
                  f"{[(k, v.reserved_count) for k, v in progs.items()]}")
            check("4. kopyalar taslak", all(t.is_draft for t in new_tasks),
                  f"{[(t.id, t.is_draft) for t in new_tasks]}")

        # ---- 5: mükerrer
        r = client.post(f"/api/v2/teacher/tasks/{ids['src1']}/spread",
                        json={"dates": days, "continue_sections": True})
        d = r.json()["data"]
        check("5. tekrar yayılım → created=0 (duplicate/exhausted)",
              len(d["created"]) == 0, str(d)[:200])

        # ---- 6: devam KAPALI (s2 — bölüm1 kalan 5-2-2(src1 s1'de! s2 ayrı) )
        # s2'nin bölüm1 rezervi yalnız kendi kaynak görevi (2) → kalan 3.
        r = client.post(f"/api/v2/teacher/tasks/{ids['src2']}/spread",
                        json={"dates": days[:3], "continue_sections": False})
        d = r.json()["data"]
        check("6. devam kapalı: 2 gün oluştu (biri partial) + 3. gün exhausted",
              len(d["created"]) == 2 and len(d["partial"]) == 1
              and any(x["reason"] == "source_exhausted" for x in d["skipped"])
              and d["warning"],
              str(d)[:300])

        # ---- 7-8: etkinlik
        r = client.post(f"/api/v2/teacher/tasks/{ids['act']}/spread",
                        json={"dates": days[:3]})
        d = r.json()["data"]
        check("7. etkinlik 3 güne yayıldı", len(d["created"]) == 3, str(d)[:200])
        with SessionLocal() as db:
            acts = (db.query(Task)
                    .filter(Task.student_id == ids["s1"], Task.date > today,
                            Task.title == "Matematik · Paragraf çöz").all())
            check("7b. kopyalar periyodu korur (morning)",
                  len(acts) == 3 and all(t.period == "morning" for t in acts),
                  f"{[(t.period,) for t in acts]}")
        r = client.post(f"/api/v2/teacher/tasks/{ids['act']}/spread",
                        json={"dates": days[:3]})
        d = r.json()["data"]
        check("8. etkinlik mükerrer → duplicate",
              len(d["created"]) == 0
              and all(x["reason"] == "duplicate" for x in d["skipped"]),
              str(d)[:200])

        # ---- 9: kitapsız deneme
        r = client.post(f"/api/v2/teacher/tasks/{ids['deneme']}/spread",
                        json={"dates": [days[0]]})
        d = r.json()["data"]
        with SessionLocal() as db:
            cp = (db.query(Task)
                  .filter(Task.student_id == ids["s2"],
                          Task.date == date.fromisoformat(days[0]),
                          Task.title == "TYT Genel Deneme").first())
            ok = (cp is not None and len(cp.book_items) == 1
                  and cp.book_items[0].book_id is None
                  and cp.book_items[0].planned_count == 120)
            check("9. kitapsız deneme aynen kopyalandı", len(d["created"]) == 1 and ok,
                  str(d)[:200])

        # ---- 10: geçmiş + bozuk tarih
        r = client.post(f"/api/v2/teacher/tasks/{ids['act']}/spread",
                        json={"dates": [(today - timedelta(days=2)).isoformat(), "bozuk-tarih"]})
        d = r.json()["data"]
        reasons = {x["reason"] for x in d["skipped"]}
        check("10. past_date + invalid_date", reasons == {"past_date", "invalid_date"},
              str(d)[:200])

        # ---- 11: periyot override
        far = (today + timedelta(days=10)).isoformat()
        r = client.post(f"/api/v2/teacher/tasks/{ids['act']}/spread",
                        json={"dates": [far], "period": "noon"})
        with SessionLocal() as db:
            cp = (db.query(Task)
                  .filter(Task.student_id == ids["s1"],
                          Task.date == date.fromisoformat(far)).first())
            check("11. period override → noon",
                  cp is not None and cp.period == "noon",
                  f"{cp.period if cp else None}")

        # ---- 12: yabancı görev 404
        get_login_limiter().reset()
        r = client.post("/api/v2/auth/login", json={"email": T2, "password": PASSWORD})
        assert r.status_code == 200
        r = client.post(f"/api/v2/teacher/tasks/{ids['src1']}/spread",
                        json={"dates": [days[0]]})
        check("12. yabancı öğretmenin görevi 404", r.status_code == 404, str(r.status_code))

        # ---- 13-14: kaynak gün atlanır + invalidate
        get_login_limiter().reset()
        r = client.post("/api/v2/auth/login", json={"email": T1, "password": PASSWORD})
        r = client.post(f"/api/v2/teacher/tasks/{ids['act']}/spread",
                        json={"dates": [today.isoformat()]})
        d = r.json()["data"]
        check("13. kaynak gün sessizce atlanır (created=0, hata yok)",
              r.status_code == 200 and len(d["created"]) == 0 and len(d["skipped"]) == 0,
              str(d)[:200])
        inv = r.json().get("invalidate") or []
        check("14. invalidate hafta/gün anahtarları taşır",
              any("students" in x for x in inv), str(inv)[:200])
    finally:
        _cleanup(ids)

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
