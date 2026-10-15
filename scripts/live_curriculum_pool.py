"""Müfredat sekmesi × havuz — canlı uçtan uca test (2026-10-14).

Saha sorusu (koç): "havuzda kaynaksız görev verildiğinde ders/konu/test belli; müfredata işleniyor mu?
Konu kapatmayı nereden yapıyoruz? Kaynağı olmayan dersler bölümü eksik."

Kendi verisini kurar/temizler (12. sınıf Sayısal Klasik havuz öğrencisi + gün-gün öğrenci, yerleşik
TYT/AYT dersleri). Doğrular:
  1  dersler kitap var/yok ayrımı olmadan TYT / AYT gruplarında, karşılıksız okul dersi (İnkılap) yok
  2  kitapsız ders kartı "kitap yok" + "havuzda N test"; kitaplı ders "kitap X/Y konu"
  3  kaynaksız havuz kalemi → konu PLANLANDI + "havuzda N test bekliyor"
  4  konusu belirsiz havuz kalemi ayrı listede ("haritaya işlenmez")
  5  öğrenci kap görevini işaretler (gerçek uç) → kalem sayacı ANINDA (sync) → konu DEVAM + kaynaksız N
  6  koç seansta işaretler → "kaynaksız N (M’i seansta)" + havuz kalanı düşer
  7  "Konuyu kapat" → Koç kapattı (DB'de kayıt) · "Geri aç" → eski duruma döner
  8  "Havuza" → miktar → kalem DB'ye konuyla yazılır, satır yenilemesiz güncellenir
  9  gün-gün öğrencide "Havuza" yok, "Konuyu kapat" var
  10 koyu tema kontrast · 390px taşma yok
Dev sunucular (:3000 + :8081) açık olmalı.
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task,
    TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.topic_closure import TopicClosure  # noqa: E402
from app.services import curriculum_progress as cp, pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lcpl_{secrets.token_hex(3)}"
PWD = "LiveCurrPool!234"
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


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"Müfredat {tag}",
             role=role, is_active=True, must_change_password=False, **kw)
    db.add(u)
    db.flush()
    return u


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = _user(db, "koc", UserRole.TEACHER)
        common = dict(teacher_id=coach.id, grade_level=12, track=Track.SAYISAL, entry_year_grade9=2023)
        st = _user(db, "havuz", UserRole.STUDENT, program_mode="havuz", **common)
        gg = _user(db, "gungun", UserRole.STUDENT, **common)
        S = {n: db.query(Subject).filter(Subject.name == n, Subject.is_builtin.is_(True)).first()
             for n in ("TYT Matematik", "TYT Kimya", "AYT Matematik")}
        leaves = cp.leaf_topics_for_student(db, st, coach.id, [s.id for s in S.values()]).by_subject
        mat0 = leaves[S["TYT Matematik"].id][0]
        k0, k1 = leaves[S["TYT Kimya"].id][0], leaves[S["TYT Kimya"].id][1]
        # TYT Matematik'e kitap (ilk konu eşli) — kitaplı ders
        book = Book(name=f"{PFX} TYT Mat SB", subject_id=S["TYT Matematik"].id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label=mat0.name, test_count=10, order=1, topic_id=mat0.id)
        db.add(sec)
        db.flush()
        for u in (st, gg):
            sb = StudentBook(student_id=u.id, book_id=book.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        p = pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=2),
                           expected_next_on=today + timedelta(days=5))
        it_k = pm.add_item(db, period=p, student=st, subject=S["TYT Kimya"], quantity=6, unit="test", topic=k0)
        pm.add_item(db, period=p, student=st, subject=S["TYT Kimya"], quantity=2, unit="sayfa",  # 2026-10-14: konusuz test yasak
                    label=f"{PFX} Serbest kalem")
        task = pm.put_in_cup(db, item=it_k, day=today, count=4)
        db.commit()
        return {"coach": coach.id, "st": st.id, "gg": gg.id, "email": coach.email, "st_email": st.email,
                "book": book.id, "item": it_k.id, "task": task.id, "task_item": task.book_items[0].id,
                "k0": k0.id, "k0_name": k0.name, "k1": k1.id, "k1_name": k1.name,
                "kimya": S["TYT Kimya"].id, "today": today}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st"], d["gg"], d["coach"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(TopicClosure).where(TopicClosure.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == d["book"]))
        db.execute(sa_delete(Book).where(Book.id == d["book"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


OVERFLOW_JS = """(sel) => {
  const root = document.querySelector(sel); if (!root) return {missing: true};
  const r = root.getBoundingClientRect();
  return {hscroll: r.right > window.innerWidth + 1 || document.documentElement.scrollWidth > window.innerWidth + 1};
}"""
TEXT = "(sel) => { const el = document.querySelector(sel); return el ? el.textContent : ''; }"


def row_text(page, topic_id) -> str:
    return page.evaluate(TEXT, f'[data-topic-id="{topic_id}"]')


def open_subject(page, name):
    page.locator('[data-testid="curriculum-subject"]', has_text=name).first.click()
    page.wait_for_timeout(500)


def goto_curriculum(page, sid):
    page.goto(f"{WEB}/teacher/students/{sid}#curriculum", wait_until="networkidle")
    page.reload(wait_until="networkidle")  # yalnız #hash farkı olan goto belgeyi yenilemez → eski veri
    page.wait_for_selector('[data-section="curriculum-panel"]', timeout=20000)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(500)


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    print(f"\n=== Müfredat × havuz — canlı ({PFX}) ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', d["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            goto_curriculum(page, d["st"])

            nav = page.evaluate(TEXT, '[data-section="curriculum:subjects"]')
            check("1a dersler TYT / AYT gruplarında (kitap var/yok ayrımı yok)",
                  "TYT dersleri" in nav and "AYT dersleri" in nav
                  and page.query_selector('[data-testid="curriculum-nosource"]') is None, nav[:160])
            check("1b karşılıksız okul dersi (İnkılap) listede yok", "İnkılap" not in nav)
            check("1c kitapsız sınav dersleri de listede (TYT Kimya, AYT Matematik, TYT Biyoloji)",
                  all(x in nav for x in ("TYT Kimya", "AYT Matematik", "TYT Biyoloji")))
            kim = page.locator('[data-testid="curriculum-subject"]', has_text="TYT Kimya").first.text_content()
            mat = page.locator('[data-testid="curriculum-subject"]', has_text="TYT Matematik").first.text_content()
            check("2a TYT Kimya kartı: 'kitap yok' + 'havuzda 6 test'", "kitap yok" in kim and "havuzda 6 test" in kim, kim)
            check("2b TYT Matematik kartı: 'kitap 1/…' (kitaplı ders)", "kitap 1/" in mat, mat)

            open_subject(page, "TYT Kimya")
            r = row_text(page, d["k0"])
            check("3 kaynaksız havuz kalemi → Planlandı + 'havuzda 6 test bekliyor' + 'kitap yok'",
                  "Planlandı" in r and "havuzda 6 test bekliyor" in r and "kitap yok" in r, r)
            un = page.evaluate(TEXT, '[data-section="curriculum:pool-unlinked"]')
            check("4 konusu belirsiz kalem ayrı listede (haritaya işlenmez)", "Serbest kalem" in un and "işlenmez" in un, un[:160])

            # 5 — öğrenci kap görevini gerçek uçtan işaretler
            sctx = b.new_context()
            sp = sctx.new_page()
            lr = sp.request.post(f"{WEB}/api/v2/auth/login", data={"email": d["st_email"], "password": PWD})
            rr = sp.request.post(f"{WEB}/api/v2/student/tasks/{d['task']}/items/{d['task_item']}/set-completed",
                                 data={"completed": 3})
            with SessionLocal() as db:
                it = db.get(PoolItem, d["item"])
                check("5a öğrenci işaretledi → havuz kalemi sayacı ANINDA 3 (havuz ekranı açılmadan)",
                      lr.status == 200 and rr.status == 200 and it.completed == 3,
                      f"login={lr.status} set={rr.status} completed={it.completed}")
            goto_curriculum(page, d["st"])
            open_subject(page, "TYT Kimya")
            r = row_text(page, d["k0"])
            check("5b konu Devam ediyor + 'kaynaksız 3 test çözüldü' + 'havuzda 3 test bekliyor'",
                  "Devam ediyor" in r and "kaynaksız 3 test çözüldü" in r and "havuzda 3 test bekliyor" in r, r)

            # 6 — koç seansta işaretler
            mr = page.request.post(f"{WEB}/api/v2/teacher/students/{d['st']}/pool/items/{d['item']}/session-mark",
                                   data={"count": 2})
            goto_curriculum(page, d["st"])
            open_subject(page, "TYT Kimya")
            r = row_text(page, d["k0"])
            check("6 seans işareti: 'kaynaksız 5 test çözüldü (2’i seansta)' + 'havuzda 1 test'",
                  mr.status == 200 and "kaynaksız 5 test çözüldü" in r and "2’i seansta" in r and "havuzda 1 test" in r,
                  f"{mr.status} {r}")

            # 7 — konuyu kapat / geri aç
            page.locator(f'[data-topic-id="{d["k0"]}"] button:has-text("Konuyu kapat")').click()
            page.wait_for_timeout(1500)
            r = row_text(page, d["k0"])
            with SessionLocal() as db:
                closed = db.query(TopicClosure).filter(TopicClosure.student_id == d["st"],
                                                       TopicClosure.topic_id == d["k0"]).count()
            check("7a Konuyu kapat → 'Koç kapattı' + 'Geri aç' (yenilemesiz) + DB kaydı",
                  "Koç kapattı" in r and "Geri aç" in r and closed == 1, f"{r} closed={closed}")
            kim = page.locator('[data-testid="curriculum-subject"]', has_text="TYT Kimya").first.text_content()
            check("7b ders kartı '1 tamam'", "1 tamam" in kim, kim)
            page.locator(f'[data-topic-id="{d["k0"]}"] button:has-text("Geri aç")').click()
            page.wait_for_timeout(1500)
            r = row_text(page, d["k0"])
            check("7c Geri aç → yeniden 'Devam ediyor'", "Devam ediyor" in r and "Koç kapattı" not in r, r)

            # 7d — seans ekranından konu kapatma (koç seansta öğrenciyle konuşurken)
            page.goto(f"{WEB}/teacher/students/{d['st']}/pool/session", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:session:items"]', timeout=15000)
            page.locator('[data-section="pool:session:items"] li', has_text=d["k0_name"]).locator(
                'button:has-text("Konuyu kapat")').click()
            page.wait_for_timeout(1500)
            li = page.locator('[data-section="pool:session:items"] li', has_text=d["k0_name"]).text_content()
            with SessionLocal() as db:
                closed = db.query(TopicClosure).filter(TopicClosure.student_id == d["st"],
                                                       TopicClosure.topic_id == d["k0"]).count()
            check("7d seans ekranında 'Konuyu kapat' → 'konu kapalı' + DB kaydı", "konu kapalı" in li and closed == 1,
                  f"{li[:160]} closed={closed}")
            goto_curriculum(page, d["st"])
            open_subject(page, "TYT Kimya")
            r = row_text(page, d["k0"])
            check("7e müfredatta aynı konu 'Koç kapattı'", "Koç kapattı" in r, r)
            page.locator(f'[data-topic-id="{d["k0"]}"] button:has-text("Geri aç")').click()
            page.wait_for_timeout(1200)

            # 8 — havuza ekle
            page.locator(f'[data-topic-id="{d["k1"]}"] button:has-text("Havuza")').click()
            page.wait_for_selector(f'[data-topic-id="{d["k1"]}"] [data-section="curriculum:pool-add"]', timeout=5000)
            page.locator(f'[data-topic-id="{d["k1"]}"] [data-section="curriculum:pool-add"] button', has_text="5").first.click()
            page.locator(f'[data-topic-id="{d["k1"]}"] button:has-text("Havuza ekle")').click()
            page.wait_for_timeout(2000)
            with SessionLocal() as db:
                it2 = (db.query(PoolItem).filter(PoolItem.student_id == d["st"], PoolItem.topic_id == d["k1"],
                                                 PoolItem.removed_at.is_(None)).first())
            r = row_text(page, d["k1"])
            check("8a Havuza ekle → DB'de konulu kaynaksız kalem (5 test)", it2 is not None and it2.quantity == 5
                  and it2.book_id is None, str(it2 and (it2.quantity, it2.book_id)))
            check("8b satır yenilemesiz 'Planlandı' + 'havuzda 5 test bekliyor'",
                  "Planlandı" in r and "havuzda 5 test bekliyor" in r, r)

            ov = page.evaluate(OVERFLOW_JS, '[data-section="curriculum-panel"]')
            check("10a 1440px yatay taşma yok", not ov.get("hscroll"), str(ov))
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_pool_light.png"), full_page=True)
            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(400)
            m = measure(page, '[data-testid="curriculum-detail"]', min_ratio=4.5)
            check("10b koyu tema ders ayrıntısı okunur (≥4.5)", m["bad"] == 0, str(m["worst"][:3]))
            m = measure(page, '[data-section="curriculum:subjects"]', min_ratio=4.5)
            check("10c koyu tema ders listesi okunur (≥4.5)", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_pool_dark.png"), full_page=True)
            page.evaluate("() => document.documentElement.classList.remove('dark')")
            page.set_viewport_size({"width": 390, "height": 900})
            page.wait_for_timeout(600)
            ov = page.evaluate(OVERFLOW_JS, '[data-section="curriculum-panel"]')
            check("10d 390px yatay taşma yok", not ov.get("hscroll"), str(ov))
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_pool_mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})

            # 9 — gün-gün öğrenci
            goto_curriculum(page, d["gg"])
            open_subject(page, "TYT Kimya")
            r = row_text(page, d["k0"])
            check("9 gün-gün öğrencide 'Havuza' yok, 'Konuyu kapat' var",
                  "Havuza" not in r and "Konuyu kapat" in r, r)
            b.close()
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
