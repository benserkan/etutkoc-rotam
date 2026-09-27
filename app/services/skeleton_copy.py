"""İskeleti başka öğrencilere kopyala (2026-09-27, kurum toplu kurulumu 3/4).

Kurumda aynı sınıftaki öğrencilerin ders yerleşimi çoğunlukla aynıdır; koç bir
öğrencinin dönem iskeletini seçili öğrencilere çoğaltır. İskelet HAFTA GÜNÜNE
bağlı satırlardır; çipler/hayaletler her öğrencinin KENDİ ilerlemesinden
hesaplandığı için satırları kopyalamak yeterlidir.

Kurallar:
- Yalnız aynı koçun öğrencileri (çağıran sahipliği doğrular).
- `day_capacity` KOPYALANMAZ — gün kapasitesi her öğrencinin kendi geçmişinden
  öğrenilir (topic_spread).
- Satırın kitabı hedef öğrencide yoksa: `assign_missing_books=True` → kitap
  öğrenciye atanır (book_assign); False → satır kitapsız (serbest metin) kopyalanır,
  etiketi kitap adı olur (öneri "etkinlik olarak yaz"a düşer, program bozulmaz).
- mode "new": `valid_from`dan başlayan YENİ dönem; hedefte aynı başlangıçlı
  dönem varsa onun satırları değiştirilir. mode "replace": hedefin BUGÜN geçerli
  döneminin satırları değiştirilir (dönemi yoksa başlangıçsız dönem açılır).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models import Book, StudentBook, User
from app.models.weekly_skeleton import WeeklySkeleton
from app.services import skeleton_suggest as sk
from app.services.book_assign import assign_books_to_student

COPY_MODES = ("new", "replace")


@dataclass
class TargetPlan:
    student: User
    missing_book_ids: list[int] = field(default_factory=list)
    period_count: int = 0
    replaced_name: str | None = None      # değişecek dönemin adı (varsa)
    replaced_slot_count: int = 0
    same_start: bool = False              # new modunda aynı başlangıçlı dönem var


def _source_book_ids(src: WeeklySkeleton) -> set[int]:
    out: set[int] = set()
    for s in src.slots:
        if s.book_id:
            out.add(s.book_id)
        if s.second_book_id:
            out.add(s.second_book_id)
    return out


def plan_targets(
    db: Session, *, source: WeeklySkeleton, targets: list[User], mode: str,
    valid_from: date | None,
) -> list[TargetPlan]:
    books = _source_book_ids(source)
    active: dict[int, set[int]] = {}
    if targets and books:
        for sid, bid in (
            db.query(StudentBook.student_id, StudentBook.book_id)
            .filter(StudentBook.student_id.in_([t.id for t in targets]),
                    StudentBook.book_id.in_(books), StudentBook.archived_at.is_(None))
        ):
            active.setdefault(sid, set()).add(bid)
    plans: list[TargetPlan] = []
    for t in targets:
        skels = sk.list_skeletons(db, t.id)
        p = TargetPlan(student=t, period_count=len(skels),
                       missing_book_ids=sorted(books - active.get(t.id, set())))
        if mode == "new":
            same = next((x for x in skels if (x.valid_from or date.min) == (valid_from or date.min)), None)
            if same is not None:
                p.same_start = True
                p.replaced_name, p.replaced_slot_count = same.name, len(same.slots)
        else:
            cur = sk.get_skeleton(db, t.id)
            if cur is not None:
                p.replaced_name, p.replaced_slot_count = cur.name, len(cur.slots)
        plans.append(p)
    return plans


def _slot_dicts(source: WeeklySkeleton, missing: set[int], names: dict[int, str]) -> list[dict]:
    out = []
    for i, s in enumerate(source.slots):
        book_id, label, mode_, scope = s.book_id, s.label, s.routine_mode, s.routine_scope
        if book_id and book_id in missing:
            label = label or names.get(book_id)
            book_id, mode_, scope = None, None, None
        second = s.second_book_id if s.second_book_id not in missing else None
        out.append(dict(
            weekday=s.weekday, period=s.period, subject_id=s.subject_id, position=s.position if s.position is not None else i,
            is_routine=s.is_routine, default_count=s.default_count, book_id=book_id, label=label,
            routine_mode=mode_, is_anchor=s.is_anchor, routine_scope=scope, second_book_id=second,
        ))
    return out


def apply_copy(
    db: Session, *, source: WeeklySkeleton, coach_id: int, plans: list[TargetPlan], mode: str,
    valid_from: date | None, name: str | None, assign_missing_books: bool,
) -> list[dict]:
    """Planı uygular (commit ETMEZ). Öğrenci başına sonuç sözlüğü döner."""
    all_missing = {b for p in plans for b in p.missing_book_ids}
    book_objs = {
        b.id: b for b in db.query(Book).options(joinedload(Book.sections))
        .filter(Book.id.in_(all_missing or {0}))
    }
    names = {bid: b.name for bid, b in book_objs.items()}
    results = []
    for p in plans:
        assigned = 0
        missing = set(p.missing_book_ids)
        if assign_missing_books and missing:
            out = assign_books_to_student(db, p.student.id, [book_objs[b] for b in missing if b in book_objs])
            assigned = len(out.created) + len(out.unarchived_ids)
            missing = set()
        slots = _slot_dicts(source, missing, names)
        target_sk = None
        if mode == "new":
            skels = sk.list_skeletons(db, p.student.id)
            target_sk = next((x for x in skels if (x.valid_from or date.min) == (valid_from or date.min)), None)
            if target_sk is None:
                target_sk = sk.create_period(
                    db, student=p.student, coach_id=coach_id, valid_from=valid_from,
                    name=name or source.name,
                )
        target_sk = sk.replace_slots(
            db, student=p.student, coach_id=coach_id, slots=slots,
            name=name if mode == "new" else None, skeleton=target_sk,
        )
        results.append({
            "student_id": p.student.id,
            "full_name": p.student.full_name,
            "skeleton_id": target_sk.id,
            "slot_count": len(slots),
            "books_assigned": assigned,
            "slots_without_book": sum(1 for s in source.slots if s.book_id and s.book_id in missing),
        })
    return results
