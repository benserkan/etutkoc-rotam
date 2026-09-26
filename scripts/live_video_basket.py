# -*- coding: utf-8 -*-
"""Video Sepeti — GERÇEK tarayıcı testi (dev: :3000 + :8081 açık olmalı).

Sepet verisi DB'ye doğrudan tohumlanır (YouTube anahtarı gerekmez). Kontrol:
yüzen düğme → panel açılır · gruplar görünür · grubu ızgaradaki güne sürükle →
tek görev + 3 video · ızgarada ▶ dk rozeti amber (>60) · panel "programda" ·
tek videoyu başka güne sürükle → yeni görev · gün kartında çoklu link listesi ·
yatay taşma yok · panel ızgarayla aynı anda görünür (kaydırmada sabit).
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
from app.models import Subject, Task, User, UserRole
from app.models.video_basket import VideoBasketItem
from app.services.security import hash_password

BASE = "http://localhost:3000"
PFX = f"lvb{secrets.token_hex(3)}"
PWD = "VideoSepet1!xyz"
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
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Video Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Video Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, is_graduate=True)
        db.add(st); db.flush()
        subj = db.query(Subject).filter(Subject.name == "TYT Matematik",
                                        Subject.teacher_id.is_(None)).first()
        rows = [
            ("g1", "Temel Kavramlar", "anlatim", "Temel Kavramlar 1 | Kamp 1. Gün", 1500),
            ("g1", "Temel Kavramlar", "anlatim", "Temel Kavramlar 2 | Kamp 2. Gün", 1500),
            ("g1", "Temel Kavramlar", "soru", "Checkpoint 1", 900),
            ("g2", "Üslü Sayılar", "anlatim", "Üslü İfadeler 1", 1200),
            ("g2", "Üslü Sayılar", "anlatim", "Üslü İfadeler 2", 1200),
        ]
        for i, (g, lab, role, title, sec) in enumerate(rows):
            db.add(VideoBasketItem(
                student_id=st.id, coach_id=coach.id, youtube_id=f"vid{PFX}{i}"[:11].ljust(11, "x"),
                title=title, channel_title="Hoca", duration_sec=sec, playlist_title="TYT Kamp",
                subject_id=subj.id if subj else None, group_key=f"{PFX}:{g}",
                group_label=lab, role=role, order=i,
            ))
        db.commit()
        return {"coach": coach.id, "student": st.id, "email": coach.email}


def cleanup(s):
    with SessionLocal() as db:
        db.execute(sa_delete(VideoBasketItem).where(VideoBasketItem.student_id == s["student"]))
        db.execute(sa_delete(Task).where(Task.student_id == s["student"]))
        db.execute(sa_delete(User).where(User.id.in_([s["coach"], s["student"]])))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    s = seed()
    sid = s["student"]
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
            pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
            pg.wait_for_timeout(2000)
            for _ in range(3):  # yeni hesap karşılama/rehber diyaloğu
                if pg.locator('[role="dialog"][data-state="open"]').count() == 0:
                    break
                pg.keyboard.press("Escape")
                pg.wait_for_timeout(500)

            fab = pg.locator('[data-section="week:video-basket-fab"]')
            chk("yüzen düğme görünür + bekleyen sayı", fab.is_visible() and "5" in fab.inner_text(), fab.inner_text() if fab.count() else "")
            fab.click()
            panel = pg.locator('[data-section="week:video-basket"]')
            panel.wait_for(timeout=5000)
            chk("iki konu grubu", panel.get_by_text("Temel Kavramlar", exact=True).count() == 1
                and panel.get_by_text("Üslü Sayılar", exact=True).count() == 1)
            chk("gruplar kapalı gelir", panel.locator("li[draggable]").count() == 0)
            for g in ("Temel Kavramlar", "Üslü Sayılar"):  # başlığa tıkla → açılır
                panel.get_by_role("button", name=g, exact=True).click()
            pg.wait_for_timeout(300)
            chk("başlığa tıklayınca videolar görünür", panel.locator("li[draggable]").count() == 5)
            chk("soru çözümü rolü ayrı işaretli", panel.locator("select").filter(has_text="Soru çözümü").count() >= 1)

            # ızgaradaki yarının hücresi (geçmiş değil)
            target = (date.today() + timedelta(days=1)).isoformat()
            cells = pg.locator("section button[title$='düzenlemek için tıkla']")
            # tarih etiketinden hedef hücreyi bul
            # hücreler Pzt..Paz sırasında; yarın bu haftadaysa o, değilse Pazar
            wd = date.today().weekday()
            cell = cells.nth(min(wd + 1, 6))
            grp_head = panel.locator("div[draggable='true']").filter(has_text="Temel Kavramlar").first
            chk("panel ve ızgara aynı anda görünür", grp_head.is_visible() and cell.is_visible())
            grp_head.drag_to(cell)
            pg.wait_for_timeout(2500)
            with SessionLocal() as db:
                tasks = db.query(Task).filter(Task.student_id == sid).all()
                t1 = tasks[0] if tasks else None
                nv = db.query(VideoBasketItem).filter(VideoBasketItem.task_id == (t1.id if t1 else -1)).count()
            chk("grup sürükle → tek görev 3 video", len(tasks) == 1 and nv == 3, f"tasks={len(tasks)} nv={nv}")
            chk("görev başlığı konu + 65 dk", t1 is not None and "Temel Kavramlar" in t1.title and "65 dk" in t1.title, t1.title if t1 else "")
            badge = pg.locator("section span", has_text="▶ 65 dk")
            chk("ızgarada ▶ 65 dk rozeti amber", badge.count() >= 1 and "bg-amber-500" in (badge.first.get_attribute("class") or ""))
            chk("panelde 'programda' etiketi", panel.get_by_text("programda").count() >= 1 or
                "2 video bekliyor" in panel.inner_text())

            # tek video başka güne
            row = panel.locator("li[draggable='true']").filter(has_text="Üslü İfadeler 1").first
            # ilk hücreyle AYNI olmayan geçmiş-olmayan gün
            dest = cells.nth(min(wd + 1, 6) - 1) if min(wd + 1, 6) - 1 >= wd else None
            if dest is not None:
                row.drag_to(dest)
                pg.wait_for_timeout(2500)
            with SessionLocal() as db:
                n_tasks = db.query(Task).filter(Task.student_id == sid).count()
            chk("tek video başka güne → yeni görev", dest is None or n_tasks == 2, f"n={n_tasks}")
            vb = pg.locator("section span[title='Video görevi']", has_text="▶ 3")
            chk("ızgarada dolgulu video rozeti (▶ 3)", vb.count() >= 1 and "bg-rose-600" in (vb.first.get_attribute("class") or ""))
            lab = pg.locator("section span", has_text="Temel Kavramlar")
            chk("ızgara etiketi kırpılmadan: 'Temel Kavramlar'", lab.count() >= 1)

            sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            chk("yatay taşma yok", sw <= 1, f"sw={sw}")
            pg.evaluate("window.scrollTo(0, 900)")
            pg.wait_for_timeout(400)
            chk("kaydırınca panel yerinde (fixed)", panel.is_visible())
            pg.evaluate("window.scrollTo(0, 0)")
            pg.screenshot(path=str(SHOTS / "video_basket.png"))

            # gün kartı: ızgaradan güne tıkla → çoklu link listesi
            cell.click()
            pg.wait_for_timeout(1500)
            summ = pg.locator("#day-editor button[aria-expanded]", has_text="3 video")
            chk("gün kartında liste katlı: özet satırı (3 video · 65 dk · 1 soru çözümü)",
                summ.count() >= 1 and "65 dk" in summ.first.inner_text() and "1 soru çözümü" in summ.first.inner_text()
                and pg.locator("#day-editor ol li a", has_text="Checkpoint 1").count() == 0)
            chk("'videonun ilkini izle' tekrar düğmesi yok", pg.locator("#day-editor", has_text="videonun ilkini izle").count() == 0)
            summ.first.click()
            pg.wait_for_timeout(300)
            chk("özete tıklayınca numaralı liste açılır",
                pg.locator("#day-editor ol li a", has_text="Checkpoint 1").count() >= 1)
            pg.screenshot(path=str(SHOTS / "video_daycard.png"))
            # tek videoyu görevden çıkar (4 videodan birini çıkarma senaryosu)
            pg.once("dialog", lambda d: d.accept())
            pg.locator("#day-editor button[aria-label='Checkpoint 1 videosunu görevden çıkar']").click()
            pg.wait_for_timeout(2000)
            with SessionLocal() as db:
                t1r = db.get(Task, t1.id)
                left = db.query(VideoBasketItem).filter(VideoBasketItem.task_id == t1.id).count()
                back = db.query(VideoBasketItem).filter(VideoBasketItem.student_id == sid,
                                                         VideoBasketItem.title == "Checkpoint 1").one()
            chk("× ile tek video görevden çıkar, görev 2 videoyla kalır",
                t1r is not None and left == 2 and back.task_id is None, f"left={left}")
            chk("görev başlığı yeni video sayısına güncellendi", t1r is not None and "2 video" in t1r.title,
                t1r.title if t1r else "")
            chk("gün kartı özeti 2 video", pg.locator("#day-editor button[aria-expanded]", has_text="2 video").count() >= 1)
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed}/{passed + len(failed)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
