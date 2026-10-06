"""Rehber — PROGRAM serisi ekran yakalayıcı (gerçek panel, demo koç).

Rota Rehberi'nin "Program" konusunun sahneleri. Demo koç (Aylin Demir) ile
Elif Kaya'nın haftalık programı GERÇEK akışlarla kurulur: yeni program, konu
arayarak görev ekleme, Kaynak Durumu ve Müfredat'tan görev, ızgarada taşıma /
kopyalama / haftaya yayma, iskelet ve öneriler, yayın + veliye duyuru, takip.
Ekranlar 1440×900, 2x çözünürlük.

Önkoşul: :8081 + :3000 açık, seed_guide_demo koşulmuş.

  python -m scripts.capture_guide_program                    # tümü (sırayla)
  python -m scripts.capture_guide_program --only sayfa,gorev
  python -m scripts.capture_guide_program --reset            # Elif'in bu+gelecek haftasını temizle
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
from datetime import date, timedelta

from playwright.sync_api import Page, sync_playwright

import scripts.capture_guide_shots as cgs
from scripts.capture_guide_kitaplar import go, hide_noise, pick_by_text

IDS = cgs.IDS
SID = IDS["elif"]
TODAY = date.today()
MONDAY = TODAY - timedelta(days=TODAY.weekday())
NEXT_MONDAY = MONDAY + timedelta(days=7)
WEEK_URL = f"/teacher/students/{SID}/week"


def iso(d: date) -> str:
    return d.isoformat()


# ---------------------------------------------------------------- veri


def reset_weeks(page: Page) -> None:
    """Elif'in bu hafta ve sonrasındaki görevlerini + gelecek programlarını sil."""
    from app.database import SessionLocal
    from app.models import Task, WeeklyProgram
    from app.models.weekly_skeleton import WeeklySkeleton

    with SessionLocal() as db:
        task_ids = [t.id for t in db.query(Task.id).filter(Task.student_id == SID, Task.date >= MONDAY)]
        progs = [
            (p.id, p.start_date)
            for p in db.query(WeeklyProgram).filter(WeeklyProgram.student_id == SID, WeeklyProgram.start_date >= MONDAY)
        ]
        skels = [s.id for s in db.query(WeeklySkeleton.id).filter(WeeklySkeleton.student_id == SID)]
    for tid in task_ids:
        page.request.delete(f"{cgs.BASE}/api/v2/teacher/tasks/{tid}")
    for pid, start in progs:
        page.request.post(
            f"{cgs.BASE}/api/v2/teacher/students/{SID}/programs/{pid}/delete",
            data={"delete_tasks": True},
        )
    for sk in skels:
        page.request.post(f"{cgs.BASE}/api/v2/teacher/students/{SID}/skeleton/delete", data={"skeleton_id": sk})
    # Önceki çekimlerden kalan hafta notu + serbest blok
    from app.models.coach_work_block import CoachWorkBlock
    from app.models.week_note import WeekNote

    with SessionLocal() as db:
        db.query(WeekNote).filter(WeekNote.student_id == SID, WeekNote.week_start >= MONDAY - timedelta(days=7)).delete(synchronize_session=False)
        db.query(CoachWorkBlock).filter(
            CoachWorkBlock.student_id == SID, CoachWorkBlock.title == "Özel ders matematik ödevi"
        ).delete(synchronize_session=False)
        db.commit()
    # Eski programsız görevleri "Eski Dönem" programına bağla (üstteki bant kalksın)
    page.request.post(f"{cgs.BASE}/api/v2/teacher/students/{SID}/programs/wrap-legacy", data={})
    print(f"  temizlendi: {len(task_ids)} görev · {len(progs)} program · {len(skels)} iskelet dönemi")


def add_task(page: Page, d: date, book_id: int, section_id: int, n: int, period: str | None = None, draft=False) -> int:
    r = page.request.post(
        f"{cgs.BASE}/api/v2/teacher/students/{SID}/tasks",
        data={
            "date": iso(d),
            "type": "test",
            "title": "Görev",
            "period": period,
            "is_draft": draft,
            "items": [{"book_id": book_id, "section_id": section_id, "planned_count": n, "allow_over_capacity": True}],
        },
    )
    try:
        return int(r.json()["data"]["id"])
    except Exception:  # noqa: BLE001
        print(f"  görev eklenemedi {r.status}: {r.text()[:200]}")
        return 0


def sections_of(book_name_like: str) -> tuple[int, dict[str, int]]:
    from app.database import SessionLocal
    from app.models import Book, BookSection

    with SessionLocal() as db:
        b = db.query(Book).filter(Book.teacher_id == IDS["coach"], Book.name.like(book_name_like)).first()
        secs = {s.label: s.id for s in db.query(BookSection).filter(BookSection.book_id == b.id)}
        return b.id, secs


def open_day(page: Page, d: date) -> None:
    btn = page.locator("nav[aria-label='Günler'] button").filter(has_text=_DAY[d.weekday()]).first
    btn.click()
    time.sleep(1.2)


_DAY = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def week(page: Page, start: date | None = None, fab: bool = False, hint: bool = False) -> None:
    path = WEEK_URL + (f"?start={iso(start)}" if start else "")
    go(page, path, "Hafta Izgarası")
    if not fab:
        page.add_style_tag(content="[data-section='week:video-basket-fab']{display:none !important}")
    if not hint:
        page.add_style_tag(content="[data-section='guide-hint']{display:none !important}")
    time.sleep(2.0)
    # eski demo verisinden kalan "programa bağlı değil" bandı eğitimle ilgisiz — gizle
    page.evaluate("""() => { for (const el of document.querySelectorAll('main div')) {
        if (el.children.length && el.innerText && el.innerText.startsWith('Bu öğrencinin') &&
            el.innerText.includes('programa bağlı değil') && el.innerText.length < 300) { el.style.display='none'; break; } } }""")
    time.sleep(0.5)


def to_top(page: Page, loc, offset: int = 140) -> None:
    """Öğeyi görünümün üstüne yakın kaydır (altında açılan liste sığsın)."""
    loc.scroll_into_view_if_needed()
    loc.evaluate(f"el => window.scrollBy(0, el.getBoundingClientRect().top - {offset})")
    time.sleep(0.6)


# ---------------------------------------------------------------- 1) sayfa + yeni program


def shots_sayfa(page: Page) -> None:
    reset_weeks(page)
    week(page, hint=True)
    head = page.locator("main").get_by_role("button", name="Yeni Program").locator("xpath=ancestor::div[contains(@class,'flex')][2]")
    cgs.snap(
        page,
        "p-bos",
        {
            "baslik": page.locator("main h1").first.locator(".."),
            "rehber": page.locator("[data-section='guide-hint']").first,
            "yeni": page.get_by_role("button", name="Yeni Program").first,
            "dugmeler": head,
        },
    )
    page.get_by_role("button", name="Yeni Program").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    page.locator("#wp-start").fill(iso(MONDAY))
    page.locator("#wp-end").fill(iso(MONDAY + timedelta(days=6)))
    time.sleep(0.8)
    cgs.snap(page, "p-yeni-program", {"pencere": dlg, "olustur": dlg.get_by_role("button", name="Oluştur")})
    dlg.get_by_role("button", name="Oluştur").click()
    time.sleep(3.0)
    hide_noise(page)
    cgs.snap(
        page,
        "p-program-acildi",
        {
            "baslik": page.locator("main h1").first.locator(".."),
            "dugmeler": page.get_by_role("button", name="Yeni Program").first.locator(".."),
        },
    )
    # Programlar menüsü
    page.get_by_role("button", name="Programlar").first.click()
    time.sleep(1.0)
    cgs.snap(page, "p-programlar", {"menu": page.get_by_role("button", name="Programı düzenle").first.locator("xpath=ancestor::div[contains(@class,'absolute')][1]")})
    page.mouse.click(5, 5)
    time.sleep(0.5)
    page.get_by_role("button", name="Tarihleri düzenle").first.click()
    time.sleep(1.2)
    cgs.snap(page, "p-tarih-duzenle", {"pencere": page.get_by_role("dialog").first})
    page.keyboard.press("Escape")
    time.sleep(0.6)


# ---------------------------------------------------------------- 2) gün kartında görev ekleme


def shots_gorev(page: Page) -> None:
    week(page)
    # sayfa düzeni
    cgs.snap(
        page,
        "p-duzen-ust",
        {
            "izgara": page.get_by_text("tüm günler bir bakışta", exact=False).first.locator("xpath=ancestor::section[1]"),
            "denge": page.get_by_text("Hafta notları").first,
        },
    )
    editor = page.locator("#day-editor")
    editor.scroll_into_view_if_needed()
    page.mouse.wheel(0, -60)
    time.sleep(0.8)
    cgs.snap(
        page,
        "p-duzen-alt",
        {
            "fihrist": page.locator("nav[aria-label='Günler']").first,
            "kart": page.locator(f"details[data-day='{iso(TODAY)}']").first,
            "serit": page.locator("nav[aria-label='Yan panel bölümleri']").first,
            "kaynak": page.locator("section[data-section='week:resources']").first,
        },
    )
    card = page.locator(f"details[data-day='{iso(TODAY)}']").first
    card.get_by_text("Yeni görev ekle").first.click()
    time.sleep(1.2)
    search = page.get_by_label("Görev ara").first
    to_top(page, search)
    search.click()
    time.sleep(2.5)
    drop = search.locator("xpath=ancestor::div[contains(@class,'relative')][1]")
    cgs.snap(page, "p-ara-oneriler", {"kutu": search, "liste": drop})
    search.fill("Doğrusal")
    time.sleep(2.5)
    cgs.snap(page, "p-ara-sonuc", {"kutu": search, "liste": drop})
    src = page.get_by_role("button", name="3D LGS Matematik", exact=False).first
    src.click()
    time.sleep(1.5)
    adet = page.get_by_label("Adet").first
    cgs.snap(page, "p-ara-secildi", {"ozet": adet.locator("xpath=ancestor::div[contains(@class,'space-y') or contains(@class,'rounded')][1]"), "adet": adet})
    page.get_by_role("button", name="Ekle", exact=True).first.click()
    time.sleep(2.5)
    cgs.snap(page, "p-eklendi", {"kart": card})
    # Kaynak belirtmeden ver
    search = page.get_by_label("Görev ara").first
    to_top(page, search)
    search.click()
    search.fill("Üçgenler")
    time.sleep(2.5)
    kb = page.get_by_role("button", name="Kaynak belirtmeden ver").first
    cgs.snap(page, "p-kaynaksiz", {"buton": kb})
    page.keyboard.press("Escape")
    time.sleep(0.5)
    # Ayrıntılı form
    page.get_by_role("button", name="Ayrıntılı form").first.click()
    time.sleep(1.2)
    tiles = page.get_by_text("Görev tipi", exact=False).first.locator("xpath=ancestor::div[2]")
    cgs.snap(page, "p-ayrintili", {"tipler": tiles})
    # Periyotlu gün: yarına sabah + akşam görevi (API) → bölgeler
    fen_id, fen = sections_of("Sınav Yayınları%")
    mat_id, mat = sections_of("3D LGS Matematik%")
    tmr = TODAY + timedelta(days=1)
    add_task(page, tmr, mat_id, mat["Cebirsel İfadeler ve Özdeşlikler"], 3, "morning", draft=True)
    add_task(page, tmr, fen_id, list(fen.values())[1], 2, "evening", draft=True)
    week(page)
    open_day(page, tmr)
    card2 = page.locator(f"details[data-day='{iso(tmr)}']").first
    card2.scroll_into_view_if_needed()
    page.mouse.wheel(0, -60)
    time.sleep(0.8)
    sabah = card2.locator("section[data-period='morning']").first
    cgs.snap(page, "p-periyot", {"kart": card2, "sabah": sabah, "ekle": card2.get_by_role("button", name="Sabaha ekle", exact=False).first})


# ---------------------------------------------------------------- 3) Kaynak Durumu + Müfredat


def chooser(page: Page):
    return page.get_by_test_id("assign-count-chooser").first


def shots_panel(page: Page) -> None:
    wed = MONDAY + timedelta(days=2)
    week(page)
    open_day(page, wed)
    res = page.locator("section[data-section='week:resources']").first
    res.locator("div.resource-subject").filter(has_text="Matematik").first.locator("button").first.click()
    time.sleep(1.0)
    res.get_by_role("button", name="3D LGS Matematik", exact=False).first.click()
    time.sleep(1.2)
    to_top(page, res, 90)
    plus = res.get_by_role("button", name="Veri Analizi: test ver").first
    cgs.snap(page, "p-kaynak", {"panel": res, "arti": plus})
    plus.click()
    time.sleep(1.0)
    ch = chooser(page)
    cgs.snap(page, "p-kaynak-sec", {"secici": ch})
    ch.get_by_role("button", name="2", exact=True).first.click()
    time.sleep(2.5)
    card = page.locator(f"details[data-day='{iso(wed)}']").first
    to_top(page, card, 90)
    cgs.snap(page, "p-kaynak-eklendi", {"kart": card, "panel": res})

    # Müfredat — şeritten geçici açılır
    rail = page.locator("nav[aria-label='Yan panel bölümleri']").first
    page.locator("[data-rail='week:curriculum']").first.click()
    time.sleep(2.5)
    peek = page.locator("div[data-peek='week:curriculum']").first
    try:
        sel = peek.get_by_label("Ders seç").first
        pick_by_text(sel, "Matematik")
        time.sleep(2.0)
    except Exception:  # noqa: BLE001
        pass
    to_top(page, peek, 90)
    cgs.snap(page, "p-mufredat", {"panel": peek, "serit": rail})
    peek.get_by_role("button", name="Eşitsizlikler", exact=False).first.click()
    time.sleep(2.0)
    cgs.snap(page, "p-mufredat-konu", {"panel": peek})
    peek.get_by_role("button", name="test ver", exact=False).first.click()
    time.sleep(1.0)
    cgs.snap(page, "p-mufredat-ver", {"secici": chooser(page)})
    chooser(page).get_by_role("button", name="2", exact=True).first.click()
    time.sleep(2.5)
    # tamamlanmış bir konu → kapatma
    peek = page.locator("div[data-peek='week:curriculum']").first
    if not peek.is_visible():
        page.locator("[data-rail='week:curriculum']").first.click()
        time.sleep(2.0)
        peek = page.locator("div[data-peek='week:curriculum']").first
    peek.get_by_role("button", name="Üslü İfadeler", exact=False).first.click()
    time.sleep(1.8)
    cgs.snap(page, "p-mufredat-kapat", {"panel": peek, "kapat": peek.get_by_role("button", name="Konuyu kapat").first})
    page.keyboard.press("Escape")
    time.sleep(0.6)
    cgs.snap(page, "p-serit", {"serit": rail})


# ---------------------------------------------------------------- 4) Hafta Izgarası


def grid_cell(page: Page, d: date):
    return page.locator(f"button[title^='{_DAY[d.weekday()]} —']").first


def shots_izgara(page: Page) -> None:
    week(page)
    grid = page.get_by_text("tüm günler bir bakışta", exact=False).first.locator("xpath=ancestor::section[1]")
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.6)
    cgs.snap(page, "p-izgara", {"izgara": grid})
    chip = grid_cell(page, MONDAY).locator("li").first
    chip.click(button="right")
    time.sleep(0.8)
    menu = page.get_by_role("button", name="Başka güne kopyala").first.locator("xpath=..")
    cgs.snap(page, "p-sagtik", {"menu": menu})
    page.get_by_role("button", name="Başka güne kopyala").first.click()
    time.sleep(0.8)
    banner = page.get_by_text("günü seç (ızgarada bir güne tıkla)", exact=False).first
    cgs.snap(page, "p-hedef", {"bant": banner.locator(".."), "izgara": grid})
    grid_cell(page, MONDAY + timedelta(days=3)).click()
    time.sleep(2.5)
    cgs.snap(page, "p-kopyalandi", {"hucre": grid_cell(page, MONDAY + timedelta(days=3))})
    # taşı: Çarşamba'daki ilk görevi Cuma'ya
    grid_cell(page, MONDAY + timedelta(days=2)).locator("li").first.click(button="right")
    time.sleep(0.8)
    page.get_by_role("button", name="Başka güne taşı").first.click()
    time.sleep(0.6)
    grid_cell(page, MONDAY + timedelta(days=4)).click()
    time.sleep(2.5)
    cgs.snap(page, "p-tasindi", {"izgara": grid, "hucre": grid_cell(page, MONDAY + timedelta(days=4))})
    # Haftaya yay — bugünün görevi
    open_day(page, TODAY)
    card = page.locator(f"details[data-day='{iso(TODAY)}']").first
    to_top(page, card, 90)
    yay = card.get_by_role("button", name="Haftaya yay").first
    cgs.snap(page, "p-yay-dugme", {"dugme": yay})
    yay.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    time.sleep(0.8)
    for g in ("Cmt", "Paz"):
        b = dlg.get_by_role("button", name=g, exact=True)
        if b.count():
            b.first.click()
            time.sleep(0.2)
    time.sleep(0.6)
    cgs.snap(page, "p-yay", {"pencere": dlg})
    dlg.get_by_role("button", name="güne yay", exact=False).last.click()
    time.sleep(3.0)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.8)
    cgs.snap(page, "p-yayildi", {"izgara": grid})


# ---------------------------------------------------------------- 5) İskelet


def shots_iskelet(page: Page) -> None:
    week(page)
    page.get_by_role("button", name="İskelet oluştur").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    time.sleep(1.5)
    cgs.snap(page, "p-iskelet-bos", {"pencere": dlg, "yap": dlg.get_by_role("button", name="Bu haftayı iskelet yap")})
    dlg.get_by_role("button", name="Bu haftayı iskelet yap").click()
    time.sleep(3.0)
    tabs = dlg.get_by_test_id("skeleton-day-tab")
    tabs.nth(1).click()
    time.sleep(1.0)
    day = dlg.get_by_test_id("skeleton-day").first
    cgs.snap(page, "p-iskelet-gun", {"gunler": dlg.locator("nav[aria-label='Günler']").first, "gun": day})
    row = day.get_by_test_id("skeleton-row").first
    cgs.snap(page, "p-iskelet-satir", {"satir": row})
    # okul/dershane dersi (çapa) — Salı Fen Bilimleri
    day.get_by_test_id("add-anchor").click()
    time.sleep(0.8)
    anc = day.locator("div[data-kind='anchor']").get_by_test_id("skeleton-row").last
    pick_by_text(anc.locator("select").first, "Fen Bilimleri")
    time.sleep(0.6)
    cgs.snap(page, "p-iskelet-capa", {"satir": anc})
    # rutin — günlük 2 paragraf testi, karışık
    day.get_by_test_id("add-routine").click()
    time.sleep(0.8)
    rut = day.locator("div[data-kind='routine']").get_by_test_id("skeleton-row").last
    pick_by_text(rut.locator("select").first, "Türkçe")
    time.sleep(0.6)
    pick_by_text(rut.get_by_label("Kaynak kitap"), "Zoom Serisi")
    time.sleep(0.8)
    rut.get_by_label("Test sayısı").fill("2")
    try:
        rb = rut.get_by_label("Rutin biçimi")
        pick_by_text(rb, "Karışık")
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.8)
    rut.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "p-iskelet-rutin", {"satir": rut})
    # rutini diğer günlere kopyala
    day.get_by_role("button", name="Bu günü başka günlere kopyala").click()
    time.sleep(0.8)
    cp = day.get_by_test_id("copy-day")
    cp.scroll_into_view_if_needed()
    time.sleep(0.4)
    cgs.snap(page, "p-iskelet-kopya", {"panel": cp})
    cp.get_by_role("button", name="vazgeç").first.click()
    time.sleep(0.4)
    dlg.get_by_role("button", name="Kaydet", exact=True).last.click()
    time.sleep(3.0)
    if dlg.is_visible():
        cgs.snap(page, "p-iskelet-donem", {"serit": dlg.get_by_test_id("period-strip")})
        page.keyboard.press("Escape")
        time.sleep(0.8)

    # Gelecek hafta: program aç → öneriler
    page.request.post(
        f"{cgs.BASE}/api/v2/teacher/students/{SID}/programs",
        data={"start_date": iso(NEXT_MONDAY), "end_date": iso(NEXT_MONDAY + timedelta(days=6)), "allow_overlap": True},
    )
    week(page, NEXT_MONDAY)
    grid = page.get_by_text("tüm günler bir bakışta", exact=False).first.locator("xpath=ancestor::section[1]")
    cgs.snap(page, "p-oneri-izgara", {"izgara": grid})
    tue = NEXT_MONDAY + timedelta(days=1)
    open_day(page, tue)
    card = page.locator(f"details[data-day='{iso(tue)}']").first
    box = card.locator("[data-section='day:skeleton-ghosts']").first
    to_top(page, box, 90)
    cgs.snap(page, "p-oneri", {"oneriler": box, "rutin": box.get_by_role("button", name="Rutinleri onayla", exact=False).first})
    # konu satırı → çip şeridi
    topic_row = box.get_by_test_id("ghost-row").filter(has_text="Matematik").first
    topic_row.click()
    time.sleep(2.5)
    strip = box.get_by_test_id("ghost-strip").first
    cgs.snap(page, "p-oneri-serit", {"serit": strip, "cip": strip.get_by_test_id("ghost-chip").first})
    strip.get_by_test_id("ghost-chip").first.click()
    time.sleep(3.0)
    to_top(page, card, 90)
    cgs.snap(page, "p-oneri-kabul", {"kart": card})
    # okul/dershane dersi → işlenen konu → yayma penceresi
    box = card.locator("[data-section='day:skeleton-ghosts']").first
    anc_row = box.get_by_test_id("ghost-row").filter(has_text="dershane").first
    if anc_row.count():
        anc_row.click()
        time.sleep(2.5)
        strip = box.get_by_test_id("ghost-strip").first
        cgs.snap(page, "p-capa-soru", {"serit": strip})
        try:
            strip.get_by_test_id("ghost-chip").first.click()
            page.get_by_test_id("spread-dialog").wait_for(timeout=20_000)
            time.sleep(2.0)
            cgs.snap(page, "p-konu-yay", {"pencere": page.get_by_test_id("spread-dialog")})
            page.keyboard.press("Escape")
            time.sleep(0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  konu yayma: {e}")
    # rutinleri onayla → önizleme
    box = card.locator("[data-section='day:skeleton-ghosts']").first
    rb = box.get_by_role("button", name="Rutinleri onayla", exact=False).first
    if rb.count():
        rb.click()
        page.get_by_test_id("routine-preview").wait_for(timeout=20_000)
        time.sleep(1.5)
        cgs.snap(page, "p-rutin-onizle", {"pencere": page.get_by_role("dialog").first})
        page.get_by_role("dialog").get_by_role("button", name="görevi yaz", exact=False).first.click()
        time.sleep(2.5)


# ---------------------------------------------------------------- 6) Yayın + veli


def shots_yayin(page: Page) -> None:
    week(page)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)
    pub = page.get_by_role("button", name="Tüm haftayı yayınla", exact=False).first
    banner = page.get_by_text("görev taslak halinde", exact=False).first
    cgs.snap(page, "p-taslak", {"dugme": pub, "bant": banner.locator("xpath=ancestor::div[1]")})
    tue = MONDAY + timedelta(days=1)
    open_day(page, tue)
    card = page.locator(f"details[data-day='{iso(tue)}']").first
    to_top(page, card, 90)
    cgs.snap(page, "p-gun-yayinla", {"dugme": card.get_by_role("button", name="Bu günü yayınla").first})
    page.evaluate("window.scrollTo(0, 0)")
    pub.click()
    time.sleep(3.0)
    cgs.snap(page, "p-yayinlandi", {"izgara": page.get_by_text("tüm günler bir bakışta", exact=False).first.locator("xpath=ancestor::section[1]")})
    page.get_by_role("button", name="Veliye duyur").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    time.sleep(3.0)
    cgs.snap(page, "p-veli", {"pencere": dlg, "gonder": dlg.get_by_role("button", name="Velilere gönder")})
    page.keyboard.press("Escape")
    time.sleep(0.5)
    from app.database import SessionLocal
    from app.models import WeeklyProgram

    with SessionLocal() as db:
        pid = (
            db.query(WeeklyProgram.id)
            .filter(WeeklyProgram.student_id == SID, WeeklyProgram.start_date == MONDAY)
            .scalar()
        )
    go(page, f"/teacher/students/{SID}/program/print?program_id={pid}", None)
    time.sleep(3.0)
    cgs.snap(page, "p-yazdir", {"sayfa": page.locator("body").first})


# ---------------------------------------------------------------- 7) Takip


def student_complete_today() -> None:
    import httpx

    from app.database import SessionLocal
    from app.models import Task

    with SessionLocal() as db:
        ids = [t.id for t in db.query(Task.id).filter(Task.student_id == SID, Task.date == TODAY, Task.is_draft.is_(False))]
    with httpx.Client(base_url="http://127.0.0.1:8081", timeout=30) as c:
        c.post("/api/v2/auth/login", json={"email": "rehber-elif@etutkoc.demo", "password": "RehberDemo2026!"})
        for tid in ids[:1]:
            r = c.post(f"/api/v2/student/tasks/{tid}/complete", json={})
            print(f"  öğrenci tamamladı #{tid} → {r.status_code}")


def shots_takip(page: Page) -> None:
    student_complete_today()
    week(page)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.6)
    grid = page.get_by_text("tüm günler bir bakışta", exact=False).first.locator("xpath=ancestor::section[1]")
    cgs.snap(page, "p-takip-izgara", {"izgara": grid, "bugun": grid_cell(page, TODAY)})
    open_day(page, TODAY)
    card = page.locator(f"details[data-day='{iso(TODAY)}']").first
    to_top(page, card, 90)
    cgs.snap(page, "p-takip-gun", {"kart": card})
    denge = page.locator("[data-section='week:subject-mix']").first
    to_top(page, denge, 90)
    cgs.snap(page, "p-denge", {"denge": denge})
    notes = page.get_by_text("Hafta notları").first
    notes.click()
    time.sleep(0.8)
    inp = page.get_by_placeholder("Yeni not ekle…").first
    inp.fill("Perşembe dersine son denemeyi getir")
    page.get_by_role("button", name="Ekle", exact=True).last.click()
    time.sleep(1.5)
    to_top(page, notes, 90)
    cgs.snap(page, "p-notlar", {"notlar": notes.locator("xpath=ancestor::*[contains(@class,'rounded-xl')][1]")})
    # Serbest Bloklar
    page.locator("[data-rail='week:work-blocks']").first.click()
    time.sleep(1.5)
    peek = page.locator("div[data-peek='week:work-blocks']").first
    try:
        peek.get_by_role("button", name="Yeni", exact=False).first.click()
        time.sleep(0.6)
        peek.get_by_placeholder("Blok adı", exact=False).fill("Özel ders matematik ödevi")
        peek.locator("input[type=number]").first.fill("40")
        peek.get_by_role("button", name="Oluştur").first.click()
        peek.get_by_text("Dağıtılan", exact=False).first.wait_for(timeout=20_000)
        time.sleep(1.0)
    except Exception as e:  # noqa: BLE001
        print(f"  blok: {e}")
    cgs.snap(page, "p-bloklar", {"panel": peek})
    page.keyboard.press("Escape")
    time.sleep(0.5)


SECTIONS = {
    "sayfa": shots_sayfa,
    "gorev": shots_gorev,
    "panel": shots_panel,
    "izgara": shots_izgara,
    "iskelet": shots_iskelet,
    "yayin": shots_yayin,
    "takip": shots_takip,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--reset", action="store_true")
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
        page.on("dialog", lambda d: d.accept())
        cgs.ensure_guide_dismissed()
        cgs.login(page)
        if args.reset:
            reset_weeks(page)
            only = []
        for name in only:
            print(f"\n== {name}")
            try:
                SECTIONS[name](page)
            except Exception as e:  # noqa: BLE001
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
