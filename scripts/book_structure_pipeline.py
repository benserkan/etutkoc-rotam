"""Kitap yapısı boru hattı — tam kitap PDF'inden katalog-hazır yapı (admin aracı).

345 TYT Matematik denemesinde (2026-08-11) elle kanıtlanan yöntemin tek-komutluk
hâli. Aşamalar:

  A) İÇİNDEKİLER ÇIKARIMI — ilk N sayfa görüntüsü, ÇİFT bağımsız Gemini okuma:
     konu listesi + (varsa) test sayısı + başlangıç sayfa numarası. Grup
     başlıkları (BÖLÜM N) ve çalışma-dışı satırlar (önsöz/cevap anahtarı) elenir.
  B) SAYFA HİZALAMA — basılı sayfa numarası okunarak PDF-indeks ↔ kitap-sayfası
     ofseti otomatik kalibre edilir (taranmış PDF'lerde kapak/boş sayfa kayması).
  C) GÖVDE TARAMASI (yalnız test sayısı içindekilerde OLMAYAN konular) — her
     sayfanın üst şeridi taranır, numaralı grup bantları (TEST N / ÖSYM TADINDA
     SORULAR N / ORİJİNAL SORULAR N ...) çıkarılır. KURAL: bant testin HER
     sayfasında tekrarlanabilir + numara KATEGORİ başına 1'den başlar → konu
     toplamı = kategori başına EN BÜYÜK numara toplamı; 1..N ZİNCİR DENETİMİ
     kopukları raporlar; ÇİFT bağımsız tarama karşılaştırılır.
  D) JSON çıktı + konsol raporu (bayraklı satırlar insan gözü ister).

Kullanım:
  PYTHONPATH=. python scripts/book_structure_pipeline.py "<pdf>" \
      --name "345 TYT Kimya Soru Bankası" --publisher "345 Yayınları" \
      --subject "TYT Kimya" [--type soru_bankasi] [--grade-min 11]
      [--grade-max 12] [--graduate] [--toc-pages 12] [--out cikti.json]

Çıktı JSON'u `scripts/seed_book_catalog_json.py` ile dev/prod kataloğuna basılır.
Kredi DÜŞMEZ (kitap yapısı kişisel veri değil → ücretsiz anahtar).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import argparse
import base64
import json
import unicodedata
from pathlib import Path

# --- DNS oto-yaması: dev makinesinin DNS'i Gemini hostunda ARALIKLI şaşıyor
# --- (koşu ortasında bile). Sarmalayıcı DAİMA kurulur: önce normal çözüm,
# --- başarısızsa sabit IP'lere düşer — prod'da normal yol hep kazanır.
import socket as _socket

_GEMINI_HOST = "generativelanguage.googleapis.com"
_GEMINI_IPS = ["172.217.113.4", "172.217.114.4", "172.217.117.4"]
_orig_gai = _socket.getaddrinfo


def _patched_gai(host, *args, **kwargs):
    if host == _GEMINI_HOST:
        try:
            return _orig_gai(host, *args, **kwargs)
        except OSError:
            pass
        last = None
        for ip in _GEMINI_IPS:
            try:
                return _orig_gai(ip, *args, **kwargs)
            except OSError as e:
                last = e
        raise last
    return _orig_gai(host, *args, **kwargs)


_socket.getaddrinfo = _patched_gai

import fitz

from app.services import gemini

BATCH = 10
STRIP_H = 0.18
STRIP_DPI = 100

TOC_PROMPT = """Sana bir soru bankasının İLK sayfalarını sırayla veriyorum (kapak/tanıtım/içindekiler karışık olabilir).
GÖREV: İÇİNDEKİLER sayfalarını bul ve konu listesini çıkar.
KURALLAR:
- Yalnız içindekilerde GERÇEKTEN yazan konu/bölüm satırlarını al; sırayla.
- "BÖLÜM 07", "ÜNİTE 3" gibi SADECE NUMARA taşıyan grup başlıklarını ALMA — altındaki konuları al.
- Önsöz, cevap anahtarı, çözümler, sözlük, dizin gibi çalışma-dışı satırları ALMA.
- Her konu için: label (yazıldığı gibi), page (satırın gösterdiği başlangıç sayfa numarası; yoksa null),
  test_count (içindekiler o konu için test adedi VERİYORSA; test listesi ayrı satırlarsa ADEDİNİ say; vermiyorsa null — ASLA TAHMİN ETME).
- Kitap adı / yayınevi görünüyorsa yaz; ders tahmini (subject_hint) yaz.
YALNIZ şu JSON: {"book_title": str|null, "publisher": str|null, "subject_hint": str|null,
 "items": [{"label": str, "page": int|null, "test_count": int|null}]}"""

PAGENO_PROMPT = """Sana kitap sayfalarının ALT şeritlerini sırayla veriyorum.
Her şeritte sayfanın BASILI sayfa numarası görünebilir (genelde alt-orta/alt-köşe).
Her şerit için basılı numarayı yaz; görünmüyorsa null.
YALNIZ şu JSON: {"pages": [int|null, ...]} — şerit sayısı kadar, sırayla."""

BANNER_PROMPT = """Sana bir soru bankasının sayfa ÜST ŞERİTLERİNİ sırayla veriyorum.
Bir soru grubunun sayfasında başlık BANDI bulunabilir: "TEST 3", "ÖSYM TADINDA SORULAR 2", "ORİJİNAL SORULAR" gibi TEST/SORULAR içeren grup başlığı (logolu/çerçeveli bant).
- Bant NUMARALI ise: {"n": numara, "t": "bant metni"}
- Bant var ama NUMARASIZ ise (örn. yalnız "ORİJİNAL SORULAR"): {"n": null, "t": "bant metni"}
- Bant yoksa (yalnız KONU ADI başlığı, filigran, boş sayfa) → null. Konu adı başlığı bant DEĞİLDİR.
YALNIZ şu JSON: {"strips": [ {"n":int|null,"t":str} | null, ... ]} — şerit sayısı kadar, sırayla."""


def norm_cat(t: str | None) -> str:
    if not t:
        return "test"
    s = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    if "osym" in s or "tadinda" in s:
        return "osym_tadinda"
    if "orijinal" in s or "original" in s:
        return "orijinal"
    return "test"


def _gen(parts, timeout=90):
    raw = gemini.generate(parts, personal_data=False, json_mode=True,
                          timeout=timeout, prefer_fast=True)
    return gemini.extract_json(raw)


def _img_part(pix) -> dict:
    return gemini.inline_part(base64.b64encode(pix.tobytes("png")).decode("ascii"), "image/png")


# ============================================================================
# A) İçindekiler
# ============================================================================


def read_toc_once(doc, n_pages: int) -> dict:
    parts = []
    for i in range(min(n_pages, doc.page_count)):
        parts.append(_img_part(doc[i].get_pixmap(dpi=75)))
    parts.append(gemini.text_part(TOC_PROMPT))
    data = _gen(parts, timeout=120)
    items = []
    for it in data.get("items") or []:
        if not isinstance(it, dict):
            continue
        label = str(it.get("label") or "").strip()
        if not label:
            continue
        pg = it.get("page")
        tc = it.get("test_count")
        items.append({
            "label": label[:255],
            "page": int(pg) if isinstance(pg, int) and pg > 0 else None,
            "test_count": int(tc) if isinstance(tc, int) and tc > 0 else None,
        })
    return {
        "book_title": (data.get("book_title") or None),
        "publisher": (data.get("publisher") or None),
        "subject_hint": (data.get("subject_hint") or None),
        "items": items,
    }


def read_toc(doc, n_pages: int) -> tuple[dict, list[str]]:
    """ÇİFT okuma + karşılaştırma. Uzun okuma esas alınır; uyuşmazlık bayraklanır."""
    from concurrent.futures import ThreadPoolExecutor

    warnings: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1, f2 = pool.submit(read_toc_once, doc, n_pages), pool.submit(read_toc_once, doc, n_pages)
        r1, r2 = f1.result(), f2.result()
    base, other = (r1, r2) if len(r1["items"]) >= len(r2["items"]) else (r2, r1)
    if len(r1["items"]) != len(r2["items"]):
        warnings.append(
            f"İçindekiler iki okumada farklı satır sayısı verdi ({len(r1['items'])}/{len(r2['items'])}) — uzun olan esas alındı, kontrol edin."
        )
    by_idx = other["items"]
    for i, it in enumerate(base["items"]):
        o = by_idx[i] if i < len(by_idx) else None
        if o and o["label"][:20].lower() == it["label"][:20].lower():
            if it["page"] is None:
                it["page"] = o["page"]
            elif o["page"] is not None and o["page"] != it["page"]:
                warnings.append(f"'{it['label']}': sayfa uyuşmazlığı ({it['page']}/{o['page']})")
            if it["test_count"] is None:
                it["test_count"] = o["test_count"]
            elif o["test_count"] is not None and o["test_count"] != it["test_count"]:
                it["flag"] = "toc_count_mismatch"
                warnings.append(f"'{it['label']}': içindekiler test sayısı uyuşmazlığı ({it['test_count']}/{o['test_count']})")
    base["book_title"] = base["book_title"] or other["book_title"]
    base["publisher"] = base["publisher"] or other["publisher"]
    base["subject_hint"] = base["subject_hint"] or other["subject_hint"]
    return base, warnings


# ============================================================================
# B) Sayfa hizalama (ofset kalibrasyonu)
# ============================================================================


def _read_printed_pageno(doc, pdf_idx: int) -> int | None:
    page = doc[pdf_idx]
    r = page.rect
    got = (_gen([
        _img_part(page.get_pixmap(dpi=90, clip=fitz.Rect(0, r.height * 0.84, r.width, r.height))),
        gemini.text_part(PAGENO_PROMPT),
    ]).get("pages") or [None])
    return got[0] if got and isinstance(got[0], int) else None


def calibrate_offset(doc, sample_pages: list[int]) -> tuple[int | None, list[str]]:
    """Basılı sayfa numarası okuyarak ofset bul: pdf_idx = kitap_sayfası - 1 + ofset.

    DERS (345 Kimya): konu BAŞLANGIÇ sayfalarında basılı numara çoğu zaman YOK
    → örnek daima başlangıç+1 (iç sayfa) alınır. Aday şeritleri tek çağrıda
    okunur; ilk aday eşleşmezse okunan değerden türetilir; iki bağımsız örnekle
    doğrulanır ve FARK çıkarsa ofset OTOMATİK düzeltilir (yalnız uyarı değil).
    """
    warnings: list[str] = []
    if not sample_pages:
        return None, ["İçindekilerde sayfa numarası yok — ofset kalibre edilemedi."]
    p0 = sample_pages[0] + 1  # iç sayfa — başlangıç sayfası genelde numarasız
    cand = [off for off in (-1, 0, 1, 2, 3, 4) if 0 <= p0 - 1 + off < doc.page_count]
    parts = []
    for off in cand:
        page = doc[p0 - 1 + off]
        r = page.rect
        parts.append(_img_part(page.get_pixmap(dpi=90, clip=fitz.Rect(0, r.height * 0.84, r.width, r.height))))
    parts.append(gemini.text_part(PAGENO_PROMPT))
    got = (_gen(parts).get("pages") or [])
    # Okunan numaralardan türet: pn = p0 + off - offset  →  offset = p0 + off - pn
    votes: dict[int, int] = {}
    for off, pn in zip(cand, got):
        if isinstance(pn, int):
            d = p0 + off - pn
            votes[d] = votes.get(d, 0) + 1
    offset = max(votes, key=lambda k: votes[k]) if votes else None
    if offset is None:
        return None, ["Basılı sayfa numarası okunamadı — ofset 0 varsayıldı, sayıları kontrol edin."]

    # İki bağımsız iç sayfayla doğrula; FARK varsa ofseti okunandan DÜZELT
    checks = [p + 1 for p in sample_pages[1:3]]
    for p1 in checks:
        idx = p1 - 1 + offset
        if not (0 <= idx < doc.page_count):
            continue
        pn = _read_printed_pageno(doc, idx)
        if pn is None:
            continue
        if pn != p1:
            fixed = offset + (p1 - pn)
            warnings.append(f"Ofset doğrulamada düzeltildi ({offset} → {fixed}; beklenen {p1}, okunan {pn}).")
            offset = fixed
    return offset, warnings


# ============================================================================
# C) Gövde taraması (v2: kategori-max + zincir denetimi + çift geçiş)
# ============================================================================


def scan_ranges_once(doc, book_pages: list[int], offset: int) -> dict[int, tuple[int, str]]:
    out: dict[int, tuple[int, str]] = {}
    for i in range(0, len(book_pages), BATCH):
        chunk = book_pages[i:i + BATCH]
        parts = []
        for bp in chunk:
            page = doc[bp - 1 + offset]
            r = page.rect
            parts.append(_img_part(page.get_pixmap(dpi=STRIP_DPI, clip=fitz.Rect(0, 0, r.width, r.height * STRIP_H))))
        parts.append(gemini.text_part(BANNER_PROMPT))
        got = []
        for attempt in (1, 2):  # ara DNS/ağ kopması bir parçayı kaybettirmesin
            try:
                got = _gen(parts).get("strips") or []
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    print(f"    parça {i//BATCH+1} HATA: {e}")
                else:
                    import time as _t
                    _t.sleep(3)
        for j, bp in enumerate(chunk):
            v = got[j] if j < len(got) else None
            if isinstance(v, dict) and v.get("t"):
                n = v.get("n")
                out[bp] = (n if isinstance(n, int) else None, norm_cat(v.get("t")))
        if (i // BATCH) % 8 == 7:
            print(f"    …parça {i//BATCH+1}/{(len(book_pages)+BATCH-1)//BATCH}")
    return out


def analyze_range(start: int, end_excl: int, banners: dict[int, tuple[int | None, str]]):
    """Kategori başına EN BÜYÜK numara toplamı; yalnız NUMARASIZ görülen
    kategori (örn. tekil "ORİJİNAL SORULAR" seti) 1 test sayılır — bant her
    sayfada tekrarlanabildiğinden numarasız tekrarlar ekstra sayılmaz."""
    cats: dict[str, set[int]] = {}
    unnumbered: set[str] = set()
    for bp in range(start, end_excl):
        if bp in banners:
            n, t = banners[bp]
            if n is None:
                unnumbered.add(t)
            else:
                cats.setdefault(t, set()).add(n)
    total, gaps = 0, []
    for t, nums in sorted(cats.items()):
        mx = max(nums)
        total += mx
        missing = sorted(set(range(1, mx + 1)) - nums)
        if missing:
            gaps.append(f"{t}: {missing} görülmedi (1..{mx})")
    total += len(unnumbered - set(cats))  # yalnız numarasız görülen kategoriler
    return total, gaps


# ============================================================================
# main
# ============================================================================


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--name", required=True)
    ap.add_argument("--publisher", required=True)
    ap.add_argument("--subject", required=True, help="Builtin ders adı (örn. 'TYT Kimya')")
    ap.add_argument("--type", default="soru_bankasi")
    ap.add_argument("--grade-min", type=int, default=None)
    ap.add_argument("--grade-max", type=int, default=None)
    ap.add_argument("--graduate", action="store_true")
    ap.add_argument("--toc-pages", type=int, default=12)
    ap.add_argument("--offset", type=int, default=None,
                    help="Bilinen ofseti dayat (kalibrasyon atlanır); pdf_idx = kitap_sayfası - 1 + ofset")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    print(f"PDF: {Path(args.pdf).name} — {doc.page_count} sayfa\n")

    # A) İçindekiler
    print("A) İçindekiler ÇİFT okunuyor…")
    toc, warnings = read_toc(doc, args.toc_pages)
    items = toc["items"]
    print(f"   {len(items)} konu — kitap: {toc['book_title']} / {toc['publisher']} / {toc['subject_hint']}")
    if not items:
        print("İçindekiler çıkarılamadı — --toc-pages artırmayı dene.")
        return 1
    missing = [it for it in items if it["test_count"] is None]
    print(f"   test sayısı içindekilerde: {len(items)-len(missing)}/{len(items)} konu")

    offset = 0
    if missing:
        # B) Ofset
        if args.offset is not None:
            offset = args.offset
            print(f"\nB) Ofset dayatıldı: {offset}")
        else:
            print("\nB) Sayfa hizalama kalibre ediliyor…")
            sample_pages = [it["page"] for it in items if it["page"]][:3]
            off, w = calibrate_offset(doc, sample_pages)
            warnings += w
            if off is not None:
                offset = off
            print(f"   ofset: {offset} (pdf_idx = kitap_sayfası - 1 + {offset})")

        # C) Gövde taraması — yalnız sayısı eksik konuların aralıkları
        pages_by_item: dict[int, tuple[int, int]] = {}
        book_last = doc.page_count - offset
        for i, it in enumerate(items):
            if it["page"] is None:
                continue
            nxt = next((items[j]["page"] for j in range(i + 1, len(items)) if items[j]["page"]), book_last + 1)
            pages_by_item[i] = (it["page"], min(nxt, book_last + 1))
        need_pages: list[int] = []
        for i, it in enumerate(items):
            if it["test_count"] is None and i in pages_by_item:
                s, e = pages_by_item[i]
                need_pages.extend(range(s, e))
        need_pages = sorted(set(bp for bp in need_pages if 0 <= bp - 1 + offset < doc.page_count))
        print(f"\nC) Gövde taraması: {len(need_pages)} sayfa × 2 bağımsız geçiş…")
        s1 = scan_ranges_once(doc, need_pages, offset)
        print("   1. geçiş tamam — 2. geçiş (doğrulama)…")
        s2 = scan_ranges_once(doc, need_pages, offset)
        for i, it in enumerate(items):
            if it["test_count"] is not None:
                it["source"] = "toc"
                continue
            if i not in pages_by_item:
                it["source"] = "unknown"
                it["flag"] = "no_page"
                warnings.append(f"'{it['label']}': sayfa numarası yok — taranamadı, elle doldurun.")
                continue
            s, e = pages_by_item[i]
            t1, g1 = analyze_range(s, e, s1)
            t2, g2 = analyze_range(s, e, s2)
            it["test_count"] = max(t1, t2) or None
            it["source"] = "scan"
            if t1 != t2:
                it["flag"] = "scan_mismatch"
                warnings.append(f"'{it['label']}': iki tarama uyuşmadı ({t1}/{t2}) — büyük olan alındı, kontrol edin.")
            for g in set(g1) | set(g2):
                warnings.append(f"'{it['label']}': zincir kopuğu {g}")
    else:
        for it in items:
            it["source"] = "toc"

    # D) Rapor + JSON
    print(f"\n{'KONU':<44}{'test':>5}  kaynak")
    total = 0
    for it in items:
        tc = it["test_count"]
        total += tc or 0
        flag = f"  ⚠ {it['flag']}" if it.get("flag") else ""
        print(f"{it['label']:<44}{tc if tc else '?':>5}  {it.get('source','?')}{flag}")
    print(f"\nTOPLAM: {len(items)} konu · {total} test")
    for w in warnings:
        print(f"  UYARI: {w}")

    out = {
        "name": args.name,
        "publisher": args.publisher,
        "subject": args.subject,
        "type": args.type,
        "target_grade_min": args.grade_min,
        "target_grade_max": args.grade_max,
        "target_graduate": bool(args.graduate),
        "sections": [
            {"label": it["label"], "test_count": it["test_count"], "source": it.get("source"),
             **({"page": it["page"]} if it.get("page") else {}),
             **({"flag": it["flag"]} if it.get("flag") else {})}
            for it in items
        ],
        "warnings": warnings,
    }
    out_path = args.out or (Path(args.pdf).stem[:40].strip().replace(" ", "_") + "_yapi.json")
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON: {out_path}  →  seed: PYTHONPATH=. python scripts/seed_book_catalog_json.py {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
