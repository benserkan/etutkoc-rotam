"""Havuz erken uyarı (Adım 4, K40–K51) — CANLI tarayıcı testi (Next :3000 + backend :8081).

Seans ekranında 1 ana kart (K48) + "Ek sinyaller" katlanır listesi + "Neden?" kanıtı ·
editörde kompakt şerit · koç panosu uyarı akışında havuz satırı seans ekranına bağlı ·
öğrenci web'de yargısız ipucu kutusu (K41/K46) · koyu tema kontrast.

Çalıştır (sistem python, venv'de playwright yok):
    python scripts/live_pool_flags.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, ClassGroup, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject,
    Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_progress import SessionAgendaItem  # noqa: E402
from app.models.exam_result import EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion  # noqa: E402
from app.models.pool import PERIOD_CLOSED  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lpf_{secrets.token_hex(3)}"
PWD = "FlagsCanli!2345"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today = date.today()
now = datetime.now(timezone.utc)
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


def _cup_done(db, item, day, count, correct, wrong):
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    for bi in t.book_items:
        bi.completed_count, bi.correct_count, bi.wrong_count = count, correct, wrong
    t.status = TaskStatus.COMPLETED
    t.completed_at = datetime.combine(day, time(20, 0), tzinfo=timezone.utc)
    db.flush()
    pm.sync_item_progress(db, item)


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Bayrak Canlı Rehber", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Bayrak Canlı Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12, track=Track.SAYISAL, program_mode="havuz",
                  created_at=now - timedelta(days=60), last_seen_at=now - timedelta(hours=20))
        db.add(st)
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        fiz = Subject(name=f"{PFX} TYT Fizik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([tyt, fiz])
        db.flush()
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t3 = Topic(subject_id=fiz.id, name="Optik", order=1, teacher_id=coach.id)
        db.add_all([t1, t3])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        s1 = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=200, order=1, topic_id=t1.id)
        db.add(s1)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=0))
        # 3 kapanmış dönem: günde 2 birim alışkanlık
        for k in (3, 2, 1):
            opened = today - timedelta(days=3 + 7 * k)
            closed = opened + timedelta(days=7)
            p = pm.open_period(db, student=st, coach=coach, opened_on=opened, expected_next_on=closed)
            it = pm.add_item(db, period=p, student=st, subject=tyt, quantity=14, unit="test", book=b, section=s1)
            _cup_done(db, it, closed - timedelta(days=1), 14, 110, 30)
            pm.close_period(db, p, closed_on=closed, status=PERIOD_CLOSED)
        p = pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=3),
                           expected_next_on=today + timedelta(days=4))
        i1 = pm.add_item(db, period=p, student=st, subject=tyt, quantity=30, unit="test", book=b, section=s1)
        i2 = pm.add_item(db, period=p, student=st, subject=fiz, quantity=10, unit="test", topic=t3)
        _cup_done(db, i1, today - timedelta(days=2), 4, 10, 30)
        _cup_done(db, i1, today - timedelta(days=1), 4, 10, 30)
        i2.cup_attempts = 3
        e = ExamResult(student_id=st.id, created_by_id=coach.id, title="TYT Deneme 2",
                       exam_date=today - timedelta(days=1), section=ExamSection.TYT,
                       total_correct=50, total_wrong=10, total_blank=60, net=40.0)
        db.add(e)
        db.flush()
        for n in (1, 2):
            db.add(ExamResultQuestion(exam_result_id=e.id, question_no=n, subject_id=tyt.id, topic_id=t1.id,
                                      result=EQ_RESULT_YANLIS))
        db.commit()
        return {"coach": coach.id, "st": st.id, "subjects": [tyt.id, fiz.id], "book": b.id, "exams": [e.id],
                "email": f"{PFX}_t@test.invalid", "semail": f"{PFX}_s@test.invalid", "tyt": tyt.id}


def cleanup():
    with SessionLocal() as db:
        u = [ids["coach"], ids["st"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(SessionAgendaItem).where(SessionAgendaItem.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
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


def _login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)


def _dismiss(page):
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(500)


def _no_ellipsis(page, sel) -> bool:
    return page.evaluate("""(sel) => {
      const root = document.querySelector(sel); if (!root) return true;
      for (const el of root.querySelectorAll('*')) {
        const cs = getComputedStyle(el);
        if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) return false;
      }
      return true; }""", sel)


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids.update(seed())
    sid = ids["st"]
    print(f"\n=== Havuz erken uyarı — canlı ({PFX}, öğrenci #{sid}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.on("dialog", lambda d: d.accept())
            _login(page, ids["email"])

            # 1) seans ekranı
            page.goto(f"{WEB}/teacher/students/{sid}/pool/session", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:flags"]', timeout=20000)
            _dismiss(page)
            card = page.query_selector('[data-section="pool:flags"]')
            check("1a seans ekranında sinyal kartı · seviye sarı", card.get_attribute("data-level") == "amber",
                  str(card.get_attribute("data-level")))
            prim = page.query_selector_all('[data-section="pool:flags"] [data-flag]')
            check("1b K48: katlanmadan önce TEK ana kart görünür (Tempo geride)",
                  len(prim) == 1 and prim[0].get_attribute("data-flag") == "pool_behind",
                  str([x.get_attribute("data-flag") for x in prim]))
            txt = prim[0].inner_text()
            check("1c ana kartta başlık + Dikkat/Tempo rozetleri + gereken/alışkanlık cümlesi",
                  "Tempo geride" in txt and "Dikkat" in txt and "Tempo" in txt and "birim gerekiyor" in txt, txt[:200])
            check("1d K48 kanıt ('Neden?') ana kartta açık gelir: Kural satırı var",
                  page.query_selector('[data-flag="pool_behind"] [data-section="pool:flag:evidence"]') is not None
                  and "Kural" in page.query_selector('[data-flag="pool_behind"] [data-section="pool:flag:evidence"]').inner_text())
            tog = page.query_selector('[data-testid="pool-flags-toggle"]')
            check("1e 'Ek sinyaller (N)' düğmesi — N≥3 (doğruluk · deneme çaprazı · kaçınma)",
                  tog is not None and any(f"Ek sinyaller ({n})" in tog.inner_text() for n in (3, 4, 5)), tog.inner_text() if tog else "-")
            tog.click()
            page.wait_for_selector('[data-section="pool:flags:extra"]', timeout=5000)
            extra = [x.get_attribute("data-flag") for x in page.query_selector_all('[data-section="pool:flags:extra"] [data-flag]')]
            check("1f ek sinyaller: pool_accuracy · pool_exam_cross · pool_avoided",
                  any(c.startswith("pool_accuracy_") for c in extra) and "pool_exam_cross" in extra and "pool_avoided" in extra, str(extra))
            page.click('[data-flag="pool_exam_cross"] button:has-text("Neden?")')
            page.wait_for_timeout(300)
            ev = page.query_selector('[data-flag="pool_exam_cross"] [data-section="pool:flag:evidence"]')
            check("1g deneme çaprazı kanıtı: Üslü Sayılar · 2 yanlış", ev is not None and "Üslü Sayılar" in ev.inner_text() and "2 yanlış" in ev.inner_text(),
                  ev.inner_text()[:120] if ev else "-")
            check("1h metin kırpılmıyor (ellipsis yok)", _no_ellipsis(page, '[data-section="pool:flags"]'))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_flags_session.png"), full_page=True)

            # 2) editör: kompakt şerit
            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:flags"]', timeout=20000)
            _dismiss(page)
            check("2a havuz editöründe aynı sinyal şeridi (kompakt, ana kart)",
                  page.query_selector('[data-section="pool:flags"] [data-flag="pool_behind"]') is not None)
            check("2b editörde kanıt katlı (kompakt) — 'Neden?' düğmesi var, dl yok",
                  page.query_selector('[data-flag="pool_behind"] button:has-text("Neden?")') is not None
                  and page.query_selector('[data-flag="pool_behind"] [data-section="pool:flag:evidence"]') is None)

            # 3) koç panosu uyarı akışı
            page.goto(f"{WEB}/teacher/dashboard", wait_until="networkidle")
            page.wait_for_timeout(2500)
            _dismiss(page)
            body = page.inner_text("body")
            check("3a pano uyarı akışında havuz öğrencisinin ANA kartı (Tempo geride)", "Tempo geride" in body)
            link = page.query_selector(f'a[href="/teacher/students/{sid}/pool/session"]')
            check("3b akış satırı seans ekranına bağlı", link is not None)

            # 4) koyu tema kontrast — seans ekranı sinyal kartı (açık + katlı)
            page.goto(f"{WEB}/teacher/students/{sid}/pool/session", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:flags"]', timeout=20000)
            page.evaluate("document.documentElement.classList.add('dark')")
            page.click('[data-testid="pool-flags-toggle"]')
            page.wait_for_timeout(400)
            m = measure(page, '[data-section="pool:flags"]', min_ratio=4.5)
            check("4 koyu tema: sinyal kartları okunur (ana + ek + kanıt)", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_flags_session_dark.png"), full_page=True)

            # 5) öğrenci web: ipuçları
            page.context.clear_cookies()
            _login(page, ids["semail"])
            page.goto(f"{WEB}/student/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="student:pool"]', timeout=20000)
            _dismiss(page)
            hints = page.query_selector_all('[data-section="student:pool:hints"] li')
            ht = " | ".join(h.inner_text() for h in hints)
            check("5a öğrenci Havuzum: 2 ipucu (tempo + doğruluk)", len(hints) == 2, str(len(hints)))
            check("5b dil yönlendirici: 'bugün bir fazla yapmak' · 'çözümlerine bak'; kırmızı/Acil yok",
                  "bir fazla" in ht and "çözümlerine bak" in ht and "Acil" not in ht and "Dikkat" not in ht, ht[:200])
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            m = measure(page, '[data-section="student:pool:hints"]', min_ratio=4.5)
            check("5c koyu tema: ipucu kutusu okunur", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/student_pool_hints_dark.png"), full_page=True)
            b.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
