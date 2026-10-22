"""Canlı — hızlı görev kutusu: birim/sayfa + seçimin formlar arası taşınması (2026-10-22).

  1 hızlı kutu: konu → "Kaynak belirtmeden ver" → birim seçici görünür
  2 sayfa + not + 45–50 → "Ekle · s. 45–50" → kayıt unit sayfa
  3 konu seç → soru · 20 → "ayrıntılı forma aktar" → form dolu (ders, kaynaksız, konu, soru, 20)
  4 "Hızlı eklemeye dön" → seçim + birim korunur
  5 "Bu konuyla: Özet" → Özet formu ders + konu dolu + "Müfredat konusuna bağlı" çipi → kayıt tasks.topic_id
  6 koyu tema kontrast + 390px taşma yok + konsol hatası yok
Ön koşul: backend :8081 + Next :3000.
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Task, TaskBookItem, User, UserRole  # noqa: E402
from app.services import curriculum_progress as cp  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lqas_{secrets.token_hex(3)}"
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


def seed():
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Kutu Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Kutu Öğrenci",
                 role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                 grade_level=8)
        db.add(s)
        db.flush()
        fen = (db.query(Subject).filter(Subject.name == "Fen Bilimleri", Subject.is_builtin.is_(True),
                                        Subject.curriculum_model == "lgs").first())
        topics = cp.leaf_topics_for_student(db, s, coach.id, [fen.id]).by_subject[fen.id]
        topic = next(t for t in topics if len(t.name) > 8)
        db.commit()
        return {"coach": coach.id, "s": s.id, "topic": topic.id, "tname": topic.name, "fen": fen.id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["s"], d["coach"]]
        tids = [t.id for t in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def open_box(page, d):
    page.goto(f"{WEB}/teacher/students/{d['s']}/week", wait_until="networkidle")
    page.wait_for_timeout(2500)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(800)
    for sel in ('text="Yeni görev ekle"', 'text="Görev ekle"'):
        el = page.query_selector(sel)
        if el:
            el.click()
            page.wait_for_timeout(1000)
            break


def pick_sourceless(page, d):
    box = page.locator('input[aria-label="Görev ara"]')
    box.click()
    box.fill(d["tname"])
    page.wait_for_timeout(1800)
    page.locator('button:has-text("Kaynak belirtmeden ver")').first.click()
    page.wait_for_timeout(500)


def last_task(d):
    with SessionLocal() as db:
        t = db.query(Task).filter(Task.student_id == d["s"]).order_by(Task.id.desc()).first()
        if t is None:
            return None, None
        return t, (t.book_items[0] if t.book_items else None)


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(".shots", exist_ok=True)
    d = seed()
    print(f"\n=== canlı: hızlı kutu birim + seçim taşıma — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 1000}, color_scheme="light")
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{PFX}_t@test.invalid")
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            # 1-2 hızlı kutuda sayfa görevi
            open_box(page, d)
            pick_sourceless(page, d)
            seg = page.locator('form[aria-label="Görev ekleme kutusu"] [role="radiogroup"][aria-label="Birim"]')
            check("1 kaynaksız seçimde birim seçici hızlı kutuda", seg.count() == 1)
            seg.locator('button:has-text("sayfa")').click()
            page.locator('input[aria-label="Kitap adı notu"]').fill("Hız Fen")
            page.locator('input[aria-label="Başlangıç sayfası"]').fill("45")
            page.locator('input[aria-label="Bitiş sayfası"]').fill("50")
            page.wait_for_timeout(400)
            btn = page.locator('form[aria-label="Görev ekleme kutusu"] button[type="submit"]')
            check("2a düğme 'Ekle · s. 45–50'", "s. 45–50" in btn.inner_text(), btn.inner_text())
            page.screenshot(path=".shots/quick_add_page_light.png")
            btn.click()
            page.wait_for_timeout(2500)
            t, it = last_task(d)
            check("2b kayıt: sayfa · s.45–50 · not Hız Fen",
                  it is not None and it.unit == "sayfa" and it.page_from == 45 and it.page_to == 50
                  and it.label == "Hız Fen" and t.title.endswith("(Hız Fen): s. 45–50"),
                  str(t and t.title))

            # 2c yeni kart düzeni: Ekle en altta (altbilgide), Kaynak satırı Ekle'den önce
            open_box(page, d)
            pick_sourceless(page, d)
            comp = page.locator('[data-section="quick-add:composer"]')
            yb = comp.locator('button[type="submit"]').bounding_box()
            yk = comp.locator('input[aria-label="Kitap adı notu"]').bounding_box()
            check("2c kartta birincil Ekle en altta (kaynak satırının altında)",
                  yb is not None and yk is not None and yb["y"] > yk["y"] + 20, f"{yb} {yk}")
            # 2d Saat · periyot kartın içinde → kayıtta periyot
            comp.locator('button:has-text("Saat · periyot")').click()
            comp.locator('[role="radiogroup"][aria-label="Periyot"] button:has-text("Akşam")').click()
            comp.locator('select[aria-label="Saat"]').select_option("20")
            comp.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            t, it = last_task(d)
            check("2d kart içinden periyot + saat kaydedildi",
                  t is not None and t.period == "evening" and t.scheduled_hour == 20,
                  str(t and (t.period, t.scheduled_hour)))

            # 3 seçim ayrıntılı forma taşınır
            open_box(page, d)
            pick_sourceless(page, d)
            seg = page.locator('form[aria-label="Görev ekleme kutusu"] [role="radiogroup"][aria-label="Birim"]')
            seg.locator('button:has-text("soru")').click()
            page.locator('[role="group"][aria-label="Miktar"] button:has-text("başka")').click()
            page.locator('input[aria-label="Soru sayısı"]').fill("20")
            page.click('button:has-text("Ayrıntılı forma aktar")')
            page.wait_for_timeout(1500)
            selects = page.locator("form select")
            subj_txt = selects.nth(0).locator("option:checked").inner_text()
            book_txt = selects.nth(1).locator("option:checked").inner_text()
            topic_txt = page.locator('button[aria-label="Müfredat konusu seç"]').inner_text()
            soru_on = page.locator('[data-section="task-form:sourceless-options"] button[role="radio"][aria-checked="true"]').inner_text()
            qty = page.locator('form input[aria-label="Soru sayısı"]').input_value()
            check("3 ayrıntılı form dolu: ders · kaynaksız · konu · soru · 20",
                  subj_txt.startswith("Fen Bilimleri") and "Kaynaksız" in book_txt and d["tname"] in topic_txt
                  and "Soru" in soru_on and qty == "20",
                  f"{subj_txt} | {book_txt} | {topic_txt} | {soru_on} | {qty}")
            page.screenshot(path=".shots/quick_add_handoff_detailed.png")

            # 4 geri dönüş
            page.click('button:has-text("Hızlı eklemeye dön")')
            page.wait_for_timeout(800)
            chip = page.locator('[data-testid="quick-add-picked"]')
            q2 = page.locator('input[aria-label="Soru sayısı"]')
            check("4 hızlı kutuya dönüşte seçim + soru · 20 korunur",
                  chip.count() == 1 and d["tname"] in chip.inner_text() and q2.count() == 1
                  and q2.input_value() == "20", chip.inner_text() if chip.count() else "yok")

            # 5 Bu konuyla: Özet
            types = page.locator('[data-section="quick-add:types"]')
            check("5a 'Bu konuyla:' etiketi + Deneme/Blok gizli",
                  "Bu konuyla" in types.inner_text() and "Deneme" not in types.inner_text(), types.inner_text())
            types.locator('button:has-text("Özet")').click()
            page.wait_for_timeout(1200)
            linked = page.locator('[data-section="task-form:linked-topic"]')
            ozet_val = page.locator('form input[placeholder^="Örn. Atatürk"]').input_value()
            o_subj = page.locator("form select").nth(0).locator("option:checked").inner_text()
            check("5b Özet formu: ders + konu metni + bağ çipi",
                  linked.count() == 1 and ozet_val == d["tname"] and o_subj.startswith("Fen Bilimleri"),
                  f"{o_subj} | {ozet_val}")
            page.screenshot(path=".shots/quick_add_ozet_linked.png")
            page.locator("form button[type=submit]").last.click()
            page.wait_for_timeout(2500)
            t, _ = last_task(d)
            check("5c kayıt: özet görevi tasks.topic_id = konu",
                  t is not None and (t.type.value if hasattr(t.type, "value") else t.type) == "ozet"
                  and t.topic_id == d["topic"], str(t and (t.type, t.topic_id)))

            # 6 koyu tema + dar ekran + konsol
            open_box(page, d)
            pick_sourceless(page, d)
            page.locator('form[aria-label="Görev ekleme kutusu"] [role="radiogroup"] button:has-text("sayfa")').click()
            page.emulate_media(color_scheme="dark")
            page.wait_for_timeout(700)
            res = measure(page, '[data-section="quick-add:composer"]', min_ratio=4.5)
            check("6a koyu tema: kutu metinleri okunur (4,5)", res["bad"] == 0, str(res["worst"][:3]))
            page.screenshot(path=".shots/quick_add_page_dark.png")
            page.set_viewport_size({"width": 390, "height": 900})
            page.wait_for_timeout(700)
            sw = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("6b 390px yatay taşma yok", sw <= 1, str(sw))
            page.screenshot(path=".shots/quick_add_page_mobile.png")
            check("6c konsol hatası yok", not errs, str(errs[:3]))
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
