"""Kaynak Durumu: "SON" işareti + 4 kademeli ısı haritası + Video Sepeti taşıma
— GERÇEK TARAYICI (2026-10-08).

Senaryolar:
  1. Kitap başlığında "SON <ünite> · <tarih>" — kitap sırasında ortadaki ünite
  2. O ünite satırında dolgulu SON etiketi (yalnız bir satırda)
  3. Isı kademeleri: 0/10 → 0 · 3/10 → 1 · 6/10 → 2 · 10/10 → 3 (+ ✓)
  4. Kademe zeminleri birbirinden ayrışır (ΔE ≥ 5), kademe 0 renksiz
  5. Açık + koyu temada ünite satırlarında metin okunur (kontrast ≥ 4.5)
  6. Video Sepeti düğmesi Rota'ya sor düğmesiyle ÇAKIŞMAZ
  7. Video Sepeti penceresi başlığından taşınır
  8. Sayfa yenilenince pencere aynı yerde açılır
Ekran görüntüleri: .shots/resource_heat_{light,dark}.png · video_basket_moved.png
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
PFX = f"rht_{secrets.token_hex(3)}"
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


def open_book(page, ids) -> None:
    page.click('[data-section="week:resources"] .resource-subject > button')
    page.wait_for_timeout(800)
    page.click(f'[data-section="week:resources"] button:has-text("{ids["book_name"]}")')
    page.wait_for_timeout(800)


def main() -> int:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    ids = seed()
    print(f"\n=== Kaynak Durumu ısı haritası + SON (öğrenci #{ids['student']}) ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            # Konum kaydı YALNIZ ilk yüklemede silinir (yenilemede kalmalı — 8. senaryo)
            ctx.add_init_script(
                "try{localStorage.setItem('lgs-theme','light');"
                "if(!sessionStorage.getItem('rht-init')){"
                "localStorage.removeItem('rotam:float:video-basket');"
                "sessionStorage.setItem('rht-init','1')}}catch(e){}")
            page = ctx.new_page()
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            url = f"{WEB}/teacher/students/{ids['student']}/week"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(800)
            page.wait_for_selector('[data-section="week:resources"]', timeout=15000)
            open_book(page, ids)

            # 1
            head = page.inner_text('[data-testid="book-last-task"]')
            check("1. kitap başlığında 'SON Basınç · <dün>'",
                  "SON" in head and LAST in head and ids["last_label"] in head, head)
            # 2
            lasts = page.query_selector_all('[data-testid="resource-section"][data-last="1"]')
            check("2. yalnız Basınç satırında SON etiketi",
                  len(lasts) == 1 and LAST in lasts[0].inner_text()
                  and lasts[0].query_selector('[data-testid="section-last-badge"]') is not None,
                  f"{len(lasts)}")
            # 3
            rows = page.query_selector_all('[data-testid="resource-section"]')
            levels = [r.get_attribute("data-heat") for r in rows]
            done_mark = "✓" in rows[3].inner_text()
            check("3. kademeler 0/1/2/3 (+ biten üniteye ✓)",
                  levels == ["0", "1", "2", "3"] and done_mark, f"{levels} ✓={done_mark}")

            def bg_colors():
                out = []
                for r in page.query_selector_all('[data-testid="resource-section"]'):
                    r.scroll_into_view_if_needed()
                    bb = r.bounding_box()
                    shot = page.screenshot(clip={"x": bb["x"] + 3, "y": bb["y"] + bb["height"] - 5,
                                                 "width": 20, "height": 3})
                    im = Image.open(io.BytesIO(shot)).convert("RGB")
                    px = [im.getpixel((x, y)) for x in range(im.width) for y in range(im.height)]
                    out.append(max(set(px), key=px.count))
                return out

            cols = bg_colors()
            steps = [round(delta_e(cols[i], cols[i + 1]), 1) for i in range(3)]
            check("4. açık tema: kademe zeminleri ayrışır (komşu ΔE ≥ 5)",
                  min(steps) >= 5, f"{steps}")
            mres = measure(page, '[data-testid="resource-section"]', min_ratio=4.5)
            bad = mres["bad"]
            check("5a. açık tema: ünite satırlarında metin okunur (≥ 4.5)", bad == 0, f"{bad} {mres['worst']}")
            os.makedirs(SHOTS, exist_ok=True)
            page.query_selector('[data-section="week:resources"]').screenshot(
                path=os.path.join(SHOTS, "resource_heat_light.png"))

            # 6. Video Sepeti ↔ Rota
            fab = page.query_selector('[data-section="week:video-basket-fab"]').bounding_box()
            rota = page.query_selector('button:has-text("Rota")')
            rb = rota.bounding_box() if rota else None
            overlap = bool(rb) and not (fab["x"] + fab["width"] <= rb["x"] or rb["x"] + rb["width"] <= fab["x"]
                                        or fab["y"] + fab["height"] <= rb["y"] or rb["y"] + rb["height"] <= fab["y"])
            check("6. Video Sepeti düğmesi Rota düğmesiyle çakışmıyor", rb is not None and not overlap,
                  f"fab={fab} rota={rb}")

            # 7. taşı
            page.click('[data-section="week:video-basket-fab"]')
            page.wait_for_timeout(1000)
            w0 = page.query_selector('[data-section="week:video-basket"]').bounding_box()
            h = page.query_selector('[data-testid="video-basket-handle"]').bounding_box()
            sx, sy = h["x"] + 140, h["y"] + h["height"] / 2
            page.mouse.move(sx, sy)
            page.mouse.down()
            page.mouse.move(sx - 600, sy - 150, steps=12)
            page.mouse.up()
            page.wait_for_timeout(500)
            w1 = page.query_selector('[data-section="week:video-basket"]').bounding_box()
            moved = abs((w0["x"] - w1["x"]) - 600) <= 3 and abs((w0["y"] - w1["y"]) - 150) <= 3
            page.screenshot(path=os.path.join(SHOTS, "video_basket_moved.png"))
            check("7. Video Sepeti penceresi başlığından taşındı (600 sola, 150 yukarı)", moved,
                  f"{w0['x']:.0f},{w0['y']:.0f} → {w1['x']:.0f},{w1['y']:.0f}")

            # 8. yenile → aynı yer
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(2500)
            page.click('[data-section="week:video-basket-fab"]')
            page.wait_for_timeout(1000)
            w2 = page.query_selector('[data-section="week:video-basket"]').bounding_box()
            check("8. yenilemeden sonra pencere aynı yerde açıldı",
                  abs(w2["x"] - w1["x"]) <= 2 and abs(w2["y"] - w1["y"]) <= 2,
                  f"{w1['x']:.0f},{w1['y']:.0f} vs {w2['x']:.0f},{w2['y']:.0f}")
            page.click('[data-section="week:video-basket"] button[aria-label="Kapat"]')
            page.wait_for_timeout(400)

            # 5b koyu tema
            page.evaluate("() => { document.documentElement.classList.remove('light'); document.documentElement.classList.add('dark'); }")
            page.wait_for_timeout(800)
            if not page.query_selector('[data-testid="resource-section"]'):
                open_book(page, ids)
            colsd = bg_colors()
            stepsd = [round(delta_e(colsd[i], colsd[i + 1]), 1) for i in range(3)]
            check("4b. koyu tema: kademe zeminleri ayrışır (komşu ΔE ≥ 5)",
                  min(stepsd) >= 5, f"{stepsd}")
            mresd = measure(page, '[data-testid="resource-section"]', min_ratio=4.5)
            badd = mresd["bad"]
            check("5b. koyu tema: ünite satırlarında metin okunur (≥ 4.5)", badd == 0, f"{badd} {mresd['worst']}")
            page.query_selector('[data-section="week:resources"]').screenshot(
                path=os.path.join(SHOTS, "resource_heat_dark.png"))
            b.close()
    finally:
        cleanup(ids)
    print(f"\n{passed} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
