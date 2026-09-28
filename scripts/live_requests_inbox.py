"""Talepler gelen kutusu (yeni tasarım) — canlı tarayıcı testi (2026-09-29).

Kendi verisini kurar/temizler: koç + öğrenci + 1 değişiklik talebi + 1 soru.
Dev sunucular (:3000 + :8081) açık olmalı. Ekran görüntüleri .shots/requests_inbox_*.png
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
from app.models import Task, TaskStatus, TaskType, User, UserRole
from app.models.task_request import RequestStatus, RequestType, TaskRequest
from app.services.security import hash_password

BASE = "http://localhost:3000"
PFX = f"lri_{secrets.token_hex(3)}"
PWD = "LiveReqInbox!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
QMSG = "Hocam yarın yapabileceğim başka bir şey yok, yarının videolarını da bugün izlemek istiyorum."
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
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Talep Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_unlimited", subscription_status="active")
        db.add(coach)
        db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                   full_name="Gamze Elif Seda Tarı Uzunsoyadlıoğlu", role=UserRole.STUDENT,
                   teacher_id=coach.id, grade_level=11, is_active=True,
                   created_at=now - timedelta(days=30), last_login_at=now)
        db.add(stu)
        db.flush()
        t = Task(student_id=stu.id, date=date.today() + timedelta(days=1), type=TaskType.OTHER,
                 title="Matematik · Türev video dersleri", status=TaskStatus.PENDING, is_draft=False)
        db.add(t)
        db.flush()
        ch = TaskRequest(student_id=stu.id, teacher_id=coach.id, task_id=t.id, type=RequestType.CHANGE,
                         status=RequestStatus.PENDING, proposed_count=2,
                         message="Bu gün okulda sınavım var, 2 test yapabilirim.")
        q = TaskRequest(student_id=stu.id, teacher_id=coach.id, task_id=t.id, type=RequestType.QUESTION,
                        status=RequestStatus.PENDING, message=QMSG)
        db.add_all([ch, q])
        db.commit()
        return {"coach": coach.id, "email": coach.email, "ids": [stu.id], "change": ch.id, "question": q.id}


def cleanup(d):
    with SessionLocal() as db:
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id.in_(d["ids"])))
        db.execute(sa_delete(Task).where(Task.student_id.in_(d["ids"])))
        db.execute(sa_delete(User).where(User.id.in_(d["ids"] + [d["coach"]])))
        db.commit()


def status_of(rid: int) -> str:
    with SessionLocal() as db:
        return db.get(TaskRequest, rid).status.value


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1300, "height": 1000})
            pg = ctx.new_page()
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/requests", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(500)

            head = pg.locator("header p").first.inner_text()
            chk("1 başlık: onay bekleyen + yeni mesaj ayrı", "1 talep onayını bekliyor" in head and "1 yeni mesaj" in head, head)
            chk("2 iki bölüm var", pg.get_by_role("heading", name="Onayını bekleyenler").count() == 1
                and pg.get_by_role("heading", name="Soru ve not mesajları").count() == 1)
            ch_card = pg.locator(f'li[data-request-id="{d["change"]}"]')
            q_card = pg.locator(f'li[data-request-id="{d["question"]}"]')
            chk("3 değişiklik kartında öneri yazılı", "Test sayısını 2 yapmak istiyor" in ch_card.inner_text())
            chk("4 soru kartında mesaj TAM (kırpma yok)", QMSG in q_card.inner_text())
            chk("5 soru kartında Onayla yok", q_card.get_by_role("button", name="Onayla").count() == 0)
            chk("6 uzun ad kırpılmadan görünür", "Uzunsoyadlıoğlu" in ch_card.inner_text())
            chk("7 yatay taşma yok", not pg.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            pg.screenshot(path=os.path.join(SHOT_DIR, "requests_inbox_light.png"), full_page=True)

            q_card.get_by_role("button", name="Gördüm").click()
            pg.wait_for_timeout(2500)
            chk("8 Gördüm → soru kapandı (resolved)", status_of(d["question"]) == "resolved", status_of(d["question"]))
            chk("9 soru kartı listeden düştü", pg.locator(f'li[data-request-id="{d["question"]}"]').count() == 0)

            ch_card.get_by_role("button", name="Reddet").click()
            gonder = ch_card.get_by_role("button", name="Reddet").last
            chk("10 gerekçe boşken reddet kapalı", gonder.is_disabled())
            ch_card.locator("textarea").fill("Bu hafta programı değiştirmeyelim.")
            gonder.click()
            pg.wait_for_timeout(2500)
            chk("11 satır içi red çalıştı", status_of(d["change"]) == "rejected", status_of(d["change"]))
            chk("12 boş durum mesajı", pg.get_by_text("Bu filtrede talep yok.").count() == 1)

            pg.goto(f"{BASE}/teacher/requests?status=all", wait_until="networkidle")
            pg.wait_for_timeout(1000)
            txt = pg.locator("main").inner_text()
            chk("13 geçmişte yanıt görünür", "Senin yanıtın:" in txt and "Reddedildi" in txt)

            dctx = b.new_context(viewport={"width": 390, "height": 900}, color_scheme="dark",
                                 storage_state=ctx.storage_state())
            dp = dctx.new_page()
            dp.goto(f"{BASE}/teacher/requests?status=all", wait_until="networkidle")
            dp.wait_for_timeout(1000)
            chk("14 390px yatay taşma yok", not dp.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            dp.screenshot(path=os.path.join(SHOT_DIR, "requests_inbox_dark_mobile.png"), full_page=True)
            b.close()
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
