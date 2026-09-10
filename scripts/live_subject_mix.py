"""Ders Dağılımı şeridi + müfredat KAYNAK SEÇİMİ — GERÇEK TARAYICI (2026-09-09).

Dev sunucu (:3000 + :8081) + Playwright ister. Kendi seed'ini kurar/temizler.

KOÇ İSTEĞİ (birebir):
  (1) "programı hazırlarken ders bazında (TYT ve AYT ayrı olarak) görev
      yüzdelerini görmek istiyorum — örneğin AYT Matematik %35"
  (2) "müfredatta konuya tıklayıp +3 test dediğimde hangi kaynaktan
      ekleyeceğini bilmiyorum; seçimi neye göre yapıyor?"

Seed (yüzdeler ELDE hesaplanabilsin diye sayılar sabit):
  TYT Matematik : 3 görev · 30 test   (%50 test · %30 görev)
  AYT Matematik : 3 görev · 21 test   (%35 test · %30 görev)
  TYT Türkçe    : 2 görev ·  9 test   (%15 test · %20 görev)
  TYT Biyoloji  : 2 görev ·  0 test   (video — test payı 0, görev payı %20)
  → TYT bloğu %65 · AYT bloğu %35  (test moduna göre)

  "Çok Kaynaklı Konu" (AYT Matematik) iki kitaba bağlı:
    A "Devam Kitabı" 12 test, 6 çözülmüş → kalan  6   (BAŞLANMIŞ)
    B "Yeni Kitap"   20 test, 0 çözülmüş → kalan 20   (kalanı EN ÇOK)
  Eski sıra kalanı çok olanı seçiyordu (B) — koç hangi kitaba yazdığını
  görmüyordu. Beklenen: A önerilir ("devam" rozeti), AMA koç B satırındaki
  butona basarsa görev B'ye yazılır.

Senaryolar:
   1. "Ders Dağılımı" şeridi hafta ızgarasının altında görünür
   2. TYT/AYT blok özeti başlıkta (%65 / %35)
   3. AYT Matematik çipi %35 (koçun birebir örneği)
   4. Görev/Test toggle → yüzdeler görev adedine döner (%30)
   5. Testi olmayan ders (video) çipte görünür — bilgi kaybolmaz
   6. Şerit sayfa düzenini bozmaz (gün kartı + sağ panel yerinde, yatay taşma yok)
   7. Çok kaynaklı konuda İKİ kaynak satırı ayrı ayrı listelenir
   8. Önerilen (başlanmış) kaynak üstte + "devam" rozeti
   9. İKİNCİ satırdaki "+3 test" görevi O kaynağa yazar (koç seçebiliyor)
  10. Kaynak satırlarında kırpılmış metin ("…") yok
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets
from datetime import date, timedelta

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
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lsm_{secrets.token_hex(3)}"
PWD_PLAIN = "SubjMix!2345"
SHOT_DIR = os.environ.get("SHOT_DIR", os.path.join(os.getcwd(), ".shots"))

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD_PLAIN),
                     full_name="Dağılım Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD_PLAIN),
                  full_name="Dağılım Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()

        subjects: dict[str, Subject] = {}
        for i, nm in enumerate(
            ["TYT Matematik", "AYT Matematik", "TYT Türkçe", "TYT Biyoloji"]
        ):
            s = Subject(name=f"{nm} {PFX}", teacher_id=coach.id, order=i + 1)
            db.add(s)
            db.flush()
            subjects[nm] = s

        # Ders başına bir kitap + tek bölüm (yüzde hesabı sade kalsın)
        books: dict[str, tuple[int, int]] = {}   # ders -> (book_id, section_id)
        for nm, total in (
            ("TYT Matematik", 60), ("AYT Matematik", 60), ("TYT Türkçe", 40),
        ):
            b = Book(name=f"{nm} SB {PFX}", teacher_id=coach.id,
                     subject_id=subjects[nm].id, type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            sec = BookSection(book_id=b.id, label=f"{nm} Bölüm", order=1,
                              test_count=total, topic_id=None)
            db.add(sec)
            db.flush()
            db.add(StudentBook(student_id=st.id, book_id=b.id))
            db.flush()
            books[nm] = (b.id, sec.id)

        monday = date.today() - timedelta(days=date.today().weekday())

        def task(subject: str, day: int, tests: int, *, video: bool = False):
            if video:
                t = Task(student_id=st.id, date=monday + timedelta(days=day),
                         type=TaskType.VIDEO, title=f"{subjects[subject].name} · Konu videosu",
                         is_draft=False)
                db.add(t)
                db.flush()
                return
            bid, sid = books[subject]
            t = Task(student_id=st.id, date=monday + timedelta(days=day),
                     type=TaskType.TEST, title=f"{subject} — {tests} test",
                     is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=bid, book_section_id=sid,
                                planned_count=tests, completed_count=0))
            db.flush()

        # TYT Mat 3 görev / 30 test · AYT Mat 3 görev / 21 test
        # TYT Türkçe 2 görev / 9 test · TYT Biyoloji 2 video (0 test)
        for d, n in ((0, 12), (1, 10), (2, 8)):
            task("TYT Matematik", d, n)
        for d, n in ((0, 7), (2, 7), (3, 7)):
            task("AYT Matematik", d, n)
        for d, n in ((1, 5), (3, 4)):
            task("TYT Türkçe", d, n)
        for d in (0, 4):
            task("TYT Biyoloji", d, 0, video=True)

        # --- Çok kaynaklı konu (AYT Matematik): iki kitap, aynı Topic
        t_multi = Topic(subject_id=subjects["AYT Matematik"].id,
                        name=f"Çok Kaynaklı Konu {PFX}", order=1,
                        teacher_id=coach.id)
        db.add(t_multi)
        db.flush()
        multi: dict[str, int] = {}
        for tag, label, total, done in (
            ("A", "Devam Kitabı", 12, 6),
            ("B", "Yeni Kitap", 20, 0),
        ):
            b = Book(name=f"{label} {PFX}", teacher_id=coach.id,
                     subject_id=subjects["AYT Matematik"].id,
                     type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            sec = BookSection(book_id=b.id, label="Çarpanlara Ayırma Alt Başlığı",
                              order=1, test_count=total, topic_id=t_multi.id)
            db.add(sec)
            db.flush()
            sbx = StudentBook(student_id=st.id, book_id=b.id)
            db.add(sbx)
            db.flush()
            db.add(SectionProgress(student_book_id=sbx.id, book_section_id=sec.id,
                                   reserved_count=0, completed_count=done))
            db.flush()
            multi[tag] = b.id

        db.commit()
        return {
            "coach": coach.id, "student": st.id,
            "email": f"{PFX}_t@test.invalid",
            "subject_ids": [s.id for s in subjects.values()],
            "book_ids": [b for b, _ in books.values()] + list(multi.values()),
            "topic_multi": t_multi.id,
            "book_a": multi["A"], "book_b": multi["B"],
            "ayt_subject": subjects["AYT Matematik"].id,
        }


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uid = [ids["coach"], ids["student"]]
        tids = [r[0] for r in db.query(Task.id)
                .filter(Task.student_id.in_(uid)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        bids = ids["book_ids"]
        if bids:
            sbids = [r[0] for r in db.query(StudentBook.id)
                     .filter(StudentBook.book_id.in_(bids)).all()]
            if sbids:
                db.execute(sa_delete(SectionProgress)
                           .where(SectionProgress.student_book_id.in_(sbids)))
                db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids)))
            db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
            db.execute(sa_delete(Book).where(Book.id.in_(bids)))
        for sid in ids["subject_ids"]:
            db.execute(sa_delete(Topic).where(Topic.subject_id == sid))
            db.execute(sa_delete(Subject).where(Subject.id == sid))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()


def _items_for_book(student_id: int, book_id: int) -> int:
    """O kitaba yazılmış planlanan test toplamı."""
    with SessionLocal() as db:
        rows = (
            db.query(TaskBookItem.planned_count)
            .join(Task, Task.id == TaskBookItem.task_id)
            .filter(Task.student_id == student_id, TaskBookItem.book_id == book_id)
            .all()
        )
    return sum(int(r[0] or 0) for r in rows)


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    ids = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1500, "height": 1000})

            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD_PLAIN)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            page.goto(f"{WEB}/teacher/students/{ids['student']}/week",
                      wait_until="networkidle")
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(1000)

            # ---- 1. Şerit var mı
            mix = page.query_selector('section:has-text("Haftanın Ders Dengesi")')
            check("1. 'Haftanın Ders Dengesi' şeridi sayfada", mix is not None)
            if mix is None:
                page.screenshot(path=os.path.join(SHOT_DIR, "mix_fail.png"),
                                full_page=True)
                b.close()
                return 1
            def chip_lines() -> list[str]:
                """Çip metinleri — inner_text her span'i ayrı satıra koyduğu için
                satır sonları boşluğa çevrilir (ad + yüzde + sayılar tek satır)."""
                return [
                    " ".join(li.inner_text().split())
                    for li in page.query_selector_all(
                        'section:has-text("Haftanın Ders Dengesi") ul > li'
                    )
                ]

            mix_text = mix.inner_text()
            chips = chip_lines()

            # ---- 2. TYT/AYT blok özeti
            check(
                "2. başlıkta TYT/AYT blok özeti (TYT %65 · AYT %35)",
                "TYT %65" in mix_text and "AYT %35" in mix_text,
                mix_text.split("\n")[0][:160],
            )

            # ---- 3. AYT Matematik %35 (koçun birebir örneği)
            check(
                "3. AYT Matematik çipi %35 (test payı) + sayılar yazılı",
                "%35" in (next((c for c in chips if "AYT Matematik" in c), ""))
                and "3 görev" in (next((c for c in chips if "AYT Matematik" in c), ""))
                and "21 test" in (next((c for c in chips if "AYT Matematik" in c), "")),
                next((c for c in chips if "AYT Matematik" in c), "") or str(chips)[:250],
            )

            # ---- 5. Testi olmayan ders de görünür (bilgi kaybı yok)
            check(
                "5. video-only ders çipte görünür (0 test ama görev var)",
                "%0" in (next((c for c in chips if "Biyoloji" in c), ""))
                and "2 görev" in (next((c for c in chips if "Biyoloji" in c), "")),
                next((c for c in chips if "Biyoloji" in c), "") or str(chips)[:250],
            )

            page.screenshot(path=os.path.join(SHOT_DIR, "mix_test.png"))

            # ---- 4. Görev moduna geç
            page.click('section:has-text("Haftanın Ders Dengesi") button:has-text("Görev")')
            page.wait_for_timeout(700)
            mix_text2 = page.query_selector(
                'section:has-text("Haftanın Ders Dengesi")').inner_text()
            check(
                "4. 'Görev' moduna geçince yüzde görev adedine döner "
                "(AYT %30, toplam 10 görev)",
                "%30" in (next((c for c in chip_lines() if "AYT Matematik" in c), ""))
                and "toplam 10 görev" in mix_text2,
                next((c for c in chip_lines() if "AYT Matematik" in c), "")
                or str(chip_lines())[:250],
            )
            page.click('section:has-text("Haftanın Ders Dengesi") button:has-text("Test")')
            page.wait_for_timeout(500)

            # ---- 6. Sayfa düzeni bozulmadı
            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth - "
                "document.documentElement.clientWidth"
            )
            grid_ok = page.query_selector('section:has-text("Hafta Izgarası")') is not None
            editor = page.query_selector("#day-editor")
            ed_w = page.evaluate(
                "(el) => el ? Math.round(el.getBoundingClientRect().width) : 0", editor
            )
            check(
                "6. şerit düzeni bozmaz (yatay taşma yok · ızgara + gün kartı yerinde)",
                overflow <= 1 and grid_ok and ed_w > 700,
                f"overflow={overflow} grid={grid_ok} editor_w={ed_w}",
            )

            # ---- Müfredat panelini aç (şeritten peek + raptiye)
            sec = page.query_selector('[data-section="week:curriculum"]')
            if sec is None:
                rail = page.query_selector('[data-rail="week:curriculum"]')
                if rail:
                    rail.click()
                    page.wait_for_timeout(800)
                    pin = page.query_selector(
                        '[data-section="week:curriculum"] button[aria-pressed]')
                    if pin:
                        pin.click()
                        page.wait_for_timeout(600)
                sec = page.query_selector('[data-section="week:curriculum"]')
            if sec is None:
                check("7-10. müfredat paneli açılamadı", False, "panel yok")
                page.screenshot(path=os.path.join(SHOT_DIR, "board_fail.png"),
                                full_page=True)
                b.close()
                return 1
            if sec.get_attribute("data-open") != "1":
                sec.query_selector("button[aria-expanded]").click()
            page.wait_for_timeout(2000)

            # AYT Matematik dersini seç (çok kaynaklı konu orada)
            sel = page.query_selector('[data-section="week:curriculum"] select')
            if sel:
                sel.select_option(str(ids["ayt_subject"]))
                page.wait_for_timeout(2000)

            page.click('[data-section="week:curriculum"] button:has-text("Çok Kaynaklı Konu")')
            page.wait_for_timeout(1200)
            panel = page.query_selector('[data-section="week:curriculum"]')
            ptext = panel.inner_text()

            # ---- 7. İki kaynak ayrı satırda
            rows = page.query_selector_all(
                '[data-section="week:curriculum"] li li')
            row_texts = [r.inner_text() for r in rows]
            check(
                "7. çok kaynaklı konuda İKİ kaynak ayrı satırda listelenir",
                "kaynak seç (2)" in ptext.lower()
                and any("Devam Kitabı" in t for t in row_texts)
                and any("Yeni Kitap" in t for t in row_texts),
                str(row_texts)[:300],
            )

            # ---- 8. Önerilen üstte + "devam" rozeti
            check(
                "8. başlanmış kaynak ÜSTTE + 'devam' rozeti (6/12 çözüldü)",
                len(row_texts) >= 2
                and "Devam Kitabı" in row_texts[0]
                and "devam" in row_texts[0].lower()
                and "6/12" in row_texts[0],
                row_texts[0][:200] if row_texts else "satır yok",
            )

            # ---- 10. Kırpma yok
            clipped = page.evaluate(
                """() => {
                  const rows = document.querySelectorAll(
                    '[data-section="week:curriculum"] li li');
                  let n = 0;
                  rows.forEach((r) => r.querySelectorAll('*').forEach((el) => {
                    if (el.children.length === 0 &&
                        el.scrollWidth > el.clientWidth + 2) n++;
                  }));
                  return n;
                }"""
            )
            check("10. kaynak satırlarında kırpılmış metin yok", clipped == 0,
                  f"taşan öğe={clipped}")

            page.screenshot(path=os.path.join(SHOT_DIR, "board_sources.png"))

            # ---- 9. İKİNCİ satırdaki butona bas → görev O kitaba yazılsın
            before_a = _items_for_book(ids["student"], ids["book_a"])
            before_b = _items_for_book(ids["student"], ids["book_b"])
            second_btn = rows[1].query_selector('button:has-text("+3 test")')
            second_btn.click()
            page.wait_for_timeout(2500)
            after_a = _items_for_book(ids["student"], ids["book_a"])
            after_b = _items_for_book(ids["student"], ids["book_b"])
            check(
                "9. İKİNCİ kaynağın '+3 test' butonu görevi O kaynağa yazar "
                "(önerilene DEĞİL)",
                after_b == before_b + 3 and after_a == before_a,
                f"A {before_a}→{after_a} · B {before_b}→{after_b}",
            )

            page.screenshot(path=os.path.join(SHOT_DIR, "week_full.png"),
                            full_page=True)

            # ---- 11. KOYU TEMA: açık tonlu kutularda metin okunur mu
            #      (tekrarlayan kontrast bug'ı — bg-*-50 + tema-token metin).
            page.evaluate(
                "() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(900)
            dark_txt = page.query_selector(
                'section:has-text("Haftanın Ders Dengesi")').inner_text()
            # Kontrast ÖLÇÜMÜ paylaşılan modülden (2026-09-10): eski satır-içi
            # ölçüm Chrome'un `lab(...)` renklerini RGB sanıp yanlış sonuç
            # veriyordu — piksel tabanlı doğru ölçüme taşındı.
            low_contrast = measure(
                page,
                '[data-section="week:subject-mix"], '
                '[data-section="week:curriculum"] li li',
                min_ratio=3.0,
            )["bad"]
            page.screenshot(path=os.path.join(SHOT_DIR, "week_dark.png"),
                            full_page=True)
            check(
                "11. koyu temada okunamayan metin yok (kontrast ≥ 3.0 / WCAG AA)",
                "Haftanın Ders Dengesi" in dark_txt and low_contrast == 0,
                f"düşük kontrastlı öğe={low_contrast}",
            )
            b.close()
    finally:
        cleanup(ids)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===  (ekran görüntüleri: {SHOT_DIR})")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
