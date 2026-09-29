"""Uyarı kuralları v2 + kanıt (2026-09-29, koç panosu "Uyarı Akışı" analizi).

Prod teşhisi: 15 uyarının 11'i "ders durgunluğu" idi; Taha aktif çalışırken
programlanmamış 6 ders için "58 gündür tamamlama yok" alıyordu, Boran'ın
verilip hiç yapılmayan AYT Kimya'sı (rezerv iade edilmiş) kaçıyordu.

  1. Son 14 günde hiç verilmemiş ders → subject_stale YOK
  2. ...o dersler öğrenci başına TEK subjects_unprogrammed satırında
  3. Yalnız ileriye programlanmış ders → ne durgunluk ne programda-yok
  4. Verilip hiç yapılmamış ders (rezerv iade) → subject_untouched VAR (Boran)
  5. Verilip kısmen yapılmış, son çözüm 3 gün önce → uyarı YOK
  6. Verilmiş, son çözüm 10 gün önce → subject_stale VAR
  7. Haftalık tempo taslak görevleri SAYMAZ
  8. Her üretilen uyarı kanıt satırı taşır
  9. Uyarı akışı ucu kanıt + bağlantı döner
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.services import analytics
from app.services.security import hash_password

PFX = f"wr2_{secrets.token_hex(3)}"
PWD = "WarnRules!234"
now = datetime.now(timezone.utc)
today = date.today()
uids: list[int] = []
book_ids: list[int] = []
subj_ids: list[int] = []
coach_id = 0
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def mk_student(tag):
    with SessionLocal() as db:
        s = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD),
                 full_name=f"{PFX} {tag}", role=UserRole.STUDENT, teacher_id=coach_id,
                 grade_level=12, is_active=True, created_at=now - timedelta(days=40),
                 last_login_at=now, last_seen_at=now)
        db.add(s)
        db.commit()
        uids.append(s.id)
        return s.id


def mk_book(name, tests=40, btype=BookType.SORU_BANKASI):
    with SessionLocal() as db:
        subj = Subject(name=f"{PFX} {name}", teacher_id=coach_id)
        db.add(subj)
        db.flush()
        b = Book(teacher_id=coach_id, subject_id=subj.id, name=f"{PFX} {name} SB", type=btype)
        db.add(b)
        db.flush()
        sec = BookSection(book_id=b.id, label="Ü1", test_count=tests)
        db.add(sec)
        db.commit()
        subj_ids.append(subj.id)
        book_ids.append(b.id)
        return subj.id, b.id, sec.id


def assign(sid, bid, secid, completed=0):
    with SessionLocal() as db:
        sb = StudentBook(student_id=sid, book_id=bid)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=secid,
                               reserved_count=0, completed_count=completed))
        db.commit()


def task(sid, day, bid, secid, planned, completed, *, draft=False):
    with SessionLocal() as db:
        done = completed >= planned
        t = Task(student_id=sid, date=day, type=TaskType.TEST, title="T", is_draft=draft,
                 published_at=None if draft else now,
                 status=TaskStatus.COMPLETED if done else TaskStatus.PENDING,
                 completed_at=now if done else None)
        db.add(t)
        db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=bid, book_section_id=secid,
                            planned_count=planned, completed_count=completed))
        db.commit()


def warns(sid):
    with SessionLocal() as db:
        s = db.get(User, sid)
        proj = analytics.compute_projection(db, s, today, window_days=28, buffer_days=5)
        from app.services.student_flags import evaluate_flags
        _r = evaluate_flags(db, s, today, proj)
        return {w.code: w for w in (_r.primary + _r.secondary + _r.good)}


def cleanup():
    with SessionLocal() as db:
        sids = [u for u in uids if u != coach_id]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(sids or [0]))]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids or [0])))
        db.execute(sa_delete(Task).where(Task.id.in_(tids or [0])))
        sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids or [0]))]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids or [0])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(book_ids or [0])))
        db.execute(sa_delete(Book).where(Book.id.in_(book_ids or [0])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(subj_ids or [0])))
        db.execute(sa_delete(User).where(User.id.in_(uids or [0])))
        db.commit()


def main() -> int:
    global coach_id
    with SessionLocal() as db:
        c = User(email=f"{PFX}_coach@test.invalid", password_hash=hash_password(PWD),
                 full_name=f"{PFX} coach", role=UserRole.TEACHER, is_active=True,
                 plan="solo_unlimited", subscription_status="active")
        db.add(c)
        db.commit()
        coach_id = c.id
    uids.append(coach_id)
    try:
        # Taha deseni: aktif (Mat her gün çözülüyor), Türkçe hiç programda yok,
        # AYT Fizik yalnız ileriye programlanmış.
        taha = mk_student("taha")
        m_sub, m_b, m_s = mk_book("Mat")
        t_sub, t_b, t_s = mk_book("Turkce")
        f_sub, f_b, f_s = mk_book("AytFizik")
        for b, s_ in ((m_b, m_s), (t_b, t_s), (f_b, f_s)):
            assign(taha, b, s_, completed=5 if b != f_b else 0)
        for k in range(1, 7):
            task(taha, today - timedelta(days=k), m_b, m_s, 2, 2)
        task(taha, today + timedelta(days=1), f_b, f_s, 3, 0)
        w = warns(taha)
        chk("1 programlanmamış ders durgunluk ÜRETMEZ",
            not any(c.startswith("subject_stale") or c.startswith("subject_untouched") for c in w), str(list(w)))
        up = w.get("subjects_unprogrammed")
        chk("2 programda-yok tek satır ve Türkçe'yi söyler",
            up is not None and "Turkce" in up.detail and "AytFizik" not in up.detail,
            up.detail if up else str(list(w)))
        chk("3 ileriye programlanmış ders listede yok", up is not None and "AytFizik" not in up.detail)

        # Boran deseni: AYT Kimya 4 görev verildi, hiç yapılmadı (rezerv iade — 0)
        boran = mk_student("boran")
        k_sub, k_b, k_s = mk_book("AytKimya")
        assign(boran, k_b, k_s)
        for k in (2, 4, 6, 8):
            task(boran, today - timedelta(days=k), k_b, k_s, 2, 0)
        w = warns(boran)
        ut = w.get(f"subject_avoid_{k_sub}")
        chk("4 verilip hiç yapılmayan ders yakalanır (rezerv iadeli) — kaçınma bayrağı", ut is not None, str(list(w)))
        chk("4b kanıt: 0/4 görev (%0)",
            ut is not None and any(v == "0/4 görev (%0)" for _, v in ut.evidence), str(ut.evidence if ut else None))

        chk("4c aynı olgu tek uyarı: boş gün serisi kırmızı, tamamlama ek sinyale iner",
            "empty_streak" in w and w["empty_streak"].level == "red"
            and "inactive_3d" not in w and "weekly_zero" not in w, str(list(w)))

        # Kısmen yapılmış, son çözüm 3 gün önce → uyarı yok
        s5 = mk_student("recent")
        a_sub, a_b, a_s = mk_book("Bio")
        assign(s5, a_b, a_s)
        task(s5, today - timedelta(days=3), a_b, a_s, 3, 3)
        task(s5, today - timedelta(days=5), a_b, a_s, 3, 0)
        w = warns(s5)
        chk("5 son çözüm 3 gün önce → durgunluk yok", f"subject_stale_{a_sub}" not in w, str(list(w)))

        # Son çözüm 10 gün önce, son 14 günde verilen var → durgunluk
        s6 = mk_student("stale")
        g_sub, g_b, g_s = mk_book("Geo")
        assign(s6, g_b, g_s)
        task(s6, today - timedelta(days=10), g_b, g_s, 2, 2)
        task(s6, today - timedelta(days=4), g_b, g_s, 3, 0)
        w = warns(s6)
        st = w.get(f"subject_stale_{g_sub}")
        chk("6 son çözüm 10 gün önce → durgunluk", st is not None, str(list(w)))
        chk("6b detay yapılmayan sayıyı söyler", st is not None and "3 tanesi yapılmadı" in st.detail,
            st.detail if st else "")

        # Taslak görevler haftalık tempoya girmez
        s7 = mk_student("draft")
        d_sub, d_b, d_s = mk_book("Kim")
        assign(s7, d_b, d_s)
        for k in (1, 2, 3):
            task(s7, today - timedelta(days=k), d_b, d_s, 2, 2)
        for k in (1, 2, 3, 4, 5):
            task(s7, today - timedelta(days=k), d_b, d_s, 2, 0, draft=True)
        w = warns(s7)
        chk("7 taslaklar haftalık tempoyu düşürmez",
            "completion_low" not in w and "empty_streak" not in w, str(list(w)))

        # Haftalık tempo düşük + kanıt
        s8 = mk_student("weekly")
        e_sub, e_b, e_s = mk_book("Fiz")
        assign(s8, e_b, e_s)
        task(s8, today - timedelta(days=1), e_b, e_s, 2, 2)
        for k in (2, 3, 4, 5):
            task(s8, today - timedelta(days=k), e_b, e_s, 2, 0)
        w = warns(s8)
        wm = w.get("completion_low")
        chk("8 haftalık tempo: 5 görevin 1'i", wm is not None and "5 görevin 1 tanesi" in wm.detail,
            wm.detail if wm else str(list(w)))
        all_w = [x for sid in (taha, boran, s6, s8) for x in warns(sid).values()]
        chk("8b her uyarı kanıt taşır", all_w and all(x.evidence for x in all_w),
            str([x.code for x in all_w if not x.evidence]))

        # (Genel projeksiyon uyarısı 2026-09-29'da ders bazlı exam_readiness'a
        # taşındı — test_exam_readiness.py.)

        # Uç: kanıt + bağlantı
        cl = TestClient(app)
        r = cl.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWD})
        r = cl.get("/api/v2/teacher/dashboard/warnings-feed")
        rows = r.json().get("rows", []) if r.status_code == 200 else []
        br = [x for x in rows if x["student_id"] == boran]
        chk("9 akış kanıt + bağlantı döner",
            br and br[0]["evidence"] and br[0]["link"].startswith(f"/teacher/students/{boran}/"),
            r.text[:300])
    finally:
        cleanup()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
