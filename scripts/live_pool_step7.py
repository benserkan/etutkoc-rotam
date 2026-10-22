"""Havuz Adım 7 — CANLI tarayıcı testi (Next :3000 + backend :8081): geçmiş dönem penceresi.

Editörde "Önceki dönemler" → "Dönemi aç" → pencere: Havuz kalemleri sekmesi (ders gruplu, rozetler,
kaçınma izi, kaldırılanlar) · Gün gün sekmesi (8 gün, kap boş gün, D/Y/B) · koyu tema kontrast ·
öğrenci Havuzum önceki dönem çipi → aynı pencere (kaçınma izi YOK) · veli çocuk sayfası → pencere
(onay bekleyen kalem YOK).

Çalıştır (sistem python): python scripts/live_pool_step7.py
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
    Book, BookSection, BookType, NotificationLog, ParentStudentLink, PoolItem, SectionProgress, StudentBook,
    StudyPeriod, Subject, Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.parent import ParentRelation  # noqa: E402
from app.models.pool import PERIOD_CLOSED, SOURCE_STUDENT  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"l7_{secrets.token_hex(3)}"
PWD = "Step7Canli!234"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
today = date.today()
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": []}


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
             role=role, is_active=True, created_at=now - timedelta(days=120), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _cup(db, item, day, count, done=None, dyb=None):
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    if done:
        for bi in t.book_items:
            bi.completed_count = done
            if dyb:
                bi.correct_count, bi.wrong_count, bi.blank_count = dyb
        t.status = TaskStatus.COMPLETED if done >= count else TaskStatus.PARTIAL
        t.completed_at = datetime.combine(day, time(20, 0), tzinfo=timezone.utc)
        db.flush()
        pm.sync_item_progress(db, item)
    return t


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        fiz = Subject(name=f"{PFX} TYT Fizik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([tyt, fiz])
        db.flush()
        ids["subjects"] += [tyt.id, fiz.id]
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t3 = Topic(subject_id=fiz.id, name="Optik", order=1, teacher_id=coach.id)
        db.add_all([t1, t3])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=100, order=1, topic_id=t1.id)
        db.add(sec)
        db.flush()
        s = _user(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                  program_mode="havuz", class_group="12-A", last_seen_at=now - timedelta(hours=20))
        sb = StudentBook(student_id=s.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        parent = _user(db, "veli", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s.id, relation=ParentRelation.ANNE, is_primary=True))
        p1 = pm.open_period(db, student=s, coach=coach, opened_on=today - timedelta(days=8))
        i_a = pm.add_item(db, period=p1, student=s, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        i_b = pm.add_item(db, period=p1, student=s, subject=fiz, quantity=6, unit="test", topic=t3)
        i_c = pm.add_item(db, period=p1, student=s, subject=fiz, quantity=None, unit="etkinlik", label="Optik videosu")
        pm.add_item(db, period=p1, student=s, subject=tyt, quantity=3, unit="sayfa", label="Kendi paragrafım",
                    source=SOURCE_STUDENT, created_by=s)
        i_rm = pm.add_item(db, period=p1, student=s, subject=tyt, quantity=5, unit="sayfa", label="Yanlışlıkla eklenen")
        pm.remove_item(db, i_rm, coach)
        _cup(db, i_a, today - timedelta(days=7), 4, done=4, dyb=(3, 1, 0))
        t_partial = _cup(db, i_a, today - timedelta(days=6), 3, done=2)
        t_partial.status = TaskStatus.PARTIAL
        db.flush()
        pm.close_day(db, student=s, day=today - timedelta(days=6))
        _cup(db, i_a, today - timedelta(days=5), 2)
        pm.close_day(db, student=s, day=today - timedelta(days=5))
        _cup(db, i_c, today - timedelta(days=4), 1, done=1)
        pm.session_mark(db, item=i_b, actor=coach, count=2)
        pm.close_period(db, p1, closed_on=today - timedelta(days=1), status=PERIOD_CLOSED)
        p2 = pm.open_period(db, student=s, coach=coach, opened_on=today - timedelta(days=1), carry=[(i_a.id, None)])
        db.execute(sa_delete(NotificationLog).where(NotificationLog.student_id == s.id))
        db.commit()
        return {"coach": coach.id, "email": f"{PFX}_coach@test.invalid", "sid": s.id, "semail": f"{PFX}_ogr@test.invalid",
                "pemail": f"{PFX}_veli@test.invalid", "p1": p1.id, "p2": p2.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
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
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        from app.models.audit_log import AuditLog
        db.execute(sa_delete(AuditLog).where(AuditLog.target_id.in_(u), AuditLog.details_json.like("%pool_period_delete%")))
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


def _no_overflow(page, selector: str) -> bool:
    return page.evaluate("(sel) => { const e = document.querySelector(sel); return !!e && e.scrollWidth <= e.clientWidth + 1; }", selector)


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = seed()
    sid = d["sid"]
    print(f"\n=== Havuz Adım 7 — canlı ({PFX}, öğrenci #{sid}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    DLG = '[data-section="pool:period-dialog"]'
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.on("dialog", lambda dd: dd.accept())
            _login(page, d["email"])

            # 1) rehber editörü → Önceki dönemler → Dönemi aç
            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:history"]', timeout=20000)
            _dismiss(page)
            page.click(f'[data-testid="pool-period-open-{d["p1"]}"]')
            page.wait_for_selector(f'{DLG} [data-section="pool:period-dialog:items"]', timeout=10000)
            head = page.query_selector(DLG).inner_text()
            check("1a pencere açıldı: başlık dönem aralığı + yüzde + kalem sayısı + 'devredildi 1'",
                  "Dönem" in head and "%" in head and "kalem bitti" in head and "devredildi 1" in head, head[:200])
            chips = page.query_selector('[data-section="pool:period-dialog:subjects"]').inner_text()
            check("1b ders kırılımı çipleri başlıkta (Matematik + Fizik)", "Matematik" in chips and "Fizik" in chips, chips)
            items = page.query_selector_all(f'{DLG} [data-section="pool:period-dialog:items"] li[data-item]')
            check("1c Havuz kalemleri: 4 canlı + 1 kaldırılan = 5 satır", len(items) == 5, str(len(items)))
            body = page.query_selector('[data-section="pool:period-dialog:items"]').inner_text()
            check("1d i_a satırı: '10 test verildi · öğrenci 6 · kalan 4' + 'kaba 3 kez girdi, 1 kez geri döndü' + 'sonraki döneme devredildi'",
                  "10 test verildi · öğrenci 6" in body and "kalan 4" in body and "kaba 3 kez girdi, 1 kez geri döndü" in body
                  and "sonraki döneme devredildi" in body, body[:400])
            check("1e i_b: 'seansta 2' + 'hiç kaba alınmadı' · öğrenci kalemi 'onay bekliyor'",
                  "seansta 2" in body and "hiç kaba alınmadı" in body and "onay bekliyor" in body, body[:400])
            rm = page.query_selector('[data-section="pool:period-dialog:removed"]')
            check("1f Kaldırılanlar (1) grubu ayrı + 'Yanlışlıkla eklenen'",
                  rm is not None and "anlar (1)" in rm.inner_text().lower() and "Yanlışlıkla eklenen" in rm.inner_text(),  # CSS uppercase → innerText büyük harf
                  rm.inner_text()[:120] if rm else "-")
            check("1g pencere yatay taşmıyor (kırpma yok)", _no_overflow(page, DLG))

            # 2) Gün gün sekmesi
            page.click('[data-testid="pool-period-tab-days"]')
            page.wait_for_selector('[data-section="pool:period-dialog:days"]', timeout=5000)
            days = page.query_selector_all('[data-section="pool:period-dialog:days"] li[data-day]')
            check("2a Gün gün: 8 gün satırı (açılış → kapanış)", len(days) == 8, str(len(days)))
            dtext = page.query_selector('[data-section="pool:period-dialog:days"]').inner_text()
            check("2b gün-7: '4 test çözdü · 3D 1Y 0B' · gün-6 '2 test çözdü' · etkinlik 'yapıldı'",
                  "4 test çözdü · 3D 1Y 0B" in dtext and "2 test çözdü" in dtext and "yapıldı" in dtext, dtext[:400])
            empty_days = [x for x in days if "kap boş" in x.inner_text()]
            check("2c kap boş günler açıkça yazılı (silinen kap görevinin günü dahil)", len(empty_days) >= 4, str(len(empty_days)))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_period_days.png"))

            # 3) koyu tema kontrast (her iki sekme)
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            m = measure(page, DLG, min_ratio=4.5)
            check("3a koyu tema: Gün gün sekmesi okunur (4,5)", m["bad"] == 0, str(m["worst"][:3]))
            page.click('[data-testid="pool-period-tab-items"]')
            page.wait_for_timeout(300)
            m = measure(page, DLG, min_ratio=4.5)
            check("3b koyu tema: Havuz kalemleri sekmesi okunur (4,5)", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_period_items_dark.png"))
            page.evaluate("document.documentElement.classList.remove('dark')")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            check("3c Esc ile kapanır", page.query_selector(DLG) is None)

            # 3b) yeni geçmiş kartı + menüden silme (açık dönem p2 listede değil; p1 silinir)
            card = page.query_selector(f'[data-section="pool:history"] li[data-period="{d["p1"]}"]')
            ctext = card.inner_text() if card else ""
            check("3d kart: tarih aralığı + gün sayısı + Kapandı + %yüzde + ders çipleri + 'devredildi 1'",
                  card is not None and "gün" in ctext and "Kapandı" in ctext and "%" in ctext and "devredildi 1" in ctext
                  and page.query_selector(f'li[data-period="{d["p1"]}"] [data-section="pool:history:subjects"]') is not None,
                  ctext[:200])
            check("3e geçmiş bölümü yatay taşmıyor", _no_overflow(page, '[data-section="pool:history"]'))
            page.evaluate("document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            m = measure(page, '[data-section="pool:history"]', min_ratio=4.5)
            check("3f koyu tema: geçmiş kartları okunur (4,5)", m["bad"] == 0, str(m["worst"][:3]))
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_history_cards_dark.png"), full_page=True)
            page.evaluate("document.documentElement.classList.remove('dark')")
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_history_cards.png"), full_page=True)

            # 4) öğrenci Havuzum → önceki dönem çipi → pencere (kaçınma izi YOK)
            page.context.clear_cookies()
            _login(page, d["semail"])
            page.goto(f"{WEB}/student/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="student:pool:previous"]', timeout=20000)
            _dismiss(page)
            page.click(f'[data-testid="student-pool-period-{d["p1"]}"]')
            page.wait_for_selector(f'{DLG} [data-section="pool:period-dialog:items"]', timeout=10000)
            sbody = page.query_selector('[data-section="pool:period-dialog:items"]').inner_text()
            sitems = page.query_selector_all(f'{DLG} li[data-item]')
            check("4a öğrenci penceresi: 4 kalem (kaldırılan yok) · kendi kalemi 'onay bekliyor' · kaçınma izi YOK",
                  len(sitems) == 4 and "onay bekliyor" in sbody and "kaba" not in sbody and "Kaldırılanlar" not in sbody,
                  f"{len(sitems)} {sbody[:200]}")
            page.click('[data-testid="pool-period-tab-days"]')
            page.wait_for_selector('[data-section="pool:period-dialog:days"]', timeout=5000)
            check("4b öğrenci Gün gün: 8 gün + D/Y/B", len(page.query_selector_all(f'{DLG} li[data-day]')) == 8
                  and "3D 1Y 0B" in page.query_selector('[data-section="pool:period-dialog:days"]').inner_text())
            page.keyboard.press("Escape")

            # 5) veli çocuk sayfası → pencere (onay bekleyen YOK)
            page.context.clear_cookies()
            _login(page, d["pemail"])
            page.goto(f"{WEB}/parent/students/{sid}", wait_until="networkidle")
            page.wait_for_selector('[data-section="parent:pool:previous"]', timeout=20000)
            _dismiss(page)
            if page.query_selector('[role="dialog"]'):
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
            page.click(f'[data-testid="parent-pool-period-{d["p1"]}"]')
            page.wait_for_selector(f'{DLG} [data-section="pool:period-dialog:items"]', timeout=10000)
            pbody = page.query_selector('[data-section="pool:period-dialog:items"]').inner_text()
            pitems = page.query_selector_all(f'{DLG} li[data-item]')
            check("5a veli penceresi: 3 kalem (onay bekleyen + kaldırılan YOK) · kaçınma izi YOK",
                  len(pitems) == 3 and "onay bekliyor" not in pbody and "kaba" not in pbody, f"{len(pitems)} {pbody[:200]}")
            page.click('[data-testid="pool-period-tab-days"]')
            page.wait_for_selector('[data-section="pool:period-dialog:days"]', timeout=5000)
            check("5b veli Gün gün: 8 gün", len(page.query_selector_all(f'{DLG} li[data-day]')) == 8)
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_period_parent.png"))

            # 6) rehber: menüden dönemi sil (etki penceresi → onay → kart kalkar)
            page.keyboard.press("Escape")
            page.context.clear_cookies()
            _login(page, d["email"])
            page.goto(f"{WEB}/teacher/students/{sid}/pool", wait_until="networkidle")
            page.wait_for_selector('[data-section="pool:history"]', timeout=20000)
            _dismiss(page)
            page.click(f'[data-testid="pool-period-menu-{d["p1"]}"]')
            page.wait_for_selector(f'[data-testid="pool-period-delete-{d["p1"]}"]', timeout=5000)
            page.click(f'[data-testid="pool-period-delete-{d["p1"]}"]')
            page.wait_for_selector('[data-section="pool:period-delete:impact"]', timeout=10000)
            imp = page.query_selector('[data-section="pool:period-delete"]').inner_text()
            check("3g silme penceresi etkiyi gösterir (4 kalem silinir · 3 görev korunur · devir bağı kopar)",
                  "4 havuz kalemi silinir" in imp and "3 görev korunur" in imp and "devir bağı kopar" in imp, imp[:300])
            page.wait_for_timeout(500)  # açılış animasyonu bitsin (belgeleme görüntüsü)
            page.screenshot(path=os.path.join(ROOT, ".shots/pool_period_delete.png"))
            page.click('[data-testid="pool-period-delete-confirm"]')
            page.wait_for_timeout(2500)
            gone = page.query_selector(f'[data-section="pool:history"] li[data-period="{d["p1"]}"]') is None
            check("3h onaydan sonra kart listeden kalktı (yenilemesiz)", gone and page.query_selector('[data-section="pool:period-delete"]') is None)
            b.close()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
