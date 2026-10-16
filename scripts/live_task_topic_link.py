"""Canlı (gerçek tarayıcı) — konusuz test görevleri (2026-10-16).

Ön koşul: backend :8081 + Next.js :3000 ayakta.
  A) "Diğer" formuna "fotosentez" + "AÇI 2 TEST" → konu paneli açılır, kesin öneri seçili
     gelir → kayıt "konuya bağlı test" olur (DB: TEST + topic kalemi 2 test)
  B) "trigo" (tahmin) → öneri seçili GELMEZ, koç seçer → bağlı kaydedilir
  C) /teacher/unlinked-tasks: kesin satır işaretli, tahmin satırında konu seçilir →
     "Seçilenleri konuya bağla" → iki görev de bağlanır, tamamlanmış görev 2/2 sayılır
  D) koyu tema kontrast + 390px taşma

  python scripts/live_task_topic_link.py
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskBookItem, TaskStatus, TaskType, Topic, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lttl_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
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


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Canlı Rehber",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Canlı Onuncu",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=10)
        db.add(st)
        db.flush()
        t1 = Task(student_id=st.id, date=today - timedelta(days=1), type=TaskType.OTHER, title="Kimya · MOL",
                  notes="AÇI 2 TEST", is_draft=False, status=TaskStatus.COMPLETED)
        t2 = Task(student_id=st.id, date=today - timedelta(days=1), type=TaskType.OTHER,
                  title="Biyoloji · fotosentez", notes="2 test", is_draft=False, status=TaskStatus.PENDING)
        db.add_all([t1, t2])
        db.commit()
        return {"coach": coach.id, "st": st.id, "t_mol": t1.id, "t_fot": t2.id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st"], d["coach"]]
        tids = [t.id for t in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def _task_rows(sid: int):
    with SessionLocal() as db:
        out = []
        for t in db.query(Task).filter(Task.student_id == sid).order_by(Task.id).all():
            it = t.book_items[0] if t.book_items else None
            tp = db.get(Topic, it.topic_id) if it and it.topic_id else None
            out.append((t.id, t.title, t.type.value, tp.name if tp else None,
                        it.planned_count if it else None, it.completed_count if it else None))
        return out


def _open_other_form(page, sid):
    page.goto(f"{WEB}/teacher/students/{sid}/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(1200)
    for sel in ('text="Yeni görev ekle"', 'text="Görev ekle"'):
        el = page.query_selector(sel)
        if el:
            el.click()
            page.wait_for_timeout(1000)
            break
    det = page.query_selector('text="Ayrıntılı form"')
    if det:
        det.click()
        page.wait_for_timeout(1000)
    page.locator('button:has-text("Diğer")').first.click()
    page.wait_for_timeout(800)


def _fill_other(page, subject: str, title: str, notes: str):
    form = page.locator('form:has(input[placeholder="Detay açıklama"])').first
    form.locator("select").first.select_option(label=subject)
    form.locator('input[placeholder="Örn. Konu özeti hazırla"]').fill(title)
    form.locator('input[placeholder="Detay açıklama"]').fill(notes)
    page.wait_for_timeout(2500)  # 500 ms gecikme + öneri isteği
    return form


def main() -> int:
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from lib_live_contrast import measure

    d = seed()
    print(f"\n=== canlı: konusuz test görevleri — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 950})
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{PFX}_t@test.invalid")
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            # ---- A: kesin öneri
            _open_other_form(page, d["st"])
            form = _fill_other(page, "Biyoloji", "fotosentez", "AÇI 2 TEST")
            panel = page.locator('text=Bu görevde 2 test var').first
            check("A1 'N test' yazınca konu paneli açıldı", panel.count() > 0 and panel.is_visible())
            sel = page.locator('select[aria-label="Görevin konusu"]')
            chosen = sel.evaluate("e => e.options[e.selectedIndex]?.text || ''") if sel.count() else ""
            check("A2 kesin öneri seçili geldi (Fotosentez)", "Fotosentez" in chosen, chosen)
            check("A3 'konuya bağlı kaydedilecek' notu", page.locator('text=olarak seçilen konuya bağlı').count() > 0)
            page.screenshot(path=".shots/topic_link_form.png")
            before = len(_task_rows(d["st"]))
            form.locator('button[type="submit"]').first.click()
            page.wait_for_timeout(2500)
            rows = _task_rows(d["st"])
            new = rows[-1] if len(rows) > before else None
            check("A4 kayıt: TEST + Fotosentez kalemi 2 test",
                  new and new[2] == "test" and new[3] == "Fotosentez" and new[4] == 2, str(new))

            # ---- B: tahmin → koç seçer
            form = _fill_other(page, "Matematik", "trigo", "2 test")
            sel = page.locator('select[aria-label="Görevin konusu"]')
            val = sel.input_value() if sel.count() else "x"
            check("B1 tahminde öneri otomatik seçilmez", val == "", val)
            opts = sel.evaluate("e => [...e.options].map(o => o.text)")
            pick = next((o for o in opts if "Trigonometrik" in o), None)
            check("B2 seçeneklerde trigonometri konuları var", pick is not None, str(opts)[:200])
            if pick:
                sel.select_option(label=pick)
            before = len(_task_rows(d["st"]))
            form.locator('button[type="submit"]').first.click()
            page.wait_for_timeout(2500)
            rows = _task_rows(d["st"])
            new = rows[-1] if len(rows) > before else None
            check("B3 seçilen konuyla TEST olarak kaydedildi",
                  new and new[2] == "test" and new[3] and "Trigonometrik" in new[3], str(new))

            # ---- C: toplu bağlama sayfası
            page.goto(f"{WEB}/teacher/unlinked-tasks", wait_until="networkidle")
            page.wait_for_timeout(2500)
            check("C1 sayfa: 2 görev listelendi", page.locator('text=Kimya · MOL').count() > 0
                  and page.locator('text=Biyoloji · fotosentez').count() > 0)
            fot_cb = page.locator('input[type="checkbox"][aria-label="Biyoloji · fotosentez görevini seç"]')
            mol_cb = page.locator('input[type="checkbox"][aria-label="Kimya · MOL görevini seç"]')
            check("C2 kesin satır (fotosentez) işaretli, tahmin satırı (mol) işaretsiz",
                  fot_cb.is_checked() and not mol_cb.is_checked())
            mol_li = page.locator('li:has-text("Kimya · MOL")')
            mol_sel = mol_li.locator('select[aria-label="Konu"]')
            mol_sel.select_option(label=next(o for o in mol_sel.evaluate("e => [...e.options].map(o => o.text)")
                                             if o.startswith("Mol Kavramı")))
            page.wait_for_timeout(300)
            check("C3 konu seçilince satır işaretlendi", mol_cb.is_checked())
            page.screenshot(path=".shots/unlinked_tasks.png", full_page=True)
            page.locator('button:has-text("Seçilenleri konuya bağla")').click()
            page.wait_for_timeout(3000)
            rows = {r[0]: r for r in _task_rows(d["st"])}
            m, f = rows[d["t_mol"]], rows[d["t_fot"]]
            check("C4 tamamlanmış MOL görevi → Mol Kavramı 2/2", m[3] == "Mol Kavramı" and m[4] == 2 and m[5] == 2, str(m))
            check("C5 bekleyen fotosentez görevi → Fotosentez 2/0", f[3] == "Fotosentez" and f[5] == 0, str(f))
            check("C6 liste boşaldı (yenilemesiz)", page.locator('text=Konusuz test görevi yok').count() > 0)

            # ---- D: koyu tema + dar ekran
            dark = b.new_page(viewport={"width": 390, "height": 844}, color_scheme="dark")
            dark.context.add_cookies(page.context.cookies())
            with SessionLocal() as db:
                db.add(Task(student_id=d["st"], date=date.today(), type=TaskType.OTHER, title="Fizik · kuvvet",
                            notes="2 test", is_draft=False, status=TaskStatus.PENDING))
                db.commit()
            dark.goto(f"{WEB}/teacher/unlinked-tasks", wait_until="networkidle")
            dark.wait_for_timeout(2500)
            overflow = dark.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("D1 390px: yatay taşma yok", overflow <= 1, str(overflow))
            r = measure(dark, "main", 4.5)
            check("D2 koyu tema: okunmayan metin yok (4,5 eşiği)", r["bad"] == 0, str(r["worst"])[:300])
            dark.screenshot(path=".shots/unlinked_tasks_dark_mobile.png", full_page=True)
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
