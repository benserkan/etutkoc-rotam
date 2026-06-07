"""Gemini (Google Generative Language API) — tek AI sağlayıcı.

Tüm AI işleri buradan geçer:
- Öğrenci verili (foto/ses/içgörü) → `generate(..., personal_data=True)` → ÜCRETLİ
  key + ücretli model (no-training, KVKK). Fallback YOK (free'ye düşmez).
- Kişisel-veri-içermeyen (kitap şablonu) → `personal_data=False` → ücretsiz key(ler)
  sırayla; kota (429) dolunca sıradakine, hepsi biterse ücretliye düşer.

httpx ile doğrudan REST (ekstra SDK yok). `responseMimeType=application/json` ile
yapılandırılmış çıktı. AIInvalidResponse/AIServiceUnavailable `ai_book_template`'ten
reuse (endpoint hata eşlemeleri korunur).
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class _QuotaExceeded(Exception):
    """429 — bu anahtarın kotası doldu (bir sonrakine/ücretliye düş)."""


def text_part(s: str) -> dict[str, Any]:
    return {"text": s}


def inline_part(data_base64: str, mime_type: str) -> dict[str, Any]:
    return {"inline_data": {"mime_type": mime_type, "data": data_base64}}


# 503 (model aşırı yük) geçici — kısa backoff ile yeniden dene.
_RETRY_503 = (1.5, 3.0)


def _call(model: str, api_key: str, parts: list[dict], *, timeout: float, json_mode: bool,
          max_output_tokens: int = 8192) -> str:
    url = f"{GEMINI_BASE}/{model}:generateContent"
    # 2.5 modelleri "düşünme" tokenı tüketir; düşük bütçe çıktıyı yarıda keser
    # (yarım JSON → parse hatası). Büyük yapılandırılmış çıktılarda (örn. vitrin
    # temalı gruplama, çok aday) max_output_tokens yükseltilir.
    gen_cfg: dict[str, Any] = {"temperature": 0.4, "maxOutputTokens": max_output_tokens}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": gen_cfg}

    resp = None
    for attempt in range(len(_RETRY_503) + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    url,
                    headers={"x-goog-api-key": api_key, "content-type": "application/json"},
                    json=body,
                )
        except httpx.HTTPError as e:
            logger.warning("Gemini çağrısı başarısız: %s", e)
            raise AIServiceUnavailable(f"Gemini çağrısı başarısız: {e}")

        if resp.status_code == 503 and attempt < len(_RETRY_503):
            logger.info("Gemini 503 (yoğunluk) — %s sn sonra yeniden", _RETRY_503[attempt])
            time.sleep(_RETRY_503[attempt])
            continue
        break

    if resp.status_code == 429:
        raise _QuotaExceeded()
    if resp.status_code != 200:
        snippet = (resp.text or "")[:200]
        logger.warning("Gemini HTTP %s: %s", resp.status_code, snippet)
        raise AIServiceUnavailable(f"Gemini HTTP {resp.status_code}")

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        # Güvenlik filtresi vb. → boş
        raise AIInvalidResponse("Gemini yanıtı boş (içerik üretilmedi)")
    parts_out = (candidates[0].get("content") or {}).get("parts") or []
    text = "\n".join(p.get("text", "") for p in parts_out if "text" in p).strip()
    if not text:
        raise AIInvalidResponse("Gemini metin yanıtı boş")
    return text


def generate(
    parts: list[dict], *, personal_data: bool, timeout: float = 45.0, json_mode: bool = True,
    max_output_tokens: int = 8192, prefer_paid: bool = True,
) -> str:
    """Gemini'den metin yanıt al — TÜM AI işlerinde önce **pro** (en zeki model).

    Politika (kullanıcı kararı): pro birinci tercih, sistem ASLA tıkanmaz/sonuçsuz
    kalmaz. Pro erişilemez/kotasızsa (örn. proje paid tier değilse 429-FreeTier)
    **AYNI ücretli anahtarla flash'a** düşülür (anahtar/tier değişmez → KVKK nötr).
    Google'da proje paid tier'a alınınca pro otomatik her yerde devreye girer
    (kod pro'yu hep önce dener).

    personal_data=True → yalnız ÜCRETLİ (faturalı/no-training) anahtar; pro→flash.
      KVKK: ücretsiz KEY'e DÜŞÜLMEZ.
    personal_data=False → önce ücretli anahtar (pro→flash); o da olmazsa ek
      dayanıklılık için ücretsiz key(ler) + flash.

    prefer_paid: geriye uyum için tutuldu (pro artık her zaman önce denenir).
    """
    from app.services.system_secrets import (
        get_gemini_free_keys, get_gemini_model, get_gemini_paid_key,
    )
    paid = get_gemini_paid_key()
    pro = get_gemini_model(paid=True)
    flash = get_gemini_model(paid=False)
    paid_models = [pro] + ([flash] if flash and flash != pro else [])

    # 1) ÜCRETLİ (faturalı) anahtar: önce pro (en zeki), erişilemez/kotasızsa
    #    AYNI anahtarla flash. AIInvalidResponse (içerik/filtre) → yükselir (gerçek
    #    sonuç hatası; model/anahtar değiştirmek çözmez).
    if paid:
        for m in paid_models:
            try:
                return _call(m, paid, parts, timeout=timeout, json_mode=json_mode,
                             max_output_tokens=max_output_tokens)
            except _QuotaExceeded:
                logger.info("Gemini ücretli anahtar + %s kotasız (paid tier mi?) → sıradaki model", m)
            except AIServiceUnavailable:
                logger.info("Gemini ücretli anahtar + %s erişilemez → sıradaki model", m)

    # KVKK: kişisel veride ücretsiz KEY'e DÜŞMEYİZ (no-training zorunlu).
    if personal_data:
        if not paid:
            raise AIServiceUnavailable(
                "Gemini ücretli anahtarı tanımlı değil (süper admin → AI Ayarları)")
        raise AIServiceUnavailable(
            "Yapay zekâ şu an kullanılamıyor: ücretli Gemini anahtarı pro+flash "
            "üretemedi. gemini-2.5-pro için Google projesi paid tier (billing aktif) olmalı.")

    # 2) Kişisel-veri DEĞİL → ek dayanıklılık: ücretsiz key(ler) + flash.
    free_keys = get_gemini_free_keys()
    if not paid and not free_keys:
        raise AIServiceUnavailable("Gemini anahtarı tanımlı değil (süper admin → AI Ayarları)")
    for k in free_keys:
        try:
            return _call(flash, k, parts, timeout=timeout, json_mode=json_mode,
                         max_output_tokens=max_output_tokens)
        except _QuotaExceeded:
            logger.info("Gemini ücretsiz anahtar + flash kotasız → sıradaki anahtar")
            continue
    raise AIServiceUnavailable("Gemini tüm anahtarların kotası doldu (süper admin → AI Ayarları).")


def extract_json(text: str) -> dict[str, Any]:
    """Gemini JSON çıktısını parse et (json_mode olsa da defansif temizlik)."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            pass
    raise AIInvalidResponse("Gemini çıktısı JSON nesnesi değil")
