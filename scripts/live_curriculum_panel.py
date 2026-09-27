"""Müfredat sekmesi yeni tasarım — canlı tarayıcı testi (2026-09-27).

Kendi verisini kurar/temizler: mezun öğrenci + yerleşik "TYT Matematik"e iki
kaynak kitap. Doğrular: mezunda İngilizce/İnkılap yok · kaynak kuralı UI'da
(çift kaynak 10/10+9/10 tamam, 10/10+5/10 süren, tek kaynak 49/50 tamam) ·
ders listesi + ayrıntı paneli · kaynak kırılımı satırda · filtre · kırpma/taşma
yok · koyu tema kontrastı. Dev sunucular (:3000 + :8081) açık olmalı.
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject, Topic, User, UserRole,
)
from app.services import curriculum_progress as cp
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

WEB = "http://localhost:3000"
PFX = f"lcp_{secrets.token_hex(3)}"
PWD = "LiveCurr!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Canlı Müfredat Koç", role=UserRole.TEACHER, is_active=True,
                     must_change_password=False)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Mezun Deneme", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, is_graduate=True)
        db.add(st)
        db.flush()
        subj = (db.query(Subject).filter(Subject.name == "TYT Matematik",
                                         Subject.is_builtin.is_(True)).first())
        leaves = cp.leaf_topics_for_student(db, st, coach.id, [subj.id]).by_subject[subj.id][:4]
        a = Book(name=f"Uzun Adlı Birinci Soru Bankası {PFX}", subject_id=subj.id,
                 teacher_id=coach.id, type=BookType.SORU_BANKASI)
        b = Book(name=f"İkinci Kaynak {PFX}", subject_id=subj.id, teacher_id=coach.id,
                 type=BookType.SORU_BANKASI)
        db.add_all([a, b])
        db.flush()
        sba = StudentBook(student_id=st.id, book_id=a.id)
        sbb = StudentBook(student_id=st.id, book_id=b.id)
        db.add_all([sba, sbb])
        db.flush()

        def sec(book, sb, topic, total, done):
            s = BookSection(book_id=book.id, label=f"{topic.name}", test_count=total,
                            order=topic.order, topic_id=topic.id)
            db.add(s)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=s.id,
                                   reserved_count=0, completed_count=done))
        t1, t2, t3, t4 = leaves
        sec(a, sba, t1, 10, 10); sec(b, sbb, t1, 10, 9)    # çift: tamam
        sec(a, sba, t2, 10, 10); sec(b, sbb, t2, 10, 5)    # çift: süren
        sec(a, sba, t3, 50, 49)                            # tek %98: tamam
        sec(a, sba, t4, 10, 0)                             # başlanmadı
        db.commit()
        return {"coach": coach.id, "student": st.id, "email": coach.email,
                "books": [a.id, b.id], "sbs": [sba.id, sbb.id],
                "names": [t.name for t in leaves]}


def cleanup(d):
    with SessionLocal() as db:
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(d["sbs"])))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == d["student"]))
        for bid in d["books"]:
            db.execute(sa_delete(BookSection).where(BookSection.book_id == bid))
            db.execute(sa_delete(Book).where(Book.id == bid))
        db.execute(sa_delete(User).where(User.id.in_([d["student"], d["coach"]])))
        db.commit()


OVERFLOW_JS = """(sel) => {
  const root = document.querySelector(sel); if (!root) return {missing: true};
  let clipped = [];
  for (const el of root.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) clipped.push(el.textContent.slice(0,40));
  }
  const r = root.getBoundingClientRect();
  return {clipped, hscroll: r.right > window.innerWidth + 1 || root.scrollWidth > root.clientWidth + 1};
}"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', d["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{d['student']}#curriculum", wait_until="networkidle")
            page.wait_for_timeout(3000)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(800)
            page.wait_for_selector('[data-section="curriculum-panel"]', timeout=20000)

            subjects = page.locator('[data-testid="curriculum-subject"]').all_inner_texts()
            joined = " | ".join(subjects)
            joined += " | " + page.locator('[data-testid="curriculum-nosource"]').inner_text()
            check("1. mezunda İngilizce / İnkılap dersi yok",
                  "İngilizce" not in joined and "İnkılap" not in joined, joined[:200])
            check("2. TYT Matematik varsayılan açık (kaynaklı ders)",
                  "TYT Matematik" in page.locator('[data-testid="curriculum-detail"] h3').inner_text())

            rows = page.locator('[data-testid="curriculum-topic"]')
            texts = {n: "" for n in d["names"]}
            for i in range(rows.count()):
                tx = rows.nth(i).inner_text()
                for n in d["names"]:
                    if tx.startswith(n):
                        texts[n] = tx
            t1, t2, t3, t4 = (texts[n] for n in d["names"])
            check("3. çift kaynak 10/10 + 9/10 → Tamamlandı", "Tamamlandı" in t1, t1[:120])
            check("4. çift kaynak 10/10 + 5/10 → Devam ediyor", "Devam ediyor" in t2, t2[:120])
            check("5. tek kaynak 49/50 → Tamamlandı", "Tamamlandı" in t3, t3[:120])
            check("6. dokunulmamış → Başlanmadı", "Başlanmadı" in t4, t4[:120])
            check("7. satırda kaynak kırılımı (kitap adı + 9/10)",
                  "İkinci Kaynak" in t1 and "9/10" in t1 and "Uzun Adlı Birinci" in t1, t1[:160])

            ov = page.evaluate(OVERFLOW_JS, '[data-section="curriculum-panel"]')
            check("8. kırpılmış metin / yatay kaydırma yok",
                  not ov.get("clipped") and not ov.get("hscroll"), str(ov))
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_panel_light.png"), full_page=True)

            page.locator('[data-testid="curriculum-detail"] [role="tab"]', has_text="Tamamlandı").click()
            page.wait_for_timeout(300)
            n_done = page.locator('[data-testid="curriculum-topic"]').count()
            check("9. Tamamlandı filtresi 2 konu gösterir", n_done == 2, str(n_done))
            page.locator('[data-testid="curriculum-detail"] [role="tab"]', has_text="Tümü").click()

            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(400)
            bad = measure(page, '[data-section="curriculum-panel"]', min_ratio=3.0)["bad"]
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_panel_dark.png"), full_page=True)
            check("10. koyu tema kontrast (r<3 yok)", bad == 0, str(bad))

            page.set_viewport_size({"width": 390, "height": 900})
            page.evaluate("() => document.documentElement.classList.remove('dark')")
            page.wait_for_timeout(600)
            ov = page.evaluate(OVERFLOW_JS, '[data-section="curriculum-panel"]')
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_panel_mobile.png"), full_page=True)
            check("11. dar ekranda panel taşmıyor", not ov.get("hscroll"), str(ov))
            ns = page.locator('[data-testid="curriculum-nosource"] summary').inner_text()
            check("12. kaynaksız dersler tek katlanır grupta", "Kaynağı olmayan dersler" in ns, ns)
            b.close()
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
