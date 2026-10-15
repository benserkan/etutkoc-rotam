"""Havuz rehber editörü — GERÇEK TARAYICI (Adım 2, 2026-10-12).

Dev :3000 + :8081 açık olmalı. Sistem python (playwright) ile koş:
  python scripts/live_pool_editor.py

Akış: gün-gün öğrenci → moda geç → dönem aç → ders → konu → 4 test → kalem listede ·
AYT kilidi (alan boş) · serbest metin ayrıştır → böyle ekle · eksik ders şeridi ·
önizleme · kaldır (onay) · başlıkta "Haftalık Havuz" · /week havuz kartı · koyu tema kontrast.
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
    Book, BookSection, BookType, ClassGroup, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, SuspiciousIp, Task, TaskBookItem, Topic, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lpe_{secrets.token_hex(3)}"
PWD = "HavuzCanli!2345"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Canlı Rehber", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Canlı Havuz Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12, class_group="12-B")
        db.add(st)
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        tur = Subject(name=f"{PFX} TYT Türkçe", teacher_id=coach.id, exam_section=ExamSection.TYT)
        ayt = Subject(name="AYT Kimya", teacher_id=coach.id, exam_section=ExamSection.AYT_SAY)
        db.add_all([tyt, tur, ayt])
        db.flush()
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=tyt.id, name="Köklü Sayılar", order=2, teacher_id=coach.id)
        db.add_all([t1, t2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal TYT Mat", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        s1 = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=8, order=1, topic_id=t1.id)
        s2 = BookSection(book_id=b.id, label="Köklü Sayılar", test_count=6, order=2, topic_id=t2.id)
        db.add_all([s1, s2])
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=0))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s2.id, reserved_count=0, completed_count=0))
        db.commit()
        return {"coach": coach.id, "st": st.id, "subjects": [tyt.id, tur.id, ayt.id], "book": b.id,
                "email": f"{PFX}_t@test.invalid", "tyt_name": tyt.name, "tur_name": tur.name}


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
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(ClassGroup).where(ClassGroup.scope_key == f"coach:{ids['coach']}"))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids.update(seed())
    sid = ids["st"]
    print(f"\n=== Havuz rehber editörü — canlı ({PFX}, öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.on("dialog", lambda d: d.accept())
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            # 1 — gün-gün öğrenci: başlıkta Haftalık Program, havuz sayfasında mod kartı
            page.goto(f"{WEB}/teacher/students/{sid}", wait_until="networkidle")
            page.wait_for_timeout(2000)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(500)
            check("1a başlıkta 'Haftalık Program' (gün-gün)", page.query_selector('[data-quick-actions] a:has-text("Haftalık Program")') is not None)
            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_timeout(1500)
            check("1b mod kartı: 'Bu öğrenci gün gün programda'", page.query_selector('text=Bu öğrenci gün gün programda') is not None)
            page.click('[data-testid="mode-switch-open"]')
            # 2026-10-15: geçiş önce etki penceresi açar; ilk dönemi burada açmayıp test kendi "Dönem aç" adımına geçer
            page.wait_for_selector('[data-section="mode-switch:effects"]', timeout=15000)
            page.uncheck('[data-section="mode-switch:effects"] input[type="checkbox"]')
            page.click('[data-testid="mode-switch-submit"]')
            page.wait_for_selector('button:has-text("Dönem aç")', timeout=15000)
            check("1c moda geçildi → dönem aç formu + rozet", page.query_selector('text=Havuz modu') is not None)

            # 2 — dönem aç
            page.click('button:has-text("Dönem aç")')
            page.wait_for_selector('[data-section="pool:add"]', timeout=10000)
            check("2a dönem açıldı → ekleme paneli + özet", page.query_selector('text=Beklenen seans') is not None
                  and page.query_selector('text=Günde gereken') is not None)

            # 3 — AYT kilidi (alan boş)
            check("3a alan boş → AYT kilit notu + AYT çipi yok",
                  page.query_selector('[data-section="pool:add"] >> text=Alan girilmedi') is not None
                  and page.query_selector('[data-section="pool:add"] button:has-text("AYT Kimya")') is None)

            # 4 — ders → Nereden? (öğrencinin kitapları, kitabın kendi bölümleri) → 4 test → ekle
            page.click(f'[data-section="pool:add"] button:has-text("{ids["tyt_name"]}")')
            page.wait_for_selector('[data-section="pool:add:books"]', timeout=10000)
            books_txt = page.query_selector('[data-section="pool:add:books"]').inner_text()
            check("4a kaynağı olan ders → 'Öğrencinin kitapları' açık: kitap + bölüm 'Üslü Sayılar · 8 kaldı'",
                  "Orijinal" in books_txt and "Üslü Sayılar" in books_txt and "8 kaldı" in books_txt, books_txt[:200])
            page.click('[data-section="pool:add:books"] button:has-text("Üslü Sayılar")')
            page.wait_for_selector('[data-section="pool:add:book-summary"]', timeout=5000)
            summ = page.query_selector('[data-section="pool:add:book-summary"]').inner_text()
            check("4b kitap özeti (8 verilebilir) + 'kalanı ver (8)', birim kitaptan sabit",
                  "8 verilebilir" in summ and page.query_selector('button:has-text("kalanı ver (8)")') is not None
                  and page.query_selector('[data-section="pool:add"] [role="radiogroup"][aria-label="Birim"]') is None, summ[:200])
            page.click('[data-section="pool:add"] button:text-is("4")')
            page.click('[data-testid="pool-add-submit"]')
            page.wait_for_selector('[data-section="pool:list"] >> text=4 test', timeout=10000)
            li = page.query_selector_all('[data-section="pool:list"] li')
            check("4c kalem listede (1) · kitap — bölüm adıyla · 'kitapta 0/8 çözüldü'",
                  len(li) == 1 and "Orijinal" in li[0].inner_text() and "kitapta 0/8" in li[0].inner_text(), li[0].inner_text()[:160] if li else "-")
            page.wait_for_timeout(800)
            books_txt = page.query_selector('[data-section="pool:add:books"]').inner_text()
            check("4d özet 4 birim · kitap listesinde 'SON' + '4 havuzda' + '4 kaldı' (verilebilir)",
                  page.query_selector('text=0 / 4 birim') is not None and "SON" in books_txt and "4 havuzda" in books_txt
                  and "4 kaldı" in books_txt, books_txt[:200])
            with SessionLocal() as db:
                sp = db.query(SectionProgress).join(StudentBook).filter(StudentBook.student_id == sid).all()
                check("4e rezerv açılmadı (0)", all(s.reserved_count == 0 for s in sp))
            step1 = page.query_selector('[data-section="pool:add"] li[data-step="1"]').inner_text()
            check("4f ekledikten sonra ders seçili kalır (özet + '1 kitap' + Değiştir), Nereden? adımı yeniden açık",
                  ids["tyt_name"] in step1 and "1 kitap" in step1 and "Değiştir" in step1
                  and page.query_selector('[data-section="pool:add:books"]') is not None, step1[:120])
            # müfredat konusu yolu: arama + kitapta var önerisi → kitaptan ver
            page.click('[data-section="pool:add"] [role="tab"]:has-text("Müfredat konusu")')
            page.wait_for_selector('[data-section="pool:add"] input[aria-label="Konu ara"]', timeout=5000)
            page.fill('[data-section="pool:add"] input[aria-label="Konu ara"]', "köklü")
            page.wait_for_timeout(300)
            check("4g konu arama süzer (Üslü gizlenir)",
                  page.query_selector('[data-section="pool:add:topics"] button:has-text("Üslü Sayılar")') is None)
            page.click('[data-section="pool:add:topics"] button:has-text("Köklü Sayılar")')
            page.wait_for_selector('[data-section="pool:add:book-hint"]', timeout=5000)
            hint = page.query_selector('[data-section="pool:add:book-hint"]').inner_text()
            check("4h müfredat konusu kitapta varsa 'Kitaptan ver' önerisi (kitap takibi kaçmasın)",
                  "Orijinal" in hint and "Köklü Sayılar" in hint and "Kitaptan ver" in hint, hint[:200])
            check("4i müfredat yolunda 'Kitap adı (not)' alanı var", page.query_selector('input[placeholder*="Palme · Yayın Denizi"]') is not None)
            page.click('[data-section="pool:add:book-hint"] button:has-text("Kitaptan ver")')
            page.wait_for_selector('[data-section="pool:add:book-summary"]', timeout=5000)
            check("4j 'Kitaptan ver' → kitap bölümüne geçti", "Köklü Sayılar" in page.query_selector('[data-section="pool:add:book-summary"]').inner_text())
            page.click('[data-section="pool:add"] li[data-step="2"] button:has-text("Değiştir")')
            page.wait_for_timeout(300)

            # 5 — serbest metin (Hızlı yaz sekmesi)
            page.click('[data-section="pool:add"] [role="tab"]:has-text("Hızlı yaz")')
            page.wait_for_selector('input[placeholder*="345 matematik"]', timeout=5000)
            page.fill('input[placeholder*="345 matematik"]', "Orijinal · Köklü Sayılar · 2 test")
            page.click('button:has-text("Ayrıştır")')
            page.wait_for_selector('button:has-text("Böyle ekle")', timeout=10000)
            chips = [c.inner_text() for c in page.query_selector_all('[data-section="pool:add"] span.rounded-full')]
            check("5a çipler: konu + kitap + 2 + test", any("Köklü" in c for c in chips) and "2" in chips, str(chips))
            page.click('button:has-text("Böyle ekle")')
            page.wait_for_timeout(1500)
            li = page.query_selector_all('[data-section="pool:list"] li')
            check("5b ikinci kalem eklendi", len(li) == 2, str(len(li)))

            # 6 — eksik ders şeridi + önizleme
            miss = page.query_selector('[data-section="pool:missing"]')
            check("6a eksik ders şeridi Türkçe'yi sayar", miss is not None and ids["tur_name"] in miss.inner_text())
            page.click(f'[data-section="pool:missing"] button:has-text("{ids["tur_name"]}")')
            page.wait_for_timeout(600)
            step1 = page.query_selector('[data-section="pool:add"] li[data-step="1"]')
            check("6c eksik ders çipi → panel 'Konudan seç' sekmesinde o derse atlar",
                  step1 is not None and ids["tur_name"] in step1.inner_text(), step1.inner_text()[:120] if step1 else "-")
            page.click('button:has-text("Gün gün nasıl görünür?")')
            page.wait_for_timeout(400)
            check("6b önizleme '~N birim' kutuları", page.query_selector('text=/~\\d+ birim/') is not None)

            # 7 — kaldır (onay)
            page.query_selector_all('[data-section="pool:list"] button[title="Kaldır"]')[0].click()
            page.wait_for_timeout(1500)
            li = page.query_selector_all('[data-section="pool:list"] li')
            check("7a kalem kaldırıldı (1 kaldı)", len(li) == 1, str(len(li)))

            # 8 — başlık + week sayfası
            page.goto(f"{WEB}/teacher/students/{sid}", wait_until="networkidle")
            page.wait_for_timeout(1500)
            check("8a başlıkta 'Haftalık Havuz' düğmesi", page.query_selector('[data-quick-actions] a:has-text("Haftalık Havuz")') is not None)
            page.goto(f"{WEB}/teacher/students/{sid}/week", wait_until="networkidle")
            page.wait_for_timeout(1000)
            check("8b /week havuz öğrencisinde gün-gün editör açılmaz, havuz kartı",
                  page.query_selector('text=haftalık havuz modunda') is not None
                  and page.query_selector('a:has-text("Haftalık havuzu aç")') is not None)

            # 8c — İzle modu (2026-10-14): kalemli havuz açılınca varsayılan İzle; gün gün + ders ders + bekleyenler
            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:watch"]', timeout=15000)
            check("8c kalemli havuzda varsayılan İzle modu (ekleme paneli yok)",
                  page.query_selector('[data-section="pool:add"]') is None
                  and page.query_selector('[data-section="pool:view"] button[aria-pressed="true"]:has-text("İzle")') is not None)
            page.wait_for_selector('[data-section="pool:days"] button[data-day]', timeout=10000)
            check("8d gün gün şeridi + derslere göre ilerleme + bekleyen kalemler",
                  page.query_selector('[data-section="pool:subjects"]') is not None
                  and page.query_selector('[data-section="pool:watch:open"]') is not None)
            page.click('[data-section="pool:view"] button:has-text("Düzenle")')
            page.wait_for_selector('[data-section="pool:add"]', timeout=10000)
            check("8e Düzenle'ye geçince ekleme paneli", True)

            # 9 — koyu tema kontrast
            page.goto(f"{WEB}/teacher/students/{sid}/pool?mod=duzenle", wait_until="networkidle")
            page.wait_for_timeout(1500)
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            for sec in ("pool:period", "pool:list", "pool:add", "pool:missing"):
                m = measure(page, f'[data-section="{sec}"]', min_ratio=4.5)
                check(f"9 koyu tema {sec} okunur (≥4.5)", m["bad"] == 0, str(m["worst"][:3]))
            # 3. adım (miktar ve kaynak) açıkken de ölç
            page.click(f'[data-section="pool:add"] button:has-text("{ids["tyt_name"]}")')
            page.wait_for_selector('[data-section="pool:add:books"] button:has-text("Üslü Sayılar")', timeout=10000)
            m = measure(page, '[data-section="pool:add"]', min_ratio=4.5)
            check("9 koyu tema: kitap listesi adımı okunur (≥4.5)", m["bad"] == 0, str(m["worst"][:3]))
            page.click('[data-section="pool:add:books"] button:has-text("Üslü Sayılar")')
            page.wait_for_selector('[data-testid="pool-add-submit"]', timeout=5000)
            m = measure(page, '[data-section="pool:add"]', min_ratio=4.5)
            check("9 koyu tema: miktar/kaynak adımı okunur (≥4.5)", m["bad"] == 0, str(m["worst"][:3]))
            check("9 ekleme paneli yatay taşmıyor", page.evaluate(
                "() => { const e = document.querySelector('[data-section=\"pool:add\"]'); return e.scrollWidth <= e.clientWidth + 1; }"))
            os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_editor_dark.png"), full_page=True)
            page.evaluate("document.documentElement.classList.remove('dark')")
            page.wait_for_timeout(300)
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_editor_light.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(500)
            check("9 390px: sayfa yatay kaymıyor", page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_editor_mobile.png"), full_page=True)
            b.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
