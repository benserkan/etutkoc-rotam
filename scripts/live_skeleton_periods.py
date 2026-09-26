"""İskelet F2-2 — dönemli iskelet: CANLI E2E (dev sunucu + Playwright).

   1. Düzenleyicide dönem şeridi: tek dönem "Yaz", "bugün" rozetli
   2. "Yeni dönem" → boş dönem, bugün+2'den başlar → şeritte 2 dönem, yeni
      dönem seçili; Yaz'ın bitişi bugün+1
   3. Hafta bölünür: bugün ve bugün+1 Yaz'dan öneri alır, bugün+2 boş dönemde
      öneri YOK (API ile doğrulanır)
   4. "Dönemi düzenle" → ad değişir, şerit güncellenir
   5. Şeritte kırpılmış metin / taşma yok · koyu tema okunur
   6. Dönemi sil → şeritte tek dönem kalır, bugün+2 yeniden Yaz'dan öneri alır

Ön koşul: backend :8081 + Next :3000.
  PYTHONPATH=. python scripts/live_skeleton_periods.py
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

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Subject, Task, TaskType, User, UserRole
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib_live_contrast import measure  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lsp_{secrets.token_hex(3)}"
PWD = "SkelPer!2345xy"
SHOT_DIR = os.path.join(os.getcwd(), ".shots")
passed = 0
failed: list[str] = []


def chk(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    today = date.today()
    hist = [today - timedelta(days=i) for i in range(7, 0, -1)]
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Lsp Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Lsp Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        subj = Subject(name=f"Lsp Ders {PFX}", teacher_id=coach.id, order=1)
        db.add(subj)
        db.flush()
        for d in hist:
            db.add(Task(student_id=st.id, date=d, type=TaskType.OTHER,
                        title=f"{subj.name} · yaz işi", is_draft=False))
        out = dict(coach=coach.id, st=st.id, subj=subj.id, email=coach.email,
                   h0=hist[0].isoformat(), h1=hist[-1].isoformat())
        db.commit()
        return out


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id == s["st"]))
        for x in db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id == s["st"]):
            db.delete(x)
        db.execute(sa_delete(Task).where(Task.student_id == s["st"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subj"]))
        db.execute(sa_delete(User).where(User.id.in_([s["st"], s["coach"]])))
        db.commit()


STRIP = '[data-testid="period-strip"]'
CHIP = '[data-testid="period-chip"]'


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOT_DIR, exist_ok=True)
    s = seed()
    sid = s["st"]
    today = date.today()
    t1, t2 = today + timedelta(days=1), today + timedelta(days=2)
    print(f"\n=== İskelet dönemleri — canlı (öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)
            api = f"{BASE}/api/v2/teacher/students/{sid}/skeleton"
            r = pg.request.post(f"{api}/from-week", data={"start": s["h0"], "end": s["h1"], "name": "Yaz"})
            assert r.ok, r.text()

            def ghost_count(d: date) -> int:
                j = pg.request.get(f"{api}/ghosts?start={d.isoformat()}&end={d.isoformat()}").json()
                return sum(len(x["ghosts"]) for x in j["days"])

            pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(800)

            # 1
            pg.get_by_role("button", name="İskelet", exact=True).click()
            strip = pg.locator(STRIP)
            strip.wait_for(timeout=10000)
            chips = pg.locator(CHIP).all_inner_texts()
            chk("1. şeritte tek dönem 'Yaz' · bugün rozeti",
                len(chips) == 1 and "Yaz" in chips[0] and "bugün" in chips[0], str(chips))

            # 2
            strip.get_by_role("button", name="Yeni dönem").click()
            form = pg.locator('[data-testid="new-period-form"]')
            form.locator('input[aria-label="Dönem adı"]').fill("Yarıyıl tatili")
            form.get_by_text("Boş dönem").click()
            form.locator('input[aria-label="Dönem başlangıcı"]').fill(t2.isoformat())
            form.get_by_role("button", name="Dönemi başlat").click()
            pg.wait_for_timeout(2000)
            chips = pg.locator(CHIP).all_inner_texts()
            yaz = next((c for c in chips if c.startswith("Yaz")), "")
            yy = next((c for c in chips if c.startswith("Yarıyıl")), "")
            t1s = t1.strftime("%d.%m.%Y")
            t2s = t2.strftime("%d.%m.%Y")
            sel = pg.locator(f"{CHIP}.bg-cyan-700").inner_text() if pg.locator(f"{CHIP}.bg-cyan-700").count() else ""
            chk("2. yeni dönem: 2 dönem · Yaz bitişi bugün+1 · yeni dönem bugün+2'den · seçili",
                len(chips) == 2 and t1s in yaz and t2s in yy and "süresiz" in yy
                and sel.startswith("Yarıyıl"), f"{chips} seçili={sel}")

            # 3
            g0, g1, g2 = ghost_count(today), ghost_count(t1), ghost_count(t2)
            chk("3. hafta bölünür: bugün ve +1 Yaz'dan öneri, +2 boş dönemde öneri yok",
                g0 > 0 and g1 > 0 and g2 == 0, f"{g0} {g1} {g2}")

            # 4
            strip.get_by_role("button", name="Dönemi düzenle").click()
            ef = pg.locator('[data-testid="edit-period-form"]')
            ef.locator('input[aria-label="Dönem adı"]').fill("Tatil")
            ef.get_by_role("button", name="Kaydet").click()
            pg.wait_for_timeout(1500)
            chips = pg.locator(CHIP).all_inner_texts()
            chk("4. dönem adı değişti", any(c.startswith("Tatil") for c in chips), str(chips))

            # 5
            clip = pg.evaluate(
                """(sel) => { const s = document.querySelector(sel);
                  const els = [...s.querySelectorAll('*')].filter(e =>
                    getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1);
                  return {clipped: els.length, overflow: s.scrollWidth > s.clientWidth + 1}; }""",
                STRIP)
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(600)
            low = measure(pg, STRIP, min_ratio=3.0)["bad"]
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_periods_dark.png"))
            pg.evaluate("() => document.documentElement.classList.remove('dark')")
            chk("5. şeritte kırpma/taşma yok · koyu tema okunur",
                clip["clipped"] == 0 and not clip["overflow"] and low == 0, f"{clip} bad={low}")
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_periods.png"))

            # 6 — seçili (Tatil) dönemi sil; confirm kabul
            pg.once("dialog", lambda d: d.accept())
            pg.get_by_role("button", name="Dönemi sil").click()
            pg.wait_for_timeout(2000)
            chips = pg.locator(CHIP).all_inner_texts()
            chk("6. dönem silindi → tek dönem, +2 yeniden Yaz'dan öneri alır",
                len(chips) == 1 and chips[0].startswith("Yaz") and ghost_count(t2) > 0, str(chips))
            b.close()
    finally:
        cleanup(s)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
