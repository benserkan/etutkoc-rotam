"""Canlı — görev denemesi → Denemeler köprüsü + sonucu eksik denemeler (D3, 2026-10-20).

  1 Öğrenci 2 denemeyi "sonucu sonra gireceğim" ile çözdü → Bugün'de amber kart, 2 satır
  2 Karttan 1. deneme 14D 4Y → kart 1 satıra iner; Denemelerim'de ayrı "Programdaki denemeler" bölümünde
  3 Koç Denemeler sekmesi: kart 1 satır · kayıt ayrı bölümde, analize karışmaz
  4 Koç karttan 2. denemeyi girer → kart kaybolur, DB'de 2 kayıt
  5 Koyu tema ekran görüntüsü · 390px yatay kaydırma yok · metin kırpılmıyor · konsol temiz
Ön koşul: backend :8081 + Next :3000.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ExamResult, Subject, Task, TaskBookItem, Track, User, UserRole  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"ldb_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed():
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Köprü Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Köprü Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL)
        db.add(st); db.flush()
        mat = Subject(name="TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(mat); db.commit()
        d = {"coach": coach.id, "st": st.id, "mat": mat.id}
    get_login_limiter().reset()
    c = TestClient(app)
    assert c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD}).status_code == 200
    r = c.post(f"/api/v2/teacher/students/{d['st']}/deneme-tasks",
               json={"date": date.today().isoformat(), "kind": "brans", "subject_id": d["mat"], "count": 2,
                     "question_count": 20, "name": "Bilgi Sarmal TYT Matematik branş denemesi uzun adı",
                     "is_draft": False})
    assert r.status_code == 200, r.text
    d["task"] = r.json()["data"]["id"]
    d["items"] = sorted(x["id"] for x in r.json()["data"]["items"])
    get_login_limiter().reset()
    s = TestClient(app)
    assert s.post("/api/v2/auth/login", json={"email": f"{PFX}_s@test.invalid", "password": PWD}).status_code == 200
    r = s.post(f"/api/v2/student/tasks/{d['task']}/deneme-results",
               json={"rows": [{"item_id": i, "solved": True} for i in d["items"]]})
    assert r.status_code == 200, r.text
    get_login_limiter().reset()
    return d


def cleanup(d):
    with SessionLocal() as db:
        u = [d["coach"], d["st"]]
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == d["coach"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def recs(sid):
    with SessionLocal() as db:
        return [(r.task_book_item_id, r.net, r.import_source)
                for r in db.query(ExamResult).filter(ExamResult.student_id == sid).all()]


def login(page, email):
    page.goto(f"{WEB}/login", wait_until="networkidle")
    page.fill('input[name="email"]', email)
    page.fill('input[name="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(6000)


def dismiss(page):
    for t in ("Daha sonra", "Kapat"):
        el = page.query_selector(f'button:has-text("{t}")')
        if el and el.is_visible():
            el.click()
            page.wait_for_timeout(500)


def clipped(page, sel):
    return page.evaluate(
        """(sel) => { const out = []; document.querySelectorAll(sel + ' *').forEach(e => {
            const cs = getComputedStyle(e); if (cs.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth + 1)
            out.push(e.textContent.slice(0, 40)); }); return out; }""", sel)


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOTS, exist_ok=True)
    d = seed()
    i1, i2 = d["items"]
    print(f"\n=== canlı: deneme köprüsü — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark")
            page = ctx.new_page()
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            login(page, f"{PFX}_s@test.invalid")
            page.goto(f"{WEB}/student/day", wait_until="networkidle")
            page.wait_for_timeout(2500)
            dismiss(page)
            card = page.locator('[data-section="deneme-pending"]')
            check("1a Bugün'de 'sonucu girilmemiş' kartı", card.count() == 1)
            check("1b 2 satır", card.locator('[data-testid="deneme-pending-row"]').count() == 2)
            check("1c başlık '2 deneme'", "Sonucu girilmemiş 2 deneme" in (card.inner_text() if card.count() else ""))
            check("5a kartta kırpma yok", clipped(page, '[data-section="deneme-pending"]') == [])
            card.screenshot(path=os.path.join(SHOTS, "deneme_pending_dark.png"))

            card.locator('[data-testid="deneme-pending-row"]').first.locator('button:has-text("Sonucu gir")').click()
            page.wait_for_timeout(1000)
            dlg = page.locator('[role="dialog"]')
            dlg.locator('input[aria-label="Doğru"]').fill("14")
            dlg.locator('input[aria-label="Yanlış"]').fill("4")
            page.wait_for_timeout(200)
            check("2a pencerede net 13", "13" in dlg.inner_text(), dlg.inner_text()[:200])
            dlg.locator('button:has-text("Kaydet")').last.click()
            page.wait_for_timeout(2500)
            check("2b kart 1 satıra indi", page.locator('[data-testid="deneme-pending-row"]').count() == 1)
            rr = recs(d["st"])
            check("2c DB: 1 kayıt, net 13, kaynak task", rr == [(i1, 13.0, "task")], str(rr))
            page.goto(f"{WEB}/student/exams", wait_until="networkidle")
            page.wait_for_timeout(2500)
            check("2c2 Denemelerim varsayılan karne görünümünde program bölümü YOK",
                  page.locator('[data-section="exams:program"]').count() == 0)
            page.locator('button[role="tab"]:has-text("Branş denemeleri")').click()
            page.wait_for_timeout(800)
            body = page.inner_text("body")
            sec = page.locator('[data-section="exams:program"]')
            check("2d Denemelerim'de AYRI 'Programdaki denemeler' bölümünde",
                  sec.count() == 1 and "1. deneme" in sec.inner_text(), body[-400:])
            check("2d2 analiz sekmeleri açılmadı (karne yok, karışmadı)",
                  page.locator('button:has-text("Tüm Denemeler")').count() == 0)
            check("2e Denemelerim'de de kart (1)", "Sonucu girilmemiş 1 deneme" in body)

            m = ctx.new_page()
            m.set_viewport_size({"width": 390, "height": 860})
            m.goto(f"{WEB}/student/day", wait_until="networkidle")
            m.wait_for_timeout(2500)
            dismiss(m)
            ov = m.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("5b 390px yatay kaydırma yok", ov <= 1, str(ov))
            m.locator('[data-section="deneme-pending"]').screenshot(path=os.path.join(SHOTS, "deneme_pending_mobile.png"))
            m.close()
            check("5c öğrenci konsolu temiz", not errs, " | ".join(errs)[:300])
            ctx.close()

            ctx2 = b.new_context(viewport={"width": 1440, "height": 950}, color_scheme="dark")
            cp = ctx2.new_page()
            cerrs: list[str] = []
            cp.on("console", lambda m: cerrs.append(m.text) if m.type == "error" else None)
            login(cp, f"{PFX}_t@test.invalid")
            cp.goto(f"{WEB}/teacher/students/{d['st']}#exams", wait_until="networkidle")
            cp.wait_for_timeout(3500)
            dismiss(cp)
            check("30 koç Denemeler sekmesi canlıdaki gibi: program bölümü ve kart YOK",
                  cp.locator('[data-section="exams:program"]').count() == 0
                  and cp.locator('[data-section="deneme-pending"]').count() == 0)
            cp.goto(f"{WEB}/teacher/students/{d['st']}#program-exams", wait_until="networkidle")
            cp.reload(wait_until="networkidle")
            cp.wait_for_timeout(3500)
            dismiss(cp)
            ccard = cp.locator('[data-section="deneme-pending"]')
            check("3a koç Branş Denemeleri: kart 1 satır", ccard.count() == 1
                  and ccard.locator('[data-testid="deneme-pending-row"]').count() == 1)
            body = cp.inner_text("body")
            csec = cp.locator('[data-section="exams:program"]')
            check("3b kayıt ayrı 'Programdaki denemeler' bölümünde", csec.count() == 1
                  and "analizine katılmaz" in csec.inner_text(), body[-400:])
            check("3c analiz listesine/sekmelerine karışmadı",
                  cp.locator('button:has-text("Tüm Denemeler")').count() == 0
                  and cp.locator('button[aria-label="Denemeyi düzenle"]').count() == 0)
            csec.screenshot(path=os.path.join(SHOTS, "program_exams_dark.png"))
            if ccard.count():
                ccard.locator('button:has-text("Sonucu gir")').first.click()
                cp.wait_for_timeout(1000)
                cd = cp.locator('[role="dialog"]')
                cd.locator('input[aria-label="Doğru"]').fill("10")
                cd.locator('input[aria-label="Yanlış"]').fill("2")
                cd.locator('button:has-text("Kaydet")').last.click()
                cp.wait_for_timeout(2500)
                check("4a kart kayboldu", cp.locator('[data-section="deneme-pending"]').count() == 0)
                rr = sorted(recs(d["st"]))
                check("4b DB: 2 kayıt (13 + 9,5)", rr == [(i1, 13.0, "task"), (i2, 9.5, "task")], str(rr))
                cp.wait_for_timeout(1000)
                check("4c bölümde 2 program denemesi",
                      "2 deneme" in cp.locator('[data-section="exams:program"]').inner_text().lower())
            check("5d koç konsolu temiz", not cerrs, " | ".join(cerrs)[:300])
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
