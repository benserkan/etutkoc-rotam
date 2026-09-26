"""İskelet F2-1 — kitaba bağlı rutin: CANLI E2E (dev sunucu + Playwright).

Zeynep Ela deseni: paragraf KARIŞIK rutini (her gün 3 farklı bölümden birer
test) + kitapsız serbest metin rutini + iki ayrı TYT Matematik satırı.

   1. Düzenleyicide satırlar KAYNAKLI: paragraf satırı kitap + "karışık",
      kitapsız satır etiketiyle, iki Matematik satırı farklı kitaplarla
   2. Gün kartında hayalet satırlar kaynağını yazar ("· Mor Paragraf",
      "rutin · karışık"); kitapsız rutin "etkinlik olarak yazılır"
   3. Karışık rutin çipi 3 farklı bölümü listeler; şeritte kırpma/taşma yok
   4. "Haftanın rutinleri" → bugünden hafta sonuna her gün karma + etkinlik
      görevi; karma bölümler günler boyu dönen halka
   5. Koyu tema: hayalet bölümü okunur

Ön koşul: backend :8081 + Next :3000.
  PYTHONPATH=. python scripts/live_skeleton_routine.py
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
PFX = f"lsr_{secrets.token_hex(3)}"
PWD = "SkelRt!2345xy"
SHOT_DIR = os.path.join(os.getcwd(), ".shots")
passed = 0
failed: list[str] = []


def chk(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


PAR = ["Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Yapı", "Ana Düşünce", "Yardımcı Düşünce"]


def seed() -> dict:
    today = date.today()
    hist = [today - timedelta(days=i) for i in range(7, 0, -1)]
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Lsr Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Lsr Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        tur = Subject(name=f"Lsr Türkçe {PFX}", teacher_id=coach.id, order=1)
        mat = Subject(name=f"Lsr Matematik {PFX}", teacher_id=coach.id, order=2)
        db.add_all([tur, mat])
        db.flush()
        tps = []
        for i, n in enumerate(["Temel Kavramlar", "Oran Orantı"], start=1):
            t = Topic(subject_id=mat.id, name=n, order=i, teacher_id=coach.id)
            db.add(t)
            tps.append(t)
        db.flush()
        par = Book(name=f"Mor Paragraf {PFX}", teacher_id=coach.id, subject_id=tur.id,
                   type=BookType.SORU_BANKASI)
        m1 = Book(name=f"3D Defter {PFX}", teacher_id=coach.id, subject_id=mat.id,
                  type=BookType.SORU_BANKASI)
        m2 = Book(name=f"Orijinal Mat {PFX}", teacher_id=coach.id, subject_id=mat.id,
                  type=BookType.SORU_BANKASI)
        db.add_all([par, m1, m2])
        db.flush()
        secs: dict = {}
        for i, n in enumerate(PAR):
            secs[f"p{i}"] = BookSection(book_id=par.id, label=n, order=i + 1, test_count=20)
        for b, key in ((m1, "a"), (m2, "b")):
            for i, t in enumerate(tps):
                secs[f"{key}{i}"] = BookSection(book_id=b.id, label=t.name, order=i + 1,
                                                test_count=10, topic_id=t.id)
        db.add_all(secs.values())
        db.flush()
        sbs = {}
        for b in (par, m1, m2):
            sbs[b.id] = StudentBook(student_id=st.id, book_id=b.id)
            db.add(sbs[b.id])
        db.flush()
        used = {k: 0 for k in secs}

        def task(d, items, title="x", ttype=TaskType.TEST):
            t = Task(student_id=st.id, date=d, type=ttype, title=title, is_draft=False)
            db.add(t)
            db.flush()
            for k, n in items:
                s = secs[k]
                db.add(TaskBookItem(task_id=t.id, book_id=s.book_id, book_section_id=s.id,
                                    planned_count=n))
                used[k] += n
                db.flush()

        pos = 0
        for d in hist:
            task(d, [(f"p{(pos + j) % 5}", 1) for j in range(3)])
            pos = (pos + 3) % 5
            task(d, [], title=f"Lsr Türkçe {PFX} · 345 Sıfır Risk Paragraf 2 Test",
                 ttype=TaskType.OTHER)
            task(d, [("a0", 2)])
            task(d, [("b0", 1)])
        for k, n in used.items():
            s = secs[k]
            db.add(SectionProgress(student_book_id=sbs[s.book_id].id, book_section_id=s.id,
                                   completed_count=min(n, s.test_count), reserved_count=0))
        out = dict(coach=coach.id, st=st.id, tur=tur.id, mat=mat.id, par=par.id,
                   m1=m1.id, m2=m2.id, books=[par.id, m1.id, m2.id],
                   sbs=[x.id for x in sbs.values()], topics=[t.id for t in tps],
                   secs={k: v.id for k, v in secs.items()}, next_pos=pos,
                   hist0=hist[0].isoformat(), hist1=hist[-1].isoformat(), email=coach.email)
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
        db.execute(sa_delete(Subject).where(Subject.id.in_([s["tur"], s["mat"]])))
        db.execute(sa_delete(User).where(User.id.in_([s["st"], s["coach"]])))
        db.commit()


GH = '[data-section="day:skeleton-ghosts"]'


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    s = seed()
    sid = s["st"]
    print(f"\n=== İskelet rutin — canlı (öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)
            # İskelet: geçmiş haftadan (API, oturum çerezleriyle)
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
            rows = dlg.locator('[data-testid="skeleton-day"]').nth(wd).locator('[data-testid="skeleton-row"]')
            info = rows.evaluate_all("""els => els.map(li => ({
                book: li.querySelector('select[aria-label="Kaynak kitap"]')?.value || '',
                bookText: li.querySelector('select[aria-label="Kaynak kitap"]')?.selectedOptions[0]?.textContent || '',
                label: li.querySelector('input[aria-label="Etkinlik adı"]')?.value || '',
                mode: li.querySelector('select[aria-label="Rutin biçimi"]')?.value || '',
                routine: li.querySelector('input[type="checkbox"]')?.checked || false,
            }))""")
            par_row = next((x for x in info if x["book"] == str(s["par"])), None)
            lab_row = next((x for x in info if x["label"]), None)
            mat_books = {x["book"] for x in info if x["book"] in (str(s["m1"]), str(s["m2"]))}
            chk("1a. paragraf satırı: kitap + rutin + karışık",
                bool(par_row and par_row["routine"] and par_row["mode"] == "karma"), str(info))
            chk("1b. kitapsız rutin satırı etiketiyle",
                bool(lab_row and lab_row["label"] == "345 Sıfır Risk Paragraf 2 Test"
                     and lab_row["routine"]), str(lab_row))
            chk("1c. iki Matematik satırı iki farklı kitapla ayırt edilir",
                mat_books == {str(s["m1"]), str(s["m2"])}, str(mat_books))
            mat_routine = [x["routine"] for x in info if x["book"] in (str(s["m1"]), str(s["m2"]))]
            chk("1d. her gün kullanılan KONU kitabı rutin sayılmaz (konu ipliği)",
                mat_routine and not any(mat_routine), str(mat_routine))
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_routine_editor.png"))
            dlg.get_by_role("button", name="Vazgeç").click()
            pg.wait_for_timeout(600)

            # 2. gün kartı
            sources = pg.locator(f'{GH} [data-testid="ghost-source"]').all_inner_texts()
            rows_txt = pg.locator(f'{GH} [data-testid="ghost-row"]').all_inner_texts()
            chk("2a. hayaletler kaynağını yazar (Mor Paragraf · 3D Defter · Orijinal Mat · etiket)",
                any("Mor Paragraf" in x for x in sources)
                and any("3D Defter" in x for x in sources)
                and any("Orijinal Mat" in x for x in sources)
                and any("345 Sıfır Risk" in x for x in sources), str(sources))
            chk("2b. rutin rozeti biçimiyle ('rutin · karışık') · etkinlik satırı",
                any("rutin · karışık" in x for x in rows_txt)
                and any("etkinlik olarak yazılır" in x for x in rows_txt), str(rows_txt))

            # 3. karma çip
            pg.locator(f'{GH} [data-testid="ghost-row"]', has_text="Mor Paragraf").first.click()
            strip = pg.locator('[data-testid="ghost-strip"]')
            strip.wait_for(timeout=5000)
            items = strip.locator('[data-testid="ghost-chip-items"] li').all_inner_texts()
            exp = [PAR[(s["next_pos"] + j) % 5] for j in range(3)]
            chk("3a. karışık rutin çipi 3 farklı bölüm, birer test (kaldığı yerden)",
                [x.split(" · ")[0] for x in items] == exp, f"{items} != {exp}")
            clip = pg.evaluate(
                """() => { const s = document.querySelector('[data-testid="ghost-strip"]');
                  const els = [...s.querySelectorAll('*')].filter(e =>
                    getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1);
                  return {clipped: els.length, overflow: s.scrollWidth > s.clientWidth + 1}; }""")
            chk("3b. şeritte kırpma/taşma yok", clip["clipped"] == 0 and not clip["overflow"], str(clip))
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_routine_strip.png"), full_page=True)
            pg.keyboard.press("Escape")

            # 5. koyu tema
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(600)
            low = measure(pg, GH, min_ratio=3.0)["bad"]
            chk("5. koyu temada okunamayan metin yok", low == 0, f"bad={low}")
            pg.evaluate("() => document.documentElement.classList.remove('dark')")

            # 4. haftanın rutinleri
            btn = pg.get_by_role("button", name="Haftanın rutinleri")
            had_btn = btn.count() == 1
            if had_btn:
                btn.click()
                pg.wait_for_timeout(3000)
            with SessionLocal() as db:
                ts = (db.query(Task).filter(Task.student_id == sid, Task.date >= date.today())
                      .order_by(Task.date, Task.id).all())
                par_seq = []
                acts = 0
                days = set()
                for t in ts:
                    days.add(t.date)
                    its = sorted(t.book_items, key=lambda x: x.id)
                    if any(i.book_id == s["par"] for i in its):
                        par_seq += [i.book_section_id for i in its]
                    if not its and "345 Sıfır Risk" in (t.title or ""):
                        acts += 1
            n_days = len(days)
            exp_seq = [s["secs"][f"p{(s['next_pos'] + j) % 5}"] for j in range(3 * n_days)]
            chk("4. 'Haftanın rutinleri': her gün karma + etkinlik; karma günler boyu döner",
                had_btn and n_days >= 1 and acts == n_days and par_seq == exp_seq,
                f"gün={n_days} etkinlik={acts} seq={par_seq[:6]}…")
            left = pg.locator(f'{GH} [data-testid="ghost-row"]', has_text="Mor Paragraf").count()
            chk("4b. bugünün rutin hayaletleri kalktı (yenilemesiz)", left == 0, f"{left}")
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
