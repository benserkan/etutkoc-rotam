"""Kaynak Durumu ALT PANEL — GERÇEK TARAYICI (2026-10-08, koç denemesi).

Koç: program hazırlarken Hafta Izgarası ↔ Kaynak Durumu arasında sürekli
yukarı-aşağı kaydırıyor. Kaynak Durumu sayfanın altına yapışık panel olur.

Senaryolar:
  1. Varsayılan: alt panel görünür, sağ panelde Kaynak Durumu yok
  2. Sayfanın EN ÜSTÜNDE de panel ekranın altında görünür (ızgara + panel birlikte)
  3. Izgara genişliği alt panel açıkken ve "Yana al" sonrası AYNI (ızgara daralmaz)
  4. Ders seç → kitaplar yan yana; "+" → "Kaç test?" → 2 → görev SEÇİLİ GÜNE yazılır
  5. Üniteyi ızgarada başka güne SÜRÜKLE → orada seçici açılır → 3 → görev O GÜNE
  6. Eklenen gün kısa süre vurgulanır
  7. Yükseklik üst kenardan büyütülür; sayfa yenilenince korunur
  8. Katla → tek çubuk; yenilemede katlı kalır; Aç → geri gelir
  9. Panelde metin kırpılmıyor + sayfada yatay taşma yok
 10. "Yana al" → panel kalkar, sağ panelde Kaynak Durumu + "Alta al" → geri gelir
 11. Koyu tema: panelde okunmayan metin yok
Ekran görüntüleri: .shots/resource_dock_{light,dark}.png
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    SuspiciousIp, Task, TaskBookItem, TaskType, User, UserRole,
)
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"rdk_{secrets.token_hex(3)}"
PWD = "AltPanel!2345"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
TR_DOW = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

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
                     full_name="Alt Panel Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Alt Panel Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        out = {"coach": coach.id, "student": st.id, "subjects": [], "books": [], "sbs": [],
               "sections": {}}
        for nm, books in (("TYT Matematik", ["Orijinal TYT Matematik", "3D TYT Matematik"]),
                          ("TYT Kimya", ["Aydın TYT Kimya"])):
            s = Subject(name=nm, teacher_id=coach.id, order=len(out["subjects"]) + 1)
            db.add(s)
            db.flush()
            out["subjects"].append(s.id)
            for bn in books:
                b = Book(name=f"{bn} {PFX}", teacher_id=coach.id, subject_id=s.id,
                         type=BookType.SORU_BANKASI)
                db.add(b)
                db.flush()
                out["books"].append(b.id)
                sb = StudentBook(student_id=st.id, book_id=b.id)
                db.add(sb)
                db.flush()
                out["sbs"].append(sb.id)
                for i, lab in enumerate(("Problemler", "Sayı Basamakları",
                                         "Bölme ve Bölünebilme Kuralları Uzun Başlıklı Ünite")):
                    sec = BookSection(book_id=b.id, label=lab, order=i, test_count=10)
                    db.add(sec)
                    db.flush()
                    db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                                           reserved_count=0, completed_count=0))
                    out["sections"][(bn, lab)] = sec.id
        # Izgarada içerik olsun diye birkaç görev (sayfayı uzatır)
        first_book = out["books"][0]
        first_sec = out["sections"][("Orijinal TYT Matematik", "Problemler")]
        monday = today - timedelta(days=today.weekday())
        for k in range(7):
            d = monday + timedelta(days=k)
            t = Task(student_id=st.id, date=d, type=TaskType.TEST,
                     title=f"Orijinal — Problemler: 1 test", is_draft=False, order=0)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=first_book,
                                book_section_id=first_sec, planned_count=1))
        sp = db.query(SectionProgress).filter(SectionProgress.book_section_id == first_sec).first()
        sp.reserved_count = 7
        db.commit()
        out["email"] = f"{PFX}_t@test.invalid"
        return out


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uid = [ids["coach"], ids["student"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uid)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(ids["sbs"])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(ids["sbs"])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1", "testclient"])))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()


def tasks_on(student: int, d: date, section_id: int) -> int:
    with SessionLocal() as db:
        return (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
                .filter(Task.student_id == student, Task.date == d,
                        TaskBookItem.book_section_id == section_id).count())


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    today = date.today()
    # sürükleme hedefi: bu haftada bugünden sonraki bir gün (yoksa bugün)
    target = today + timedelta(days=1) if today.weekday() < 6 else today
    target_label = TR_DOW[target.weekday()]
    sec_kimya = ids["sections"][("Aydın TYT Kimya", "Sayı Basamakları")]
    sec_orj = ids["sections"][("Orijinal TYT Matematik", "Sayı Basamakları")]
    print(f"\n=== Kaynak Durumu alt panel (öğrenci #{ids['student']}) ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            ctx.add_init_script("try{localStorage.setItem('lgs-theme','light')}catch(e){}")
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
            page.wait_for_selector('[data-testid="resource-dock"]', timeout=15000)

            # 1
            side_res = page.query_selector('[data-docked-panel] :text("Kaynak Durumu")')
            check("1. alt panel görünür, sağ panelde Kaynak Durumu yok", side_res is None)

            # 2
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(400)
            dock = page.query_selector('[data-testid="resource-dock"]').bounding_box()
            grid = page.query_selector('section:has-text("Hafta Izgarası")').bounding_box()
            check("2. sayfanın en üstünde: panel ekranın altında + ızgara aynı anda görünür",
                  abs((dock["y"] + dock["height"]) - 900) <= 2 and grid["y"] < 900 - dock["height"],
                  f"dock={dock} grid_y={grid['y']}")
            grid_w_dock = grid["width"]

            # 4. "+" ile seçili güne ekle
            page.click('[data-testid="resource-dock-subject"]:has-text("Kimya")')
            page.wait_for_timeout(1500)
            n_books = len(page.query_selector_all('[data-testid="resource-dock-book"]'))
            day_txt = page.inner_text('[data-testid="resource-dock-day"]')
            row = page.query_selector('[data-testid="resource-dock-section"]:has-text("Sayı Basamakları")')
            row.query_selector('button[aria-label*="ver"]').click()
            page.wait_for_timeout(400)
            row.query_selector('[data-testid="assign-count-chooser"] button:text-is("2")').click()
            page.wait_for_timeout(2500)
            check("4. Kimya seçili, kitap kartı görünür; '+' → 2 → görev BUGÜNE yazıldı",
                  n_books == 1 and tasks_on(ids["student"], today, sec_kimya) == 1,
                  f"kitap={n_books} gün={day_txt} görev={tasks_on(ids['student'], today, sec_kimya)}")

            # 5. Sürükle-bırak başka güne
            page.click('[data-testid="resource-dock-subject"]:has-text("Matematik")')
            page.wait_for_timeout(1200)
            n_books_mat = len(page.query_selector_all('[data-testid="resource-dock-book"]'))
            src = page.locator('[data-testid="resource-dock-book"]').first.locator(
                '[data-testid="resource-dock-section"]:has-text("Sayı Basamakları")')
            dst = page.locator(f'section:has-text("Hafta Izgarası") button[title^="{target_label} —"]').first
            src.drag_to(dst)
            page.wait_for_timeout(800)
            pop = page.query_selector('[data-testid="grid-resource-drop"]')
            pop_ok = pop is not None and target_label in pop.inner_text()
            if pop:
                pop.query_selector('button:text-is("3")').click()
                page.wait_for_timeout(1000)
            # 6. vurgu
            flash = page.evaluate(f"""() => {{
                const b = [...document.querySelectorAll('button[title^="{target_label} —"]')][0];
                return b ? b.className.includes('ring-emerald-500') : false;
            }}""")
            page.wait_for_timeout(1500)
            check("5. Matematikte 2 kitap yan yana; üniteyi ızgaradaki güne sürükle → seçici → 3 → görev O GÜNE",
                  n_books_mat == 2 and pop_ok and tasks_on(ids["student"], target, sec_orj) == 1,
                  f"kitap={n_books_mat} pop={pop_ok} görev={tasks_on(ids['student'], target, sec_orj)}")
            check("6. eklenen gün ızgarada vurgulandı", flash)

            # 9. kırpma + yatay taşma
            clipped = page.evaluate("""() => [...document.querySelectorAll('[data-testid="resource-dock"] *')]
                .filter(e => e.children.length === 0 && e.scrollWidth > e.clientWidth + 2
                        && getComputedStyle(e).overflowX !== 'auto').length""")
            hscroll = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            check("9. panelde kırpılmış metin yok + sayfada yatay taşma yok",
                  clipped == 0 and not hscroll, f"kırpık={clipped} taşma={hscroll}")
            os.makedirs(SHOTS, exist_ok=True)
            page.screenshot(path=os.path.join(SHOTS, "resource_dock_light.png"))

            # 7. yükseklik
            h0 = page.query_selector('[data-testid="resource-dock"]').bounding_box()["height"]
            hb = page.query_selector('[data-testid="resource-dock-resize"]').bounding_box()
            page.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2)
            page.mouse.down()
            page.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] - 120, steps=8)
            page.mouse.up()
            page.wait_for_timeout(500)
            h1 = page.query_selector('[data-testid="resource-dock"]').bounding_box()["height"]
            page.reload(wait_until="networkidle")
            page.wait_for_selector('[data-testid="resource-dock"]', timeout=15000)
            page.wait_for_timeout(1500)
            h2 = page.query_selector('[data-testid="resource-dock"]').bounding_box()["height"]
            check("7. üst kenardan büyütüldü ve yenilemede korundu",
                  h1 > h0 + 80 and abs(h2 - h1) <= 4, f"{h0:.0f}→{h1:.0f}→{h2:.0f}")

            # 8. katla
            page.click('[data-testid="resource-dock-toggle"]')
            page.wait_for_timeout(400)
            hc = page.query_selector('[data-testid="resource-dock"]').bounding_box()["height"]
            page.reload(wait_until="networkidle")
            page.wait_for_selector('[data-testid="resource-dock"]', timeout=15000)
            page.wait_for_timeout(1200)
            still = page.get_attribute('[data-testid="resource-dock"]', "data-collapsed")
            page.click('[data-testid="resource-dock-toggle"]')
            page.wait_for_timeout(400)
            ho = page.query_selector('[data-testid="resource-dock"]').bounding_box()["height"]
            check("8. katla → tek çubuk, yenilemede katlı; Aç → geri geldi",
                  hc <= 60 and still == "1" and ho > 150, f"katlı={hc:.0f} kalıcı={still} açık={ho:.0f}")

            # 3 + 10. Yana al
            page.click('[data-testid="resource-dock-side"]')
            page.wait_for_timeout(1200)
            gone = page.query_selector('[data-testid="resource-dock"]') is None
            grid_w_side = page.query_selector('section:has-text("Hafta Izgarası")').bounding_box()["width"]
            check("3. ızgara genişliği alt panelde ve yan panelde AYNI (daralmaz)",
                  abs(grid_w_dock - grid_w_side) <= 2, f"{grid_w_dock:.0f} vs {grid_w_side:.0f}")
            to_dock = page.query_selector('[data-testid="resource-to-dock"]')
            check("10a. 'Yana al' → alt panel kalktı, sağ panelde 'Alta al' var",
                  gone and to_dock is not None)
            if to_dock:
                to_dock.click()
                page.wait_for_timeout(1200)
            check("10b. 'Alta al' → alt panel geri geldi",
                  page.query_selector('[data-testid="resource-dock"]') is not None)

            # 11. koyu tema
            page.evaluate("() => { document.documentElement.classList.remove('light'); document.documentElement.classList.add('dark'); }")
            page.wait_for_timeout(800)
            page.click('[data-testid="resource-dock-subject"]:has-text("Kimya")')
            page.wait_for_timeout(1000)
            bad = measure(page, '[data-testid="resource-dock"]', min_ratio=3.0)["bad"]
            page.screenshot(path=os.path.join(SHOTS, "resource_dock_dark.png"))
            check("11. koyu temada panelde okunmayan metin yok (kontrast ≥ 3)", bad == 0, f"{bad}")
            b.close()
    finally:
        cleanup(ids)
    print(f"\n{passed} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
