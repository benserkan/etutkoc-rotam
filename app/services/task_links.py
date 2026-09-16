"""Görev bağlantısı (video linki) — TEK MERKEZ (2026-09-16).

`Task.link_url` kolonu modelde vardı ama API v2 hiç doldurmuyor/serialize
etmiyordu; web formu video URL'ini `notes`'un son satırına gömüyordu. Sonuç:
mobilde/web öğrencide "videoyu izle" diye tıklanacak bir şey YOKTU, koç
listesinde de video görevi "etkinlik" diye görünüyordu.

Kurallar:
  · Etkin link = `task.link_url` (varsa) YOKSA notes içindeki ilk http(s) URL.
    Eski kayıtlar (URL yalnız notes'ta) böylece kod değişmeden link kazanır.
  · Yalnız http/https kabul edilir — `javascript:`/`file:` şemaları hiçbir
    yüzeyde tıklanabilir link olmaz (koç metni öğrenci cihazında açılır).
  · Gösterim: UI notes'u basarken URL satırını ayıklar (`strip_urls`) ki link
    hem buton hem düz metin olarak iki kez görünmesin.
"""
from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
# "şema:" — iki nokta "/"tan önce gelir ve ardından rakam (port) gelmez.
_SCHEME_RE = re.compile(r"^([a-z][a-z0-9+.\-]*):(?!\d)", re.IGNORECASE)
_MAX_LEN = 500  # Task.link_url String(500)


def extract_url(text: str | None) -> str | None:
    """Metindeki ilk http(s) bağlantısı; yoksa None."""
    if not text:
        return None
    m = _URL_RE.search(text)
    if not m:
        return None
    url = m.group(0).rstrip(".,;)")
    return url[:_MAX_LEN] if url else None


def normalize_link(value: str | None) -> str | None:
    """Koçun girdiği bağlantıyı doğrula/temizle.

    Boş → None. `www.`/çıplak alan adı → https:// öneki. http(s) dışı şema →
    ValueError (çağıran 422'ye çevirir)."""
    raw = (value or "").strip()
    if not raw:
        return None
    # Şema var mı? ("javascript:alert(1)" → şema=javascript → RED;
    # "example.com:8080/x" → iki noktadan sonra sayı = port, şema DEĞİL)
    m = _SCHEME_RE.match(raw)
    if m:
        if m.group(1).lower() not in ("http", "https"):
            raise ValueError("unsupported_scheme")
    else:
        raw = "https://" + raw
    if any(ch.isspace() for ch in raw):
        raise ValueError("invalid_url")
    return raw[:_MAX_LEN]


def effective_link_url(task) -> str | None:
    """Serializer'ların kullandığı tek kaynak: kolon > notes içindeki URL."""
    explicit = (getattr(task, "link_url", None) or "").strip()
    if explicit:
        return explicit
    return extract_url(getattr(task, "notes", None))


def strip_urls(text: str | None) -> str | None:
    """Notlardan URL'leri ayıkla (gösterim için). Geriye anlamlı metin
    kalmazsa None."""
    if not text:
        return None
    cleaned = _URL_RE.sub("", text)
    lines = [ln.strip() for ln in cleaned.splitlines()]
    out = "\n".join(ln for ln in lines if ln)
    return out or None


def is_video_like(task) -> bool:
    """Öğrenci yüzeylerinde "Video dersi" etiketi + izle düğmesi kararı."""
    ttype = getattr(task, "type", None)
    tval = getattr(ttype, "value", ttype)
    return tval == "video" or effective_link_url(task) is not None
