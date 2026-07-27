# -*- coding: utf-8 -*-
"""Veli rehberi EK ekran görüntüleri — 4 yeni bölüm (2026-07-27).

Haftalık Programı Gör + Konu Performansı + Denemeler & Analiz + Seans
Hareketleri sayfalarının uygulamalı kareleri (rehber-veli → Elif 228).

Önkoşul: :8081 + :3000 açık + seed_guide_demo_sessions +
enrich_guide_demo_topics koşulmuş. Gemini GEREKMEZ (salt-okuma sayfalar).

  PYTHONPATH=. python -m scripts.capture_guide_shots_parent2
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time

from playwright.sync_api import sync_playwright

import scripts.capture_guide_shots as cgs

VELI_EMAIL = "rehber-veli@etutkoc.demo"
ELIF = 228


def login_veli(page):
    cgs.goto(page, "/login")
    page.locator('input[type="email"]').fill(VELI_EMAIL)
    page.locator('input[type="password"]').fill(cgs.PWD)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/parent**", timeout=120_000)
    time.sleep(1.5)


def card_of(page, text, cls="rounded-xl"):
    return page.get_by_text(text, exact=False).first.locator(
        f"xpath=ancestor::div[contains(@class,'{cls}')][1]"
    )


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport={"width": cgs.VW, "height": cgs.VH})
        ctx.add_init_script(
            "const s=document.createElement('style');"
            "s.textContent='[class*=tsqd]{display:none!important}nextjs-portal{display:none!important}';"
            "document.addEventListener('DOMContentLoaded',()=>document.head.appendChild(s));"
        )
        page = ctx.new_page()
        login_veli(page)

        # ---- 0) Çocuk detayı — hızlı erişim düğmeleri ----
        cgs.goto(page, f"/parent/students/{ELIF}", wait_text="Rota'nın Yorumu")
        cgs.snap(page, "veli-hizli-butonlar", {
            "programButon": page.get_by_role("link", name="Haftalık Programı Gör").first,
            "konuButon": page.get_by_role("link", name="Konu Performansı").first,
            "denemeButon": page.get_by_role("link", name="Denemeler & Analiz").first,
            "seansButon": page.get_by_role("link", name="Seans Hareketleri").first,
        })

        # ---- 1) Haftalık Program ----
        cgs.goto(page, f"/parent/students/{ELIF}/week", wait_text="7 Günlük Program")
        time.sleep(1.0)
        pzt_kart = page.get_by_role("button").filter(
            has_text="Pazartesi").first.locator("xpath=..")
        cgs.snap(page, "veli-program-genel", {
            "hafta": pzt_kart,
            "gezinme": page.get_by_role("link", name="Bu hafta").first.locator("xpath=.."),
            "tamamRozeti": page.get_by_text("✓ tamamlandı").first,
        })
        # Perşembe kartına kaydır — dolu günün görev satırları
        per_btn = page.get_by_role("button").filter(has_text="Perşembe").first
        per_btn.scroll_into_view_if_needed()
        page.mouse.wheel(0, 120)
        time.sleep(0.8)
        gorev_satiri = page.get_by_text("Doğrusal Denklemler", exact=False).first.locator(
            "xpath=ancestor::li[1]")
        cgs.snap(page, "veli-program-gun", {
            "gunKarti": per_btn.locator("xpath=.."),
            "gorevSatiri": gorev_satiri,
            "gunOzeti": per_btn.get_by_text("görev", exact=False).first,
        })

        # ---- 2) Konu Performansı ----
        cgs.goto(page, f"/parent/students/{ELIF}/topics", wait_text="Konu Performansı")
        time.sleep(1.2)
        cgs.snap(page, "veli-konu-ozet", {
            "aciklama": page.get_by_text("Konu performansı", exact=False).first.locator(
                "xpath=ancestor::div[contains(@class,'rounded-lg')][1]"),
            "ozetKartlar": page.get_by_text("Genel doğruluk").first.locator(
                "xpath=ancestor::div[contains(@class,'grid')][1]"),
            "genelDogruluk": page.get_by_text("Genel doğruluk").first.locator("xpath=.."),
        })
        mat_kart = card_of(page, "Matematik")
        fen_kart = card_of(page, "Fen Bilimleri")
        cgs.snap(page, "veli-konu-dersler", {
            "matRozet": mat_kart.get_by_text("doğru", exact=False).first,
            "fenRozet": fen_kart.get_by_text("doğru", exact=False).first,
            "fenKart": fen_kart,
        })
        # Fen'i aç → Basınç kırmızı
        page.get_by_role("button").filter(has_text="Fen Bilimleri").first.click()
        time.sleep(0.8)
        basinc = page.get_by_text("Basınç", exact=False).first.locator(
            "xpath=ancestor::div[contains(@class,'rounded-lg')][1]")
        basinc.scroll_into_view_if_needed()
        time.sleep(0.5)
        cgs.snap(page, "veli-konu-fen-acik", {
            "basincSatiri": basinc,
            "mevsimlerSatiri": page.get_by_text("Mevsimler", exact=False).first.locator(
                "xpath=ancestor::div[contains(@class,'rounded-lg')][1]"),
        })
        # Fen'i kapat, Matematik'i aç
        page.get_by_role("button").filter(has_text="Fen Bilimleri").first.click()
        time.sleep(0.4)
        page.get_by_role("button").filter(has_text="Matematik").first.click()
        time.sleep(0.8)
        dogrusal = page.get_by_text("Doğrusal Denklemler", exact=False).first.locator(
            "xpath=ancestor::div[contains(@class,'rounded-lg')][1]")
        dogrusal.scroll_into_view_if_needed()
        time.sleep(0.5)
        cgs.snap(page, "veli-konu-mat-acik", {
            "dogrusalSatiri": dogrusal,
            "sonTarih": dogrusal.get_by_text("son:", exact=False).first,
        })

        # ---- 3) Denemeler & Analiz ----
        cgs.goto(page, f"/parent/students/{ELIF}/exams", wait_text="Deneme Geçmişi")
        time.sleep(1.5)
        cgs.snap(page, "veli-analiz-ozet", {
            "ozetKartlar": page.get_by_text("Ortalama net").first.locator(
                "xpath=ancestor::div[contains(@class,'grid')][1]"),
            "rotaKopru": page.get_by_text("yapay zekâ anlatımı", exact=False).first.locator(
                "xpath=ancestor::a[1]"),
            "sorButonu": page.get_by_role("link", name="Koça deneme hakkında sor").first,
        })
        # En yeni kart (karne importu — ders kırılımı çipleri)
        karne = card_of(page, "LGS DENEME SINAVI - 3")
        karne.scroll_into_view_if_needed()
        time.sleep(0.5)
        cgs.snap(page, "veli-analiz-karne", {
            "karneKarti": karne,
            "dersCipleri": karne.locator("div.flex.flex-wrap").last,
        })
        # LGS Deneme 6 — büyük net + D/Y/B
        lgs6 = card_of(page, "LGS Deneme 6")
        lgs6.scroll_into_view_if_needed()
        page.mouse.wheel(0, 60)
        time.sleep(0.5)
        brans = card_of(page, "Matematik Branş Denemesi 2")
        cgs.snap(page, "veli-analiz-kart", {
            "lgsKarti": lgs6,
            "netDegeri": lgs6.get_by_text("net", exact=True).first.locator("xpath=.."),
            "dyb": lgs6.get_by_text("B ", exact=False).first.locator("xpath=.."),
            "bransKarti": brans,
        })
        # Trend göstergesi (sayfa altı)
        trend = page.get_by_text("İlk denemeden bu yana", exact=False).first
        trend.scroll_into_view_if_needed()
        time.sleep(0.5)
        cgs.snap(page, "veli-analiz-trend", {
            "trendRozeti": trend.locator("xpath=.."),
            "sonKarne": card_of(page, "LGS Deneme 1"),
        })

        # ---- 4) Seans Hareketleri ----
        cgs.goto(page, f"/parent/students/{ELIF}/sessions", wait_text="Seans Hareketleri")
        time.sleep(1.5)
        cgs.snap(page, "veli-seans-genel", {
            "acikHesap": page.get_by_text("Tahakkuk", exact=False).first.locator(
                "xpath=ancestor::div[contains(@class,'rounded-lg')][1]"),
            "pencere": page.get_by_role("button", name="3 ay").first.locator("xpath=.."),
        })
        page.get_by_role("button", name="3 ay").first.click()
        time.sleep(1.5)
        aylik = page.get_by_text("Aylık Hesap").first.locator(
            "xpath=ancestor::section[1]")
        cgs.snap(page, "veli-seans-aylik", {
            "aylikTablo": aylik,
            "buAySatiri": aylik.get_by_role("row").nth(1),
            "seansListesi": page.get_by_text("Seans Listesi").first.locator(
                "xpath=ancestor::section[1]"),
            "ertelendiRozeti": page.get_by_text("Ertelendi").first,
        })
        odeme = page.get_by_text("Ödemeler", exact=True).first.locator(
            "xpath=ancestor::section[1]")
        odeme.scroll_into_view_if_needed()
        time.sleep(0.5)
        cgs.snap(page, "veli-seans-odeme", {
            "odemeler": odeme,
            "kismiOdeme": page.get_by_text("Kısmi ödeme", exact=False).first.locator(
                "xpath=ancestor::li[1]"),
        })

        browser.close()

    existing = {}
    if cgs.BOXES_PATH.exists():
        existing = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8"))
    existing.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKutular yazıldı: {cgs.BOXES_PATH}")
    for name, st in cgs.results:
        print(f"  {st}: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
