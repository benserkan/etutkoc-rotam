"""Program bitmeden yeni program başlatma — erken bitirme akışı (Beril vakası, 2026-10-27).

Eski program bugünden 6 gün önce başlıyor, 2 gün sonra bitiyor. Yeni program bugün başlıyor →
kesilen 3 gün: bugün (başlanmamış, 3 test rezervli) · yarın (kısmi 1/3) · ertesi gün (tamamlanmış).
  1. Gerekçesiz/seçimsiz → 409 + kesilen gün/görev kırılımı; gerekçe kısa → 422
  2. AKTAR: eski program dün biter, tüm görevler yerinde, notuna gerekçe yazılır, tek "bu hafta"
  3. İADE: başlanmamış görev silinir + rezerv iade, kısmi kalır (kalan rezerv iade), tamamlanan kalır
  4. Aynı gün başlayan program kırpılamaz → 409 (trimmable=False)
  5. Eski kayıtlarda iki çakışık program olsa da tek "bu hafta" (en geç başlayan); görev çift sayılmaz
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

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (Book, BookSection, StudentBook, Subject, Task, TaskBookItem,  # noqa: E402
                        TaskStatus, TaskType, User, UserRole, WeeklyProgram)
from app.models.book import BookType  # noqa: E402
from app.models.progress import SectionProgress  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"wpt_{secrets.token_hex(3)}"
PWD = "Kirp!Program2345"
today = date.today()
passed = 0
failed: list[str] = []
uids: list[int] = []
subj_ids: list[int] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed(tag: str) -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}{tag}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                     role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add(coach); db.flush()
        st = User(email=f"{PFX}{tag}_s@test.invalid", password_hash=hash_password(PWD), full_name="Beril",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=8)
        db.add(st); db.flush()
        subj = Subject(name=f"{PFX}{tag} Mat", teacher_id=coach.id)
        db.add(subj); db.flush()
        book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX}{tag} SB", type=BookType.SORU_BANKASI)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Kesirler", test_count=50, order=1)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb); db.flush()
        old = WeeklyProgram(student_id=st.id, coach_id=coach.id,
                            start_date=today - timedelta(days=6), end_date=today + timedelta(days=2))
        db.add(old)

        def task(d, done, status, title):
            t = Task(student_id=st.id, date=d, title=title, type=TaskType.TEST, status=status,
                     is_draft=False, order=0,
                     book_items=[TaskBookItem(book_id=book.id, book_section_id=sec.id, planned_count=3,
                                              completed_count=done)])
            db.add(t); db.flush()
            return t.id

        ids = dict(
            untouched=task(today, 0, TaskStatus.PENDING, "Başlanmamış"),
            partial=task(today + timedelta(days=1), 1, TaskStatus.PARTIAL, "Kısmi"),
            done=task(today + timedelta(days=2), 3, TaskStatus.COMPLETED, "Tamam"),
            past=task(today - timedelta(days=2), 3, TaskStatus.COMPLETED, "Geçmiş"),
        )
        # rezerv: başlanmamış 3 + kısmi 2 = 5; çözülen 1 + 3 + 3 = 7
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=5,
                               completed_count=7))
        db.commit()
        uids.extend([coach.id, st.id])
        subj_ids.append(subj.id)
        return dict(sid=st.id, old=old.id, email=coach.email, sb=sb.id, sec=sec.id, **ids)


def client(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    assert c.post("/api/v2/auth/login", json={"email": email, "password": PWD}).status_code == 200
    return c


def body() -> dict:
    return {"start_date": today.isoformat(), "end_date": (today + timedelta(days=6)).isoformat()}


def main() -> int:
    try:
        # --- 1 + 2: AKTAR ---
        d = seed("a")
        c = client(d["email"])
        url = f"/api/v2/teacher/students/{d['sid']}/programs"
        r = c.post(url, json=body())
        ov = (r.json().get("detail") or {}).get("overlaps") or []
        o = ov[0] if ov else {}
        check("1a gerekçesiz → 409", r.status_code == 409, r.text[:200])
        check("1b kırpılır, dün biter", o.get("trimmable") and o.get("trim_to") == (today - timedelta(days=1)).isoformat(), str(o))
        check("1c kesilen 3 gün: 1 başlanmamış · 1 kısmi · 1 tamam · 5 test",
              (o.get("cut_days"), o.get("cut_untouched"), o.get("cut_partial"), o.get("cut_completed"),
               o.get("cut_release_tests")) == (3, 1, 1, 1, 5), str(o))
        r = c.post(url, json={**body(), "early_end_reason": "x", "early_end_mode": "transfer"})
        check("1d gerekçe kısa → 422", r.status_code == 422, r.text[:200])

        r = c.post(url, json={**body(), "early_end_reason": "Seans erkene alındı", "early_end_mode": "transfer"})
        check("2a aktar 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            old = db.get(WeeklyProgram, d["old"])
            check("2b eski program dün biter", old.end_date == today - timedelta(days=1), str(old.end_date))
            check("2c gerekçe eski programın notunda", "Seans erkene alındı" in (old.notes or ""), old.notes)
            check("2d görevler yerinde (4)", db.query(Task).filter(Task.student_id == d["sid"]).count() == 4)
            sp = db.query(SectionProgress).filter(SectionProgress.student_book_id == d["sb"]).first()
            check("2e rezerv değişmedi (5)", sp.reserved_count == 5, str(sp.reserved_count))
        lst = c.get(url).json()["items"]
        act = [p for p in lst if p["is_active"]]
        check("2f tek 'bu hafta' = yeni program", len(act) == 1 and act[0]["start_date"] == today.isoformat(), str(act))
        cnt = {p["start_date"]: p["task_count"] for p in lst}
        check("2g sayım: eski 1, yeni 3", cnt.get((today - timedelta(days=6)).isoformat()) == 1
              and cnt.get(today.isoformat()) == 3, str(cnt))

        r = c.post(url, json={"start_date": today.isoformat(), "end_date": (today + timedelta(days=3)).isoformat()})
        ov = (r.json().get("detail") or {}).get("overlaps") or []
        check("4 aynı gün başlayan kırpılamaz", r.status_code == 409 and ov and not ov[0]["trimmable"], str(ov))

        # --- 3: İADE ---
        d = seed("b")
        c = client(d["email"])
        url = f"/api/v2/teacher/students/{d['sid']}/programs"
        r = c.post(url, json={**body(), "early_end_reason": "Program erken bitti", "early_end_mode": "refund"})
        check("3a iade 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            check("3b başlanmamış görev silindi", db.get(Task, d["untouched"]) is None)
            pt = db.get(Task, d["partial"])
            check("3c kısmi görev kalır, kalan rezervi bırakılır",
                  pt is not None and pt.book_items[0].reservation_released_at is not None)
            check("3d tamamlanan + geçmiş görev kalır",
                  db.get(Task, d["done"]) is not None and db.get(Task, d["past"]) is not None)
            sp = db.query(SectionProgress).filter(SectionProgress.student_book_id == d["sb"]).first()
            check("3e rezerv 5 → 0, çözülen 7 aynı", sp.reserved_count == 0 and sp.completed_count == 7,
                  f"{sp.reserved_count}/{sp.completed_count}")

        # --- 5: eski kayıt — iki çakışık program ---
        with SessionLocal() as db:
            old = db.get(WeeklyProgram, d["old"]); old.end_date = today; db.commit()
        lst = c.get(url).json()["items"]
        act = [p for p in lst if p["is_active"]]
        check("5a çakışıkta tek 'bu hafta'", len(act) == 1 and act[0]["start_date"] == today.isoformat(), str(act))
        wk = c.get(f"/api/v2/teacher/students/{d['sid']}/week").json()
        check("5b hafta yanıtında tek 'bu hafta'", len([p for p in wk.get("programs", []) if p["is_active"]]) == 1)
        wk_old = c.get(f"/api/v2/teacher/students/{d['sid']}/week?program_id={d['old']}").json()
        days = [x["date"] for x in wk_old.get("days", [])]
        check("5c eski programın haftası kesilen günü göstermez",
              days and days[-1] == (today - timedelta(days=1)).isoformat(), str(days[-3:]))
        from app.routes.api_v2.weekly_plan import _resolve_window
        with SessionLocal() as db:
            rng = _resolve_window(db, d["sid"], d["old"], "")
        check("5d yayın aralığı kesilen günü kapsamaz", rng[1] == today - timedelta(days=1), str(rng))
        from app.services.weekly_progress import _weeks
        with SessionLocal() as db:
            ws = _weeks(db, db.get(User, d["sid"]), today)
            old_w = next((w for w in ws if w.program_id == d["old"]), None)
            new_w = next((w for w in ws if w.start == today), None)
            check("5h analiz: eski hafta dün biter, bugün yeni haftada",
                  old_w is not None and old_w.end == today - timedelta(days=1) and new_w is not None,
                  str([(w.program_id, w.start, w.end) for w in ws]))
        from scripts.fix_overlapping_programs import fix
        with SessionLocal() as db:
            fx, _ = fix(db, apply=False, student_id=d["sid"])
            check("5e düzeltme betiği kuru çalışmada bulur", len(fx) == 1 and fx[0]["program_id"] == d["old"], str(fx))
            fix(db, apply=True, student_id=d["sid"])
        with SessionLocal() as db:
            o = db.get(WeeklyProgram, d["old"])
            check("5f betik eski programı dün bitirir + not", o.end_date == today - timedelta(days=1)
                  and "otomatik" in (o.notes or ""), f"{o.end_date} {o.notes}")
            fx, _ = fix(db, apply=False, student_id=d["sid"])
            check("5g idempotent", fx == [], str(fx))
        # --- 6: DÜZENLEME ile bilinçli kesme (başlangıcı öne çekme) ---
        d = seed("c")
        c = client(d["email"])
        url = f"/api/v2/teacher/students/{d['sid']}/programs"
        r = c.post(url, json={"start_date": (today + timedelta(days=3)).isoformat(),
                              "end_date": (today + timedelta(days=9)).isoformat()})
        nid = r.json()["data"]["id"]
        eb = {"start_date": today.isoformat(), "end_date": (today + timedelta(days=9)).isoformat()}
        r = c.post(f"{url}/{nid}", json=eb)
        ov = (r.json().get("detail") or {}).get("overlaps") or []
        check("6a düzenlemede çakışma → 409 + kırpılabilir", r.status_code == 409 and ov and ov[0]["trimmable"], r.text[:200])
        r = c.post(f"{url}/{nid}", json={**eb, "early_end_reason": "Seans ertelendi", "early_end_mode": "transfer"})
        check("6b gerekçe + aktar ile kaydedilir", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            o = db.get(WeeklyProgram, d["old"])
            check("6c eski program dün biter + gerekçe notta",
                  o.end_date == today - timedelta(days=1) and "Seans ertelendi" in (o.notes or ""), f"{o.end_date} {o.notes}")
    finally:
        with SessionLocal() as db:
            tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(uids)).all()]
            if tids:
                db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
                db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
            sbs = [x.id for x in db.query(StudentBook).filter(StudentBook.student_id.in_(uids)).all()]
            if sbs:
                db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbs)).delete(synchronize_session=False)
                db.query(StudentBook).filter(StudentBook.id.in_(sbs)).delete(synchronize_session=False)
            bids = [b.id for b in db.query(Book).filter(Book.subject_id.in_(subj_ids or [-1])).all()]
            if bids:
                db.query(BookSection).filter(BookSection.book_id.in_(bids)).delete(synchronize_session=False)
                db.query(Book).filter(Book.id.in_(bids)).delete(synchronize_session=False)
            db.query(Subject).filter(Subject.id.in_(subj_ids or [-1])).delete(synchronize_session=False)
            db.query(WeeklyProgram).filter(WeeklyProgram.student_id.in_(uids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
            db.commit()
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
