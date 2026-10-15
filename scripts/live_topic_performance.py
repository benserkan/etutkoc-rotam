"""Canlı test — Konu performansı yeniden tasarım + sonuç girişi + havuzda konu zorunluluğu (2026-10-14).

Kurulum (kendi koç/öğrencisi, sonunda siler):
  · K0: 3 test, 10D 14Y 6B → %42 → ZAYIF          · K1: 3 test, sonuç YOK
  · K2: koç seansta 2 test işaretledi (sonuçsuz)    · K3: görevi yok, denemede 0/4 → "yalnız denemede"
  · K4: bugün kapta 2 test (öğrenci işaretleyecek)
Kontroller:
  koç Konu Performansı → özet sayıları + "sonuç girilmemiş" uyarısı + "Nerede kaybediyor" + ders kartı
  öğrenci Bugün → görevi işaretleyince sonuç penceresi KENDİLİĞİNDEN açılır → 24D 6Y 0B kaydedilir (test birimi)
  koç havuz editörü → "Konusuz" seçilince test/soru birimi kilitli · Hızlı yazda konusuz test eklenemez
  koyu tema kontrast + 390px taşma

  python scripts/live_topic_performance.py
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    PoolItem, StudyPeriod, Subject, Task, TaskBookItem, TaskStatus, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_result import EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion  # noqa: E402
from app.services import curriculum_progress as cp, pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"ltp_{secrets.token_hex(3)}"
PWD = "LiveTopicPerf!234"
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
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"Konu {tag}",
             role=role, is_active=True, must_change_password=False, **kw)
    db.add(u)
    db.flush()
    return u


def _cup_done(db, item, day, n, dyb=None):
    t = pm.put_in_cup(db, item=item, day=day, count=n)
    bi = t.book_items[0]
    bi.completed_count = n
    if dyb:
        bi.correct_count, bi.wrong_count, bi.blank_count = dyb
    t.status = TaskStatus.COMPLETED
    from datetime import datetime, timezone
    t.completed_at = datetime.now(timezone.utc)
    db.flush()
    pm.sync_item_progress(db, item)
    return t


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = _user(db, "koc", UserRole.TEACHER)
        st = _user(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                   entry_year_grade9=2023, program_mode="havuz")
        kim = db.query(Subject).filter(Subject.name == "TYT Kimya", Subject.is_builtin.is_(True)).first()
        ks = cp.leaf_topics_for_student(db, st, coach.id, [kim.id]).by_subject[kim.id]
        k0, k1, k2, k3, k4 = ks[0], ks[1], ks[2], ks[3], ks[4]
        p = pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=2),
                           expected_next_on=today + timedelta(days=5))
        i0 = pm.add_item(db, period=p, student=st, subject=kim, quantity=6, unit="test", topic=k0)
        i1 = pm.add_item(db, period=p, student=st, subject=kim, quantity=6, unit="test", topic=k1)
        i2 = pm.add_item(db, period=p, student=st, subject=kim, quantity=4, unit="test", topic=k2)
        i4 = pm.add_item(db, period=p, student=st, subject=kim, quantity=4, unit="test", topic=k4)
        _cup_done(db, i0, today - timedelta(days=1), 3, (10, 14, 6))
        _cup_done(db, i1, today - timedelta(days=1), 3)
        pm.session_mark(db, item=i2, actor=coach, count=2)
        cup = pm.put_in_cup(db, item=i4, day=today, count=2)
        ex = ExamResult(student_id=st.id, created_by_id=coach.id, title=f"{PFX} TYT", exam_date=today - timedelta(days=5),
                        section=ExamSection.TYT, total_correct=0, total_wrong=4, total_blank=0, net=-1.0)
        db.add(ex)
        db.flush()
        for n in range(4):
            db.add(ExamResultQuestion(exam_result_id=ex.id, question_no=n + 1, subject_id=kim.id, topic_id=k3.id,
                                      result=EQ_RESULT_YANLIS))
        db.commit()
        return {"coach": coach.id, "st": st.id, "email": coach.email, "st_email": st.email, "kim": kim.name,
                "k0": k0.name, "k1": k1.name, "k2": k2.name, "k3": k3.name, "cup": cup.id, "exam": ex.id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st"], d["coach"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id == d["exam"]))
        db.execute(sa_delete(ExamResult).where(ExamResult.id == d["exam"]))
        from app.models.self_study import SelfStudyEntry
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
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


def dismiss(page):
    for t in ("Daha sonra", "Kapat"):
        b = page.query_selector(f'[role="dialog"] button:has-text("{t}")')
        if b:
            b.click()
            page.wait_for_timeout(300)


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    print(f"\n=== Konu performansı + sonuç girişi + konu zorunluluğu — canlı ({PFX}) ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            login(page, d["email"])
            page.goto(f"{WEB}/teacher/students/{d['st']}#topics", wait_until="networkidle")
            page.reload(wait_until="networkidle")
            dismiss(page)
            page.wait_for_selector('[data-section="topic-perf:overview"]', timeout=30000)
            ov = page.evaluate(TEXT, '[data-section="topic-perf:overview"]')
            check("1a özet: 8 test (2'si seansta) · %42 · sonucu girilen 3/6 test",
                  "8" in ov and "seansta" in ov and "%42" in ov and "3/6" in ov, ov.replace("\n", " | ")[:300])
            gap = page.evaluate(TEXT, '[data-section="topic-perf:gap"]')
            check("1b uyarı: '6 testin 3 tanesinde sonuç girilmemiş' + koça yönlendirme",
                  "6 testin 3 tanesinde sonuç girilmemiş" in gap and "Öğrenciden" in gap, gap[:200])
            focus = page.evaluate(TEXT, '[data-section="topic-perf:focus"]')
            check("1c Nerede kaybediyor: K0 zayıf (%42) önde", d["k0"] in focus and "Zayıf" in focus and "%42" in focus,
                  focus[:300])
            check("1d yalnız denemede zayıf konu (K3) listede + rozet",
                  d["k3"] in focus and "yalnız denemede" in focus)
            page.locator('[data-testid="topic-perf-subject"]', has_text=d["kim"]).first.click()
            page.wait_for_timeout(400)
            rows = [r.inner_text() for r in page.query_selector_all('[data-testid="topic-perf-topic"]')]
            check("1e ders açılınca zayıf konu ilk sırada", rows and d["k0"] in rows[0], str(rows[:2]))
            check("1f seans işareti satırda: '2 test (2 tanesi seansta)'",
                  any(d["k2"] in r and "2 tanesi seansta" in r for r in rows), str(rows))
            check("1g sonuçsuz konu: 'sonuç girilmemiş'", any(d["k1"] in r and "sonuç girilmemiş" in r for r in rows))
            check("1h taşma yok", not page.evaluate(OVERFLOW_JS))
            page.screenshot(path=os.path.join(SHOT_DIR, "topic_perf_light.png"), full_page=True)
            page.emulate_media(color_scheme="dark")
            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            bad = []
            for sel in ('[data-section="topic-perf:overview"]', '[data-section="topic-perf:gap"]',
                        '[data-section="topic-perf:focus"]', '[data-section="topic-perf:subjects"]'):
                r = measure(page, sel, 4.5)
                bad += r.get("worst", []) if r.get("bad") else []
            check("1i koyu tema kontrast ≥4,5 (4 bölüm)", not bad, str(bad[:4]))
            page.screenshot(path=os.path.join(SHOT_DIR, "topic_perf_dark.png"), full_page=True)
            page.emulate_media(color_scheme="light")
            page.evaluate("() => document.documentElement.classList.remove('dark')")

            # 3 — havuz editörü: konu zorunluluğu
            page.goto(f"{WEB}/teacher/students/{d['st']}/pool?mod=duzenle", wait_until="networkidle")
            dismiss(page)
            page.wait_for_selector('[data-section="pool:add"]', timeout=30000)
            page.locator('[data-section="pool:add"] button', has_text=d["kim"]).first.click()
            page.wait_for_timeout(500)
            mufredat = page.query_selector('[data-section="pool:add"] button:has-text("Müfredat konusundan")')
            if mufredat:
                mufredat.click()
                page.wait_for_timeout(400)
            page.click('[data-section="pool:add"] button:has-text("Konusuz")')
            page.wait_for_timeout(500)
            test_btn = page.locator('[data-section="pool:add"] [role="radiogroup"][aria-label="Birim"] button', has_text="Test").first
            check("3a Konusuz kalemde 'Test' birimi kilitli", test_btn.is_disabled())
            sel = page.locator('[data-section="pool:add"] [role="radiogroup"][aria-label="Birim"] [aria-checked="true"]').first.inner_text()
            check("3b konusuz kalemde varsayılan birim Sayfa", "sayfa" in sel.lower(), sel)
            page.click('[data-section="pool:add"] [role="tab"]:has-text("Hızlı yaz")')
            page.fill('input[placeholder*="345 matematik"]', "zzqxw denemesi 3 test")
            page.click('button:has-text("Ayrıştır")')
            try:
                page.wait_for_selector('text=bağlanmalı', timeout=15000)
            except Exception:
                pass
            body = page.evaluate(TEXT, '[data-section="pool:add"]')
            check("3c hızlı yaz: konusuz test → 'Böyle ekle' yok + 'konuya bağlanmalı' uyarısı",
                  page.query_selector('button:has-text("Böyle ekle")') is None and "konuya" in body and "bağlanmalı" in body,
                  body[-300:])
            page.fill('input[placeholder*="345 matematik"]', f"tyt kimya {d['k1']} 2 test")
            page.click('button:has-text("Ayrıştır")')
            page.wait_for_timeout(2500)
            check("3d konu yazılınca 'Böyle ekle' görünür (ya da konu seçenekleri)",
                  page.query_selector('button:has-text("Böyle ekle")') is not None
                  or page.query_selector('[data-section="pool:add:parse-options"]') is not None)

            # 2 — öğrenci: işaretleyince sonuç penceresi
            ctx2 = b.new_context(viewport={"width": 1280, "height": 900})
            sp = ctx2.new_page()
            login(sp, d["st_email"])
            sp.goto(f"{WEB}/student/day", wait_until="networkidle")
            dismiss(sp)
            card = sp.locator("article", has_text="2 test").first
            card.locator("header button").first.click()
            sp.wait_for_timeout(1500)
            dlg_text = sp.evaluate("() => document.body.innerText")
            check("2a görev işaretlenince sonuç penceresi kendiliğinden açıldı (test birimi)",
                  "çözdüğüm test" in dlg_text.lower() and "doğru" in dlg_text.lower(), dlg_text[-400:])
            dlg = sp.locator('[aria-label="Görev tamamlama"]')
            res_inputs = dlg.locator('input[placeholder="—"]')
            filled = res_inputs.count()
            vals = "doğru/yanlış/boş"
            res_inputs.nth(0).fill("24")
            res_inputs.nth(1).fill("6")
            if filled > 2:
                res_inputs.nth(2).fill("0")
            sp.click('button:has-text("Kaydet")')
            sp.wait_for_timeout(1500)
            with SessionLocal() as db:
                bi = db.query(TaskBookItem).filter(TaskBookItem.task_id == d["cup"]).first()
                check("2b 2 test · 24D 6Y kaydedildi (D+Y > test sayısı kabul — test birimi)",
                      bi.completed_count == 2 and bi.correct_count == 24 and bi.wrong_count == 6,
                      f"filled={filled} labels={vals} → {bi.completed_count} {bi.correct_count} {bi.wrong_count}")
            sp.screenshot(path=os.path.join(SHOT_DIR, "student_result_prompt.png"), full_page=False)

            # 390px
            m = b.new_context(viewport={"width": 390, "height": 844})
            mp = m.new_page()
            login(mp, d["email"])
            mp.goto(f"{WEB}/teacher/students/{d['st']}#topics", wait_until="networkidle")
            mp.reload(wait_until="networkidle")
            dismiss(mp)
            mp.wait_for_selector('[data-section="topic-perf:overview"]', timeout=30000)
            check("4 390px yatay taşma yok", not mp.evaluate(OVERFLOW_JS))
            b.close()
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed · {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
