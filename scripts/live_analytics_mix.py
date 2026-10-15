"""Canlı test — Analitik sekmesi veri denetimi + yeni tasarım (2026-10-15).

Kurulum (havuz öğrencisi, kendi koç/öğrencisi, sonunda siler):
  · dün   : TYT Matematik KİTAPLI 4 test (4 çözüldü, 30D 10Y 2B)
  · dün   : TYT Kimya KAYNAKSIZ 3 test (3 çözüldü)
  · bugün : TYT Biyoloji KAYNAKSIZ 2 test (planlı, çözülmedi)
  · seans : TYT Kimya 2 test seansta işaretlendi
Beklenen: trend/hız/haftalık KAYNAKSIZI da sayar; kaynak dağılımı 4 kitaplı + 3 kaynaksız + 2 seansta = 9;
ders kartında Kimya kaynaksız 3 + seansta 2; Biyoloji "verildi, çözülmedi"; müfredat kartı; koyu tema; 390px.

  python scripts/live_analytics_mix.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task,
    TaskBookItem, TaskStatus, Track, User, UserRole,
)
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.services import curriculum_progress as cp, pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lam_{secrets.token_hex(3)}"
PWD = "LiveAnalyticsMix!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"Analitik {tag}",
             role=role, is_active=True, must_change_password=False, **kw)
    db.add(u)
    db.flush()
    return u


def _done(db, task, n, dyb=None):
    bi = task.book_items[0]
    bi.completed_count = n
    if dyb:
        bi.correct_count, bi.wrong_count, bi.blank_count = dyb
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(timezone.utc)
    db.flush()


def seed() -> dict:
    today = date.today()
    y = today - timedelta(days=1)
    with SessionLocal() as db:
        coach = _user(db, "koc", UserRole.TEACHER)
        st = _user(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                   entry_year_grade9=2023, program_mode="havuz")
        S = {n: db.query(Subject).filter(Subject.name == n, Subject.is_builtin.is_(True)).first()
             for n in ("TYT Matematik", "TYT Kimya", "TYT Biyoloji")}
        L = cp.leaf_topics_for_student(db, st, coach.id, [s.id for s in S.values()]).by_subject
        mt = L[S["TYT Matematik"].id][0]
        k0, k1 = L[S["TYT Kimya"].id][0], L[S["TYT Kimya"].id][1]
        b0 = L[S["TYT Biyoloji"].id][0]
        book = Book(name=f"{PFX} Mat SB", subject_id=S["TYT Matematik"].id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label=mt.name, test_count=20, order=1, topic_id=mt.id)
        db.add(sec)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        p = pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=3),
                           expected_next_on=today + timedelta(days=4))
        im = pm.add_item(db, period=p, student=st, subject=S["TYT Matematik"], quantity=8, unit="test", book=book, section=sec)
        ik = pm.add_item(db, period=p, student=st, subject=S["TYT Kimya"], quantity=6, unit="test", topic=k0)
        ik2 = pm.add_item(db, period=p, student=st, subject=S["TYT Kimya"], quantity=4, unit="test", topic=k1)
        ib = pm.add_item(db, period=p, student=st, subject=S["TYT Biyoloji"], quantity=4, unit="test", topic=b0)
        _done(db, pm.put_in_cup(db, item=im, day=y, count=4), 4, (30, 10, 2))
        _done(db, pm.put_in_cup(db, item=ik, day=y, count=3), 3)
        pm.put_in_cup(db, item=ib, day=today, count=2)
        pm.session_mark(db, item=ik2, actor=coach, count=2)
        for it in (im, ik):
            pm.sync_item_progress(db, it)
        db.commit()
        return {"coach": coach.id, "st": st.id, "email": coach.email, "book": book.id, "y": y}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st"], d["coach"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == d["book"]))
        db.execute(sa_delete(Book).where(Book.id == d["book"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


TEXT = "(sel) => { const el = document.querySelector(sel); return el ? el.innerText : ''; }"
OVERFLOW_JS = "() => document.documentElement.scrollWidth > window.innerWidth + 1"


def login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)


def open_tab(page, sid):
    page.goto(f"{WEB}/teacher/students/{sid}#analytics", wait_until="networkidle")
    page.reload(wait_until="networkidle")
    for t in ("Daha sonra",):
        b = page.query_selector(f'[role="dialog"] button:has-text("{t}")')
        if b:
            b.click()
            page.wait_for_timeout(300)
    page.wait_for_selector('[data-section="analytics:mix"]', timeout=30000)


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    print(f"\n=== Analitik veri denetimi + tasarım — canlı ({PFX}) ===\n")
    try:
        # servis düzeyi
        from app.routes.api_v2.teacher import teacher_student_analytics_v2
        with SessionLocal() as db:
            r = teacher_student_analytics_v2(d["st"], user=db.get(User, d["coach"]), db=db).model_dump()
            ytrend = next(p for p in r["trend"] if p["date"] == d["y"].isoformat())
            check("S1 dünün trendi kaynaksızı da sayar: 7/7 (4 kitaplı + 3 kaynaksız)",
                  ytrend["completed"] == 7 and ytrend["planned"] == 7, str(ytrend))
            m = r["mix"]
            check("S2 kaynak dağılımı: kitaplı 4 · kaynaksız 3 · seansta 2 · toplam 9",
                  (m["book_completed"], m["sourceless_completed"], m["session_tests"], m["total_tests"]) == (4, 3, 2, 9), str(m))
            check("S3 sonucu girilen 4/7 · doğruluk %75", m["tests_with_result"] == 4 and m["accuracy_pct"] == 75, str(m))
            sw = {x["name"]: x for x in r["subject_work"]}
            check("S4 Kimya: kaynaksız 3 + seansta 2 · müfredatta konu girildi",
                  sw["TYT Kimya"]["sourceless_tests"] == 3 and sw["TYT Kimya"]["session_tests"] == 2
                  and sw["TYT Kimya"]["started_topics"] >= 1, str(sw.get("TYT Kimya")))
            check("S5 Biyoloji: 2 verildi, 0 çözüldü", sw["TYT Biyoloji"]["planned"] == 2 and sw["TYT Biyoloji"]["total"] == 0)
            check("S6 hız (7g) kaynaksızı da sayar: 7 test / 7 gün = 1.0", abs(r["summary"]["rate_7d"] - 1.0) < 0.01,
                  str(r["summary"]))
            check("S7 kitap projeksiyonu yalnız kitaplı hız (kaynaksız kitap envanterini tüketmez)",
                  abs(r["projection"]["rate_per_day"] - 2.0) < 0.01, str(r["projection"]))  # 4 kitaplı / 2 gün

        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            login(page, d["email"])
            open_tab(page, d["st"])
            mix = page.evaluate(TEXT, '[data-section="analytics:mix"]')
            check("1a kahraman kart: 9 test + Kitaplı 4 / Kaynaksız 3 / Seansta 2",
                  "9" in mix and "Kitaplı" in mix and "Kaynaksız" in mix and "Seansta" in mix, mix.replace("\n", " | ")[:300])
            ins = page.evaluate(TEXT, '[data-section="analytics:insights"]')
            check("1b kısa okuma: Biyoloji görev verildi ama çözülmedi + kaynaksız payı",
                  "TYT Biyoloji" in ins and "çözülmedi" in ins and "kaynaksız" in ins.lower() and "2 hafta" in ins, ins[:400])
            subj = page.evaluate(TEXT, '[data-section="analytics:subjects"]')
            check("1c ders kartı: 'kaynaksız 3 · seansta 2' + '2 test verildi, çözülmedi'",
                  "kaynaksız 3 · seansta 2" in subj and "2 test verildi, çözülmedi" in subj, subj[:400])
            cur = page.evaluate(TEXT, '[data-section="analytics:readiness"]')
            check("1d 12. sınıf: müfredat kartı (15 Haziran hedefi) + sınav/kitap bitirme kartı",
                  "15 Haziran" in cur and "Sınava hazırlık" in cur, cur[:300])
            daily = page.evaluate(TEXT, '[data-section="analytics:daily"]')
            check("1e günlük grafik açıklamalı (kitaplı + kaynaksız)", "kitaplı + kaynaksız" in daily)
            check("1f taşma yok", not page.evaluate(OVERFLOW_JS))
            page.screenshot(path=os.path.join(SHOT_DIR, "analytics_light.png"), full_page=True)
            page.emulate_media(color_scheme="dark")
            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            bad = []
            for sel in ('[data-section="analytics:mix"]', '[data-section="analytics:insights"]',
                        '[data-section="analytics:pace"]', '[data-section="analytics:subjects"]',
                        '[data-section="analytics:dow"]', '[data-section="analytics:curriculum"]',
                        '[data-section="analytics:weekly"]'):
                res = measure(page, sel, 4.5)
                bad += res.get("worst", []) if res.get("bad") else []
            check("2 koyu tema kontrast ≥4,5 (7 bölüm)", not bad, str(bad[:5]))
            page.screenshot(path=os.path.join(SHOT_DIR, "analytics_dark.png"), full_page=True)
            m = b.new_context(viewport={"width": 390, "height": 844})
            mp = m.new_page()
            login(mp, d["email"])
            open_tab(mp, d["st"])
            check("3 390px yatay taşma yok", not mp.evaluate(OVERFLOW_JS))
            mp.screenshot(path=os.path.join(SHOT_DIR, "analytics_mobile.png"), full_page=True)
            b.close()
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed · {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
