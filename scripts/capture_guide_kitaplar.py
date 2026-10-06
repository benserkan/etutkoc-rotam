"""Rehber — KİTAPLAR serisi ekran yakalayıcı (gerçek panel, demo koç).

Rota Rehberi'nin "Kitaplar" konusunun sahneleri. Demo koç (seed_guide_demo,
Aylin Demir) hesabıyla GERÇEK akışlar yürütülür: katalogdan kitap ekleme,
kapak + içindekiler taraması (gerçek Gemini okuması), elle tanımlama, öğrenciye
atama, ilerleme düzeltme, koltuk ızgarası. Ekranlar 1440×900 görünümde, 2x
çözünürlükte çekilir (oynatıcı yakınlaştırınca yazılar keskin kalsın).

Önkoşul: :8081 + :3000 açık, seed_guide_demo koşulmuş.

  python -m scripts.capture_guide_kitaplar                 # tümü
  python -m scripts.capture_guide_kitaplar --only kutup,katalog
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

import scripts.capture_guide_shots as cgs

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "scripts" / "guide_assets"
IDS = cgs.IDS
CATALOG_BOOK = "Zoom Serisi 8. Sınıf Türkçe Soru Bankası"
SCAN_BOOK = "Kâşif Yayınları 8. Sınıf İngilizce Soru Bankası"
MANUAL_BOOK = "Koçluk Föyü — LGS Matematik Tekrar"


def hide_noise(page: Page) -> None:
    """Geliştirme rozetleri + Rota sohbet balonu kareye girmesin."""
    page.add_style_tag(
        content=(
            "nextjs-portal,[data-nextjs-toast],[class*='tsqd'],"
            "button[aria-label*='Rota asistan'],[aria-label='Rota asistanını aç'],"
            "section[aria-label^='Notifications']"
            "{display:none !important}"
        )
    )


def go(page: Page, path: str, wait_text: str | None = None) -> None:
    cgs.goto(page, path, wait_text)
    hide_noise(page)


def delete_books_named(page: Page, names: list[str]) -> None:
    """Önceki çekimden kalan kitapları API üzerinden sil (temiz tekrar)."""
    from app.database import SessionLocal
    from app.models import Book

    with SessionLocal() as db:
        rows = (
            db.query(Book.id, Book.name)
            .filter(Book.teacher_id == IDS["coach"], Book.name.in_(names))
            .all()
        )
    for bid, name in rows:
        # önce atamaları kaldır (rezervsiz) — sonra kitabı sil
        page.request.patch(
            f"{cgs.BASE}/api/v2/teacher/library/books/{bid}/assignments",
            data={"student_ids": []},
        )
        r = page.request.delete(f"{cgs.BASE}/api/v2/teacher/library/books/{bid}")
        print(f"  eski kitap silindi: {name} → {r.status}")


# ---------------------------------------------------------------- bölümler


def shots_kutuphane(page: Page) -> None:
    go(page, "/teacher/library", "Kütüphane")
    nav = page.locator("aside a[href='/teacher/library']").first
    cgs.snap(
        page,
        "k-kutuphane",
        {
            "nav": nav,
            "baslik": page.locator("h1:has-text('Kütüphane')").locator(".."),
            "rehber": page.get_by_text("eğitimini izle", exact=False).first.locator("xpath=ancestor::div[3]"),
            "yeni": page.get_by_role("link", name="Yeni kitap").first,
            "sekmeler": page.locator("nav[aria-label='Kütüphane bölümleri']"),
            "durum": page.get_by_text("henüz öğrenciye atanmamış").first.locator("xpath=ancestor::*[self::div or self::section][3]"),
            "suzgec": page.get_by_placeholder("Kitap veya yayınevi ara…").locator("xpath=ancestor::div[contains(@class,'rounded')][1]"),
        },
    )
    card = page.locator("a[href^='/teacher/library/books/']").first
    page.mouse.wheel(0, 420)
    time.sleep(0.8)
    cgs.snap(page, "k-kutuphane-kart", {"kart": card, "grup": page.get_by_text("kitap ·", exact=False).first})
    # eksiği olanlar süzgeci
    go(page, "/teacher/library?durum=eksik", "Kütüphane")
    issue = page.get_by_text("müfredata bağlı değil", exact=False).first
    cgs.snap(
        page,
        "k-kutuphane-eksik",
        {
            "durum": page.get_by_text("eksiği var", exact=False).first.locator("xpath=ancestor::button[1]"),
            "uyari": issue,
        },
    )
    go(page, "/teacher/library?view=list", "Kütüphane")
    page.mouse.wheel(0, 380)
    time.sleep(0.8)
    cgs.snap(page, "k-kutuphane-liste", {"tablo": page.locator("table").first})


def shots_katalog(page: Page) -> None:
    delete_books_named(page, [CATALOG_BOOK, "Zoom Serisi 8. Sınıf Paragraf Soru Bankası"])
    go(page, "/teacher/library/new", "Ne yapmak istiyorsun?")
    cgs.snap(
        page,
        "k-sihirbaz-yol",
        {
            "adimlar": page.get_by_text("Başlangıç", exact=True).first.locator("xpath=ancestor::ol[1] | ancestor::div[2]").first,
            "secenekler": page.get_by_text("Hazır bir kitap ekle").first.locator("xpath=ancestor::div[contains(@class,'grid')][1]"),
            "hazir": page.get_by_text("Hazır bir kitap ekle").first.locator("xpath=ancestor::button[1]"),
            "tarat": page.get_by_text("Kitabım elimde, tarat").first.locator("xpath=ancestor::button[1]"),
            "elle": page.get_by_text("Kitabı kendim tanımlayacağım").first.locator("xpath=ancestor::button[1]"),
        },
    )
    page.get_by_text("Hazır bir kitap ekle").first.click()
    page.get_by_text("Kitabını katalogda bul").first.wait_for(timeout=30_000)
    time.sleep(2.5)
    search = page.get_by_placeholder("Kitap adı ya da yayınevi yaz", exact=False).first
    cgs.snap(
        page,
        "k-katalog",
        {
            "gruplar": page.get_by_role("button", name="TYT", exact=False).first.locator(".."),
            "arama": search,
        },
    )
    search.fill("Zoom Türkçe")
    time.sleep(2.0)
    row = page.get_by_text(CATALOG_BOOK).first
    cgs.snap(page, "k-katalog-ara", {"arama": search, "satir": row.locator("xpath=ancestor::div[contains(@class,'rounded')][1]")})
    row.click()
    time.sleep(2.5)
    box = page.get_by_text(CATALOG_BOOK).first.locator(
        "xpath=ancestor::div[.//button[normalize-space()='Kütüphaneme ekle']][1]"
    )
    add_btn = box.get_by_role("button", name="Kütüphaneme ekle").first
    cgs.snap(
        page,
        "k-katalog-acik",
        {
            "bolumler": box,
            "ekle": add_btn,
        },
    )
    add_btn.click()
    page.get_by_text("2. Adım", exact=False).first.wait_for(timeout=60_000)
    time.sleep(2.0)
    devam = page.get_by_role("button", name="Devam", exact=False).first
    cgs.snap(page, "k-katalog-uniteler", {"hazir": page.get_by_text("ünite", exact=False).locator("xpath=ancestor::div[contains(@class,'rounded')][1]").first, "devam": devam})
    devam.click()
    page.get_by_text("3. Adım", exact=False).first.wait_for(timeout=60_000)
    time.sleep(2.0)
    nxt = page.get_by_role("button", name="Eşleştir ve devam").or_(page.get_by_role("button", name="Devam", exact=False)).first
    cgs.snap(page, "k-katalog-esles", {"devam": nxt})
    nxt.click()
    page.get_by_text("4. Adım", exact=False).first.wait_for(timeout=60_000)
    time.sleep(1.5)
    page.get_by_text("Elif Kaya").first.click()
    time.sleep(0.8)
    ata = page.get_by_role("button", name="ata ve bitir", exact=False).first
    cgs.snap(page, "k-katalog-ogrenci", {"liste": page.get_by_text("Elif Kaya").first.locator("xpath=ancestor::div[contains(@class,'rounded')][1]"), "ata": ata})
    ata.click()
    page.get_by_text("Kitap hazır", exact=False).first.wait_for(timeout=60_000)
    time.sleep(2.0)
    cgs.snap(page, "k-katalog-ozet", {"ozet": page.get_by_text("öğrenciye atalı", exact=False).first, "git": page.get_by_role("link", name="Kitaba git", exact=False).first})


def pick_by_text(sel, text, group_hint=None) -> bool:
    script = """(el, arg) => {
      const [text, hint] = arg;
      for (const o of Array.from(el.options)) {
        if (!o.text.includes(text)) continue;
        const g = o.parentElement && o.parentElement.tagName === 'OPTGROUP' ? o.parentElement.label : '';
        if (hint && !g.includes(hint)) continue;
        return o.value;
      }
      return null;
    }"""
    val = sel.evaluate(script, [text, group_hint])
    if val is not None:
        sel.select_option(val)
    return val is not None


def shots_tarat(page: Page) -> None:
    delete_books_named(page, [SCAN_BOOK, "8. SINIF İNGİLİZCE SORU BANKASI", "8. Sınıf İngilizce Soru Bankası"])
    go(page, "/teacher/library/new", "Ne yapmak istiyorsun?")
    page.get_by_text("Kitabım elimde, tarat").first.click()
    up = page.get_by_role("button", name="Fotoğraf ya da PDF seç").first
    up.wait_for(timeout=30_000)
    cgs.snap(page, "k-tarat-yol", {"yukle": up.locator("xpath=ancestor::div[contains(@class,'rounded')][1]")})
    page.locator("input[type=file]").first.set_input_files(
        [str(ASSETS / "kapak.jpg"), str(ASSETS / "icindekiler.jpg")]
    )
    time.sleep(2.0)
    cgs.snap(page, "k-tarat-isleniyor", {"durum": page.get_by_text("Kapak tanınıyor", exact=False).first}, settle=0.3)
    page.get_by_text("içindekilerden", exact=False).first.wait_for(timeout=240_000)
    time.sleep(2.5)
    bar = page.get_by_text("içindekilerden", exact=False).first
    cgs.snap(page, "k-tarat-sonuc", {"bar": bar})
    subj = page.locator("#cb-subject")
    subj.scroll_into_view_if_needed()
    pick_by_text(subj, "İngilizce", "LGS")
    time.sleep(0.6)
    olustur = page.get_by_role("button", name="Oluştur ve bölümlere geç").first
    olustur.scroll_into_view_if_needed()
    cgs.snap(page, "k-tarat-form", {"olustur": olustur, "form": subj.locator("xpath=ancestor::form[1]")})
    olustur.click()
    page.get_by_text("2. Adım", exact=False).first.wait_for(timeout=60_000)
    note = page.get_by_text("test sayısı tahmini", exact=False).first
    note.wait_for(timeout=60_000)
    time.sleep(2.0)
    cgs.snap(page, "k-tarat-tahmini", {"not": note.locator("xpath=ancestor::div[1]")})
    counts = page.get_by_label("Test sayısı")
    counts.first.fill("5")
    time.sleep(0.6)
    tumu = page.get_by_label("Tümüne uygulanacak test sayısı")
    tumu.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(
        page,
        "k-tarat-duzelt",
        {
            "satir": counts.first.locator("xpath=ancestor::*[self::li or self::div][1]"),
            "tumu": tumu.locator("xpath=ancestor::div[1]"),
        },
    )
    ekle = page.get_by_role("button", name="bölümü kitaba ekle", exact=False).first
    ekle.click()
    time.sleep(2.5)
    page.get_by_role("button", name="Devam", exact=False).first.click()
    page.get_by_text("3. Adım", exact=False).first.wait_for(timeout=60_000)
    page.wait_for_function("() => !document.body.innerText.includes('Eşleştiriliyor')", timeout=120_000)
    time.sleep(2.0)
    table = page.locator("table").first
    cgs.snap(page, "k-tarat-esles", {"tablo": table})
    page.get_by_role("button", name="Yapay zekâ ile öner").first.click()
    time.sleep(3)
    page.wait_for_function("() => !document.body.innerText.includes('Eşleştiriliyor') && !document.body.innerText.includes('öneriliyor')", timeout=180_000)
    time.sleep(3)
    cgs.snap(page, "k-tarat-esles-ai", {"tablo": table})
    page.get_by_role("button", name="Eşleştir ve devam").first.click()
    page.get_by_text("4. Adım", exact=False).first.wait_for(timeout=60_000)
    time.sleep(2.0)
    kat = page.get_by_text("ortak kataloğa öner", exact=False).first
    cgs.snap(page, "k-tarat-ogrenci", {"katalog": kat.locator("xpath=ancestor::label[1]")})
    # Kataloğa öneriyi gönderme (demo) — kutuyu kaldır, atlamadan Mert'e ata
    try:
        kat.locator("xpath=ancestor::label[1]").locator("input[type=checkbox]").uncheck()
    except Exception:
        pass
    page.get_by_role("button", name="Atla").first.click()
    time.sleep(2)


def shots_elle(page: Page) -> None:
    delete_books_named(page, [MANUAL_BOOK])
    go(page, "/teacher/library/new", "Ne yapmak istiyorsun?")
    page.get_by_text("Kitabı kendim tanımlayacağım").first.click()
    name = page.locator("input").filter(has=page.locator("xpath=.")).first
    page.get_by_label("Kitap adı").fill(MANUAL_BOOK)
    page.get_by_text("LGS (5-8)", exact=False).first.click()
    time.sleep(1.0)
    subj = page.locator("#cb-subject")
    pick_by_text(subj, "Matematik", "LGS")
    time.sleep(0.6)
    form = subj.locator("xpath=ancestor::form[1]")
    cgs.snap(page, "k-elle-form", {"form": form})
    subj.evaluate("el => { el.size = 14; }")
    time.sleep(0.8)
    cgs.snap(page, "k-elle-ders", {"liste": subj})
    subj.evaluate("el => { el.size = 0; }")
    page.get_by_role("button", name="Oluştur ve devam").first.click()
    page.get_by_text("2. Adım", exact=False).first.wait_for(timeout=60_000)
    time.sleep(2.0)
    cgs.snap(page, "k-elle-yontem", {"yontemler": page.get_by_text("Fotoğraftan oku").first.locator("xpath=ancestor::div[contains(@class,'grid')][1]")})
    page.get_by_text("Resmi konulardan ekle").first.click()
    time.sleep(2.0)
    panel = page.get_by_text("Sınıf seç", exact=False).first.locator("xpath=ancestor::div[contains(@class,'rounded')][1]")
    cgs.snap(page, "k-elle-resmi", {"panel": panel})
    page.get_by_role("button", name="konuyu ekle", exact=False).first.click()
    time.sleep(3.0)
    page.get_by_role("button", name="Devam", exact=False).first.click()
    page.get_by_text("3. Adım", exact=False).first.wait_for(timeout=60_000)
    time.sleep(2.0)
    cgs.snap(page, "k-elle-esles", {"mesaj": page.get_by_text("3. Adım", exact=False).first.locator("xpath=ancestor::div[1]")})


# ---------------------------------------------------------------- veri hazırlığı


def ensure_week_state(page: Page) -> None:
    """Elif için bu haftanın programı + rezervli görevler (sarı koltuk)."""
    from datetime import date, timedelta

    from app.database import SessionLocal
    from app.models import Task, WeeklyProgram

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sid = IDS["elif"]
    with SessionLocal() as db:
        has_prog = (
            db.query(WeeklyProgram)
            .filter(
                WeeklyProgram.student_id == sid,
                WeeklyProgram.start_date <= today,
                WeeklyProgram.end_date >= today,
            )
            .first()
        )
        has_task = db.query(Task).filter(Task.student_id == sid, Task.date >= monday).count()
    if not has_prog:
        r = page.request.post(
            f"{cgs.BASE}/api/v2/teacher/students/{sid}/programs",
            data={
                "start_date": monday.isoformat(),
                "end_date": (monday + timedelta(days=6)).isoformat(),
                "allow_overlap": True,
            },
        )
        print(f"  program açıldı → {r.status}")
    if not has_task:
        for d, sec, n in [(today, 1076, 3), (today + timedelta(days=1), 1080, 2)]:
            r = page.request.post(
                f"{cgs.BASE}/api/v2/teacher/students/{sid}/tasks",
                data={
                    "date": d.isoformat(),
                    "type": "test",
                    "title": "Görev",
                    "is_draft": False,
                    "items": [{"book_id": IDS["book"], "section_id": sec, "planned_count": n}],
                },
            )
            print(f"  görev {d} → {r.status}")


def ensure_student_declaration() -> None:
    """Elif'in onay bekleyen bir bağımsız çalışma beyanı olsun."""
    import httpx

    from app.database import SessionLocal
    from app.models import StudentBook
    from app.models.self_study import SelfStudyEntry

    with SessionLocal() as db:
        sb = db.query(StudentBook).filter_by(student_id=IDS["elif"], book_id=IDS["book"]).first()
        pending = (
            db.query(SelfStudyEntry)
            .filter(SelfStudyEntry.student_id == IDS["elif"], SelfStudyEntry.status == "pending")
            .count()
        )
    if pending or not sb:
        return
    with httpx.Client(base_url="http://127.0.0.1:8081", timeout=30) as c:
        c.post("/api/v2/auth/login", json={"email": "rehber-elif@etutkoc.demo", "password": "RehberDemo2026!"})
        r = c.post(
            "/api/v2/student/self-study",
            json={
                "items": [{"student_book_id": sb.id, "section_id": 1081, "test_count": 4}],
                "note": "Hafta sonu dershanede Eşitsizlikler testlerini çözdüm.",
            },
        )
        print(f"  öğrenci beyanı → {r.status_code}")


def ensure_book_set(page: Page) -> int:
    from app.database import SessionLocal
    from app.models import Book, BookSet

    name = "8. Sınıf Paketi"
    with SessionLocal() as db:
        s = db.query(BookSet).filter_by(teacher_id=IDS["coach"], name=name).first()
        if s:
            return s.id
        books = [
            b.id
            for b in db.query(Book).filter(
                Book.teacher_id == IDS["coach"],
                Book.name.in_(
                    [
                        "3D LGS Matematik Soru Bankası",
                        "Karekök LGS Türkçe Soru Bankası",
                        "Sınav Yayınları LGS Fen Bilimleri Soru Bankası",
                        CATALOG_BOOK,
                    ]
                ),
            )
        ]
    r = page.request.post(
        f"{cgs.BASE}/api/v2/teacher/library/book-sets",
        data={
            "name": name,
            "notes": "8. sınıf LGS hazırlık kitapları",
            "target_grade_min": 8,
            "target_grade_max": 8,
        },
    )
    sid = r.json()["data"]["id"]
    page.request.post(f"{cgs.BASE}/api/v2/teacher/library/book-sets/{sid}/books", data={"book_ids": books})
    print(f"  kitap seti kuruldu #{sid}")
    return sid


# ---------------------------------------------------------------- kitap detayı


def shots_detay(page: Page) -> None:
    bid = IDS["book"]
    go(page, f"/teacher/library/books/{bid}", "Bölümler")
    cgs.snap(
        page,
        "k-detay",
        {
            "baslik": page.locator("main header").first,
            "satir": page.locator("main ul > li").first,
            "dugmeler": page.get_by_role("button", name="+ Bölüm ekle").locator(".."),
        },
    )
    page.get_by_role("button", name="Müfredata eşleştir").first.click()
    page.get_by_role("dialog").first.wait_for(timeout=20_000)
    time.sleep(3.0)
    cgs.snap(page, "k-detay-esles", {"tablo": page.get_by_role("dialog").locator("table").first})
    page.keyboard.press("Escape")
    time.sleep(0.8)
    page.get_by_role("button", name="Dersi değiştir").first.click()
    time.sleep(1.2)
    cgs.snap(page, "k-detay-ders", {"pencere": page.get_by_role("dialog").first})
    page.keyboard.press("Escape")
    time.sleep(0.6)
    from app.database import SessionLocal
    from app.models import Book

    with SessionLocal() as db:
        palme = db.query(Book.id).filter(Book.teacher_id == IDS["coach"], Book.name.like("Palme%")).scalar()
    go(page, f"/teacher/library/books/{palme}", "Bölümler")
    cgs.snap(
        page,
        "k-detay-uyari",
        {"uyari": page.get_by_text("henüz hiçbir öğrenciye atanmadı").first.locator("xpath=ancestor::div[2]")},
    )
    page.get_by_role("tab", name="Şablon").first.click()
    time.sleep(1.5)
    cgs.snap(
        page,
        "k-detay-sablon",
        {"panel": page.locator("[role='tablist'][aria-label='Kitap sekmeleri']").locator("xpath=following-sibling::*[1]")},
    )


# ---------------------------------------------------------------- atama + ilerleme


def open_student_books(page: Page) -> None:
    go(page, f"/teacher/students/{IDS['elif']}#books", None)
    page.locator("[data-section='books-panel']").first.wait_for(timeout=30_000)
    time.sleep(2.5)


def shots_ata(page: Page) -> None:
    set_id = ensure_book_set(page)
    open_student_books(page)
    panel = page.locator("[data-section='books-panel']").first
    ata = page.get_by_test_id("open-assign").first
    panel.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "k-ogr-kitaplar", {"panel": panel.locator("xpath=./div[1]"), "ata": ata})
    ata.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=20_000)
    time.sleep(2.0)
    cgs.snap(
        page,
        "k-ata-pencere",
        {
            "suzgec": page.get_by_test_id("assign-search").locator("xpath=ancestor::div[contains(@class,'space-y-2')][1]"),
            "liste": dlg.locator("ul").first,
        },
    )
    rows = page.get_by_test_id("assign-row")
    for i in range(min(2, rows.count())):
        rows.nth(i).locator("input[type=checkbox]").first.check()
        time.sleep(0.3)
    time.sleep(0.8)
    cgs.snap(page, "k-ata-secili", {"alt": page.get_by_test_id("assign-submit")})
    dlg.get_by_role("tab", name="Set'ten uygula").first.click()
    time.sleep(1.5)
    pick_by_text(dlg.locator("select").first, "8. Sınıf Paketi")
    time.sleep(2.0)
    cgs.snap(page, "k-ata-set", {"panel": dlg.locator("[role='tablist']").locator("xpath=following-sibling::*[1]")})
    page.keyboard.press("Escape")
    time.sleep(0.6)
    go(page, "/teacher/library/book-sets", "8. Sınıf Paketi")
    cgs.snap(page, "k-setler", {"liste": page.get_by_role("link", name="8. Sınıf Paketi").first.locator("xpath=ancestor::div[contains(@class,'rounded')][1]")})
    go(page, f"/teacher/library/book-sets/{set_id}", "8. Sınıf Paketi")
    page.get_by_role("button", name="Öğrenci seç ve uygula").first.click()
    time.sleep(2.5)
    cgs.snap(page, "k-set-uygula", {"pencere": page.get_by_role("dialog").first})
    page.keyboard.press("Escape")


def shots_ilerleme(page: Page) -> None:
    ensure_student_declaration()
    open_student_books(page)
    ov = page.get_by_test_id("books-overview").first
    ov.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "k-ogr-ozet", {"ozet": ov})
    card = page.locator("[data-testid='book-card']").filter(has_text="3D LGS Matematik").first
    card.scroll_into_view_if_needed()
    time.sleep(0.8)
    cgs.snap(
        page,
        "k-ogr-kart",
        {
            "sirada": card.get_by_text("Sıradaki:", exact=False).first.locator(".."),
            "dugmeler": card.get_by_role("button", name="Arşivle").locator(".."),
        },
    )
    card.get_by_role("button", name="Üniteler", exact=False).first.click()
    time.sleep(1.0)
    secs = card.locator("[data-testid='book-section']")
    secs.nth(2).scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "k-ogr-uniteler", {"liste": card.locator("ul").first})
    target = secs.filter(has_text="Veri Analizi").first
    target.scroll_into_view_if_needed()
    target.get_by_role("button").first.click()
    time.sleep(0.6)
    cgs.snap(page, "k-ogr-zaten", {"editor": target})
    target.locator("input[type=number]").first.fill("0")
    time.sleep(0.6)
    cgs.snap(page, "k-ogr-azalt", {"ipucu": target.get_by_text("gerçek sayıyı yaz", exact=False).first})
    target.get_by_role("button", name="İptal").first.click()
    time.sleep(0.5)
    ss = page.get_by_text("Bağımsız çalışma", exact=True).first.locator(
        "xpath=ancestor::div[contains(@class,'rounded-xl')][1]"
    )
    ss.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "k-bagimsiz-beyan", {"beyan": ss})
    ss.get_by_role("button", name="Giriş yap").first.click()
    time.sleep(1.5)
    dlg = page.get_by_role("dialog").first
    try:
        dlg.locator("select").first.select_option(index=1)
        time.sleep(1.0)
    except Exception:  # noqa: BLE001
        pass
    cgs.snap(page, "k-bagimsiz", {"pencere": dlg})
    page.keyboard.press("Escape")


# ---------------------------------------------------------------- kapasite + koltuk


def open_week(page: Page) -> None:
    go(page, f"/teacher/students/{IDS['elif']}/week", "Kaynak Durumu")
    time.sleep(2.5)


def shots_kapasite(page: Page) -> None:
    ensure_week_state(page)
    open_week(page)
    page.get_by_text("Yeni görev ekle").first.click()
    time.sleep(1.2)
    page.get_by_role("button", name="Ayrıntılı form").first.click()
    time.sleep(1.2)
    form = page.locator("form").filter(has=page.get_by_text("Ünite / Deneme")).first
    sels = form.locator("select")
    pick_by_text(sels.nth(0), "Matematik")
    time.sleep(1.2)
    pick_by_text(sels.nth(1), "3D LGS Matematik")
    time.sleep(1.5)
    pick_by_text(sels.nth(2), "Çarpanlar ve Katlar")
    time.sleep(0.8)
    form.locator("input[type=number]").last.fill("3")
    time.sleep(0.8)
    warn = form.get_by_text("aşılacak", exact=False).first.locator("xpath=ancestor::p[1]")
    warn.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "k-kapasite", {"uyari": warn})

    open_week(page)
    side = page.locator("[data-section]").filter(has_text="Kaynak Durumu").filter(
        has=page.get_by_role("button", name="Sinema-koltuğu görünümü")
    )
    grid_btn = page.get_by_role("button", name="Sinema-koltuğu görünümü").first
    if not grid_btn.is_visible():
        page.get_by_role("button", name="Matematik", exact=False).last.click()
        time.sleep(1.2)
    grid_btn.scroll_into_view_if_needed()
    time.sleep(0.5)
    cgs.snap(page, "k-kaynak-durumu", {"izgara": grid_btn})
    grid_btn.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=20_000)
    time.sleep(2.5)
    cgs.snap(page, "k-koltuk", {"sayaclar": dlg.locator("xpath=./*[1]")})
    green = dlg.locator("button[title*='tarihinde çözüldü']").first
    green.scroll_into_view_if_needed()
    green.click()
    time.sleep(1.0)
    strip = dlg.locator("[data-section='book-grid:revert-strip']").first
    cgs.snap(page, "k-koltuk-yesil", {"serit": strip})
    strip.get_by_role("button", name="Kapat").first.click()
    time.sleep(0.5)
    yellow = dlg.locator("button[title*='tarihli görevde rezerve']").first
    yellow.scroll_into_view_if_needed()
    yellow.click()
    time.sleep(1.0)
    cgs.snap(page, "k-koltuk-sari", {"serit": dlg.locator("[data-section='book-grid:revert-strip']").first})
    page.keyboard.press("Escape")
    del side


# ---------------------------------------------------------------- şablonlar


def shots_sablon(page: Page) -> None:
    go(page, "/teacher/library/templates", None)
    time.sleep(1.5)
    cgs.snap(page, "k-sablonlar", {"liste": page.locator("main").first})
    go(page, "/teacher/library/task-templates", None)
    time.sleep(1.5)
    form = page.get_by_text("Yeni görev şablonu").first.locator("xpath=ancestor::div[contains(@class,'rounded')][1]")
    try:
        form.get_by_placeholder("Örn. Günlük 20 matematik").fill("Günlük Matematik — 20 test")
        sels = form.locator("select")
        pick_by_text(sels.nth(1), "3D LGS Matematik")
        time.sleep(1.2)
        pick_by_text(sels.nth(2), "Kareköklü")
        time.sleep(0.5)
        form.locator("input[type=number]").first.fill("20")
    except Exception as e:  # noqa: BLE001
        print(f"  form doldurma: {e}")
    time.sleep(0.8)
    cgs.snap(page, "k-gorev-sablon", {"form": form})


SECTIONS = {
    "kutup": shots_kutuphane,
    "katalog": shots_katalog,
    "tarat": shots_tarat,
    "elle": shots_elle,
    "detay": shots_detay,
    "ata": shots_ata,
    "ilerleme": shots_ilerleme,
    "kapasite": shots_kapasite,
    "sablon": shots_sablon,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    only = args.only.split(",") if args.only else list(SECTIONS)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH},
            device_scale_factor=2,
            locale="tr-TR",
            color_scheme="light",
        )
        ctx.route("**/me/panel-visits", lambda r: r.fulfill(status=204, body=""))
        page = ctx.new_page()
        cgs.ensure_guide_dismissed()
        cgs.login(page)
        for name in only:
            print(f"\n== {name}")
            try:
                SECTIONS[name](page)
            except Exception as e:  # noqa: BLE001 — devam et, raporla
                print(f"  ✗ {name}: {e}")
                cgs.SHOTS_DIR.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(cgs.SHOTS_DIR / f"_hata_{name}.png"))
        browser.close()

    data = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8")) if cgs.BOXES_PATH.exists() else {}
    data.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nKutular yazıldı: {len(cgs.boxes_out)} ekran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
