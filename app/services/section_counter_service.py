"""SectionProgress sayaç onarımı — TEK MERKEZ (script + koç UI ortak).

`SectionProgress.reserved_count` / `completed_count` zamanla gerçek görev
verisinden sapabilir ("sayaç uyumsuzluğu"): bir görev doğrudan silindiğinde,
elle SQL müdahalesi yapıldığında veya geçmişte düzeltilmiş bir rezerv bug'ı
nedeniyle. Sapma olunca koç kitap ızgarasında "sayaç uyumsuz" rozetini görür
ve kapasite yanlış hesaplanır (ölü rezerv yüzünden yeni test atanamaz).

2026-09-03'e kadar onarım YALNIZ `scripts/reconcile_section_progress.py` ile,
yani sunucuya SSH ile yapılabiliyordu — koç panelde uyarıyı görüyor ama
düzeltemiyordu. Hesap mantığı buraya taşındı; script ve koç ucu aynı kuralları
kullanır.

KURALLAR (release-aware — `diagnose_elif_reserves` ile aynı "tutucu" tanımı):
  expected_reserved  = Σ max(0, planned − completed)  · YALNIZ
                       reservation_released_at IS NULL olan + görevi COMPLETED
                       olmayan kalemler (TASLAK DAHİL: taslak da kapasite kilitler)
  expected_completed = max(kayıtlı completed, Σ kalem completed)
                       → kayıtlı BÜYÜKSE korunur: koçun "öğrenci zaten çözmüştü"
                         baseline girişi görev kalemi üretmez, silinmemeli.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
    TaskStatus,
)


@dataclass
class CounterFix:
    student_id: int
    student_book_id: int
    section_id: int
    section_label: str
    book_name: str
    old_reserved: int
    new_reserved: int
    old_completed: int
    new_completed: int


def compute_fixes(
    db: Session,
    *,
    student_id: int | None = None,
    student_book_id: int | None = None,
) -> list[CounterFix]:
    """Gerçek görev verisinden beklenen sayaçları hesapla; sapanları döndür.

    Hiçbir şey yazmaz — çağıran `apply_fixes` ile uygular.
    """
    q = db.query(StudentBook).options(
        joinedload(StudentBook.book).joinedload(Book.sections),
        joinedload(StudentBook.section_progress),
    )
    if student_id is not None:
        q = q.filter(StudentBook.student_id == student_id)
    if student_book_id is not None:
        q = q.filter(StudentBook.id == student_book_id)
    sbs = q.all()
    if not sbs:
        return []

    section_ids: set[int] = set()
    for sb in sbs:
        for sec in sb.book.sections:
            section_ids.add(sec.id)
    if not section_ids:
        return []

    agg: dict[tuple[int, int], dict[str, int]] = defaultdict(
        lambda: {"holding": 0, "completed": 0}
    )
    rows = (
        db.query(
            Task.student_id,
            TaskBookItem.book_section_id,
            TaskBookItem.planned_count,
            TaskBookItem.completed_count,
            TaskBookItem.reservation_released_at,
            Task.status,
        )
        .join(Task, TaskBookItem.task_id == Task.id)
        .filter(TaskBookItem.book_section_id.in_(section_ids))
        .all()
    )
    for sid, sec_id, planned_n, completed_n, released_at, tstatus in rows:
        key = (sid, sec_id)
        agg[key]["completed"] += completed_n or 0
        if released_at is None and tstatus != TaskStatus.COMPLETED:
            agg[key]["holding"] += max(0, (planned_n or 0) - (completed_n or 0))

    out: list[CounterFix] = []
    for sb in sbs:
        labels = {s.id: s.label for s in sb.book.sections}
        for sp in sb.section_progress:
            key = (sb.student_id, sp.book_section_id)
            exp_reserved = agg[key]["holding"]
            exp_completed = max(sp.completed_count, agg[key]["completed"])
            if sp.reserved_count == exp_reserved and sp.completed_count == exp_completed:
                continue
            out.append(
                CounterFix(
                    student_id=sb.student_id,
                    student_book_id=sb.id,
                    section_id=sp.book_section_id,
                    section_label=labels.get(sp.book_section_id, f"#{sp.book_section_id}"),
                    book_name=sb.book.name,
                    old_reserved=sp.reserved_count,
                    new_reserved=exp_reserved,
                    old_completed=sp.completed_count,
                    new_completed=exp_completed,
                )
            )
    return out


def apply_fixes(db: Session, fixes: list[CounterFix]) -> int:
    """Hesaplanan düzeltmeleri yaz (commit ÇAĞIRANA ait)."""
    if not fixes:
        return 0
    n = 0
    for f in fixes:
        sp = (
            db.query(SectionProgress)
            .filter(
                SectionProgress.student_book_id == f.student_book_id,
                SectionProgress.book_section_id == f.section_id,
            )
            .first()
        )
        if sp is None:
            continue
        sp.reserved_count = f.new_reserved
        sp.completed_count = f.new_completed
        n += 1
    db.flush()
    return n


def reconcile_student_book(
    db: Session, *, student_book_id: int
) -> dict:
    """Tek kitap için sayaçları onar → {fixed, details}. commit ÇAĞIRANDA."""
    fixes = compute_fixes(db, student_book_id=student_book_id)
    fixed = apply_fixes(db, fixes)
    return {
        "fixed": fixed,
        "details": [
            {
                "section": f.section_label,
                "reserved": [f.old_reserved, f.new_reserved],
                "completed": [f.old_completed, f.new_completed],
            }
            for f in fixes
        ],
    }
