# -*- coding: utf-8 -*-
"""Video Sepeti — öğrenciye göre video durum renkleri (GERÇEK tarayıcı; dev :3000 + :8081).

4 video tohumlanır: verilmedi · programda (yarın) · verildi-izlenmedi (dün,
tamamlanmamış) · izlendi (dün, tamamlanmış). Kontrol: panel varsayılan tüm
videoları gösterir · lejant 4 durum · grup başlığında durum sayıları · her
satır kendi durumunu taşır (data-video-state) + farklı zemin tonu · rozet
tarih içerir · "Yalnız verilmeyen" filtresi yalnız bekleyeni bırakır · başka
öğrencide aynı video durumsuz (öğrenciye özel).
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Task, TaskStatus, TaskType, User, UserRole
from app.models.video_basket import VideoBasketItem
from app.services.security import hash_password

BASE = "http://localhost:3000"
PFX = f"lvst{secrets.token_hex(3)}"
PWD = "VideoDurum1!xyz"
SHOTS = Path(__file__).resolve().parent.parent / ".shots"
passed = 0
failed: list[str] = []


def chk(name, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Durum Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Durum Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, is_graduate=True)
        st2 = User(email=f"{PFX}_s2@test.invalid", password_hash=hash_password(PWD),
                   full_name="Durum İkinci", role=UserRole.STUDENT, is_active=True,
                   teacher_id=coach.id, is_graduate=True)
        db.add_all([st, st2]); db.flush()

        def task(d, done):
            t = Task(student_id=st.id, date=d, type=TaskType.VIDEO, title="Kinematik — 1 video",
                     status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, is_draft=False)
            db.add(t); db.flush()
            return t.id

        t_future = task(today + timedelta(days=1), False)
        t_missed = task(today - timedelta(days=1), False)
        t_done = task(today - timedelta(days=1), True)
        rows = [("Kinematik 1", None), ("Kinematik 2", t_future),
                ("Kinematik 3", t_missed), ("Kinematik 4", t_done)]
        for sid in (st.id, st2.id):
            for i, (title, tid) in enumerate(rows):
                db.add(VideoBasketItem(
                    student_id=sid, coach_id=coach.id,
                    youtube_id=f"s{PFX}{i}"[:11].ljust(11, "x"), title=title, channel_title="Hoca",
                    duration_sec=900, playlist_title="Fizik Kampı", group_key=f"{PFX}:g",
                    group_label="Kinematik", role="anlatim", order=i,
                    task_id=tid if sid == st.id else None,
                ))
        db.commit()
        return {"coach": coach.id, "student": st.id, "student2": st2.id, "email": coach.email}


def cleanup(s):
    with SessionLocal() as db:
        ids = [s["student"], s["student2"]]
        db.execute(sa_delete(VideoBasketItem).where(VideoBasketItem.student_id.in_(ids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(User).where(User.id.in_([s["coach"], *ids])))
        db.commit()


def open_panel(pg, sid):
    pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
    pg.wait_for_timeout(2000)
    for _ in range(3):
        if pg.locator('[role="dialog"][data-state="open"]').count() == 0:
            break
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)
    pg.locator('[data-section="week:video-basket-fab"]').click()
    panel = pg.locator('[data-section="week:video-basket"]')
    panel.wait_for(timeout=5000)
    return panel


def main() -> int:
    from playwright.sync_api import sync_playwright

    s = seed()
    SHOTS.mkdir(exist_ok=True)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)

            panel = open_panel(pg, s["student"])
            legend = panel.locator('[data-section="week:video-state-legend"]')
            chk("lejant 4 durum", legend.locator("span").count() == 4, legend.inner_text() if legend.count() else "")
            head = panel.locator("div[draggable]").filter(has_text="Kinematik").first
            htxt = head.inner_text()
            chk("grup başlığında durum sayıları",
                "1 izlendi" in htxt and "1 verildi, izlenmedi" in htxt and "1 programda" in htxt, htxt)
            panel.get_by_role("button", name="Kinematik", exact=True).click()
            pg.wait_for_timeout(300)
            states = {}
            for st in ("bekliyor", "programda", "izlenmedi", "izlendi"):
                states[st] = panel.locator(f'li[data-video-state="{st}"]')
            chk("dört durum satırda ayrışır", all(states[k].count() == 1 for k in states),
                {k: v.count() for k, v in states.items()})
            chk("izlendi satırı Kinematik 4", "Kinematik 4" in states["izlendi"].inner_text())
            chk("izlenmedi satırı Kinematik 3 + tarih",
                "Kinematik 3" in states["izlenmedi"].inner_text()
                and (date.today() - timedelta(days=1)).strftime("%d.%m") in states["izlenmedi"].inner_text())
            bgs = {k: pg.evaluate("e => getComputedStyle(e).backgroundColor", v.element_handle())
                   for k, v in states.items()}
            chk("zemin tonları birbirinden farklı", len(set(bgs.values())) == 4, bgs)
            chk("bekleyen satır sürüklenebilir, diğerleri değil",
                states["bekliyor"].get_attribute("draggable") == "true"
                and states["izlendi"].get_attribute("draggable") == "false")
            sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            chk("yatay taşma yok", sw <= 1, f"sw={sw}")
            panel.screenshot(path=str(SHOTS / "video_states.png"))
            panel.get_by_label("Yalnız verilmeyen videolar").check()
            pg.wait_for_timeout(300)
            chk("filtre yalnız verilmeyeni bırakır",
                panel.locator("li[data-video-state]").count() == 1
                and panel.locator('li[data-video-state="bekliyor"]').count() == 1)

            panel = open_panel(pg, s["student2"])
            panel.get_by_role("button", name="Kinematik", exact=True).click()
            pg.wait_for_timeout(300)
            chk("başka öğrencide aynı videolar durumsuz (öğrenciye özel)",
                panel.locator('li[data-video-state="bekliyor"]').count() == 4)
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed}/{passed + len(failed)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
