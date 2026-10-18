"""Havuz ekleme paneli — liste konum hafızası + kalem miktar düzeltme (GERÇEK TARAYICI, 2026-10-18).

Saha: koç kitabın 25. bölümünden kalem verince liste başa dönüyordu; sonraki kalem için yeniden
kaydırmak gerekiyordu. Kalemin test sayısı da (7 → 5) düzenlenemiyordu.

  A1 kitap listesinde aşağıdaki bölümden ekle → adım 2 tekrar açılınca liste o bölümde (kaydırılmış, işaretli)
  A2 müfredat konusundan ekle → konu listesi o konuda + aynı sınıf süzgeci
  Q1 havuz listesinde "7 test" → düzenle → 5 → "5 test" (DB) · Q2 yapılanın altı reddedilir (DB değişmez)

Dev :3000 + :8081 açık olmalı:  python scripts/live_pool_add_anchor.py
"""
from __future__ import annotations

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
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, SuspiciousIp,
    Task, TaskBookItem, Topic, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.services import pool_mode  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lpa_{secrets.token_hex(3)}"
PWD = "HavuzCanli!2345"
passed = 0
failed: list[str] = []
ids: dict = {}


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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Canlı Rehber",
                     role=UserRole.TEACHER, is_active=True)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Konum Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12)
        db.add(st); db.flush()
        subj = Subject(name=f"{PFX} TYT Kimya", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(subj); db.flush()
        topics = [Topic(subject_id=subj.id, name=f"Kimya Konusu {i:02d}", order=i, teacher_id=coach.id) for i in range(1, 31)]
        db.add_all(topics); db.flush()
        b = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} Orbital Kimya", type=BookType.SORU_BANKASI)
        db.add(b); db.flush()
        secs = [BookSection(book_id=b.id, label=f"Bölüm {i:02d}", test_count=8, order=i) for i in range(1, 31)]
        db.add_all(secs); db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb); db.flush()
        pool_mode.set_program_mode(db, st, "havuz")
        p = pool_mode.open_period(db, student=st, coach=coach, opened_on=date.today())
        db.commit()
        return {"coach": coach.id, "st": st.id, "subj": subj.id, "book": b.id, "pid": p.id,
                "email": coach.email, "subj_name": subj.name, "sec25": secs[24].id, "topic24": topics[23].id}


def cleanup():
    with SessionLocal() as db:
        u = [ids["coach"], ids["st"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
        db.execute(sa_delete(Book).where(Book.id == ids["book"]))
        db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
        db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids.update(seed())
    sid = ids["st"]
    print(f"\n=== Havuz ekleme konum hafızası + miktar — canlı ({PFX}) ===\n")
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chrome", headless=True)
            page = br.new_page(viewport={"width": 1440, "height": 900})
            page.on("dialog", lambda d: d.accept())
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{sid}/pool?mod=duzenle", wait_until="networkidle")
            page.wait_for_timeout(1500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click(); page.wait_for_timeout(400)

            add = '[data-section="pool:add"]'
            page.click(f'{add} button:has-text("{ids["subj_name"]}")')
            page.wait_for_selector('[data-section="pool:add:books"]', timeout=10000)
            sel = f'[data-section="pool:add:books"] [data-section-id="{ids["sec25"]}"]'
            page.locator(sel).scroll_into_view_if_needed()
            page.click(sel)
            page.click(f'{add} button:text-is("3")')
            page.click('[data-testid="pool-add-submit"]')
            page.wait_for_selector('[data-section="pool:list"] >> text=Bölüm 25', timeout=10000)
            page.wait_for_selector(sel, timeout=5000)
            page.wait_for_timeout(400)
            st = page.evaluate(f"""() => {{
              const el = document.querySelector('{sel}'); const ul = el.closest('ul');
              const a = el.getBoundingClientRect(), b = ul.getBoundingClientRect();
              return {{ top: ul.scrollTop, inView: a.top >= b.top - 1 && a.bottom <= b.bottom + 1,
                        marked: el.className.includes('ring-1') }};
            }}""")
            check("A1 eklemeden sonra kitap listesi Bölüm 25'te açılır (kaydırılmış + görünür + işaretli)",
                  st["top"] > 100 and st["inView"] and st["marked"], st)

            # A2 — müfredat konusu yolu
            page.click(f'{add} [role="tab"]:has-text("Müfredat konusundan")')
            tsel = f'[data-section="pool:add:topics"] [data-topic-id="{ids["topic24"]}"]'
            page.wait_for_selector(tsel, timeout=10000)
            page.locator(tsel).scroll_into_view_if_needed()
            page.click(tsel)
            page.click(f'{add} button:text-is("2")')
            page.click('[data-testid="pool-add-submit"]')
            page.wait_for_selector('[data-section="pool:list"] >> text=Kimya Konusu 24', timeout=10000)
            page.wait_for_selector(tsel, timeout=5000)
            page.wait_for_timeout(400)
            st = page.evaluate(f"""() => {{
              const el = document.querySelector('{tsel}'); const box = el.closest('.overflow-y-auto');
              const a = el.getBoundingClientRect(), b = box.getBoundingClientRect();
              return {{ top: box.scrollTop, inView: a.top >= b.top - 1 && a.bottom <= b.bottom + 1,
                        marked: el.className.includes('ring-1') }};
            }}""")
            check("A2 eklemeden sonra konu listesi Konu 24'te, sekme 'Müfredat' açık kalır",
                  st["top"] > 100 and st["inView"] and st["marked"], st)

            # Q1 — miktar düzelt (Bölüm 25 kalemi: 3 test → 5)
            row = page.locator('[data-section="pool:list"] li', has_text="Bölüm 25")
            row.locator('button[aria-label^="Miktarı değiştir"]').click()
            page.fill('[data-section="pool:item:qty-edit"] input', "5")
            page.click('[data-section="pool:item:qty-edit"] button:has-text("Kaydet")')
            page.wait_for_timeout(1200)
            with SessionLocal() as db:
                it = db.query(PoolItem).filter(PoolItem.student_id == sid, PoolItem.book_section_id == ids["sec25"]).one()
                q = it.quantity
                iid = it.id
            check("Q1 '3 test' → düzenle → 5: DB 5 + satırda '5 test'",
                  q == 5 and "5 test" in row.inner_text(), (q, row.inner_text()[:120]))

            # Q2 — yapılanın altına inmez
            with SessionLocal() as db:
                db.get(PoolItem, iid).session_marked = 4
                db.commit()
            page.reload(wait_until="networkidle"); page.wait_for_timeout(1200)
            row = page.locator('[data-section="pool:list"] li', has_text="Bölüm 25")
            row.locator('button[aria-label^="Miktarı değiştir"]').click()
            page.fill('[data-section="pool:item:qty-edit"] input', "2")
            page.click('[data-section="pool:item:qty-edit"] button:has-text("Kaydet")')
            page.wait_for_timeout(1500)
            with SessionLocal() as db:
                q = db.get(PoolItem, iid).quantity
            toast = page.locator("text=En az 4 olabilir").count()
            check("Q2 4 yapılmışken 2 → reddedilir (DB 5 kalır) + açıklayan uyarı", q == 5 and toast > 0, (q, toast))
            page.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".shots", "pool_qty_edit.png"))
            br.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
