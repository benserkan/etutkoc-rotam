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
from app.services import gemini

logger = logging.getLogger(__name__)

__all__ = ["generate_coaching_insight", "generate_report_agenda", "AIInvalidResponse", "AIServiceUnavailable"]


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
    # Faz 3: son 7 günde işlenen müfredat üniteleri (seans "geçen hafta" analizi)
    ru = academic.get("recent_units") or []
    if ru:
        lines.append("Son 7 günde işlenen üniteler: " + ", ".join(
            f"{u.get('subject')}—{u.get('topic')} ({u.get('tests')} test)" for u in ru[:10]))

    # YSA: öğrencinin arşivlediği YANLIŞ sorular — "neden yanlış yapıyor"un
    # en somut kanıtı (biriken konular + hata türü dağılımı + kapanış hızı)
    wa = academic.get("wrong_archive") or {}
    if wa.get("open") or wa.get("top_topics"):
        lines.append(
            f"Yanlış arşivi: {wa.get('open', 0)} açık yanlış, "
            f"son 30 günde {wa.get('closed_last_30d', 0)} yanlış kapatıldı "
            "(kapanış = aralıklı iki doğru çözüm)."
        )
        tt = wa.get("top_topics") or []
        if tt:
            lines.append("Yanlışı en çok biriken konular: " + ", ".join(
                f"{t.get('subject')}—{t.get('topic')} ({t.get('open')} açık)"
                for t in tt))
        et = wa.get("error_types") or {}
        if et:
            from app.models import WQ_ERROR_LABELS_TR
            lines.append("Hata türü dağılımı: " + ", ".join(
                f"{WQ_ERROR_LABELS_TR.get(k, k)} {v}" for k, v in
                sorted(et.items(), key=lambda x: -x[1])))

    # Deneme köprüsü (Faz 3): konu × deneme analizinden en büyük net
    # fırsatları + unutulan konular — "hangi konuya çalışsak" sorusunun
    # ölçülmüş cevabı (PDF'ten aktarılan denemelerin soru satırlarından).
    ex = academic.get("exam_topics") or {}
    if ex.get("opportunities") or ex.get("forgotten"):
        lines.append(
            f"Deneme konu analizi ({ex.get('section_label')}, "
            f"son {ex.get('exams')} deneme):")
        ops = ex.get("opportunities") or []
        if ops:
            lines.append("En büyük net fırsatları: " + ", ".join(
                f"{o.get('subject')}—{o.get('topic')} (+{o.get('gain')} net/deneme)"
                for o in ops))
        fg = ex.get("forgotten") or []
        if fg:
            lines.append("Unutulmuş görünen konular: " + ", ".join(
                f"{t.get('subject')}—{t.get('topic')}" for t in fg))

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
    text = gemini.generate([gemini.text_part(prompt)], personal_data=True, timeout=timeout)
    out = _normalize_insight(gemini.extract_json(text))
    if not out["summary"] and not out["agenda_suggestions"]:
        raise AIInvalidResponse("İçgörü üretilemedi (boş yanıt)")
    return out


# ============================================================================
# Haftalık rapor → "Seans gündemi" (2026-08-19)
# ============================================================================
def _normalize_report_agenda(obj: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, str]] = []
    for x in (obj.get("agenda") or []):
        if isinstance(x, dict):
            t = str(x.get("title") or "").strip()
            d = str(x.get("detail") or "").strip()
            if t or d:
                items.append({"title": t or d[:60], "detail": d})
        elif isinstance(x, str) and x.strip():
            items.append({"title": x.strip()[:60], "detail": x.strip()})
    return {
        "summary": str(obj.get("summary") or "").strip(),
        "agenda": items[:10],
        "psychological_tips": _list_of_str(obj.get("psychological_tips"), limit=5),
        "watch_outs": _list_of_str(obj.get("watch_outs"), limit=4),
    }


def _build_report_prompt(student_name: str, bundle: dict[str, Any], sessions: list[dict[str, Any]]) -> str:
    import json as _json
    lines: list[str] = []
    lines.append(
        "Sen, lise/üniversite sınavına hazırlanan öğrencilerle çalışan deneyimli bir eğitim "
        "koçuna danışmanlık yapan bir asistansın. Aşağıda öğrencinin BİR HAFTALIK programının "
        "ölçülmüş verisi (görev/test/deneme seyri, ders ve konu bazlı doğru-yanlış, branş "
        "denemeleri, müfredat kapsama, başlanmamış kaynaklar, öğrencinin koçuna yazdığı mesajlar, "
        "çalışma saatleri) ve kural motorunun çıkardığı ham gündem maddeleri var. Koçun bir "
        "sonraki koçluk SEANSI için 'Seans gündemi — veriden çıkan başlıklar' yaz."
    )
    lines.append(f"\nÖğrenci: {student_name}")
    lines.append("\n--- HAFTANIN VERİSİ (JSON) ---")
    lines.append(_json.dumps(bundle, ensure_ascii=False)[:14000])
    if sessions:
        lines.append("\n--- ÖNCEKİ SEANSLAR (yeniden eskiye) ---")
        for s in sessions[:4]:
            lines.append(f"[{s.get('session_date')}] gündem: {s.get('agenda') or '-'} | not: {s.get('coach_note') or '-'} | değişiklik: {s.get('next_change') or '-'}")
    lines.append(
        "\n--- GÖREV ---\n"
        "YALNIZ şu JSON nesnesini döndür (açıklama, markdown yok):\n"
        "{\n"
        '  "summary": "haftanın 2-3 cümlelik gidişat özeti (rakamlı)",\n'
        '  "agenda": [{"title": "kısa başlık", "detail": "2-4 cümle: somut rakam + karar ya da koça soru"}],\n'
        '  "psychological_tips": ["koça yaklaşım önerileri (2-4)"],\n'
        '  "watch_outs": ["dikkat edilecek riskler (0-3)"]\n'
        "}\n"
        "Kurallar: Türkçe yaz. 7-10 gündem maddesi, ÖNCELİK SIRASIYLA (önce takdir/özet, sonra en "
        "kritik olanlar, en sonda gelecek hafta programı). Her madde verilen rakamlara dayansın; "
        "uydurma. Ders ve konu adlarını aynen kullan. Öğrenci mesajlarındaki sinyalleri (zorlanma, "
        "enerji, kaynak bitti, bekleyen soru) maddelere yedir. Sıcak ama net; koçluk dili; tıbbi/"
        "klinik teşhis yok. Her madde bir KARAR ya da bir SORU içersin."
    )
    return "\n".join(lines)


def generate_report_agenda(
    student_name: str,
    bundle: dict[str, Any],
    sessions: list[dict[str, Any]] | None = None,
    *,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Haftalık rapor paketi → akıcı, rakamlı seans gündemi (+ KS4 cache alanları).

    Raises: AIServiceUnavailable / AIInvalidResponse (endpoint çevirir).
    """
    prompt = _build_report_prompt(student_name, bundle, sessions or [])
    text = gemini.generate([gemini.text_part(prompt)], personal_data=True, timeout=timeout,
                           max_output_tokens=12288)
    out = _normalize_report_agenda(gemini.extract_json(text))
    if not out["agenda"]:
        raise AIInvalidResponse("Gündem üretilemedi (boş yanıt)")
    return out
