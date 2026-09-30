"""İskelet F2-4 — problem rutini + kaynak sırası + 2. kaynak: CANLI E2E (dev sunucu + Playwright).

Zeynep Ela deseni: TYT Matematik'te iki satır — konu hattı (Orijinal) + PROBLEM
rutini (Orijinal'den başladı). Orijinal'in problemleri bitiyor; sıradaki soru
bankası Fen Bilimleri. Video destekli defter kitaplıkta ama ana kaynak değil.

   1. Düzenleyici: rutin satırında kapsam "yalnız problemler"; konu satırında
      2. kaynak = Fen Bilimleri; 2. kaynak listesinde video defter YOK
   2. Gün kartı: rutin "rutin · problemler" · konu satırında "konu bitti · kaynak seç"
   3. Problem rutini çipi: Orijinal'in son problem testi + Fen Bilimleri Oran-Orantı,
      kitap adlarıyla; video defter / Polinomlar yok; şeritte kırpma yok
   4. Konu satırı: 2. kaynakta aynı konu İLK çip (otomatik, seçim uyarısı yok) + "sıradaki" alternatif
   5. Rutin çipine tık → iki görev (kitap başına); rutin hayaleti kalkar, konu
      hayaleti kalır (yenilemesiz)
   6. Koyu tema: hayalet bölümü okunur

Ön koşul: backend :8081 + Next :3000.
  PYTHONPATH=. python scripts/live_skeleton_problems.py
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

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.models.book import BookType
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_live_contrast import measure  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lsp_{secrets.token_hex(3)}"
PWD = "SkelPr!2345xy"
SHOT_DIR = os.path.join(os.getcwd(), ".shots")
passed = 0
failed: list[str] = []


def chk(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(f"{name} {extra}")
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    today = date.today()
    hist = [today - timedelta(days=i) for i in range(7, 0, -1)]
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Problem Koç", role=UserRole.TEACHER, is_active=True,
                     must_change_password=False)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Problem Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        mat = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, order=1)
        db.add(mat)
        db.flush()
        topics: dict = {}
        for i, n in enumerate(["Temel Kavramlar", "Oran ve Orantı", "Yaş Problemleri",
                               "Fonksiyonlar", "Polinomlar"]):
            t = Topic(subject_id=mat.id, name=n, order=i + 1, teacher_id=coach.id)
            db.add(t)
            db.flush()
            topics[n] = t
        orj = Book(name=f"{PFX} Orijinal TYT Mat", teacher_id=coach.id, subject_id=mat.id,
                   type=BookType.SORU_BANKASI)
        fen = Book(name=f"{PFX} Fen Bilimleri TYT Mat", teacher_id=coach.id, subject_id=mat.id,
                   type=BookType.SORU_BANKASI)
        vdd = Book(name=f"{PFX} AAA 3D Video Destekli Defter", teacher_id=coach.id,
                   subject_id=mat.id, type=BookType.KONU_ANLATIMLI)
        db.add_all([orj, fen, vdd])
        db.flush()
        secs: dict = {}

        def add(book, key, label, total, order, topic=None):
            x = BookSection(book_id=book.id, label=label, order=order, test_count=total,
                            topic_id=topics[topic].id if topic else None)
            db.add(x)
            db.flush()
            secs[key] = x

        add(orj, "o_temel", "Temel Kavramlar", 4, 0, "Temel Kavramlar")
        add(orj, "o_oran", "Oran - Orantı", 4, 1, "Oran ve Orantı")
        add(orj, "o_yas", "Yaş Problemleri", 4, 2, "Yaş Problemleri")
        add(orj, "o_osym", "ÖSYM'DE ÇIKMIŞ SORULAR (2. BÖLÜM)", 2, 3)
        add(orj, "o_pd", "Problem Denemeleri", 7, 4)
        add(orj, "o_fonk", "Fonksiyon", 4, 5, "Fonksiyonlar")
        add(orj, "o_pol", "Polinomlar", 3, 6, "Polinomlar")
        add(fen, "f_temel", "Temel Kavramlar", 10, 0, "Temel Kavramlar")
        add(fen, "f_oran", "Oran ve Orantı", 10, 1, "Oran ve Orantı")
        add(fen, "f_yas", "Yaş Problemleri", 10, 2, "Yaş Problemleri")
        add(fen, "f_fonk", "Fonksiyonlar", 10, 3, "Fonksiyonlar")
        add(vdd, "v_oran", "Oran - Orantı", 3, 0, "Oran ve Orantı")
        sbs = {}
        for book in (orj, fen, vdd):
            sbs[book.id] = StudentBook(student_id=st.id, book_id=book.id)
            db.add(sbs[book.id])
        db.flush()
        used = {k: 0 for k in secs}

        def task(d, items):
            t = Task(student_id=st.id, date=d, type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            for key, n in items:
                db.add(TaskBookItem(task_id=t.id, book_id=secs[key].book_id,
                                    book_section_id=secs[key].id, planned_count=n))
                used[key] += n
            db.flush()

        plan = ["o_oran", "o_oran", "o_yas", "o_yas", "o_pd", "o_pd", "o_pd"]
        for i, d in enumerate(hist):
            task(d, [(plan[i], 2)])
            if i in (0, 2, 4):
                task(d, [("o_fonk", 2 if i == 4 else 1)])
            if i == 1:
                task(d, [("f_temel", 2)])
        for key, n in used.items():
            if n:
                db.add(SectionProgress(student_book_id=sbs[secs[key].book_id].id,
                                       book_section_id=secs[key].id, completed_count=n,
                                       reserved_count=0))
        out = dict(coach=coach.id, st=st.id, mat=mat.id, orj=orj.id, fen=fen.id, vdd=vdd.id,
                   books=[orj.id, fen.id, vdd.id], sbs=[x.id for x in sbs.values()],
                   topics=[t.id for t in topics.values()], email=coach.email,
                   hist0=hist[0].isoformat(), hist1=hist[-1].isoformat())
        db.commit()
    return out


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id == s["st"]))
        db.execute(sa_delete(WeeklySkeleton).where(WeeklySkeleton.student_id == s["st"]))
        tids = [t.id for t in db.query(Task).filter(Task.student_id == s["st"])]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id == s["st"]))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(s["sbs"])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(s["sbs"])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(s["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(s["books"])))
        db.execute(sa_delete(Topic).where(Topic.id.in_(s["topics"])))
        db.execute(sa_delete(Subject).where(Subject.id == s["mat"]))
        db.execute(sa_delete(User).where(User.id.in_([s["st"], s["coach"]])))
        db.commit()


GH = '[data-section="day:skeleton-ghosts"]'
CLIP_JS = """(sel) => { const s = document.querySelector(sel);
  if (!s) return {clipped: -1, overflow: true};
  const els = [...s.querySelectorAll('*')].filter(e =>
    getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1);
  return {clipped: els.length, overflow: s.scrollWidth > s.clientWidth + 1}; }"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    s = seed()
    sid = s["st"]
    print(f"\n=== İskelet problem rutini — canlı (öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)
            r = pg.request.post(
                f"{BASE}/api/v2/teacher/students/{sid}/skeleton/from-week",
                data={"start": s["hist0"], "end": s["hist1"]},
            )
            assert r.ok, r.text()
            pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(800)

            # 1. düzenleyici
            pg.get_by_role("button", name="İskelet", exact=True).click()
            dlg = pg.locator('[role="dialog"]')
            dlg.wait_for(timeout=10000)
            wd = date.today().weekday()
            dlg.locator('[data-testid="skeleton-day-tab"]').nth(wd).click()
            pg.wait_for_timeout(200)
            rows = dlg.locator('[data-testid="skeleton-day"]').locator('[data-testid="skeleton-row"]')
            info = rows.evaluate_all("""els => els.map(li => ({
                book: li.querySelector('select[aria-label="Kaynak kitap"]')?.value || '',
                routine: li.querySelector('input[aria-label="Rutin"]')?.checked || false,
                scope: li.querySelector('select[aria-label="Rutin kapsamı"]')?.value || '',
                second: li.querySelector('select[aria-label="İkinci kaynak"]')?.value || '',
                secondOpts: [...(li.querySelector('select[aria-label="İkinci kaynak"]')?.options || [])]
                  .map(o => o.textContent),
            }))""")
            rr = next((x for x in info if x["routine"]), None)
            tr = next((x for x in info if not x["routine"]), None)
            chk("1a. rutin satırı: kapsam 'yalnız problemler'", bool(rr and rr["scope"] == "problems"),
                str(info))
            chk("1b. konu satırı: 2. kaynak Fen Bilimleri · listede video defter yok",
                bool(tr and tr["second"] == str(s["fen"])
                     and not any("Video" in o for o in tr["secondOpts"])), str(tr))
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_problems_editor.png"))
            pg.emulate_media(color_scheme="dark")
            pg.wait_for_timeout(400)
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_problems_editor_dark.png"))
            pg.emulate_media(color_scheme="light")
            pg.wait_for_timeout(300)
            dlg.get_by_role("button", name="Vazgeç").click()
            pg.wait_for_timeout(600)

            # 2. gün kartı
            rows_txt = pg.locator(f'{GH} [data-testid="ghost-row"]').all_inner_texts()
            chk("2a. rutin rozeti 'rutin · problemler'",
                any("rutin · problemler" in x for x in rows_txt), str(rows_txt))
            chk("2b. konu satırında 'kaynak seç' uyarısı YOK (2. kaynak otomatik)",
                pg.locator(f'{GH} [data-testid="ghost-source-choice"]').count() == 0)

            # 3. problem rutini çipi
            pg.locator(f'{GH} [data-testid="ghost-row"]', has_text="rutin · problemler").first.click()
            strip = pg.locator('[data-testid="ghost-strip"]')
            strip.wait_for(timeout=5000)
            items = strip.locator('[data-testid="ghost-chip-items"] li').all_inner_texts()
            chk("3a. çip: Orijinal Problem Denemeleri 1 + Fen Bilimleri Oran ve Orantı 1",
                len(items) == 2 and "Orijinal" in items[0] and "Problem Denemeleri" in items[0]
                and "Fen Bilimleri" in items[1] and "Oran ve Orantı" in items[1], str(items))
            txt = strip.inner_text()
            chk("3b. video defter / Polinomlar yok · gerekçe kaynak geçişini söyler",
                "Video" not in txt and "Polinom" not in txt and "problemleri bu gün bitiyor" in txt,
                txt[:300])
            clip = pg.evaluate(CLIP_JS, '[data-testid="ghost-strip"]')
            chk("3c. şeritte kırpma/taşma yok", clip["clipped"] == 0 and not clip["overflow"], str(clip))
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_problems_routine.png"), full_page=True)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(400)

            # 4. konu satırı
            pg.locator(f'{GH} [data-testid="ghost-row"]').filter(has_not_text="rutin").first.click()
            strip = pg.locator('[data-testid="ghost-strip"]')
            strip.wait_for(timeout=5000)
            note = strip.locator('[data-testid="source-choice-note"]')
            chips_txt = strip.locator('[data-testid="ghost-chip"]').all_inner_texts()
            chk("4a. seçim uyarısı yok · ilk çip 2. kaynakta aynı konu (Fen · Fonksiyonlar)",
                note.count() == 0 and bool(chips_txt) and chips_txt[0].startswith("2. kaynak")
                and "Fonksiyonlar" in chips_txt[0], str([c[:60] for c in chips_txt]))
            chk("4b. '2. kaynak' (Fen · Fonksiyonlar) + 'sıradaki' (Orijinal · Polinomlar) çipleri",
                any(c.startswith("2. kaynak") and "Fonksiyonlar" in c for c in chips_txt)
                and any(c.startswith("sıradaki") and "Polinomlar" in c for c in chips_txt),
                str([c[:60] for c in chips_txt]))
            chk("4c. konu satırında problem bölümü önerilmez",
                not any("Oran" in c or "Problem" in c for c in chips_txt))
            clip = pg.evaluate(CLIP_JS, '[data-testid="ghost-strip"]')
            chk("4d. şeritte kırpma/taşma yok", clip["clipped"] == 0 and not clip["overflow"], str(clip))
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_problems_choice.png"), full_page=True)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(400)

            # 6. koyu tema
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(600)
            low = measure(pg, GH, min_ratio=3.0)["bad"]
            chk("6. koyu temada okunamayan metin yok", low == 0, f"bad={low}")
            pg.evaluate("() => document.documentElement.classList.remove('dark')")
            pg.wait_for_timeout(400)

            # 5. rutin kabul
            pg.locator(f'{GH} [data-testid="ghost-row"]', has_text="rutin · problemler").first.click()
            strip = pg.locator('[data-testid="ghost-strip"]')
            strip.wait_for(timeout=5000)
            strip.locator('[data-testid="ghost-chip"]').first.click()
            pg.wait_for_timeout(3000)
            with SessionLocal() as db:
                ts = db.query(Task).filter(Task.student_id == sid, Task.date == date.today()).all()
                per = [{i.book_id for i in t.book_items} for t in ts]
            chk("5a. iki görev, her biri tek kitap (Orijinal + Fen)",
                len(ts) == 2 and all(len(p) == 1 for p in per)
                and {next(iter(p)) for p in per} == {s["orj"], s["fen"]}, str(per))
            rows_after = pg.locator(f'{GH} [data-testid="ghost-row"]').all_inner_texts()
            chk("5b. rutin hayaleti kalktı · konu hayaleti kaldı (yenilemesiz)",
                not any("rutin · problemler" in x for x in rows_after)
                and any("öneri" in x and "Fonksiyonlar" in x for x in rows_after), str(rows_after))
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
