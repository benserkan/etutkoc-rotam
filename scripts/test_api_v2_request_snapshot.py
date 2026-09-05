"""Talep detayında "Mevcut görev" donması — smoke (2026-09-05 saha hatası).

SAHA VAKASI (/teacher/requests/141): öğrenci "Kaynağı değiştir" talebi açtı
("orijinalden başlamak daha iyi olur"). Koç onayladıktan SONRA detay sayfasında
"Mevcut görev" ile "Önerilen değişiklik" AYNI görünüyordu → koç neyi onayladığını,
öğrencinin neyi değiştirmek istediğini göremiyordu.

Kök neden: `_apply_replace` eski kalemleri siler + başlığı yeniden yazar;
"Mevcut görev" bloğu CANLI görevden okunuyordu.

Senaryolar:
  1. Bekleyen talepte "Mevcut görev" CANLI görevi gösterir (eski davranış korunur)
  2. REPLACE onayı sonrası "Mevcut görev" TALEP ANINDAKİ kitabı gösterir
     (önerilenden FARKLI) — asıl saha hatası
  3. Başlık + tarih de talep anındaki hâli gösterir
  4. current_is_snapshot bayrağı UI'a gider
  5. CHANGE (sayı değişikliği) onayında da eski sayı korunur
  6. Reddedilen talepte de snapshot dondurulur
  7. Snapshot'ı olmayan ESKİ talepte canlı göreve düşülür (geriye uyum)
  8. Görev gerçekten değişti mi (onay uygulandı) — snapshot canlıyı maskelemesin
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
    RequestStatus,
    RequestType,
    SectionProgress,
    StudentBook,
    Subject,
    SuspiciousIp,
    Task,
    TaskBookItem,
    TaskRequest,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.security import hash_password

PFX = f"rs_{secrets.token_hex(3)}"
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
    tomorrow = date.today() + timedelta(days=1)
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Talep Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Talep Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=11)
        db.add(st)
        db.flush()
        subj = Subject(name=f"Talep Ders {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        # ESKİ kaynak (talepte "mevcut") + YENİ kaynak (öğrencinin istediği)
        old_book = Book(name=f"Acil TYT Matematik {PFX}", subject_id=subj.id,
                        teacher_id=coach.id, type=BookType.SORU_BANKASI)
        new_book = Book(name=f"Orijinal TYT Matematik {PFX}", subject_id=subj.id,
                        teacher_id=coach.id, type=BookType.SORU_BANKASI)
        db.add_all([old_book, new_book])
        db.flush()
        old_sec = BookSection(book_id=old_book.id, label="Eski Bölüm",
                              test_count=30, order=1)
        new_sec = BookSection(book_id=new_book.id, label="Basamak Kavramı",
                              test_count=30, order=1)
        db.add_all([old_sec, new_sec])
        db.flush()
        for b in (old_book, new_book):
            db.add(StudentBook(student_id=st.id, book_id=b.id))
        db.flush()
        sb_old = db.query(StudentBook).filter(
            StudentBook.student_id == st.id,
            StudentBook.book_id == old_book.id).first()
        db.add(SectionProgress(student_book_id=sb_old.id,
                               book_section_id=old_sec.id,
                               reserved_count=3, completed_count=0))

        def mk_task(title: str, book, sec, n: int) -> Task:
            t = Task(student_id=st.id, date=tomorrow, type=TaskType.TEST,
                     title=title, status=TaskStatus.PENDING, is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=sec.id,
                                planned_count=n, completed_count=0))
            db.flush()
            return t

        # REPLACE senaryosu (saha vakası) + CHANGE + REJECT + ESKİ talep
        t_rep = mk_task(f"Acil TYT Matematik {PFX} — Eski Bölüm: 3 test",
                        old_book, old_sec, 3)
        t_chg = mk_task(f"Acil TYT Matematik {PFX} — Eski Bölüm: 5 test",
                        old_book, old_sec, 5)
        t_rej = mk_task(f"Acil TYT Matematik {PFX} — Eski Bölüm: 2 test",
                        old_book, old_sec, 2)
        t_old = mk_task(f"Acil TYT Matematik {PFX} — Eski Bölüm: 4 test",
                        old_book, old_sec, 4)

        def mk_req(task, rtype, **kw) -> TaskRequest:
            r = TaskRequest(student_id=st.id, teacher_id=coach.id, task_id=task.id,
                            type=rtype, status=RequestStatus.PENDING,
                            message="orijinalden başlamak daha iyi olur", **kw)
            db.add(r)
            db.flush()
            return r

        r_rep = mk_req(t_rep, RequestType.REPLACE,
                       proposed_book_id=new_book.id,
                       proposed_section_id=new_sec.id, proposed_count=3)
        r_chg = mk_req(t_chg, RequestType.CHANGE, proposed_count=2)
        r_rej = mk_req(t_rej, RequestType.REPLACE,
                       proposed_book_id=new_book.id,
                       proposed_section_id=new_sec.id, proposed_count=2)
        # ESKİ talep: zaten onaylanmış ama snapshot'ı YOK (migration öncesi kayıt)
        r_old = mk_req(t_old, RequestType.CHANGE, proposed_count=4)
        r_old.status = RequestStatus.APPROVED
        db.commit()
        return {
            "coach_id": coach.id, "student_id": st.id, "subject_id": subj.id,
            "old_book": old_book.id, "new_book": new_book.id,
            "req_replace": r_rep.id, "req_change": r_chg.id,
            "req_reject": r_rej.id, "req_old": r_old.id,
            "task_replace": t_rep.id,
        }


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["student_id"]]
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id.in_(ids)))
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        sbids = [r.id for r in db.query(StudentBook).filter(
            StudentBook.student_id.in_(ids)).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.student_book_id.in_(sbids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
        for bid in (s["old_book"], s["new_book"]):
            db.execute(sa_delete(BookSection).where(BookSection.book_id == bid))
            db.execute(sa_delete(Book).where(Book.id == bid))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def main() -> int:
    # DEV HIZLANDIRMA: yanıt bildirimleri (e-posta comm_log + push) bu testin
    # konusu DEĞİL; dev SQLite tek-yazar olduğu için her yanıtta ~60 sn kilit
    # bekletiyorlar (prod PG etkilenmez). Bildirim yolu kendi testlerinde
    # kapsanıyor — burada susturulur.
    import app.services.request_service as _rs

    _rs._notify_resolved_safe = lambda *a, **k: None

    s = seed()
    print(f"\n=== Talep detayı snapshot (koç #{s['coach_id']}) ===\n")
    try:
        c = TestClient(app)
        from app.services.rate_limit import get_login_limiter
        get_login_limiter().reset()
        r = c.post("/api/v2/auth/login",
                   json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        rid = s["req_replace"]

        # ---- 1. BEKLEYEN talepte canlı görev
        d0 = c.get(f"/api/v2/teacher/requests/{rid}").json()
        names0 = [i["book_name"] for i in d0.get("current_items", [])]
        check("1. bekleyen talepte 'Mevcut görev' CANLI görevi gösterir",
              d0.get("current_is_snapshot") is False
              and any("Acil" in n for n in names0),
              f"snapshot={d0.get('current_is_snapshot')} {names0}")

        # ---- ONAYLA (saha akışı)
        ap = c.post(f"/api/v2/teacher/requests/{rid}/approve", json={})
        assert ap.status_code == 200, ap.text

        d1 = c.get(f"/api/v2/teacher/requests/{rid}").json()
        names1 = [i["book_name"] for i in d1.get("current_items", [])]
        check("2. ONAY SONRASI 'Mevcut görev' talep anındaki KİTABI gösterir",
              any("Acil" in n for n in names1)
              and not any("Orijinal" in n for n in names1),
              f"{names1}")

        check("3. başlık + tarih de talep anındaki hâli gösterir",
              "Acil" in (d1.get("task_title") or ""),
              f"{d1.get('task_title')}")

        check("4. current_is_snapshot bayrağı UI'a gidiyor",
              d1.get("current_is_snapshot") is True,
              f"{d1.get('current_is_snapshot')}")

        # önerilen HÂLÂ yeni kitabı gösteriyor → fark görünür
        check("4b. önerilen değişiklik yeni kitabı gösterir (fark görünür)",
              "Orijinal" in (d1.get("proposed_book_name") or ""),
              f"{d1.get('proposed_book_name')}")

        # ---- 8. görev gerçekten değişti mi (snapshot canlıyı maskelemesin)
        with SessionLocal() as db:
            t = db.get(Task, s["task_replace"])
            live_items = db.query(TaskBookItem).filter(
                TaskBookItem.task_id == t.id).all()
            live_books = {i.book_id for i in live_items}
        check("8. onay GERÇEKTEN uygulandı (canlı görev yeni kitaba geçti)",
              live_books == {s["new_book"]} and "Orijinal" in (t.title or ""),
              f"books={live_books} title={t.title}")

        # ---- 5. CHANGE onayında eski sayı korunur
        rc = s["req_change"]
        c.post(f"/api/v2/teacher/requests/{rc}/approve", json={})
        d2 = c.get(f"/api/v2/teacher/requests/{rc}").json()
        planned = [i["planned_count"] for i in d2.get("current_items", [])]
        check("5. CHANGE onayında 'Mevcut görev' ESKİ sayıyı korur (5 → önerilen 2)",
              planned == [5] and d2.get("proposed_count") == 2,
              f"planned={planned} proposed={d2.get('proposed_count')}")

        # ---- 6. reddedilen talepte de dondurulur
        rj = s["req_reject"]
        c.post(f"/api/v2/teacher/requests/{rj}/reject",
               json={"reason": "şimdilik devam"})
        d3 = c.get(f"/api/v2/teacher/requests/{rj}").json()
        check("6. reddedilen talepte de snapshot dondurulur",
              d3.get("current_is_snapshot") is True,
              f"{d3.get('current_is_snapshot')}")

        # ---- 7. eski kayıt (snapshot yok) → canlı göreve düşer
        d4 = c.get(f"/api/v2/teacher/requests/{s['req_old']}").json()
        names4 = [i["book_name"] for i in d4.get("current_items", [])]
        check("7. snapshot'ı olmayan ESKİ talepte canlı göreve düşülür",
              d4.get("current_is_snapshot") is False and len(names4) == 1,
              f"snapshot={d4.get('current_is_snapshot')} {names4}")
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
