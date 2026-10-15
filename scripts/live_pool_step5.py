"""Havuz Adım 5 — CANLI tarayıcı testi (Next :3000 + backend :8081).

Rehber: dönem kapandı bandı → veli özeti önizle → cümle düzenle → gönder → rozet "Veliye
gönderildi" → yeniden açınca salt okuma · Görüşmeler sayfasında günlük havuz listesi (bugünkü
seans üstte, Gördüm) · Kurum: Haftalık Havuz panosu (nav + KPI + şube tablosu + geciken) ·
Veli: çocuk detayında havuz kartı (salt okuma) · koyu tema kontrast.

Çalıştır (sistem python): python scripts/live_pool_step5.py
"""
from __future__ import annotations

import json
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
    Book, BookSection, BookType, ClassGroup, CoachingSession, Institution, NotificationLog, ParentNotificationPref,
    ParentStudentLink, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task, TaskBookItem, TaskStatus,
    Topic, Track, User, UserRole, WarningState,
)
from app.models.appointment import APPT_STATUS_SCHEDULED, CoachingAppointment  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_progress import SessionAgendaItem  # noqa: E402
from app.models.parent import ParentRelation  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"l5_{secrets.token_hex(3)}"
PWD = "Step5Canli!234"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today = date.today()
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "inst": [], "subjects": [], "books": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"Canlı {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=60), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


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
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k", contact_email=f"{PFX}@t.invalid", plan="etut_standart", is_active=True)
        db.add(inst)
        db.flush()
        ids["inst"].append(inst.id)
        admin = _user(db, "admin", UserRole.INSTITUTION_ADMIN, institution_id=inst.id)
        coach = _user(db, "coach", UserRole.TEACHER, institution_id=inst.id)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        ids["subjects"].append(tyt.id)
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        db.add(t1)
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=100, order=1, topic_id=t1.id)
        db.add(sec)
        db.flush()

        def mk(tag, cg):
            s = _user(db, tag, UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                      program_mode="havuz", class_group=cg, last_seen_at=now - timedelta(hours=20))
            sb = StudentBook(student_id=s.id, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
            return s
        s_main = mk("main", "12-A")
        p_old = pm.open_period(db, student=s_main, coach=coach, opened_on=today - timedelta(days=10), expected_next_on=today - timedelta(days=3))
        i_a = pm.add_item(db, period=p_old, student=s_main, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        _cup_done(db, i_a, today - timedelta(days=6), 6, 50, 10)
        new_p, _ = pm.finish_session(db, student=s_main, coach=coach, period=p_old, closed_on=today - timedelta(days=3),
                                     expected_next_on=today + timedelta(days=4), carry=[(i_a.id, None)],
                                     record_session=False, agenda=None, coach_note=None, next_change=None, mood=None)
        i_new = pm.add_item(db, period=new_p, student=s_main, subject=tyt, quantity=8, unit="test", book=b, section=sec)
        _cup_done(db, i_new, today, 2, 15, 5)
        s_late = mk("late", "12-B")
        p_l = pm.open_period(db, student=s_late, coach=coach, opened_on=today - timedelta(days=9), expected_next_on=today - timedelta(days=4))
        i_l = pm.add_item(db, period=p_l, student=s_late, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        _cup_done(db, i_l, today - timedelta(days=1), 5, 40, 10)
        s_today = mk("today", "12-A")
        pm.open_period(db, student=s_today, coach=coach, opened_on=today - timedelta(days=2))
        db.add(CoachingAppointment(coach_id=coach.id, student_id=s_today.id, date=today, start_time="16:00", duration_min=40, status=APPT_STATUS_SCHEDULED))
        parent = _user(db, "veli", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s_main.id, relation=ParentRelation.ANNE, is_primary=True))
        db.add(ParentNotificationPref(parent_id=parent.id, unsubscribe_token=f"ut{PFX}"))
        # id yeniden kullanımı: yarıda kesilen koşuların yetim bildirim kayıtları yeni öğrenciye yapışmasın
        db.execute(sa_delete(NotificationLog).where(NotificationLog.student_id.in_([s_main.id, s_late.id, s_today.id])))
        db.commit()
        return {"coach": coach.id, "admin": admin.id, "main": s_main.id, "late": s_late.id, "today": s_today.id,
                "parent": parent.id, "p_old": p_old.id, "p_new": new_p.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(CoachingAppointment).where(CoachingAppointment.student_id.in_(u)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(u)))
        db.execute(sa_delete(SessionAgendaItem).where(SessionAgendaItem.student_id.in_(u)))
        db.execute(sa_delete(NotificationLog).where(NotificationLog.parent_id.in_(u)))
        db.execute(sa_delete(ParentNotificationPref).where(ParentNotificationPref.parent_id.in_(u)))
        db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(ClassGroup).where(ClassGroup.scope_key.in_([f"inst:{i}" for i in ids["inst"]])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.execute(sa_delete(Institution).where(Institution.id.in_(ids["inst"])))
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


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = seed()
    ids.update(d)
    sid = d["main"]
    print(f"\n=== Havuz Adım 5 — canlı ({PFX}, öğrenci #{sid}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.on("dialog", lambda dd: dd.accept())
            _login(page, f"{PFX}_coach@test.invalid")

            # 1) editör: dönem kapandı bandı → özet
            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:history"]', timeout=20000)
            _dismiss(page)
            band = page.query_selector('[data-section="pool:history:pending-summary"]')
            check("1a 'Dönem kapandı — veli özeti hazır; otomatik gitmez' bandı", band is not None and "otomatik gitmez" in band.inner_text(), band.inner_text()[:120] if band else "-")
            page.click('[data-testid="pool-parent-summary-open"]')
            page.wait_for_selector('[data-section="pool:parent-summary:lines"] textarea', timeout=15000)
            kpi = page.query_selector('[data-section="pool:parent-summary:kpi"]').inner_text()
            check("1b önizleme: yüzde 60 · 6/10 birim (ölçüm, düzenlenemez)", "%60" in kpi and "6/10" in kpi, kpi)
            tas = page.query_selector_all('[data-section="pool:parent-summary:lines"] textarea')
            check("1c cümleler düzenlenebilir (≥2 cümle, readonly değil)", len(tas) >= 2 and tas[0].get_attribute("readonly") is None, str(len(tas)))
            tas[0].fill("Canlı test cümlesi: bu dönem yüzde 60 tamamlandı.")
            page.click('[data-section="pool:parent-summary"] button[aria-label="Cümleyi sil"] >> nth=1')
            page.wait_for_timeout(200)
            rec = page.query_selector('[data-section="pool:parent-summary:recipients"]').inner_text()
            check("1d alıcılar: 1 veli (gönderilir)", "Canlı veli" in rec and "almadı" not in rec, rec[:120])
            btn = page.query_selector('[data-testid="pool-parent-summary-send"]')
            check("1e gönder düğmesi '1 veliye gönder'", btn is not None and "1 veliye gönder" in btn.inner_text(), btn.inner_text() if btn else "-")
            btn.click()
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                logs = db.query(NotificationLog).filter(NotificationLog.student_id == sid, NotificationLog.parent_id == d["parent"]).all()
                per = db.get(StudyPeriod, d["p_old"])
                check("1f gönderildi: 1 bildirim kuyrukta, dönem damgalı, koçun cümlesi payload'da, silinen cümle yok",
                      len(logs) == 1 and per.parent_summary_sent_at is not None
                      and "Canlı test cümlesi" in (per.parent_summary_json or "") and len(json.loads(logs[0].payload_json or '{}').get("narrative", [])) == len(tas) - 1,
                      f"logs={[(l.kind.value, l.channel.value, l.status.value, (json.loads(l.payload_json or '{}')).get('__template')) for l in logs]} sent={per.parent_summary_sent_at}")
            page.wait_for_timeout(1000)
            # 2026-10-13 geçmiş kartı: gönderildi bilgisi kart meta satırında, özet ⋯ menüsünde
            card = page.query_selector(f'[data-section="pool:history"] li[data-period="{d["p_old"]}"]')
            ctext = card.inner_text() if card else ""
            check("1g dönem kartında 'veliye gönderildi' + band kayboldu",
                  "veliye gönderildi" in ctext.lower()
                  and page.query_selector('[data-section="pool:history:pending-summary"]') is None, ctext[:160])
            page.click(f'[data-testid="pool-period-menu-{d["p_old"]}"]')
            page.wait_for_selector(f'[data-testid="pool-parent-summary-{d["p_old"]}"]', timeout=5000)
            check("1g2 menüde 'Gönderilen veli özeti'",
                  "Gönderilen veli özeti" in page.query_selector(f'[data-testid="pool-parent-summary-{d["p_old"]}"]').inner_text())
            page.click(f'[data-testid="pool-parent-summary-{d["p_old"]}"]')
            page.wait_for_selector('[data-section="pool:parent-summary:lines"] textarea', timeout=15000)
            ro = page.query_selector_all('[data-section="pool:parent-summary:lines"] textarea')
            check("1h yeniden açınca salt okuma: gönderilen cümle, readonly, Gönder yok",
                  ro and ro[0].get_attribute("readonly") is not None and "Canlı test cümlesi" in ro[0].input_value()
                  and page.query_selector('[data-testid="pool-parent-summary-send"]') is None)
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)

            # 2) görüşmeler sayfası: günlük liste
            page.goto(f"{WEB}/teacher/appointments", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:daily"]', timeout=20000)
            _dismiss(page)
            rows = page.query_selector_all('[data-section="pool:daily"] li[data-student]')
            check("2a günlük liste: 3 havuz öğrencisi, bugün 16:00 seansı ÜSTTE",
                  len(rows) == 3 and rows[0].get_attribute("data-session-today") == "1" and "16:00" in rows[0].inner_text(), str(len(rows)))
            late_row = next((r for r in rows if r.get_attribute("data-student") == str(d["late"])), None)
            check("2b geciken seans öğrencisinde ana sinyal + Gördüm düğmesi", late_row is not None and "Seans" in late_row.inner_text() and late_row.query_selector('button:has-text("Gördüm")') is not None,
                  late_row.inner_text()[:120] if late_row else "-")
            late_row.query_selector('button:has-text("Gördüm")').click()
            page.wait_for_timeout(2000)
            late_row = next((r for r in page.query_selector_all('[data-section="pool:daily"] li[data-student]') if r.get_attribute("data-student") == str(d["late"])), None)
            check("2c Gördüm → 'Geri al' + ertelenen sayacı", late_row is not None and late_row.query_selector('button:has-text("Geri al")') is not None
                  and "ertelenen 1" in page.query_selector('[data-section="pool:daily"]').inner_text())
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_daily_card.png"), full_page=True)

            # 3) kurum
            page.context.clear_cookies()
            _login(page, f"{PFX}_admin@test.invalid")
            page.goto(f"{WEB}/institution", wait_until="networkidle")
            page.wait_for_timeout(1500)
            check("3a kurum menüsünde 'Haftalık Havuz'", page.query_selector('a[href="/institution/pool"]') is not None)
            page.goto(f"{WEB}/institution/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="institution:pool:groups"]', timeout=20000)
            kpi = page.query_selector('[data-section="institution:pool:kpi"]').inner_text()
            head = page.query_selector('[data-section="institution:pool"] header').inner_text()
            check("3b KPI: 3 havuz öğrencisi · son dönem %60 · 1 geciken", "3 öğrenci" in head and "%60" in kpi and "Seansı geciken" in kpi, head + kpi[:200])
            for sec in ("students", "coachside", "signals", "trend", "subjects"):
                check(f"3b2 yeni bölüm institution:pool:{sec}", page.query_selector(f'[data-section="institution:pool:{sec}"]') is not None)
            stxt = page.query_selector('[data-section="institution:pool:students"]').inner_text()
            check("3b3 öğrenci tarafı: bugün kabını kuran + tempo", "Bugün kabını kuran" in stxt and "Tempo" in stxt, stxt[:200])
            check("3b4 metin kırpılmıyor (truncate yok)", page.locator('[data-section="institution:pool"] .truncate').count() == 0)
            gtxt = page.query_selector('[data-section="institution:pool:groups"]').inner_text()
            check("3c şube tablosu 12-A / 12-B", "12-A" in gtxt and "12-B" in gtxt, gtxt[:200])
            ltxt = page.query_selector('[data-section="institution:pool:late"]').inner_text()
            check("3d geciken seans satırı: öğrenci + rehber + gecikme", "Canlı late" in ltxt and "gün gecikti" in ltxt and "Canlı coach" in ltxt, ltxt[:200])
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            bad = 0
            worst = []
            for sec in ("institution:pool:kpi", "institution:pool:groups", "institution:pool:late", "institution:pool:coaches",
                        "institution:pool:students", "institution:pool:coachside", "institution:pool:signals",
                        "institution:pool:trend", "institution:pool:subjects"):
                m = measure(page, f'[data-section="{sec}"]', min_ratio=4.5)
                bad += m["bad"]
                worst += m["worst"][:2]
            check("3e koyu tema: 9 bölüm okunur", bad == 0, str(worst[:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/institution_pool_dark.png"), full_page=True)
            page.evaluate("document.documentElement.classList.remove('dark')")
            page.screenshot(path=os.path.join(ROOT, ".shots/institution_pool_light.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 900})
            page.wait_for_timeout(500)
            check("3f 390px yatay kaymıyor", page.evaluate("document.documentElement.scrollWidth") <= 392)
            page.screenshot(path=os.path.join(ROOT, ".shots/institution_pool_mobile.png"), full_page=True)
            page.set_viewport_size({"width": 1400, "height": 1000})

            # 4) veli
            page.context.clear_cookies()
            _login(page, f"{PFX}_veli@test.invalid")
            page.goto(f"{WEB}/parent/students/{sid}", wait_until="domcontentloaded")
            page.wait_for_selector('[data-section="parent:pool"]', timeout=20000)
            ptxt = page.query_selector('[data-section="parent:pool"]').inner_text()
            cup_li = page.query_selector_all('[data-section="parent:pool:cup"] li')
            check("4a veli kartı: havuz 2/12 birim + bugünün kabında 1 kalem + önceki dönem %60; uyarı/kırmızı yok",
                  "2/12 birim" in ptxt and len(cup_li) == 1 and "%60" in ptxt and "Acil" not in ptxt and "Dikkat" not in ptxt, ptxt[:400].replace(chr(10), " | "))
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            m = measure(page, '[data-section="parent:pool"]', min_ratio=4.5)
            check("4b koyu tema: veli kartı okunur", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/parent_pool_dark.png"), full_page=True)
            b.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
