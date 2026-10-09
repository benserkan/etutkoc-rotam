"""Kaynak Durumu "Ayir" -> yuzen pencere + Video Sepeti dugmesi tasima (2026-10-09).

GERCEK TARAYICI, 14 senaryo. Ekran: .shots/resources_float_{light,dark}.png
"""
from __future__ import annotations

import io
import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    SuspiciousIp, Task, TaskBookItem, TaskType, User, UserRole,
)
from app.services.security import hash_password  # noqa: E402
from scripts.audit_day_card_perception import delta_e  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"rfl_{secrets.token_hex(3)}"
PWD = "IsiHarita!2345"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
TR_M = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]

# (ünite, çözülen) — test sayısı hepsinde 10
PLAN = [("Hareket", 0), ("Kuvvet", 3), ("Basınç", 6), ("Kaldırma Kuvveti", 10)]
LAST = "Basınç"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Isı Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Isı Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        subj = Subject(name="TYT Fizik", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"345 TYT Fizik {PFX}", subject_id=subj.id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        secs = {}
        for i, (lab, done) in enumerate(PLAN):
            sec = BookSection(book_id=book.id, label=lab, test_count=10, order=i)
            db.add(sec)
            db.flush()
            secs[lab] = sec.id
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                                   reserved_count=0, completed_count=done))
        # son görev Basınç (dün); Kaldırma Kuvveti daha eski
        for lab, d in (("Kaldırma Kuvveti", today - timedelta(days=6)), (LAST, today - timedelta(days=1))):
            t = Task(student_id=st.id, date=d, type=TaskType.TEST, title="g",
                     is_draft=False, status="completed")
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=secs[lab],
                                planned_count=1, completed_count=1))
        db.commit()
        last_d = today - timedelta(days=1)
        return {"coach": coach.id, "student": st.id, "subject": subj.id, "book": book.id,
                "sb": sb.id, "email": f"{PFX}_t@test.invalid", "book_name": book.name,
                "last_label": f"{last_d.day} {TR_M[last_d.month - 1]}"}


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uid = [ids["coach"], ids["student"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uid)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == ids["sb"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == ids["sb"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
        db.execute(sa_delete(Book).where(Book.id == ids["book"]))
        db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1", "testclient"])))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()




def login(page, ids):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', ids["email"])
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)


def goto_week(page, ids):
    page.goto(f"{WEB}/teacher/students/{ids['student']}/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(800)


def drag(page, sel, dx, dy):
    bb = page.locator(sel).bounding_box()
    x, y = bb["x"] + 30, bb["y"] + bb["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 11):
        page.mouse.move(x + dx * i / 10, y + dy * i / 10)
        page.wait_for_timeout(15)
    page.mouse.up()
    page.wait_for_timeout(400)


def box(page, sel):
    return page.locator(sel).bounding_box()


FLOAT = '[data-testid="resources-float"]'


def open_float_book(page, ids):
    page.click(f'{FLOAT} .resource-subject > button')
    page.wait_for_timeout(700)
    page.click(f'{FLOAT} button:has-text("{ids["book_name"]}")')
    page.wait_for_timeout(700)


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    print(f"\n=== Kaynak Durumu 'Ayır' + Video Sepeti düğmesi (öğrenci #{ids['student']}) ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script(
                "try{if(!sessionStorage.getItem('rfl-init')){"
                "localStorage.setItem('lgs-theme','light');"
                "['rotam:float:resources','rotam:float:resources:on','rotam:float:video-basket-fab',"
                "'rotam:float:video-basket'].forEach(k=>localStorage.removeItem(k));"
                "sessionStorage.setItem('rfl-init','1')}}catch(e){}")
            page = ctx.new_page()
            login(page, ids)
            goto_week(page, ids)
            page.wait_for_selector('[data-section="week:resources"]', timeout=15000)

            check("1. panelde 'Ayır' düğmesi",
                  page.query_selector('[data-testid="resources-detach"]') is not None)
            page.click('[data-testid="resources-detach"]')
            page.wait_for_timeout(700)
            fl = page.query_selector(FLOAT)
            docked = page.query_selector('[data-docked-panel] [data-section="week:resources"]')
            check("2. yüzen pencere açıldı, sağ panelden çıktı", fl is not None and docked is None)
            rail = page.query_selector('[data-rail="week:resources"]')
            check("3. şeritte 'yüzen' işareti",
                  rail is not None and rail.get_attribute("data-floating-section") == "1")

            open_float_book(page, ids)
            rows = page.query_selector_all(f'{FLOAT} [data-testid="resource-section"]')
            check("4. pencerede ders/kitap/üniteler açılıyor", len(rows) == 4, f"{len(rows)}")

            y0 = box(page, FLOAT)["y"]
            page.mouse.move(700, 500)
            page.mouse.wheel(0, 900)
            page.wait_for_timeout(500)
            y1 = box(page, FLOAT)["y"]
            check("5. sayfa kayınca pencere yerinde", abs(y0 - y1) < 1, f"{y0}->{y1}")
            page.mouse.wheel(0, -900)
            page.wait_for_timeout(300)

            b0 = box(page, FLOAT)
            drag(page, '[data-testid="resources-float-handle"]', -500, 120)
            b1 = box(page, FLOAT)
            check("6. başlıktan taşınıyor", b1["x"] < b0["x"] - 400 and b1["y"] > b0["y"] + 80,
                  f"{b0['x']:.0f},{b0['y']:.0f} -> {b1['x']:.0f},{b1['y']:.0f}")

            clip = page.evaluate("""() => {
              const w = document.querySelector('[data-testid="resources-float"]');
              const bad = [];
              for (const el of w.querySelectorAll('*')) {
                const cs = getComputedStyle(el);
                if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1)
                  bad.push(el.textContent.trim().slice(0, 40));
              }
              const sc = w.querySelector('.overflow-y-auto');
              return {ellipsis: bad, hscroll: sc ? sc.scrollWidth > sc.clientWidth + 1 : false,
                      page: document.documentElement.scrollWidth > window.innerWidth};
            }""")
            check("7. pencerede kırpma/yatay taşma yok",
                  not clip["ellipsis"] and not clip["hscroll"] and not clip["page"], str(clip))
            os.makedirs(SHOTS, exist_ok=True)
            page.screenshot(path=os.path.join(SHOTS, "resources_float_light.png"))

            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2500)
            b2 = box(page, FLOAT)
            check("8. yenilemede ayrık + aynı yerde",
                  b2 is not None and abs(b2["x"] - b1["x"]) < 2 and abs(b2["y"] - b1["y"]) < 2,
                  f"{b1} vs {b2}")

            page.evaluate("localStorage.setItem('lgs-theme','dark')")
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2500)
            page.evaluate("document.documentElement.classList.add('dark')")
            open_float_book(page, ids)
            m = measure(page, f'{FLOAT} [data-testid="resource-section"], {FLOAT} [data-testid="resources-float-handle"]', min_ratio=4.5)
            check("9. koyu temada metin okunur (≥4.5)", m["bad"] == 0, str(m["worst"][:4]))
            page.screenshot(path=os.path.join(SHOTS, "resources_float_dark.png"))
            page.evaluate("localStorage.setItem('lgs-theme','light')")

            page.click('[data-testid="resources-dock"]')
            page.wait_for_timeout(600)
            check("10. 'Panele koy' → pencere kapandı, panelde",
                  page.query_selector(FLOAT) is None
                  and page.query_selector('[data-docked-panel] [data-section="week:resources"]') is not None)

            page.click('[data-testid="resources-detach"]')
            page.wait_for_timeout(500)
            page.click('[data-rail="week:resources"]')
            page.wait_for_timeout(500)
            check("11. şerit simgesi pencereyi panele geri koyar", page.query_selector(FLOAT) is None)

            fab = '[data-section="week:video-basket-fab"]'
            f0 = box(page, fab)
            drag(page, fab, -600, -300)
            f1 = box(page, fab)
            opened = page.query_selector('[data-section="week:video-basket"]') is not None
            check("12. Video Sepeti düğmesi sürüklenince taşınıyor (ve açılmıyor)",
                  f1["x"] < f0["x"] - 500 and f1["y"] < f0["y"] - 200 and not opened,
                  f"{f0['x']:.0f},{f0['y']:.0f} -> {f1['x']:.0f},{f1['y']:.0f} açıldı={opened}")
            page.click(fab)
            page.wait_for_timeout(600)
            check("13. düğmeye tıklayınca sepet açılıyor",
                  page.query_selector('[data-section="week:video-basket"]') is not None)
            page.click('[data-section="week:video-basket"] button[aria-label="Kapat"]')
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2500)
            f2 = box(page, fab)
            check("14. düğmenin yeri yenilemede kalıyor",
                  abs(f2["x"] - f1["x"]) < 2 and abs(f2["y"] - f1["y"]) < 2, f"{f1} vs {f2}")
            b.close()
    finally:
        cleanup(ids)
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
