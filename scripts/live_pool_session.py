"""Havuz SEANS EKRANI — GERÇEK TARAYICI (Adım 2b, 2026-10-12).

Dev :3000 + :8081 açık olmalı; sistem python (playwright): python scripts/live_pool_session.py

Akış: havuz öğrencisi (dönem 5 gün önce açık, 3 kalem, 1 kap kaydı, 2 deneme, önceki seans)
→ /pool/session: tek cümle özet · kalem satırları (öğrenci/seansta/kalan) · "seansta" girişi
2 → kalan düşer · etkinlik "yapıldı" · kaçınılan kart · deneme şeridi 3 satır · önceki seans
notu → Seansı bitir: devir seç → yeni dönem /pool'da · devir rozeti · koyu tema kontrast.
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
    Book, BookSection, BookType, ClassGroup, CoachingSession, PoolItem, SectionProgress, StudentBook,
    StudyPeriod, Subject, SuspiciousIp, Task, TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.coaching_session import CoachingSessionStatus  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_result import EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.services import pool_mode, task_service  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lps_{secrets.token_hex(3)}"
PWD = "SeansCanli!2345"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today = date.today()
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
                     full_name="Seans Canlı Rehber", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Seans Canlı Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12, track=Track.SAYISAL, program_mode="havuz")
        db.add(st)
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=tyt.id, name="Köklü Sayılar", order=2, teacher_id=coach.id)
        db.add_all([t1, t2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        s1 = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=10, order=1, topic_id=t1.id)
        db.add(s1)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=0))
        e_old = ExamResult(student_id=st.id, created_by_id=coach.id, title="TYT Deneme 1",
                           exam_date=today - timedelta(days=20), section=ExamSection.TYT,
                           total_correct=50, total_wrong=10, total_blank=60, net=40.0)
        e_new = ExamResult(student_id=st.id, created_by_id=coach.id, title="TYT Deneme 2",
                           exam_date=today - timedelta(days=2), section=ExamSection.TYT,
                           total_correct=55, total_wrong=10, total_blank=55, net=45.0)
        db.add_all([e_old, e_new])
        db.flush()
        db.add(ExamResultQuestion(exam_result_id=e_new.id, question_no=1, subject_id=tyt.id, topic_id=t1.id,
                                  result=EQ_RESULT_YANLIS))
        db.add(CoachingSession(coach_id=coach.id, student_id=st.id, session_date=today - timedelta(days=6),
                               status=CoachingSessionStatus.DONE, agenda="Önceki gündem", coach_note="Önceki not"))
        db.flush()
        p = pool_mode.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=5), expected_next_on=today)
        i1 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=4, unit="test", book=b, section=s1)
        i2 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=3, unit="test", topic=t2, teacher_homework=True)
        i3 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=None, unit="etkinlik", label="Üslü videosu")
        # Kalemler dönem açılırken eklenmiş olsun (kaçınma süresi kalemin havuza girdiği günden ölçülür)
        from datetime import datetime as _dt, time as _tm, timezone as _tz
        for _it in (i1, i2, i3):
            _it.created_at = _dt.combine(today - timedelta(days=5), _tm(12), tzinfo=_tz.utc)
        t = pool_mode.put_in_cup(db, item=i1, day=today - timedelta(days=3), count=2)
        task_service.complete_task(db, t)
        pool_mode.sync_item_progress(db, i1)
        db.commit()
        return {"coach": coach.id, "st": st.id, "subjects": [tyt.id], "book": b.id, "exams": [e_old.id, e_new.id],
                "email": f"{PFX}_t@test.invalid", "i1": i1.id, "i2": i2.id, "i3": i3.id, "pid": p.id}


def cleanup():
    with SessionLocal() as db:
        u = [ids["coach"], ids["st"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(u)))
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_(ids["exams"])))
        db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(ids["exams"])))
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
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
    print(f"\n=== Havuz seans ekranı — canlı ({PFX}, öğrenci #{sid}) ===\n")
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

            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_timeout(1500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(500)
            check("1a editörde 'Seans ekranı' düğmesi", page.query_selector('a:has-text("Seans ekranı")') is not None)
            page.click('a:has-text("Seans ekranı")')
            page.wait_for_selector('[data-section="pool:session:headline"]', timeout=15000)
            head = page.query_selector('[data-section="pool:session:headline"]').inner_text()
            check("1b tek cümle özet: yüzde 25 (2/8 birim) + kaçınma", "yüzde 25" in head and "2/8" in head and "kaçınma" in head, head[:120])

            rows = page.query_selector_all('[data-section="pool:session:items"] li')
            check("2a 3 kalem satırı", len(rows) == 3, str(len(rows)))
            txt = page.query_selector('[data-section="pool:session:items"]').inner_text()
            check("2b satırda öğrenci 2 · seansta 0 · kalan 2", "öğrenci 2" in txt and "kalan 2" in txt, txt[:300])
            check("2c öğretmen ödevi eğik/mor (italic sınıfı)", page.query_selector('[data-section="pool:session:items"] .italic') is not None)
            check("2d kaçınılan kartı (4+ gün kaba alınmadı)", page.query_selector('[data-section="pool:session:avoided"]') is not None
                  and "gündür" in page.query_selector('[data-section="pool:session:avoided"]').inner_text())

            # seansta işaretle: ilk satır (kitaplı) 1 → kalan 1
            inp = page.query_selector_all('[data-section="pool:session:items"] input[aria-label="Seansta işaretlenen"]')
            check("3a iki sayısal kalemde 'seansta' girişi", len(inp) == 2, str(len(inp)))
            inp[0].fill("1")
            inp[0].press("Tab")
            page.wait_for_timeout(2000)
            txt = page.query_selector('[data-section="pool:session:items"]').inner_text()
            check("3b kitaplı kalem: seansta 1 · kalan 1", "seansta 1" in txt and "kalan 1" in txt, txt[:300])
            with SessionLocal() as db:
                sp = db.query(SectionProgress).join(StudentBook).filter(StudentBook.student_id == sid).one()
                check("3c kitap sayacı 3 (2 görev + 1 seans), rezerv 0", sp.completed_count == 3 and sp.reserved_count == 0,
                      f"c={sp.completed_count} r={sp.reserved_count}")
            page.click('[data-section="pool:session:items"] button:has-text("yapıldı")')
            page.wait_for_timeout(1500)
            check("3d etkinlik 'yapıldı ✓'", page.query_selector('button:has-text("yapıldı ✓")') is not None)
            head = page.query_selector('[data-section="pool:session:headline"]').inner_text()
            check("3e özet yüzde 50 (4/8)", "yüzde 50" in head and "4/8" in head, head[:120])

            ex = page.query_selector('[data-section="pool:session:exam"]')
            et = ex.inner_text() if ex else ""
            check("4a deneme şeridi: 45 net · +5 · yanlış Üslü · bu dönem çalışılan konuda yanlış Üslü",
                  "45" in et and "+5" in et and "Üslü Sayılar (1)" in et and "kaçırdığı: Üslü" in et, et[:300])
            check("4b önceki seans notu", page.query_selector('[data-section="pool:session:previous"]') is not None
                  and "Önceki not" in page.query_selector('[data-section="pool:session:previous"]').inner_text())

            # seansı bitir
            page.click('button:has-text("Seansı bitir")')
            page.wait_for_selector('[role="dialog"] >> text=Devredilecek kalemler', timeout=10000)
            boxes = page.query_selector_all('[role="dialog"] input[aria-label="Devret"]')
            check("5a devir adayı 2 (kalanı olan iki kalem)", len(boxes) == 2, str(len(boxes)))
            boxes[0].check()
            page.click('[role="dialog"] button:has-text("Bitir ve yeni dönemi aç")')
            page.wait_for_url(f"**/teacher/students/{sid}/pool?mod=duzenle", timeout=15000)
            page.wait_for_selector('[data-section="pool:list"]', timeout=15000)
            page.wait_for_timeout(1000)
            lst = page.query_selector('[data-section="pool:list"]').inner_text()
            check("5b yeni dönem havuzunda 1 devir kalemi (rozet 'Devir ×1')", "1 kalem" in lst and "Devir ×1" in lst, lst[:200])
            check("5c dönem çubuğu bugünden başlıyor", page.query_selector('text=Dönem başlangıcı') is not None)
            with SessionLocal() as db:
                old = db.get(StudyPeriod, ids["pid"])
                ses = db.query(CoachingSession).filter(CoachingSession.student_id == sid).count()
                check("5d eski dönem kapandı + ikinci seans kaydı", old.status == "kapandi" and ses == 2, f"{old.status} ses={ses}")
            hist = page.query_selector('[data-section="pool:history"]')
            check("5e önceki dönem listede yüzde 50", hist is not None and "%50" in hist.inner_text())

            # koyu tema kontrast — seans ekranı (yeni dönemle tekrar aç, kalemli)
            page.goto(f"{WEB}/teacher/students/{sid}/pool/session", wait_until="networkidle")
            page.wait_for_timeout(1500)
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            for sec in ("pool:session:headline", "pool:session:items", "pool:session:exam", "pool:session:previous"):
                if page.query_selector(f'[data-section="{sec}"]') is None:
                    continue
                m = measure(page, f'[data-section="{sec}"]', min_ratio=4.5)
                check(f"6 koyu tema {sec} okunur", m["bad"] == 0, str(m["worst"][:3]))
            os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_session_dark.png"), full_page=True)
            b.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
