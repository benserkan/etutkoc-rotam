"""Öğrenci listesi (yeni tasarım) — canlı tarayıcı testi (2026-09-28).

Kendi verisini kurar/temizler: koç + farklı durumlarda 7 öğrenci (kritik,
uyarı, yolunda, molada, talep bekleyen, pasif, uzun adlı). Dev sunucular
(:3000 + :8081) açık olmalı. Ekran görüntüleri .shots/students_list_*.png
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Task, TaskStatus, TaskType, User, UserRole
from app.models.task_request import RequestStatus, RequestType, TaskRequest
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

BASE = "http://localhost:3000"
PFX = f"lsl_{secrets.token_hex(3)}"
PWD = "LiveStudList!234"
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


# ad, sınıf, şube, profil
PROFILES = [
    ("Ayşe Yıldırım", 10, "10-A", "ok"),
    ("Burak Demir", 10, "10-A", "half"),
    ("Ceren Kaya", 11, "11-B", "none"),
    ("Deniz Arslan", 8, None, "ok_paused"),
    ("Gamze Elif Seda Tarı Uzunsoyadlıoğlu", 12, "12-Sayısal", "half_request"),
    ("Emre Pasif", 9, None, "inactive"),
    ("Mezun Merve Şahin", None, None, "ok"),
]


def seed() -> dict:
    now = datetime.now(timezone.utc)
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Liste Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_unlimited", subscription_status="active")
        db.add(coach)
        db.flush()
        ids = []
        for i, (name, grade, grp, prof) in enumerate(PROFILES):
            u = User(email=f"{PFX}_{i}@test.invalid", password_hash=hash_password(PWD),
                     full_name=name, role=UserRole.STUDENT, teacher_id=coach.id,
                     grade_level=grade, is_graduate=grade is None, class_group=grp,
                     is_active=prof != "inactive", is_paused=prof == "ok_paused",
                     created_at=now - timedelta(days=40),
                     last_login_at=(now if prof.startswith("ok") else
                                    now - timedelta(days=3) if prof.startswith("half") else None))
            db.add(u)
            db.flush()
            ids.append(u.id)
            if prof == "none":
                continue
            for d in range(0, 8):
                day = today - timedelta(days=d)
                for k in range(2):
                    done = prof.startswith("ok") or (prof.startswith("half") and k == 0 and d % 2 == 0)
                    if d == 0 and k == 1:
                        done = False
                    db.add(Task(student_id=u.id, date=day, type=TaskType.OTHER,
                                title=f"Paragraf rutini {k + 1}", is_draft=False,
                                published_at=now, order=k,
                                status=TaskStatus.COMPLETED if done else TaskStatus.PENDING,
                                completed_at=now if done else None))
            if prof == "half_request":
                db.add(TaskRequest(student_id=u.id, teacher_id=coach.id, type=RequestType.QUESTION,
                                   status=RequestStatus.PENDING, message="Bu hafta çok yoğun, konuşabilir miyiz?"))
        db.commit()
        return {"coach": coach.id, "email": coach.email, "ids": ids}


def cleanup(d):
    with SessionLocal() as db:
        db.execute(sa_delete(TaskRequest).where(TaskRequest.student_id.in_(d["ids"])))
        db.execute(sa_delete(Task).where(Task.student_id.in_(d["ids"])))
        db.execute(sa_delete(User).where(User.id.in_(d["ids"] + [d["coach"]])))
        db.commit()


def no_overflow(pg) -> bool:
    return not pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")


def truncated(pg) -> list[str]:
    return pg.evaluate("""() => [...document.querySelectorAll('li.group *')].filter(e =>
        e.children.length === 0 && e.textContent.trim() &&
        (getComputedStyle(e).textOverflow === 'ellipsis' || e.scrollWidth > e.clientWidth + 1) &&
        getComputedStyle(e).overflow !== 'visible').map(e => e.textContent.trim()).slice(0, 5)""")


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1400, "height": 1000})
            pg = ctx.new_page()
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/students", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(500)

            api = pg.request.get(f"{BASE}/api/v2/teacher/students?status=aktif").json()
            s = api.get("summary", {})
            print("  özet:", s, [(i["full_name"], i["risk_level"]) for i in api["items"]])
            chk("1 özet: 6 aktif öğrenci 3 kutuya dağılır", s.get("critical", 0) + s.get("warning", 0) + s.get("ok", 0) == 6, str(s))
            chk("2 özet: 1 molada · 1 bekleyen talep", s.get("paused") == 1 and s.get("pending_requests") == 1, str(s))
            chk("3 satır sayısı 6 (pasif gizli)", pg.locator("li.group").count() == 6)
            ayse = next(i for i in api["items"] if i["full_name"] == "Ayşe Yıldırım")
            chk("3b son 7 gün görev bazlı: Ayşe 13/14", (ayse.get("week_gorev_done"), ayse.get("week_gorev_total")) == (13, 14),
                str((ayse.get("week_gorev_done"), ayse.get("week_gorev_total"))))
            row_txt = pg.locator("li.group").filter(has_text="Ayşe Yıldırım").inner_text()
            chk("3c satırda %93 görünür", "%93" in row_txt, row_txt)
            misalign = pg.evaluate("""() => {
                const head = [...document.querySelectorAll('section > div.md\\\\:grid > *')].map(e => e.getBoundingClientRect().left);
                const row = document.querySelector('li.group');
                const cells = [...row.children].filter(e => getComputedStyle(e).position !== 'absolute');
                const flat = cells.flatMap(e => getComputedStyle(e).display === 'contents' ? [...e.children] : [e]);
                return head.slice(1, 5).map((x, i) => Math.round(Math.abs(x - flat[i + 1].getBoundingClientRect().left)));
            }""")
            chk("3d başlıklar sütunlarla hizalı", all(m <= 2 for m in misalign), str(misalign))
            chk("4 kutu sayısı ekranda", pg.get_by_test_id("status-tile-critical").inner_text().count(str(s.get("critical"))) >= 1)

            # Kutuya tıkla → süzgeç
            crit = s.get("critical", 0)
            pg.get_by_test_id("status-tile-critical").click()
            pg.wait_for_timeout(2000)
            chk("5 Kritik kutusu: liste = kutudaki sayı", pg.locator("li.group").count() == crit,
                f"{pg.locator('li.group').count()} vs {crit}")
            chk("6 URL risk=critical + çip", "risk=critical" in pg.url and pg.get_by_text("Etkin süzgeçler").count() == 1)
            chk("7 kritik satırlarda kırmızı şerit", pg.locator('li.group[data-risk="critical"]').count() == crit)
            pg.get_by_test_id("status-tile-critical").click()
            pg.wait_for_timeout(2000)
            chk("8 ikinci tık süzgeci kaldırır", pg.locator("li.group").count() == 6 and "risk=" not in pg.url)

            # Arama
            pg.get_by_label("Öğrenci ara").fill("gamze")
            pg.wait_for_timeout(2200)
            chk("9 arama", pg.locator("li.group").count() == 1)
            chk("10 talep rozeti", pg.get_by_text("talep bekliyor").count() == 1)
            pg.get_by_label("Öğrenci ara").fill("")
            pg.wait_for_timeout(2200)

            # Durum segmenti
            pg.get_by_role("radio", name="Pasif").click()
            pg.wait_for_timeout(2000)
            chk("11 Pasif sekmesi yalnız pasifi gösterir", pg.locator("li.group").count() == 1
                and "Emre Pasif" in pg.locator("li.group").first.inner_text())
            chk("12 pasifte özet kutuları gizli", pg.get_by_test_id("status-tiles").count() == 0)
            pg.get_by_role("radio", name="Aktif").click()
            pg.wait_for_timeout(2000)

            # Şube süzgeci
            pg.get_by_label("Şube filtresi").select_option("10-A")
            pg.wait_for_timeout(2000)
            chk("13 şube süzgeci 10-A → 2", pg.locator("li.group").count() == 2)
            pg.get_by_role("button", name="Tümünü temizle").click()
            pg.wait_for_timeout(2000)

            # Eylem menüsü (Radix)
            pg.locator("li.group").first.get_by_label("Öğrenci eylemleri").click()
            pg.wait_for_timeout(400)
            items = pg.get_by_role("menuitem").all_inner_texts()
            chk("14 menü: profil/program/talepler/şifre/sonlandır", len(items) == 5, str(items))
            pg.get_by_role("menuitem", name="Şifre sıfırla").click()
            pg.wait_for_timeout(500)
            chk("15 şifre sıfırlama penceresi açılır", pg.get_by_role("dialog").count() == 1)
            pg.get_by_role("button", name="Vazgeç").click()
            pg.wait_for_timeout(400)
            chk("16 pencere kapanınca sayfa tıklanabilir", pg.evaluate("getComputedStyle(document.body).pointerEvents") != "none")

            # Toplu şube
            pg.locator('[data-testid="student-select"]').nth(2).check()
            chk("17 toplu çubuk çıkar", pg.get_by_test_id("class-group-bar").count() == 1)
            pg.locator('[data-testid="class-group-bar"] input[aria-label="Şube adı"]').fill("11-C")
            pg.click('[data-testid="class-group-apply"]')
            pg.wait_for_timeout(2200)
            chk("18 şube atandı, çubuk kapandı", pg.get_by_text("11-C").count() >= 1
                and pg.get_by_test_id("class-group-bar").count() == 0)

            chk("19 kırpılmış metin yok", truncated(pg) == [], str(truncated(pg)))
            chk("20 masaüstünde yatay taşma yok", no_overflow(pg))
            pg.screenshot(path=os.path.join(SHOT_DIR, "students_list_light.png"), full_page=True)

            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(400)
            bad = measure(pg, '[data-testid="status-tiles"]', min_ratio=3.0)["bad"]
            chk("21 koyu tema kutu kontrastı", bad == 0, str(bad))
            bad = measure(pg, "li.group", min_ratio=3.0)["bad"]
            chk("22 koyu tema satır kontrastı", bad == 0, str(bad))
            pg.screenshot(path=os.path.join(SHOT_DIR, "students_list_dark.png"), full_page=True)
            pg.evaluate("() => document.documentElement.classList.remove('dark')")

            pg.set_viewport_size({"width": 390, "height": 844})
            pg.wait_for_timeout(700)
            chk("23 390px yatay taşma yok", no_overflow(pg))
            chk("24 390px kırpılmış metin yok", truncated(pg) == [], str(truncated(pg)))
            pg.screenshot(path=os.path.join(SHOT_DIR, "students_list_mobile.png"), full_page=True)
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
