"""Görev miktarı öğrenme — koçun kendi alışkanlığından (P3, 2026-09-07).

KULLANICI KARARI: "genelde bir koç bir konudan 3 test 2 test şeklinde rutin bir
görevlendirme yapıyor; sistem koçun görev verme alışkanlıklarından öğrenmeli,
miktarı ders bazında öğrenebilir."

Canlı veri bunu doğruluyor — ders bazında görevlerin çoğu aynı sayıda:
  TYT Geometri %72 · TYT Kimya %70 · TYT Fizik %68 · TYT Matematik %58
En sık değer derslerin çoğunda 3.

İKİ KATMAN (veriyle seçildi): aynı koç+ders içinde öğrenciler arası medyan
farkı ölçüldü — gerçek ama küçük (çoğunlukla 1 test, en fazla 2). Bu yüzden
o öğrenci için yeterli veri VARSA öğrenci medyanı, yoksa koçun o dersteki
genel medyanı kullanılır. Hiç veri yoksa 3.

NEDEN MOD (en sık değer): koçun ifadesi "genelde 3 test veririm" — bu ortanca
değil EN SIK verilen sayıdır. Canlı veriyle ölçüldü: mod %63, medyan %60 tam
isabet; ama medyanın battığı derslerde fark 5 kat (TYT Fizik: medyan 1/20,
mod 10/20 — koç 1 ve 3 veriyor, ortanca 2'yi neredeyse hiç vermiyor).
Beraberlikte ortancaya yakın olan seçilir. Ortalama kullanılmaz: tek bir
"40 test" girişi öneriyi kaydırırdı.

Açıklanabilirlik önemli — koça "bu derste genelde 3" diyeceğiz, kara kutu
bir tahmin sunmayacağız.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Book, Task, TaskBookItem, Topic
from app.services import gorev_stats

# Öntanımlı miktar — koçun hiç geçmişi yoksa. Canlı veride derslerin çoğunda
# en sık değer 3.
DEFAULT_QUANTITY = 3

# Kaç kalem geriye bakılır (koçun güncel alışkanlığı; eski alışkanlık kaymış olabilir)
WINDOW = 20

# Öğrenci-özel tipiğe geçmek için gereken en az örnek. Altındaysa koçun o
# dersteki geneli daha güvenilir (tek-iki görevden alışkanlık çıkmaz).
MIN_STUDENT_SAMPLES = 5

# Koçun ders genelini "alışkanlık" saymak için gereken en az örnek.
# CANLI DOĞRULAMADA YAKALANDI (2026-09-07): eşiksiz sürüm 4 kalemden
# "bu derste genelde 12 test" diyordu — tek seferlik büyük bir atama
# alışkanlık sanılıyordu. Yeterli veri yoksa uydurmak yerine varsayılana düş.
MIN_COACH_SAMPLES = 5


@dataclass
class QuantitySuggestion:
    quantity: int
    source: str       # "student" | "coach" | "default"
    sample_size: int
    reason: str       # koça gösterilecek kısa gerekçe


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    # Çift sayıda örnekte alt-orta: "3 mü 4 mü" ikileminde koçu fazla yüklemeyiz.
    return ordered[mid - 1]


def _typical(values: list[int]) -> int:
    """Koçun bu derste TİPİK verdiği sayı = en sık değer (mod).

    Beraberlikte ortancaya en yakın aday, o da eşitse küçük olan seçilir —
    öneri koçu gereğinden fazla yüklememeli.
    """
    if not values:
        return DEFAULT_QUANTITY
    counts = Counter(values)
    top = max(counts.values())
    candidates = [v for v, n in counts.items() if n == top]
    if len(candidates) == 1:
        return candidates[0]
    mid = _median(values)
    return min(candidates, key=lambda v: (abs(v - mid), v))


def _recent_counts(
    db: Session,
    *,
    coach_id: int,
    subject_id: int,
    student_id: int | None = None,
) -> list[int]:
    """Son WINDOW kalemin planlanan sayıları (yeniden eskiye).

    Hem kitaplı hem KAYNAKSIZ (kitapsız ama konuya bağlı) kalemler sayılır —
    koçun alışkanlığı kaynağın varlığından bağımsızdır. Deneme kitapları HARİÇ:
    orada planned_count "kaç deneme" demektir, test sayısıyla karışır.
    """
    booked = (
        db.query(TaskBookItem.planned_count, Task.date, Task.id)
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Book, Book.id == TaskBookItem.book_id)
        .filter(
            Book.teacher_id == coach_id,
            Book.subject_id == subject_id,
            TaskBookItem.planned_count > 0,
            Book.type.notin_(gorev_stats.DENEME_BOOK_TYPES),
        )
    )
    sourceless = (
        db.query(TaskBookItem.planned_count, Task.date, Task.id)
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Topic, Topic.id == TaskBookItem.topic_id)
        .filter(
            Topic.subject_id == subject_id,
            TaskBookItem.book_id.is_(None),
            TaskBookItem.planned_count > 0,
        )
    )
    if student_id is not None:
        booked = booked.filter(Task.student_id == student_id)
        sourceless = sourceless.filter(Task.student_id == student_id)
    else:
        # Koç geneli: kaynaksız kalemlerde kitap yok → koç bağı öğrenci üzerinden
        from app.models import User

        sourceless = sourceless.join(User, User.id == Task.student_id).filter(
            User.teacher_id == coach_id
        )

    rows = (
        booked.union_all(sourceless)
        .order_by(Task.date.desc(), Task.id.desc())
        .limit(WINDOW)
        .all()
    )
    return [int(r[0]) for r in rows]


def learned_quantity(
    db: Session,
    *,
    coach_id: int,
    subject_id: int | None,
    student_id: int | None = None,
) -> QuantitySuggestion:
    """Koçun bu derste tipik olarak verdiği test sayısı + gerekçesi."""
    if not subject_id:
        return QuantitySuggestion(
            quantity=DEFAULT_QUANTITY, source="default", sample_size=0,
            reason="Varsayılan",
        )

    if student_id is not None:
        own = _recent_counts(
            db, coach_id=coach_id, subject_id=subject_id, student_id=student_id
        )
        if len(own) >= MIN_STUDENT_SAMPLES:
            q = _typical(own)
            return QuantitySuggestion(
                quantity=q, source="student", sample_size=len(own),
                reason=f"bu öğrenciye genelde {q}",
            )

    general = _recent_counts(db, coach_id=coach_id, subject_id=subject_id)
    if len(general) >= MIN_COACH_SAMPLES:
        q = _typical(general)
        return QuantitySuggestion(
            quantity=q, source="coach", sample_size=len(general),
            reason=f"bu derste genelde {q}",
        )

    return QuantitySuggestion(
        quantity=DEFAULT_QUANTITY, source="default", sample_size=0,
        reason="Varsayılan",
    )
