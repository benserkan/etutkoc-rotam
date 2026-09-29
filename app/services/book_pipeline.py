"""Kitap yapısı boru hattı — tam kitap PDF'inden katalog-hazır yapı (TEK MERKEZ).

Önceden yalnız `scripts/book_structure_pipeline.py` CLI'ıydı; 2026-09-29'da
süper admin panelindeki arka plan işine (`book_scan_jobs`) taşındı. CLI artık
bu modülü çağıran ince sarmalayıcıdır.

Aşamalar:
  A) İÇİNDEKİLER — ilk N sayfa, ÇİFT bağımsız Gemini okuma (dijital PDF'te metin).
  B) SAYFA HİZALAMA — basılı sayfa numarasından PDF-indeks ofseti.
  C) GÖVDE TARAMASI — yalnız test sayısı içindekilerde olmayan konular: metin
     katmanı (deterministik, bedava) ya da görüntü şeritleri × 2 bağımsız geçiş;
     bant numaralarından seri-yürüyüş sayımı + zincir denetimi.
  D) SAĞLAMLIK KAPILARI — eksik sayı / iki tarama uyuşmazlığı / zincir kopukluğu /
     sayfa-test oranı / içindekiler okuma farkı. Kapıdan geçemeyen iş "elle
     incele" bayrağı taşır; sonuç her durumda TASLAKTIR (admin onaylar).
Kredi DÜŞMEZ (kitap yapısı kişisel veri değil → ücretsiz anahtar).
"""
from __future__ import annotations

import base64
import logging
import re
import unicodedata
from typing import Any, Callable

try:
    import pymupdf as fitz  # PyMuPDF (yeni ad)
except ImportError:  # pragma: no cover — eski kurulum
    import fitz

from app.services import gemini

logger = logging.getLogger(__name__)

ProgressFn = Callable[[int, str], None]

BATCH = 10
STRIP_H = 0.20
STRIP_DPI = 120

TOC_PROMPT = """Sana bir soru bankasının İLK sayfalarını sırayla veriyorum (kapak/tanıtım/içindekiler karışık olabilir).
GÖREV: İÇİNDEKİLER sayfalarını bul ve konu listesini çıkar.
KURALLAR:
- Yalnız içindekilerde GERÇEKTEN yazan konu/bölüm satırlarını al; sırayla.
- "BÖLÜM 07", "ÜNİTE 3" gibi SADECE NUMARA taşıyan grup başlıklarını ALMA — altındaki konuları al.
  Ünite/bölüm başlığı AD içeriyorsa ("ÜNİTE 1 İNSAN FİZYOLOJİSİ") o da bir KONU satırı DEĞİLDİR;
  altındaki konulara "unit" alanı olarak yaz.
- DİKKAT: "Ünite Değerlendirme", "Ünite Sonu Testi", "Genel Tekrar" gibi ünite içi/sonu
  ÇALIŞMA satırları KONUDUR — bunları AL (unit alanıyla birlikte).
- Önsöz, cevap anahtarı, çözümler, sözlük, dizin gibi çalışma-dışı satırları ALMA.
- ÇOK ÖNEMLİ — bazı kitapların içindekileri HER TESTİ ayrı satır listeler
  ("Kazanım Testi - 1", "Kazanım Testi - 2", "Test 3", "ÖSYM Tipi"...). Bu satırlar
  KONU DEĞİLDİR ve items'a TEK TEK YAZILMAZ: konu = üst başlık satırı (örn.
  "DOĞRUDA AÇILAR"); test_count = o konunun altındaki test satırlarının TOPLAM ADEDİ
  (Kazanım Testi + Test + ÖSYM Tipi vb. hepsi); page = konunun İLK sayfası.
  "Bilgi Alanı", "Konu Anlatımı", "Çözümler" satırları test SAYILMAZ; ADLI test
  satırları ("Yıldızlar Yarışıyor", "Sarmal Test", "Bölüm Değerlendirme") test SAYILIR.
  İçindekiler listesini SONUNA KADAR işle — SON KONUYU DÜŞÜRME.
- Her konu için: label (yazıldığı gibi), unit (bulunduğu ünitenin/bölümün adı; yoksa null),
  page (satırın gösterdiği başlangıç sayfa numarası; yoksa null),
  test_count (içindekiler o konu için test adedi VERİYORSA veya test satırlarından SAYILABİLİYORSA; vermiyorsa null — ASLA TAHMİN ETME).
- Kitap adı / yayınevi görünüyorsa yaz; ders tahmini (subject_hint) yaz.
YALNIZ şu JSON: {"book_title": str|null, "publisher": str|null, "subject_hint": str|null,
 "items": [{"label": str, "unit": str|null, "page": int|null, "test_count": int|null}]}"""

PAGENO_PROMPT = """Sana kitap sayfalarının ALT şeritlerini sırayla veriyorum.
Her şeritte sayfanın BASILI sayfa numarası görünebilir (genelde alt-orta/alt-köşe).
Her şerit için basılı numarayı yaz; görünmüyorsa null.
YALNIZ şu JSON: {"pages": [int|null, ...]} — şerit sayısı kadar, sırayla."""

BANNER_PROMPT = """Sana bir soru bankasının sayfa ÜST ŞERİTLERİNİ sırayla veriyorum.
Bir soru grubunun sayfasında başlık BANDI bulunabilir: "TEST 3", "3. bölüm KAZANIM ODAKLI SORULAR", "KARMA SORULAR 2", "GÜNLÜK HAYAT UYGULAMALARI 1", "ÖSYM TADINDA SORULAR 2", "ORİJİNAL SORULAR" gibi grup başlığı (logolu/rozet/puzzle çerçeveli olabilir; numara rozetin İÇİNDE olabilir).
- "t" alanına bandın TAM metnini yaz (tür adı dahil — "KARMA SORULAR", "GÜNLÜK HAYAT UYGULAMALARI" gibi ayrımlar önemli).
- DİKKAT: sayfada PAZARLAMA ROZETİ olabilir ("1 SORU 1 YORUM", "3D", seri logosu) — bunlar bant DEĞİLDİR ve numarası ALINMAZ. "TEST 8" ile "1 SORU YORUM" aynı şeritteyse numara 8'dir (TEST'in bitişiğindeki numara esastır).
- "N. BÖLÜM" / "N. ÜNİTE" AYRAÇ sayfası (bölüm kapağı) bant DEĞİLDİR → null; bölüm numarasını test numarası sanma.
- Bant NUMARALI ise: {"n": numara, "t": "bant metni"}
- Bant var ama NUMARASIZ ise (örn. yalnız "ORİJİNAL SORULAR"): {"n": null, "t": "bant metni"}
- Bant yoksa (yalnız KONU ADI başlığı, filigran, boş sayfa) → null. Konu adı başlığı bant DEĞİLDİR.
YALNIZ şu JSON: {"strips": [ {"n":int|null,"t":str} | null, ... ]} — şerit sayısı kadar, sırayla."""


def norm_cat(t: str | None) -> str:
    """Bant kategorisi. AYRI kategoriler ayrı sayaçtır (seri-yürüyüş kategori
    başına koşar) — Fizik/Biyoloji'de 'Karma Sorular'/'Günlük Hayat' kendi
    1..N'iyle akar; tek kovada birleşince kaçan sayfalar hayalet seri üretir.
    Ortak-sayaçlı çiftlerde (Biyotik ANALİZ→SENTEZ) ayırmak zararsız:
    seri-yürüyüş min..max saydığından toplam değişmez."""
    if not t:
        return "test"
    s = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    if "osym" in s or "tadinda" in s:
        return "osym_tadinda"
    if "orijinal" in s or "original" in s:
        return "orijinal"
    if "karma" in s:
        return "karma"
    if "gunluk" in s or "hayat" in s:
        return "gunluk"
    if "sentez" in s:
        return "sentez"
    return "test"


def _gen(parts, timeout=90, max_output_tokens=16384):
    # 16K çıktı bütçesi: 2.5 ailesinde düşünme tokenları bütçeden düşer —
    # uzun içindekiler JSON'u 8K'da kesilip AIInvalidResponse veriyordu.
    raw = gemini.generate(parts, personal_data=False, json_mode=True,
                          timeout=timeout, prefer_fast=True,
                          max_output_tokens=max_output_tokens)
    return gemini.extract_json(raw)


def _img_part(pix) -> dict:
    return gemini.inline_part(base64.b64encode(pix.tobytes("png")).decode("ascii"), "image/png")


# ============================================================================
# A) İçindekiler
# ============================================================================


def read_toc_once(doc, n_pages: int) -> dict:
    # Dijital PDF: içindekiler METİNDEN okunur (iki okuma aynı girdiyi görür →
    # satır düşürme/uydurma azalır); taranmışta görüntüden.
    pages = [doc[i] for i in range(min(n_pages, doc.page_count))]
    texts = [p.get_text().strip() for p in pages]
    if sum(1 for t in texts if len(t) > 150) >= len(pages) * 0.6:
        blob = "\n\n".join(f"--- SAYFA {i+1} ---\n{t[:4000]}" for i, t in enumerate(texts))
        parts = [gemini.text_part(TOC_PROMPT + "\n\nSAYFA METİNLERİ:\n" + blob)]
    else:
        parts = [_img_part(p.get_pixmap(dpi=75)) for p in pages]
        parts.append(gemini.text_part(TOC_PROMPT))
    try:
        data = _gen(parts, timeout=120)
    except Exception:  # noqa: BLE001 — tek tekrar (kesik JSON / geçici hata)
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
        unit = it.get("unit")
        items.append({
            "label": label[:255],
            "unit": str(unit).strip()[:120] if unit else None,
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
        r1 = r2 = None
        err = None
        try:
            r1 = f1.result()
        except Exception as e:  # noqa: BLE001
            err = e
        try:
            r2 = f2.result()
        except Exception as e:  # noqa: BLE001
            err = e
    if r1 is None and r2 is None:
        raise err  # her iki okuma da çöktü
    if r1 is None or r2 is None:
        warnings.append("İçindekiler okumalarından biri başarısız — TEK okuma esas alındı, kontrol edin.")
        one = r1 or r2
        return one, warnings
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
# C) Gövde taraması (v3: metin katmanı > görüntü; global numara-örüntüsü sayacı)
# ============================================================================

BannerMap = dict[int, list[tuple[int | None, str]]]  # kitap sayfası → [(numara|None, kategori)]


def scan_ranges_once(doc, book_pages: list[int], offset: int, progress=None) -> BannerMap:
    out: BannerMap = {}
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
                    logger.warning("tarama parçası %s hata: %s", i // BATCH + 1, e)
                else:
                    import time as _t
                    _t.sleep(3)
        for j, bp in enumerate(chunk):
            v = got[j] if j < len(got) else None
            if isinstance(v, dict) and v.get("t"):
                ts = unicodedata.normalize("NFKD", str(v["t"])).encode("ascii", "ignore").decode().lower()
                # "N. BÖLÜM"/"N. ÜNİTE" ayraç kapağı test bandı değildir (Aydın dersi)
                if ("bolum" in ts or "unite" in ts) and not any(k in ts for k in ("test", "soru", "osym", "orijinal", "analiz", "sentez", "karma")):
                    continue
                n = v.get("n")
                out[bp] = [(n if isinstance(n, int) else None, norm_cat(v.get("t")))]
        if progress is not None:
            progress(i + len(chunk), len(book_pages))
    return out


# Metin-katmanlı (dijital) PDF: bantlar üst bölge BÜYÜK PUNTO metninden
# deterministik çıkar. DERS (Biyotik): cevap-anahtarı sayfalarında "ANALİZ 1 2 3…"
# soru-numarası ızgarası küçük fontta — yalnız iri span'lerde arayınca hayalet
# numara girmez; gerçek bant numarası iri fonttadır.
_TXT_BANNERS = [
    (re.compile(r"ÖSYM\s*TADINDA\D{0,30}?(\d{1,3})", re.IGNORECASE), "osym_tadinda"),
    (re.compile(r"OR[İIiı]J[İIiı]NAL\s*(?:®\s*)?SORULAR\D{0,15}?(\d{1,3})?", re.IGNORECASE), "orijinal"),
    (re.compile(r"ANAL[İIiı]Z\D{0,15}?(\d{1,3})", re.IGNORECASE), "test"),
    (re.compile(r"SENTEZ\D{0,15}?(\d{1,3})", re.IGNORECASE), "test"),
    (re.compile(r"(\d{1,3})\s*\.\s*TEST\b", re.IGNORECASE), "test"),
    (re.compile(r"\bTEST\D{0,10}?(\d{1,3})", re.IGNORECASE), "test"),
]
_TXT_TOP_FRAC = 0.30
_TXT_HEADER_FRAC = 0.09  # bölüm adı başlığı en tepede; soru metni ~%10'dan başlar
_TXT_BIG_SIZE = 12.0


def _page_top_text(page, min_size: float | None = None, frac: float = _TXT_TOP_FRAC) -> str:
    h = page.rect.height
    lines: list[str] = []
    for blk in page.get_text("dict").get("blocks", []):
        if blk.get("type") != 0 or blk["bbox"][1] > h * frac:
            continue
        for ln in blk.get("lines", []):
            spans = ln.get("spans", [])
            if min_size is not None:
                spans = [sp for sp in spans if sp.get("size", 0) >= min_size]
            if spans:
                lines.append(" ".join(sp.get("text", "") for sp in spans))
    return " ".join(lines)


def has_text_layer(doc, book_pages: list[int], offset: int) -> bool:
    sample = book_pages[:: max(1, len(book_pages) // 10)][:10]
    ok = sum(1 for bp in sample if len(doc[bp - 1 + offset].get_text().strip()) > 120)
    return bool(sample) and ok / len(sample) >= 0.7


def scan_ranges_text(doc, book_pages: list[int], offset: int) -> BannerMap:
    out: BannerMap = {}
    for bp in book_pages:
        txt = _page_top_text(doc[bp - 1 + offset], min_size=_TXT_BIG_SIZE)
        found: list[tuple[int | None, str]] = []
        for rex, cat in _TXT_BANNERS:
            for m in rex.finditer(txt):
                n = m.group(1)
                found.append((int(n) if n else None, cat))
        if found:
            out[bp] = sorted(set(found), key=lambda x: (x[1], x[0] or 0))
    return out


def _norm_label(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def attribute_pages_text(doc, items: list[dict], offset: int, banner_pages: list[int]) -> dict[int, list[int]]:
    """Dijital PDF'te her sayfanın üst başlığında BÖLÜM ADI yazar → bantlı
    sayfalar içindekiler sayfa numarasına güvenmeden başlık eşleşmesiyle
    sahiplenilir (monoton ilerleyen imleç + en uzun etiket; mükerrer etiketler
    ["Ünite Değerlendirme"] imleç sayesinde doğru üniteye düşer)."""
    labels = [(i, _norm_label(it.get("base_label") or it["label"])) for i, it in enumerate(items)]
    owned: dict[int, list[int]] = {}
    unmatched = 0
    cur = 0
    for bp in banner_pages:
        # Yalnız EN TEPE bandı (başlık satırı) — soru metnindeki konu-adı geçişleri
        # ("sindirim", "sinir sistemi") sayfayı yanlış konuya atamasın.
        txt = _norm_label(_page_top_text(doc[bp - 1 + offset], frac=_TXT_HEADER_FRAC))
        best, blen = None, 0
        for i, nl in labels:
            if i >= cur and nl and nl in txt and len(nl) > blen:
                best, blen = i, len(nl)
        if best is None:  # başlık eşleşmedi → sahiplenme (geriye dönük atama YASAK)
            unmatched += 1
            continue
        cur = best
        owned.setdefault(best, []).append(bp)
    if unmatched:
        logger.info("başlık eşleşmeyen bantlı sayfa: %s", unmatched)
    return owned


def _series_walk(nums: list[int]) -> tuple[int, list[str]]:
    """Sayfa SIRASINDAKİ bant numaralarından test sayısı: ardışık tekrar = aynı
    test (bant her sayfada tekrarlanır); numara DÜŞÜŞÜ = yeni alt seri (Fizik'te
    bir içindekiler-konusu içinde alt bölümler 1'den yeniden başlar). Toplam =
    Σ(seri_max − seri_min + 1) — konu-başına 1..N (345) ve süren sayaç m..M
    (Biyotik) tek kuralda. GÜRÜLTÜ ATLAMA (KR Akademi "1 SORU 1 YORUM" rozeti):
    akışı kesen düşük numaradan sonra seri KALDIĞI YERDEN sürüyorsa
    (…8, 1, 9 → 9 = son±1) o gözlem rozet/yanlış-okumadır, atlanır; gerçek alt
    seri başlangıcı (…5, 1, 2) devam etmediği için etkilenmez."""
    series: list[dict] = []
    cur: dict | None = None
    for i, n in enumerate(nums):
        if cur is not None and n == cur["last"]:
            continue
        if cur is not None and n < cur["last"]:
            nxt = next((m for m in nums[i + 1:] if m != n), None)
            if nxt is not None and cur["last"] <= nxt <= cur["last"] + 1:
                continue  # gürültü: mevcut seri devam ediyor
        if cur is None or n < cur["last"]:
            cur = {"min": n, "max": n, "seen": {n}, "last": n}
            series.append(cur)
        else:
            cur["max"] = max(cur["max"], n)
            cur["seen"].add(n)
            cur["last"] = n
    total, gaps = 0, []
    for s in series:
        total += s["max"] - s["min"] + 1
        missing = sorted(set(range(s["min"], s["max"] + 1)) - s["seen"])
        if missing:
            gaps.append(f"{missing} görülmedi ({s['min']}..{s['max']})")
    return total, gaps


def count_items_global(ordered: list[tuple[int, list[int] | None, bool]], banners: BannerMap):
    """ordered: (item_idx, sahiplenilen sayfalar|None, uygula). Kategori başına
    seri-yürüyüş sayımı (_series_walk); yalnız NUMARASIZ görülen kategori
    (tekil "ORİJİNAL SORULAR") 1 sayılır."""
    counts: dict[int, int | None] = {}
    warns: list[tuple[int, str]] = []
    for idx, pages, apply in ordered:
        if not apply:
            continue
        if pages is None:
            counts[idx] = None
            continue
        cats: dict[str, list[int]] = {}
        unnum: set[str] = set()
        for bp in pages:
            for n, t in banners.get(bp, []):
                if n is None:
                    unnum.add(t)
                else:
                    cats.setdefault(t, []).append(n)
        total = 0
        for t, nums in sorted(cats.items()):
            c, gaps = _series_walk(nums)
            total += c
            for g in gaps:
                warns.append((idx, f"{t}: {g}"))
        total += len(unnum - set(cats))
        counts[idx] = total or None
    return counts, warns




# ============================================================================
# Uçtan uca koşu + sağlamlık kapıları
# ============================================================================

# Soru bankalarında ölçülen bant: sayfa/test ≈ 1,8–2,2 (345/Aydın/Orbital).
# Kapı biraz geniş tutulur; dışı "elle incele" der (engellemez).
PAGES_PER_TEST_BAND = (1.5, 2.8)


class PipelineError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _gate(code: str, label: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"code": code, "label": label, "ok": ok, "detail": detail}


def run_pipeline(
    pdf_path: str,
    *,
    toc_pages: int = 12,
    offset: int | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """Tam kitap PDF'i → bölüm + test sayısı taslağı + sağlamlık kapıları.

    progress(yüzde, aşama_metni) uzun koşuda ilerleme bildirir.
    Raises PipelineError (pdf_unreadable / no_toc).
    """
    def _p(pct: int, stage: str) -> None:
        if progress is not None:
            progress(max(0, min(100, pct)), stage)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:  # noqa: BLE001
        raise PipelineError("pdf_unreadable", f"PDF açılamadı: {e}")
    with doc:
        page_count = doc.page_count
        _p(3, f"İçindekiler iki kez okunuyor ({page_count} sayfalık PDF)…")
        toc, warnings = read_toc(doc, toc_pages)
        toc_level_warn = any("farklı satır sayısı" in w for w in warnings)
        items = toc["items"]
        if not items:
            raise PipelineError(
                "no_toc",
                f"İlk {toc_pages} sayfada içindekiler bulunamadı — içindekiler daha ilerideyse "
                "'içindekiler sayfa sayısı'nı artırıp yeniden dene.",
            )
        _p(15, f"İçindekiler: {len(items)} konu")

        # Azınlık-TOC-sayısı güvensizdir (3D TYT Fizik dersi)
        toc_counted = [it for it in items if it["test_count"] is not None]
        if toc_counted and len(toc_counted) < max(3, len(items) // 5):
            for it in toc_counted:
                it["toc_claimed"] = it["test_count"]
                it["test_count"] = None
            warnings.append(
                f"İçindekiler test sayısı yalnız {len(toc_counted)}/{len(items)} satırda — "
                "azınlık sayı model çıkarımı olabilir, o konular da gövde taramasıyla sayıldı.")
        missing = [it for it in items if it["test_count"] is None]

        from collections import Counter

        dupes = {lbl for lbl, c in Counter(it["label"] for it in items).items() if c > 1}
        for it in items:
            if it["label"] in dupes and it.get("unit"):
                it["base_label"] = it["label"]
                it["label"] = f"{it['label']} ({it['unit']})"[:255]

        mode = "toc"
        used_offset = 0
        pages_by_item: dict[int, tuple[int, int]] = {}
        scan_debug: dict[str, Any] | None = None
        if missing:
            if offset is not None:
                used_offset = offset
            else:
                _p(17, "Basılı sayfa numaraları hizalanıyor…")
                sample_pages = [it["page"] for it in items if it["page"]][:3]
                off, w = calibrate_offset(doc, sample_pages)
                warnings += w
                if off is not None:
                    used_offset = off
            book_last = page_count - used_offset
            for i, it in enumerate(items):
                if it["page"] is None:
                    continue
                nxt = next((items[j]["page"] for j in range(i + 1, len(items)) if items[j]["page"]),
                           book_last + 1)
                pages_by_item[i] = (it["page"], min(nxt, book_last + 1))
            need_pages: list[int] = []
            for i, it in enumerate(items):
                if it["test_count"] is None and i in pages_by_item:
                    st, en = pages_by_item[i]
                    need_pages.extend(range(st, en))
            need_pages = sorted({bp for bp in need_pages if 0 <= bp - 1 + used_offset < page_count})

            text_mode = has_text_layer(doc, need_pages, used_offset) if need_pages else False
            ordered: list[tuple[int, list[int] | None, bool]] = []
            passes: list[BannerMap] = []
            if text_mode:
                first_page = min((it["page"] for it in items if it["page"]), default=1)
                all_pages = [bp for bp in range(first_page, book_last + 1)
                             if 0 <= bp - 1 + used_offset < page_count]
                _p(22, f"Gövde taraması (metin katmanı): {len(all_pages)} sayfa…")
                tmap = scan_ranges_text(doc, all_pages, used_offset)
                if len(tmap) < len(all_pages) * 0.25:
                    text_mode = False
                    warnings.append("Metin katmanında az bant bulundu — görüntü taramasına dönüldü.")
                else:
                    owned = attribute_pages_text(doc, items, used_offset, sorted(tmap))
                    for i, it in enumerate(items):
                        pages = owned.get(i)
                        if pages:
                            ordered.append((i, pages, it["test_count"] is None))
                        elif it["test_count"] is None:
                            ordered.append((i, None, True))
                    passes = [tmap]
            if not text_mode:
                total_pages = len(need_pages)

                def _scan_progress(base: int, label: str):
                    def cb(done: int, total: int) -> None:
                        _p(base + int(37 * done / max(1, total)),
                           f"Gövde taraması {label}: {done}/{total} sayfa")
                    return cb

                _p(20, f"Gövde taraması: {total_pages} sayfa × 2 bağımsız görüntü geçişi…")
                s1 = scan_ranges_once(doc, need_pages, used_offset,
                                      progress=_scan_progress(20, "1. geçiş"))
                s2 = scan_ranges_once(doc, need_pages, used_offset,
                                      progress=_scan_progress(57, "2. geçiş (doğrulama)"))
                passes = [s1, s2]
                ordered = []
                for i, it in enumerate(items):
                    rng = pages_by_item.get(i)
                    pages = list(range(rng[0], rng[1])) if rng else None
                    ordered.append((i, pages, it["test_count"] is None))
            mode = "text" if text_mode else "vision"
            _p(95, "Sayılar hesaplanıyor…")
            results = [count_items_global(ordered, pm) for pm in passes]
            for i, it in enumerate(items):
                if it["test_count"] is not None:
                    it["source"] = "toc"
                    continue
                if not text_mode and i not in pages_by_item:
                    it["source"] = "unknown"
                    it["flag"] = "no_page"
                    warnings.append(f"'{it['label']}': sayfa numarası yok — taranamadı, elle doldurun.")
                    continue
                vals = [r[0].get(i) for r in results]
                gaps_per_pass = [sum(1 for idx, _ in r[1] if idx == i) for r in results]
                src = "scan_text" if text_mode else "scan"
                if len(vals) > 1 and vals[0] != vals[1] and min(gaps_per_pass) != max(gaps_per_pass):
                    it["test_count"] = vals[gaps_per_pass.index(min(gaps_per_pass))]
                    it["source"] = src
                    it["flag"] = "scan_mismatch"
                    warnings.append(
                        f"'{it['label']}': iki tarama uyuşmadı ({vals[0]}/{vals[1]}) — zinciri temiz "
                        f"geçiş ({it['test_count']}) alındı.")
                    continue
                it["test_count"] = max((v for v in vals if v), default=None)
                it["source"] = src
                if it["test_count"] is None:
                    it["flag"] = "no_banner"
                    warnings.append(f"'{it['label']}': bant bulunamadı — elle doldurun.")
                elif len(vals) > 1 and vals[0] != vals[1]:
                    it["flag"] = "scan_mismatch"
                    warnings.append(
                        f"'{it['label']}': iki tarama uyuşmadı ({vals[0]}/{vals[1]}) — büyük olan "
                        "alındı, kontrol edin.")
            for it in items:
                claimed = it.get("toc_claimed")
                if claimed is not None and it.get("test_count") not in (None, claimed):
                    warnings.append(
                        f"'{it['label']}': içindekiler {claimed} demişti, tarama {it['test_count']} "
                        "buldu — tarama esas alındı.")
            seen_w: set[tuple[int, str]] = set()
            for _, ws in results:
                for idx, msg in ws:
                    if (idx, msg) not in seen_w:
                        seen_w.add((idx, msg))
                        items[idx]["chain_gap"] = True
                        warnings.append(f"'{items[idx]['label']}': {msg}")
            scan_debug = {
                "mode": mode,
                "passes": [
                    {str(bp): ["%s#%s" % (t, n if n is not None else "-") for n, t in v]
                     for bp, v in sorted(pm.items())}
                    for pm in passes
                ],
            }
        else:
            for it in items:
                it["source"] = "toc"

    # --- Sağlamlık kapıları ---
    unfilled = [it for it in items if not it.get("test_count")]
    mism = [it for it in items if it.get("flag") == "scan_mismatch"]
    gaps = [it for it in items if it.get("chain_gap")]
    scanned = [(i, it) for i, it in enumerate(items)
               if it.get("source") in ("scan", "scan_text") and it.get("test_count")
               and i in pages_by_item]
    gates = [
        _gate("toc_reads", "İçindekiler iki okumada aynı", not toc_level_warn,
              "İki okuma aynı satır sayısını verdi." if not toc_level_warn
              else "İki okuma farklı satır sayısı verdi — konu listesini kitapla karşılaştır."),
        _gate("unfilled", "Her bölümün test sayısı bulundu", not unfilled,
              "Eksik yok." if not unfilled
              else f"{len(unfilled)} bölümde sayı bulunamadı: "
              + ", ".join(it["label"] for it in unfilled[:5])),
    ]
    if mode == "vision":
        gates.append(_gate("scan_agree", "İki bağımsız tarama uyuştu", not mism,
                           "Tüm bölümlerde iki geçiş aynı sayıyı verdi." if not mism
                           else f"{len(mism)} bölümde geçişler farklı: "
                           + ", ".join(it["label"] for it in mism[:5])))
    if mode in ("vision", "text"):
        gates.append(_gate("chain", "Test numaraları kesintisiz (1..N)", not gaps,
                           "Zincir kopukluğu yok." if not gaps
                           else f"{len(gaps)} bölümde atlanan numara var — kaçırılmış sayfa ya da "
                           "yayınevi dizgi atlaması olabilir."))
        if scanned:
            span = sum(pages_by_item[i][1] - pages_by_item[i][0] for i, _ in scanned)
            tests = sum(it["test_count"] for _, it in scanned)
            ratio = span / tests if tests else 0
            lo, hi = PAGES_PER_TEST_BAND
            gates.append(_gate("ratio", "Sayfa/test oranı olağan", lo <= ratio <= hi,
                               f"Taranan bölümlerde {span} sayfa / {tests} test = "
                               f"{ratio:.2f} sayfa/test (olağan {lo}–{hi})."))
    needs_review = not all(g["ok"] for g in gates)
    _p(100, "Bitti — kapılardan geçemeyenleri elle incele." if needs_review else "Bitti")
    return {
        "book_title": toc.get("book_title"),
        "publisher": toc.get("publisher"),
        "subject_hint": toc.get("subject_hint"),
        "page_count": page_count,
        "offset": used_offset,
        "mode": mode,
        "sections": [
            {
                "label": it["label"],
                "test_count": it.get("test_count"),
                "source": it.get("source"),
                "page": it.get("page"),
                "flag": it.get("flag"),
            }
            for it in items
        ],
        "total_tests": sum(it.get("test_count") or 0 for it in items),
        "warnings": warnings,
        "gates": gates,
        "needs_review": needs_review,
        "scan_debug": scan_debug,
    }
