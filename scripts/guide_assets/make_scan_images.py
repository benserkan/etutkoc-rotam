"""Tarama demosu için kapak + içindekiler görseli (HTML → PNG, Playwright)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT = Path(__file__).parent
COVER = """<html><body style="margin:0;width:900px;height:1260px;font-family:Georgia,serif;
background:linear-gradient(160deg,#0f4c81,#1b7bbf 55%,#f4b400 55%,#f4b400 62%,#0f4c81 62%);color:#fff">
<div style="padding:70px 60px"><div style="font-size:34px;letter-spacing:6px;opacity:.9">KÂŞİF YAYINLARI</div>
<div style="margin-top:220px;font-size:92px;font-weight:bold;line-height:1.05">8. SINIF<br>İNGİLİZCE</div>
<div style="margin-top:30px;font-size:52px">SORU BANKASI</div>
<div style="margin-top:40px;display:inline-block;background:#f4b400;color:#0f4c81;padding:14px 28px;font-size:34px;font-weight:bold;border-radius:8px">LGS'YE HAZIRLIK</div></div></body></html>"""
UNITS = [("Friendship",5),("Teen Life",17),("In the Kitchen",29),("On the Phone",41),("The Internet",53),
         ("Adventures",65),("Tourism",77),("Chores",89),("Science",101),("Natural Forces",113),("Genel Tekrar Testleri",125)]
rows = "".join(f'<tr><td style="padding:14px 0;font-size:34px">{i+1}. Ünite — {n}</td><td style="text-align:right;font-size:34px">{p}</td></tr>' for i,(n,p) in enumerate(UNITS))
TOC = f"""<html><body style="margin:0;width:900px;height:1260px;font-family:Georgia,serif;background:#fffdf7;color:#1b2a3a">
<div style="padding:80px 70px"><div style="font-size:60px;font-weight:bold;border-bottom:4px solid #0f4c81;padding-bottom:14px">İÇİNDEKİLER</div>
<table style="width:100%;margin-top:40px;border-collapse:collapse">{rows}<tr><td style="padding:14px 0;font-size:34px">Cevap Anahtarı</td><td style="text-align:right;font-size:34px">137</td></tr></table></div></body></html>"""
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    pg = b.new_page(viewport={"width":900,"height":1260})
    for name, html in (("kapak", COVER), ("icindekiler", TOC)):
        pg.set_content(html); pg.screenshot(path=str(OUT/f"{name}.jpg"), type="jpeg", quality=88)
    b.close()
print("ok")
