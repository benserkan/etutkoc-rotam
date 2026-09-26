"""Haftalık İskelet (F1b) — CANLI E2E (dev sunucu + Playwright).

Koç akışı gerçek tarayıcıda:
   1. Başlıkta "İskelet oluştur" → düzenleyici açılır
   2. Bugünün hafta gününe 3 satır eklenir (Mat sabah · Mat akşam · Fizik rutin) → kaydet
   3. Hafta Izgarası'nda bugünün sütununda 3 kesikli "öneri"
   4. Gün kartında "İskeletten öneriler" + 3 hayalet satır + "Rutinleri onayla (1)"
   5. Hayalete tıkla → ŞERİT satırın altında; ilk çip "devam" + gerekçe
      "dünün devamı"; bilgi rozeti (denemede N yanlış) dolgulu
   6. Şeritte kırpılmış (ellipsis) metin yok, yatay taşma yok
   7. Çipe tıkla → görev yazıldı (DB) + periyot iskeletten · hayalet 3→2
   8. × kaldır → hayalet 2→1 (DB'de dismissed kaydı)
   9. "Rutinleri onayla" → Fizik görevi yazıldı · hayalet kalmadı
  10. Koyu tema: hayalet satır/şerit metinleri okunur (kontrast ≥ 3.0)

Ön koşul: backend :8081 + Next :3000. Kullanım:
  PYTHONPATH=. python scripts/live_weekly_skeleton.py
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
    ExamResult,
    ExamSection,
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
from app.models.exam_result import ExamResultQuestion
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_live_contrast import measure  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lsk_{secrets.token_hex(3)}"
PWD = "Skel!Live2345xy"
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
    today = date.today()
    d0 = today - timedelta(days=1)
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Lsk Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Lsk Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        mat = Subject(name=f"Lsk Matematik {PFX}", teacher_id=coach.id, order=1)
        fiz = Subject(name=f"Lsk Fizik {PFX}", teacher_id=coach.id, order=2)
        db.add_all([mat, fiz])
        db.flush()
        tp = {}
        for i, n in enumerate(["Üslü İfadeler", "Köklü İfadeler", "Çarpanlara Ayırma",
                               "Oran Orantı"], start=1):
            tp[n] = Topic(subject_id=mat.id, name=n, order=i, teacher_id=coach.id)
            db.add(tp[n])
        tf = Topic(subject_id=fiz.id, name="Kuvvet ve Hareket", order=1, teacher_id=coach.id)
        db.add(tf)
        db.flush()
        ba = Book(name=f"Lsk Matematik Soru Bankası {PFX}", teacher_id=coach.id,
                  subject_id=mat.id, type=BookType.SORU_BANKASI)
        bf = Book(name=f"Lsk Fizik Soru Bankası {PFX}", teacher_id=coach.id,
                  subject_id=fiz.id, type=BookType.SORU_BANKASI)
        db.add_all([ba, bf])
        db.flush()
        secs = {}
        sbs = {}
        spec = [("s1", ba, "Üslü İfadeler", 10, 0, 3), ("s2", ba, "Köklü İfadeler", 4, 4, 0),
                ("s3", ba, "Çarpanlara Ayırma", 10, 0, 0), ("s4", ba, "Oran Orantı", 10, 0, 0),
                ("f1", bf, "Kuvvet ve Hareket", 10, 0, 0)]
        for key, book, tname, total, comp, res in spec:
            topic = tf if book is bf else tp[tname]
            sec = BookSection(book_id=book.id, label=f"{tname} Testleri",
                              order=len([k for k in secs if secs[k].book_id == book.id]) + 1,
                              test_count=total, topic_id=topic.id)
            db.add(sec)
            db.flush()
            if book.id not in sbs:
                sbs[book.id] = StudentBook(student_id=st.id, book_id=book.id)
                db.add(sbs[book.id])
                db.flush()
            db.add(SectionProgress(student_book_id=sbs[book.id].id, book_section_id=sec.id,
                                   completed_count=comp, reserved_count=res))
            secs[key] = sec
        db.flush()

        def task(d, sec, planned, done=0):
            t = Task(student_id=st.id, date=d, type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=sec.book_id, book_section_id=sec.id,
                                planned_count=planned, completed_count=done))
            db.flush()

        task(d0, secs["s2"], 2, done=2)
        task(d0, secs["s1"], 3)
        ex = ExamResult(student_id=st.id, title="Deneme", exam_date=today,
                        section=ExamSection.TYT, total_correct=40, total_wrong=10,
                        total_blank=0, net=37.5, created_by_id=coach.id)
        db.add(ex)
        db.flush()
        for _ in range(2):
            db.add(ExamResultQuestion(exam_result_id=ex.id, topic_id=tp["Çarpanlara Ayırma"].id,
                                      result="yanlis"))
        out = dict(coach=coach.id, st=st.id, mat=mat.id, fiz=fiz.id,
                   subjects=[mat.id, fiz.id], books=[ba.id, bf.id],
                   sbs=[sb.id for sb in sbs.values()], topics=[t.id for t in tp.values()] + [tf.id],
                   exam=ex.id, email=coach.email)
        db.commit()
        return out


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id == s["st"]))
        db.execute(sa_delete(WeeklySkeleton).where(WeeklySkeleton.student_id == s["st"]))
        tids = [t.id for t in db.query(Task).filter(Task.student_id == s["st"]).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id == s["st"]))
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id == s["exam"]))
        db.execute(sa_delete(ExamResult).where(ExamResult.id == s["exam"]))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(s["sbs"])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(s["sbs"])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(s["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(s["books"])))
        db.execute(sa_delete(Topic).where(Topic.id.in_(s["topics"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(s["subjects"])))
        db.execute(sa_delete(User).where(User.id.in_([s["st"], s["coach"]])))
        db.commit()


def today_tasks(sid: int) -> list[Task]:
    with SessionLocal() as db:
        return db.query(Task).filter(Task.student_id == sid, Task.date == date.today()).all()


GHOST = '[data-section="day:skeleton-ghosts"] [data-testid="ghost-row"]'


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    s = seed()
    sid = s["st"]
    wd = date.today().weekday()
    print(f"\n=== Haftalık İskelet — canlı (öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)
            pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
            pg.wait_for_timeout(2500)

            # Yeni koç hesabında Rehber karşılama penceresi açılır — kapat
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(800)
            # 1-2. düzenleyici
            pg.get_by_role("button", name="İskelet oluştur").click()
            dlg = pg.locator('[role="dialog"]')
            dlg.wait_for(timeout=10000)
            chk("1. İskelet düzenleyicisi açıldı", dlg.count() == 1)
            day_box = dlg.locator('[data-testid="skeleton-day"]').nth(wd)
            for _ in range(3):
                day_box.get_by_role("button", name="Satır ekle").click()
                pg.wait_for_timeout(150)
            rows = day_box.locator('[data-testid="skeleton-row"]')
            rows.nth(0).locator('select[aria-label="Ders"]').select_option(str(s["mat"]))
            rows.nth(0).locator('select[aria-label="Periyot"]').select_option("morning")
            rows.nth(1).locator('select[aria-label="Ders"]').select_option(str(s["mat"]))
            rows.nth(1).locator('select[aria-label="Periyot"]').select_option("evening")
            rows.nth(2).locator('select[aria-label="Ders"]').select_option(str(s["fiz"]))
            rows.nth(2).locator('input[type="checkbox"]').check()
            rows.nth(2).locator('input[type="number"]').fill("2")
            dlg.get_by_role("button", name="Kaydet").click()
            pg.wait_for_timeout(2500)
            with SessionLocal() as db:
                sk = db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id == sid).first()
                nslots = len(sk.slots) if sk else 0
            chk("2. iskelet kaydedildi (3 satır)", nslots == 3, f"slot={nslots}")

            # 3. ızgara
            grid_cells = pg.locator('[data-testid="grid-ghosts"] > div').count()
            chk("3. Hafta Izgarası'nda 3 kesikli öneri", grid_cells == 3, f"{grid_cells}")

            # 4. gün kartı
            nghost = pg.locator(GHOST).count()
            routine_btn = pg.get_by_role("button", name="Rutinleri onayla (1)")
            chk("4. gün kartında 3 hayalet + 'Rutinleri onayla (1)'",
                nghost == 3 and routine_btn.count() == 1, f"hayalet={nghost}")

            # 5. şerit
            pg.locator(GHOST).first.click()
            strip = pg.locator('[data-testid="ghost-strip"]')
            strip.wait_for(timeout=5000)
            chips = strip.locator('[data-testid="ghost-chip"]')
            first_txt = chips.first.inner_text() if chips.count() else ""
            strip_txt = strip.inner_text()
            chk("5a. ilk çip 'devam' + gerekçe 'dünün devamı'",
                "devam" in first_txt and "dünün devamı" in first_txt, first_txt[:160])
            chk("5b. bilgi rozeti: 'denemede 2 yanlış' çipte görünür",
                "denemede 2 yanlış" in strip_txt, strip_txt[:300])
            # şerit satırın ALTINDA
            row_box = pg.locator(GHOST).first.bounding_box()
            strip_box = strip.bounding_box()
            chk("5c. şerit hayalet satırın altında",
                bool(row_box and strip_box and strip_box["y"] >= row_box["y"] + row_box["height"] - 1))

            # 6. kırpma / taşma
            clip = pg.evaluate(
                """() => { const s = document.querySelector('[data-testid="ghost-strip"]');
                  const els = [...s.querySelectorAll('*')].filter(e =>
                    getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1);
                  return {clipped: els.length, overflow: s.scrollWidth > s.clientWidth + 1}; }""")
            chk("6. şeritte kırpılmış metin yok · yatay taşma yok",
                clip["clipped"] == 0 and not clip["overflow"], str(clip))
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_strip.png"), full_page=True)

            # 7. çip → görev
            before = len(today_tasks(sid))
            chips.first.click()
            pg.wait_for_timeout(2500)
            tt = today_tasks(sid)
            periods = sorted(str(t.period.value if hasattr(t.period, "value") else t.period)
                             for t in tt)
            chk("7a. çip görev yazdı (DB +1) · periyot iskeletten",
                len(tt) == before + 1 and any("morning" in p or "evening" in p for p in periods),
                f"{before}->{len(tt)} {periods}")
            n2 = pg.locator(GHOST).count()
            chk("7b. hayalet 3→2 (yenilemesiz)", n2 == 2, f"{n2}")

            # 8. kaldır
            mat_ghost = pg.locator('[data-section="day:skeleton-ghosts"] button[aria-label*="Matematik"]')
            mat_ghost.first.click()
            pg.wait_for_timeout(2000)
            n3 = pg.locator(GHOST).count()
            with SessionLocal() as db:
                dis = db.query(SkeletonGhostAction).filter(
                    SkeletonGhostAction.student_id == sid,
                    SkeletonGhostAction.action == "dismissed").count()
            chk("8. × kaldır → hayalet 2→1 + dismissed kaydı", n3 == 1 and dis == 1,
                f"hayalet={n3} dismissed={dis}")

            # 10. koyu tema (kalan rutin hayaletle ölç, şeridi aç)
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(600)
            pg.locator(GHOST).first.click()
            pg.wait_for_timeout(600)
            low = measure(pg, '[data-section="day:skeleton-ghosts"]', min_ratio=3.0)["bad"]
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_dark.png"), full_page=True)
            chk("10. koyu temada okunamayan metin yok (kontrast ≥ 3.0)", low == 0, f"bad={low}")
            pg.keyboard.press("Escape")
            pg.evaluate("() => document.documentElement.classList.remove('dark')")

            # 9. rutin
            before = len(today_tasks(sid))
            pg.get_by_role("button", name="Rutinleri onayla (1)").click()
            pg.wait_for_timeout(2500)
            with SessionLocal() as db:
                fiz_tasks = (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
                             .join(Book, Book.id == TaskBookItem.book_id)
                             .filter(Task.student_id == sid, Task.date == date.today(),
                                     Book.subject_id == s["fiz"]).all())
            n4 = pg.locator(GHOST).count()
            chk("9. rutin onay → Fizik görevi (2 test) · hayalet kalmadı",
                len(fiz_tasks) == 1 and fiz_tasks[0].planned_count == 2 and n4 == 0,
                f"fiz={[f.planned_count for f in fiz_tasks]} hayalet={n4}")

            # 11. kabul raporu (F1c) iskelet penceresinde
            pg.get_by_role("button", name="İskelet", exact=True).click()
            acc = pg.locator('[data-testid="skeleton-acceptance"]')
            try:
                acc.wait_for(timeout=10000)
            except Exception:
                pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_acc_fail.png"))
                print(pg.evaluate("() => fetch('/api/v2/teacher/skeleton/acceptance?days=30').then(r => r.status + ' ' + r.url).then(x=>x)"))
                print(pg.evaluate("() => fetch('/api/v2/teacher/skeleton/acceptance?days=30').then(r => r.text())"))
                raise
            acc_txt = acc.inner_text()
            chk("11. iskelet penceresinde kabul raporu (işlenen öneri + çipten kabul %)",
                "öneri işlendi" in acc_txt and "çipten kabul" in acc_txt and "kaldırılan 1" in acc_txt,
                acc_txt)
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
