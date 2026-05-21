"""AI-asistanlı kitap şablonu üretimi.

Anthropic API (Haiku) çağrısıyla bir kitabın tipik ünite yapısını öneren
modül. SDK kullanmadan httpx ile direkt API'ye gidiyor (zaten requirements'ta
var, ekstra bağımlılık yok).

Çıktı: [{"label": str, "default_test_count": int}, ...]

Maliyet: Haiku ile penny seviyesi (~1500 tokens / call). Hata olursa boş liste
döner ve UI fallback olarak manuel girişe yönlendirir.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any


logger = logging.getLogger(__name__)


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_VERSION = "2023-06-01"


class AIServiceUnavailable(Exception):
    """API key yok veya servis ulaşılamaz."""


class AIInvalidResponse(Exception):
    """Model JSON parse hatası ya da boş yanıt."""


def _build_prompt(
    *,
    book_name: str,
    publisher: str | None,
    subject_name: str,
    book_type_label: str,
    grade_label: str,
) -> str:
    return (
        "Sen Türkiye eğitim sistemi uzmanı bir asistansın. Aşağıdaki kitap için "
        "tipik ünite/bölüm yapısını JSON olarak öner.\n\n"
        f"Kitap adı: {book_name}\n"
        f"Yayın evi: {publisher or 'belirtilmemiş'}\n"
        f"Sınıf seviyesi: {grade_label}\n"
        f"Ders: {subject_name}\n"
        f"Kitap tipi: {book_type_label}\n\n"
        "Kurallar:\n"
        "1) Sadece JSON array döndür, başka açıklama YAZMA.\n"
        "2) Format: [{\"label\": \"1. Ünite — Sayılar\", \"default_test_count\": 12}, ...]\n"
        "3) Bilmediğin kitap için MEB müfredatına en yakın tipik yapıyı öner.\n"
        "4) Test sayısı tahminleri:\n"
        "   - Soru bankası: 10-20 / ünite\n"
        "   - Fasikül: 6-12 / ünite\n"
        "   - Konu anlatımlı: 5-10 / ünite\n"
        "   - Branş denemesi: tek bir 'Denemeler' kalemi, 8-15 deneme\n"
        "   - Genel deneme: tek bir 'Denemeler' kalemi, 10-20 deneme\n"
        "5) Ünite isimleri Türkçe ve kısa olsun (max 60 karakter).\n"
        "6) Maximum 30 ünite öner.\n\n"
        "Çıktı (sadece JSON array):"
    )


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Model çıktısından JSON array'i çıkarır.

    Bazen model markdown code fence ile sarar veya açıklama ekler;
    JSON array'i tespit edip parse ediyoruz.
    """
    text = text.strip()
    # Markdown code fence
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
        if m:
            text = m.group(1)
    # Direkt JSON array
    if not text.startswith("["):
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            text = m.group(0)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise AIInvalidResponse(f"JSON parse hatası: {e}")
    if not isinstance(parsed, list):
        raise AIInvalidResponse("Yanıt array değil")
    out: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        try:
            count = int(item.get("default_test_count", 10))
            if count < 1:
                count = 1
            elif count > 100:
                count = 100
        except (TypeError, ValueError):
            count = 10
        out.append({"label": label[:200], "default_test_count": count})
    return out


def suggest_sections(
    *,
    book_name: str,
    publisher: str | None,
    subject_name: str,
    book_type_label: str,
    grade_label: str,
    timeout: float = 30.0,
) -> list[dict[str, Any]]:
    """AI'dan ünite önerisi al.

    Raises:
        AIServiceUnavailable: API key yok veya HTTP hatası
        AIInvalidResponse: Model çıktısı parse edilemedi

    Kişisel veri içermez (yalnız kitap adı/yayınevi) → Gemini ÜCRETSİZ key sırayla,
    kota dolunca ücretliye düşer (personal_data=False).
    """
    from app.services import gemini

    prompt = _build_prompt(
        book_name=book_name,
        publisher=publisher,
        subject_name=subject_name,
        book_type_label=book_type_label,
        grade_label=grade_label,
    )
    full_text = gemini.generate(
        [gemini.text_part(prompt)], personal_data=False, timeout=timeout, json_mode=True,
    )
    sections = _extract_json_array(full_text)
    if not sections:
        raise AIInvalidResponse("Hiç ünite çıkarılamadı")
    return sections
