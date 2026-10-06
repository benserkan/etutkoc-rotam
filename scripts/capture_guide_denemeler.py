"""Rehber — DENEMELER serisi ekran yakalayıcı (gerçek panel, demo koç).

Elif Kaya'nın Denemeler sekmesinde GERÇEK akışlar: PDF karne aktarma (gerçek
Gemini okuması, 6 kredi), elle giriş, mükerrer koruması, deneme detayı, analiz
sekmeleri (Genel Bakış · Net Gelişimi · Konu Analizi · Sınav Davranışı · Gelişim
Raporu · Puan Tahmini), öğrenciyle paylaşım ve veliye duyuru önizlemesi
(GÖNDERİLMEZ — tekrar çekim bozulmasın). 1440×900, 2x.

Önkoşul: :8081 (run_dev_patched — Gemini) + :3000, seed_guide_demo,
scripts/ornek_sonuc_karnesi_4.pdf (gen_ornek_karne.py --deneme4).

  python -m scripts.capture_guide_denemeler
  python -m scripts.capture_guide_denemeler --only liste,konu
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
from scripts.capture_guide_kitaplar import go, pick_by_text

IDS = cgs.IDS
SID = IDS["elif"]
ROOT = Path(__file__).resolve().parent.parent
PDF_NEW = ROOT / "scripts" / "ornek_sonuc_karnesi_4.pdf"
NEW_TITLE = "LGS DENEME SINAVI - 4"


def exams_page(page: Page, all_periods: bool = False, hint: bool = False) -> None:
    go(page, f"/teacher/students/{SID}#exams", None)
    page.get_by_text("Deneme Analizi", exact=True).first.wait_for(timeout=60_000)
    if not hint:
        page.add_style_tag(content="[data-section='guide-hint']{display:none !important}")
    time.sleep(2.5)
    if all_periods:
        # Elif'in önceki denemeleri geçen dönemde (7. sınıf) — analizler hepsini görsün
        page.get_by_text("Dönem:", exact=True).first.locator("xpath=..").get_by_role("button", name="Tümü", exact=True).first.click()
        time.sleep(2.5)


def sub_tab(page: Page, name: str) -> None:
    page.locator("[role='tablist'][aria-label='Deneme analizi bölümleri']").get_by_role("tab", name=name).first.click()
    time.sleep(2.5)


def block(page: Page, heading: str):
    """Başlığın ait olduğu kart/bölüm."""
    return page.get_by_text(heading, exact=True).first.locator(
        "xpath=ancestor::*[self::section or contains(@class,'rounded-xl') or contains(@class,'rounded-lg')][1]"
    )


def to_top(page: Page, loc, offset: int = 100) -> None:
    loc.scroll_into_view_if_needed()
    loc.evaluate(f"el => window.scrollBy(0, el.getBoundingClientRect().top - {offset})")
    time.sleep(0.6)


def exam_row(page: Page, title: str):
    return page.locator("li").filter(has=page.get_by_role("button", name=title, exact=True)).first


def new_exam_id() -> int | None:
    from app.database import SessionLocal
    from app.models.exam_result import ExamResult

    with SessionLocal() as db:
        return (
            db.query(ExamResult.id)
            .filter(ExamResult.student_id == SID, ExamResult.title == NEW_TITLE)
            .order_by(ExamResult.id.desc())
            .scalar()
        )


def reset(page: Page) -> None:
    from app.database import SessionLocal
    from app.models.exam_progress import ExamTarget, SessionAgendaItem
    from app.models.exam_result import ExamResult

    with SessionLocal() as db:
        ids = [e.id for e in db.query(ExamResult.id).filter(ExamResult.student_id == SID, ExamResult.title.like(NEW_TITLE + "%"))]
        db.query(ExamTarget).filter(ExamTarget.student_id == SID).delete(synchronize_session=False)
        db.query(SessionAgendaItem).filter(SessionAgendaItem.student_id == SID).delete(synchronize_session=False)
        db.commit()
    for eid in ids:
        r = page.request.delete(f"{cgs.BASE}/api/v2/teacher/exams/{eid}")
        print(f"  eski deneme silindi #{eid} → {r.status}")


# ---------------------------------------------------------------- 1) ekle


def shots_ekle(page: Page) -> None:
    reset(page)
    exams_page(page, all_periods=False)
    pdf_btn = page.locator("button").filter(has_text="Deneme sonuç PDF'ini yükle").first
    elle = page.get_by_text("Elle deneme gir", exact=False).first
    to_top(page, page.get_by_text("Deneme Analizi", exact=True).first, 90)
    cgs.snap(
        page,
        "d-panel",
        {"baslik": page.get_by_text("Deneme Analizi", exact=True).first.locator(".."), "pdf": pdf_btn, "elle": elle},
    )
    # elle giriş
    elle.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    page.locator("#ex-title").fill("Karekök LGS Deneme 5")
    dlg.get_by_role("button", name="Ders kırılımı").first.click()
    time.sleep(0.8)
    cgs.snap(page, "d-elle", {"pencere": dlg})
    page.keyboard.press("Escape")
    time.sleep(0.8)
    # PDF'ten aktar
    pdf_btn.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    time.sleep(0.8)
    sels = dlg.locator("select")
    pick_by_text(sels.nth(0), "8. Sınıf")
    time.sleep(0.5)
    pick_by_text(sels.nth(1), "LGS")
    time.sleep(0.6)
    cgs.snap(page, "d-pdf-sec", {"beyan": sels.nth(0).locator("xpath=ancestor::div[contains(@class,'rounded')][1]"), "pencere": dlg})
    dlg.locator("input[type=file]").first.set_input_files(str(PDF_NEW))
    time.sleep(2.0)
    start = dlg.get_by_role("button", name="Okumaya başla")
    if start.count():
        start.first.click()
        time.sleep(2.0)
    try:
        page.get_by_text("Yapay zekâ belgeyi okuyor", exact=False).first.wait_for(timeout=15_000)
        time.sleep(1.0)
        cgs.snap(page, "d-pdf-okunuyor", {"pencere": dlg})
    except Exception as e:  # noqa: BLE001
        print(f"  okuma ekranı: {e}")
    save = dlg.get_by_role("button", name="Kontrol ettim, kaydet")
    save.first.wait_for(timeout=400_000)
    time.sleep(2.0)
    # Okuma bazen başlığa "KONU ANALİZLİ SONUÇ KARNESİ" ekler — koç adı sadeleştirir
    dlg.get_by_label("Deneme adı").first.fill(NEW_TITLE)
    time.sleep(0.8)
    cgs.snap(
        page,
        "d-pdf-onizleme",
        {
            "kimlik": dlg.get_by_label("Deneme adı").locator("xpath=ancestor::div[contains(@class,'grid') or contains(@class,'flex')][1]"),
            "cipler": dlg.get_by_text("otomatik eşleşti", exact=False).first.locator(".."),
            "tablo": dlg.locator("table").first,
        },
    )
    tbl = dlg.locator("table").first
    tbl.locator("tbody tr").nth(4).scroll_into_view_if_needed()
    time.sleep(0.8)
    cgs.snap(page, "d-pdf-tablo", {"satir": tbl.locator("tbody tr").nth(4), "konu": tbl.locator("select[aria-label='Müfredat konusu']").nth(4)})
    save.first.scroll_into_view_if_needed()
    cgs.snap(page, "d-pdf-alt", {"kaydet": save.first.locator("xpath=..")})
    save.first.click()
    page.get_by_text("Deneme kaydedildi", exact=False).first.wait_for(timeout=120_000)
    time.sleep(1.5)
    arch = dlg.get_by_role("button", name="Yanlışlardan arşive soru seç")
    cgs.snap(page, "d-pdf-kaydedildi", {"sonuc": dlg, "arsiv": arch.first})
    arch.first.click()
    time.sleep(2.0)
    adlg = page.get_by_role("dialog").last
    boxes = adlg.locator("input[type=checkbox]:not([disabled])")
    if boxes.count():
        boxes.first.check()
        time.sleep(0.6)
        ht = adlg.get_by_label("Hata türü")
        if ht.count():
            ht.first.select_option(index=1)
            time.sleep(0.4)
    cgs.snap(page, "d-arsiv", {"pencere": adlg})
    page.keyboard.press("Escape")
    time.sleep(0.8)
    page.keyboard.press("Escape")
    time.sleep(0.8)
    # mükerrer: aynı PDF yeniden
    exams_page(page)
    page.locator("button").filter(has_text="Deneme sonuç PDF'ini yükle").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    dlg.locator("input[type=file]").first.set_input_files(str(PDF_NEW))
    time.sleep(2.0)
    start = dlg.get_by_role("button", name="Okumaya başla")
    if start.count():
        start.first.click()
    try:
        page.get_by_text("Bu PDF zaten aktarılmış", exact=False).first.wait_for(timeout=60_000)
        time.sleep(1.0)
        cgs.snap(page, "d-mukerrer", {"uyari": page.get_by_text("Bu PDF zaten aktarılmış", exact=False).first.locator("xpath=ancestor::div[1]")})
    except Exception as e:  # noqa: BLE001
        print(f"  mükerrer: {e}")
    page.keyboard.press("Escape")
    time.sleep(0.6)


# ---------------------------------------------------------------- 2) liste + detay


def shots_liste(page: Page) -> None:
    exams_page(page)
    sub_tab(page, "Tüm Denemeler")
    row = exam_row(page, NEW_TITLE)
    to_top(page, row, 140)
    acts = row.get_by_role("button", name="Deneme detayı").locator("xpath=..")
    cgs.snap(page, "d-liste", {"satir": row, "islemler": acts})
    row.get_by_role("button", name="Deneme detayı").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=20_000)
    time.sleep(2.5)
    cgs.snap(page, "d-detay", {"pencere": dlg})
    for head, name, tgt in [
        ("Test içinde ilerleyiş", "d-ilerleyis", "bolum"),
        ("Soru soru", "d-soru-soru", "bolum"),
        ("Çeldirici analizi", "d-celdirici", "bolum"),
    ]:
        h = dlg.get_by_text(head, exact=False).first
        if h.count():
            h.scroll_into_view_if_needed()
            h.evaluate("el => el.scrollIntoView({block:'start'})")
            time.sleep(1.0)
            cgs.snap(page, name, {tgt: h.locator("xpath=ancestor::*[self::section or contains(@class,'rounded')][1]")})
    page.keyboard.press("Escape")
    time.sleep(0.8)
    row = exam_row(page, NEW_TITLE)
    row.get_by_role("button", name="İçe aktarılan satırları düzenle").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.get_by_role("button", name="Kontrol ettim, kaydet").first.wait_for(timeout=120_000)
    time.sleep(1.5)
    cgs.snap(page, "d-duzelt", {"pencere": dlg})
    page.keyboard.press("Escape")
    time.sleep(0.8)
    eid = new_exam_id()
    go(page, f"/teacher/students/{SID}/exams/{eid}/print", None)
    time.sleep(3.0)
    cgs.snap(page, "d-karne", {"sayfa": page.locator("main, body").first})


# ---------------------------------------------------------------- 3) genel + net


def shots_genel(page: Page) -> None:
    exams_page(page)
    sw = page.get_by_text("Dönem:", exact=True).first.locator("xpath=..")
    to_top(page, sw, 300)
    cgs.snap(page, "d-donem", {"secici": sw})
    sub_tab(page, "Genel Bakış")
    son = block(page, "Son deneme")
    to_top(page, page.locator("[role='tablist'][aria-label='Deneme analizi bölümleri']").first, 100)
    cgs.snap(page, "d-genel", {"sekmeler": page.locator("[role='tablist'][aria-label='Deneme analizi bölümleri']").first, "son": son})
    one = page.get_by_text("Öne çıkanlar", exact=False).first
    to_top(page, one, 120)
    cgs.snap(page, "d-one-cikan", {"kutu": one.locator("xpath=ancestor::div[contains(@class,'rounded')][1]")})
    ders = block(page, "Ders bazında sonuç")
    to_top(page, ders, 100)
    cgs.snap(page, "d-ders", {"tablo": ders})
    btn = page.get_by_role("button", name="Genel ortalama gir")
    if btn.count():
        btn.first.click()
        time.sleep(1.2)
        cgs.snap(page, "d-ortalama", {"pencere": page.get_by_role("dialog").first})
        page.keyboard.press("Escape")
        time.sleep(0.6)
    sub_tab(page, "Net Gelişimi")
    g = block(page, "Toplam net gelişimi")
    to_top(page, g, 100)
    cgs.snap(page, "d-net-grafik", {"grafik": g})
    t = block(page, "Ders × deneme net tablosu")
    to_top(page, t, 100)
    cgs.snap(page, "d-net-tablo", {"tablo": t})


# ---------------------------------------------------------------- 4) konu analizi


def shots_konu(page: Page) -> None:
    exams_page(page)
    sub_tab(page, "Konu Analizi")
    f = page.get_by_text("Net fırsatı", exact=True).first
    to_top(page, f, 100)
    cgs.snap(page, "d-firsat", {"liste": f.locator("xpath=ancestor::*[self::section or contains(@class,'rounded')][1]")})
    d = page.get_by_text("Konu değişimleri", exact=False).first
    to_top(page, d, 100)
    cgs.snap(page, "d-degisim", {"kartlar": d.locator("xpath=ancestor::*[self::section or contains(@class,'rounded')][1]")})
    k = page.get_by_role("button", name="Kanıtı gör")
    if k.count():
        k.first.click()
        time.sleep(1.5)
        cgs.snap(page, "d-kanit", {"pencere": page.get_by_role("dialog").first})
        page.keyboard.press("Escape")
        time.sleep(0.6)
    s = page.get_by_role("button", name="Seansa ekle")
    if s.count():
        to_top(page, s.first, 300)
        cgs.snap(page, "d-seansa", {"dugme": s.first})
        s.first.click()
        time.sleep(1.5)
    h = page.get_by_text("Konu × deneme ısı haritası", exact=False).first
    if h.count():
        to_top(page, h, 100)
        cgs.snap(page, "d-isi", {"tablo": h.locator("xpath=ancestor::*[self::section or contains(@class,'rounded')][1]")})


# ---------------------------------------------------------------- 5) davranış + puan


def shots_davranis(page: Page) -> None:
    exams_page(page)
    sub_tab(page, "Sınav Davranışı")
    e = block(page, "İşaretleme eğilimi")
    to_top(page, e, 100)
    cgs.snap(page, "d-davranis", {"egilim": e, "ders": block(page, "Ders bazında kaçan sorular")})
    sub_tab(page, "Puan Tahmini")
    p = page.get_by_text("Tahmini LGS puanı", exact=False).first
    to_top(page, p, 100)
    cgs.snap(page, "d-puan", {"kart": p.locator("xpath=ancestor::*[self::section or contains(@class,'rounded')][1]")})


# ---------------------------------------------------------------- 6) gelişim raporu


def shots_rapor(page: Page) -> None:
    exams_page(page)
    sub_tab(page, "Gelişim Raporu")
    import re

    page.get_by_role("button", name=re.compile("Hedef belirle|Hedefi düzenle")).first.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    dlg.get_by_label("Toplam hedef net").fill("16")
    try:
        dlg.locator("input[type=date]").first.fill("2026-12-31")
        dlg.locator("textarea").first.fill("Kasım sonuna kadar Matematik'te 16 nete çıkıyoruz.")
    except Exception:  # noqa: BLE001
        pass
    time.sleep(0.8)
    cgs.snap(page, "d-hedef-pencere", {"pencere": dlg})
    dlg.get_by_role("button", name="Kaydet").first.click()
    time.sleep(2.5)
    h = block(page, "Hedef net")
    to_top(page, h, 100)
    cgs.snap(page, "d-hedef", {"kutu": h})
    o = block(page, "Gelişim özeti")
    to_top(page, o, 100)
    cgs.snap(page, "d-ozet", {"kutu": o})
    y = block(page, "Otomatik yorum")
    to_top(page, y, 100)
    cgs.snap(page, "d-yorum", {"kutu": y})
    a = block(page, "Aksiyon planı")
    to_top(page, a, 100)
    cgs.snap(page, "d-aksiyon", {"kutu": a, "dugme": page.get_by_role("button", name="Seansa ekle", exact=False).last})
    go(page, f"/teacher/students/{SID}/exams/report/print?section=lgs", None)
    time.sleep(3.0)
    cgs.snap(page, "d-rapor-a4", {"sayfa": page.locator("body").first})


# ---------------------------------------------------------------- 7) paylaşım


def shots_paylas(page: Page) -> None:
    exams_page(page)
    sub_tab(page, "Tüm Denemeler")
    row = exam_row(page, NEW_TITLE)
    to_top(page, row, 140)
    row.get_by_role("button", name="Öğrenciyle paylaş").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.wait_for(timeout=15_000)
    dlg.locator("textarea").first.fill(
        "Elif, Üslü İfadeler'de toparlanman çok iyi. Bu hafta Veri Analizi ve Eşitsizlikler testlerine ağırlık veriyoruz."
    )
    time.sleep(0.6)
    cgs.snap(page, "d-ogrenci", {"pencere": dlg})
    page.keyboard.press("Escape")
    time.sleep(0.8)
    row = exam_row(page, NEW_TITLE)
    row.get_by_role("button", name="Sonucu veliye duyur").first.click()
    dlg = page.get_by_role("dialog").first
    dlg.get_by_text("Bu deneme ne anlatıyor", exact=False).first.wait_for(timeout=30_000)
    time.sleep(2.0)
    cgs.snap(page, "d-veli", {"pencere": dlg})
    nar = dlg.get_by_text("Bu deneme ne anlatıyor", exact=False).first
    nar.scroll_into_view_if_needed()
    nar.evaluate("el => el.scrollIntoView({block:'start'})")
    time.sleep(0.8)
    cgs.snap(
        page,
        "d-veli-yorum",
        {
            "yorum": nar.locator("xpath=ancestor::div[contains(@class,'rounded') or contains(@class,'space-y')][1]"),
            "sil": dlg.get_by_role("button", name="1. cümleyi kaldır").first,
        },
    )
    tg = dlg.get_by_text("Ders bazında tabloyu da gönder", exact=False).first
    tg.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "d-veli-tablolar", {"secim": tg})
    pdf = dlg.get_by_role("button", name="PDF olarak indir").first
    pdf.scroll_into_view_if_needed()
    time.sleep(0.6)
    cgs.snap(page, "d-veli-alt", {"pdf": pdf, "gonder": pdf.locator("xpath=..")})
    page.keyboard.press("Escape")


def shots_panel(page: Page) -> None:
    """Giriş sahnesi: eğitim kartı görünür (ekle bölümünden SONRA koşulur)."""
    exams_page(page, hint=True)
    to_top(page, page.get_by_text("Deneme Analizi", exact=True).first, 90)
    cgs.snap(
        page,
        "d-panel",
        {
            "baslik": page.get_by_text("Deneme Analizi", exact=True).first.locator(".."),
            "rehber": page.locator("[data-section='guide-hint']").first,
            "pdf": page.locator("button").filter(has_text="Deneme sonuç PDF'ini yükle").first,
            "elle": page.get_by_text("Elle deneme gir", exact=False).first,
        },
    )


SECTIONS = {
    "ekle": shots_ekle,
    "panel": shots_panel,
    "liste": shots_liste,
    "genel": shots_genel,
    "konu": shots_konu,
    "davranis": shots_davranis,
    "rapor": shots_rapor,
    "paylas": shots_paylas,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    only = args.only.split(",") if args.only else list(SECTIONS)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH}, device_scale_factor=2, locale="tr-TR", color_scheme="light"
        )
        ctx.route("**/me/panel-visits", lambda r: r.fulfill(status=204, body=""))
        page = ctx.new_page()
        page.on("dialog", lambda d: d.dismiss())  # yerel silme onayları — çekimde hiçbir şey silinmesin
        cgs.ensure_guide_dismissed()
        cgs.login(page)
        for name in only:
            print(f"\n== {name}")
            try:
                SECTIONS[name](page)
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ {name}: {e}")
                cgs.SHOTS_DIR.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(cgs.SHOTS_DIR / f"_hata_d_{name}.png"))
        browser.close()
    data = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8")) if cgs.BOXES_PATH.exists() else {}
    data.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nKutular yazıldı: {len(cgs.boxes_out)} ekran")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
