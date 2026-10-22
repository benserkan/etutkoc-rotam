"""Canlı — "Görevi düzenle" penceresi: kaynaksız konulu görev (2026-10-22).

  1 sayfa görevi açılınca pencere dolu: Kaynaksız · konu · birim sayfa · not · s.45–50
  2 aralığı 51–55 yap → kaydet → kayıt s.51–55 + başlık
  3 birimi soru · miktar 3 çipi → kaydet → unit soru, adet 3, aralık yok
  4 kitaplı görev: Kaynak listesinde kitap seçili + "Kaynaksız" seçeneği var
  5 koyu tema kontrast (4,5) · 390px taşma yok · ellipsis yok · konsol temiz
Ön koşul: backend :8081 + Next :3000.
"""
from __future__ import annotations

import os
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Book, BookSection, BookType, StudentBook, Task, TaskBookItem, TaskType  # noqa: E402
from scripts import live_quick_add_seed as L  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

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


def seed_tasks(d):
    with SessionLocal() as db:
        t = Task(student_id=d["s"], date=date.today(), type=TaskType.TEST, title=f"{d['tname']} (Hız Fen): s. 45–50",
                 is_draft=False)
        t.book_items = [TaskBookItem(book_id=None, book_section_id=None, topic_id=d["topic"], label="Hız Fen",
                                     planned_count=6, completed_count=0, unit="sayfa", page_from=45, page_to=50)]
        db.add(t)
        book = Book(teacher_id=d["coach"], subject_id=d["fen"], name="Canlı Fen Soru Bankası",
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label="Basınç Testleri", test_count=10, order=1)
        db.add(sec)
        db.flush()
        db.add(StudentBook(student_id=d["s"], book_id=book.id))
        bt = Task(student_id=d["s"], date=date.today(), type=TaskType.TEST, title="Canlı Fen — Basınç: 2 test",
                  is_draft=False)
        bt.book_items = [TaskBookItem(book_id=book.id, book_section_id=sec.id, planned_count=2, completed_count=0,
                                      reservation_released_at=None)]
        db.add(bt)
        db.commit()
        d.update({"tid": t.id, "btid": bt.id, "book": book.id, "sec": sec.id})


def cleanup_extra(d):
    from sqlalchemy import delete as sa_delete

    from app.models import SectionProgress

    with SessionLocal() as db:
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.book_id == d["book"]).all()]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id == d["s"]).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
            db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbs)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == d["book"]))
        db.execute(sa_delete(Book).where(Book.id == d["book"]))
        db.commit()


def item(tid):
    with SessionLocal() as db:
        t = db.get(Task, tid)
        return t.title, t.book_items[0]


def open_edit(page, d, title_part):
    page.goto(f"{L.WEB}/teacher/students/{d['s']}/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(600)
    row = page.locator(f'[data-task-id]:has-text("{title_part}")').first
    if row.count() == 0:
        row = page.locator(f'div:has(> * button[aria-label="Düzenle"]):has-text("{title_part}")').last
    row.hover()
    row.locator('button[aria-label="Düzenle"]').first.click()
    page.wait_for_timeout(1500)
    return page.locator('form[aria-label="Görev düzenleme"]')


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(".shots", exist_ok=True)
    d = L.seed()
    seed_tasks(d)
    print(f"\n=== canlı: görevi düzenle — kaynaksız — {L.PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="light")
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.goto(f"{L.WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{L.PFX}_t@test.invalid")
            page.fill('input[name="password"]', L.PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            f = open_edit(page, d, "Hız Fen")
            book_txt = f.locator('select[id^="te-book-"] option:checked').inner_text()
            topic_txt = f.locator('button[aria-label="Müfredat konusu seç"]').inner_text()
            unit_on = f.locator('[role="radiogroup"][aria-label="Birim"] [aria-checked="true"]').inner_text()
            note = f.locator('input[aria-label="Kitap adı notu"]').input_value()
            pf = f.locator('input[aria-label="Başlangıç sayfası"]').input_value()
            pt = f.locator('input[aria-label="Bitiş sayfası"]').input_value()
            check("1 pencere dolu: Kaynaksız · konu · sayfa · not · 45–50",
                  "Kaynaksız" in book_txt and d["tname"] in topic_txt and "Sayfa" in unit_on
                  and note == "Hız Fen" and pf == "45" and pt == "50",
                  f"{book_txt}|{topic_txt}|{unit_on}|{note}|{pf}-{pt}")
            page.screenshot(path=".shots/task_edit_sourceless_light.png")
            sug = f.locator('[data-section="task-form:page-suggestion"]')
            check("1b devam önerisi düzenlenen görevin kendisini göstermez", sug.count() == 0,
                  sug.inner_text() if sug.count() else "")

            f.locator('input[aria-label="Başlangıç sayfası"]').fill("51")
            f.locator('input[aria-label="Bitiş sayfası"]').fill("55")
            f.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            title, it = item(d["tid"])
            check("2 kayıt s.51–55 (adet 5) + başlık",
                  it.page_from == 51 and it.page_to == 55 and it.planned_count == 5 and title.endswith("s. 51–55"),
                  f"{title} {it.page_from}-{it.page_to}")

            f = open_edit(page, d, "Hız Fen")
            f.locator('[role="radiogroup"][aria-label="Birim"] button:has-text("Soru")').click()
            f.locator('[role="group"][aria-label="Miktar"] button:has-text("3")').first.click()
            f.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            title, it = item(d["tid"])
            check("3 birim soru · 3 · aralık temizlendi",
                  it.unit == "soru" and it.planned_count == 3 and it.page_from is None, f"{title} {it.unit}")

            f = open_edit(page, d, "Basınç")
            sel = f.locator('select[id^="te-book-"]')
            opts = sel.locator("option").all_inner_texts()
            cur = sel.locator("option:checked").inner_text()
            check("4 kitaplı görev: kitap seçili + Kaynaksız seçeneği var",
                  cur == "Canlı Fen Soru Bankası" and any("Kaynaksız" in o for o in opts), f"{cur} {opts}")

            page.emulate_media(color_scheme="dark")
            page.wait_for_timeout(600)
            res = measure(page, 'form[aria-label="Görev düzenleme"]', min_ratio=4.5)
            check("5a koyu tema metinleri okunur (4,5)", res["bad"] == 0, str(res["worst"][:3]))
            page.screenshot(path=".shots/task_edit_dark.png")
            ell = page.evaluate("""() => [...document.querySelectorAll('form[aria-label="Görev düzenleme"] *')]
              .filter(e => e.children.length===0 && e.scrollWidth > e.clientWidth + 1
                && getComputedStyle(e).textOverflow==='ellipsis').length""")
            check("5b kırpılmış metin yok", ell == 0, str(ell))
            page.keyboard.press("Escape")
            page.set_viewport_size({"width": 390, "height": 900})
            f = open_edit(page, d, "Hız Fen")
            sw = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("5c 390px yatay taşma yok", sw <= 1, str(sw))
            page.screenshot(path=".shots/task_edit_mobile.png", full_page=True)
            check("5d konsol hatası yok", not errs, str(errs[:3]))
            b.close()
    finally:
        cleanup_extra(d)
        L.cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for x in failed:
        print("  -", x)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
