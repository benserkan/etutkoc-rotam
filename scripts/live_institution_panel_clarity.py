"""Kurum yöneticisi paneli — anlaşılırlık turu canlı testi (2026-09-28).

Menü sadeleşmesi (Davet → Öğretmenler sekmesi, Roster → Tüm Öğrenciler, tek
Talepler) · sütun/kart açıklamaları (hover + dokunma) · koç detayında program
zamanı + gün gün tamamlama · "programı yok" doğruluğu (ileri gün/etkinlik
görevi/pasif) · Aktivite Akışı sayaçları süzgeçten bağımsız · taşma/kırpma.
Kendi verisini kurar/temizler. Dev sunucular (:3000 + :8081) açık olmalı.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (AuditLog, Book, BookType, Institution, Subject, Task, TaskBookItem,
                        TaskStatus, TaskType, User, UserRole)

from app.services.security import hash_password
from scripts.lib_live_contrast import measure

BASE = "http://localhost:3000"
PFX = f"lipc_{secrets.token_hex(3)}"
PWD = "LiveInstPanel!2345"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    now = datetime.now(timezone.utc)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurum", slug=PFX, plan="dershane_pro", is_active=True)
        db.add(inst)
        db.flush()
        adm = User(email=f"{PFX}_adm@test.invalid", password_hash=hash_password(PWD), full_name="Test Yönetici",
                   role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True)
        koc = User(email=f"{PFX}_koc@test.invalid", password_hash=hash_password(PWD), full_name="Koç Deneme",
                   role=UserRole.TEACHER, institution_id=inst.id, is_active=True, last_login_at=now)
        db.add_all([adm, koc])
        db.flush()
        subj = db.query(Subject).first()
        book = Book(teacher_id=koc.id, subject_id=subj.id, name=f"{PFX} SB", type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()

        def stu(name, **kw):
            u = User(email=kw.pop("email", f"{PFX}_{len(name)}_{secrets.token_hex(2)}@test.invalid"),
                     password_hash=hash_password(PWD), full_name=name, role=UserRole.STUDENT,
                     teacher_id=koc.id, institution_id=inst.id, grade_level=10,
                     created_at=now - timedelta(days=30), is_active=kw.pop("is_active", True), **kw)
            db.add(u)
            db.flush()
            return u

        def task(u, d, *, planned=0, done=0, ttype=TaskType.TEST, pub=now):
            t = Task(student_id=u.id, date=d, type=ttype, title="Görev", is_draft=False,
                     published_at=pub, order=0,
                     status=TaskStatus.COMPLETED if (done and done >= planned) else TaskStatus.PENDING)
            db.add(t)
            db.flush()
            if planned:
                db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=None, label="x",
                                    planned_count=planned, completed_count=done))

        full = stu("Tam Programlı Ayşe")
        for i in range(7):
            task(full, today - timedelta(days=i), planned=2, done=2 if i % 2 == 0 else 1)
        future = stu("İleri Günlü Burak")
        fd = min(monday + timedelta(days=6), today + timedelta(days=2))
        if fd <= today:  # Pazar günü: ileri gün kalmıyor → bugün
            fd = today
        task(future, fd, planned=3, done=0, pub=now - timedelta(days=1))
        activity = stu("Etkinlikli Ceren")
        task(activity, today, ttype=TaskType.VIDEO)
        empty = stu("Programsız Deniz")
        stu("Pasif Emre", is_active=False)
        stu("(Silinen Kullanıcı)", email=f"anonymized-{PFX}@kvkk.local", is_active=False)
        db.commit()
        return {"inst": inst.id, "koc": koc.id, "adm_email": adm.email, "empty": empty.full_name,
                "future": future.full_name, "activity": activity.full_name}


def cleanup(d):
    with SessionLocal() as db:
        uids = [u.id for u in db.query(User).filter(
            (User.institution_id == d["inst"]) | (User.email == f"anonymized-{PFX}@kvkk.local")).all()]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(uids)).all()]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(Book).where(Book.name == f"{PFX} SB"))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == d["inst"]))
        db.commit()


PAGES = [
    "/institution", "/institution/teachers", "/institution/roster", "/institution/compliance",
    "/institution/action-center", "/institution/academic", "/institution/self-study",
    "/institution/at-risk", "/institution/cohorts", "/institution/activity-heatmap",
    "/institution/burnout", "/institution/teacher-scorecard", "/institution/goals",
    "/institution/parent-trust", "/institution/usage", "/institution/quota",
    "/institution/subscription", "/institution/activity-stream",
]


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1400, "height": 950})
            pg = ctx.new_page()
            errors: list[str] = []
            pg.on("pageerror", lambda e: errors.append(str(e)[:160]))
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["adm_email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()

            nav = pg.locator("aside").first.inner_text()
            chk("1 menüde 'Davet' ve 'Roster' yok", "Davet\n" not in nav + "\n" and "Roster" not in nav, nav[:300])
            chk("2 menüde 'Tüm Öğrenciler' + tek 'Talepler'", "Tüm Öğrenciler" in nav and nav.count("Talepler") == 1
                and "Taleplerim" not in nav and "Gelen Talepler" not in nav)

            pg.goto(f"{BASE}/institution/invitations", wait_until="networkidle")
            chk("3 eski davet adresi → Öğretmenler/davet sekmesi", "tab=davet" in pg.url
                and pg.get_by_role("heading", name="Davet bağlantıları").count() == 1, pg.url)
            pg.goto(f"{BASE}/institution/support", wait_until="networkidle")
            chk("4 eski Taleplerim adresi → birleşik Talepler/sistem sekmesi", "tab=sistem" in pg.url, pg.url)
            chk("5 Talepler iki sekmeli", pg.get_by_role("link", name="Öğretmenlerden gelen").count() == 1
                and pg.get_by_role("link", name="Sistem yöneticisiyle").count() == 1)

            # Sütun açıklamaları — her sayfada var + hover açılır
            no_hint = []
            for path in PAGES:
                pg.goto(f"{BASE}{path}", wait_until="networkidle")
                pg.wait_for_timeout(500)
                empty_page = path == "/institution/burnout" and pg.locator("table").count() == 0
                if pg.locator("[data-column-hint]").count() == 0 and not empty_page:
                    no_hint.append(path)
            chk("6 tüm veri sayfalarında sütun/kart açıklaması", no_hint == [], str(no_hint))
            chk("7 sayfalarda JS hatası yok", errors == [], str(errors[:3]))

            pg.goto(f"{BASE}/institution/teachers", wait_until="networkidle")
            h = pg.locator("th [data-column-hint]").filter(has_text="Planlanan test").first
            h.hover()
            pg.wait_for_timeout(500)
            chk("8 başlığa gelince açıklama açılır", pg.get_by_role("tooltip").count() >= 1
                and "Son 7 günde" in pg.get_by_role("tooltip").first.inner_text())
            pg.mouse.move(5, 5)
            pg.wait_for_timeout(300)
            h.click()
            pg.wait_for_timeout(400)
            chk("9 dokununca (tık) da açılır", pg.get_by_role("tooltip").count() >= 1)

            # Koç detayı
            pg.goto(f"{BASE}/institution/teachers/{d['koc']}", wait_until="networkidle")
            rows = pg.get_by_test_id("teacher-card-student")
            txt = " | ".join(rows.all_inner_texts())
            chk("10 KVKK silinen hesap listelenmez", "Silinen Kullanıcı" not in txt, txt[:200])
            chk("11 her öğrencide 7 günlük şerit", pg.get_by_test_id("day-strip").first.locator("button").count() == 7)
            chk("12 program sütunu: yayın zamanı / yok", "yayınlandı" in txt and "Henüz program yok" in txt)
            first_row = rows.filter(has_text="Tam Programlı Ayşe").inner_text()
            chk("13 görev % ve görev sayısı", "görev" in first_row and "%" in first_row, first_row)
            pg.get_by_test_id("day-strip").first.locator("button").last.hover()
            pg.wait_for_timeout(500)
            chk("14 gün karesinde açıklama (tarih + görev)", pg.get_by_role("tooltip").count() >= 1
                and "görev" in pg.get_by_role("tooltip").first.inner_text())
            pg.screenshot(path=os.path.join(SHOT_DIR, "inst_teacher_card.png"), full_page=True)

            # Müdahale merkezi — programı yok doğruluğu
            pg.goto(f"{BASE}/institution/action-center", wait_until="networkidle")
            body = pg.locator("main").inner_text()
            chk("15 gerçekten programsız öğrenci listede", d["empty"] in body)
            chk("16 ileri günde programı olan öğrenci 'programı yok' sayılmaz", d["future"] not in body)
            chk("17 yalnız etkinlik görevi olan öğrenci 'programı yok' sayılmaz", d["activity"] not in body)
            chk("18 pasif öğrenci sayılmaz", "Pasif Emre" not in body)
            chk("19 kart metni sade: 'bu hafta programı yok'", "bu hafta programı yok" in body)
            pg.screenshot(path=os.path.join(SHOT_DIR, "inst_action_center.png"), full_page=True)

            # Aktivite akışı — sayaçlar süzgeçten bağımsız
            pg.goto(f"{BASE}/institution/activity-stream", wait_until="networkidle")
            body = pg.locator("main").inner_text()
            chk("20 Yeni hesap kartı kırılım yazar (öğrenci/koç)", "öğrenci" in body and "Yeni hesap" in body.replace("YENİ HESAP", "Yeni hesap"))
            api_all = pg.request.get(f"{BASE}/api/v2/institution/activity-stream?days=90").json()
            api = pg.request.get(f"{BASE}/api/v2/institution/activity-stream?days=90&type=invitation").json()
            chk("21 tür süzgeci seçilince diğer kartlar 0'a düşmez", api["counts"]["signup"] == api_all["counts"]["signup"] > 0,
                f"{api['counts']} vs {api_all['counts']}")

            # Taşma / kırpma / koyu tema
            over = []
            for path in ["/institution", f"/institution/teachers/{d['koc']}", "/institution/action-center",
                         "/institution/compliance", "/institution/teachers"]:
                pg.set_viewport_size({"width": 390, "height": 844})
                pg.goto(f"{BASE}{path}", wait_until="networkidle")
                pg.wait_for_timeout(400)
                if pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"):
                    over.append(path)
            chk("22 390px'te yatay taşma yok (tablolar kendi kutusunda kayar)", over == [], str(over))
            pg.set_viewport_size({"width": 1400, "height": 950})
            pg.goto(f"{BASE}/institution/teachers/{d['koc']}", wait_until="networkidle")
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(400)
            bad = measure(pg, "main", min_ratio=3.0)["bad"]
            chk("23 koç detayı koyu tema kontrastı", bad == 0, str(bad))
            pg.screenshot(path=os.path.join(SHOT_DIR, "inst_teacher_card_dark.png"), full_page=True)
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
