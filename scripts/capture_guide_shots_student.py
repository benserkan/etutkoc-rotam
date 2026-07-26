"""Öğrenci rehberi ekran görüntüleri — gerçek öğrenci panelinden (Elif).

25 sahne: Bugün (görev sonucu + günün notu + koça ilet) · Hafta · Kitaplarım
(detay + bağımsız çalışma) · Yanlış Soru Arşivi (liste + ekle + AI ipucu +
yeniden çözme) · Denemelerim (PDF aktar + özet + konu analizi + arşive köprü) ·
Gelişim (konu perf/tekrar/hedef/odak/DNA) · Talepler + Anketler.

Önkoşul: :8081 + :3000 açık + seed_guide_demo + seed_guide_demo_student koşulmuş.

  python -m scripts.capture_guide_shots_student
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

STUDENT_EMAIL = "rehber-elif@etutkoc.demo"


def ensure_student_guide_dismissed():
    """Öğrencinin karşılama diyaloğu kareleri kapatmasın."""
    from datetime import datetime, timezone

    from app.database import SessionLocal
    from app.models import UserGuideState

    with SessionLocal() as db:
        st = (
            db.query(UserGuideState)
            .filter_by(user_id=cgs.IDS["elif"], guide_key="student_onboarding")
            .one_or_none()
        )
        now = datetime.now(timezone.utc)
        if st is None:
            db.add(UserGuideState(
                user_id=cgs.IDS["elif"], guide_key="student_onboarding",
                status="dismissed", dismissed_at=now,
            ))
        else:
            st.status = "dismissed"
            st.dismissed_at = now
        db.commit()


def login_student(page):
    cgs.goto(page, "/login")
    try:
        page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(3.0)  # taze .next'te hydration — form JS'i bağlansın
    page.locator('input[type="email"]').fill(STUDENT_EMAIL)
    page.locator('input[type="password"]').fill(cgs.PWD)
    for _ in range(4):
        page.locator('button[type="submit"]').first.click()
        try:
            page.wait_for_url("**/student/**", timeout=30_000)
            break
        except Exception:  # noqa: BLE001
            if "/student/" in page.url:
                break
            time.sleep(2.0)
    time.sleep(1.5)


def close_dialog(page):
    page.keyboard.press("Escape")
    time.sleep(0.8)


def nav(page, path, wait=None, tries=3):
    """goto + hata toleransı (dev sunucusu ilk derlemede ERR_ABORTED verebilir)."""
    for i in range(tries):
        try:
            cgs.goto(page, path, wait)
            return
        except Exception as e:  # noqa: BLE001
            print(f"  nav tekrar ({path}, {i + 1}): {type(e).__name__}")
            time.sleep(3.0)
    cgs.goto(page, path, wait)


def card_of(loc):
    return loc.locator("xpath=ancestor::article[1]")


def main() -> int:
    ensure_student_guide_dismissed()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH},
            device_scale_factor=1, locale="tr-TR", color_scheme="light",
        )
        # Dev rozetleri (TanStack devtools palmiyesi + Next.js göstergesi)
        # ekran görüntülerine sızmasın.
        ctx.add_init_script(
            """
            (() => {
              const hide = () => {
                const st = document.createElement('style');
                st.textContent = '[class*="tsqd"],nextjs-portal{display:none!important}';
                document.head && document.head.appendChild(st);
              };
              if (document.readyState === 'loading')
                document.addEventListener('DOMContentLoaded', hide);
              else hide();
            })();
            """
        )
        page = ctx.new_page()
        page.route("**/me/panel-visits", lambda r: r.abort())
        login_student(page)

        # ---------------- BUGÜN ----------------
        nav(page, "/student/day", "Günün notu")
        header = page.locator("header").first
        video = page.get_by_text("Doğrusal denklemler konu videosu", exact=False).first
        cgs.snap(page, "ogr-bugun", {
            "ust-menu": header,
            "video-gorev": card_of(video),
        }, settle=1.5)

        done = page.get_by_text("Kareköklü İfadeler", exact=False).first
        done.scroll_into_view_if_needed()
        cgs.snap(page, "ogr-gorev-sonuc", {"sonuc-alani": card_of(done)}, settle=0.8)

        note = page.get_by_text("Günün notu", exact=False).first
        note.scroll_into_view_if_needed()
        note_card = page.locator("textarea").first.locator("xpath=ancestor::div[2]")
        cgs.snap(page, "ogr-gun-notu", {"not-kutusu": note_card}, settle=0.8)

        # Koça ilet — video görevinin ⋯ menüsünden "Koçuna sor"
        try:
            page.keyboard.press("Home")
            time.sleep(0.5)
            menu_btn = card_of(video).locator('button[aria-label="Görev eylemleri"]').first
            menu_btn.click()
            time.sleep(0.6)
            page.get_by_text("Koçuna sor", exact=False).first.click()
            time.sleep(1.2)
            cgs.snap(page, "ogr-talep-dialog", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  talep dialog: {e}")

        # ---------------- HAFTA + KİTAPLAR ----------------
        nav(page, "/student/week")
        cgs.snap(page, "ogr-hafta", settle=1.5)

        nav(page, "/student/books", "Kitaplarım")
        cgs.snap(page, "ogr-kitaplar", settle=1.2)

        try:
            page.get_by_text("Bağımsız çalışma bildir", exact=False).first.click()
            time.sleep(1.2)
            cgs.snap(page, "ogr-bagimsiz", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  bağımsız dialog: {e}")

        nav(page, f"/student/books/{cgs.IDS['book']}", "3D LGS")
        cgs.snap(page, "ogr-kitap-detay", settle=1.5)

        # ---------------- YANLIŞ SORU ARŞİVİ ----------------
        nav(page, "/student/wrong-questions", "Yanlış")
        cgs.snap(page, "ogr-yanlislar", settle=1.5)

        try:
            page.get_by_text("Yanlış ekle", exact=False).first.click()
            time.sleep(1.2)
            cgs.snap(page, "ogr-yanlis-ekle", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  yanlış ekle dialog: {e}")

        try:
            # AI ipuçlu kart (Üslü İfadeler — wq1)
            page.get_by_text("Üslü İfadeler", exact=False).first.click()
            time.sleep(1.2)
            page.get_by_text("Yaklaşım ipucu", exact=False).first.scroll_into_view_if_needed()
            cgs.snap(page, "ogr-ai-ipucu", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  ai ipucu dialog: {e}")

        try:
            for label in ("Çözmeye başla", "Kendini dene"):
                btn = page.get_by_text(label, exact=False)
                if btn.count() > 0:
                    btn.first.click()
                    break
            time.sleep(1.4)
            cgs.snap(page, "ogr-yeniden-coz", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  yeniden çöz: {e}")

        # ---------------- DENEMELERİM ----------------
        nav(page, "/student/exams", "Konu Analizi")
        cgs.snap(page, "ogr-denemeler", settle=2.0)

        try:
            page.get_by_text("PDF'ten aktar", exact=False).first.click()
            time.sleep(1.2)
            cgs.snap(page, "ogr-deneme-pdf", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  pdf dialog: {e}")

        try:
            strip = page.get_by_text("Ortalama net", exact=False).first.locator(
                "xpath=ancestor::section[1]"
            )
            strip.scroll_into_view_if_needed()
            cgs.snap(page, "ogr-net-trend", {"net-trend": strip}, settle=0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  özet şeridi: {e}")

        try:
            analiz = page.get_by_text("Konu Analizi", exact=False).first.locator(
                "xpath=ancestor::div[1]"
            )
            analiz.scroll_into_view_if_needed()
            time.sleep(0.6)
            cgs.snap(page, "ogr-konu-analiz", {"analiz-alani": analiz}, settle=0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  konu analizi: {e}")

        try:
            arsiv = page.locator('[aria-label="Yanlışlardan arşive soru seç"]').first
            arsiv.scroll_into_view_if_needed()
            time.sleep(0.6)
            cgs.snap(page, "ogr-deneme-arsiv", {"arsiv-btn": arsiv}, settle=0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  arşiv butonu: {e}")

        # ---------------- GELİŞİM ----------------
        for path, name, wait in (
            ("/student/topics", "ogr-konu-perf", "Matematik"),
            ("/student/review", "ogr-tekrar", "Tekrar"),
            ("/student/goals", "ogr-hedefler", "Hedef"),
            ("/student/focus", "ogr-odak", "Seans"),
            ("/student/dna", "ogr-dna", "DNA"),
            ("/student/requests", "ogr-talepler", "Talep"),
            ("/student/surveys", "ogr-anketler", "Anket"),
        ):
            cgs.goto(page, path, wait)
            cgs.snap(page, name, settle=1.6)

        try:
            page.locator('a[href^="/student/surveys/"]').first.click()
            page.wait_for_url("**/student/surveys/**", timeout=60_000)
            page.get_by_text("Kaydet", exact=False).first.wait_for(timeout=60_000)
            time.sleep(1.5)
            cgs.snap(page, "ogr-anket-doldur", settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  anket doldurma: {e}")

        browser.close()

    existing = {}
    if cgs.BOXES_PATH.exists():
        existing = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8"))
    existing.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nshot-boxes.json güncellendi ({len(cgs.boxes_out)} sahne).")
    for name, st in cgs.results:
        print(f"  {st}: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
