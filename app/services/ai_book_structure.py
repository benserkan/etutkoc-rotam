"""Kitap yapısı okuma motoru — içindekiler foto/PDF → ünite + BİREBİR test sayısı.

Ortak Kitap Kataloğu'nun besleme aracı: koç (veya süper admin) kitabın
İÇİNDEKİLER sayfalarını fotoğraflar ya da yayınevinin örnek PDF'ini yükler;
Gemini vision yapıyı KİTAPTAN OKUYARAK çıkarır. Kapak fotoğrafı içerik
üretmez — yalnız kitabı TANIMAYA yarar (`identify_cover`).

Uydurma önleme (3 katman):
  1. ÇİFT OKUMA — iki bağımsız Gemini çağrısı paralel; test sayısı çelişen
     satır `suspect=True` (önizlemede amber, koç düzeltir).
  2. NULL KORUNUR — içindekilerde test sayısı yazmıyorsa model null döndürür;
     satır boş gelir, ASLA tahmin edilmez.
  3. `NotATocError` — <2 bölüm çıkarsa belge içindekiler değildir (kapak/
     rastgele sayfa) → 422.

KVKK/maliyet: kitap içindekiler sayfası kişisel veri DEĞİL →
`personal_data=False` (ücretsiz anahtar önce) → koçtan KREDİ DÜŞMEZ.
Ölçüm + kötüye kullanım tavanı için 0 kredilik UsageEvent yazılır
(`record_book_read` / `book_read_count_today`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.services import gemini
from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable  # noqa: F401 (router reuse)

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGES = 6
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PDF_BYTES = 10 * 1024 * 1024
# Tek yükleme ("Kapak + içindekiler"): büyük PDF kabul edilir, yalnız ilk
# sayfaları okunur (kapak + içindekiler kitabın başındadır).
MAX_SCAN_PDF_BYTES = 80 * 1024 * 1024
MAX_SCAN_IMAGES = 8
# Fasikül setleri (6 kapak + 6 içindekiler) 12 sayfaya sığmıyordu (2026-10-27).
SCAN_PDF_PAGES = 20

# Koç başına günlük okuma tavanı (kredi yok — yalnız kötüye kullanım rayı).
AI_BOOK_READ_DAILY_LIMIT = 30

# İçindekiler tipik 1-3 sayfa; 2.5'in düşünme tokenı payıyla geniş bütçe
# (yarım JSON = parse hatası dersi).
_MAX_OUTPUT_TOKENS = 32768
_TIMEOUT = 90.0


class NotATocError(Exception):
    """Yüklenen görsel/PDF bir içindekiler sayfası gibi görünmüyor."""


_READ_PROMPT = """Sana bir ders kitabının (soru bankası/fasikül/deneme kitabı) İÇİNDEKİLER sayfalarını veriyorum. Görevin kitabın yapısını UYDURMADAN çıkarmak.

KURALLAR (çok önemli):
- Yalnız belgede GERÇEKTEN görünen bölümleri yaz; asla bölüm uydurma.
- Bölüm/ünite adını yazıldığı gibi kopyala (kısaltmaysa kısaltılmış haliyle). "1. ÜNİTE", "BÖLÜM 3" gibi önekleri koru.
- TEST SAYISI EN KRİTİK ALAN: test_count = o ünitenin/konunun içindeki TEST ADEDİ.
  * İçindekiler test listesini ünitenin altında ayrı satırlar olarak veriyorsa
    ("TEST 1, TEST 2, ... TEST 14" veya "Mini Test - 1", "Kazanım Testi 3" gibi)
    bu satırları AYRI BÖLÜM OLARAK YAZMA — ait oldukları konu başlığına SAY:
    o konunun test_count'u bu satırların adedidir (konu başlığından sonra,
    bir sonraki konu başlığına kadar gelen test satırları o konuya aittir).
  * Sayfa numaralarını sayma, TESTLERİ say.
  * İçindekiler test bilgisi hiç vermiyorsa test_count=null yaz — ASLA TAHMİN ETME.
- page: bölümün içindekilerde YAZAN başlangıç sayfa numarası (tam sayı); yazmıyorsa null. Sayfa numarasını ASLA uydurma.
- ÇALIŞMA BÖLÜMÜ OLMAYAN satırları listeye ALMA: önsöz/sunuş, içindekiler,
  cevap anahtarı, çözümler, kavramlar sözlüğü, dizin, yazar hakkında vb.
- SADECE NUMARA taşıyan GRUP başlıklarını listeye ALMA: "BÖLÜM 07", "ÜNİTE 3"
  gibi altında konu listesi olan ara başlıklar bölüm DEĞİLDİR — onların
  altındaki KONULARI çıkar. (Adı da olan üniteler kalır: "1. Ünite — Sayılar".)
- DÜZEY: testlerin bağlandığı düzey esas alınır.
  * Test sayısı ünite/bölüm satırında ya da ünitenin altındaki test satırlarında
    veriliyorsa ÜNİTE/BÖLÜM düzeyini çıkar.
  * İçindekiler HİÇ test bilgisi vermiyor ama ünite başlıklarının altında SAYFA
    NUMARALI KONU satırları varsa KONULARI çıkar (her biri kendi sayfasıyla).
    Ünite başlığını yine de yazarsan o satıra kind="unit" yaz; diğer tüm
    satırlar kind="topic".
- Tekrar/giriş satırlarını listeye ALMA: "Geçmişten Günümüze Bilgilerimi
  Hatırlıyorum", "Hazırbulunuşluk", "Konu Özeti", "Kavram Haritası" gibi.
- ÇOK CİLT/FASİKÜL: belge birden çok fasikülün/cildin kapağını ve içindekilerini
  içeriyorsa (sayfa numaraları her fasikülde 1'den yeniden başlar) her bölüme
  volume = fasikül/cilt numarası yaz. volumes listesine her fasikül için:
  volume, kapakta "N TEST SORUSU" gibi açık yazıyorsa test_questions = N (yoksa
  null), içindekilerdeki CEVAP ANAHTARI sayfası end_page (yoksa null).
  Tek kitapsa volume=null ve volumes=[] bırak.
- Verilen sayfaların bazıları kapak, önsöz, künye ya da soru sayfası olabilir — bunları yok say, yalnız İÇİNDEKİLER sayfalarından çıkar (kitap adı/yayınevi için kapağı kullanabilirsin).
- Birden çok görsel/sayfa verdiysem hepsi AYNI kitabın devamıdır — tek liste halinde sırayla birleştir, tekrar eden başlıkları bir kez yaz.
- Kitap adı/yayınevi belgede görünüyorsa yaz; görünmüyorsa null (çok fasikülde
  fasikül numarasını adın içine yazma: "Benim 1. Fasikülüm 8. Sınıf Matematik"
  yerine "Benim Fasikülüm 8. Sınıf Matematik").
- subject_hint: kitabın dersi (örn. "Matematik", "Fen Bilimleri", "Türkçe") — belgeden anlaşılıyorsa.
- grade_hint: hedef sınıf (5-12 tam sayı) — "8. Sınıf", "TYT" (11-12 sayılmaz, null bırak) gibi ibare belgede AÇIKÇA varsa.
- Belge bir içindekiler sayfası DEĞİLSE (kapak, rastgele sayfa, alakasız görsel) sections'ı boş liste döndür.

YALNIZ şu JSON nesnesini döndür:
{
  "book_title": "kitap adı" | null,
  "publisher": "yayınevi" | null,
  "subject_hint": "ders adı" | null,
  "grade_hint": 5-12 arası tam sayı | null,
  "sections": [
    {"label": "bölüm/ünite adı", "test_count": int | null, "page": int | null, "volume": int | null, "kind": "topic" | "unit"}
  ],
  "volumes": [
    {"volume": int, "test_questions": int | null, "end_page": int | null}
  ]
}"""


_COVER_PROMPT = """Sana bir ders kitabının KAPAK fotoğrafını veriyorum. Görevin kapaktan kitabı TANIMAK (içerik üretmek değil).

KURALLAR:
- Yalnız kapakta GERÇEKTEN yazanları çıkar; okuyamadığını null bırak.
- book_title: kitabın adı (seri adı + ders dahil, kapakta yazdığı gibi).
- publisher: yayınevi adı (logo/alt yazıdan).
- subject_hint: ders (örn. "Matematik", "Fen Bilimleri").
- grade_hint: hedef sınıf 5-12 tam sayı (kapakta "8. Sınıf" gibi AÇIK ibare varsa; "TYT"/"AYT"/"LGS" tek başına sınıf değildir → null).
- exam_hint: kapakta "LGS", "TYT", "AYT" gibi sınav ibaresi varsa aynen; yoksa null.

YALNIZ şu JSON nesnesini döndür:
{"book_title": str|null, "publisher": str|null, "subject_hint": str|null, "grade_hint": int|null, "exam_hint": str|null}"""


# =============================================================================
# Normalize + tek okuma
# =============================================================================


def _clean_str(v: Any, limit: int = 200) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s[:limit] if s else None


def _clean_count(v: Any) -> int | None:
    """test_count: null korunur (uydurma yok); 1-200 aralığına kırpılır."""
    if v is None:
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    if n < 1:
        return None
    return min(n, 200)


def _clean_page(v: Any) -> int | None:
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 2000 else None


def _clean_grade(v: Any) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 4 <= n <= 12 else None


import re as _re


def _clean_volume(v: Any) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 30 else None

# "BÖLÜM 07" / "ÜNİTE 3" / "UNIT 2" — adı olmayan salt-numara grup başlığı.
# Deterministik süzgeç (prompt kuralının kod tarafı): model kaçırırsa da girmez.
_GROUP_HEADER_RE = _re.compile(
    r"^\s*(bölüm|bolum|ünite|unite|unit|chapter|kısım|kisim)\s*[-:.]?\s*\d+\s*$",
    _re.IGNORECASE,
)


def _normalize_read(data: dict[str, Any]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for item in data.get("sections") or []:
        if not isinstance(item, dict):
            continue
        label = _clean_str(item.get("label"))
        if not label:
            continue
        if _GROUP_HEADER_RE.match(label):
            continue
        sections.append({
            "label": label,
            "test_count": _clean_count(item.get("test_count")),
            "page": _clean_page(item.get("page")),
            "volume": _clean_volume(item.get("volume")),
            "kind": "unit" if str(item.get("kind") or "").lower() == "unit" else "topic",
        })
    volumes: list[dict[str, Any]] = []
    for v in data.get("volumes") or []:
        if not isinstance(v, dict):
            continue
        no = _clean_volume(v.get("volume"))
        if no is None or any(x["volume"] == no for x in volumes):
            continue
        q = v.get("test_questions")
        try:
            q = int(q) if q is not None else None
        except (TypeError, ValueError):
            q = None
        volumes.append({"volume": no, "test_questions": q if q and 1 <= q <= 5000 else None,
                        "end_page": _clean_page(v.get("end_page"))})
    return {
        "volumes": volumes,
        "book_title": _clean_str(data.get("book_title")),
        "publisher": _clean_str(data.get("publisher")),
        "subject_hint": _clean_str(data.get("subject_hint"), 120),
        "grade_hint": _clean_grade(data.get("grade_hint")),
        "sections": sections,
    }


def _build_parts(files: list[tuple[bytes, str]]) -> list[dict[str, Any]]:
    import base64

    parts: list[dict[str, Any]] = []
    for raw, media_type in files:
        parts.append(gemini.inline_part(base64.b64encode(raw).decode("ascii"), media_type))
    parts.append(gemini.text_part(_READ_PROMPT))
    return parts


def _read_once(parts: list[dict[str, Any]]) -> dict[str, Any]:
    raw = gemini.generate(
        parts,
        personal_data=False,
        json_mode=True,
        timeout=_TIMEOUT,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        thinking_budget=4096,  # uzun içindekilerde düşünme bütçeyi yiyip yanıtı kesmesin
    )
    return _normalize_read(gemini.extract_json(raw))


# =============================================================================
# Çift okuma + birleştirme
# =============================================================================


def _norm_label(label: str) -> str:
    from app.services.curriculum_mapping import normalize

    return normalize(label)


def _labels_agree(a: str, b: str) -> bool:
    na, nb = _norm_label(a), _norm_label(b)
    if not na or not nb:
        return False
    return na == nb or na.startswith(nb) or nb.startswith(na)


def _merge_reads(r1: dict[str, Any], r2: dict[str, Any]) -> dict[str, Any]:
    """İki bağımsız okumayı birleştir; test sayısı çelişkisi → suspect.

    Hizalama sıra-bazlı (içindekiler sıralı bir listedir); uzunluklar farklıysa
    normalize-etiket eşleşmesiyle telafi edilir, yalnız ikinci okumada görünen
    bölümler sona `suspect=True` ile eklenir.
    """
    s1, s2 = r1["sections"], r2["sections"]
    warnings: list[str] = []
    merged: list[dict[str, Any]] = []

    # İki okuma FARKLI DÜZEY seçtiyse (biri üniteler, öbürü konular) sıra
    # hizalaması anlamsızdır — birleştirmek iki listeyi alt alta yapıştırır.
    # Etiket örtüşmesi küçük listenin yarısından azsa tek okuma esas alınır:
    # test sayısı daha çok olan, eşitse daha ayrıntılı (çok satırlı) olan.
    if s1 and s2:
        small, large = (s1, s2) if len(s1) <= len(s2) else (s2, s1)
        overlap = sum(1 for a in small if any(_labels_agree(a["label"], b["label"]) for b in large))
        # Uzunluk 1,5 katı ve üstü de düzey farkıdır (birinde "Ünite - Konu"
        # satırları, öbüründe yalnız üniteler — etiketler önek olarak uyuşur).
        if overlap * 2 < len(small) or (len(small) >= 4 and len(large) * 2 >= len(small) * 3):
            def _score(secs: list[dict[str, Any]]) -> tuple[int, int]:
                return (sum(1 for x in secs if x["test_count"] is not None), len(secs))

            base_r, other_r = (r1, r2) if _score(s1) >= _score(s2) else (r2, r1)
            warnings.append(
                f"İki okuma farklı düzey seçti ({len(base_r['sections'])} / "
                f"{len(other_r['sections'])} satır) — daha ayrıntılı liste alındı; "
                "bölümleri kitapla karşılaştır."
            )
            return {
                "book_title": r1["book_title"] or r2["book_title"],
                "publisher": r1["publisher"] or r2["publisher"],
                "subject_hint": r1["subject_hint"] or r2["subject_hint"],
                "grade_hint": r1["grade_hint"] or r2["grade_hint"],
                "sections": [
                    {"label": x["label"], "test_count": x["test_count"], "suspect": False,
                     "page": x.get("page"), "volume": x.get("volume"), "kind": x.get("kind", "topic")}
                    for x in base_r["sections"]
                ],
                "volumes": base_r.get("volumes") or other_r.get("volumes") or [],
                "warnings": warnings,
                "read_count": 2,
            }

    by_norm2: dict[str, dict[str, Any]] = {}
    for sec in s2:
        key = _norm_label(sec["label"])
        if key and key not in by_norm2:
            by_norm2[key] = sec

    used2: set[int] = set()

    for i, a in enumerate(s1):
        b: dict[str, Any] | None = None
        if i < len(s2) and _labels_agree(a["label"], s2[i]["label"]):
            b = s2[i]
            used2.add(id(s2[i]))
        else:
            cand = by_norm2.get(_norm_label(a["label"]))
            if cand is not None and id(cand) not in used2:
                b = cand
                used2.add(id(cand))

        label = a["label"] if len(a["label"]) >= len(b["label"] if b else "") else (b or a)["label"]
        c1 = a["test_count"]
        c2 = b["test_count"] if b else None
        suspect = False
        if b is None:
            # Yalnız birinci okumada var — ikinci okuma bölümü hiç görmedi.
            count = c1
            suspect = True
        elif c1 is not None and c2 is not None:
            count = c1
            if c1 != c2:
                suspect = True
        else:
            # Biri null: yazılı değeri al; etiketler birebir uyuşuyorsa güvenilir
            # (diğer okuma sayıyı kaçırmış), uyuşmuyorsa şüpheli.
            count = c1 if c1 is not None else c2
            if count is not None and not _labels_agree(a["label"], (b or a)["label"]):
                suspect = True
        page = a.get("page") or (b.get("page") if b else None)
        volume = a.get("volume") or (b.get("volume") if b else None)
        kind = "unit" if "unit" in (a.get("kind"), (b or {}).get("kind")) else "topic"
        merged.append({"label": label, "test_count": count, "suspect": suspect, "page": page,
                       "volume": volume, "kind": kind})

    # Yalnız ikinci okumada görünen bölümler (birincinin kaçırdıkları)
    extra = [sec for sec in s2 if id(sec) not in used2]
    for sec in extra:
        merged.append({"label": sec["label"], "test_count": sec["test_count"], "suspect": True,
                       "page": sec.get("page"), "volume": sec.get("volume"),
                       "kind": sec.get("kind", "topic")})

    if len(s1) != len(s2):
        warnings.append(
            f"İki okuma farklı bölüm sayısı buldu ({len(s1)} / {len(s2)}) — "
            "işaretli satırları kontrol edin."
        )
    suspect_count = sum(1 for m in merged if m["suspect"])
    if suspect_count:
        warnings.append(
            f"{suspect_count} satırda iki okuma uyuşmadı — sarı satırları kitapla karşılaştırın."
        )

    return {
        "book_title": r1["book_title"] or r2["book_title"],
        "publisher": r1["publisher"] or r2["publisher"],
        "subject_hint": r1["subject_hint"] or r2["subject_hint"],
        "grade_hint": r1["grade_hint"] or r2["grade_hint"],
        "sections": merged,
        "volumes": (r1.get("volumes") if len(r1.get("volumes") or []) >= len(r2.get("volumes") or [])
                    else r2.get("volumes")) or [],
        "warnings": warnings,
        "read_count": 2,
    }


def read_structure(files: list[tuple[bytes, str]]) -> dict[str, Any]:
    """İçindekiler foto/PDF → yapı. ÇİFT okuma paralel; biri düşerse tek okuma.

    Raises:
        NotATocError: belge içindekiler değil (<2 bölüm)
        AIServiceUnavailable / AIInvalidResponse: sağlayıcı hataları
    """
    from concurrent.futures import ThreadPoolExecutor

    parts = _build_parts(files)
    r1: dict[str, Any] | None = None
    r2: dict[str, Any] | None = None
    single_warning: str | None = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_read_once, parts)
        f2 = pool.submit(_read_once, parts)
        try:
            r1 = f1.result()
        except (AIServiceUnavailable, AIInvalidResponse) as e:
            logger.warning("Kitap yapısı 1. okuma düştü: %s", e)
        try:
            r2 = f2.result()
        except (AIServiceUnavailable, AIInvalidResponse) as e:
            logger.warning("Kitap yapısı 2. okuma düştü: %s", e)

    if r1 is None and r2 is None:
        raise AIServiceUnavailable("Kitap yapısı okunamadı (iki deneme de başarısız).")
    if r1 is not None and r2 is not None:
        result = _merge_reads(r1, r2)
    else:
        only = r1 if r1 is not None else r2
        assert only is not None
        single_warning = (
            "Doğrulama okuması yapılamadı (tek okuma) — test sayılarını kitapla karşılaştırın."
        )
        result = {
            **only,
            "sections": [
                {"label": s["label"], "test_count": s["test_count"], "suspect": False,
                 "page": s.get("page"), "volume": s.get("volume"), "kind": s.get("kind", "topic")}
                for s in only["sections"]
            ],
            "warnings": [single_warning],
            "read_count": 1,
        }

    if len(result["sections"]) < 2:
        raise NotATocError(
            "Bu görselden bölüm listesi çıkarılamadı. Lütfen kitabın İÇİNDEKİLER "
            "sayfasını net bir şekilde çekin (kapak değil)."
        )
    for sec in result["sections"]:
        sec.setdefault("estimated", False)
    # Konu düzeyi okunduysa ünite başlık satırları test taşımaz → çıkar.
    units = [x for x in result["sections"] if x.get("kind") == "unit" and x.get("test_count") is None]
    if units and len(units) < len(result["sections"]) - len(units):
        result["sections"] = [x for x in result["sections"] if x not in units]
        result["warnings"].append(
            f"{len(units)} ünite başlığı (konular ayrıca okundu) listeden çıkarıldı."
        )
    volumes = result.get("volumes") or []
    vol_nos = {s.get("volume") for s in result["sections"] if s.get("volume")}
    if len(vol_nos) > 1:
        # Yalnız bir okumada görünen satırlar sona eklenir → fasikül içinde sayfaya göre sırala.
        first_seen: dict[Any, int] = {}
        for i, x in enumerate(result["sections"]):
            first_seen.setdefault(x.get("volume"), i)
        result["sections"] = sorted(
            result["sections"],
            key=lambda x: (first_seen[x.get("volume")], x.get("page") or 10_000),
        )
    multi = len(vol_nos) > 1
    from_questions = sum(1 for v in volumes if v.get("test_questions")) if multi else 0
    estimated = estimate_from_pages(result["sections"], volumes if multi else None)
    if estimated:
        # Sayfa numarası ve test sayısı olmayan satırlar bu düzende ünite
        # başlıklarıdır ("BASINÇ", "MADDE VE ENDÜSTRİ") — test bağlanmaz.
        headers = [
            x for x in result["sections"]
            if x.get("test_count") is None and not x.get("page")
        ]
        if headers and len(headers) < len(result["sections"]) // 2:
            result["sections"] = [x for x in result["sections"] if x not in headers]
            result["warnings"].append(
                f"{len(headers)} ünite başlığı (sayfa ve test bilgisi yok) listeden çıkarıldı: "
                + ", ".join(h["label"] for h in headers[:6])
                + ("…" if len(headers) > 6 else "")
            )
        if from_questions:
            result["warnings"].append(
                f"{estimated} bölümde test sayısı içindekilerde yazmıyor — her fasikülün "
                f"kapağındaki 'test sorusu' sayısından TAHMİN edildi (test ≈ "
                f"{QUESTIONS_PER_TEST} soru), konulara sayfa aralığı oranında dağıtıldı. "
                "'Tahmini' satırları kitapla karşılaştır."
            )
        else:
            result["warnings"].append(
                f"{estimated} bölümde test sayısı içindekilerde yazmıyor — sayfa aralığından "
                f"TAHMİN edildi (her test ≈ {PAGES_PER_TEST} sayfa). 'Tahmini' satırları kitapla "
                "karşılaştır; konu anlatımı sayfaları varsa sayı fazla çıkabilir."
            )
    for sec in result["sections"]:
        sec["label"] = tidy_label(sec["label"])
        if multi and sec.get("volume"):
            sec["label"] = f"{sec['volume']}. Fasikül · {sec['label']}"
    if multi:
        result["warnings"].append(
            f"Belgede {len(vol_nos)} fasikül var — tek kitap olarak eklenir, bölüm adlarının "
            "başında fasikül numarası yazar."
        )
    missing = sum(1 for s in result["sections"] if s["test_count"] is None)
    if missing:
        result["warnings"].append(
            f"{missing} bölümde test sayısı içindekilerde yazmıyor — elle doldurun."
        )
    return result


PAGES_PER_TEST = 2
# Kapakta "258 TEST SORUSU" gibi soru toplamı verilen fasiküllerde test başına soru.
QUESTIONS_PER_TEST = 10

_UNIT_PREFIX_RE = _re.compile(
    r"^\s*\d+\s*\.?\s*(ünite|unite|bölüm|bolum|kısım|kisim)\s*[:\-–—.]?\s*", _re.IGNORECASE
)
_SMALL_WORDS = {"ve", "ile", "ya", "da", "de", "veya", "ki", "mi"}
_ACRONYMS = {"DNA", "RNA", "ATP", "ÖSYM", "TYT", "AYT", "LGS", "YKS", "MEB", "EBOB", "EKOK", "OBEB", "OKEK", "KPSS", "YDT"}


def _tr_title(word: str) -> str:
    low = word.replace("I", "ı").replace("İ", "i").lower()
    if not low:
        return low
    first = {"i": "İ", "ı": "I"}.get(low[0], low[0].upper())
    return first + low[1:]


def tidy_label(label: str) -> str:
    """'1. ÜNİTE : MEVSİMLER VE İKLİM' → 'Mevsimler ve İklim' (koçun gördüğü bölüm adı).

    Önek yalnız ardından ad varsa atılır; büyük harf yalnız etiketin çoğu büyük
    harfse düzeltilir (karışık yazım olduğu gibi kalır)."""
    raw = label.strip()
    stripped = _UNIT_PREFIX_RE.sub("", raw).strip()
    if len(stripped) >= 3:
        raw = stripped
    letters = [c for c in raw if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.8:
        out = []
        for i, w in enumerate(raw.split(" ")):
            t = "-".join(x if x.strip(".,:;()") in _ACRONYMS else _tr_title(x) for x in w.split("-"))
            if i > 0 and t.lower() in _SMALL_WORDS:
                t = t.lower()
            out.append(t)
        raw = " ".join(out)
    return raw


def _estimate_group(sections: list[dict[str, Any]], idxs: list[int],
                    end_page: int | None, questions: int | None) -> int:
    """Tek sayfa dizisi (tek kitap ya da tek fasikül) için tahmin."""
    with_page = [i for i in idxs if sections[i].get("page")]
    pages = [sections[i]["page"] for i in with_page]
    if (len(with_page) < max(2, (len(idxs) + 1) // 2)
            or any(b < a for a, b in zip(pages, pages[1:]))):
        if not questions:
            return 0
        # Sayfa yok/bozuk ama kapakta toplam var → konulara eşit dağıt.
        with_page = [i for i in idxs if sections[i].get("test_count") is None]
        if not with_page:
            return 0
        return _distribute(sections, with_page, {i: 1 for i in with_page}, questions)
    spans: dict[int, int] = {}
    for k, i in enumerate(with_page[:-1]):
        span = sections[with_page[k + 1]]["page"] - sections[i]["page"]
        if span > 0:
            spans[i] = span
    last = with_page[-1]
    if end_page and end_page > sections[last]["page"]:
        spans[last] = end_page - sections[last]["page"]
    elif spans:
        ordered = sorted(spans.values())
        spans[last] = ordered[len(ordered) // 2]
    if not spans:
        return 0
    todo = [i for i in with_page if sections[i].get("test_count") is None and spans.get(i)]
    if not todo:
        return 0
    if questions:
        # Sayfası okunamayan konular da fasikülün testinden pay alır (ortanca aralık).
        ordered = sorted(spans.values())
        med = ordered[len(ordered) // 2]
        rest = [i for i in idxs if sections[i].get("test_count") is None and i not in todo]
        for i in rest:
            spans[i] = med
        return _distribute(sections, todo + rest, spans, questions)
    for i in todo:
        sections[i]["test_count"] = max(1, round(spans[i] / PAGES_PER_TEST))
        sections[i]["estimated"] = True
    return len(todo)


def _distribute(sections: list[dict[str, Any]], todo: list[int], spans: dict[int, int],
                questions: int) -> int:
    """Fasikül toplamı kapaktan: test ≈ soru / 10, sayfa aralığı oranında dağıt."""
    target = max(len(todo), round(questions / QUESTIONS_PER_TEST))
    total_span = sum(spans[i] for i in todo)
    raw = {i: spans[i] * target / total_span for i in todo}
    cnt = {i: max(1, int(raw[i])) for i in todo}
    order = sorted(todo, key=lambda i: -(raw[i] - int(raw[i])))
    k = 0
    while sum(cnt.values()) < target:
        cnt[order[k % len(order)]] += 1
        k += 1
    while sum(cnt.values()) > target:
        j = max((i for i in todo if cnt[i] > 1), key=lambda i: cnt[i] - raw[i])
        cnt[j] -= 1
    for i in todo:
        sections[i]["test_count"] = cnt[i]
        sections[i]["estimated"] = True
    return len(todo)


def estimate_from_pages(sections: list[dict[str, Any]],
                        volumes: list[dict[str, Any]] | None = None) -> int:
    """Test sayısı yazmayan bölümlere içindekilerdeki SAYFA ARALIĞINDAN tahmin.

    Kural: aralık = sonraki sayfa numaralı bölümün başlangıcı − bu bölümün
    başlangıcı; test ≈ aralık / PAGES_PER_TEST (en az 1). Son bölümün bitişi
    bilinmediğinden diğer aralıkların ortancası kullanılır. Yalnız sayfa
    numaraları bölümlerin en az yarısında VAR ve SIRALI (azalmayan) ise
    çalışır — aksi halde hiçbir şey uydurulmaz. Tahmin edilen satır
    `estimated=True` taşır (arayüzde "tahmini" rozeti). Döner: tahmin sayısı.
    """
    if not any(s.get("test_count") is None for s in sections):
        return 0
    if volumes is not None:
        # Çok fasikül: sayfa numaraları her fasikülde baştan başlar → fasikül fasikül.
        info = {v["volume"]: v for v in volumes}
        groups: dict[Any, list[int]] = {}
        for i, s in enumerate(sections):
            groups.setdefault(s.get("volume"), []).append(i)
        n = 0
        for vol, idxs in groups.items():
            v = info.get(vol) or {}
            n += _estimate_group(sections, idxs, v.get("end_page"), v.get("test_questions"))
        return n
    return _estimate_group(sections, list(range(len(sections))), None, None)


def identify_cover(image: bytes, media_type: str) -> dict[str, Any]:
    """Kapak fotoğrafı → kitap kimliği (ad/yayınevi/ders/sınıf). İçerik ÜRETMEZ."""
    import base64

    raw = gemini.generate(
        [
            gemini.inline_part(base64.b64encode(image).decode("ascii"), media_type),
            gemini.text_part(_COVER_PROMPT),
        ],
        personal_data=False,
        json_mode=True,
        timeout=60.0,
        prefer_fast=True,  # tanıma hafif iş — hızlı model yeter
    )
    data = gemini.extract_json(raw)
    return {
        "book_title": _clean_str(data.get("book_title")),
        "publisher": _clean_str(data.get("publisher")),
        "subject_hint": _clean_str(data.get("subject_hint"), 120),
        "grade_hint": _clean_grade(data.get("grade_hint")),
        "exam_hint": _clean_str(data.get("exam_hint"), 40),
    }


class ScanFileError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _render_pdf_page(doc: Any, index: int, dpi: int = 110) -> bytes:
    page = doc.load_page(index)
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("jpeg")


def prepare_scan_files(files: list[tuple[bytes, str]]) -> dict[str, Any]:
    """"Kapak + içindekiler" tek yüklemesini okumaya hazırlar.

    - Görseller: ilki kapak sayılır, TÜMÜ içindekiler okumasına gider.
    - PDF: ilk sayfa görsele çevrilip kapak olur; okumaya yalnız ilk
      SCAN_PDF_PAGES sayfa gider (tam kitap yüklense de). Kırpılmış PDF hâlâ
      10 MB'ı aşıyorsa (taranmış ağır sayfalar) sayfalar JPEG'e çevrilir.

    Döner: {"cover": (bytes, mt) | None, "toc": [(bytes, mt)], "notes": [str],
            "page_count": int | None}
    """
    notes: list[str] = []
    if not files:
        raise ScanFileError("no_files", "En az bir fotoğraf veya PDF yükleyin.")
    pdfs = [f for f in files if f[1] == PDF_MIME]
    if pdfs:
        if len(files) > 1:
            raise ScanFileError("mixed_files", "PDF tek başına yüklenmeli (fotoğrafla karıştırmayın).")
        raw = pdfs[0][0]
        try:
            try:
                import pymupdf as fitz  # PyMuPDF (yeni ad)
            except ImportError:
                import fitz  # PyMuPDF eski ad
        except ImportError:  # pragma: no cover — kurulum eksik
            if len(raw) > MAX_PDF_BYTES:
                raise ScanFileError("file_too_large", "PDF en fazla 10 MB olabilir.")
            return {"cover": None, "toc": [(raw, PDF_MIME)], "notes": notes, "page_count": None}
        try:
            doc = fitz.open(stream=raw, filetype="pdf")
        except Exception:
            raise ScanFileError("pdf_unreadable", "PDF açılamadı — dosya bozuk ya da şifreli olabilir.")
        with doc:
            total = doc.page_count
            if total == 0:
                raise ScanFileError("pdf_unreadable", "PDF'te sayfa yok.")
            cover = (_render_pdf_page(doc, 0), "image/jpeg")
            n = min(total, SCAN_PDF_PAGES)
            if total > n:
                notes.append(
                    f"PDF {total} sayfa — yalnız ilk {n} sayfası (kapak + içindekiler) okundu."
                )
            sub = fitz.open()
            with sub:
                sub.insert_pdf(doc, from_page=0, to_page=n - 1)
                trimmed = sub.tobytes(garbage=3, deflate=True)
            if len(trimmed) <= MAX_PDF_BYTES:
                toc = [(trimmed, PDF_MIME)]
            else:
                toc = [(_render_pdf_page(doc, i, dpi=130), "image/jpeg") for i in range(n)]
        return {"cover": cover, "toc": toc, "notes": notes, "page_count": total}
    if len(files) > MAX_SCAN_IMAGES:
        raise ScanFileError("too_many_files", f"En fazla {MAX_SCAN_IMAGES} fotoğraf yüklenebilir.")
    for raw, mt in files:
        if mt not in ALLOWED_IMAGE_TYPES:
            raise ScanFileError("invalid_media_type", "Yalnız JPEG/PNG/WebP fotoğraf veya PDF yükleyin.")
        if len(raw) > MAX_IMAGE_BYTES:
            raise ScanFileError("file_too_large", "Her fotoğraf en fazla 8 MB olabilir.")
    return {"cover": files[0], "toc": list(files), "notes": notes, "page_count": None}


# =============================================================================
# Ölçüm + günlük tavan (kredi DÜŞMEZ — 0 kredilik UsageEvent)
# =============================================================================


def book_read_count_today(db: Session, user_id: int) -> int:
    """Bugünkü (UTC günü) okuma sayısı — günlük tavan kontrolü.

    UTC gün başı kullanılır (P4 dersi: yerel gün UTC'ye çevrilince gece
    penceresinde limit deliniyordu).
    """
    from app.models import UsageEvent, UsageKind

    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        db.query(func.count(UsageEvent.id))
        .filter(
            UsageEvent.kind == UsageKind.AI_BOOK_READ,
            UsageEvent.actor_user_id == user_id,
            UsageEvent.occurred_at >= day_start,
        )
        .scalar()
        or 0
    )


def record_book_read(
    db: Session, user, *, mode: str, section_count: int, autocommit: bool = False,
) -> None:
    """0 kredilik ölçüm kaydı. `record_usage` KULLANILMAZ (kredileri 1'e
    clamp'ler + hesaptan düşer); UsageEvent doğrudan yazılır — koç havuzuna
    dokunulmaz, admin kullanım panosunda satır olarak görünür.
    """
    import json as _json

    from app.models import UsageEvent
    from app.models import UsageKind
    from app.services.credits import CreditOwner, current_period

    owner = CreditOwner.for_user(user)
    db.add(UsageEvent(
        owner_type=owner.type,
        owner_id=owner.id,
        kind=UsageKind.AI_BOOK_READ,
        credits=0,
        period_year_month=current_period(datetime.now(timezone.utc)),
        actor_user_id=user.id,
        metadata_json=_json.dumps(
            {"mode": mode, "section_count": section_count}, ensure_ascii=False,
        ),
    ))
    if autocommit:
        db.commit()
