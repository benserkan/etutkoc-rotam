# -*- coding: utf-8 -*-
"""Video Sepeti — kayıtlı listeler GERÇEK tarayıcı testi (dev :3000 + :8081).

İki oynatma listesi tohumlanır (YouTube anahtarı gerekmez). Kontrol: panel
açılışta yalnız EN SON listeyi gösterir (eski listeyle karışmaz) · liste
seçiciyle öteki listeye geçilir · "Kayıtlı listelerim" açılır, ad düzenlenir ·
silme onayı bekleyenleri kaldırır · metin kırpılmaz / yatay taşma yok.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.video_basket import VideoBasketItem, VideoSource
from app.services.security import hash_password

BASE = "http://localhost:3000"
PFX = f"lvs{secrets.token_hex(3)}"
PWD = "VideoListe1!xyz"
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
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Liste Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Liste Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, is_graduate=True)
        db.add(st); db.flush()
        old = VideoSource(coach_id=coach.id, source_key=f"pl:PL{PFX}old", url=f"https://www.youtube.com/playlist?list=PL{PFX}old",
                          playlist_id=f"PL{PFX}old", title="AYT Fizik Kampı Eski Liste", video_count=2,
                          created_at=now - timedelta(days=3), last_used_at=now - timedelta(days=3))
        new = VideoSource(coach_id=coach.id, source_key=f"pl:PL{PFX}new", url=f"https://www.youtube.com/playlist?list=PL{PFX}new",
                          playlist_id=f"PL{PFX}new", title="TYT Kimya Yeni Liste", video_count=2,
                          created_at=now, last_used_at=now)
        db.add_all([old, new]); db.flush()
        rows = [(old, "g1", "Atışlar", "Atışlar 1"), (old, "g1", "Atışlar", "Atışlar 2"),
                (new, "g2", "Mol Kavramı", "Mol Kavramı 1"), (new, "g2", "Mol Kavramı", "Mol Kavramı 2")]
        for i, (src, g, lab, title) in enumerate(rows):
            db.add(VideoBasketItem(
                student_id=st.id, coach_id=coach.id, youtube_id=f"x{PFX}{i}"[:11].ljust(11, "x"),
                title=title, channel_title="Hoca", duration_sec=900, playlist_title=src.title,
                group_key=f"{PFX}:{g}", group_label=lab, role="anlatim", order=i, source_id=src.id,
            ))
        db.commit()
        return {"coach": coach.id, "student": st.id, "email": coach.email, "new": new.id}


def cleanup(s):
    with SessionLocal() as db:
        db.execute(sa_delete(VideoBasketItem).where(VideoBasketItem.student_id == s["student"]))
        db.execute(sa_delete(VideoSource).where(VideoSource.coach_id == s["coach"]))
        db.execute(sa_delete(User).where(User.id.in_([s["coach"], s["student"]])))
        db.commit()


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
            pg.goto(f"{BASE}/teacher/students/{s['student']}/week", wait_until="networkidle")
            pg.wait_for_timeout(2000)
            for _ in range(3):
                if pg.locator('[role="dialog"][data-state="open"]').count() == 0:
                    break
                pg.keyboard.press("Escape")
                pg.wait_for_timeout(500)

            pg.locator('[data-section="week:video-basket-fab"]').click()
            panel = pg.locator('[data-section="week:video-basket"]')
            panel.wait_for(timeout=5000)
            chk("açılışta en son liste gösterilir", panel.get_by_text("Mol Kavramı", exact=True).count() == 1)
            chk("eski liste karışmaz", panel.get_by_text("Atışlar", exact=True).count() == 0)
            sel = panel.locator('[data-section="week:video-basket-list"]')
            chk("liste seçicide iki liste + tümü", sel.locator("option").count() == 3)
            sel.select_option(label=sel.locator("option").nth(1).inner_text())
            pg.wait_for_timeout(400)
            chk("seçiciyle eski listeye geçilir", panel.get_by_text("Atışlar", exact=True).count() == 1
                and panel.get_by_text("Mol Kavramı", exact=True).count() == 0)

            saved = panel.locator('[data-section="week:video-sources"]')
            saved.get_by_role("button", name="Kayıtlı listelerim").click()
            chk("kayıtlı listeler açılır (2)", saved.locator("li").count() == 2)
            row = saved.locator("li").filter(has_text="TYT Kimya Yeni Liste")
            row.get_by_role("button", name="Adını / dersini düzenle").click()
            saved.get_by_label("Liste adı").fill("Kimya — Hoca X")
            saved.get_by_role("button", name="Kaydet").click()
            pg.wait_for_timeout(1500)
            chk("liste adı düzenlendi", saved.get_by_text("Kimya — Hoca X", exact=True).count() == 1
                and saved.get_by_text("YouTube adı: TYT Kimya Yeni Liste").count() == 1)

            # kırpma / taşma
            clipped = pg.evaluate("""() => [...document.querySelectorAll('[data-section="week:video-basket"] *')]
                .filter(e => e.children.length === 0 && e.textContent.trim() && getComputedStyle(e).textOverflow === 'ellipsis'
                        && e.scrollWidth > e.clientWidth).length""")
            chk("panelde kırpılmış metin yok", clipped == 0, f"n={clipped}")
            sw = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            chk("yatay taşma yok", sw <= 1, f"sw={sw}")
            pg.screenshot(path=str(SHOTS / "video_sources.png"))

            row = saved.locator("li").filter(has_text="Kimya — Hoca X")
            row.get_by_role("button", name="Kayıtlı listeyi sil").click()
            row.get_by_label("Bu öğrencinin sepetinde bekleyen 2 videoyu da kaldır").check()
            row.get_by_role("button", name="Sil", exact=True).click()
            pg.wait_for_timeout(1500)
            with SessionLocal() as db:
                n_src = db.query(VideoSource).filter(VideoSource.coach_id == s["coach"]).count()
                n_items = db.query(VideoBasketItem).filter(VideoBasketItem.student_id == s["student"]).count()
            chk("liste silindi + bekleyenleri kaldırıldı", n_src == 1 and n_items == 2, f"src={n_src} items={n_items}")
            chk("sepet kalan listeye döner", panel.get_by_text("Atışlar", exact=True).count() == 1)
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed}/{passed + len(failed)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
