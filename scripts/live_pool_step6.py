"""Havuz Adım 6 — CANLI tarayıcı testi (Next :3000 + backend :8081).

Editörde devir ekranı (son dönemin kalanları, kalem kalem seç + miktar, "3. devir olacak" rozeti,
"Dönem aç · N kalem devret") · ara (tatil) bandı + aradan dönüş · sayfalı dönem geçmişi
("Daha fazla", satır aç → ders kırılımı) · öğrenci web Havuzum ara metni + önceki dönemler ·
koyu tema kontrast.

Çalıştır (sistem python): python scripts/live_pool_step6.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, ClassGroup, NotificationLog, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.pool import PERIOD_BREAK, PERIOD_CLOSED  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"l6_{secrets.token_hex(3)}"
PWD = "Step6Canli!234"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today = date.today()
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"Canlı {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=120), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _cup(db, item, day, count, done=None):
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    if done:
        for bi in t.book_items:
            bi.completed_count = done
        t.status = TaskStatus.COMPLETED
        t.completed_at = datetime.combine(day, time(20, 0), tzinfo=timezone.utc)
        db.flush()
        pm.sync_item_progress(db, item)
    return t


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        fiz = Subject(name=f"{PFX} TYT Fizik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([tyt, fiz])
        db.flush()
        ids["subjects"] += [tyt.id, fiz.id]
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t3 = Topic(subject_id=fiz.id, name="Optik", order=1, teacher_id=coach.id)
        db.add_all([t1, t3])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=200, order=1, topic_id=t1.id)
        db.add(sec)
        db.flush()

        def mk(tag):
            s = _user(db, tag, UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                      program_mode="havuz", class_group="12-A", last_seen_at=now - timedelta(hours=20))
            sb = StudentBook(student_id=s.id, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
            return s

        # s_main: 11 kapanmış dönem (geçmiş sayfalama) + son dönem kalanlı (devir adayı, biri 3. devir olacak)
        s_main = mk("main")
        for k in range(12, 1, -1):
            p = pm.open_period(db, student=s_main, coach=coach, opened_on=today - timedelta(days=7 * k + 1))
            it = pm.add_item(db, period=p, student=s_main, subject=tyt, quantity=4, unit="test", book=b, section=sec)
            _cup(db, it, p.opened_on + timedelta(days=2), 4, done=4)
            pm.close_period(db, p, closed_on=p.opened_on + timedelta(days=7), status=PERIOD_CLOSED)
        p_last = pm.open_period(db, student=s_main, coach=coach, opened_on=today - timedelta(days=8))
        i_a = pm.add_item(db, period=p_last, student=s_main, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        i_b = pm.add_item(db, period=p_last, student=s_main, subject=fiz, quantity=6, unit="test", topic=t3)
        i_a.carry_count = 2
        _cup(db, i_a, today - timedelta(days=5), 4, done=4)
        pm.close_period(db, p_last, closed_on=today - timedelta(days=1), status=PERIOD_CLOSED)
        # s_break: ara
        s_break = mk("break")
        p_b = pm.open_period(db, student=s_break, coach=coach, opened_on=today - timedelta(days=9))
        pm.add_item(db, period=p_b, student=s_break, subject=tyt, quantity=8, unit="test", book=b, section=sec)
        pm.close_period(db, p_b, closed_on=today - timedelta(days=2), status=PERIOD_BREAK)
        db.execute(sa_delete(NotificationLog).where(NotificationLog.student_id.in_([s_main.id, s_break.id])))
        db.commit()
        return {"coach": coach.id, "main": s_main.id, "break": s_break.id, "i_a": i_a.id, "i_b": i_b.id,
                "email": f"{PFX}_coach@test.invalid", "semail": f"{PFX}_break@test.invalid"}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(ClassGroup).where(ClassGroup.scope_key == f"coach:{ids['users'][0]}"))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def _login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)


def _dismiss(page):
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(500)


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = seed()
    sid = d["main"]
    print(f"\n=== Havuz Adım 6 — canlı ({PFX}, öğrenci #{sid}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.on("dialog", lambda dd: dd.accept())
            _login(page, d["email"])

            # 1) devir ekranı
            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:carry"]', timeout=20000)
            _dismiss(page)
            rows = page.query_selector_all('[data-section="pool:carry"] li[data-carry]')
            check("1a devir adayları: 2 kalem (kalan 6 + kalan 6)", len(rows) == 2, str(len(rows)))
            ctext = page.query_selector('[data-section="pool:carry"]').inner_text()
            check("1b K58 rozeti: 'Devir ×2' + '3. devir olacak'; toplu düğme yok", "Devir ×2" in ctext and "3. devir olacak" in ctext and "Tümünü" not in ctext, ctext[:200])
            row_a = page.query_selector(f'[data-carry="{d["i_a"]}"]')
            row_a.query_selector('input[aria-label="Devret"]').check()
            page.wait_for_timeout(200)
            qty = row_a.query_selector('input[aria-label="Devir miktarı"]')
            check("1c seçince miktar kutusu kalanla (6) ön-dolu", qty is not None and qty.input_value() == "6", qty.input_value() if qty else "-")
            qty.fill("3")
            btn = page.query_selector('[data-testid="pool-open-period"]')
            check("1d düğme 'Dönem aç · 1 kalem devret'", "1 kalem devret" in btn.inner_text(), btn.inner_text())
            btn.click()
            page.wait_for_selector('[data-section="pool:list"]', timeout=20000)
            page.wait_for_timeout(1000)
            lst = page.query_selector('[data-section="pool:list"]').inner_text()
            check("1e yeni dönem: 1 devir kalemi, 'Devir ×3' rozeti, 3 test", "1 kalem" in lst and "Devir ×3" in lst and "3 test" in lst, lst[:200])
            with SessionLocal() as db:
                newp = pm.get_open_period(db, sid)
                check("1f DB: yeni dönemde 1 kalem, kaynak devir, miktar 3, sayaç 3, kaynak kalem bağlı",
                      newp is not None and len(newp.items) == 1 and newp.items[0].source == "devir"
                      and newp.items[0].quantity == 3 and newp.items[0].carry_count == 3 and newp.items[0].parent_item_id == d["i_a"])
            flags = page.query_selector('[data-section="pool:flags"]')
            check("1g K58: 3. devir → kaçınma sinyali editör şeridinde", flags is not None and "kaçın" in flags.inner_text().lower(), flags.inner_text()[:120] if flags else "-")

            # 2) dönem geçmişi sayfalı
            hist = page.query_selector('[data-section="pool:history"]')
            check("2a geçmiş başlığı '12 dönem · geçmiş sınırsız saklanır', ilk sayfa 10 satır",
                  hist is not None and "12 dönem" in hist.inner_text() and len(page.query_selector_all('[data-section="pool:history"] li[data-period]')) == 10,
                  hist.inner_text()[:100] if hist else "-")
            page.click('[data-testid="pool-history-more"]')
            page.wait_for_timeout(2500)
            n = len(page.query_selector_all('[data-section="pool:history"] li[data-period]'))
            check("2b 'Daha fazla' → 12 satır, düğme kayboldu", n == 12 and page.query_selector('[data-testid="pool-history-more"]') is None, str(n))
            first = page.query_selector_all('[data-section="pool:history"] li[data-period]')[0]
            check("2c son kapanmış dönem satırı: 'devredildi 1'", "devredildi 1" in first.inner_text(), first.inner_text()[:120])
            det = first.query_selector('[data-section="pool:history:subjects"]').inner_text()  # 2026-10-13: çipler kartta
            check("2d kartta ders kırılımı (Matematik 4/10 · Fizik 0/6)", "4/10" in det and "0/6" in det, det[:200])
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            m = measure(page, '[data-section="pool:history"]', min_ratio=4.5)
            check("2e koyu tema: geçmiş + detay okunur", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_history_dark.png"), full_page=True)
            page.evaluate("document.documentElement.classList.remove('dark')")

            # 3) ara (tatil)
            page.goto(f"{WEB}/teacher/students/{d['break']}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:open"]', timeout=20000)
            br = page.query_selector('[data-section="pool:break"]')
            check("3a editörde 'Ara (tatil)' bandı + aradan dönüş notu", br is not None and "Ara (tatil)" in br.inner_text() and "Aradan dönmek" in br.inner_text(), br.inner_text()[:150] if br else "-")
            check("3b aradan dönüşte devir adayı (ara döneminin 8 testi)", page.query_selector('[data-section="pool:carry"] li[data-carry]') is not None
                  and "kalan 8" in page.query_selector('[data-section="pool:carry"]').inner_text())
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            m = measure(page, '[data-section="pool:open"]', min_ratio=4.5)
            check("3c koyu tema: ara bandı + devir listesi okunur", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_break_dark.png"), full_page=True)

            # 4) öğrenci web (ara)
            page.context.clear_cookies()
            _login(page, d["semail"])
            page.goto(f"{WEB}/student/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="student:pool:empty"]', timeout=20000)
            _dismiss(page)
            st = page.query_selector('[data-section="student:pool:empty"]').inner_text()
            check("4a öğrenci Havuzum: 'Ara (tatil)' metni + önceki dönem (%0)", "Ara (tatil)" in st and "Önceki dönemlerin" in st and "%0" in st, st[:200])
            b.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
