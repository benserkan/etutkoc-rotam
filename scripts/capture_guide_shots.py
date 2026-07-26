"""Rehber ekran görüntüsü yakalayıcı — gerçek panelden, Playwright + Chrome.

Rota rehberinin sahneleri UYDURMA DEĞİL: demo koç hesabıyla (seed_guide_demo)
gerçek panelde gezinip 1440×900 sabit görünümde ekran görüntüsü alır ve vurgu
kutularının (buton/panel) yüzde koordinatlarını shot-boxes.json'a yazar.
Oynatıcı sahne alanı aynı oranda olduğundan kutular birebir oturur.

Önkoşul: :8081 + :3000 dev sunucuları açık + seed_guide_demo koşulmuş.

  python -m scripts.capture_guide_shots            # tümü
  python -m scripts.capture_guide_shots --only kutuphane,panel
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

ROOT = Path(__file__).resolve().parent.parent
SHOTS_DIR = ROOT / "app" / "static" / "guide" / "shots"
BOXES_PATH = ROOT / "web" / "components" / "guide" / "shot-boxes.json"
IDS = json.loads((ROOT / "scripts" / "guide_demo_ids.json").read_text())

BASE = "http://127.0.0.1:3000"
VW, VH = 1440, 900
EMAIL = "rehber-koc@etutkoc.demo"
PWD = "RehberDemo2026!"

boxes_out: dict[str, dict] = {}
results: list[tuple[str, str]] = []


def pct_box(b: dict, pad: float = 6) -> dict:
    """Piksel bbox → yüzde kutu (hafif iç boşlukla)."""
    x = max(0.0, (b["x"] - pad) / VW * 100)
    y = max(0.0, (b["y"] - pad) / VH * 100)
    w = min(100 - x, (b["width"] + 2 * pad) / VW * 100)
    h = min(100 - y, (b["height"] + 2 * pad) / VH * 100)
    return {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)}


def snap(page: Page, name: str, targets: dict[str, object] | None = None, settle: float = 1.2):
    time.sleep(settle)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS_DIR / f"{name}.png"))
    entry: dict = {"targets": {}}
    for key, loc in (targets or {}).items():
        try:
            b = loc.bounding_box()  # type: ignore[union-attr]
            if b:
                entry["targets"][key] = pct_box(b)
        except Exception as e:  # noqa: BLE001
            print(f"    kutu alınamadı ({name}/{key}): {e}")
    boxes_out[name] = entry
    results.append((name, "OK"))
    print(f"  ✓ {name}.png ({len(entry['targets'])} kutu)")


def goto(page: Page, path: str, wait_text: str | None = None):
    page.goto(BASE + path, timeout=120_000, wait_until="domcontentloaded")
    if wait_text:
        page.get_by_text(wait_text, exact=False).first.wait_for(timeout=60_000)
    time.sleep(1.0)


def login(page: Page):
    goto(page, "/login")
    page.locator('input[type="email"]').fill(EMAIL)
    page.locator('input[type="password"]').fill(PWD)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_url("**/teacher/dashboard**", timeout=120_000)
    time.sleep(1.5)


def ensure_guide_dismissed():
    """Karşılama diyaloğu ekran görüntülerini kapatmasın — demo koçun rehber
    durumu 'dismissed' yapılır (yakalama sonrası sıfırlanabilir)."""
    from datetime import datetime, timezone

    from app.database import SessionLocal
    from app.models import UserGuideState

    with SessionLocal() as db:
        st = (
            db.query(UserGuideState)
            .filter_by(user_id=IDS["coach"], guide_key="coach_onboarding")
            .one_or_none()
        )
        now = datetime.now(timezone.utc)
        if st is None:
            db.add(UserGuideState(
                user_id=IDS["coach"], guide_key="coach_onboarding",
                status="dismissed", dismissed_at=now,
            ))
        else:
            st.status = "dismissed"
            st.dismissed_at = now
        db.commit()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None

    def want(*names: str) -> bool:
        return only is None or any(n in only for n in names)

    elif_id = IDS["elif"]

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": VW, "height": VH},
            device_scale_factor=1,
            locale="tr-TR",
            color_scheme="light",
        )
        page = ctx.new_page()
        print("Giriş yapılıyor…")
        ensure_guide_dismissed()
        login(page)

        # --- panel + ogrenciler + kutuphane -----------------------------------
        if want("panel"):
            goto(page, "/teacher/dashboard", "Pano")
            snap(page, "panel", settle=2.5)

        if want("ogrenciler"):
            goto(page, "/teacher/students", "Elif")
            targets = {
                "nav-ogrenciler": page.locator("aside").get_by_text("Öğrenciler", exact=True).first,
                "yeni-ogrenci": page.get_by_text("Yeni öğrenci", exact=False).first,
            }
            snap(page, "ogrenciler", targets, settle=2.0)

        if want("kutuphane"):
            goto(page, "/teacher/library", "Yeni kitap")
            targets = {
                "nav-kitaplar": page.locator("aside").get_by_text("Kitaplar", exact=True).first,
                "yeni-kitap": page.get_by_text("Yeni kitap", exact=False).first,
            }
            snap(page, "kutuphane", targets, settle=2.0)

        # --- kitap sihirbazı ---------------------------------------------------
        if want("sihirbaz-bilgiler", "sihirbaz-uniteler", "sihirbaz-eslestirme", "sihirbaz-ozet"):
            try:
                goto(page, "/teacher/library/new", "Bilgiler")
                name_input = page.get_by_role("textbox").first
                subj_select = page.locator("select").first
                snap(page, "sihirbaz-bilgiler", {"sihirbaz-ders": subj_select}, settle=2.0)

                # Adım 2'ye geç: gerçek kitap oluştur (demo koçun kütüphanesine)
                name_input.fill("Karekök LGS Matematik Soru Bankası")
                val = subj_select.evaluate(
                    "el => { const o = Array.from(el.options).find(o => o.text.includes('Matematik'));"
                    " return o ? o.value : null; }"
                )
                if val:
                    subj_select.select_option(val)
                page.get_by_role("button", name="Oluştur").first.click()
                page.get_by_text("Üniteler", exact=False).first.wait_for(timeout=60_000)
                snap(page, "sihirbaz-uniteler", settle=2.0)

                # Resmi konulardan ekle görünüyorsa aç (görsel zenginlik)
                try:
                    page.get_by_text("Resmi konulardan", exact=False).first.click(timeout=4_000)
                    time.sleep(1.2)
                    page.screenshot(path=str(SHOTS_DIR / "sihirbaz-uniteler.png"))
                    print("  ✓ sihirbaz-uniteler.png (katalog açık)")
                except Exception:
                    pass

                # Devam → Eşleştirme → Devam → Öğrenci/Özet (best-effort)
                try:
                    page.get_by_role("button", name="Devam").first.click(timeout=6_000)
                    time.sleep(1.5)
                    snap(page, "sihirbaz-eslestirme", settle=1.5)
                    page.get_by_role("button", name="Devam").first.click(timeout=6_000)
                    time.sleep(1.5)
                    snap(page, "sihirbaz-ozet", settle=1.5)
                except Exception as e:
                    print(f"    sihirbaz ileri adımları atlandı: {e}")
                    results.append(("sihirbaz-eslestirme", f"SKIP {e}"))
            except Exception as e:
                print(f"  ✗ sihirbaz: {e}")
                results.append(("sihirbaz-bilgiler", f"FAIL {e}"))

        # --- öğrenci detayı + kitaplar ----------------------------------------
        if want("ogrenci-detay", "ogrenci-kitaplar", "ogrenci-kitap-detay", "durum-ozeti"):
            goto(page, f"/teacher/students/{elif_id}", "Elif Kaya")
            try:
                tabs = page.locator('[aria-label="Öğrenci paneli sekmeleri"]').first
                tabs.wait_for(timeout=8_000)
                snap(page, "ogrenci-detay", {"ogrenci-sekmeler": tabs}, settle=2.0)
            except Exception:
                snap(page, "ogrenci-detay", settle=2.0)
            try:
                page.get_by_text("Durum Özeti", exact=False).first.scroll_into_view_if_needed(
                    timeout=6_000
                )
            except Exception:
                pass
            snap(page, "durum-ozeti", settle=0.8)

            try:
                try:
                    page.get_by_role("tab", name="Kitaplar").first.click(timeout=8_000)
                except Exception:
                    page.get_by_text("Kitaplar", exact=True).last.click(timeout=8_000)
                time.sleep(2.0)
                try:
                    kitap_ata = page.get_by_text("Kitap ata", exact=False).first
                    snap(page, "ogrenci-kitaplar", {"kitap-ata": kitap_ata}, settle=1.0)
                except Exception:
                    snap(page, "ogrenci-kitaplar", settle=1.0)
            except Exception as e:
                print(f"    ogrenci-kitaplar atlandı: {e}")
                results.append(("ogrenci-kitaplar", f"SKIP {e}"))

            # Kitap detayı (bölüm satırları) — kitap adına tıkla
            try:
                page.get_by_text("3D LGS Matematik", exact=False).first.click(timeout=6_000)
                time.sleep(1.5)
                snap(page, "ogrenci-kitap-detay", settle=1.0)
                page.keyboard.press("Escape")
            except Exception as e:
                print(f"    ogrenci-kitap-detay atlandı: {e}")
                results.append(("ogrenci-kitap-detay", f"SKIP {e}"))

        # --- haftalık program --------------------------------------------------
        if want("hafta", "gorev-ekle", "kaynak-durumu", "hafta-izgara", "yayinla", "veliye-duyur"):
            goto(page, f"/teacher/students/{elif_id}/week", "Kaynak Durumu")
            time.sleep(2.0)
            snap(page, "hafta", settle=1.5)

            # Kaynak Durumu paneli
            try:
                kd = page.get_by_text("Kaynak Durumu", exact=False).first
                panel = kd.locator(
                    "xpath=ancestor::*[contains(@class,'rounded') and contains(@class,'border')][1]"
                )
                snap(page, "kaynak-durumu", {"kaynak-panel": panel}, settle=0.5)
            except Exception:
                snap(page, "kaynak-durumu", settle=0.5)

            # Hafta ızgarası
            try:
                grid = page.get_by_text("Hafta Izgarası", exact=False).first
                grid.scroll_into_view_if_needed(timeout=6_000)
                snap(page, "hafta-izgara", settle=1.0)
                page.keyboard.press("Home")
            except Exception as e:
                print(f"    hafta-izgara: {e}")
                results.append(("hafta-izgara", f"SKIP {e}"))

            # Görev ekle formu
            try:
                btn = page.get_by_text("Yeni görev ekle", exact=False).first
                btn.scroll_into_view_if_needed(timeout=8_000)
                btn.click()
                time.sleep(1.5)
                form = page.locator("form").last
                snap(page, "gorev-ekle", {"gorev-ekle-form": form}, settle=0.8)
                page.keyboard.press("Escape")
            except Exception as e:
                print(f"    gorev-ekle: {e}")
                results.append(("gorev-ekle", f"SKIP {e}"))

            # Yayınla + Veliye duyur
            page.keyboard.press("Home")
            time.sleep(0.8)
            try:
                pub = page.get_by_text("Tüm haftayı yayınla", exact=False).first
                snap(page, "yayinla", {"yayinla-btn": pub}, settle=0.8)
            except Exception as e:
                print(f"    yayinla: {e}")
                results.append(("yayinla", f"SKIP {e}"))
            try:
                page.get_by_text("Veliye duyur", exact=False).first.click(timeout=6_000)
                page.get_by_text("önizleme", exact=False).first.wait_for(timeout=20_000)
                snap(page, "veliye-duyur", settle=1.5)
                page.keyboard.press("Escape")
            except Exception as e:
                print(f"    veliye-duyur: {e}")
                results.append(("veliye-duyur", f"SKIP {e}"))

        # --- gün takibi + pano uyarı -------------------------------------------
        if want("gun-takip"):
            goto(page, f"/teacher/students/{elif_id}/day")
            snap(page, "gun-takip", settle=2.5)

        if want("pano-uyari"):
            goto(page, "/teacher/dashboard", "Pano")
            try:
                page.get_by_text("Uyarı", exact=False).first.scroll_into_view_if_needed(timeout=8_000)
            except Exception:
                pass
            snap(page, "pano-uyari", settle=1.5)

        # --- denemeler ----------------------------------------------------------
        if want("denemeler", "deneme-pdf", "deneme-analiz"):
            goto(page, f"/teacher/students/{elif_id}", "Elif Kaya")
            try:
                page.get_by_role("tab", name="Denemeler").first.click(timeout=8_000)
            except Exception:
                page.get_by_text("Denemeler", exact=True).last.click(timeout=8_000)
            time.sleep(2.5)
            try:
                targets = {
                    "deneme-ekle": page.get_by_text("Deneme Ekle", exact=False).first,
                    "pdf-aktar": page.get_by_text("PDF'ten aktar", exact=False).first,
                }
                snap(page, "denemeler", targets, settle=1.0)
            except Exception:
                snap(page, "denemeler", settle=1.0)

            try:
                page.get_by_text("PDF'ten aktar", exact=False).first.click(timeout=6_000)
                time.sleep(1.5)
                snap(page, "deneme-pdf", settle=1.0)
                page.keyboard.press("Escape")
                time.sleep(0.8)
            except Exception as e:
                print(f"    deneme-pdf: {e}")
                results.append(("deneme-pdf", f"SKIP {e}"))

            try:
                page.get_by_text("Konu", exact=False).nth(0).scroll_into_view_if_needed(timeout=6_000)
                for txt in ("Net fırsatı", "Isı haritası", "Konu ×", "fırsat"):
                    try:
                        page.get_by_text(txt, exact=False).first.scroll_into_view_if_needed(timeout=3_000)
                        break
                    except Exception:
                        continue
                snap(page, "deneme-analiz", settle=1.0)
            except Exception as e:
                print(f"    deneme-analiz: {e}")
                results.append(("deneme-analiz", f"SKIP {e}"))

        browser.close()

    # Kutuları birleştirilmiş yaz (önceki koşuların kutularını koru)
    existing: dict = {}
    if BOXES_PATH.exists():
        try:
            existing = json.loads(BOXES_PATH.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    existing.update(boxes_out)
    BOXES_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"\nKutular yazıldı: {BOXES_PATH}")
    fails = [r for r in results if r[1] != "OK"]
    print(f"Toplam: {len([r for r in results if r[1] == 'OK'])} OK · {len(fails)} atlanan/hata")
    for n, s in fails:
        print(f"  - {n}: {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
