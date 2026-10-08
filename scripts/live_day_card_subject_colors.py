"""Gün kartında derslerin bir bakışta ayrışması — GERÇEK TARAYICI (2026-10-08).

Saha: koç koyu temada gün kartındaki dersleri birbirinden ayırt edemedi
(satır zemini ders rengini %16 saydamlıkla basıyordu → hepsi lacivert-gri).

Seed ekran görüntüsünün aynısı: TYT Matematik ×2 · AYT Matematik · TYT Türkçe ·
TYT Geometri · TYT Fizik · TYT Kimya ×2 (periyotsuz gün).

Senaryolar (açık + koyu tema):
  1. Ders adı DOLGULU etiket (beyaz yazı, renkli zemin) her ders satırında
  2. AYT satırında AYT işareti, TYT satırında TYT işareti
  3. Aynı dersin ardışık görevleri tek kutuda: 6 grup (TYT Mat 2'li, Kimya 2'li)
  4. Gruplar arasında görünür boşluk (≥ 3px; 9 görevlik gün tek ekrana sığsın)
  5. Farklı ders satırlarının zeminleri ölçülebilir biçimde ayrışır
     (komşu farklı ders ΔE ≥ 10 = "belirgin"; aynı dersin iki satırı ≈ aynı)
  6. Sol şerit ≥ 6px
  7. Etiket metni kırpılmıyor (… yok, taşma yok)
  8. Öğrenci Hafta Izgarası aynı renk sistemi: dolgulu etiket, şerit, ΔE ≥ 10
Ekran görüntüleri: .shots/day_card_subjects_{light,dark}.png
"""
from __future__ import annotations

import io
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
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    SuspiciousIp, Task, TaskBookItem, TaskType, User, UserRole,
)
from app.services.security import hash_password  # noqa: E402
from scripts.audit_day_card_perception import delta_e  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"dcc_{secrets.token_hex(3)}"
PWD = "Renkler!2345"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")

# (ders, görev bölümü) — ekran görüntüsündeki sıra
PLAN = [
    ("TYT Matematik", "Problem Denemeleri"),
    ("TYT Matematik", "Sayılar"),
    ("AYT Matematik", "Fonksiyonlar"),
    ("TYT Türkçe", "Paragrafın Yapısı"),
    ("TYT Geometri", "Eşkenar Üçgen"),
    ("TYT Fizik", "Kaldırma Kuvveti"),
    ("TYT Kimya", "Atom Modelleri"),
    ("TYT Kimya", "Temel Tanecikler"),
]

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
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Renk Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Renk Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        subj: dict[str, tuple] = {}
        for i, (nm, _) in enumerate(PLAN):
            if nm in subj:
                continue
            s = Subject(name=nm, teacher_id=coach.id, order=i + 1)
            db.add(s)
            db.flush()
            b = Book(name=f"{PFX} {nm} Soru Bankası", teacher_id=coach.id,
                     subject_id=s.id, type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            sb = StudentBook(student_id=st.id, book_id=b.id)
            db.add(sb)
            db.flush()
            subj[nm] = (s, b, sb)
        day = date.today()
        for order, (nm, sec_label) in enumerate(PLAN):
            s, b, sb = subj[nm]
            sec = BookSection(book_id=b.id, label=sec_label, order=order, test_count=20)
            db.add(sec)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                                   reserved_count=2, completed_count=0))
            t = Task(student_id=st.id, date=day, type=TaskType.TEST,
                     title=f"{b.name} — {sec_label}: 2 test", is_draft=False,
                     order=order)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=b.id, book_section_id=sec.id,
                                planned_count=2))
        db.commit()
        return {"coach": coach.id, "student": st.id,
                "subjects": [v[0].id for v in subj.values()],
                "books": [v[1].id for v in subj.values()],
                "sbs": [v[2].id for v in subj.values()],
                "email": f"{PFX}_t@test.invalid",
                "student_email": f"{PFX}_s@test.invalid"}


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


def run_theme(p, ids: dict, theme: str) -> None:
    from PIL import Image

    print(f"\n--- {theme} tema ---")
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 1000},
                        color_scheme="dark" if theme == "dark" else "light")
    ctx.add_init_script(f"try{{localStorage.setItem('lgs-theme','{theme}')}}catch(e){{}}")
    page = ctx.new_page()
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', ids["email"])
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)
    page.goto(f"{WEB}/teacher/students/{ids['student']}/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(1000)
    page.wait_for_selector("#day-editor .task-row", timeout=15000)
    page.wait_for_timeout(800)

    rows = page.query_selector_all("#day-editor .task-row")
    check(f"[{theme}] 8 görev satırı çizildi", len(rows) == 8, f"{len(rows)}")

    info = page.evaluate("""() => [...document.querySelectorAll('#day-editor .task-row')].map(r => {
        const spans = [...r.querySelectorAll('span[title]')];
        const tagWrap = spans.find(s => s.querySelector('span'));
        const inner = tagWrap ? [...tagWrap.querySelectorAll(':scope > span')] : [];
        const chip = inner[inner.length - 1];
        const exam = inner.length > 1 ? inner[0].innerText.trim() : null;
        const cs = chip ? getComputedStyle(chip) : null;
        return {
          name: tagWrap ? tagWrap.getAttribute('title') : null,
          exam, chipText: chip ? chip.innerText.trim() : null,
          chipColor: cs ? cs.color : null, chipBg: cs ? cs.backgroundColor : null,
          chipClipped: chip ? chip.scrollWidth > chip.clientWidth + 1 : true,
          border: parseFloat(getComputedStyle(r).borderLeftWidth),
        };
    })""")
    filled = all(i["chipBg"] and i["chipBg"] not in ("rgba(0, 0, 0, 0)", "transparent")
                 and i["chipColor"] in ("rgb(255, 255, 255)",) for i in info)
    check(f"[{theme}] 1. ders adı dolgulu etiket (beyaz yazı, renkli zemin)", filled,
          f"{[(i['chipText'], i['chipColor'], i['chipBg']) for i in info]}")
    exams = [i["exam"] for i in info]
    check(f"[{theme}] 2. TYT/AYT işareti doğru",
          exams == ["TYT", "TYT", "AYT", "TYT", "TYT", "TYT", "TYT", "TYT"], f"{exams}")
    check(f"[{theme}] 6. sol şerit ≥ 6px", all(i["border"] >= 6 for i in info),
          f"{[i['border'] for i in info]}")
    check(f"[{theme}] 7. etiket kırpılmıyor", not any(i["chipClipped"] for i in info))

    runs = page.query_selector_all('#day-editor [data-testid="subject-run"]')
    sizes = [len(r.query_selector_all(".task-row")) for r in runs]
    check(f"[{theme}] 3. aynı dersin ardışık görevleri tek kutuda (6 grup)",
          sizes == [2, 1, 1, 1, 1, 2], f"{sizes}")
    boxes = [r.bounding_box() for r in runs]
    gaps = [round(boxes[i + 1]["y"] - (boxes[i]["y"] + boxes[i]["height"]), 1)
            for i in range(len(boxes) - 1)]
    check(f"[{theme}] 4. gruplar arası boşluk ≥ 3px", gaps and min(gaps) >= 3, f"{gaps}")

    # 9. koç Hafta Izgarası: aynı renk sistemi (dolgulu etiket + şerit), gün
    #    kartıyla aynı ders sırası
    gnames = page.evaluate("""() => [...document.querySelectorAll('[data-testid="subject-block"] [data-testid="subject-tag"]')]
        .map(t => t.getAttribute('title'))""")
    check(f"[{theme}] 9a. Hafta Izgarası 6 ders bloğu, gün kartı sırasıyla",
          gnames == ["TYT Matematik", "AYT Matematik", "TYT Türkçe", "TYT Geometri",
                     "TYT Fizik", "TYT Kimya"], f"{gnames}")
    gtags = page.evaluate("""() => [...document.querySelectorAll('[data-testid="subject-block"] [data-testid="subject-tag-name"]')]
        .map(c => getComputedStyle(c).color)""")
    check(f"[{theme}] 9b. Hafta Izgarası etiketleri dolgulu (beyaz yazı)",
          gtags and all(c == "rgb(255, 255, 255)" for c in gtags), f"{gtags}")

    # 5. gerçek piksel: her satırın sağ ucundan zemin rengi
    os.makedirs(SHOTS, exist_ok=True)
    editor = page.query_selector("#day-editor")
    editor.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    editor.screenshot(path=os.path.join(SHOTS, f"day_card_subjects_{theme}.png"))
    colors = []
    for r in page.query_selector_all("#day-editor .task-row"):
        r.scroll_into_view_if_needed()
        bb = r.bounding_box()
        # satırın ortasında, metin/ikonlardan uzak boş bir şerit: aksiyon
        # ikonlarının solu değil, ders etiketinin hemen önündeki tutamak altı
        shot = page.screenshot(clip={"x": bb["x"] + 8, "y": bb["y"] + 2,
                                     "width": 14, "height": bb["height"] - 4})
        im = Image.open(io.BytesIO(shot)).convert("RGB")
        px = [im.getpixel((x, y)) for x in range(im.width) for y in range(im.height)]
        # en sık renk = zemin (tutamak ikonu az pikselli)
        colors.append(max(set(px), key=px.count))
    names = [i["name"] for i in info]
    diffs = []
    for a in range(len(colors)):
        for c in range(a + 1, len(colors)):
            if names[a] != names[c] and names[a].split()[-1] != names[c].split()[-1]:
                diffs.append((names[a], names[c], round(delta_e(colors[a], colors[c]), 1)))
    worst = min(diffs, key=lambda d: d[2])
    print(f"    en yakın farklı ders çifti: {worst}")
    check(f"[{theme}] 5a. farklı dersler arası en küçük ΔE ≥ 10 (belirgin)",
          worst[2] >= 10, f"{worst}")
    same = round(delta_e(colors[0], colors[1]), 1)
    check(f"[{theme}] 5b. aynı dersin iki satırı aynı renk (ΔE < 2.3)", same < 2.3, f"{same}")
    b.close()


def run_student_week(p, ids: dict, theme: str) -> None:
    """Öğrenci Hafta Izgarası: aynı renk sistemi (koç gün kartıyla birebir)."""
    from PIL import Image

    print(f"\n--- öğrenci hafta ızgarası · {theme} tema ---")
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": 1440, "height": 1000},
                        color_scheme="dark" if theme == "dark" else "light")
    ctx.add_init_script(f"try{{localStorage.setItem('lgs-theme','{theme}')}}catch(e){{}}")
    page = ctx.new_page()
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', ids["student_email"])
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)
    page.goto(f"{WEB}/student/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    for txt in ("Daha sonra", "Kapat"):
        btn = page.query_selector(f'button:has-text("{txt}")')
        if btn:
            btn.click()
            page.wait_for_timeout(800)
    page.wait_for_selector('[data-testid="subject-block"]', timeout=15000)

    blocks = page.query_selector_all('[data-testid="subject-block"]')
    names = [bl.query_selector('[data-testid="subject-tag"]').get_attribute("title")
             for bl in blocks]
    check(f"[öğrenci {theme}] 6 ders bloğu (TYT Mat 2'li, Kimya 2'li tek blokta)",
          names == ["TYT Matematik", "AYT Matematik", "TYT Türkçe", "TYT Geometri",
                    "TYT Fizik", "TYT Kimya"], f"{names}")
    info = page.evaluate("""() => [...document.querySelectorAll('[data-testid="subject-tag-name"]')].map(c => {
        const cs = getComputedStyle(c);
        return {color: cs.color, bg: cs.backgroundColor,
                clipped: c.scrollWidth > c.clientWidth + 1};
    })""")
    check(f"[öğrenci {theme}] dolgulu ders etiketi (beyaz yazı)",
          info and all(i["color"] == "rgb(255, 255, 255)" and i["bg"] != "rgba(0, 0, 0, 0)"
                       for i in info), f"{info}")
    rails = page.evaluate("""() => [...document.querySelectorAll('[data-testid="subject-block"]')]
        .map(b => parseFloat(getComputedStyle(b).borderLeftWidth))""")
    check(f"[öğrenci {theme}] sol şerit ≥ 4px", all(r >= 4 for r in rails), f"{rails}")
    clipped = page.evaluate("""() => [...document.querySelectorAll('[data-testid="subject-block"] *')]
        .filter(e => getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1).length""")
    check(f"[öğrenci {theme}] metin kırpılmıyor (… yok)", clipped == 0 and not any(i["clipped"] for i in info),
          f"{clipped}")
    colors = []
    for bl in blocks:
        bl.scroll_into_view_if_needed()
        bb = bl.bounding_box()
        shot = page.screenshot(clip={"x": bb["x"] + bb["width"] - 10, "y": bb["y"] + 2,
                                     "width": 8, "height": max(4, bb["height"] - 4)})
        im = Image.open(io.BytesIO(shot)).convert("RGB")
        px = [im.getpixel((x, y)) for x in range(im.width) for y in range(im.height)]
        colors.append(max(set(px), key=px.count))
    diffs = [(names[a], names[c], round(delta_e(colors[a], colors[c]), 1))
             for a in range(len(colors)) for c in range(a + 1, len(colors))
             if names[a].split()[-1] != names[c].split()[-1]]
    worst = min(diffs, key=lambda d: d[2])
    print(f"    en yakın farklı ders çifti: {worst}")
    check(f"[öğrenci {theme}] farklı dersler arası en küçük ΔE ≥ 10", worst[2] >= 10, f"{worst}")
    os.makedirs(SHOTS, exist_ok=True)
    page.query_selector('section:has([data-testid="subject-block"])').screenshot(
        path=os.path.join(SHOTS, f"student_week_subjects_{theme}.png"))
    b.close()


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    print(f"\n=== Gün kartı ders renkleri (öğrenci #{ids['student']}) ===")
    try:
        with sync_playwright() as p:
            for theme in ("light", "dark"):
                run_theme(p, ids, theme)
            for theme in ("light", "dark"):
                run_student_week(p, ids, theme)
    finally:
        cleanup(ids)
    print(f"\n{passed} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
