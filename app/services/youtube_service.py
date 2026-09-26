"""YouTube Data API v3 — Video Sepeti için oynatma listesi / video bilgisi.

Yalnız OKUMA: oynatma listesinin videoları (başlık, kanal, sıra) + süreler.
Anahtar: süper admin panelinden (system_secrets "youtube_api_key") ya da env.
Kişisel veri GÖNDERİLMEZ (yalnız video/oynatma listesi kimliği).

Ağ çağrıları `_get` üzerinden yapılır → testlerde tek noktadan taklit edilir.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from app.services.system_secrets import get_youtube_api_key

logger = logging.getLogger(__name__)

API_BASE = "https://www.googleapis.com/youtube/v3"
MAX_PLAYLIST_VIDEOS = 300  # tek içe aktarmada üst sınır (kota + sepet düzeni)
_TIMEOUT = 20.0

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,64}$")


class YouTubeError(Exception):
    """code: not_configured | bad_url | not_found | quota | unavailable"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class YtVideo:
    youtube_id: str
    title: str
    channel_title: str | None
    duration_sec: int | None
    position: int


@dataclass
class YtImport:
    kind: str  # "playlist" | "video"
    playlist_id: str | None
    playlist_title: str | None
    channel_title: str | None
    videos: list[YtVideo]
    truncated: bool = False


# ---------------------------- URL çözümleme ----------------------------


def parse_youtube_url(raw: str) -> tuple[str, str, str | None]:
    """→ (kind, id, video_id?) — kind "playlist" | "video".

    Liste içindeki bir videonun linki (watch?v=..&list=..) → oynatma listesi
    (koç genelde listeden tek videoyu kopyalar ama tüm listeyi ister).
    Çıplak kimlik de kabul edilir (11 karakter → video, PL/UU/OL.. → liste).
    """
    s = (raw or "").strip()
    if not s:
        raise YouTubeError("bad_url", "Bağlantı boş.")
    if "://" not in s and "/" not in s and "." not in s:
        if _VIDEO_ID_RE.match(s):
            return "video", s, None
        if _PLAYLIST_ID_RE.match(s):
            return "playlist", s, None
        raise YouTubeError("bad_url", "YouTube bağlantısı ya da kimliği tanınmadı.")
    if "://" not in s:
        s = "https://" + s
    u = urlparse(s)
    host = (u.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]
    q = parse_qs(u.query)
    lst = (q.get("list") or [None])[0]
    vid: str | None = None
    if host == "youtu.be":
        vid = u.path.strip("/").split("/")[0] or None
    elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        path = u.path.rstrip("/")
        if path == "/watch":
            vid = (q.get("v") or [None])[0]
        else:
            m = re.match(r"^/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})", path)
            if m:
                vid = m.group(1)
    else:
        raise YouTubeError("bad_url", "Yalnız YouTube bağlantıları desteklenir.")
    if lst and _PLAYLIST_ID_RE.match(lst) and not lst.startswith("RD"):
        # RD… = otomatik "mix" listesi, API ile okunamaz → tek video say
        return "playlist", lst, vid if (vid and _VIDEO_ID_RE.match(vid)) else None
    if vid and _VIDEO_ID_RE.match(vid):
        return "video", vid, None
    raise YouTubeError("bad_url", "Bağlantıda video ya da oynatma listesi bulunamadı.")


_ISO_DUR_RE = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def parse_iso_duration(v: str | None) -> int | None:
    """ISO 8601 süre (PT1H2M3S) → saniye. Canlı yayın 'P0D' → None."""
    if not v:
        return None
    m = _ISO_DUR_RE.match(v)
    if not m:
        return None
    d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    total = d * 86400 + h * 3600 + mi * 60 + se
    return total or None


# ---------------------------- Ağ ----------------------------


def is_configured() -> bool:
    return bool(get_youtube_api_key())


def _get(path: str, params: dict) -> dict:
    """Tek HTTP noktası (testlerde monkeypatch)."""
    key = get_youtube_api_key()
    if not key:
        raise YouTubeError(
            "not_configured",
            "Video Sepeti şu an kullanılamıyor: YouTube bağlantısı henüz kurulmamış. "
            "Platform yöneticisi bağlantıyı tamamlayınca liste getirebilirsiniz.",
        )
    try:
        r = httpx.get(f"{API_BASE}/{path}", params={**params, "key": key}, timeout=_TIMEOUT)
    except httpx.HTTPError as e:
        logger.warning("YouTube isteği başarısız: %s", e)
        raise YouTubeError("unavailable", "YouTube'a ulaşılamadı, biraz sonra tekrar deneyin.") from e
    if r.status_code == 404:
        raise YouTubeError("not_found", "Video ya da oynatma listesi bulunamadı (gizli olabilir).")
    if r.status_code == 403:
        reason = ""
        try:
            reason = r.json()["error"]["errors"][0].get("reason", "")
        except Exception:  # noqa: BLE001
            pass
        if "quota" in reason.lower():
            raise YouTubeError("quota", "Günlük YouTube kotası doldu; yarın tekrar deneyin.")
        logger.warning("YouTube 403: %s", r.text[:300])
        raise YouTubeError(
            "not_configured",
            "Video Sepeti şu an YouTube'a bağlanamıyor. Platform yöneticisi bağlantıyı "
            "kontrol ediyor; biraz sonra tekrar deneyin.",
        )
    if r.status_code >= 400:
        logger.warning("YouTube %s: %s", r.status_code, r.text[:300])
        raise YouTubeError("unavailable", "YouTube isteği reddedildi.")
    return r.json()


def _video_details(ids: list[str]) -> dict[str, dict]:
    """videos.list — 50'şer parti; id → {title, channel, duration_sec, privacy}."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        data = _get("videos", {"part": "snippet,contentDetails,status", "id": ",".join(chunk),
                               "maxResults": 50})
        for it in data.get("items", []):
            sn = it.get("snippet", {}) or {}
            out[it["id"]] = {
                "title": sn.get("title") or "",
                "channel": sn.get("channelTitle"),
                "duration_sec": parse_iso_duration((it.get("contentDetails") or {}).get("duration")),
            }
    return out


def fetch(url: str) -> YtImport:
    kind, ident, _ = parse_youtube_url(url)
    if kind == "video":
        det = _video_details([ident])
        if ident not in det:
            raise YouTubeError("not_found", "Video bulunamadı ya da gizli.")
        d = det[ident]
        return YtImport(kind="video", playlist_id=None, playlist_title=None,
                        channel_title=d["channel"],
                        videos=[YtVideo(ident, d["title"], d["channel"], d["duration_sec"], 0)])

    meta = _get("playlists", {"part": "snippet", "id": ident, "maxResults": 1})
    items = meta.get("items") or []
    if not items:
        raise YouTubeError("not_found", "Oynatma listesi bulunamadı ya da gizli.")
    psn = items[0].get("snippet", {}) or {}
    ids: list[str] = []
    token: str | None = None
    truncated = False
    while True:
        params = {"part": "contentDetails", "playlistId": ident, "maxResults": 50}
        if token:
            params["pageToken"] = token
        data = _get("playlistItems", params)
        for it in data.get("items", []):
            vid = (it.get("contentDetails") or {}).get("videoId")
            if vid and vid not in ids:
                ids.append(vid)
        token = data.get("nextPageToken")
        if not token:
            break
        if len(ids) >= MAX_PLAYLIST_VIDEOS:
            truncated = True
            break
    ids = ids[:MAX_PLAYLIST_VIDEOS]
    det = _video_details(ids)
    videos: list[YtVideo] = []
    for vid in ids:
        d = det.get(vid)
        if not d:  # silinmiş / gizli video listede kalmış
            continue
        videos.append(YtVideo(vid, d["title"], d["channel"], d["duration_sec"], len(videos)))
    return YtImport(kind="playlist", playlist_id=ident, playlist_title=psn.get("title"),
                    channel_title=psn.get("channelTitle"), videos=videos, truncated=truncated)
