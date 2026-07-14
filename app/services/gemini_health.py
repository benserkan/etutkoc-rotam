"""Gemini anahtar sağlık testi — süper admin "Bağlantıyı test et".

2026-07-14 olayı: canlıda tüm AI özellikleri sessizce 502 vermeye başladı.
Kök neden Google tarafındaydı (faturalandırma askıya alınmış → proje 403
"denied access" + ücretsiz katmana düşüp 429). Panelden anlamanın yolu yoktu;
ancak bir özelliği deneyip hata alınca fark ediliyordu.

Bu servis her anahtarı GERÇEK ama minik bir çağrıyla dener ve Google'ın ham
yanıtını SADE TÜRKÇE teşhise çevirir. Süper admin, anahtarı düzelttikten sonra
tek tıkla doğrular.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Durum kodları (frontend ton eşlemesi için)
OK = "ok"                       # çalışıyor
QUOTA = "quota"                 # kota doldu (429)
DENIED = "denied"               # proje erişime kapalı / faturalandırma (403)
INVALID_KEY = "invalid_key"     # anahtar geçersiz (400/401)
NOT_SET = "not_set"             # anahtar tanımlı değil
NETWORK = "network"             # ağ/zaman aşımı
UNKNOWN = "unknown"


@dataclass
class KeyProbe:
    slot: str                   # "paid" | "free"
    label: str                  # "Ücretli anahtar" ...
    model: str
    is_set: bool
    status: str                 # OK/QUOTA/DENIED/...
    summary: str                # sade Türkçe teşhis
    action: str                 # ne yapmalı
    http_status: int | None = None
    raw_message: str = ""       # Google'ın ham mesajı (geliştirici detayı)


@dataclass
class GeminiHealth:
    overall: str                        # ok | degraded | down
    headline: str
    probes: list[KeyProbe] = field(default_factory=list)


def _diagnose(status_code: int, message: str) -> tuple[str, str, str]:
    """(status, sade özet, ne yapmalı)."""
    msg = (message or "").lower()
    if status_code == 200:
        return OK, "Çalışıyor — Google yanıt verdi.", ""
    if status_code == 429:
        if "free_tier" in msg or "free tier" in msg:
            return (
                QUOTA,
                "Ücretsiz katman kotası doldu. Bu anahtarın Google projesinde "
                "faturalandırma AKTİF DEĞİL — ücretli kullanım açılmamış.",
                "Google Cloud Console → Faturalandırma: projeye faturalandırma "
                "hesabı bağla ve bekleyen ödeme varsa öde. Ardından burayı yeniden test et.",
            )
        return (
            QUOTA,
            "Kota doldu (istek/dakika veya günlük sınır).",
            "Birkaç dakika bekleyip tekrar dene; sürekli oluyorsa Google Cloud "
            "Console → API'ler → Kotalar bölümünden sınırı yükselt.",
        )
    if status_code == 403:
        if "denied access" in msg or "permission_denied" in msg:
            return (
                DENIED,
                "Google bu projeye ERİŞİMİ KAPATMIŞ. Genellikle başarısız ödeme "
                "sonrası faturalandırma hesabının askıya alınmasından olur "
                "(kart limiti yetmemiş / kart reddedilmiş).",
                "Google Cloud Console → Faturalandırma: hesabın durumunu kontrol et, "
                "bekleyen tutarı ELLE öde ve kartı doğrula. Askı kalkmazsa yeni bir "
                "proje + faturalandırma + yeni API anahtarı en hızlı yol.",
            )
        return (
            DENIED,
            "Erişim reddedildi (403).",
            "Google Cloud Console'da 'Generative Language API' bu projede "
            "etkinleştirilmiş mi ve anahtarın kısıtlamaları uygun mu kontrol et.",
        )
    if status_code in (400, 401):
        return (
            INVALID_KEY,
            "Anahtar geçersiz veya biçimi bozuk.",
            "Google AI Studio'dan yeni bir API anahtarı üretip buraya yapıştır.",
        )
    return (
        UNKNOWN,
        f"Beklenmeyen yanıt (HTTP {status_code}).",
        "Google'ın ham mesajını geliştirici detayında görebilirsin.",
    )


def _probe(slot: str, label: str, key: str | None, model: str) -> KeyProbe:
    if not key:
        return KeyProbe(
            slot=slot, label=label, model=model, is_set=False, status=NOT_SET,
            summary="Anahtar tanımlı değil.",
            action="Google AI Studio'dan anahtar üretip bu sayfadan gir.",
        )
    try:
        r = httpx.post(
            f"{GEMINI_BASE}/{model}:generateContent",
            params={"key": key},
            json={"contents": [{"parts": [{"text": "ping"}]}],
                  "generationConfig": {"maxOutputTokens": 8}},
            timeout=20.0,
        )
    except httpx.HTTPError as e:
        return KeyProbe(
            slot=slot, label=label, model=model, is_set=True, status=NETWORK,
            summary="Google'a ulaşılamadı (ağ/zaman aşımı).",
            action="Sunucunun internet erişimini kontrol et; birazdan tekrar dene.",
            raw_message=str(e)[:300],
        )
    raw = ""
    try:
        err = (r.json() or {}).get("error") or {}
        raw = str(err.get("message") or "")[:400]
    except Exception:  # noqa: BLE001
        raw = r.text[:200]
    status, summary, action = _diagnose(r.status_code, raw)
    return KeyProbe(
        slot=slot, label=label, model=model, is_set=True, status=status,
        summary=summary, action=action, http_status=r.status_code, raw_message=raw,
    )


def check_gemini_health() -> GeminiHealth:
    """Ücretli + ücretsiz anahtarları gerçek (minik) çağrıyla dener.

    Ücretli anahtar KVKK açısından kritik: öğrenci verili tüm AI işleri (seans
    yakalama, koçluk içgörüsü, kariyer sentezi, yanlış soru etiketleme) YALNIZ
    onu kullanır — ücretsiz anahtara DÜŞÜLMEZ. Bu yüzden ücretli anahtar
    çalışmıyorsa "down" sayılır.
    """
    from app.services.system_secrets import (
        get_gemini_free_keys, get_gemini_model, get_gemini_paid_key,
    )

    paid_key = get_gemini_paid_key()
    free_keys = get_gemini_free_keys()
    paid_model = get_gemini_model(paid=True)
    free_model = get_gemini_model(paid=False)

    probes = [_probe("paid", "Ücretli anahtar (öğrenci verili işler)",
                     paid_key, paid_model)]
    # Ücretli anahtar pro'da tıkanırsa kod AYNI anahtarla flash'a düşer →
    # onu da ölç (gerçek dayanıklılık burada).
    if paid_key and free_model and free_model != paid_model:
        probes.append(_probe("paid_fallback",
                             f"Ücretli anahtar — yedek model ({free_model})",
                             paid_key, free_model))
    for i, k in enumerate(free_keys):
        probes.append(_probe(
            "free",
            f"Ücretsiz anahtar {i + 1} (kişisel veri İÇERMEYEN işler)",
            k, free_model,
        ))

    paid_ok = any(p.slot.startswith("paid") and p.status == OK for p in probes)
    free_ok = any(p.slot == "free" and p.status == OK for p in probes)

    if paid_ok:
        overall = OK if (free_ok or not free_keys) else "degraded"
        headline = (
            "Yapay zekâ çalışıyor."
            if overall == OK
            else "Öğrenci verili AI çalışıyor; ücretsiz anahtar sorunlu "
                 "(yalnız kitap şablonu gibi işleri etkiler)."
        )
    else:
        overall = "down"
        headline = (
            "Öğrenci verili yapay zekâ ÇALIŞMIYOR — seans içgörüsü, foto/ses "
            "yakalama, kariyer sentezi ve yanlış soru etiketleme şu an devre dışı."
        )
    return GeminiHealth(overall=overall, headline=headline, probes=probes)
