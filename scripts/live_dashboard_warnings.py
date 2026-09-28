"""Koç panosu yeni tasarım + Uyarı Akışı (öğrenci bazlı, kanıtlı) — canlı test.

Kendi verisini kurar/temizler. Dev sunucular (:3000 + :8081) açık olmalı.
Ekran görüntüleri: .shots/dashboard_light.png, .shots/dashboard_dark_mobile.png
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

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.models.warning_state import WarningState
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(__file__))
from lib_live_contrast import measure  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"ldw_{secrets.token_hex(3)}"
PWD = "LiveDashWarn!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
now = datetime.now(timezone.utc)
today = date.today()
ids: dict = {"users": [], "books": [], "subjects": []}
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


def seed():
    with SessionLocal() as db:
        c = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                 full_name="Pano Koç", role=UserRole.TEACHER, is_active=True,
                 plan="solo_unlimited", subscription_status="active")
        db.add(c)
        db.flush()
        ids["coach"] = c.id
        ids["users"].append(c.id)
        studs = {}
        for tag, name in (("b", "Boran Kalın Uzunsoyadlı Öğrenci"), ("y", "Yolunda Öğrenci")):
            s = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD),
                     full_name=name, role=UserRole.STUDENT, teacher_id=c.id, grade_level=12,
                     is_active=True, created_at=now - timedelta(days=40),
                     last_login_at=now, last_seen_at=now)
            db.add(s)
            db.flush()
            studs[tag] = s.id
            ids["users"].append(s.id)
        subj = Subject(name=f"{PFX} AYT Kimya", teacher_id=c.id)
        db.add(subj)
        db.flush()
        ids["subjects"].append(subj.id)
        b = Book(teacher_id=c.id, subject_id=subj.id, name=f"{PFX} Kimya SB", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Ü1", test_count=40)
        db.add(sec)
        db.flush()
        for sid in studs.values():
            sb = StudentBook(student_id=sid, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                                   reserved_count=0, completed_count=0))
        # Boran: 5 görev verildi, hiçbiri yapılmadı
        for k in (1, 2, 3, 4, 5):
            t = Task(student_id=studs["b"], date=today - timedelta(days=k), type=TaskType.TEST,
                     title="Kimya", is_draft=False, published_at=now, status=TaskStatus.PENDING)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=b.id, book_section_id=sec.id,
                                planned_count=2, completed_count=0))
        # Yolunda: her gün yaptı
        for k in (1, 2, 3):
            t = Task(student_id=studs["y"], date=today - timedelta(days=k), type=TaskType.TEST,
                     title="Kimya", is_draft=False, published_at=now,
                     status=TaskStatus.COMPLETED, completed_at=now)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=b.id, book_section_id=sec.id,
                                planned_count=2, completed_count=2))
        db.commit()
        ids.update(studs)


def cleanup():
    with SessionLocal() as db:
        sids = [u for u in ids["users"] if u != ids.get("coach")]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(sids or [0]))]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids or [0])))
        db.execute(sa_delete(Task).where(Task.id.in_(tids or [0])))
        sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids or [0]))]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids or [0])))
        db.execute(sa_delete(WarningState).where(WarningState.actor_id == ids.get("coach", 0)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"] or [0])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"] or [0])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"] or [0])))
        db.execute(sa_delete(User).where(User.id.in_(ids["users"] or [0])))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    seed()
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            ctx = br.new_context(viewport={"width": 1300, "height": 1100})
            pg = ctx.new_page()
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', f"{PFX}_t@test.invalid")
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/dashboard", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(500)

            sec = pg.locator('[data-section="dashboard:warnings"]')
            summ = pg.locator('[data-testid="warnings-summary"]').inner_text()
            chk("1 özet satırı öğrenci + uyarı sayısı", "1 öğrencide" in summ, summ)
            groups = sec.locator('[data-testid="warning-group"]')
            chk("2 uyarılar öğrenci bazında tek grupta", groups.count() == 1, str(groups.count()))
            g = groups.first
            chk("3 uzun öğrenci adı kırpılmadan", "Uzunsoyadlı Öğrenci" in g.inner_text())
            codes = [g.locator('[data-testid="warning-item"]').nth(i).get_attribute("data-code")
                     for i in range(g.locator('[data-testid="warning-item"]').count())]
            chk("4 verilip yapılmayan ders + haftalık sıfır yakalandı",
                any(c.startswith("subject_untouched") for c in codes) and "weekly_zero" in codes, str(codes))
            chk("5 açıklama: haftalık sıfırlanmaz", "haftalık sıfırlanmaz" in sec.inner_text())
            item = g.locator('[data-testid="warning-item"][data-code^="subject_untouched"]')
            item.locator('[data-testid="warning-why"]').click()
            pg.wait_for_timeout(300)
            ev = item.locator('[data-testid="warning-evidence"]')
            evt = ev.inner_text() if ev.count() else ""
            chk("6 Neden? kanıtı açılır (verilen 5 görev · 10 test)", "5 görev · 10 test" in evt, evt)
            chk("7 yatay taşma yok", not pg.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            ell = pg.evaluate("""() => [...document.querySelectorAll('[data-section="dashboard:warnings"] *')]
                .filter(e => e.children.length === 0 && e.scrollWidth > e.clientWidth + 1
                        && getComputedStyle(e).textOverflow === 'ellipsis').length""")
            chk("8 kırpılmış metin yok", ell == 0, str(ell))
            pg.screenshot(path=os.path.join(SHOT_DIR, "dashboard_light.png"), full_page=True)

            before = g.locator('[data-testid="warning-item"]').count()
            g.locator('[data-testid="warning-item"]').first.get_by_role("button", name="Gördüm").click()
            pg.wait_for_timeout(2500)
            after = sec.locator('[data-testid="warning-item"]').count()
            chk("9 Gördüm → uyarı akıştan çıktı", after == before - 1, f"{before}->{after}")
            chk("10 gizlenenler bölümü", "Gizlediğin uyarılar (1)" in sec.inner_text())

            dctx = br.new_context(viewport={"width": 390, "height": 900}, color_scheme="dark",
                                  storage_state=ctx.storage_state())
            dp = dctx.new_page()
            dp.goto(f"{BASE}/teacher/dashboard", wait_until="networkidle")
            dp.wait_for_timeout(2500)
            dp.evaluate("() => document.documentElement.classList.add('dark')")
            dp.wait_for_timeout(300)
            chk("11 390px yatay taşma yok", not dp.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            bad = measure(dp, '[data-section="dashboard:warnings"]', min_ratio=3.0)["bad"]
            chk("12 koyu tema kontrastı", bad == 0, str(bad))
            dp.screenshot(path=os.path.join(SHOT_DIR, "dashboard_dark_mobile.png"), full_page=True)
            br.close()
    finally:
        cleanup()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
