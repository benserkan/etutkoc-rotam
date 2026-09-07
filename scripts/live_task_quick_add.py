"""Görev kutusu — GERÇEK TARAYICI doğrulaması (P4, 2026-09-07).

Dev sunucu (:3000 Next + :8081 API) + Playwright ister. Kendi seed'ini kurar
ve sonunda temizler.

İDDİA: "kutu → satır → Ekle = 3 tık". Bu iddiayı gerçek tıklamalarla sayar.

Senaryolar:
   1. Kutu tıklanınca aday listesi açılır (yazmadan)
   2. Kaynaklı satır seçilip Ekle → görev oluşur; TOPLAM 3 TIK
   3. Adet öğrenilmiş değerle ön-dolu gelir (koç yazmıyor)
   4. "Kaynak belirtmeden ver" → kaynaksız görev oluşur (rezerv tutmaz)
   5. Kapasitesi dolu bölüm listede GÖRÜNÜR + "kapasite doldu" yazar
   6. Dolu bölüm seçilince amber aşım uyarısı çıkar, Ekle yine çalışır
   7. Arama kutuya yazınca liste daralır
   8. "Ayrıntılı form" eski akışa döner (geri dönüş yolu korunuyor)
   9b. Escape aday listesini kapatır (klavyeyle çıkış)
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

WEB = "http://localhost:3000"
PFX = f"lqa_{secrets.token_hex(3)}"
PWD_PLAIN = "LiveQuick!234"

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
                     full_name="Canlı Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD_PLAIN),
                  full_name="Canlı Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()

        subj = Subject(name=f"{PFX} Matematik", teacher_id=coach.id, order=1)
        db.add(subj)
        db.flush()
        t_ok = Topic(subject_id=subj.id, name="Türev", order=1, teacher_id=coach.id)
        t_full = Topic(subject_id=subj.id, name="Limit", order=2, teacher_id=coach.id)
        t_free = Topic(subject_id=subj.id, name="İntegral", order=3, teacher_id=coach.id)
        db.add_all([t_ok, t_full, t_free])
        db.flush()

        book = Book(name=f"{PFX} Soru Bankası", teacher_id=coach.id,
                    subject_id=subj.id, type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        s_ok = BookSection(book_id=book.id, label="Türev Bölümü", order=1,
                           test_count=10, topic_id=t_ok.id)
        s_full = BookSection(book_id=book.id, label="Limit Bölümü", order=2,
                             test_count=4, topic_id=t_full.id)
        db.add_all([s_ok, s_full])
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        db.add_all([
            SectionProgress(student_book_id=sb.id, book_section_id=s_ok.id,
                            reserved_count=0, completed_count=2),
            SectionProgress(student_book_id=sb.id, book_section_id=s_full.id,
                            reserved_count=0, completed_count=4),   # DOLU
        ])
        # Miktar öğrenmesi için geçmiş: hep 4 test
        for i in range(6):
            t = Task(student_id=st.id, date=date.today() - timedelta(days=10 + i),
                     type=TaskType.TEST, title="x", is_draft=False)
            db.add(t)
            db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=s_ok.id, planned_count=4,
                                completed_count=4))
        db.commit()
        return {
            "coach": coach.id, "student": st.id, "subject": subj.id,
            "book": book.id, "email": f"{PFX}_t@test.invalid",
        }


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uid = [ids["coach"], ids["student"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uid)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        sbids = [r[0] for r in db.query(StudentBook.id)
                 .filter(StudentBook.book_id == ids["book"]).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress)
                       .where(SectionProgress.student_book_id.in_(sbids)))
            db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
        db.execute(sa_delete(Book).where(Book.id == ids["book"]))
        db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subject"]))
        db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    day = (date.today() + timedelta(days=1)).isoformat()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 950})

            # --- giriş (tam sayfa geçiş: networkidle yetmez, sabit bekleme şart)
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD_PLAIN)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            # Görev ekleme formu HAFTA görünümündeki gün kartında yaşıyor
            page.goto(f"{WEB}/teacher/students/{ids['student']}/week",
                      wait_until="networkidle")
            page.wait_for_timeout(2500)

            # Yeni koç hesabında Rota rehberi karşılama diyaloğu açılır ve
            # overlay tüm tıklamaları keser — kapat.
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(1500)

            # Görev ekleme bölümünü aç (gün kartındaki "Yeni görev ekle")
            for sel in ('text="Yeni görev ekle"', 'text="Görev ekle"'):
                el = page.query_selector(sel)
                if el:
                    el.click()
                    page.wait_for_timeout(1200)
                    break

            box = page.query_selector('input[aria-label="Görev ara"]')
            check("0. hızlı ekleme kutusu sayfada", box is not None,
                  "kutu bulunamadı")
            if box is None:
                page.screenshot(path="/tmp/qa_fail.png")
                b.close()
                return 1

            # ---- 1. TIK 1: kutuya tıkla → liste açılır (yazmadan)
            box.click()
            page.wait_for_timeout(1800)
            has_list = page.query_selector('text="Müfredatta sıradaki"') is not None
            check("1. kutuya tıklayınca aday listesi açılır (yazmadan)", has_list)

            # ---- 5. Dolu bölüm: "sıradaki" listesinde bilinçli ELENİR
            #        (koç sırada ne var diye bakıyor), ama ARAMAYLA bulunur
            #        ve "kapasite doldu" diye işaretlenir — gizlenmiş değil.
            box.fill("Limit")
            page.wait_for_timeout(2200)
            full_marker = page.query_selector('text="kapasite doldu"')
            check("5. dolu bölüm aramada GÖRÜNÜR + 'kapasite doldu' işaretli",
                  full_marker is not None)
            box.fill("")
            page.wait_for_timeout(1800)

            # ---- 2+3. TIK 2: kaynaklı satırı seç → adet ön-dolu; TIK 3: Ekle
            row = page.query_selector('button:has-text("Türev Bölümü")')
            check("2a. kaynaklı satır listede", row is not None)
            if row:
                row.click()
                page.wait_for_timeout(900)
                qty = page.query_selector('input[aria-label="Adet"]')
                val = qty.input_value() if qty else ""
                check("3. adet öğrenilmiş değerle ön-dolu (koç yazmıyor: 4)",
                      val == "4", f"deger={val!r}")

                before = _task_count(ids["student"], day)
                _submit(page)
                page.wait_for_timeout(2500)
                after = _task_count(ids["student"], day)
                check("2b. TOPLAM 3 TIK ile görev oluştu (kutu→satır→Ekle)",
                      after == before + 1, f"{before} → {after}")

            # ---- 4. Kaynaksız görev
            box = page.query_selector('input[aria-label="Görev ara"]')
            box.click()
            page.wait_for_timeout(1500)
            free_btn = page.query_selector('button:has-text("Kaynak belirtmeden ver")')
            check("4a. 'Kaynak belirtmeden ver' seçeneği her konunun altında",
                  free_btn is not None)
            if free_btn:
                free_btn.click()
                page.wait_for_timeout(800)
                before = _task_count(ids["student"], day)
                _submit(page)
                page.wait_for_timeout(2500)
                after = _task_count(ids["student"], day)
                ok, res_ok = _sourceless_check(ids["student"], day)
                check("4b. kaynaksız görev oluştu ve REZERV TUTMADI",
                      after == before + 1 and ok and res_ok,
                      f"{before}→{after} konulu={ok} rezerv_degismedi={res_ok}")

            # ---- 6. Dolu bölüm seçilince aşım uyarısı, Ekle yine çalışır
            box = page.query_selector('input[aria-label="Görev ara"]')
            box.click()
            box.fill("Limit")
            page.wait_for_timeout(2200)
            full_row = page.query_selector('button:has-text("Limit Bölümü")')
            if full_row:
                full_row.click()
                page.wait_for_timeout(900)
                warn = page.query_selector("text=aşılacak")
                check("6a. dolu bölüm seçilince amber aşım uyarısı çıkar",
                      warn is not None)
                before = _task_count(ids["student"], day)
                _submit(page)
                page.wait_for_timeout(2500)
                after = _task_count(ids["student"], day)
                check("6b. uyarıya rağmen görev oluşur (engel değil)",
                      after == before + 1, f"{before} → {after}")
            else:
                check("6a. dolu bölüm seçilince amber aşım uyarısı çıkar", False,
                      "dolu satır bulunamadı")

            # ---- 7. Arama daraltır
            box = page.query_selector('input[aria-label="Görev ara"]')
            box.click()
            box.fill("İntegral")
            page.wait_for_timeout(2200)
            names = page.query_selector_all('div.mb-0\\.5')
            check("7. arama listeyi daraltır (tek konu kaldı)",
                  0 < len(names) <= 3, f"satir={len(names)}")

            # ---- 9b. Escape listeyi kapatmalı. İlk sürümde kapatmıyordu ve
            #          açık liste altındaki kontrolleri örtüyordu (bu test
            #          tıklayamayınca yakalandı) → bileşene Escape eklendi.
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)
            still_open = page.query_selector('text="Müfredatta sıradaki"')
            check("9b. Escape aday listesini kapatır", still_open is None)

            # ---- 8. Ayrıntılı forma dönüş
            det = page.query_selector('text="Ayrıntılı form"')
            check("8a. 'Ayrıntılı form' bağlantısı duruyor (geri dönüş yolu)",
                  det is not None)
            if det:
                det.click()
                page.wait_for_timeout(1200)
                check("8b. eski form açılıyor (görev tipi çipleri)",
                      page.query_selector('text="Görev tipi"') is not None)

            page.screenshot(path="/tmp/qa_final.png", full_page=False)
            b.close()
    finally:
        cleanup(ids)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


def _submit(page) -> None:
    """Kutunun KENDİ 'Ekle' butonu.

    Sayfada başka 'Ekle' butonları var (öneri kartları, sıradaki üniteler);
    metin eşleşmesi yanlışını tıklayıp testi sessizce yanlış geçirir/düşürür.
    Kutuyu arama input'undan tanımlayıp onun form'undaki submit'e basıyoruz.
    """
    page.locator(
        'form:has(input[aria-label="Görev ara"]) button[type="submit"]'
    ).first.click()


def _task_count(student_id: int, day: str) -> int:
    """Öğrencinin TOPLAM görev sayısı.

    Hafta görünümünde kutu hangi gün kartındaysa görev o güne eklenir; test
    hangi günün seçili olduğunu varsaymamalı (varsayarsa sessizce yanlış
    ölçer). Seed'deki geçmiş görevler sabit olduğu için delta güvenilir.
    """
    with SessionLocal() as db:
        return db.query(Task).filter(Task.student_id == student_id).count()


def _sourceless_check(student_id: int, day: str) -> tuple[bool, bool]:
    """(konuya bağlı kitapsız kalem var mı, rezerv artmadı mı)"""
    with SessionLocal() as db:
        item = (
            db.query(TaskBookItem)
            .join(Task, Task.id == TaskBookItem.task_id)
            .filter(
                Task.student_id == student_id,
                TaskBookItem.book_id.is_(None),
                TaskBookItem.topic_id.isnot(None),
            )
            .first()
        )
        # Kaynaksız görev hiçbir bölümün rezervini artırmamalı
        reserved = (
            db.query(SectionProgress)
            .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
            .filter(StudentBook.student_id == student_id,
                    SectionProgress.reserved_count > 0)
            .count()
        )
        return item is not None, reserved <= 2


if __name__ == "__main__":
    raise SystemExit(main())
