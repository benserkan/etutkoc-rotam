# -*- coding: utf-8 -*-
"""Video görevi — öğrenci ekranı + çıktılar (GERÇEK tarayıcı; dev :3000 + :8081).

Bugüne 3 videoluk görev tohumlanır. Kontrol: öğrenci Bugün ekranında her video
ayrı link (YouTube adresi, yeni sekme) · tıklayınca YouTube açılır · öğrenci
hafta çıktısı + koç program çıktısı videoları listeler. Ekran görüntüleri .shots.
"""
import sys
from datetime import date
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
PFX = f"lvsp{secrets.token_hex(3)}"
PWD = "VideoCikti1!xyz"
SHOTS = Path(__file__).resolve().parent.parent / ".shots"
passed = 0
failed: list[str] = []
TITLES = [("Hareket 1 | Konum", "anlatim"), ("Hareket 2 | İvme", "anlatim"), ("Hareket Soru Çözümü", "soru")]


def chk(name, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Çıktı Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Çıktı Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, is_graduate=True, must_change_password=False)
        db.add(st); db.flush()
        t = Task(student_id=st.id, date=date.today(), type=TaskType.VIDEO,
                 title="TYT Fizik · Hareket — 3 video (60 dk)", status=TaskStatus.PENDING,
                 is_draft=False, link_url="https://www.youtube.com/watch?v=aaaaaaaaaa0")
        db.add(t); db.flush()
        for i, (title, role) in enumerate(TITLES):
            db.add(VideoBasketItem(
                student_id=st.id, coach_id=coach.id, youtube_id=f"aaaaaaaaaa{i}", title=title,
                channel_title="Hoca", duration_sec=1200, playlist_title="Fizik Kampı",
                group_key=f"{PFX}:g", group_label="Hareket", role=role, order=i, task_id=t.id,
            ))
        db.commit()
        return {"coach": coach.id, "student": st.id, "coach_email": coach.email, "st_email": st.email}


def cleanup(s):
    with SessionLocal() as db:
        db.execute(sa_delete(VideoBasketItem).where(VideoBasketItem.student_id == s["student"]))
        db.execute(sa_delete(Task).where(Task.student_id == s["student"]))
        db.execute(sa_delete(User).where(User.id.in_([s["coach"], s["student"]])))
        db.commit()


def login(pg, email):
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', email)
    pg.fill('input[type="password"]', PWD)
    pg.click('button[type="submit"]')
    pg.wait_for_timeout(3500)


def close_dialogs(pg):
    for _ in range(3):
        if pg.locator('[role="dialog"][data-state="open"]').count() == 0:
            break
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(500)


def main() -> int:
    from playwright.sync_api import sync_playwright

    s = seed()
    SHOTS.mkdir(exist_ok=True)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            # ---- öğrenci (telefon boyutu)
            ctx = b.new_context(viewport={"width": 390, "height": 844})
            # Bu ağ YouTube'u engelleyebilir — isteği yakala, gerçek adres doğrulansın.
            ctx.route("**://*.youtube.com/**", lambda r: r.fulfill(status=200, body="<html>yt</html>",
                                                                  content_type="text/html"))
            pg = ctx.new_page()
            login(pg, s["st_email"])
            pg.goto(f"{BASE}/student/day", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            close_dialogs(pg)
            links = pg.locator("a[href*='youtube.com/watch']")
            hrefs = [links.nth(i).get_attribute("href") for i in range(links.count())]
            chk("öğrenci Bugün: 3 videonun her biri ayrı link",
                all(any(f"aaaaaaaaaa{i}" in (h or "") for h in hrefs) for i in range(3)), hrefs)
            chk("linkler yeni sekmede açılır",
                all(links.nth(i).get_attribute("target") == "_blank" for i in range(links.count())))
            chk("soru çözümü videosu işaretli", pg.get_by_text("soru çözümü").count() >= 1)
            chk("çok videoda tekrar eden 'Videoyu izle' düğmesi yok",
                pg.get_by_text("Videoyu izle").count() == 0)
            pg.screenshot(path=str(SHOTS / "student_day_videos.png"), full_page=True)
            with ctx.expect_page() as newp:
                pg.locator("a[href*='aaaaaaaaaa1']").first.click()
            from urllib.parse import unquote
            newp.value.wait_for_load_state("load")
            u = unquote(unquote(newp.value.url))
            chk("tıklayınca o videonun YouTube sekmesi açılır",
                "youtube.com" in u and "aaaaaaaaaa1" in u, newp.value.url)
            newp.value.close()
            pg.set_viewport_size({"width": 1440, "height": 900})  # çıktı yatay A4
            pg.goto(f"{BASE}/student/week/print", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            body = pg.inner_text("body")
            chk("öğrenci hafta çıktısında videolar listelenir",
                all(t in body for t, _ in TITLES), body[:400])
            pg.screenshot(path=str(SHOTS / "student_week_print_videos.png"), full_page=True)
            ctx.close()
            # ---- koç program çıktısı
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            pg = ctx.new_page()
            login(pg, s["coach_email"])
            pg.goto(f"{BASE}/teacher/students/{s['student']}/program/print", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            body = pg.inner_text("body")
            chk("koç program çıktısında videolar listelenir",
                all(t in body for t, _ in TITLES), body[:400])
            pg.screenshot(path=str(SHOTS / "teacher_program_print_videos.png"), full_page=True)
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed}/{passed + len(failed)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
