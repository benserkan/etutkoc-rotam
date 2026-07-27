# -*- coding: utf-8 -*-
"""Veli rehberi ekran görüntüleri — GERÇEK veli panelinden (rehber-veli → Elif).

~24 sahne: Panel + çocuk detayı + Rota kartı UYGULAMALI (boş → yorumlat →
hazırlanıyor → yorum → seslendir → dinle; deneme sekmesi aynı zincir) +
Rota'ya Sor (karşılama/çipler → çip bas → düşünüyor → cevap → yaz → mikrofon →
KAYIT → çevrilmiş metin → cevabı dinle) + Haftalık Rapor + Hafta + Denemeler
sayfası + Koça Talep (doldur → gönder → listede) + Bildirimler + Ayarlar.

Önkoşul: :8081 + :3000 açık + refresh_guide_demo_parent koşulmuş.
GERÇEK Gemini kullanır (yorum 6+6 kredi, sohbet 3, TTS 2×2 — demo koç havuzu).

  PYTHONPATH=. python -m scripts.capture_guide_shots_parent
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
OWN_QUESTION = "Oğlum bu hafta ödevlerini yaptı mı?"


def login_veli(page):
    cgs.goto(page, "/login")
    page.locator('input[type="email"]').fill(VELI_EMAIL)
    page.locator('input[type="password"]').fill(cgs.PWD)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/parent**", timeout=120_000)
    time.sleep(1.5)


def rota_card(page):
    return page.get_by_text("Rota'nın Yorumu").first.locator(
        "xpath=ancestor::div[contains(@class,'rounded')][2]"
    )


def open_chat_tab(page):
    page.get_by_role("button", name="Rota'ya Sor").first.click()
    time.sleep(0.8)
    if page.get_by_placeholder("Rota'ya sor", exact=False).count() == 0:
        page.get_by_role("button", name="Rota'ya Sor").first.click()
        time.sleep(0.8)
    page.get_by_placeholder("Rota'ya sor", exact=False).first.wait_for(timeout=30_000)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
        ])
        ctx = browser.new_context(viewport={"width": cgs.VW, "height": cgs.VH})
        ctx.add_init_script(
            "const s=document.createElement('style');"
            "s.textContent='[class*=tsqd]{display:none!important}nextjs-portal{display:none!important}';"
            "document.addEventListener('DOMContentLoaded',()=>document.head.appendChild(s));"
        )
        page = ctx.new_page()
        login_veli(page)

        # ---- 1) Panel ----
        cgs.goto(page, "/parent", wait_text="Elif")
        card = page.get_by_text("Elif Kaya").first.locator(
            "xpath=ancestor::*[contains(@class,'rounded')][last()-1]")
        son_deneme = None
        if page.get_by_text("Son Deneme", exact=False).count():
            son_deneme = page.get_by_text("Son Deneme", exact=False).first.locator(
                "xpath=ancestor::div[contains(@class,'rounded')][1]")
        cgs.snap(page, "veli-panel", {
            "cocukKarti": card,
            **({"sonDeneme": son_deneme} if son_deneme else {}),
        })

        # ---- 2) Çocuk detayı ----
        cgs.goto(page, f"/parent/students/{ELIF}", wait_text="Rota'nın Yorumu")
        cgs.snap(page, "veli-cocuk-detay", {
            "rotaKart": rota_card(page),
            "raporButon": page.get_by_role("link", name="Haftalık Rapor").first,
        })

        # ---- 3) Rota kartı — Program zinciri (GERÇEK Gemini) ----
        yorumla = page.get_by_role("button", name="Rota yorumlasın").first
        cgs.snap(page, "veli-rota-bos", {
            "kart": rota_card(page),
            "yorumlaButon": yorumla,
        })
        yorumla.click()
        cgs.snap(page, "veli-rota-hazirlaniyor", settle=1.0)
        page.get_by_role("button", name="Rota seslendirsin").first.wait_for(timeout=120_000)
        time.sleep(0.8)
        bolumler = rota_card(page)
        cgs.snap(page, "veli-rota-yorum", {
            "bolumler": bolumler,
            "seslendirButon": page.get_by_role("button", name="Rota seslendirsin").first,
        })
        page.get_by_role("button", name="Rota seslendirsin").first.click()
        page.get_by_role("button", name="Dinle").first.wait_for(timeout=180_000)
        time.sleep(0.5)
        cgs.snap(page, "veli-rota-dinle", {
            "dinleButon": page.get_by_role("button", name="Dinle").first,
        })

        # ---- 4) Denemeler sekmesi zinciri ----
        deneme_tab = page.get_by_role("button", name="Denemeler").first
        deneme_tab.click()
        time.sleep(1.0)
        yorumla2 = page.get_by_role("button", name="Rota yorumlasın").first
        cgs.snap(page, "veli-deneme-bos", {
            "denemeSekme": deneme_tab,
            "yorumlaButon": yorumla2,
        })
        yorumla2.click()
        page.get_by_role("button", name="Rota seslendirsin").first.wait_for(timeout=120_000)
        time.sleep(0.8)
        cgs.snap(page, "veli-deneme-yorum", {
            "bolumler": rota_card(page),
            "seslendirButon": page.get_by_role("button", name="Rota seslendirsin").first,
        })

        # ---- 5) Denemeler & Analiz sayfası ----
        cgs.goto(page, f"/parent/students/{ELIF}/exams")
        time.sleep(1.5)
        cgs.snap(page, "veli-deneme-analiz")

        # ---- 6) Rota'ya Sor ----
        cgs.goto(page, f"/parent/students/{ELIF}", wait_text="Rota'nın Yorumu")
        open_chat_tab(page)
        greet = None
        bubbles = page.locator("div.rounded-2xl.rounded-tl-sm")
        if bubbles.count():
            greet = bubbles.first
        chips_row = page.get_by_role("button", name="Dün neler yapılmadı?").first.locator(
            "xpath=ancestor::div[1]")
        cgs.snap(page, "veli-sor-karsilama", {
            **({"karsilama": greet} if greet else {}),
            "cipler": chips_row,
        })
        # çip → düşünüyor → cevap
        page.get_by_role("button", name="Programa uyuyor mu?").first.click()
        cgs.snap(page, "veli-sor-dusunuyor", settle=0.6)
        page.get_by_text("Rota düşünüyor", exact=False).first.wait_for(
            state="detached", timeout=120_000)
        time.sleep(0.8)
        cevap = page.locator("div.rounded-2xl.rounded-tl-sm").last
        cgs.snap(page, "veli-sor-cevap", {"cevap": cevap})

        # kendi sorunu yaz
        inp = page.get_by_placeholder("Rota'ya sor", exact=False).first
        inp.fill("Matematikte durumu nasıl?")
        cgs.snap(page, "veli-sor-yaz", {
            "soruKutusu": inp,
            "mikrofon": page.get_by_title("Sesli sor", exact=False).first,
        })

        # mikrofon → kayıt karesi (fake mic; transcribe TETİKLENMEZ — reload ile iptal)
        inp.fill("")
        page.get_by_title("Sesli sor", exact=False).first.click()
        page.locator("button.bg-rose-600").first.wait_for(timeout=15_000)
        time.sleep(2.2)  # sayaç 0:02 göstersin
        cgs.snap(page, "veli-sor-kayit", {
            "kayitButon": page.locator("button.bg-rose-600").first,
        })
        page.reload()
        time.sleep(2.0)
        open_chat_tab(page)
        inp = page.get_by_placeholder("Rota'ya sor", exact=False).first
        inp.fill(OWN_QUESTION)
        cgs.snap(page, "veli-sor-cevrildi", {"soruKutusu": inp})

        # cevabı dinle (son rota balonu — ses yoksa GERÇEK TTS üretir)
        inp.fill("")
        dinle_btns = page.get_by_role("button", name="Dinle")
        dinle_btns.last.click()
        page.get_by_role("button", name="Duraklat").first.wait_for(timeout=180_000)
        time.sleep(0.6)
        cgs.snap(page, "veli-sor-dinle", {
            "dinleButon": page.get_by_role("button", name="Duraklat").first,
        })

        # ---- 7) Haftalık Rapor (BU haftaya gezin — dün taşındı, bu hafta zengin) ----
        cgs.goto(page, f"/parent/students/{ELIF}/report")
        time.sleep(2.0)
        nxt = page.locator("button:has(svg.lucide-chevron-right)")
        if nxt.count():
            try:
                nxt.first.click()
                time.sleep(2.0)
            except Exception:
                pass
        manset = None
        if page.get_by_text("önceki hafta", exact=False).count():
            manset = page.get_by_text("önceki hafta", exact=False).first.locator(
                "xpath=ancestor::div[contains(@class,'rounded')][1]")
        cgs.snap(page, "veli-rapor", {**({"manset": manset} if manset else {})})
        page.mouse.wheel(0, 700)
        dersler = None
        if page.get_by_text("aksatılan", exact=False).count():
            dersler = page.get_by_text("aksatılan", exact=False).first.locator(
                "xpath=ancestor::div[contains(@class,'rounded')][1]")
        cgs.snap(page, "veli-rapor-dersler", {**({"dersler": dersler} if dersler else {})})
        page.mouse.wheel(0, 900)
        cgs.snap(page, "veli-rapor-gunler")

        # ---- 8) Haftalık Program ----
        cgs.goto(page, f"/parent/students/{ELIF}/week")
        time.sleep(2.0)
        cgs.snap(page, "veli-hafta-program")

        # ---- 9) Koça Talep (uygulamalı) ----
        cgs.goto(page, "/parent/support")
        time.sleep(2.0)
        try:
            for name in ("Yeni Talep", "Yeni talep", "Talep oluştur", "Yeni"):
                btn = page.get_by_role("button", name=name)
                if btn.count():
                    btn.first.click()
                    break
            page.locator('[role="dialog"]').first.wait_for(timeout=10_000)
            dlg = page.locator('[role="dialog"]').first
            for sel in dlg.locator("select").all():
                try:
                    opts = sel.locator("option").all_inner_texts()
                    for i, o in enumerate(opts):
                        if "Elif" in o:
                            sel.select_option(index=i)
                except Exception:
                    pass
            subj = dlg.locator('input[type="text"]').first
            subj.fill("Deneme sonucu hakkında")
            dlg.locator("textarea").first.fill(
                "Merhaba hocam, Elif'in son denemesindeki matematik netini konuşmak istiyorum. "
                "Uygun olduğunuz bir gün kısaca görüşebilir miyiz?")
            cgs.snap(page, "veli-talep-form", {"form": dlg})
            for name in ("Gönder", "Oluştur", "Talep gönder"):
                b = dlg.get_by_role("button", name=name)
                if b.count():
                    b.first.click()
                    break
            dlg.wait_for(state="detached", timeout=15_000)
            time.sleep(1.5)
            talep = page.get_by_text("Deneme sonucu hakkında").first
            cgs.snap(page, "veli-talep-liste", {"talep": talep.locator(
                "xpath=ancestor::div[contains(@class,'rounded') or contains(@class,'border')][1]")})
        except Exception as e:  # noqa: BLE001
            print(f"  !! talep akışı: {e}")
            cgs.snap(page, "veli-talep-form")
            cgs.snap(page, "veli-talep-liste")

        # ---- 10) Bildirimler + Ayarlar ----
        cgs.goto(page, "/parent/notifications")
        time.sleep(1.5)
        cgs.snap(page, "veli-bildirimler")
        cgs.goto(page, "/parent/settings")
        time.sleep(1.5)
        cgs.snap(page, "veli-ayarlar")

        browser.close()

    # kutuları birleştirip yaz (cgs deseni)
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
