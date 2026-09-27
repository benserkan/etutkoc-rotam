"""İskeleti başka öğrencilere kopyala — canlı tarayıcı testi (2026-09-27).

Kendi verisini kurar/temizler. Dev sunucular (:3000 + :8081) açık olmalı.
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
from app.models import Subject, User, UserRole
from app.models.weekly_skeleton import SkeletonGhostAction, WeeklySkeleton, WeeklySkeletonSlot
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

BASE = "http://localhost:3000"
PFX = f"lskc_{secrets.token_hex(3)}"
PWD = "LiveSkelCopy!234"
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
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Kopya Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        ids = []
        for n, grp in [("Kaynak Öğrenci", "10-A"), ("Hedef Bir Çok Uzun Adlı Öğrenci", "10-A"),
                       ("Hedef İki", "10-B")]:
            u = User(email=f"{PFX}_{len(ids)}@test.invalid", password_hash=hash_password(PWD),
                     full_name=n, role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                     grade_level=10, class_group=grp)
            db.add(u)
            db.flush()
            ids.append(u.id)
        subj = Subject(name=f"Kopya Ders {PFX}", teacher_id=coach.id, order=1)
        db.add(subj)
        db.flush()
        sk = WeeklySkeleton(student_id=ids[0], coach_id=coach.id, name="Okul dönemi")
        db.add(sk)
        db.flush()
        for wd in (0, 2, 4):
            sk.slots.append(WeeklySkeletonSlot(weekday=wd, subject_id=subj.id, position=0,
                                               label="Paragraf", is_routine=True, default_count=2))
        db.commit()
        return {"coach": coach.id, "email": coach.email, "ids": ids, "subj": subj.id}


def cleanup(d):
    with SessionLocal() as db:
        db.execute(sa_delete(SkeletonGhostAction).where(SkeletonGhostAction.student_id.in_(d["ids"])))
        for x in db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id.in_(d["ids"])):
            db.delete(x)
        db.flush()
        db.execute(sa_delete(Subject).where(Subject.id == d["subj"]))
        db.execute(sa_delete(User).where(User.id.in_(d["ids"] + [d["coach"]])))
        db.commit()


ELLIPSIS_JS = """(sel) => { const r = document.querySelector(sel); if (!r) return ['missing'];
  const out=[]; for (const el of r.querySelectorAll('*')) { const cs=getComputedStyle(el);
  if (cs.textOverflow==='ellipsis' && el.scrollWidth>el.clientWidth+1) out.push(el.textContent.slice(0,40)); }
  return out; }"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    src = d["ids"][0]
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/students/{src}/week", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(800)
            pg.get_by_role("button", name="İskelet", exact=True).click()
            pg.locator('[data-testid="period-strip"]').wait_for(timeout=10000)
            pg.click('[data-testid="open-skeleton-copy"]')
            panel = pg.locator('[data-testid="skeleton-copy-panel"]')
            panel.wait_for(timeout=10000)
            pg.wait_for_selector('[data-testid="skeleton-copy-row"]', timeout=10000)
            rows = pg.locator('[data-testid="skeleton-copy-row"]')
            chk("1. kaynak hariç 2 öğrenci", rows.count() == 2, str(rows.count()))
            txt = panel.inner_text()
            chk("2. şube başlıkları", "10-A" in txt and "10-B" in txt)
            chk("3. etki açıklaması (yeni dönem)", "yeni dönem açılır" in txt)
            panel.get_by_text("Bugünkü dönemlerinin yerine").click()
            chk("4. replace modunda açıklama değişir", "iskeleti yok" in panel.inner_text())
            panel.get_by_text("Yeni dönem olarak").click()
            start = (date.today() + timedelta(days=7)).isoformat()
            panel.locator('input[type="date"]').fill(start)
            for i in range(rows.count()):
                rows.nth(i).locator('input[type="checkbox"]').check()
            chk("5. panelde kırpma yok", pg.evaluate(ELLIPSIS_JS, '[data-testid="skeleton-copy-panel"]') == [])
            pg.screenshot(path=os.path.join(SHOT_DIR, "skeleton_copy.png"))
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(300)
            bad = measure(pg, '[data-testid="skeleton-copy-panel"]', min_ratio=3.0)["bad"]
            chk("6. koyu tema kontrastı", bad == 0, str(bad))
            pg.evaluate("() => document.documentElement.classList.remove('dark')")
            pg.click('[data-testid="skeleton-copy-submit"]')
            pg.wait_for_timeout(2500)
            with SessionLocal() as db:
                for sid in d["ids"][1:]:
                    sks = db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id == sid).all()
                    ok = len(sks) == 1 and len(sks[0].slots) == 3 and sks[0].valid_from.isoformat() == start
                    chk(f"7. öğrenci {sid}: yeni dönem 3 satır", ok, str([(x.id, x.name, [(s.weekday, s.label, s.subject_id) for s in x.slots]) for x in sks]))
            chk("8. panel kapandı", pg.locator('[data-testid="skeleton-copy-panel"]').count() == 0)
            b.close()
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
