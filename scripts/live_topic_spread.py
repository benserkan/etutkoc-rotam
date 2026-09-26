"""İskelet F2-3 — çapa dersi + konuyu yay: CANLI E2E (dev sunucu + Playwright).

Zeynep Ela deseni: bugün dershanede Fizik (çapa), yarın Kimya (çapa); günlük
kapasite 10 test; yarın 5, bugün+3 9 test zaten yazılı.

   1. Gün kartında Fizik hayaleti "dershane/okul dersi" rozetli
   2. Şerit "Bugün Fizik dersinde hangi konu işlendi?" diye sorar
   3. Konu seçilince bugüne görev yazılır ve yayma önizlemesi KENDİLİĞİNDEN açılır
   4. Önizleme: yarın dershane payı yüzünden atlanır, +3 dolu → atlanır,
      +2 ve +4'e 3'er test; sonraki Fizik gününden önce biter
   5. Pencerede kırpılmış metin / taşma yok · koyu tema okunur
   6. "2 güne 6 test yaz" → +2 ve +4'e görev (taslak)
   7. Düzenleyicide satır "okul/dershane dersi" işaretli, gün kapasiteleri görünür

Ön koşul: backend :8081 + Next :3000.
  PYTHONPATH=. python scripts/live_topic_spread.py
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

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_live_contrast import measure  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lts_{secrets.token_hex(3)}"
PWD = "TopSpr!2345xy"
SHOT_DIR = os.path.join(os.getcwd(), ".shots")
passed = 0
failed: list[str] = []


def chk(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    T = date.today()
    D = [T + timedelta(days=i) for i in range(8)]
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Lts Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Lts Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        fiz = Subject(name=f"Lts Fizik {PFX}", teacher_id=coach.id, order=1)
        kim = Subject(name=f"Lts Kimya {PFX}", teacher_id=coach.id, order=2)
        mat = Subject(name=f"Lts Matematik {PFX}", teacher_id=coach.id, order=3)
        db.add_all([fiz, kim, mat])
        db.flush()
        tk = Topic(subject_id=fiz.id, name="Kuvvet ve Hareket", order=1, teacher_id=coach.id)
        tm = Topic(subject_id=kim.id, name="Mol Kavramı", order=1, teacher_id=coach.id)
        ts = Topic(subject_id=mat.id, name="Sayılar", order=1, teacher_id=coach.id)
        db.add_all([tk, tm, ts])
        db.flush()
        bf = Book(name=f"Fizik SB {PFX}", teacher_id=coach.id, subject_id=fiz.id, type=BookType.SORU_BANKASI)
        bk = Book(name=f"Kimya SB {PFX}", teacher_id=coach.id, subject_id=kim.id, type=BookType.SORU_BANKASI)
        bm = Book(name=f"Mat SB {PFX}", teacher_id=coach.id, subject_id=mat.id, type=BookType.SORU_BANKASI)
        db.add_all([bf, bk, bm])
        db.flush()
        sf = BookSection(book_id=bf.id, label="Kuvvet ve Hareket", order=1, test_count=9, topic_id=tk.id)
        sk_ = BookSection(book_id=bk.id, label="Mol Kavramı", order=1, test_count=10, topic_id=tm.id)
        sm = BookSection(book_id=bm.id, label="Sayılar", order=1, test_count=40, topic_id=ts.id)
        db.add_all([sf, sk_, sm])
        db.flush()
        sbs = {}
        for b in (bf, bk, bm):
            sbs[b.id] = StudentBook(student_id=st.id, book_id=b.id)
            db.add(sbs[b.id])
        db.flush()
        for d, n in ((D[1], 5), (D[3], 9)):
            t = Task(student_id=st.id, date=d, type=TaskType.TEST, title="x", is_draft=True)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=bm.id, book_section_id=sm.id, planned_count=n))
        for s, res in ((sf, 0), (sk_, 0), (sm, 14)):
            db.add(SectionProgress(student_book_id=sbs[s.book_id].id, book_section_id=s.id,
                                   completed_count=0, reserved_count=res))
        out = dict(coach=coach.id, st=st.id, fiz=fiz.id, kim=kim.id, mat=mat.id,
                   books=[bf.id, bk.id, bm.id], sbs=[x.id for x in sbs.values()],
                   topics=[tk.id, tm.id, ts.id], sf=sf.id, email=coach.email,
                   D=[d.isoformat() for d in D])
        db.commit()
        return out


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id == s["st"]))
        for x in db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id == s["st"]):
            db.delete(x)
        tids = [t.id for t in db.query(Task).filter(Task.student_id == s["st"])]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id == s["st"]))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(s["sbs"])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(s["sbs"])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(s["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(s["books"])))
        db.execute(sa_delete(Topic).where(Topic.id.in_(s["topics"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_([s["fiz"], s["kim"], s["mat"]])))
        db.execute(sa_delete(User).where(User.id.in_([s["st"], s["coach"]])))
        db.commit()


GH = '[data-section="day:skeleton-ghosts"]'
DLG = '[data-testid="spread-dialog"]'


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    s = seed()
    sid = s["st"]
    D = [date.fromisoformat(x) for x in s["D"]]
    print(f"\n=== Çapa + konuyu yay — canlı (öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)
            api = f"{BASE}/api/v2/teacher/students/{sid}/skeleton"
            base_row = {"period": None, "is_routine": False, "position": 0}
            r = pg.request.post(api, data={
                "slots": [
                    dict(base_row, weekday=D[0].weekday(), subject_id=s["fiz"], is_anchor=True, default_count=3),
                    dict(base_row, weekday=D[1].weekday(), subject_id=s["kim"], is_anchor=True, default_count=3),
                    dict(base_row, weekday=D[5].weekday(), subject_id=s["fiz"], is_anchor=True, default_count=3),
                ],
                "day_capacity": {str(i): 10 for i in range(7)},
            })
            assert r.ok, r.text()
            pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(800)

            # 1-2
            row = pg.locator(f'{GH} [data-testid="ghost-row"]', has_text="Lts Fizik").first
            row_txt = row.inner_text() if row.count() else ""
            chk("1. Fizik hayaleti 'dershane/okul dersi' rozetli", "dershane/okul dersi" in row_txt, row_txt)
            row.click()
            q_txt = pg.locator('[data-testid="anchor-question"]').inner_text()
            chk("2. şerit 'hangi konu işlendi?' diye sorar", "hangi konu işlendi" in q_txt, q_txt)

            # 3
            pg.locator('[data-testid="ghost-strip"] [data-testid="ghost-chip"]').first.click()
            dlg = pg.locator(DLG)
            dlg.wait_for(timeout=10000)
            with SessionLocal() as db:
                today_t = db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id).filter(
                    Task.student_id == sid, Task.date == D[0], TaskBookItem.book_section_id == s["sf"]).all()
            chk("3. bugüne Fizik görevi yazıldı + yayma penceresi kendiliğinden açıldı",
                len(today_t) == 1 and today_t[0].planned_count == 3 and dlg.count() == 1,
                f"{[(x.planned_count) for x in today_t]}")

            # 4
            pg.wait_for_timeout(1500)
            day_txt = dlg.locator('[data-testid="spread-day"]').all_inner_texts()
            dlg.locator("summary").click()
            full = dlg.inner_text()
            d2 = D[2].strftime("%d.%m")
            d4 = D[4].strftime("%d.%m")
            d1 = D[1].strftime("%d.%m")
            chk("4. yarın dershane payı yüzünden atlandı · +3 dolu · +2 ve +4'e 3'er · sonraki Fizik gününde durur",
                len(day_txt) == 2 and d2 in day_txt[0] and d4 in day_txt[1]
                and "dershane payı 3" in full and d1 in full and "bir sonraki" in full,
                f"{day_txt} | {full[-400:]}")

            # 5
            clip = pg.evaluate(
                """(sel) => { const s = document.querySelector(sel);
                  const els = [...s.querySelectorAll('*')].filter(e =>
                    getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1);
                  return {clipped: els.length, overflow: s.scrollWidth > s.clientWidth + 1}; }""", DLG)
            pg.screenshot(path=os.path.join(SHOT_DIR, "topic_spread.png"))
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(600)
            low = measure(pg, DLG, min_ratio=3.0)["bad"]
            pg.screenshot(path=os.path.join(SHOT_DIR, "topic_spread_dark.png"))
            pg.evaluate("() => document.documentElement.classList.remove('dark')")
            chk("5. pencerede kırpma/taşma yok · koyu tema okunur",
                clip["clipped"] == 0 and not clip["overflow"] and low == 0, f"{clip} bad={low}")

            # 6
            btn = dlg.get_by_role("button", name="2 güne 6 test yaz")
            btn_ok = btn.count() == 1
            btn.click()
            pg.wait_for_timeout(2500)
            with SessionLocal() as db:
                rows = db.query(Task, TaskBookItem).join(TaskBookItem, TaskBookItem.task_id == Task.id).filter(
                    Task.student_id == sid, TaskBookItem.book_section_id == s["sf"], Task.date > D[0]).all()
                got = sorted((t.date, i.planned_count, t.is_draft) for t, i in rows)
            chk("6. '2 güne 6 test yaz' → +2 ve +4'e 3'er (taslak)",
                btn_ok and got == [(D[2], 3, True), (D[4], 3, True)], str(got))

            # 7
            pg.get_by_role("button", name="İskelet", exact=True).click()
            ed = pg.locator('[role="dialog"]')
            ed.wait_for(timeout=10000)
            anchors = ed.locator('input[aria-label="Okul/dershane dersi"]').evaluate_all(
                "els => els.map(e => e.checked)")
            caps = ed.locator('[data-testid="capacity-input"]').evaluate_all("els => els.map(e => e.value)")
            chk("7. düzenleyicide çapa işaretleri + gün kapasiteleri",
                anchors.count(True) == 3 and caps == ["10"] * 7, f"{anchors} {caps}")
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
