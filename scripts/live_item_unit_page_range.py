"""Canlı — gün gün Test formu: tüm dersler + kaynaksız birim (sayfa/soru) + sayfa aralığı (2026-10-22).

  1 ders listesi TEK parça: kitabı olan ders "· kitabı var" notuyla, kitapsız dersler de listede
  2 kitaplı derste Kaynak kutusunda "Kaynaksız" seçilebilir → konu seçilince birim/not/aralık paneli
  3 Sayfa + "Hız Fen" + 45–50 → adet "6 sayfa" → kayıt: unit sayfa, s.45–50, label Hız Fen
  4 aynı kaynak yeniden: "Son verilen s. 45–50" + "51. sayfadan devam et" → tıklayınca başlangıç 51
  5 öğrenci Bugün'de "s. 45–50" görünür, "sayfa" birimi
  6 koyu tema kontrast + 390px taşma yok
Ön koşul: backend :8081 + Next :3000.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, StudentBook, Subject, Task, TaskBookItem, User, UserRole,
)
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lupr_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
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


def seed():
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Sayfa Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Sayfa Öğrenci",
                 role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                 grade_level=8)
        db.add(s)
        db.flush()
        fen = (db.query(Subject).filter(Subject.name == "Fen Bilimleri", Subject.is_builtin.is_(True),
                                        Subject.curriculum_model == "lgs").first()
               or db.query(Subject).filter(Subject.name == "Fen Bilimleri", Subject.is_builtin.is_(True)).first())
        bk = Book(teacher_id=coach.id, subject_id=fen.id, name=f"Hız Fen {PFX}", type=BookType.SORU_BANKASI)
        db.add(bk)
        db.flush()
        db.add(BookSection(book_id=bk.id, label="Mevsimler", test_count=5, order=1))
        db.add(StudentBook(student_id=s.id, book_id=bk.id))
        db.commit()
        return {"coach": coach.id, "s": s.id, "book": bk.id, "fen": fen.id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["s"], d["coach"]]
        tids = [t.id for t in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == d["s"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == d["book"]))
        db.execute(sa_delete(Book).where(Book.id == d["book"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)


def dismiss(page):
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(800)


def open_form(page, d):
    page.goto(f"{WEB}/teacher/students/{d['s']}/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    dismiss(page)
    for sel in ('text="Yeni görev ekle"', 'text="Görev ekle"'):
        el = page.query_selector(sel)
        if el:
            el.click()
            page.wait_for_timeout(1000)
            break
    page.click('text="Ayrıntılı form"')
    page.wait_for_timeout(1200)


def pick_sourceless_topic(page):
    selects = page.locator("form select")
    subj = selects.nth(0)
    fen = next(o for o in subj.locator("option").all_inner_texts() if o.startswith("Fen Bilimleri"))
    subj.select_option(label=fen)
    page.wait_for_timeout(2000)
    selects.nth(1).select_option(value="none")
    page.wait_for_timeout(1500)
    panel = page.locator('[data-testid="topic-picker-panel"]')
    if panel.count() == 0:
        page.click('button[aria-label="Müfredat konusu seç"]')
        page.wait_for_timeout(1200)
    first = panel.locator("button.block").first
    name = first.inner_text().strip()
    first.click()
    page.wait_for_timeout(600)
    return name


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(".shots", exist_ok=True)
    d = seed()
    print(f"\n=== canlı: birim + sayfa aralığı — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="light")
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            login(page, f"{PFX}_t@test.invalid")
            open_form(page, d)
            opts = page.locator("form select").nth(0).locator("option").all_inner_texts()
            fen_opt = next((o for o in opts if o.startswith("Fen Bilimleri")), "")
            check("1 ders listesi tek parça: Fen '· kitabı var' + kitapsız dersler de var",
                  "kitabı var" in fen_opt and len(opts) > 3
                  and page.locator("form select optgroup").count() == 0, str(opts[:6]))

            topic_name = pick_sourceless_topic(page)
            box = page.locator('[data-section="task-form:sourceless-options"]')
            check("2 kitaplı derste kaynaksız konu → birim/not paneli", box.count() == 1, topic_name)
            box.locator('button[role="radio"]:has-text("Sayfa")').click()
            page.locator('input[aria-label="Kitap adı notu"]').fill("Hız Fen")
            page.locator('input[aria-label="Başlangıç sayfası"]').fill("45")
            page.locator('input[aria-label="Bitiş sayfası"]').fill("50")
            page.wait_for_timeout(500)
            adet = page.locator('[aria-label="Sayfa adedi"]').inner_text()
            check("3a adet aralıktan: 6 sayfa", "6 sayfa" in adet, adet)
            page.screenshot(path=".shots/task_form_page_range_light.png")
            page.locator('form button[type="submit"]').last.click()
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                t = db.query(Task).filter(Task.student_id == d["s"]).order_by(Task.id.desc()).first()
                it = t.book_items[0] if t and t.book_items else None
                tdate = t.date if t else None
            check("3b kayıt: unit sayfa · s.45–50 · 6 · label Hız Fen",
                  it is not None and it.unit == "sayfa" and it.page_from == 45 and it.page_to == 50
                  and it.planned_count == 6 and it.label == "Hız Fen" and it.topic_id is not None,
                  str(it and (it.unit, it.page_from, it.page_to, it.label)))
            check("3d ders dağılımı sayfa görevini test saymaz",
                  "6 test" not in page.inner_text("body"), "")
            check("3c başlık 'Konu (Hız Fen): s. 45–50'", t is not None and t.title.endswith("(Hız Fen): s. 45–50"),
                  str(t and t.title))

            # 4 devam önerisi
            open_form(page, d)
            pick_sourceless_topic(page)
            box = page.locator('[data-section="task-form:sourceless-options"]')
            box.locator('button[role="radio"]:has-text("Sayfa")').click()
            page.locator('input[aria-label="Kitap adı notu"]').fill("Hız Fen")
            page.wait_for_timeout(1500)
            sug = page.locator('[data-section="task-form:page-suggestion"]')
            check("4a 'Son verilen s. 45–50' görünür", sug.count() == 1 and "45–50" in sug.inner_text(),
                  sug.inner_text() if sug.count() else "yok")
            page.locator('button:has-text("51. sayfadan devam et")').click()
            page.wait_for_timeout(300)
            check("4b devam → başlangıç 51",
                  page.locator('input[aria-label="Başlangıç sayfası"]').input_value() == "51")
            sw = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("4c yatay taşma yok", sw <= 1, str(sw))

            check("4d koç sayfasında konsol hatası yok", not errs, str(errs[:3]))
            # koyu tema kontrast
            page.emulate_media(color_scheme="dark")
            page.wait_for_timeout(600)
            page.screenshot(path=".shots/task_form_page_range_dark.png")
            res = measure(page, '[data-section="task-form:sourceless-options"]', min_ratio=4.5)
            check("6a koyu tema: panel metinleri okunur (4,5)", res["bad"] == 0, str(res["worst"][:3]))

            # 390px
            page.set_viewport_size({"width": 390, "height": 900})
            page.wait_for_timeout(800)
            sw = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("6b 390px yatay taşma yok", sw <= 1, str(sw))
            page.screenshot(path=".shots/task_form_page_range_mobile.png", full_page=False)

            # 5 öğrenci
            ctx = b.new_context(viewport={"width": 1280, "height": 900})
            sp = ctx.new_page()
            login(sp, f"{PFX}_s@test.invalid")
            sp.goto(f"{WEB}/student/day?date={tdate.isoformat() if tdate else date.today().isoformat()}",
                    wait_until="networkidle")
            sp.wait_for_timeout(2500)
            dismiss(sp)
            body = sp.inner_text("body")
            check("5 öğrenci gününde 's. 45–50' görünür", "s. 45–50" in body, body[:300])
            sp.screenshot(path=".shots/student_page_range.png")
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
