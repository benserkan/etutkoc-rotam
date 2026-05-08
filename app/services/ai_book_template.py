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
import os
import re
from typing import Any

import httpx


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
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise AIServiceUnavailable("ANTHROPIC_API_KEY tanımlı değil (.env)")

    prompt = _build_prompt(
        book_name=book_name,
        publisher=publisher,
        subject_name=subject_name,
        book_type_label=book_type_label,
        grade_label=grade_label,
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
    except httpx.HTTPError as e:
        logger.warning("Anthropic API çağrısı başarısız: %s", e)
        raise AIServiceUnavailable(f"API çağrısı başarısız: {e}")

    if response.status_code != 200:
        body_preview = response.text[:200] if response.text else ""
        logger.warning(
            "Anthropic API HTTP %s: %s", response.status_code, body_preview
        )
        raise AIServiceUnavailable(f"HTTP {response.status_code}")

    data = response.json()
    content = data.get("content", [])
    if not content or not isinstance(content, list):
        raise AIInvalidResponse("İçerik blokları boş")
    text_blocks = [b.get("text", "") for b in content if b.get("type") == "text"]
    full_text = "\n".join(text_blocks).strip()
    if not full_text:
        raise AIInvalidResponse("Metin yanıtı boş")

    sections = _extract_json_array(full_text)
    if not sections:
        raise AIInvalidResponse("Hiç ünite çıkarılamadı")
    return sections
