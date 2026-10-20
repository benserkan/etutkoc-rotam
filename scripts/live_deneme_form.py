"""Canlı — koç Deneme formu (D1, 2026-10-20).

  1 Deneme formu açılır; ders listesinde deneme kitabı olan ders başta
  2 Kaynak hazır seçili, "Verilecek: DENEME 1", soru 6 (sınavdaki soru sayısı)
  3 Adet 2 → "DENEME 1, DENEME 2" + düğme "Ekle · 2 deneme"
  4 Ekle → DB: 1 görev, 2 deneme kalemi (exam_kind brans, 6 soru)
  5 Gün kartında satır "2 deneme · 6 soru" (soru değil deneme)
  6 Kalıp çipi görünür → tek tıkla DENEME 3, 4
  7 Kaynaksız branş (özel ders 20 soru, ad) → kitapsız + dersli
  8 Genel → TYT 120 soru
  9 Ayrıntılı form Test + deneme kitabı → "Adet (deneme)"
 10 Form taşma/kırpma yok · koyu tema + 390px ekran görüntüsü
Ön koşul: backend :8081 + Next :3000.
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, SectionProgress, StudentBook, Subject, Task, TaskBookItem, User, UserRole,
)
from app.models.book import BookType  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"ldf_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Deneme Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Deneme Öğrenci",
                 role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                 grade_level=12, track=Track.SAYISAL)
        db.add(s); db.flush()
        bio = Subject(name="TYT Biyoloji", teacher_id=coach.id, order=1, exam_section=ExamSection.TYT)
        db.add(bio); db.flush()
        book = Book(name=f"{PFX} Bio Branş Denemeleri", teacher_id=coach.id, subject_id=bio.id,
                    type=BookType.BRANS_DENEMESI)
        db.add(book); db.flush()
        db.add_all([BookSection(book_id=book.id, label=f"DENEME {i}", order=i, test_count=1) for i in range(1, 7)])
        db.add(StudentBook(student_id=s.id, book_id=book.id))
        db.commit()
        return {"coach": coach.id, "s": s.id, "bio": bio.id, "book": book.id}


def cleanup(d):
    with SessionLocal() as db:
        tids = [t.id for t in db.query(Task).filter(Task.student_id == d["s"]).all()]
        if tids:
            db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
            db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
        sbs = [x.id for x in db.query(StudentBook).filter(StudentBook.student_id == d["s"]).all()]
        if sbs:
            db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbs)).delete(synchronize_session=False)
            db.query(StudentBook).filter(StudentBook.id.in_(sbs)).delete(synchronize_session=False)
        db.query(BookSection).filter(BookSection.book_id == d["book"]).delete(synchronize_session=False)
        db.query(Book).filter(Book.id == d["book"]).delete(synchronize_session=False)
        db.query(Subject).filter(Subject.teacher_id == d["coach"]).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_([d["s"], d["coach"]])).delete(synchronize_session=False)
        db.commit()


def exam_tasks(d):
    with SessionLocal() as db:
        out = []
        for t in db.query(Task).filter(Task.student_id == d["s"]).order_by(Task.id).all():
            out.append([(i.exam_kind, i.book_id, i.book_section_id, i.subject_id, i.question_count,
                         i.planned_count) for i in t.book_items])
        return out


def open_form(page):
    f = page.locator('form[aria-label="Deneme ekleme"]')
    if f.count() and f.first.is_visible():
        return f
    for sel in ('text="Yeni görev ekle"', 'text="Görev ekle"'):
        el = page.query_selector(sel)
        if el and el.is_visible():
            el.click()
            page.wait_for_timeout(800)
            break
    tile = page.locator("button", has_text="Deneme").filter(has_not_text="Deneme ").first
    page.locator('button:text-is("Deneme")').first.click()
    page.wait_for_timeout(1500)
    return page.locator('form[aria-label="Deneme ekleme"]')


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOTS, exist_ok=True)
    d = seed()
    print(f"\n=== canlı: Deneme formu — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 950}, color_scheme="dark")
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{PFX}_t@test.invalid")
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{d['s']}/week", wait_until="networkidle")
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(800)

            form = open_form(page)
            check("1a Deneme formu açıldı", form.count() == 1)
            subj = form.locator('select[aria-label="Ders"]')
            first_opt = subj.locator("option").first.inner_text() if subj.count() else ""
            check("1b deneme kitabı olan ders başta", "TYT Biyoloji" in first_opt and "kitap" in first_opt,
                  first_opt)
            src = form.locator('[role="radiogroup"][aria-label="Kaynak"] [aria-checked="true"]').inner_text()
            check("2a kaynak hazır seçili", "Bio Branş" in src, src)
            check("2b verilecek DENEME 1", "DENEME 1" in form.inner_text())
            qv = form.locator('input[aria-label="Deneme başına soru"]').input_value()
            check("2c soru 6 (sınav standardı)", qv == "6" and "sınavdaki soru sayısı" in form.inner_text(), qv)

            form.locator('button[aria-pressed]:has-text("2")').first.click()
            page.wait_for_timeout(400)
            txt = form.inner_text()
            check("3a DENEME 1, DENEME 2", "DENEME 1, DENEME 2" in txt)
            check("3b düğme 'Ekle · 2 deneme'", form.locator('button[type="submit"]:has-text("Ekle · 2 deneme")').count() == 1)
            # taşma
            ov = page.evaluate("""() => { const f = document.querySelector('form[aria-label="Deneme ekleme"]');
              return f.scrollWidth - f.clientWidth; }""")
            check("10a form yatay taşma yok", ov <= 1, str(ov))
            clip = page.evaluate("""() => {
              const c = document.createElement('canvas').getContext('2d');
              return [...document.querySelectorAll('form[aria-label="Deneme ekleme"] select')].map(s => {
                const cs = getComputedStyle(s); c.font = cs.fontSize + ' ' + cs.fontFamily;
                const t = s.options[s.selectedIndex]?.text || '';
                return {t, over: c.measureText(t).width - (s.clientWidth - 40)};
              }).filter(x => x.over > 0);
            }""")
            check("10c seçili seçenek metni kırpılmıyor", clip == [], str(clip))
            form.screenshot(path=os.path.join(SHOTS, "deneme_form_dark.png"))

            form.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            et = exam_tasks(d)
            ok4 = len(et) == 1 and len(et[0]) == 2 and all(x[0] == "brans" and x[4] == 6 and x[5] == 1 for x in et[0])
            check("4 DB: 1 görev, 2 deneme kalemi, 6 soru", ok4, str(et))
            body = page.inner_text("body")
            check("5 gün kartında '2 deneme · 6 soru'", "2 deneme · 6 soru" in body)
            check("5b gün başlığı '2 deneme' (kalem sayısı)", "· 2 deneme" in body, "")

            form = open_form(page)
            chip = form.locator("button:has-text('TYT Biyoloji branş ×2')")
            check("6a kalıp çipi görünür", chip.count() >= 1, form.inner_text()[:300])
            if chip.count():
                chip.first.click()
                page.wait_for_timeout(2500)
                et = exam_tasks(d)
                with SessionLocal() as db:
                    labels = [db.get(BookSection, x[2]).label for x in et[-1]] if len(et) > 1 else []
                check("6b tek tıkla DENEME 3, 4", labels == ["DENEME 3", "DENEME 4"], str(labels))

            form = open_form(page)
            form.locator('[role="radiogroup"][aria-label="Kaynak"] [role="radio"]:has-text("Kaynaksız")').click()
            page.wait_for_timeout(300)
            form.locator('input[aria-label="Deneme başına soru"]').fill("20")
            form.locator('input[placeholder^="örn. Özel ders"]').fill("Özel ders biyoloji")
            form.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            et = exam_tasks(d)
            last = et[-1] if et else []
            check("7 kaynaksız branş: kitapsız + dersli + 20 soru",
                  len(last) == 1 and last[0][1] is None and last[0][3] == d["bio"] and last[0][4] == 20, str(last))

            form = open_form(page)
            form.locator('[role="radio"]:has-text("Genel deneme")').click()
            page.wait_for_timeout(300)
            form.locator('select[aria-label="Genel deneme türü"]').select_option("tyt")
            page.wait_for_timeout(200)
            form.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            last = exam_tasks(d)[-1]
            check("8 genel TYT 120 soru", len(last) == 1 and last[0][0] == "genel" and last[0][4] == 120, str(last))

            # 9 ayrıntılı form Test + deneme kitabı
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2500)
            lt = page.query_selector('button:has-text("Daha sonra")')
            if lt:
                lt.click(); page.wait_for_timeout(600)
            page.locator('text="Yeni görev ekle"').first.click()
            page.wait_for_timeout(1200)
            page.locator('text="Ayrıntılı form"').first.click()
            page.wait_for_timeout(1200)
            page.screenshot(path=os.path.join(SHOTS, "deneme_test_form0.png"), full_page=False)
            for k, sl in enumerate(page.locator("form select:visible").all()):
                print("   select", k, sl.locator("option").all_inner_texts()[:6])
            try:
                sel_subj = page.locator("form select:visible").filter(
                    has=page.locator("option", has_text="TYT Biyoloji")).first
                sel_subj.select_option(label=next(o for o in sel_subj.locator("option").all_inner_texts()
                                                  if o.startswith("TYT Biyoloji")))
                page.wait_for_timeout(1200)
                sel_book = page.locator("form select:visible").filter(
                    has=page.locator("option", has_text="Bio Branş")).first
                sel_book.select_option(label=next(o for o in sel_book.locator("option").all_inner_texts()
                                                  if "Bio Branş" in o))
                page.wait_for_timeout(1500)
                bt = page.inner_text("body")
                i = bt.find("Adet (")
                page.screenshot(path=os.path.join(SHOTS, "deneme_test_form.png"), full_page=True)
                check("9 Test formunda 'Adet (deneme)'", "adet (deneme)" in bt.lower(), bt[max(0, i - 200):i + 40])
            except Exception as e:  # noqa: BLE001
                check("9 Test formunda 'Adet (deneme)'", False, str(e)[:300])

            # 390px
            m = b.new_page(viewport={"width": 390, "height": 900}, color_scheme="light")
            errs: list[str] = []
            m.on("console", lambda msg: errs.append(msg.text) if msg.type == "error" else None)
            m.context.add_cookies(page.context.cookies())
            m.goto(f"{WEB}/teacher/students/{d['s']}/week", wait_until="networkidle")
            m.wait_for_timeout(2500)
            lt = m.query_selector('button:has-text("Daha sonra")')
            if lt:
                lt.click(); m.wait_for_timeout(600)
            f2 = open_form(m)
            ov2 = m.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("10b 390px sayfa yatay kaydırma yok", ov2 <= 1, str(ov2))
            if f2.count():
                f2.screenshot(path=os.path.join(SHOTS, "deneme_form_mobile.png"))
            m.wait_for_timeout(1500)
            check("10d konsol hatası yok", not errs, " | ".join(errs)[:400])
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
