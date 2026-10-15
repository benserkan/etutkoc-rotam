"""Program modu geçişi — CANLI tarayıcı testi (Next :3000 + backend :8081), 2026-10-15.

Gün gün öğrenci: /pool mod kartı → "Havuz moduna geç" → önizleme penceresi (silinecek/kalacak görev,
iade) → geç → editör havuzda + dönem açık + geçiş geçmişi · havuz öğrencisi: seans ekranı "Seansı bitir"
→ "Bu seansla gün gün programa geç" → geçiş bilgisi kutusu → bitir → /week'e yönlenir, mod gün gün,
Durum Özeti'nde sarı "ilk programı hazırla" · koyu tema kontrast · 390px taşma yok.

Çalıştır (sistem python): python scripts/live_program_mode_switch.py
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, CoachingSession, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.pool import ProgramModeChange  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lms_{secrets.token_hex(3)}"
PWD = "ModCanli!23456"
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
             role=role, is_active=True, email_verified_at=now, created_at=now - timedelta(days=60), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _task(db, s, day, planned, done, b, sec):
    t = Task(student_id=s.id, date=day, title=f"{b.name} — Üslü Sayılar: {planned} test", type="test",
             is_draft=False,
             status=TaskStatus.COMPLETED if done >= planned else TaskStatus.PARTIAL if done else TaskStatus.PENDING)
    db.add(t)
    db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=b.id, book_section_id=sec.id, planned_count=planned, completed_count=done))
    return t


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        ids["subjects"].append(tyt.id)
        top = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        db.add(top)
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Kitap", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=100, order=1, topic_id=top.id)
        db.add(sec)
        db.flush()
        s = _user(db, "gg", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL)
        sb = StudentBook(student_id=s.id, book_id=b.id)
        db.add(sb)
        db.flush()
        _task(db, s, today, 4, 0, b, sec)
        _task(db, s, today + timedelta(days=1), 5, 2, b, sec)
        _task(db, s, today + timedelta(days=2), 3, 0, b, sec)
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=10, completed_count=2))
        h = _user(db, "hv", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                  program_mode="havuz")
        sbh = StudentBook(student_id=h.id, book_id=b.id)
        db.add(sbh)
        db.flush()
        db.add(SectionProgress(student_book_id=sbh.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        db.flush()
        p = pm.open_period(db, student=h, coach=coach, opened_on=today - timedelta(days=6))
        it = pm.add_item(db, period=p, student=h, subject=tyt, quantity=8, unit="test", book=b, section=sec)
        pm.put_in_cup(db, item=it, day=today, count=2)
        db.commit()
        return {"email": coach.email, "s": s.id, "h": h.id, "sb": sb.id, "sec": sec.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        db.execute(sa_delete(ProgramModeChange).where(ProgramModeChange.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1", "::1"])))
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
    print(f"\n=== Program modu geçişi — canlı ({PFX}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            _login(page, d["email"])

            # 1) gün gün → havuz
            page.goto(f"{WEB}/teacher/students/{d['s']}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-testid="mode-switch-open"]', timeout=20000)
            _dismiss(page)
            page.click('[data-testid="mode-switch-open"]')
            page.wait_for_selector('[data-section="mode-switch:effects"]', timeout=15000)
            eff = page.inner_text('[data-section="mode-switch:effects"]')
            check("1a önizleme: 2 silinecek + 1 kalacak + 10 test iade",
                  "Silinecek görevler" in eff and "2/5 test çözüldü" in eff and "10" in eff, eff[:300])
            page.screenshot(path=os.path.join(ROOT, ".shots", "mode_switch_preview.png"))
            r = measure(page, '[data-testid="mode-switch-dialog"]', 4.5)
            check("1b pencere kontrastı ≥4,5", not r["bad"], str(r.get("worst")))
            # koyu tema
            page.emulate_media(color_scheme="dark")
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            r = measure(page, '[data-testid="mode-switch-dialog"]', 4.5)
            check("1c koyu tema pencere kontrastı ≥4,5", not r["bad"], str(r.get("worst")))
            page.screenshot(path=os.path.join(ROOT, ".shots", "mode_switch_preview_dark.png"))
            page.evaluate("document.documentElement.classList.remove('dark')")
            page.emulate_media(color_scheme="light")
            page.click('[data-testid="mode-switch-submit"]')
            page.wait_for_url("**/pool?mod=duzenle", timeout=20000)
            page.wait_for_selector('[data-section="pool:period"]', timeout=20000)
            check("1d geçti: editör havuz modunda + dönem açık", page.query_selector('[data-section="pool:period"]') is not None)
            page.wait_for_selector('[data-section="pool:mode-history"]', timeout=15000)
            hist = page.inner_text('[data-section="pool:mode-history"]')
            check("1e geçiş geçmişi: gün gün → havuz + 2 görev silindi + 10 test iade",
                  "Haftalık görev havuzu" in hist and "2 görev silindi" in hist and "10 test iade" in hist, hist[:200])
            with SessionLocal() as db:
                n = db.query(Task).filter(Task.student_id == d["s"]).count()
                prog = db.query(SectionProgress).filter_by(student_book_id=d["sb"], book_section_id=d["sec"]).one()
                check("1f DB: yalnız kısmi görev kaldı, rezerv 0, çözülen 2", n == 1 and prog.reserved_count == 0
                      and prog.completed_count == 2, f"{n} {prog.reserved_count}")

            # 2) havuz → gün gün (seansı bitir)
            page.goto(f"{WEB}/teacher/students/{d['h']}/pool/session", wait_until="networkidle")
            page.wait_for_selector('button:has-text("Seansı bitir")', timeout=20000)
            _dismiss(page)
            page.click('button:has-text("Seansı bitir")')
            page.wait_for_selector('[data-testid="finish-to-gun-gun"]', timeout=10000)
            page.check('[data-testid="finish-to-gun-gun"] input')
            page.wait_for_selector('[data-section="pool:finish:switch"]', timeout=5000)
            info = page.inner_text('[data-section="pool:finish:switch"]')
            check("2a geçiş bilgisi: kalan 1 kalem havuzdan çıkar + 3 gün sarı", "1 kalem" in info and "sarı" in info, info[:200])
            btn = page.inner_text('[data-testid="finish-submit"]')
            check("2b düğme 'Bitir ve gün gün programa geç'", "gün gün" in btn, btn)
            check("2c devir listesi gizli", page.query_selector('input[aria-label="Devret"]') is None)
            page.screenshot(path=os.path.join(ROOT, ".shots", "mode_switch_finish.png"))
            page.click('[data-testid="finish-submit"]')
            page.wait_for_url(f"**/teacher/students/{d['h']}/week", timeout=20000)
            check("2d /week'e yönlendi", page.url.endswith(f"/students/{d['h']}/week"))
            with SessionLocal() as db:
                h = db.get(User, d["h"])
                check("2e DB: mod gün gün, açık dönem yok, kap görevi silindi",
                      h.program_mode == "gun_gun" and pm.get_open_period(db, h.id) is None
                      and db.query(Task).filter(Task.student_id == h.id).count() == 0)
            page.goto(f"{WEB}/teacher/students/{d['h']}", wait_until="networkidle")
            page.wait_for_timeout(2500)
            body = page.inner_text("body")
            check("2f Durum Özeti: 'Gün gün programa geçti — ilk programı hazırla'",
                  "ilk programı hazırla" in body and "Programı yok" not in body, "")

            # 3) 390px taşma yok
            m = b.new_page(viewport={"width": 390, "height": 844})
            m.context.add_cookies(page.context.cookies())
            m.goto(f"{WEB}/teacher/students/{d['s']}/pool?mod=duzenle", wait_until="networkidle")
            m.wait_for_timeout(2500)
            ov = m.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check("3a 390px yatay taşma yok", ov <= 1, str(ov))
            b.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
