"""Konu anlatımlı FASİKÜL yapısı → katalog JSON (admin aracı; taranmış PDF, görüntü modu).

Soru bankası pipeline'ı (`book_structure_pipeline.py`) global İÇİNDEKİLER ister; konu
anlatımlı fasiküllerde içindekiler yoktur — her BÖLÜM kendi ayraç sayfasında
alt başlıklarını (+ sayfa no) listeler; testler alt başlık GRUPLARININ sonunda
kümelenir ("KAZANIM TEST-1/2" + "ÖSYM TARZI TEST"), bölüm sonunda "ÖSYM TARZI
TARAMA TESTİ 1..N" gelir. Bu script o yapıyı çıkarır:

  A) Ayraç sayfaları: doygun-renk oranıyla bulunur, Gemini ile okunur → bölüm adı +
     alt başlık listesi (label, sayfa).
  B) Gövde: TÜM sayfaların üst şeridi (%20) 10'lu batch'lerle ÇİFT bağımsız geçişte
     okunur → {başlık konusu, bant metni, numara}. DERS: geçişler parça bazında ±1-2
     sayfa KAYABİLİR ve bir geçiş bant düşürebilir → iki geçiş BİRLEŞTİRİLİR
     (birim düzeyinde, yakınlık toleransıyla); tek geçiş eksik sayar.
  C) Test birimi = (bölüm, kategori, numara) — AMA numara alt-grupta YENİDEN başlar
     ("Kazanım Test-1" aynı bölümde iki kez) → aynı anahtar yalnız yakın sayfadaysa
     (≤3) aynı birim; uzaksa yeni seri. Numarasız bant → bitişik koşu = 1 test.
     Sayılan: KAZANIM TESTİ · ÖSYM TARZI TEST · TARAMA TESTİ · TEST N. SAYILMAYAN:
     örnek / çözümlü örnek / "Bir de Orijinal'den Dinle" (ayrıca raporlanır; --include-dinle
     ile sayılır) / cevap anahtarı. Bölüm ataması: sayfa BAŞLIĞINDAKİ konu adı ayraç
     aralığını EZER (DERS: İkinci Dereceden Denklemler'in tarama testleri fiziksel olarak
     Karmaşık Sayılar'ın arkasında).
  D) Alt başlıklar test-taşıyan GRUPLARA bağlanır: grup = ardışık alt başlıklar + onları
     izleyen test kümesi; etiket "Bölüm · İlk Alt Başlık – Son Alt Başlık"; tarama testleri
     bölümün kendi satırı. 0 testli alt başlık katalog satırı olmaz (raporlanır).
  E) JSON `seed_book_catalog_json.py` sözleşmesinde + .raw.json (iki geçişin ham okuması;
     --from-raw ile Gemini'siz yeniden hesap).

Kullanım:
  PYTHONPATH=. python scripts/fasikul_structure.py "<pdf>" --name "..." --publisher "..." \
      --subject "AYT Matematik" [--type fasikul] [--grade-min 11 --grade-max 12 --graduate]
      [--include-dinle] [--from-raw x.json.raw.json] [--out data/kitap-katalog/x.json]
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import argparse
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import fitz
from PIL import Image

from scripts.book_structure_pipeline import _gen, _img_part  # noqa: E402  (DNS yaması + gemini)
from app.services import gemini  # noqa: E402

BATCH = 10
STRIP_H = 0.20
STRIP_DPI = 110
NEAR = 3  # aynı birim sayılacak sayfa yakınlığı (geçiş kayması + 2 sayfalık test)

DIVIDER_PROMPT = """Bu görsel bir konu anlatımlı fasikülün BÖLÜM AYRAÇ sayfası olabilir ("1. BÖLÜM", büyük renkli zemin, altında bölüm adı ve madde madde alt başlıklar + sayfa numaraları).
GÖREV: bölüm numarasını, bölüm adını ve alt başlık listesini (yazıldığı gibi, sırayla) + her birinin sayfa numarasını çıkar.
- "ÖSYM Tarzı Tarama Testleri / 31" gibi test satırları da listeye DAHİL (label olarak).
- Sayfa numarası yoksa null. Ayraç sayfası DEĞİLSE {"is_divider": false}.
YALNIZ şu JSON: {"is_divider": bool, "bolum_no": int|null, "bolum_adi": str|null, "items": [{"label": str, "page": int|null}]}"""

STRIP_PROMPT = """Sana bir konu anlatımlı fasikülün sayfa ÜST ŞERİTLERİNİ sırayla veriyorum.
Her şeritte (1) sayfanın üst başlığındaki KONU/BÖLÜM adı (örn. "POLİNOMLAR", "PARABOL") ve (2) varsa bir BANT/ROZET bulunur.
Bant türleri (yazıldığı gibi oku): "KAZANIM TEST-1", "KAZANIM TESTİ 3", "ÖSYM TARZI TEST", "ÖSYM TARZI TEST 2", "ÖSYM TARZI TARAMA TESTİ 1", "TARAMA TESTİ", "TEST 4",
"BİR DE ORİJİNAL'DEN DİNLE", "ÖSYM TARZI ÇÖZÜMLÜ ÖRNEKLER", "ÖRNEK", "CEVAP ANAHTARI", "BİLGİ NOTU" vb.
- "h": üst başlıktaki konu adı (yoksa null).
- "b": bandın TAM metni (yoksa null). Konu adı başlığı bant DEĞİLDİR. "Bir de Orijinal'den Dinle"/"Örnek" gibi olanları da b olarak yaz — süzmeyi ben yaparım.
- "n": bantta numara varsa o numara (örn. "KAZANIM TEST-2" → 2), yoksa null. Konu başlığındaki "1. BÖLÜM" gibi numaraları n sanma.
- Bölüm AYRAÇ kapağı (tam renkli sayfa) → {"h": bölüm adı, "b": "AYRAÇ", "n": null}.
YALNIZ şu JSON: {"strips": [{"h": str|null, "b": str|null, "n": int|null}, ...]} — şerit sayısı kadar, sırayla."""


def _ascii(s: str | None) -> str:
    return unicodedata.normalize("NFKD", (s or "").replace("İ", "I").replace("ı", "i")).encode("ascii", "ignore").decode().lower()


def band_cat(b: str | None) -> str | None:
    s = _ascii(b)
    if not s:
        return None
    if "ayrac" in s:
        return "x_ayrac"
    if "cevap" in s or "anahtar" in s:
        return "x_cevap"
    if "dinle" in s:
        return "x_dinle"
    if "cozumlu" in s or "ornek" in s or "bilgi notu" in s or "cozum" in s or s.startswith("soru"):
        return "x_ornek"
    if "tarama" in s:
        return "tarama"
    if "kazanim" in s:
        return "kazanim"
    if "osym" in s and "test" in s:
        return "osym_test"
    if "test" in s:
        return "test"
    return None


CAT_TR = {"kazanim": "Kazanım Testi", "osym_test": "ÖSYM Tarzı Test", "tarama": "ÖSYM Tarzı Tarama Testi",
          "test": "Test", "dinle": "Bir de Orijinal'den Dinle", "x_dinle": "Bir de Orijinal'den Dinle",
          "x_ornek": "Örnek/Çözümlü örnek"}

_TR_LOWER = str.maketrans("IİÇĞÖŞÜ", "ıiçğöşü")
_TR_UPPER = str.maketrans("ıiçğöşü", "IİÇĞÖŞÜ")


def tr_title(s: str) -> str:
    """Türkçe başlık hâli: 'KATSAYILAR TOPLAMI VE SABİT TERİM' → 'Katsayılar Toplamı ve Sabit Terim'.
    Rakam/sembol içeren kelimelere (ax², i'NİN) dokunulmaz; bağlaçlar küçük."""
    small = {"ve", "ile", "veya", "için", "de", "da"}
    out = []
    for w in s.split():
        if any(ch.isdigit() for ch in w) or "²" in w or "'" in w:
            out.append(w if any(ch.isdigit() for ch in w) or "²" in w else w[:1].translate(_TR_UPPER).upper() + w[1:].translate(_TR_LOWER).lower())
            continue
        lw = w.translate(_TR_LOWER).lower()
        if lw in small and out:
            out.append(lw)
        else:
            out.append(lw[:1].translate(_TR_UPPER).upper() + lw[1:])
    return " ".join(out)


# ---------------------------------------------------------------- A) ayraç sayfaları
def find_dividers(doc) -> list[int]:
    out = []
    for i in range(doc.page_count):
        pix = doc[i].get_pixmap(dpi=18)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("HSV")
        px = list(im.getdata())
        frac = sum(1 for h, s, v in px if s > 110 and v > 120) / max(1, len(px))
        if frac > 0.3:
            out.append(i)
    return out


def read_divider(doc, idx: int) -> dict:
    parts = [_img_part(doc[idx].get_pixmap(dpi=80)), gemini.text_part(DIVIDER_PROMPT)]
    try:
        data = _gen(parts, timeout=90)
    except Exception:  # noqa: BLE001
        data = _gen(parts, timeout=90)
    items = []
    for it in data.get("items") or []:
        if isinstance(it, dict) and it.get("label"):
            pg = it.get("page")
            items.append({"label": str(it["label"]).strip()[:200], "page": int(pg) if isinstance(pg, int) else None})
    return {"pdf_idx": idx, "bolum_no": data.get("bolum_no"), "bolum_adi": (data.get("bolum_adi") or "").strip() or None,
            "items": items, "is_divider": bool(data.get("is_divider", True))}


# ---------------------------------------------------------------- B) gövde taraması
def scan_once(doc, pages: list[int]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for i in range(0, len(pages), BATCH):
        chunk = pages[i:i + BATCH]
        parts = []
        for idx in chunk:
            page = doc[idx]
            r = page.rect
            parts.append(_img_part(page.get_pixmap(dpi=STRIP_DPI, clip=fitz.Rect(0, 0, r.width, r.height * STRIP_H))))
        parts.append(gemini.text_part(STRIP_PROMPT))
        got = []
        for attempt in (1, 2):
            try:
                got = _gen(parts).get("strips") or []
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"    parça {i//BATCH+1} HATA: {e}")
                else:
                    import time as _t
                    _t.sleep(3)
        for j, idx in enumerate(chunk):
            v = got[j] if j < len(got) else None
            if isinstance(v, dict):
                n = v.get("n")
                out[idx] = {"h": (v.get("h") or None), "b": (v.get("b") or None), "n": n if isinstance(n, int) else None}
        if (i // BATCH) % 5 == 4:
            print(f"    …parça {i//BATCH+1}/{(len(pages)+BATCH-1)//BATCH}", flush=True)
    return out


# ---------------------------------------------------------------- C) birimler
def bolum_index(h: str | None, idx: int, dividers: list[dict], bolum_ranges) -> int | None:
    """Önce sayfa başlığı (bölüm adı eşleşmesi), yoksa ayraç aralığı."""
    hs = _ascii(h)
    if hs:
        best, blen = None, 0
        for bi, d in enumerate(dividers):
            name = _ascii(d["bolum_adi"])
            if name and (name in hs or hs in name) and len(name) > blen:
                best, blen = bi, len(name)
        if best is not None:
            return best
    for bi, s, e in bolum_ranges:
        if s <= idx < e:
            return bi
    return None


def units_from_scan(scan: dict[int, dict], dividers, bolum_ranges, include_dinle: bool) -> list[dict]:
    units: list[dict] = []
    for idx in sorted(scan):
        v = scan[idx]
        cat = band_cat(v.get("b"))
        if cat == "x_dinle" and include_dinle:
            cat = "dinle"
        if cat is None or cat.startswith("x_"):
            continue
        bi = bolum_index(v.get("h"), idx, dividers, bolum_ranges)
        if bi is None:
            continue
        n = v.get("n")
        # aynı (bölüm, kategori, numara) + yakın sayfa → aynı birim; numarasız → bitişik koşu
        hit = None
        for u in reversed(units):
            if u["bolum_i"] != bi or u["cat"] != cat:
                continue
            if n is not None and u["n"] == n and idx - u["last"] <= NEAR:
                hit = u
            elif n is None and u["n"] is None and idx - u["last"] <= 1:
                hit = u
            if hit or idx - u["last"] > NEAR + 2:
                break
        if hit:
            hit["pages"].append(idx)
            hit["last"] = max(hit["last"], idx)
        else:
            units.append({"bolum_i": bi, "cat": cat, "n": n, "first": idx, "last": idx, "pages": [idx]})
    return units


def merge_passes(u1: list[dict], u2: list[dict]) -> list[dict]:
    """İki geçişin birleşimi: aynı (bölüm,kat,n) ve |first−first|≤NEAR → aynı birim."""
    merged = [dict(u, pages=list(u["pages"])) for u in u1]
    for u in u2:
        hit = None
        for m in merged:
            if m["bolum_i"] == u["bolum_i"] and m["cat"] == u["cat"] and m["n"] == u["n"] and abs(m["first"] - u["first"]) <= NEAR:
                hit = m
                break
        if hit:
            hit["pages"] = sorted(set(hit["pages"]) | set(u["pages"]))
            hit["first"] = min(hit["first"], u["first"])
            hit["last"] = max(hit["last"], u["last"])
            hit["both"] = True
        else:
            merged.append(dict(u, pages=list(u["pages"]), only="2"))
    for m in merged:
        if "both" not in m and "only" not in m:
            m["only"] = "1"
    return sorted(merged, key=lambda u: (u["bolum_i"], u["first"]))


# ---------------------------------------------------------------- D) gruplar
def build_groups(dividers, units, offset) -> tuple[list[dict], list[str], list[str]]:
    sections, zero, warnings = [], [], []
    for bi, d in enumerate(dividers):
        bname = tr_title(d["bolum_adi"] or f"Bölüm {bi+1}")
        subs = [(it["page"] - 1 + offset, k, it["label"]) for k, it in enumerate(d["items"]) if it["page"]]
        subs.sort()
        subs = [(p, lab) for p, _k, lab in subs]  # aynı sayfadaki alt başlıklar ayraç sırasını korur
        bunits = [u for u in units if u["bolum_i"] == bi]
        tarama = [u for u in bunits if u["cat"] == "tarama"]
        others = [u for u in bunits if u["cat"] != "tarama"]
        # olaylar: (sayfa, tür, veri)
        events = [(p, "S", lab) for p, lab in subs if "tarama" not in _ascii(lab)] + [(u["first"], "T", u) for u in others]
        events.sort(key=lambda e: (e[0], 0 if e[1] == "S" else 1))
        cur_subs: list[str] = []
        cur_units: list[dict] = []
        groups: list[tuple[list[str], list[dict]]] = []
        for p, kind, data in events:
            if kind == "S":
                if cur_units:  # yeni grup başlıyor
                    groups.append((cur_subs, cur_units))
                    cur_subs, cur_units = [], []
                cur_subs.append(data)
            else:
                cur_units.append(data)
        if cur_units or cur_subs:
            groups.append((cur_subs, cur_units))
        for gsubs, gunits in groups:
            if not gunits:
                zero.extend(f"{bname} · {tr_title(s)}" for s in gsubs)
                continue
            if not gsubs:
                gsubs = ["(alt başlık yok)"]
                warnings.append(f"{bname}: alt başlıksız test kümesi (PDF s.{gunits[0]['first']+1}) — etiketi elle ver.")
            if len(gsubs) == 1:
                lab = f"{bname} · {tr_title(gsubs[0])}"
            else:
                lab = f"{bname} · {tr_title(gsubs[0])} – {tr_title(gsubs[-1])}"
            cats = {}
            for u in gunits:
                cats[u["cat"]] = cats.get(u["cat"], 0) + 1
            sections.append({"label": lab[:255], "test_count": len(gunits), "source": "scan",
                             "page": min(u["first"] for u in gunits) + 1 - offset, "cats": cats,
                             "subtopics": [tr_title(s) for s in gsubs]})
        if tarama:
            cats = {"tarama": len(tarama)}
            sections.append({"label": f"{bname} · ÖSYM Tarzı Tarama Testleri"[:255], "test_count": len(tarama),
                             "source": "scan", "page": min(u["first"] for u in tarama) + 1 - offset, "cats": cats,
                             "subtopics": ["ÖSYM Tarzı Tarama Testleri"]})
            nums = sorted(u["n"] for u in tarama if u["n"] is not None)
            if nums and nums != list(range(1, len(nums) + 1)):
                warnings.append(f"{bname}: tarama numara zinciri kopuk {nums} — gözle kontrol.")
        else:
            if any("tarama" in _ascii(it["label"]) for it in d["items"]):
                warnings.append(f"{bname}: ayraçta 'ÖSYM Tarzı Tarama Testleri' var ama tarama bandı bulunamadı (başka bölümün başlığı altında olabilir).")
    return sections, zero, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--name", required=True)
    ap.add_argument("--publisher", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--type", default="fasikul")
    ap.add_argument("--grade-min", type=int, default=None)
    ap.add_argument("--grade-max", type=int, default=None)
    ap.add_argument("--graduate", action="store_true")
    ap.add_argument("--include-dinle", action="store_true", help="'Bir de Orijinal'den Dinle' soru setlerini de test say")
    ap.add_argument("--from-raw", default=None, help="önceki koşunun .raw.json'u — Gemini çağrılmaz")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    print(f"PDF: {doc.page_count} sayfa")

    raw = json.loads(Path(args.from_raw).read_text(encoding="utf-8")) if args.from_raw else None
    if raw and raw.get("dividers"):
        dividers = raw["dividers"]
        div_idx = [d["pdf_idx"] for d in dividers]
    else:
        div_idx = find_dividers(doc)
        print(f"Ayraç adayı: {[i+1 for i in div_idx]}")
        with ThreadPoolExecutor(max_workers=3) as pool:
            dividers = list(pool.map(lambda i: read_divider(doc, i), div_idx))
        dividers = [d for d in dividers if d["is_divider"] and d["items"]]
    for d in dividers:
        print(f"  Bölüm {d['bolum_no']}: {d['bolum_adi']} — {len(d['items'])} alt başlık (PDF s.{d['pdf_idx']+1})")
    if not dividers:
        print("Ayraç okunamadı — çıkılıyor.")
        return 1

    offsets = []
    for d in dividers:
        first_pg = next((it["page"] for it in d["items"] if it["page"]), None)
        if first_pg:
            offsets.append((d["pdf_idx"] + 1) - first_pg)
    offset = max(set(offsets), key=offsets.count) if offsets else 0
    print(f"Ofset (pdf0 = basılı + {offset})")

    bolum_ranges = []
    for k, d in enumerate(dividers):
        s = d["pdf_idx"]
        e = dividers[k + 1]["pdf_idx"] if k + 1 < len(dividers) else doc.page_count
        bolum_ranges.append((k, s, e))

    if raw:
        s1 = {int(k): v for k, v in raw["scan1"].items()}
        s2 = {int(k): v for k, v in raw["scan2"].items()}
        print("Ham tarama dosyadan yüklendi (Gemini çağrılmadı).")
    else:
        pages = [i for i in range(doc.page_count) if i not in div_idx]
        print(f"Gövde taraması: {len(pages)} sayfa × 2 geçiş ({(len(pages)+BATCH-1)//BATCH} parça/geçiş)", flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1, f2 = pool.submit(scan_once, doc, pages), pool.submit(scan_once, doc, pages)
            s1, s2 = f1.result(), f2.result()

    u1 = units_from_scan(s1, dividers, bolum_ranges, args.include_dinle)
    u2 = units_from_scan(s2, dividers, bolum_ranges, args.include_dinle)
    units = merge_passes(u1, u2)

    print("\nBölüm bazında (geçiş1 / geçiş2 / BİRLEŞİM):")
    for bi, d in enumerate(dividers):
        a = sum(1 for u in u1 if u["bolum_i"] == bi)
        b = sum(1 for u in u2 if u["bolum_i"] == bi)
        m = sum(1 for u in units if u["bolum_i"] == bi)
        only = sum(1 for u in units if u["bolum_i"] == bi and u.get("only"))
        print(f"  {d['bolum_adi']:<34} {a:>3} / {b:>3} → {m:>3}   (tek geçişte görülen: {only})")

    sections, zero, warnings = build_groups(dividers, units, offset)

    excl = {}
    for idx, v in s1.items():
        c = band_cat(v.get("b"))
        if c and c.startswith("x_") and c != "x_ayrac":
            excl[c] = excl.get(c, 0) + 1

    print("\nSONUÇ (iki geçişin birleşimi):")
    for s in sections:
        print(f"  {s['test_count']:>3}  {s['label']}   ← {s['cats']}  (s.{s['page']})")
    print(f"  TOPLAM {sum(s['test_count'] for s in sections)} test · {len(sections)} satır")
    print("  Sayılmayan bant sayfaları:", {CAT_TR.get(k, k): v for k, v in excl.items()})
    if zero:
        print("  Testsiz alt başlıklar (kataloğa girmez):")
        for z in zero:
            print("     -", z)
    for w in warnings:
        print("  ⚠", w)
    # tek geçişte görülen birimler — gözle kontrol listesi
    singles = [u for u in units if u.get("only")]
    if singles:
        print("  Tek geçişte görülen birimler (diğer geçiş kaçırmış olabilir — normal):")
        for u in singles:
            print(f"     - {dividers[u['bolum_i']]['bolum_adi']} · {CAT_TR.get(u['cat'], u['cat'])} {u['n'] or ''} PDF s.{u['first']+1} (geçiş {u['only']})")

    out = {
        "name": args.name, "publisher": args.publisher, "subject": args.subject, "type": args.type,
        "target_grade_min": args.grade_min, "target_grade_max": args.grade_max, "target_graduate": bool(args.graduate),
        "sections": sections, "warnings": warnings,
        "meta": {"dividers": dividers, "offset": offset, "zero_test_subtopics": zero, "excluded_pages": excl,
                 "units": [{k: v for k, v in u.items()} for u in units]},
    }
    out_path = args.out or (Path(args.pdf).stem[:40].strip().replace(" ", "_") + "_yapi.json")
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(str(out_path) + ".raw.json").write_text(json.dumps({"dividers": dividers, "scan1": s1, "scan2": s2}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON: {out_path}  →  seed: PYTHONPATH=. python scripts/seed_book_catalog_json.py {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
