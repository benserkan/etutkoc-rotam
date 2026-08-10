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

# Koç başına günlük okuma tavanı (kredi yok — yalnız kötüye kullanım rayı).
AI_BOOK_READ_DAILY_LIMIT = 30

# İçindekiler tipik 1-3 sayfa; 2.5'in düşünme tokenı payıyla geniş bütçe
# (yarım JSON = parse hatası dersi).
_MAX_OUTPUT_TOKENS = 16384
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
- ÇALIŞMA BÖLÜMÜ OLMAYAN satırları listeye ALMA: önsöz/sunuş, içindekiler,
  cevap anahtarı, çözümler, kavramlar sözlüğü, dizin, yazar hakkında vb.
- Alt başlıklar değil ÜNİTE/BÖLÜM düzeyini çıkar: testlerin bağlandığı düzey esas alınır.
- Birden çok görsel/sayfa verdiysem hepsi AYNI kitabın devamıdır — tek liste halinde sırayla birleştir, tekrar eden başlıkları bir kez yaz.
- Kitap adı/yayınevi belgede görünüyorsa yaz; görünmüyorsa null.
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
    {"label": "bölüm/ünite adı", "test_count": int | null}
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


def _clean_grade(v: Any) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 4 <= n <= 12 else None


def _normalize_read(data: dict[str, Any]) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for item in data.get("sections") or []:
        if not isinstance(item, dict):
            continue
        label = _clean_str(item.get("label"))
        if not label:
            continue
        sections.append({"label": label, "test_count": _clean_count(item.get("test_count"))})
    return {
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
        merged.append({"label": label, "test_count": count, "suspect": suspect})

    # Yalnız ikinci okumada görünen bölümler (birincinin kaçırdıkları)
    extra = [sec for sec in s2 if id(sec) not in used2]
    for sec in extra:
        merged.append({"label": sec["label"], "test_count": sec["test_count"], "suspect": True})

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
                {"label": s["label"], "test_count": s["test_count"], "suspect": False}
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
    missing = sum(1 for s in result["sections"] if s["test_count"] is None)
    if missing:
        result["warnings"].append(
            f"{missing} bölümde test sayısı içindekilerde yazmıyor — elle doldurun."
        )
    return result


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
