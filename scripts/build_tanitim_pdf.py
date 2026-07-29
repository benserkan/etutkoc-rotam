# -*- coding: utf-8 -*-
"""ETÜTKOÇ Rotam — tanıtım kılavuzu (HTML → PDF, Chrome print).

Çıktı: docs/rotam-tanitim-kilavuzu.pdf (+ Desktop kopyası) ve kaynak HTML.
Görseller: app/static/guide/shots + scratchpad/docshots + scratchpad/video/kurum
"""
from __future__ import annotations

import sys, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import scripts.tanitim_doc_content as C

ROOT = Path(__file__).resolve().parent.parent
SCR = Path(__file__).resolve().parent.parent / ".doc-build"
SCR.mkdir(exist_ok=True)
SRC_DIRS = {
    "guide": ROOT / "app" / "static" / "guide" / "shots",
    "docs": SCR / "docshots",
    "kurum": SCR / "video" / "kurum",
}
OUT_DIR = ROOT / "docs"
OUT_DIR.mkdir(exist_ok=True)
HTML = SCR / "tanitim.html"
PDF = OUT_DIR / "rotam-tanitim-kilavuzu.pdf"
LOGO = (ROOT / "web" / "public" / "etutkoc-logo.svg").as_uri()
MARK = (ROOT / "web" / "public" / "etutkoc-mark.svg").as_uri()


from PIL import Image

PREP = SCR / "prepshots"
PREP.mkdir(exist_ok=True)
# Koç/kurum ekranlarında sol menü çubuğu içeriği daraltıyor → kırp.
# Modal kareleri hariç (içerik zaten ortada).
SKIP_CROP = {"deneme-pdf.png", "aktar-tablo.png", "aktar-kayit.png",
             "ogr-yanlis-ekle.png", "ogr-ai-ipucu.png", "ogr-talep-doldur.png",
             "veli-talep-form.png"}
SIDEBAR_X = 238
BADGES = [(6, 830, 76, 898), (1366, 828, 1440, 898)]


def prep(name: str, src: str, path: Path) -> Path:
    """Sol menüyü kırp + köşe rozetlerini temizle; hazır kopyayı döndür."""
    out = PREP / f"{src}-{name}"
    if out.exists():
        return out
    im = Image.open(path).convert("RGB")
    for (x0, y0, x1, y1) in BADGES:
        if x1 <= im.width and y1 <= im.height:
            sample = im.getpixel(((x0 + x1) // 2, max(0, y0 - 10)))
            im.paste(sample, (x0, y0, x1, y1))
    sidebar = (not name.startswith(("ogr-", "veli-"))) and name not in SKIP_CROP
    if sidebar and im.width > SIDEBAR_X + 400:
        im = im.crop((SIDEBAR_X, 0, im.width, im.height))
    im.save(out)
    return out

missing: list[str] = []


def img_uri(name: str | None, src: str) -> str | None:
    if not name:
        return None
    p = SRC_DIRS[src] / name
    if not p.exists():
        missing.append(f"{src}/{name}")
        return None
    return prep(name, src, p).as_uri()


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


ROLE_COLOR = {
    "Koça": "#0e7490", "Öğrenciye": "#7c3aed", "Veliye": "#b45309",
    "Kuruma": "#0f766e", "Öğrenciye ve veliye": "#7c3aed",
}


def feature_html(f: dict, idx: int) -> str:
    uri = img_uri(f["img"], f["src"])
    bens = "".join(
        f'<li><span class="who" style="background:{ROLE_COLOR.get(who, "#334155")}">{esc(who)}</span>'
        f'<span class="ben">{esc(txt)}</span></li>'
        for who, txt in f["benefits"]
    )
    shot = (f'<figure><img src="{uri}" alt=""><figcaption>{esc(f["cap"] or "")}</figcaption></figure>'
            if uri else "")
    note = f'<p class="note">{esc(f["note"])}</p>' if f.get("note") else ""
    return f"""
<article class="feat">
  <h3><span class="fnum">{idx}</span>{esc(f['title'])}</h3>
  <p class="what">{esc(f['what'])}</p>
  <div class="bens"><h4>Ne kazandırır?</h4><ul>{bens}</ul></div>
  {note}{shot}
</article>"""


def groups_html(groups, start_idx=1) -> tuple[str, int]:
    out, i = [], start_idx
    for gtitle, gdesc, feats in groups:
        out.append(f'<div class="grp"><h2 class="gtitle">{esc(gtitle)}</h2>'
                   f'<p class="gdesc">{esc(gdesc)}</p></div>')
        for f in feats:
            out.append(feature_html(f, i))
            i += 1
    return "".join(out), i


def section(sid: str, kicker: str, title: str, lead: str, body: str, tone: str) -> str:
    return f"""
<section class="sec" id="{sid}" data-tone="{tone}">
  <div class="sechead">
    <span class="kicker">{esc(kicker)}</span>
    <h1>{esc(title)}</h1>
    <p class="lead">{esc(lead)}</p>
  </div>
  {body}
</section>"""


# ---------------------------------------------------------------- bölümler
coach_body, n = groups_html(C.COACH_GROUPS, 1)
stu_body, n = groups_html(C.STUDENT_GROUPS, n)
par_body, n = groups_html(C.PARENT_GROUPS, n)
inst_body, n = groups_html(C.INST_GROUPS, n)

intro_problems = "".join(
    f'<div class="pcard"><h4>{esc(t)}</h4><p>{esc(d)}</p></div>'
    for t, d in C.INTRO["problems"])
intro_cycle = "".join(
    f'<li><span class="cyc">{i+1}</span><b>{esc(t)}</b><span>{esc(d)}</span></li>'
    for i, (t, d) in enumerate(C.INTRO["cycle"]))
intro_aud = "".join(
    f'<div class="acard"><h4>{esc(t)}</h4><p>{esc(d)}</p></div>'
    for t, d in C.INTRO["audiences"])

ai_uses = "".join(
    f'<div class="pcard"><h4>{esc(t)}</h4><p>{esc(d)}</p></div>'
    for t, d in C.AI_SECTION["uses"])
ai_limits = "".join(f"<li>{esc(x)}</li>" for x in C.AI_SECTION["limits"])
ai_priv = "".join(
    f'<li><b>{esc(t)}</b> {esc(d)}</li>' for t, d in C.AI_SECTION["privacy"])

mob_items = "".join(
    f'<div class="acard"><h4>{esc(t)}</h4><p>{esc(d)}</p></div>'
    for t, d in C.MOBILE["items"])
start_steps = "".join(
    f'<li><span class="cyc">{i+1}</span><b>{esc(t)}</b><span>{esc(d)}</span></li>'
    for i, (t, d) in enumerate(C.START["steps"]))

TOC = [
    ("Rotam nedir?", "s-giris"),
    ("Koç için — planlamadan tahsilata", "s-koc"),
    ("Öğrenci için — günlük akış ve kendi verisi", "s-ogrenci"),
    ("Veli için — anlaşılır ve şeffaf takip", "s-veli"),
    ("Kurum için — ölçülebilir yönetim", "s-kurum"),
    ("Yapay zekâ ve veri güvenliği", "s-ai"),
    ("Mobil uygulama", "s-mobil"),
    ("Nasıl başlanır?", "s-basla"),
]
toc_html = "".join(
    f'<li><span class="tnum">{i+1}</span><span class="ttitle">{esc(t)}</span></li>'
    for i, (t, _a) in enumerate(TOC))

html = f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<title>ETÜTKOÇ Rotam — Tanıtım Kılavuzu</title>
<style>
  @page {{ size: A4; margin: 16mm 14mm 18mm 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:"Segoe UI",system-ui,sans-serif; color:#0f172a;
         font-size:10.6pt; line-height:1.55; }}
  h1,h2,h3,h4 {{ margin:0; }}

  /* ---------- kapak ---------- */
  .cover {{ height:257mm; display:flex; flex-direction:column; justify-content:center;
            page-break-after:always; background:linear-gradient(150deg,#ecfeff,#f8fafc 55%,#fef3c7);
            margin:-16mm -14mm 0 -14mm; padding:0 22mm; }}
  .cover img.logo {{ height:26mm; margin-bottom:12mm; }}
  .cover h1 {{ font-size:34pt; line-height:1.1; color:#0e7490; letter-spacing:-.5px; }}
  .cover .sub {{ font-size:15pt; color:#334155; margin-top:7mm; max-width:150mm; line-height:1.5; }}
  .cover .meta {{ margin-top:18mm; font-size:10pt; color:#475569; }}
  .cover .badge {{ display:inline-block; background:#0e7490; color:#fff; font-weight:700;
                   padding:3mm 7mm; border-radius:99px; font-size:11pt; margin-top:10mm; }}

  /* ---------- içindekiler ---------- */
  .toc {{ page-break-after:always; }}
  .toc h2 {{ font-size:19pt; color:#0e7490; margin-bottom:6mm; }}
  .toc ol {{ list-style:none; padding:0; margin:0; }}
  .toc li {{ display:flex; gap:5mm; align-items:baseline; padding:3.2mm 0;
             border-bottom:1px solid #e2e8f0; font-size:12pt; }}
  .tnum {{ width:9mm; height:9mm; flex:0 0 9mm; border-radius:50%; background:#0e7490;
           color:#fff; font-weight:800; font-size:10pt; display:inline-flex;
           align-items:center; justify-content:center; }}
  .ttitle {{ font-weight:600; }}

  /* ---------- bölüm ---------- */
  .sec {{ page-break-before:always; }}
  .sechead {{ border-left:5px solid #0e7490; padding:0 0 0 6mm; margin-bottom:8mm; }}
  .sec[data-tone="violet"] .sechead {{ border-color:#7c3aed; }}
  .sec[data-tone="amber"]  .sechead {{ border-color:#b45309; }}
  .sec[data-tone="teal"]   .sechead {{ border-color:#0f766e; }}
  .kicker {{ font-size:9pt; font-weight:800; letter-spacing:1.2px; text-transform:uppercase;
             color:#0e7490; }}
  .sec[data-tone="violet"] .kicker {{ color:#7c3aed; }}
  .sec[data-tone="amber"]  .kicker {{ color:#b45309; }}
  .sec[data-tone="teal"]   .kicker {{ color:#0f766e; }}
  .sechead h1 {{ font-size:24pt; margin:2mm 0 3mm; letter-spacing:-.3px; }}
  .lead {{ font-size:11.4pt; color:#334155; margin:0; max-width:165mm; }}

  .grp {{ margin:9mm 0 5mm; page-break-after:avoid; }}
  .gtitle {{ font-size:14.5pt; color:#0f172a; padding-bottom:2mm;
             border-bottom:2px solid #e2e8f0; }}
  .gdesc {{ font-size:10.4pt; color:#64748b; margin:2.5mm 0 0; }}

  /* ---------- özellik ---------- */
  .feat {{ page-break-inside:avoid; margin:0 0 7mm; padding:4.5mm 5mm;
           border:1px solid #e2e8f0; border-radius:3mm; background:#fff; }}
  .feat h3 {{ font-size:12.6pt; display:flex; gap:3mm; align-items:baseline; }}
  .fnum {{ background:#ecfeff; color:#0e7490; font-size:9pt; font-weight:800;
           border-radius:99px; padding:.6mm 2.6mm; flex:0 0 auto; }}
  .what {{ margin:2.5mm 0 0; color:#334155; }}
  .bens {{ margin-top:3.5mm; background:#f8fafc; border-radius:2mm; padding:3mm 3.5mm; }}
  .bens h4 {{ font-size:9.4pt; text-transform:uppercase; letter-spacing:.8px;
              color:#64748b; margin-bottom:2mm; }}
  .bens ul {{ list-style:none; margin:0; padding:0; }}
  .bens li {{ display:flex; gap:2.6mm; align-items:flex-start; margin-bottom:1.8mm; }}
  .bens li:last-child {{ margin-bottom:0; }}
  .who {{ color:#fff; font-size:8.2pt; font-weight:800; border-radius:99px;
          padding:.5mm 2.4mm; flex:0 0 auto; margin-top:.4mm; }}
  .ben {{ font-size:10.2pt; }}
  .note {{ font-size:9.6pt; color:#7c2d12; background:#fffbeb; border-left:3px solid #f59e0b;
           padding:2mm 3mm; margin:3mm 0 0; border-radius:0 2mm 2mm 0; }}
  figure {{ margin:4mm 0 0; }}
  figure img {{ width:100%; border:1px solid #cbd5e1; border-radius:2mm; display:block; }}
  figcaption {{ font-size:9pt; color:#64748b; margin-top:1.6mm; font-style:italic; }}

  /* ---------- kartlar ---------- */
  .cards {{ display:flex; gap:4mm; flex-wrap:wrap; margin:5mm 0; }}
  .pcard, .acard {{ flex:1 1 47%; border:1px solid #e2e8f0; border-radius:2.5mm;
                    padding:3.5mm 4mm; background:#fff; page-break-inside:avoid; }}
  .pcard h4, .acard h4 {{ font-size:11pt; color:#0e7490; margin-bottom:1.5mm; }}
  .pcard p, .acard p {{ margin:0; font-size:10pt; color:#334155; }}
  .steps {{ list-style:none; padding:0; margin:5mm 0; }}
  .steps li {{ display:flex; gap:3.5mm; align-items:baseline; margin-bottom:3.4mm;
               page-break-inside:avoid; }}
  .steps b {{ flex:0 0 34mm; }}
  .cyc {{ width:7.5mm; height:7.5mm; flex:0 0 7.5mm; border-radius:50%; background:#0e7490;
          color:#fff; font-size:9pt; font-weight:800; display:inline-flex;
          align-items:center; justify-content:center; }}
  .box {{ border:1px solid #e2e8f0; border-left:4px solid #0e7490; border-radius:0 2mm 2mm 0;
          padding:4mm 5mm; margin:5mm 0; background:#f8fafc; page-break-inside:avoid; }}
  .box h4 {{ font-size:11.5pt; color:#0f172a; margin-bottom:2.5mm; }}
  .box ul {{ margin:0; padding-left:5mm; }}
  .box li {{ margin-bottom:1.6mm; font-size:10.2pt; }}
  .closing {{ margin-top:10mm; padding:6mm; border-radius:3mm; text-align:center;
              background:linear-gradient(140deg,#083344,#0e7490); color:#fff;
              page-break-inside:avoid; }}
  .closing h3 {{ font-size:16pt; }}
  .closing p {{ margin:2.5mm 0 0; font-size:11pt; color:#cffafe; }}
  .closing .url {{ display:inline-block; margin-top:4mm; background:#fff; color:#0e7490;
                   font-weight:800; font-size:13pt; padding:2.5mm 8mm; border-radius:99px; }}
</style></head><body>

<div class="cover">
  <img class="logo" src="{LOGO}" alt="ETÜTKOÇ">
  <h1>Rotam<br>Tanıtım Kılavuzu</h1>
  <p class="sub">Sınav hazırlığında koçun, öğrencinin, velinin ve kurumun aynı
     veriye baktığı çalışma takip ve planlama sistemi — özellikler ve
     sağladığı faydalar.</p>
  <span class="badge">rotam.etutkoc.com</span>
  <p class="meta">ETÜTKOÇ Akademi Kişisel Gelişim Özel Eğitim ve Öğretim Hizmetleri Ltd. Şti.</p>
</div>

<div class="toc">
  <h2>İçindekiler</h2>
  <ol>{toc_html}</ol>
  <div class="box" style="margin-top:10mm">
    <h4>Bu kılavuz nasıl okunur?</h4>
    <p style="margin:0;font-size:10.4pt">Her özellik üç parçadan oluşur:
      <b>ne yaptığı</b> (sade anlatım), <b>kime ne kazandırdığı</b> (koç, öğrenci,
      veli ve kurum için ayrı ayrı) ve <b>ekran görüntüsü</b>. Görsellerin tamamı
      sistemin gerçek ekranlarından alınmıştır; temsilî çizim değildir.</p>
  </div>
</div>

{section("s-giris", "Giriş", "Rotam nedir?", C.INTRO["lead"],
  f'''<div class="grp"><h2 class="gtitle">{C.INTRO["problem_title"]}</h2></div>
      <div class="cards">{intro_problems}</div>
      <div class="grp"><h2 class="gtitle">{C.INTRO["cycle_title"]}</h2></div>
      <ul class="steps">{intro_cycle}</ul>
      <div class="grp"><h2 class="gtitle">{C.INTRO["audience_title"]}</h2></div>
      <div class="cards">{intro_aud}</div>''', "cyan")}

{section("s-koc", "Bölüm 1", "Koç için",
  "Planlamadan tahsilata kadar koçun bütün iş akışı tek sistemde. Bu bölümdeki "
  "özellikler hem bağımsız koçlar hem kuruma bağlı öğretmenler için geçerlidir.",
  coach_body, "cyan")}

{section("s-ogrenci", "Bölüm 2", "Öğrenci için",
  "Öğrenci için sistem basit olmalı: bugün ne yapacağını bil, yaptığını işaretle, "
  "kendi gelişimini gör. Karmaşık her ekran, kullanılmayan bir ekrandır.",
  stu_body, "violet")}

{section("s-veli", "Bölüm 3", "Veli için",
  "Veliler için tasarım ilkemiz tek cümle: sayı ve grafik okumak zorunda kalmasın. "
  "Yapay zekâ, panel verisini velinin diline çevirir; isterse sesli dinler.",
  par_body, "amber")}

{section("s-kurum", "Bölüm 4", "Kurum için",
  "Dershane, etüt merkezi ve okullar için Rotam bir öğretmen takip yazılımı değil; "
  "koçluk sürecinin ölçülebilir yönetim sistemidir.",
  inst_body, "teal")}

{section("s-ai", "Bölüm 5", "Yapay zekâ ve veri güvenliği", C.AI_SECTION["lead"],
  f'''<div class="grp"><h2 class="gtitle">Nerelerde kullanılır?</h2></div>
      <div class="cards">{ai_uses}</div>
      <div class="box"><h4>{C.AI_SECTION["limits_title"]}</h4><ul>{ai_limits}</ul></div>
      <div class="grp"><h2 class="gtitle">{C.AI_SECTION["privacy_title"]}</h2></div>
      <div class="box"><ul>{ai_priv}</ul></div>''', "cyan")}

{section("s-mobil", "Bölüm 6", "Mobil uygulama", C.MOBILE["lead"],
  f'''<div class="cards">{mob_items}</div>
      <div class="box"><p style="margin:0">{esc(C.MOBILE["note"])}</p></div>''', "violet")}

{section("s-basla", "Bölüm 7", "Nasıl başlanır?", C.START["lead"],
  f'''<ul class="steps">{start_steps}</ul>
      <div class="box"><h4>{C.START["inst_title"]}</h4>
        <p style="margin:0">{esc(C.START["inst"])}</p></div>
      <div class="closing">
        <h3>Denemesi ücretsiz</h3>
        <p>Bağımsız koçsanız on dört gün ücretsiz — kart bilgisi istemiyoruz.<br>
           Kurumsanız kurulumuyla birlikte teslim ediyoruz.</p>
        <span class="url">rotam.etutkoc.com</span>
      </div>''', "cyan")}

</body></html>"""

HTML.write_text(html, encoding="utf-8")
print(f"HTML: {HTML}  ({len(html)//1024} KB)")
if missing:
    print(f"!! EKSİK GÖRSEL ({len(missing)}): {missing[:8]}")

from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    br = pw.chromium.launch(channel="chrome")
    pg = br.new_page()
    pg.goto(HTML.as_uri(), wait_until="networkidle", timeout=180_000)
    pg.wait_for_timeout(1500)
    pg.pdf(path=str(PDF), format="A4", print_background=True,
           margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
           display_header_footer=True,
           header_template='<div></div>',
           footer_template=(
               '<div style="width:100%;font-size:8pt;color:#94a3b8;'
               'font-family:Segoe UI,sans-serif;padding:0 14mm;display:flex;'
               'justify-content:space-between"><span>ETÜTKOÇ Rotam — Tanıtım Kılavuzu</span>'
               '<span>rotam.etutkoc.com · <span class="pageNumber"></span>/'
               '<span class="totalPages"></span></span></div>'))
    br.close()

size = PDF.stat().st_size / 1e6
print(f"PDF: {PDF}  ({size:.1f} MB)")
desktop = Path.home() / "Desktop" / PDF.name
shutil.copy(PDF, desktop)
print(f"Kopya: {desktop}")
