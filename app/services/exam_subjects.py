"""AYT alan ayrımı (sayısal / eşit ağırlık / sözel) — TEK MERKEZ.

AYT kitapçığı tektir; öğrenci yalnız alanının bölümlerini çözer. SAYISAL
öğrencinin 86 sözel boşu belgede "Toplam 166 soru · 103 boş" diye yazar ama
öğrencinin sınavı 80 sorudur. Sözel satırlar kayda girince ders kırılımı
("AYT Edebiyat 0/0/24"), Sınav Davranışı ("%100 boş · 24 kaçan net"),
aksiyon planı ("son denemede 103 boş"), gelişim raporu, veli tablosu ve kurum
net-başarı yüzdesi (38/166) anlamsızlaşıyordu (Yağmur #224 AYT-2, 2026-10-11;
koç: "sayısal öğrencide sözel dersler hiç dikkate alınmamalı — her analiz
ekranında bu ayrıma dikkat edilmeli").

KURAL: kayıt anında (confirm / düzeltme / yeniden kurulum) AYT evreninde,
öğrencinin alanı biliniyorsa, alan DIŞI ve HİÇ cevaplanmamış (doğru=yanlış=0)
ders grupları ders kırılımından DÜŞER; toplam boş da o kadar azalır (net
değişmez). Soru satırları (ExamResultQuestion) belgeye sadık kalır — "Satırları
düzelt" hepsini gösterir; konu analizi aynı kuralı satır düzeyinde uygular
(`untaken_optional_block_ids`). Alan içi boş ders (zaman yetmedi) GERÇEK
eksiktir, kalır. Alanı bilinmeyen öğrencide (track None) hiçbir şey düşmez.
Bütün okuyucular (kart, davranış tablosu, rapor, mail, kurum panosu, mobil)
kayıttan beslendiği için ayrım her ekranda otomatik tutarlıdır.
"""
from __future__ import annotations

from app.models import ExamSection


def untaken_track_keys(section: ExamSection | None, track) -> set[str] | None:
    """Alan İÇİ derslerin kanonik anahtarları; filtre uygulanmayacaksa None."""
    from app.services.curriculum_progress import TRACK_AYT_SUBJECTS
    from app.services.exam_import_service import (
        EXAM_UNIVERSE_AYT, _subject_key, universe_for_section,
    )
    if section is None or track is None:
        return None
    if universe_for_section(section) != EXAM_UNIVERSE_AYT:
        return None
    keys = {_subject_key(n) for n in TRACK_AYT_SUBJECTS.get(track, set())}
    return keys or None


def split_untaken_groups(
    groups: list[dict], section: ExamSection | None, track,
) -> tuple[list[dict], list[dict]]:
    """Ders grupları ({name, correct, wrong, blank, …}) → (kalan, girilmeyen)."""
    from app.services.exam_import_service import _subject_key
    keys = untaken_track_keys(section, track)
    if keys is None:
        return list(groups), []
    kept: list[dict] = []
    dropped: list[dict] = []
    for g in groups:
        answered = int(g.get("correct") or 0) + int(g.get("wrong") or 0)
        if answered == 0 and _subject_key(g.get("name")) not in keys:
            dropped.append(g)
        else:
            kept.append(g)
    return kept, dropped
