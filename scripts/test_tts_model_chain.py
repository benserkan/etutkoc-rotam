"""TTS model zinciri + ses çözme testi (gerçek Gemini çağrısı YOK).

  python scripts/test_tts_model_chain.py

Senaryolar:
  1. 2.5 biçimi (başlıksız PCM) → PCM aynen, hız mime'dan
  2. 3.8 biçimi (RIFF WAV) → başlık ayıklanır, yalnız PCM döner
  3. İlk model 404 (kapandı) → sıradaki modele düşer, ses üretilir
  4. İlk model bozuk yanıt → sıradaki modele düşer
  5. Tüm modeller başarısız → AIServiceUnavailable
  6. GEMINI_TTS_MODELS ortam değişkeni sırayı değiştirir
  7. synthesize_speech 3.8 WAV yanıtından geçerli ses dosyası üretir
"""
from __future__ import annotations

import base64
import io
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.services import tts
from app.services.ai_book_template import AIServiceUnavailable

PCM = (b"\x01\x02" * 2400)  # 0,1 sn, 24 kHz


def _wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _resp_json(data: bytes, mime: str) -> dict:
    return {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}
    ]}}]}


class _Resp:
    def __init__(self, status: int, payload: dict | None = None, text: str = ""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class _FakeClient:
    """model adı → yanıt üreten sahte httpx.Client."""
    plan: dict = {}
    calls: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, headers=None):
        model = url.split("/models/")[1].split(":")[0]
        _FakeClient.calls.append(model)
        return _FakeClient.plan[model]


results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail and not ok else ""))


def main() -> int:
    orig_client = tts.httpx.Client
    orig_key = tts.get_gemini_paid_key
    tts.httpx.Client = _FakeClient
    tts.get_gemini_paid_key = lambda: "test-key"
    os.environ.pop("GEMINI_TTS_MODELS", None)
    m1, m2, m3 = tts.DEFAULT_TTS_MODELS
    try:
        # 1
        pcm, rate = tts.decode_audio_part(
            {"mimeType": "audio/L16;codec=pcm;rate=22050", "data": base64.b64encode(PCM).decode()})
        check("1 başlıksız PCM aynen döner, hız mime'dan", pcm == PCM and rate == 22050, f"{len(pcm)} {rate}")

        # 2
        pcm, rate = tts.decode_audio_part(
            {"mimeType": "audio/wav", "data": base64.b64encode(_wav(PCM)).decode()})
        check("2 WAV başlığı ayıklanır", pcm == PCM and rate == 24000, f"{len(pcm)} {rate}")

        # 3
        _FakeClient.calls = []
        _FakeClient.plan = {
            m1: _Resp(404, text="model not found"),
            m2: _Resp(200, _resp_json(_wav(PCM), "audio/wav")),
        }
        pcm, rate = tts._tts_pcm("merhaba", "Kore", 5)
        check("3 kapanan modelden sıradakine düşer", pcm == PCM and _FakeClient.calls == [m1, m2],
              str(_FakeClient.calls))

        # 4
        _FakeClient.calls = []
        _FakeClient.plan = {
            m1: _Resp(200, {"candidates": []}),
            m2: _Resp(200, _resp_json(PCM, "audio/L16;codec=pcm;rate=24000")),
        }
        pcm, rate = tts._tts_pcm("merhaba", "Kore", 5)
        check("4 bozuk yanıtta sıradaki model", pcm == PCM and _FakeClient.calls == [m1, m2],
              str(_FakeClient.calls))

        # 5
        _FakeClient.calls = []
        _FakeClient.plan = {m: _Resp(503, text="overloaded") for m in (m1, m2, m3)}
        try:
            tts._tts_pcm("merhaba", "Kore", 5)
            check("5 hepsi başarısız → hata", False, "hata fırlatılmadı")
        except AIServiceUnavailable:
            check("5 hepsi başarısız → hata", _FakeClient.calls == [m1, m1, m2, m2, m3, m3],
                  str(_FakeClient.calls))

        # 6
        os.environ["GEMINI_TTS_MODELS"] = f" {m3} , {m1} "
        check("6 ortam değişkeni sırayı belirler", tts.tts_models() == [m3, m1], str(tts.tts_models()))
        os.environ.pop("GEMINI_TTS_MODELS")

        # 7
        _FakeClient.plan = {m1: _Resp(200, _resp_json(_wav(PCM), "audio/wav"))}
        audio, ctype = tts.synthesize_speech("merhaba")
        if ctype == "audio/wav":
            with wave.open(io.BytesIO(audio)) as w:
                ok = w.readframes(w.getnframes()) == PCM
        else:
            ok = ctype == "audio/mpeg" and len(audio) > 100
        check("7 synthesize_speech geçerli ses üretir", ok, ctype)
    finally:
        tts.httpx.Client = orig_client
        tts.get_gemini_paid_key = orig_key

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} geçti")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
