"""Canlı test — müfredat sekmesi ODAK SINIF (2026-10-14).

Koç kuralı: 9-10-11 (ve LGS 5-8) öğrencide müfredat haritası İÇİNDE BULUNULAN sınıfa göre hesaplanır
ve önde görünür; önceki sınıflar ayrı sayılır ve katlı gelir. 12/mezunda kümülatif.

Gerçek tarayıcı (dev :3000 + :8081). Kendi koç/öğrencilerini kurar, sonunda siler.
  python scripts/live_curriculum_focus_grade.py
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Track, User, UserRole  # noqa: E402
from app.models.topic_closure import TopicClosure  # noqa: E402
from app.services import curriculum_progress as cp  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lcfg_{secrets.token_hex(3)}"
PWD = "LiveFocusGrade!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"Odak {tag}",
             role=role, is_active=True, must_change_password=False, **kw)
    db.add(u)
    db.flush()
    return u


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "koc", UserRole.TEACHER)
        st11 = _user(db, "on1", UserRole.STUDENT, teacher_id=coach.id, grade_level=11, track=Track.SAYISAL)
        st12 = _user(db, "on2", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                     entry_year_grade9=2023)
        subs = cp._applicable_subjects(db, st11, coach.id)
        fiz = next(s for s in subs if s.name == "Fizik")
        leaves = cp.leaf_topics_for_student(db, st11, coach.id, [fiz.id]).by_subject[fiz.id]
        g11 = [t for t in leaves if t.grade_level == 11]
        g9 = [t for t in leaves if t.grade_level == 9]
        # 11. sınıftan 2, 9. sınıftan 1 konu kapat (koç kararı = işlendi + tamam)
        for t in (g11[0], g11[1], g9[0]):
            db.add(TopicClosure(student_id=st11.id, topic_id=t.id, closed_by_id=coach.id))
        db.commit()
        return {"coach": coach.id, "st11": st11.id, "st12": st12.id, "email": coach.email,
                "fiz_total11": len(g11), "fiz_prior": len(leaves) - len(g11),
                "g11a": g11[0].id, "g9a": g9[0].id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st11"], d["st12"], d["coach"]]
        db.execute(sa_delete(TopicClosure).where(TopicClosure.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


TEXT = "(sel) => { const el = document.querySelector(sel); return el ? el.textContent : ''; }"
OVERFLOW_JS = "() => document.documentElement.scrollWidth > window.innerWidth + 1"


def goto(page, sid):
    page.goto(f"{WEB}/teacher/students/{sid}#curriculum", wait_until="networkidle")
    page.reload(wait_until="networkidle")
    page.wait_for_selector('[data-section="curriculum-panel"]', timeout=30000)
    later = page.query_selector('button:has-text("Daha sonra")')
    if later:
        later.click()
        page.wait_for_timeout(400)


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    print(f"\n=== Müfredat odak sınıf — canlı ({PFX}) ===\n")
    try:
        # servis düzeyi
        with SessionLocal() as db:
            r = cp.compute_curriculum_progress(db, db.get(User, d["st11"]), d["coach"])
            fz = next(s for s in r.subjects if s.name == "Fizik")
            check("S1 odak sınıf 11", r.focus_grade == 11, str(r.focus_grade))
            check("S2 Fizik: odak 2/N girildi, önceki 1/M",
                  fz.started_topics == 2 and fz.total_topics == d["fiz_total11"]
                  and fz.prior_started_topics == 1 and fz.prior_total_topics == d["fiz_prior"],
                  f"{fz.started_topics}/{fz.total_topics} · {fz.prior_started_topics}/{fz.prior_total_topics}")
            r12 = cp.compute_curriculum_progress(db, db.get(User, d["st12"]), d["coach"])
            # 2026-10-15: 12. sınıf da odaklı (TYT/AYT dersinde dersin tüm konuları), hedef eğitim yılı sonu
            check("S3 12. sınıf → odak 12 · TYT/AYT tüm konular · hedef eğitim yılı sonu",
                  r12.focus_grade == 12 and r12.overall_total_topics == r12.cumulative_total_topics
                  and r12.projection.target_kind == "okul_yili_sonu")
            check("S4 11. sınıf projeksiyonu: hedef 15 Haziran, kalan = 11. sınıf konuları",
                  r.projection.target_kind == "okul_yili_sonu"
                  and r.projection.remaining_topics == r.overall_total_topics - r.overall_started_topics,
                  str(r.projection))

        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 1000})
            page = ctx.new_page()
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', d["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            goto(page, d["st11"])

            panel = page.evaluate(TEXT, '[data-section="curriculum-panel"]')
            check("1a başlık '11. sınıf müfredatı' + 'bu yıl' + 'Eğitim yılı sonuna yetişme'",
                  "11. sınıf müfredatı" in panel and "bu yıl" in panel and "Eğitim yılı sonuna yetişme" in panel)
            strip = page.evaluate(TEXT, '[data-section="curriculum:grades"]')
            check("1b sınıf şeridi: 11 · bu yıl, 10, 9 + Toplam",
                  "11. sınıf · bu yıl" in strip and "10. sınıf" in strip and "9. sınıf" in strip
                  and "Toplam" in strip, strip[:200])

            page.locator('[data-testid="curriculum-subject"]', has_text="Fizik").first.click()
            page.wait_for_timeout(500)
            card = page.locator('[data-testid="curriculum-subject"]', has_text="Fizik").first.text_content()
            check("2a Fizik kartı: '11. sınıf:' + 'önceki sınıflar: 1/…'",
                  "11. sınıf:" in card and "önceki sınıflar: 1/" in card, card)

            heads = page.locator('[data-testid="curriculum-detail"] [data-section="curriculum:grade"] > button')
            labels = [heads.nth(i).text_content() for i in range(heads.count())]
            check("3a bölüm sırası: 11 (bu yıl) → 10 → 9",
                  len(labels) == 3 and labels[0].startswith("11. Sınıf · bu yıl")
                  and labels[1].startswith("10.") and labels[2].startswith("9."), str(labels))
            exp = [heads.nth(i).get_attribute("aria-expanded") for i in range(heads.count())]
            check("3b yalnız bu yıl açık, önceki sınıflar katlı", exp == ["true", "false", "false"], str(exp))
            check("3c 11. sınıf konusu görünür, 9. sınıf konusu gizli",
                  page.query_selector(f'[data-topic-id="{d["g11a"]}"]') is not None
                  and page.query_selector(f'[data-topic-id="{d["g9a"]}"]') is None)
            heads.nth(2).click()
            page.wait_for_timeout(300)
            check("3d 9. sınıf açılınca konusu görünür",
                  page.query_selector(f'[data-topic-id="{d["g9a"]}"]') is not None)
            heads.nth(0).click()
            page.wait_for_timeout(300)
            check("3e bu yıl katlanabilir",
                  page.query_selector(f'[data-topic-id="{d["g11a"]}"]') is None)
            page.locator('[data-testid="curriculum-detail"] [role="tab"]', has_text="Tamamlandı").click()
            page.wait_for_timeout(300)
            check("3f durum filtresi seçilince tüm sınıflar açık (3 tamamlanan görünür)",
                  page.locator('[data-testid="curriculum-topic"]').count() == 3)
            check("3g yatay taşma yok", not page.evaluate(OVERFLOW_JS))
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_focus_grade.png"), full_page=True)

            # koyu tema kontrast — bölüm başlıkları + şerit
            page.emulate_media(color_scheme="dark")
            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.locator('[data-testid="curriculum-detail"] [role="tab"]', has_text="Tümü").click()
            page.wait_for_timeout(400)
            bad = []
            for sel in ('[data-section="curriculum:grades"]', '[data-testid="curriculum-detail"]'):
                res = measure(page, sel, 4.5)
                bad += res.get("worst", []) if res.get("bad") else []
            check("4 koyu tema kontrast 4,5", not bad, str(bad[:4]))
            page.screenshot(path=os.path.join(SHOT_DIR, "curriculum_focus_grade_dark.png"), full_page=True)

            # 11. sınıf analitik: yalnız eğitim yılı sonu müfredat kartı, sınav kartı yok
            page.goto(f"{WEB}/teacher/students/{d['st11']}#analytics", wait_until="networkidle")
            page.reload(wait_until="networkidle")
            page.wait_for_selector('[data-section="analytics:readiness"]', timeout=30000)
            rd = page.evaluate(TEXT, '[data-section="analytics:readiness"]')
            check("6 11. sınıf analitik: 'Bu yılın müfredatına yetişme' + 15 Haziran, sınav kartı YOK",
                  "Bu yılın müfredatına yetişme" in rd and "15 Haziran" in rd and "Sınava hazırlık" not in rd, rd[:300])
            # 12. sınıf: odak yok, şeritte 'bu yıl' yok
            page.emulate_media(color_scheme="light")
            page.evaluate("() => document.documentElement.classList.remove('dark')")
            goto(page, d["st12"])
            panel12 = page.evaluate(TEXT, '[data-section="curriculum-panel"]')
            check("5 12. sınıf (TYT/AYT): 'TYT / AYT müfredatı · bu yıl' + 'Eğitim yılı sonuna yetişme'",
                  "TYT / AYT müfredatı" in panel12 and "bu yıl" in panel12
                  and "Eğitim yılı sonuna yetişme" in panel12, panel12[:300])
            b.close()
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed · {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
