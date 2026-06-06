"""AI veli içgörüsü (P2b) — Gemini ücretli key.

Çocuğun KONU PERFORMANSI (çözülen test + doğru/yanlış) + DENEME sonuçlarından
VELİYE yönelik anlaşılır, cesaretlendirici bir analiz üretir. Koça-özel seans
notları KULLANILMAZ (gizlilik). Tıbbi/klinik teşhis yok; ailenin nasıl destek
olabileceğine dair somut öneriler.

Kredi öğrencinin KOÇUNUN havuzundan düşer (çağıran katman yönetir).
"""
from __future__ import annotations

import json
from typing import Any

from app.services import gemini
from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable

__all__ = ["generate_parent_insight", "AIInvalidResponse", "AIServiceUnavailable"]


def _as_list(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for x in v:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def _normalize(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": (obj.get("summary") or "").strip() if isinstance(obj.get("summary"), str) else "",
        "strengths": _as_list(obj.get("strengths")),
        "focus_areas": _as_list(obj.get("focus_areas")),
        "parent_tips": _as_list(obj.get("parent_tips")),
    }


def _build_prompt(student_name: str, subjects: list[dict[str, Any]], exams: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append(
        "Sen, bir öğrenci velisine çocuğunun çalışma durumunu sade ve anlaşılır bir "
        "dille açıklayan bir eğitim danışmanısın. Aşağıda çocuğun ders/konu bazında "
        "çözdüğü test ve doğru/yanlış performansı ile deneme sonuçları var. VELİYE "
        "yönelik, cesaretlendirici ama gerçekçi bir analiz yaz."
    )
    lines.append(f"\nÖğrenci: {student_name}")

    lines.append("\n--- DERS/KONU PERFORMANSI (çözülen test · doğruluk) ---")
    if not subjects:
        lines.append("Henüz çözülmüş test/konu verisi yok.")
    for s in subjects:
        acc = s.get("accuracy_pct")
        lines.append(
            f"{s.get('subject_name')}: {s.get('tests_solved', 0)} test, "
            f"doğruluk {('%' + str(acc)) if acc is not None else 'D/Y girilmemiş'}"
        )
        weak = s.get("weak_topics") or []
        if weak:
            lines.append("  Zorlandığı konular: " + ", ".join(
                f"{w.get('name')} (%{w.get('accuracy_pct')})" for w in weak))
        strong = s.get("strong_topics") or []
        if strong:
            lines.append("  İyi olduğu konular: " + ", ".join(
                f"{w.get('name')} (%{w.get('accuracy_pct')})" for w in strong))

    lines.append("\n--- DENEME SONUÇLARI (yeniden eskiye) ---")
    if not exams:
        lines.append("Henüz deneme sonucu girilmemiş.")
    for e in exams[:8]:
        lines.append(f"[{e.get('exam_date')}] {e.get('section_label')} — net {e.get('net')}")

    lines.append(
        "\n--- GÖREV ---\n"
        "YALNIZ şu JSON nesnesini döndür (açıklama, markdown yok):\n"
        "{\n"
        '  "summary": "çocuğun genel gidişatının veliye 3-5 cümlelik sade özeti",\n'
        '  "strengths": ["çocuğun güçlü/iyi giden yanları (2-4 madde)"],\n'
        '  "focus_areas": ["geliştirilmesi gereken konu/alanlar (2-4 madde)"],\n'
        '  "parent_tips": ["velinin evde nasıl destek olabileceğine dair somut, '
        'uygulanabilir öneriler (2-4 madde)"]\n'
        "}\n"
        "Kurallar: Türkçe, sade dil (veli eğitimci değil). Sıcak ve motive edici ol "
        "ama abartma. Uydurma — yalnız verilen verilere dayan. Tıbbi/klinik teşhis "
        "KOYMA; suçlayıcı olma. Öneriler aileyi yormayacak, uygulanabilir olsun."
    )
    return "\n".join(lines)


def generate_parent_insight(
    student_name: str,
    subjects: list[dict[str, Any]],
    exams: list[dict[str, Any]],
    *,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """Konu performansı + deneme → veli içgörüsü taslağı (dict).

    Raises:
        AIServiceUnavailable: API key yok / HTTP hatası
        AIInvalidResponse: parse hatası / boş yanıt
    """
    prompt = _build_prompt(student_name, subjects, exams)
    text = gemini.generate([gemini.text_part(prompt)], personal_data=True, timeout=timeout)
    out = _normalize(gemini.extract_json(text))
    if not out["summary"] and not out["strengths"] and not out["focus_areas"]:
        raise AIInvalidResponse("İçgörü üretilemedi (boş yanıt)")
    return out
