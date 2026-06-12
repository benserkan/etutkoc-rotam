"""AI Kariyer Sentezi — anket sonuçları + gerçek akademik veri → kariyer önerisi.

Kullanıcının çekirdek ihtiyacı (2026-06-12): öğrencilerin çoğu hangi mesleğe
yatkın olduğunu bilmiyor; koçun hedef belirleme çalışmasının en güçlü girdisi
**beceri × ilgi × akademik gerçeklik** denklemidir. Somut bir bölüm/meslek
hedefi (örn. eşit ağırlıkçıya "psikoloji") sınav motivasyonunu dönüştürür.

Tasarım ilkesi: **AI test SORMAZ — anketler ölçer (deterministik skor), AI
sentezler.** Girdi: Mesleki İlgi (RIASEC) + Beceri Seti (zorunlu çekirdek),
Akademik Benlik + Çoklu Zeka (varsa) + deneme netleri + program tamamlama.
Çıktı: 3-5 meslek/bölüm önerisi (nedenli, YKS alan uyumlu) + güçlü yönler +
koç için hedef-belirleme seans gündemi + dikkat noktaları.

GİZLİLİK: kişisel veri → Gemini ÜCRETLİ key (personal_data=True, no-training).
Sonuç öneri/taslaktır; yönlendirme kararı koç + öğrenci + velinindir, klinik/
kesin yönlendirme dili kullanılmaz. Maliyet endpoint'te
`consume_credits(UsageKind.AI_CAREER_SYNTHESIS)` ile metere edilir.
"""
from __future__ import annotations

import logging
from typing import Any

from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
from app.services import gemini

logger = logging.getLogger(__name__)

__all__ = ["generate_career_synthesis", "AIInvalidResponse", "AIServiceUnavailable"]


def _list_of_str(v: Any, *, limit: int) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if x and str(x).strip()][:limit]


def _normalize(obj: dict[str, Any]) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    raw = obj.get("career_suggestions")
    if isinstance(raw, list):
        for item in raw[:5]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            suggestions.append({
                "title": title,
                "field": str(item.get("field") or "").strip(),
                "why": str(item.get("why") or "").strip(),
                "example_departments": _list_of_str(
                    item.get("example_departments"), limit=4
                ),
            })
    return {
        "summary": str(obj.get("summary") or "").strip(),
        "career_suggestions": suggestions,
        "strengths": _list_of_str(obj.get("strengths"), limit=5),
        "agenda": _list_of_str(obj.get("agenda"), limit=6),
        "watch_outs": _list_of_str(obj.get("watch_outs"), limit=4),
    }


def _build_prompt(
    student_name: str,
    grade_label: str,
    surveys: list[dict[str, Any]],
    academic: dict[str, Any],
    exams: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append(
        "Sen, ortaokul/lise öğrencilerine kariyer keşfi konusunda danışmanlık "
        "yapan deneyimli bir eğitim koçu asistanısın. Aşağıda bir öğrencinin "
        "tanıma anketi sonuçları ve GERÇEK akademik verileri var. Koçun "
        "öğrenciyle yapacağı HEDEF BELİRLEME seansına hazırlan: öğrencinin "
        "beceri × ilgi × akademik gerçeklik kesişimine uyan somut meslek/bölüm "
        "önerileri üret."
    )
    lines.append(f"\nÖğrenci: {student_name} ({grade_label})")

    lines.append("\n--- ANKET SONUÇLARI (öğrencinin öz-değerlendirmesi) ---")
    for s in surveys:
        lines.append(f"\n[{s['title']}] (tamamlandı: {s.get('completed_at', '?')})")
        for d in s.get("dimensions", []):
            lines.append(
                f"  - {d['label']}: %{round(d['score_pct'])} ({d['level_label']})"
            )

    lines.append("\n--- GERÇEK AKADEMİK VERİ (sistemden ölçülen) ---")
    pct = academic.get("week_completion_pct")
    lines.append(
        "Program tamamlama (bu hafta): "
        + (f"%{pct}" if pct is not None else "veri yok")
    )
    rate = academic.get("recent_rate")
    if rate is not None:
        lines.append(f"Çalışma hızı: {rate} test/gün")
    behind = academic.get("behind_subjects") or []
    if behind:
        lines.append("Geride kalan dersler: " + ", ".join(
            f"{b.get('name')} (%{b.get('percent_done')})" for b in behind))
    if exams:
        lines.append("Son denemeler:")
        for e in exams:
            net_pct = f" (%{e['net_pct']} başarı)" if e.get("net_pct") is not None else ""
            lines.append(f"  - {e['title']} [{e['section_label']}]: net {e['net']}{net_pct}")
    else:
        lines.append("Henüz deneme sonucu girilmemiş.")

    lines.append(
        "\n--- GÖREV ---\n"
        "YALNIZ şu JSON nesnesini döndür (açıklama, markdown yok):\n"
        "{\n"
        '  "summary": "öğrencinin beceri-ilgi-akademik profilinin 2-4 cümlelik sentezi",\n'
        '  "career_suggestions": [\n'
        '    {"title": "meslek/alan adı", "field": "YKS alan uyumu (Sayısal/Eşit Ağırlık/Sözel/Dil) veya LGS için lise türü önerisi", '
        '"why": "bu öğrenciye neden uygun — anket boyutları + akademik veriyle gerekçele", '
        '"example_departments": ["örnek üniversite bölümleri (2-4)"]}\n'
        "  ],\n"
        '  "strengths": ["öğrencinin öne çıkan güçlü yönleri (3-5)"],\n'
        '  "agenda": ["koçun hedef belirleme seansında konuşacağı somut maddeler (3-5)"],\n'
        '  "watch_outs": ["dikkat noktaları — örn. ilgi yüksek ama ilgili ders performansı düşükse (0-3)"]\n'
        "}\n"
        "Kurallar: Türkçe yaz. 3-5 öneri ver; her önerinin gerekçesi anket "
        "boyutlarına VE akademik veriye dayansın (uydurma). İlgi ile gerçek ders "
        "performansı çelişiyorsa bunu watch_outs'ta dürüstçe belirt. Kesin "
        "yönlendirme dili kullanma — 'yakın duruyor', 'keşfetmeye değer' gibi "
        "öneri dili kullan; karar koç + öğrenci + ailenindir. Sınıf seviyesine "
        "uygun konuş (ortaokulda lise türü + alan eğilimi, lisede bölüm/meslek)."
    )
    return "\n".join(lines)


def generate_career_synthesis(
    student_name: str,
    grade_label: str,
    surveys: list[dict[str, Any]],
    academic: dict[str, Any],
    exams: list[dict[str, Any]],
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Anket sonuçları + akademik veri → kariyer sentezi (dict).

    Raises:
        AIServiceUnavailable: API key yok / HTTP hatası
        AIInvalidResponse: parse hatası / boş yanıt
    """
    prompt = _build_prompt(student_name, grade_label, surveys, academic, exams)
    text = gemini.generate(
        [gemini.text_part(prompt)], personal_data=True, timeout=timeout,
        max_output_tokens=16384,
    )
    out = _normalize(gemini.extract_json(text))
    if not out["summary"] or not out["career_suggestions"]:
        raise AIInvalidResponse("Kariyer sentezi üretilemedi (boş yanıt)")
    return out
