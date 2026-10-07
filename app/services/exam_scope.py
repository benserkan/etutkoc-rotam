"""Deneme kapsamı — GENEL deneme mi, BRANŞ denemesi mi? (TEK MERKEZ, 2026-10-06)

Sorun: aynı sınav türünde (ör. LGS) 90 soruluk genel deneme ile 20 soruluk
Matematik branş denemesi aynı seride kıyaslanıyordu → net grafiği "61 → 11"
düşüş gösteriyor, gelişim raporu / puan tahmini / veli e-postası yanlış yorum
üretiyordu. Netler ancak AYNI KAPSAMDAKİ denemeler arasında kıyaslanabilir.

Kural (veri gerektirmez, migration YOK):
  1. Koçun açık işareti varsa o esas (analysis_meta["scope"] = genel|brans).
  2. Başlıkta "branş" geçiyorsa branş.
  3. Türün standart soru sayısı biliniyorsa: soru < %60 → branş.
     (LGS 90 · TYT 120 · AYT 80 · YDT 80 · Maarif 1. Basamak 125)
  4. Standart bilinmiyorsa (okul / Maarif sınıf sınavları): tek derslik deneme
     branş, aksi halde genel.

Seri anahtarı: genel → tür değeri ("lgs"); branş → "lgs~matematik".
Hedef net (exam_targets) tür anahtarıyla tutulduğu için yalnız GENEL seriye uygulanır.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection
from app.models.exam_result import ExamResult

SEP = "~"
BRANCH_RATIO = 0.6

STANDARD_QUESTIONS: dict[str, int] = {
    "lgs": 90,
    "tyt": 120,
    "ayt_say": 80, "ayt_ea": 80, "ayt_soz": 80, "ayt_dil": 80,
    "maarif_1": 125,
}

# Kapsam etiketi için ders adları (en uzun eşleşme önce; geometri matematiğe katılır)
_SUBJECT_WORDS: list[tuple[str, str]] = [
    ("inkilap", "İnkılap Tarihi"), ("inkılap", "İnkılap Tarihi"),
    ("din kültürü", "Din Kültürü"), ("din kulturu", "Din Kültürü"),
    ("ingilizce", "İngilizce"), ("yabancı dil", "Yabancı Dil"),
    ("fen bilimleri", "Fen Bilimleri"), ("sosyal bilimler", "Sosyal Bilimler"),
    ("sosyal bilgiler", "Sosyal Bilgiler"),
    ("paragraf", "Türkçe"), ("türkçe", "Türkçe"), ("turkce", "Türkçe"),
    ("edebiyat", "Edebiyat"), ("matematik", "Matematik"), ("geometri", "Matematik"),
    ("problem", "Matematik"),
    ("fizik", "Fizik"), ("kimya", "Kimya"), ("biyoloji", "Biyoloji"),
    ("tarih", "Tarih"), ("coğrafya", "Coğrafya"), ("cografya", "Coğrafya"),
    ("felsefe", "Felsefe"), ("fen", "Fen Bilimleri"),
]

_PREFIX_RE = re.compile(r"^(tyt|ayt|lgs)\s+", re.I)


def _low(s: str) -> str:
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


def _canon_subject(name: str) -> str:
    """'AYT Geometri' → 'Matematik', 'TYT Türkçe' → 'Türkçe'; bilinmeyen ad olduğu gibi."""
    low = _low(_PREFIX_RE.sub("", (name or "").strip()))
    for word, label in _SUBJECT_WORDS:
        if word in low:
            return label
    return _PREFIX_RE.sub("", (name or "").strip()) or "Bilinmeyen ders"


def _subject_rows(exam: ExamResult) -> list[dict]:
    try:
        data = json.loads(exam.subject_nets) if exam.subject_nets else []
    except ValueError:
        return []
    out = []
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict) or not d.get("name"):
            continue
        q = int(d.get("correct") or 0) + int(d.get("wrong") or 0) + int(d.get("blank") or 0)
        if q > 0:
            out.append({"name": str(d["name"]), "q": q})
    return out


def _meta_scope(exam: ExamResult) -> str | None:
    try:
        meta = json.loads(exam.analysis_meta) if exam.analysis_meta else {}
    except ValueError:
        return None
    v = meta.get("scope") if isinstance(meta, dict) else None
    return v if v in ("genel", "brans") else None


def _skey(label: str) -> str:
    return re.sub(r"[^a-z0-9çğıöşü]+", "-", _low(label)).strip("-") or "ders"


@dataclass(frozen=True)
class ExamScope:
    kind: str               # "genel" | "brans"
    subject: str | None     # branşta ders etiketi ("Matematik")
    series_key: str         # "lgs" | "lgs~matematik"
    series_label: str       # "LGS (genel)" | "LGS · Matematik branş"

    @property
    def is_branch(self) -> bool:
        return self.kind == "brans"


def _section_value(section) -> str:
    return section.value if isinstance(section, ExamSection) else str(section)


def _section_label(section) -> str:
    try:
        return EXAM_SECTION_LABELS[ExamSection(_section_value(section))]
    except (ValueError, KeyError):
        return _section_value(section).upper()


def branch_subject(exam: ExamResult) -> str:
    """Branş denemesinin ders etiketi: ders kırılımından, yoksa başlıktan."""
    rows = _subject_rows(exam)
    if rows:
        totals: dict[str, int] = {}
        for r in rows:
            c = _canon_subject(r["name"])
            totals[c] = totals.get(c, 0) + r["q"]
        ordered = sorted(totals.items(), key=lambda x: -x[1])
        return " + ".join(n for n, _ in ordered[:2])
    low = _low(exam.title or "")
    for word, label in _SUBJECT_WORDS:
        if word in low:
            return label
    return "Karma"


def classify(exam: ExamResult) -> str:
    """'genel' | 'brans'."""
    forced = _meta_scope(exam)
    if forced:
        return forced
    if "branş" in _low(exam.title or "") or "brans" in _low(exam.title or ""):
        return "brans"
    sec = _section_value(exam.section)
    std = STANDARD_QUESTIONS.get(sec)
    qn = exam.total_correct + exam.total_wrong + exam.total_blank
    if std:
        if qn and qn < std * BRANCH_RATIO:
            return "brans"
        return "genel"
    subjects = {_canon_subject(r["name"]) for r in _subject_rows(exam)}
    return "brans" if len(subjects) == 1 else "genel"


def exam_scope(exam: ExamResult) -> ExamScope:
    sec = _section_value(exam.section)
    label = _section_label(exam.section)
    if classify(exam) == "genel":
        return ExamScope("genel", None, sec, f"{label} (genel deneme)")
    subj = branch_subject(exam)
    return ExamScope("brans", subj, f"{sec}{SEP}{_skey(subj)}", f"{label} · {subj} branş")


def series_key(exam: ExamResult) -> str:
    return exam_scope(exam).series_key


def section_of_key(key: str) -> str:
    """'lgs~matematik' → 'lgs'."""
    return (key or "").split(SEP, 1)[0]


def is_general_key(key: str | None) -> bool:
    return bool(key) and SEP not in key


def series_options(exams: list[ExamResult]) -> list[dict]:
    """Seçici seçenekleri: genel seriler önce (deneme sayısına göre), sonra branşlar."""
    counts: dict[str, int] = {}
    labels: dict[str, str] = {}
    kinds: dict[str, str] = {}
    for e in exams:
        s = exam_scope(e)
        counts[s.series_key] = counts.get(s.series_key, 0) + 1
        labels[s.series_key] = s.series_label
        kinds[s.series_key] = s.kind
    ordered = sorted(counts.items(), key=lambda x: (kinds[x[0]] != "genel", -x[1]))
    return [{"value": k, "label": labels[k], "count": n, "kind": kinds[k],
             "section": section_of_key(k)} for k, n in ordered]


def resolve_series(requested: str | None, options: list[dict]) -> str | None:
    """İstenen seri; yoksa / yalnız tür verildiyse uyumlu ilk seri.

    Eski istemciler `section=lgs` gönderir → 'lgs' genel serisi varsa o, yoksa
    o türün ilk serisi (ör. yalnız branş denemesi olan öğrenci).
    """
    values = [o["value"] for o in options]
    if requested in values:
        return requested
    if requested:
        sec = section_of_key(requested)
        for v in values:
            if section_of_key(v) == sec:
                return v
    return values[0] if values else None


def in_series(exam: ExamResult, key: str | None) -> bool:
    return key is not None and series_key(exam) == key
