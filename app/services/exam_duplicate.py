"""Deneme mükerrer tespiti — TEK MERKEZ (2026-09-19).

Saha: aynı karne PDF'i iki kez aktarıldı (öğrenci #163); eski koruma yalnız
"aynı ad + tarih" bakıyor ve "yine de kaydet" ile geçiliyordu → iki kayıt,
konu×deneme analizi ikisini de saydı. Üç katman, kredisiz ve AI'sız:

1. **Belge parmak izi** — PDF SHA-256. Aynı dosya = kesin mükerrer; analiz
   adımında, Gemini'ye gitmeden yakalanır (kredi harcanmaz).
2. **İçerik parmak izi** — aynı öğrenci + aynı sınav türü + aynı soru sayısı +
   soru soru aynı öğrenci cevabı/sonucu. Tam eşleşme kesin (aynı karnenin
   yeniden taranmış kopyası); ≥%95 "büyük olasılıkla" (koç birkaç satırı
   düzeltmiş olabilir).
3. **Ad + tarih** — normalize ad eşit ve tarih aynı ya da ±3 gün → "büyük
   olasılıkla". Tek başına kesin sayılmaz (aynı adlı deneme gerçekten iki kez
   çözülmüş olabilir).

Karar kuralı çağırana aittir: `level == "exact"` → kayıt AÇILMAZ (zorlama yok;
yol: mevcut kaydı düzelt / "yerine yaz"); `level == "likely"` → uyarı, koç
"yerine yaz" ya da "ayrı kaydet"i seçer.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session, selectinload

from app.models import ExamResult, ExamResultQuestion, ExamSection

NEAR_ANSWER_RATIO = 0.95   # bu oranın üstü "büyük olasılıkla aynı"
NEAR_DATE_DAYS = 3         # ad aynı + tarih bu kadar yakın → uyarı

LEVEL_EXACT = "exact"
LEVEL_LIKELY = "likely"

REASON_LABELS_TR = {
    "same_file": "aynı PDF dosyası daha önce aktarılmış",
    "same_answers": "soru soru aynı cevaplar daha önce kaydedilmiş",
    "near_answers": "cevapların neredeyse tamamı kayıtlı bir denemeyle aynı",
    "same_title_date": "aynı ad ve tarihle kayıtlı bir deneme var",
    "near_title_date": "aynı adla birkaç gün arayla kayıtlı bir deneme var",
}


@dataclass
class DuplicateMatch:
    level: str          # exact | likely
    reason: str         # REASON_LABELS_TR anahtarı
    exam_id: int
    title: str
    exam_date: str      # ISO
    similarity: float   # 0..1 (içerik katmanında; diğerlerinde 1.0)

    def as_details(self) -> dict:
        return {
            "exam_id": self.exam_id,
            "level": self.level,
            "reason": self.reason,
            "reason_label": REASON_LABELS_TR.get(self.reason, self.reason),
            "title": self.title,
            "exam_date": self.exam_date,
            "similarity": round(self.similarity, 3),
        }

    def message(self) -> str:
        head = "Bu deneme zaten kayıtlı" if self.level == LEVEL_EXACT else "Bu deneme kayıtlı olabilir"
        return (
            f"{head}: {REASON_LABELS_TR.get(self.reason, self.reason)} "
            f"(\"{self.title}\", {self.exam_date})."
        )


# ---------------------------------------------------------------------------
# Parmak izleri
# ---------------------------------------------------------------------------


def pdf_sha256(data: bytes | None) -> str | None:
    if not data:
        return None
    return hashlib.sha256(data).hexdigest()


_TR_UPPER = str.maketrans({"İ": "i", "I": "ı", "Ç": "ç", "Ğ": "ğ", "Ö": "ö", "Ş": "ş", "Ü": "ü"})
_NON_ALNUM = re.compile(r"[^0-9a-zçğıöşü]+")


def normalize_title(s: str | None) -> str:
    """Ad karşılaştırması: Türkçe küçük harf, aksan/noktalama/boşluk farkı yok."""
    if not s:
        return ""
    t = s.translate(_TR_UPPER).lower()
    t = unicodedata.normalize("NFKC", t)
    return _NON_ALNUM.sub(" ", t).strip()


def _row_field(row, name: str):
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def answer_signature(rows) -> tuple[tuple[int, str, str], ...]:
    """Soru sırasına göre (no, öğrenci cevabı, sonuç) dizisi.

    Dict (taslak/onay satırı) ve ExamResultQuestion ikisini de kabul eder.
    Soru numarası olmayan satırlar giriş sırasıyla sona dizilir.
    """
    items = []
    for idx, r in enumerate(rows or []):
        no = _row_field(r, "question_no")
        ans = (str(_row_field(r, "student_answer") or "")).strip().upper()
        res = (str(_row_field(r, "result") or "")).strip().lower()
        key = (int(no) if no is not None else 10_000 + idx)
        items.append((key, ans, res))
    items.sort(key=lambda x: x[0])
    return tuple(items)


def similarity(sig_a, sig_b) -> float:
    """Aynı uzunlukta iki imzanın soru bazında örtüşme oranı; uzunluk farklıysa 0."""
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    same = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return same / len(sig_a)


# ---------------------------------------------------------------------------
# Arama
# ---------------------------------------------------------------------------


def _section_value(section) -> str | None:
    if section is None:
        return None
    if isinstance(section, ExamSection):
        return section.value
    try:
        return ExamSection(str(section)).value
    except ValueError:
        return None


def find_by_pdf(
    db: Session, student_id: int, sha: str | None, *, exclude_exam_id: int | None = None
) -> ExamResult | None:
    if not sha:
        return None
    q = db.query(ExamResult).filter(
        ExamResult.student_id == student_id,
        ExamResult.import_pdf_sha256 == sha,
    )
    if exclude_exam_id is not None:
        q = q.filter(ExamResult.id != exclude_exam_id)
    return q.order_by(ExamResult.id.asc()).first()


def find_duplicate(
    db: Session,
    student_id: int,
    *,
    section=None,
    rows=None,
    title: str | None = None,
    exam_date: date | None = None,
    pdf_sha: str | None = None,
    exclude_exam_id: int | None = None,
) -> DuplicateMatch | None:
    """Üç katmanı sırayla dener; en güçlü eşleşmeyi döndürür (exact > likely)."""
    # --- 1. belge
    hit = find_by_pdf(db, student_id, pdf_sha, exclude_exam_id=exclude_exam_id)
    if hit is not None:
        return DuplicateMatch(
            LEVEL_EXACT, "same_file", hit.id, hit.title, hit.exam_date.isoformat(), 1.0
        )

    sec = _section_value(section)
    best: DuplicateMatch | None = None

    # --- 2. içerik
    sig = answer_signature(rows) if rows else ()
    if sig:
        q = (
            db.query(ExamResult)
            .options(selectinload(ExamResult.questions))
            .filter(ExamResult.student_id == student_id)
        )
        if sec is not None:
            q = q.filter(ExamResult.section == ExamSection(sec))
        if exclude_exam_id is not None:
            q = q.filter(ExamResult.id != exclude_exam_id)
        for e in q.all():
            if not e.questions or len(e.questions) != len(sig):
                continue
            ratio = similarity(sig, answer_signature(e.questions))
            if ratio >= 1.0:
                return DuplicateMatch(
                    LEVEL_EXACT, "same_answers", e.id, e.title,
                    e.exam_date.isoformat(), ratio,
                )
            if ratio >= NEAR_ANSWER_RATIO and (best is None or ratio > best.similarity):
                best = DuplicateMatch(
                    LEVEL_LIKELY, "near_answers", e.id, e.title,
                    e.exam_date.isoformat(), ratio,
                )
    if best is not None:
        return best

    # --- 3. ad + tarih
    nt = normalize_title(title)
    if nt and exam_date is not None:
        q = db.query(ExamResult).filter(ExamResult.student_id == student_id)
        if exclude_exam_id is not None:
            q = q.filter(ExamResult.id != exclude_exam_id)
        near: DuplicateMatch | None = None
        for e in q.all():
            if normalize_title(e.title) != nt:
                continue
            gap = abs((e.exam_date - exam_date).days)
            if gap == 0:
                return DuplicateMatch(
                    LEVEL_LIKELY, "same_title_date", e.id, e.title,
                    e.exam_date.isoformat(), 1.0,
                )
            if gap <= NEAR_DATE_DAYS and near is None:
                near = DuplicateMatch(
                    LEVEL_LIKELY, "near_title_date", e.id, e.title,
                    e.exam_date.isoformat(), 1.0,
                )
        if near is not None:
            return near
    return None


def question_count_exams(db: Session, student_id: int) -> int:
    """Soru satırı taşıyan deneme sayısı (tarama betiği/raporlar için)."""
    return (
        db.query(ExamResult.id)
        .join(ExamResultQuestion, ExamResultQuestion.exam_result_id == ExamResult.id)
        .filter(ExamResult.student_id == student_id)
        .distinct()
        .count()
    )
