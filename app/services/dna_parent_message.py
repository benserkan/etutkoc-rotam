"""DNA panelinden veliye gönderilecek otomatik mesaj şablonu üreticisi.

`build_dna_parent_message(student, burnout, profile)` çağrısı, BurnoutReport +
StudyDnaProfile verilerinden Türkçe, sayı destekli bir mesaj metni üretir.

Mesaj kullanım yeri:
- `/teacher/students/{id}/dna` sayfasındaki "Veliye duyur" butonu öğretmene
  bu metni preview olarak gösterir; öğretmen düzenler ya da olduğu gibi yollar.
- Gönderim mevcut `TeacherNoteToParent` + `on_teacher_note_created` event
  trigger'ı üzerinden mevcut bildirim kuyruğuna düşer (email + WA).

Tasarım kararı:
- Profil "yetersiz veri" ise düz bir genel uyarı dönüyoruz, sayı uydurmuyoruz.
- Sinyal yoksa "şu an iyi gidiyor" şablonu var (öğretmen olumlu da iletebilsin).
- 3'ten fazla sinyal varsa en şiddetli 3'üyle sınırlı (mesaj uzamasın).
"""
from __future__ import annotations

from app.models import User
from app.services.burnout import BurnoutReport
from app.services.study_dna import StudyDnaProfile


CHRONO_TR = {
    "morning": "sabah saatlerinde",
    "afternoon": "öğleden sonra",
    "evening": "akşam üzeri",
    "night": "gece geç saatlerde",
    "unknown": None,
}

# Her sinyal için veliye anlaşılır bir cümle + (varsa) öğretmen aksiyonu.
SIGNAL_PARENT_LINE = {
    "night_owl": "• Gece 22 ile 04 arası tamamlamaların oranı yüksek seyrediyor.",
    "weekend_no_break": "• Son üç haftadır hafta sonu hiç dinlenme günü almamış.",
    "intensity_spike": "• Bu hafta görev yoğunluğu geçen haftaya göre belirgin şekilde arttı.",
    "completion_drop": "• Bu hafta tamamlama temposu geçen haftaya göre belirgin düştü.",
    "streak_break": "• Birkaç gün üst üste çalışmadan sonra son üç günde tamamlama yok.",
}


def _greeting(student: User) -> str:
    """Kişiye özel selam — veli adı bilinmediği için 'Sayın veli'."""
    return f"Sayın velim,"


def _level_intro(level: str, student_name: str) -> str:
    if level == "critical":
        return (
            f"{student_name}'ın son iki haftalık çalışma örüntüsünü inceledim, "
            "birkaç noktada gözlemlerimi sizinle paylaşmak istedim."
        )
    if level == "warn":
        return (
            f"{student_name}'ın çalışma temposunda son dönemde dikkatimi çeken "
            "bir kaç işaret var, sizinle de paylaşayım istedim."
        )
    if level == "watch":
        return (
            f"{student_name}'ın çalışma düzeniyle ilgili küçük bir gözlemimi "
            "sizinle de paylaşmak istedim."
        )
    return (
        f"{student_name}'ın bu dönemki çalışma düzeniyle ilgili olumlu bir not "
        "iletmek istedim."
    )


def _closing(level: str) -> str:
    if level == "critical":
        return (
            "Bu hafta yükü hafifletmek ve birkaç dinlenme penceresi açmak için "
            "küçük düzenlemeler yapıyorum. Müsait olduğunuzda 10 dakika "
            "konuşabilir miyiz?"
        )
    if level == "warn":
        return (
            "Önümüzdeki günler için programda küçük ayarlamalar planlıyorum. "
            "Sizinle de kısa bir konuşma faydalı olur."
        )
    if level == "watch":
        return (
            "Şimdilik küçük bir gözlem, ileride büyümemesi için takipte "
            "olacağım. Aklınızda olsun istedim."
        )
    return (
        "Şu an için tempo sağlıklı görünüyor — bu duruşu birlikte korumaya "
        "devam edelim."
    )


def build_dna_parent_message(
    *,
    student: User,
    teacher: User,
    burnout: BurnoutReport,
    profile: StudyDnaProfile,
) -> str:
    """DNA verisinden veliye uygun, sayı destekli mesaj üret.

    Çıktı düz metin (email + WA). Maks ~600 karakter — WA pratik sınır içinde.
    """
    lines: list[str] = []
    lines.append(_greeting(student))
    lines.append("")
    lines.append(_level_intro(burnout.risk_level, student.full_name))

    # Yetersiz veri ya da sinyal yoksa kısa kalsın
    if not profile.has_enough_data:
        lines.append("")
        lines.append(
            "Henüz çalışma profili için yeterli veri yok, ama sizi sürecin "
            "içinde tutmak için yazdım."
        )
        lines.append("")
        lines.append(_closing(burnout.risk_level))
        lines.append("")
        lines.append(f"Saygılarımla,\n{teacher.full_name}")
        return "\n".join(lines)

    # Sayı destekli giriş — saat bazlı her şey güven eşiği altındaysa atlanır.
    # chronotype, peak_hour, peak_day_idx hepsi filtrelenmiş heatmap'ten geliyor;
    # batch ağırlıklı veride hepsi anlamsız → mesajda yer almasın.
    low_hour_confidence = profile.hour_data_confidence < 50
    if not low_hour_confidence:
        facts: list[str] = []
        chrono = CHRONO_TR.get(profile.chronotype)
        if chrono:
            facts.append(f"Çalışma saatleri ağırlıklı olarak {chrono}")
        if profile.peak_day_name and profile.peak_hour is not None:
            facts.append(
                f"en yoğun tempoyu {profile.peak_day_name} günü "
                f"{profile.peak_hour:02d}:00 sularında yakalıyor"
            )
        if facts:
            lines.append("")
            lines.append("Genel tablo: " + ", ".join(facts) + ".")

    # En şiddetli en fazla 3 sinyal. Saat verisi güvensizse night_owl yutulur.
    if burnout.signals:
        signals_to_show = []
        for sig in burnout.signals:
            if sig.kind == "night_owl" and low_hour_confidence:
                continue
            signals_to_show.append(sig)
            if len(signals_to_show) >= 3:
                break
        if signals_to_show:
            lines.append("")
            lines.append("Son dönem öne çıkan noktalar:")
            for sig in signals_to_show:
                text = SIGNAL_PARENT_LINE.get(sig.kind)
                if text:
                    lines.append(text)

    # Tamamlama oranı destekleyici cümle
    if profile.total_planned >= 5:
        pct = int(round(profile.completion_rate * 100))
        lines.append("")
        lines.append(
            f"Son {profile.window_days} günde planlanan görevlerin yüzde "
            f"{pct}'sini tamamladı ({profile.total_completed}/"
            f"{profile.total_planned})."
        )

    lines.append("")
    lines.append(_closing(burnout.risk_level))
    lines.append("")
    lines.append(f"Saygılarımla,\n{teacher.full_name}")

    return "\n".join(lines)
