"""AI koçluk içgörüsü — birikmiş seans geçmişi → bir sonraki seans hazırlığı (KS4).

Koçun girdiği seans notları + öğrencinin akademik anlık görüntüsü Claude'a verilir;
bir sonraki seans için ÖZET + ÖNERİLEN GÜNDEM ("bugün şunu konuş") + psikolojik/
motivasyon ipuçları + dikkat edilecekler üretilir.

GİZLİLİK: Sonuç TASLAK/ÖNERİ — koç değerlendirir; kaydedilmez. Anthropic httpx
plumbing + JSON parse, `ai_session_capture` modülünden reuse edilir. Maliyet
`consume_credits(UsageKind.AI_COACHING_INSIGHT)` ile metere edilir (endpoint'te).
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
from app.services.ai_session_capture import _claude_messages, _extract_json_object

logger = logging.getLogger(__name__)

__all__ = ["generate_coaching_insight", "AIInvalidResponse", "AIServiceUnavailable"]


def _list_of_str(v: Any, *, limit: int) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if x and str(x).strip()][:limit]


def _normalize_insight(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": str(obj.get("summary") or "").strip(),
        "agenda_suggestions": _list_of_str(obj.get("agenda_suggestions"), limit=6),
        "psychological_tips": _list_of_str(obj.get("psychological_tips"), limit=5),
        "watch_outs": _list_of_str(obj.get("watch_outs"), limit=4),
    }


def _build_prompt(student_name: str, sessions: list[dict[str, Any]], academic: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(
        "Sen, ortaokul/lise öğrencileriyle çalışan deneyimli bir eğitim koçuna "
        "danışmanlık yapan bir asistansın. Aşağıda bir öğrencinin son koçluk "
        "seanslarının notları ve güncel akademik durumu var. Koçun BİR SONRAKİ "
        "seansa hazırlanmasına yardım et."
    )
    lines.append(f"\nÖğrenci: {student_name}")

    lines.append("\n--- AKADEMİK DURUM ---")
    pct = academic.get("week_completion_pct")
    lines.append(f"Bu hafta program tamamlama: {('%' + str(pct)) if pct is not None else 'veri yok'} "
                 f"({academic.get('week_completed', 0)}/{academic.get('week_planned', 0)} soru)")
    lines.append(f"Son günlerdeki çalışma hızı: {academic.get('recent_rate', 0)} test/gün")
    behind = academic.get("behind_subjects") or []
    if behind:
        lines.append("Geride kalan dersler: " + ", ".join(
            f"{b.get('name')} (%{b.get('percent_done')})" for b in behind))
    le = academic.get("latest_exam")
    if le:
        lines.append(f"Son deneme: {le.get('section_label')} — net {le.get('net')}"
                     + (f" (%{le.get('net_pct')} başarı)" if le.get("net_pct") is not None else ""))
    else:
        lines.append("Henüz deneme sonucu girilmemiş.")

    lines.append("\n--- SON SEANSLAR (yeniden eskiye) ---")
    if not sessions:
        lines.append("Kayıtlı seans yok.")
    for s in sessions:
        parts = [f"[{s.get('session_date')}] ({s.get('status_label')})"]
        if s.get("mood"):
            parts.append(f"ruh hali {s['mood']}/5")
        lines.append(" ".join(parts))
        if s.get("agenda"):
            lines.append(f"  Gündem: {s['agenda']}")
        if s.get("coach_note"):
            lines.append(f"  Not: {s['coach_note']}")
        if s.get("next_change"):
            lines.append(f"  Değiştirilecek: {s['next_change']}")
        if s.get("tags"):
            lines.append(f"  Etiketler: {', '.join(s['tags'])}")

    lines.append(
        "\n--- GÖREV ---\n"
        "YALNIZ şu JSON nesnesini döndür (açıklama, markdown yok):\n"
        "{\n"
        '  "summary": "öğrencinin son seanslardaki gidişatının 2-4 cümlelik özeti",\n'
        '  "agenda_suggestions": ["bir sonraki seansta konuşulacak somut maddeler (3-5)"],\n'
        '  "psychological_tips": ["koça psikolojik/motivasyonel yaklaşım önerileri (2-4)"],\n'
        '  "watch_outs": ["dikkat edilecek riskler/işaretler (0-3, yoksa boş liste)"]\n'
        "}\n"
        "Kurallar: Türkçe yaz. Sıcak ama gerçekçi ol. Uydurma — yalnız verilen "
        "notlara/verilere dayan. Tıbbi/klinik teşhis koyma; koçluk dili kullan. "
        "Maddeler kısa ve uygulanabilir olsun."
    )
    return "\n".join(lines)


def generate_coaching_insight(
    student_name: str,
    sessions: list[dict[str, Any]],
    academic: dict[str, Any],
    *,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """Seans geçmişi + akademik durum → koçluk içgörüsü taslağı (dict).

    Raises:
        AIServiceUnavailable: API key yok / HTTP hatası
        AIInvalidResponse: parse hatası / boş yanıt
    """
    prompt = _build_prompt(student_name, sessions, academic)
    text = _claude_messages([{"type": "text", "text": prompt}], timeout=timeout)
    out = _normalize_insight(_extract_json_object(text))
    if not out["summary"] and not out["agenda_suggestions"]:
        raise AIInvalidResponse("İçgörü üretilemedi (boş yanıt)")
    return out
