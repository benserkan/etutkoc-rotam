"""Demo seslendirme üretici — Gemini 2.5 TTS ile sahne başına MP3.

Seslendirme metnini CANLI demo sayfalarından (template tek kaynak) çıkarır,
her sahne için Gemini TTS çağırır, PCM → MP3 (ffmpeg) olarak
app/static/demos/audio/{slug}/{n}.mp3 yazar. İdempotent (var olanı atlar).

Önkoşul: dev sunucu :8081 açık + Gemini anahtarı (.env/system_secrets) + ffmpeg.

  python -m scripts.generate_demo_audio                 # eksikleri üret
  python -m scripts.generate_demo_audio --force         # hepsini yeniden üret
  python -m scripts.generate_demo_audio --slug dna-coach
  python -m scripts.generate_demo_audio --dry-run       # yalnız metni çıkar+say
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
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import httpx

from app.services.system_secrets import get_gemini_paid_key, get_gemini_free_keys

BASE = "http://127.0.0.1:8081/demos?play="
MODEL = "gemini-2.5-flash-preview-tts"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
OUT_ROOT = Path(__file__).resolve().parent.parent / "app" / "static" / "demos" / "audio"
# Seslendirme metni anlık görüntüsü — dev sunucu (:8081) kapalıyken üretim için yedek.
# `--snapshot` ile doldurulur (sunucu açıkken); kota sıfırlanınca cron sunucu olmadan üretir.
SNAPSHOT = Path(__file__).resolve().parent / "demo_narrations.json"


def get_scenes(slug: str) -> list[str]:
    """Sahne metinlerini önce dev sunucudan, olmazsa JSON anlık görüntüsünden al."""
    try:
        html = httpx.get(BASE + slug, timeout=30).text
        scenes = extract_narrations(html)
        if scenes:
            return scenes
    except httpx.HTTPError:
        pass
    if SNAPSHOT.exists():
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        return data.get(slug, [])
    return []

# 8 yeni demo (her biri için ses). Ses: tüm demolar tek marka sesi "Kore" (net,
# ciddi). İstenirse rol bazlı değiştirilir.
SLUGS = [
    "book-add-coach", "program-create-coach",
    "review-cards-coach", "review-cards-student",
    "dna-coach", "dna-student",
    "focus-coach", "focus-student",
    "goals-coach", "goals-student",
    "whatsapp-coach", "whatsapp-institution",
    "daily-manage-student",
    "task-request-student", "task-request-coach",
    "academic-years-coach", "promote-grade-coach",
    "billing-coach", "sessions-coach",
    "week-grid-coach", "week-grid-student",
    "weekly-report-parent", "topic-performance",
    "support-system-coach", "notif-prefs-parent",
    "parent-ai-insight-parent",
    "inst-activity-stream", "inst-teacher-detail", "inst-invitations",
    "inst-roster", "inst-requests", "inst-analysis-1",
    "inst-analysis-2", "inst-parent-trust", "inst-membership",
]
VOICE = {s: "Kore" for s in SLUGS}

_STR = re.compile(r'"((?:[^"\\]|\\.)*)"\s*([+,]?)')


def extract_narrations(html: str) -> list[str]:
    """`var narrations = [ "a" + "b", "c", ... ];` bloğunu sahne listesine çevir.

    + ile birleşen string'ler aynı sahneye katılır; , yeni sahne başlatır.
    // yorum satırları temizlenir. Tırnak içi virgüller korunur.
    """
    m = re.search(r"var narrations\s*=\s*\[(.*?)\];", html, re.DOTALL)
    if not m:
        return []
    body = m.group(1)
    # // yorum satırlarını at (satır başı veya boşluk sonrası)
    body = re.sub(r"//[^\n]*", "", body)
    items: list[str] = []
    cur = ""
    for sm in _STR.finditer(body):
        cur += sm.group(1)
        op = sm.group(2)
        if op != "+":  # ',' veya '' → sahne biter
            items.append(cur.strip())
            cur = ""
    if cur.strip():
        items.append(cur.strip())
    # JS escape (\" \\) çöz
    return [s.replace('\\"', '"').replace("\\\\", "\\") for s in items]


def pcm_to_mp3(pcm: bytes, rate: int, out_mp3: Path):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = Path(tf.name)
    try:
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
            w.writeframes(pcm)
        out_mp3.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
             "-codec:a", "libmp3lame", "-b:a", "64k", str(out_mp3)],
            check=True,
        )
    finally:
        wav_path.unlink(missing_ok=True)


def tts(text: str, voice: str, keys: list[str], exhausted: set[str]) -> tuple[bytes, int]:
    """Sesi üret. Birden çok key (ücretli + ücretsiz, ayrı projeler/kotalar) sırayla
    denenir; bir key GÜNLÜK cap'e (per_model_per_day 429) takılınca `exhausted`'a
    eklenir ve sonraki key'e geçilir. Dakika-başı (RPM) 429'da aynı key beklenip
    tekrar denenir."""
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    last = ""
    # Her turda TÜM key'ler denenir (her birinin AYRI dakika-başı + günlük kotası
    # var). Bir key günlük cap'e takılırsa `exhausted`'a girer; dakika-başı (RPM)
    # 429'da ise hemen DİĞER key'e geçilir (onun ayrı RPM kovası boş olabilir).
    # Tüm key'ler bir turda başarısız olursa kısa bekleyip yeni tur denenir.
    for rnd in range(6):
        progressed = False
        for key in keys:
            if key in exhausted:
                continue
            progressed = True
            try:
                with httpx.Client(timeout=180) as c:
                    r = c.post(URL, json=body, headers={"x-goog-api-key": key, "content-type": "application/json"})
            except httpx.HTTPError as e:
                last = str(e); continue
            if r.status_code == 200:
                part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                mime = part.get("mimeType", "")
                rate = int(mime.split("rate=")[1].split(";")[0]) if "rate=" in mime else 24000
                return base64.b64decode(part["data"]), rate
            txt = r.text[:300]
            last = f"{r.status_code}: {txt}"
            if r.status_code == 429 and ("per_day" in txt or "PerDay" in txt or "PerProjectPerModel" in txt):
                exhausted.add(key)  # günlük cap → bu key bugün bitti
            # diğer 429 (RPM) / 500 / 503 → hemen sıradaki key'e geç
        if not progressed:
            break  # tüm key'ler günlük cap'li
        time.sleep(8)  # bir tur tüm key'lerde başarısız → RPM kovası dolsun, yeni tur
    raise RuntimeError(f"TTS başarısız: {last}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--snapshot", action="store_true",
                    help="Tüm slugların seslendirme metnini sunucudan çekip JSON'a yaz (sunucu açıkken).")
    args = ap.parse_args()

    # Snapshot modu: sunucudan tüm narration'ları topla → demo_narrations.json
    if args.snapshot:
        snap: dict[str, list[str]] = {}
        for slug in SLUGS:
            try:
                html = httpx.get(BASE + slug, timeout=30).text
            except httpx.HTTPError as e:
                print(f"[{slug}] alınamadı: {e}"); continue
            sc = extract_narrations(html)
            snap[slug] = sc
            print(f"[{slug}] {len(sc)} sahne")
        SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n✓ Anlık görüntü yazıldı: {SNAPSHOT} ({len(snap)} demo)")
        return 0

    # Tüm key'ler (ücretli + ücretsiz, ayrı projeler/kotalar). Her birinin kendi
    # 100/gün TTS kotası var → birini cap'leyince diğerine geçilir.
    keys: list[str] = []
    pk = get_gemini_paid_key()
    if pk:
        keys.append(pk)
    for fk in (get_gemini_free_keys() or []):
        if fk and fk not in keys:
            keys.append(fk)
    if not keys and not args.dry_run:
        print("HATA: Gemini anahtarı yok."); return 1
    exhausted: set[str] = set()
    if not args.dry_run:
        print(f"Kullanılabilir TTS key sayısı: {len(keys)} (her biri ~100/gün)")

    slugs = [args.slug] if args.slug else SLUGS
    total_made = total_skip = total_scenes = 0
    for slug in slugs:
        scenes = get_scenes(slug)
        total_scenes += len(scenes)
        print(f"\n[{slug}] {len(scenes)} sahne çıkarıldı.")
        if not scenes:
            print("  ⚠️ narration bulunamadı — atlanıyor."); continue
        if args.dry_run:
            for i, s in enumerate(scenes):
                print(f"  {i}: {s[:70]}…")
            continue
        for i, text in enumerate(scenes):
            out = OUT_ROOT / slug / f"{i}.mp3"
            if out.exists() and not args.force:
                total_skip += 1; continue
            try:
                pcm, rate = tts(text, VOICE[slug], keys, exhausted)
                pcm_to_mp3(pcm, rate, out)
                kb = out.stat().st_size / 1024
                print(f"  ✓ {i}.mp3 ({kb:.0f} KB)")
                total_made += 1
                time.sleep(0.5)  # nazik hız
            except Exception as e:
                print(f"  ✗ sahne {i}: {e}")
    print(f"\n=== Üretilen: {total_made} · atlanan(var): {total_skip} · toplam sahne: {total_scenes} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
