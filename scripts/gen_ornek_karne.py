"""Rehber için örnek 'konu analizli sonuç karnesi' PDF'i (sentetik, Elif Kaya).

HTML → Chrome print-to-PDF (metin tabanlı, gerçek karne gibi). Çıktılar:
  - scripts/ornek_sonuc_karnesi.pdf          → rehberde GERÇEKTEN yüklenecek dosya
  - app/static/guide/shots/ornek-pdf.png     → "böyle bir belge" sahnesi (1440×900)
Konu adları gerçek LGS Matematik konuları — normalizasyon birebir eşlesin diye.
(PIL metin çizimi bu ortamda segfault veriyor → Playwright/Chrome kullanıldı.)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

ROWS = [
    (1, "Çarpanlar ve Katlar", "B", "B", "D"),
    (2, "Çarpanlar ve Katlar", "D", "D", "D"),
    (3, "Üslü İfadeler", "A", "C", "Y"),
    (4, "Üslü İfadeler", "C", "E", "Y"),
    (5, "Üslü İfadeler", "B", "—", "B"),
    (6, "Kareköklü İfadeler", "D", "D", "D"),
    (7, "Kareköklü İfadeler", "A", "A", "D"),
    (8, "Kareköklü İfadeler", "E", "B", "Y"),
    (9, "Veri Analizi", "C", "C", "D"),
    (10, "Veri Analizi", "B", "B", "D"),
    (11, "Basit Olayların Olma Olasılığı", "A", "D", "Y"),
    (12, "Basit Olayların Olma Olasılığı", "D", "D", "D"),
    (13, "Cebirsel İfadeler ve Özdeşlikler", "B", "B", "D"),
    (14, "Cebirsel İfadeler ve Özdeşlikler", "C", "C", "D"),
    (15, "Doğrusal Denklemler", "A", "A", "D"),
    (16, "Doğrusal Denklemler", "E", "—", "B"),
    (17, "Eşitsizlikler", "B", "D", "Y"),
    (18, "Eşitsizlikler", "C", "C", "D"),
    (19, "Üçgenler", "D", "D", "D"),
    (20, "Dönüşüm Geometrisi", "A", "A", "D"),
]

# İkinci karne (rehber Denemeler serisi, 2026-10-05): bir sonraki deneme.
# Üslü toparlanıyor; Veri Analizi bu kez yanlış (unutma sinyali). 15D 3Y 2B → 14,00
ROWS_4 = [
    (1, "Çarpanlar ve Katlar", "C", "C", "D"),
    (2, "Çarpanlar ve Katlar", "A", "A", "D"),
    (3, "Üslü İfadeler", "D", "D", "D"),
    (4, "Üslü İfadeler", "B", "B", "D"),
    (5, "Üslü İfadeler", "E", "A", "Y"),
    (6, "Kareköklü İfadeler", "B", "B", "D"),
    (7, "Kareköklü İfadeler", "C", "C", "D"),
    (8, "Kareköklü İfadeler", "A", "A", "D"),
    (9, "Veri Analizi", "D", "B", "Y"),
    (10, "Veri Analizi", "A", "—", "B"),
    (11, "Basit Olayların Olma Olasılığı", "B", "B", "D"),
    (12, "Basit Olayların Olma Olasılığı", "C", "C", "D"),
    (13, "Cebirsel İfadeler ve Özdeşlikler", "D", "D", "D"),
    (14, "Cebirsel İfadeler ve Özdeşlikler", "E", "E", "D"),
    (15, "Doğrusal Denklemler", "B", "B", "D"),
    (16, "Doğrusal Denklemler", "A", "A", "D"),
    (17, "Eşitsizlikler", "C", "E", "Y"),
    (18, "Eşitsizlikler", "D", "—", "B"),
    (19, "Üçgenler", "A", "A", "D"),
    (20, "Dönüşüm Geometrisi", "E", "E", "D"),
]

SONUC = {"D": ("Doğru", "#168250"), "Y": ("Yanlış", "#be3c3c"), "B": ("Boş", "#c88c14")}


def build_html(rows=None, title="LGS DENEME SINAVI - 3", tarih="19.07.2026", ozet=(13, 5, 2, "11,33")) -> str:
    rows = rows or ROWS
    tr = "\n".join(
        f"<tr><td>{no}</td><td class='k'>{konu}</td><td class='c'>{dc}</td>"
        f"<td class='c'>{oc}</td><td class='c' style='color:{SONUC[s][1]};font-weight:600'>{SONUC[s][0]}</td></tr>"
        for no, konu, dc, oc, s in rows
    )
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; color:#1e282e; background:#fff; }}
  .head {{ background:#0e6478; color:#fff; padding:26px 44px; }}
  .head h1 {{ font-size:26px; letter-spacing:1px; }}
  .head p {{ font-size:15px; color:#d8eef4; margin-top:6px; }}
  .meta {{ padding:16px 44px; font-size:14.5px; }}
  .sec {{ background:#eef4f6; color:#0e6478; font-weight:700; font-size:15px;
          padding:8px 44px; margin-top:8px; }}
  table {{ width:calc(100% - 88px); margin:8px 44px; border-collapse:collapse; font-size:12.5px; }}
  th {{ text-align:left; color:#69737a; font-weight:600; border-bottom:1.5px solid #c8d2d6;
        padding:4px 6px; }}
  td {{ padding:3.5px 6px; border-bottom:0.5px solid #e6ecee; }}
  td.k {{ width:46%; }} td.c {{ text-align:center; }}
  th.c {{ text-align:center; }}
  .foot {{ margin:14px 44px; font-size:11.5px; color:#69737a; }}
  .net {{ color:#0e6478; font-weight:700; }}
</style></head><body>
  <div class="head"><h1>KAREKÖK YAYINLARI</h1>
    <p>{title} &nbsp;·&nbsp; KONU ANALİZLİ SONUÇ KARNESİ</p></div>
  <div class="meta"><b>Öğrenci:</b> Elif Kaya &nbsp;&nbsp; <b>Sınıf:</b> 8-A
    &nbsp;&nbsp; <b>Sınav Tarihi:</b> {tarih}</div>
  <div class="sec">MATEMATİK</div>
  <table><thead><tr><th>No</th><th>Konu</th><th class="c">Doğru Cevap</th>
    <th class="c">Öğrenci Cevabı</th><th class="c">Sonuç</th></tr></thead>
    <tbody>{tr}</tbody></table>
  <div class="sec">DERS ÖZETİ</div>
  <table><thead><tr><th>Ders</th><th class="c">Soru</th><th class="c">Doğru</th>
    <th class="c">Yanlış</th><th class="c">Boş</th><th class="c">Net</th></tr></thead>
    <tbody><tr><td>Matematik</td><td class="c">20</td>
    <td class="c" style="color:#168250">{ozet[0]}</td><td class="c" style="color:#be3c3c">{ozet[1]}</td>
    <td class="c" style="color:#c88c14">{ozet[2]}</td><td class="c net">{ozet[3]}</td></tr>
    </tbody></table>
  <div class="foot">Net = Doğru − (Yanlış ÷ 3). Bu karne Karekök Yayınları
    değerlendirme sistemince üretilmiştir.</div>
</body></html>"""


def main() -> int:
    four = "--deneme4" in sys.argv
    html_path = ROOT / "scripts" / "_ornek_karne.html"
    if four:
        html_path.write_text(
            build_html(ROWS_4, "LGS DENEME SINAVI - 4", "02.10.2026", (15, 3, 2, "14,00")), encoding="utf-8"
        )
    else:
        html_path.write_text(build_html(), encoding="utf-8")
    pdf_name = "ornek_sonuc_karnesi_4.pdf" if four else "ornek_sonuc_karnesi.pdf"
    shot_name = "ornek-pdf-4.png" if four else "ornek-pdf.png"
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.goto(html_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(ROOT / "scripts" / pdf_name),
            format="A4", print_background=True,
        )
        # Sahne: belgenin üst kısmı, oynatıcı oranında
        page.screenshot(path=str(ROOT / "app" / "static" / "guide" / "shots" / shot_name))
        b.close()
    html_path.unlink(missing_ok=True)
    print(f"üretildi: scripts/{pdf_name} + shots/{shot_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
