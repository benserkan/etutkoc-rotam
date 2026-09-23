"""Kalan 25 kitap → katalog JSON (kullanıcı kuralları, 2026-09-23).

Kurallar (kullanıcı):
- Deneme kitapları: deneme sayısı → her deneme 1 satır.
- PSH: bölüm soru sayısı / 10 (10 soruluk test).
- MEB çalışma kitapları: müfredat konusuna göre bölüm × 10 test; sözel kitap derse göre 3 kitap.
- Ay Serisi (soru bankası + fasikül): her konu 5 test.
- İçindekilerde yalnız konu+sayfa olanlar: sayfa aralığından tahmin.
"""
import json, math, re, unicodedata
from pathlib import Path

SRC = Path(__file__).parent / "out"
DST = Path(r"D:/LGS-Program/data/kitap-katalog/lgs")
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slug(s):
    s = unicodedata.normalize("NFKC", s).translate(_TR).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60]


def load(i):
    return json.loads((SRC / f"{i}.json").read_text(encoding="utf-8"))


def write(d, rows, note, *, name=None, subject=None, btype=None, no_map=False):
    out = {
        "name": name or d["name"], "publisher": d.get("publisher"),
        "subject": subject or d["subject"], "curriculum_model": "lgs",
        "type": btype or d["type"], "target_grade_min": 8, "target_grade_max": 8,
        "target_graduate": False,
        "sections": [{"label": l, "test_count": int(t), "source": "toc_estimate"} for l, t in rows if t],
        "warnings": ["TAHMİNİ test sayısı — kitabın gövdesi görülmedi; koç kendi kopyasında düzeltebilir."],
        "notes": [f"Kaynak: kapak + içindekiler fotoğrafı ({d['file']}). {note}"] + list(d.get("notes") or []),
        "no_map": no_map,
    }
    fn = DST / f"lgs8_{slug(out['name'])}.json"
    fn.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{fn.name}: {len(out['sections'])} satır · {sum(s['test_count'] for s in out['sections'])} test")


def span(s):
    a, b = s.get("page_start"), s.get("page_end")
    return (b - a + 1) if a and b else None


def est_rows(d, ppt=2, skip=lambda s: False):
    rows = []
    for s in d["sections"]:
        if skip(s):
            continue
        if s.get("confidence") == "exact" and s.get("test_count"):
            rows.append((s["label"], s["test_count"]))
            continue
        n = span(s)
        if n:
            rows.append((s["label"], max(1, math.ceil(n / ppt))))
    return rows


# ---- Sayfa aralığından tahmin (1 test ≈ 2 sayfa) ----
PP_NOTE = "İçindekilerde yalnız konu + başlangıç sayfası var; test sayısı sayfa aralığından (1 test ≈ 2 sayfa) TAHMİN edildi."
# Ankara Paragraf: konu anlatımı satırları (est yok) atlanır
d = load(0); write(d, [(s["label"], s["est_tests_2pp"]) for s in d["sections"] if s.get("est_tests_2pp")], PP_NOTE + " Konu anlatımı satırları katalog dışı.")
d = load(1); write(d, est_rows(d), PP_NOTE)
for i in (30, 31, 32, 34, 37):
    d = load(i); write(d, est_rows(d), PP_NOTE + " Numaralı değerlendirme sınavları 1'er test (içindekilerde listeli).")
# Eker Din defteri: 'Tanıyorum' okuma sayfaları test değil
d = load(18)
write(d, est_rows(d, skip=lambda s: "Tanıyorum" in s["label"]), PP_NOTE + " 'Bir Peygamber/Ayet/Sure Tanıyorum' okuma sayfaları test sayılmadı; Deneme Sınavları 5 (içindekilerde yazıyor).")
# Paragrafın Yıldızı: Paragraf Denemeleri 40 s. → ~8 s./deneme = 5 deneme
d = load(36)
rows = []
for s in d["sections"]:
    if s["label"] == "Paragraf Denemeleri":
        rows.append(("Paragraf Denemeleri (5 deneme)", 5))
    else:
        rows.append((s["label"], math.ceil(span(s) / 2)))
write(d, rows, PP_NOTE + " Paragraf Denemeleri (40 sayfa) ≈ 8 sayfa/deneme → 5.")
# Mozaik Paragraf: Kavrama testleri exact; 10'da On/Final 3 sayfa/test (gözlenen)
d = load(33)
write(d, est_rows(d, ppt=3), "Kavrama testleri içindekilerde listeli (1'er); 10'da On ve Final testleri 3 sayfa/test (Kavrama testinde gözlenen) ile TAHMİN.")
# Benim Hocam: kapakta 133 test → sayfa oranıyla dağıt (en büyük kalan)
d = load(10)
spans = [(s["label"], span(s)) for s in d["sections"]]
tot = sum(n for _, n in spans)
raw = [(l, n * 133 / tot) for l, n in spans]
base = [(l, math.floor(x)) for l, x in raw]
rem = 133 - sum(b for _, b in base)
order = sorted(range(len(raw)), key=lambda k: raw[k][1] - base[k][1], reverse=True)[:rem]
rows = [(l, b + (1 if k in order else 0)) for k, (l, b) in enumerate(base)]
write(d, [(l, max(t, 1)) for l, t in rows], "Kapakta toplam 133 test yazıyor; konulara sayfa aralığı oranında dağıtıldı (toplam birebir, konu dağılımı TAHMİN).")

# ---- PSH: 10 soruluk test ----
d = load(35)
write(d, [(s["label"] + f" ({s['question_count']} soru)", math.ceil(s["question_count"] / 10)) for s in d["sections"]],
      "Bölümler soru sayısıyla verilmiş; 1 test = 10 soru kabul edildi (kullanıcı kararı).")

# ---- Ay Serisi: her konu 5 test ----
for i in (2, 4, 5, 6, 8, 9):
    d = load(i)
    write(d, [(s["label"], 5) for s in d["sections"]],
          "İçindekiler yerine 32 haftalık plan tablosu var (sayfa yok); her konu 5 test kabul edildi (kullanıcı kararı).")

# ---- Denemeler ----
d = load(23)
write(d, [(f"Deneme {k}", 1) for k in range(1, 41)], "Yalnız kapak: '40 deneme' (kullanıcı onayı).", no_map=True)
d = load(44)
rows = [(f"Mini Kazanım Denemesi {k}", 1) for k in range(1, 41)] + \
       [(f"Sarmal Deneme {k}", 1) for k in range(1, 7)] + [(f"Genel Deneme {k}", 1) for k in range(1, 7)]
write(d, rows, "Yalnız kapak: 40 mini kazanım + 6 sarmal + 6 genel deneme (kullanıcı onayı).", no_map=True)

# ---- MEB çalışma kitapları: müfredat konusu × 10 test; yıllık sınav ders payı / 10 ----
YEAR_NOTE = "LGS'de her ders için yıllık çıkmış sorular: 20 soruluk derslerde 2, 10 soruluk derslerde 1 test (10 soru/test)."
MEB = "MEB LGS Çalışma Kitabı (Çıkmış Sorular ve Örnek Sorular)"


def meb(i, subject, topic_rows, per_year, name_suffix):
    d = load(i)
    rows = [(t, 10) for t in topic_rows]
    for s in d["sections"]:
        if "Merkezî Sınav" in s["label"]:
            m = re.match(r"(\d{4}-\d{4})", s["label"])
            yr = m.group(1) if m else s["label"]
            if "ikinci kez" in s["label"]:
                yr = "2025-2026"
            rows.append((f"{yr} LGS Çıkmış Soruları", per_year))
    write(d, rows, "Kitap MEB çalışma kitabı; üniteler test numarası taşımıyor → her müfredat konusu 10 test (kullanıcı kararı). " + YEAR_NOTE,
          name=f"{MEB} — {name_suffix}", subject=subject, btype="soru_bankasi")


def units(i, prefix=""):
    return [re.sub(r"^\S+ \d+\. (Ünite|Tema): ", "", s["label"]).replace(prefix, "")
            for s in load(i)["sections"] if "Merkezî Sınav" not in s["label"]]


meb(26, "Fen Bilimleri", [re.sub(r"^\d+\. Ünite: ", "", l) for l in units(26)], 2, "Fen Bilimleri")
mat = []
for l in units(27):
    mat += [p.strip() for p in re.sub(r"^\d+\. Ünite: ", "", l).split(" - ")]
meb(27, "Matematik", mat, 2, "Matematik")
meb(29, "Türkçe", [re.sub(r"^\d+\. Tema: ", "", l) for l in units(29)], 2, "Türkçe")
sz = [s["label"] for s in load(28)["sections"] if "Merkezî Sınav" not in s["label"]]
meb(28, "T.C. İnkılap Tarihi ve Atatürkçülük", [re.sub(r"^İnkılap \d+\. Ünite: ", "", l) for l in sz if l.startswith("İnkılap")], 1, "T.C. İnkılap Tarihi ve Atatürkçülük")
meb(28, "Din Kültürü ve Ahlak Bilgisi", [re.sub(r"^Din \d+\. Ünite: ", "", l) for l in sz if l.startswith("Din")], 1, "Din Kültürü ve Ahlak Bilgisi")
meb(28, "İngilizce", [re.sub(r"^İngilizce ", "", l) for l in sz if l.startswith("İngilizce")], 1, "İngilizce")
