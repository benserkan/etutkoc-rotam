"""'{Ders} henüz başlanmadı' (subject_untouched) uyarısı teşhis aracı.

analytics.generate_warnings içindeki subject_untouched_* uyarısının bir öğrenci
için neden tetiklendiğini SATIR SATIR açıklar. Salt-okuma.

Uyarı koşulu (analytics.py):
    total > 0
    AND last_completed_at IS NULL      (o derste Task.completed_at YOK)
    AND reserved > 0                    (SectionProgress.reserved_count toplamı)
    AND subject_id in due_subject_ids   (o derste date < today olan görev VAR)

Çalıştırma:
  python -m scripts.diagnose_subject_untouched --student-id 11
  python -m scripts.diagnose_subject_untouched --student-id 11 --subject "Türk Dili"
"""
from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    User,
)
from app.services import analytics


def run(student_id: int, subject_filter: str | None = None) -> int:
    db = SessionLocal()
    try:
        student = db.query(User).filter(User.id == student_id).first()
        if not student:
            print(f"Öğrenci #{student_id} bulunamadı.")
            return 1
        today = date.today()
        print(f"=== Öğrenci: {student.full_name} (id={student.id}) · bugün={today} ===\n")

        # 1) subject_breakdown çıktısı (uyarının beslendiği kaynak)
        breakdown = analytics.subject_breakdown(db, student.id)

        # 2) due_subject_ids — uyarı kodundaki sorgunun BİREBİR aynısı
        #    (DİKKAT: is_draft FİLTRESİ YOK)
        due_rows = (
            db.query(Book.subject_id, Task.is_draft)
            .join(TaskBookItem, TaskBookItem.book_id == Book.id)
            .join(Task, Task.id == TaskBookItem.task_id)
            .filter(
                Task.student_id == student.id,
                Task.date < today,
                Book.subject_id.isnot(None),
            )
            .distinct()
            .all()
        )
        due_subject_ids = {r[0] for r in due_rows}
        due_draft_only = {  # SADECE draft past-task'i olan dersler
            sid for sid in due_subject_ids
            if all(is_draft for (s, is_draft) in due_rows if s == sid)
        }

        print("--- DERS KIRILIMI (subject_breakdown) ---")
        print(f"{'ders':32} {'total':>6} {'compl':>6} {'rezerv':>6} "
              f"{'lastDone(Task)':>16} {'pastGörev':>9}")
        flagged: list[dict] = []
        for s in breakdown:
            if subject_filter and subject_filter.lower() not in s["name"].lower():
                continue
            last = s["last_completed_at"]
            last_s = last.date().isoformat() if last else "—(None)"
            in_due = s["subject_id"] in due_subject_ids
            fires = (
                s["total"] > 0
                and s["last_completed_at"] is None
                and s["reserved"] > 0
                and s["subject_id"] in due_subject_ids
            )
            mark = " ⚠️ UYARI" if fires else ""
            print(f"{s['name'][:32]:32} {s['total']:>6} {s['completed']:>6} "
                  f"{s['reserved']:>6} {last_s:>16} {str(in_due):>9}{mark}")
            if fires:
                flagged.append(s)

        if not flagged:
            print("\nBu öğrenci için subject_untouched uyarısı YOK.")
            if subject_filter:
                print(f"(filtre: '{subject_filter}')")
            return 0

        # 3) Tetiklenen her ders için DERİN inceleme
        for s in flagged:
            sid = s["subject_id"]
            print(f"\n\n=== ⚠️ '{s['name']}' henüz başlanmadı — DERİN İNCELEME ===")
            subj = db.query(Subject).filter(Subject.id == sid).first()
            print(f"Subject id={sid} · müfredat={getattr(subj, 'curriculum_model', '?')} "
                  f"· teacher_id={getattr(subj, 'teacher_id', '?')}")

            # Aynı isimli BAŞKA subject kaydı var mı? (curriculum çoğullaması)
            dupes = (
                db.query(Subject)
                .filter(Subject.name == s["name"], Subject.id != sid)
                .all()
            )
            if dupes:
                print(f"  ! Aynı isimli {len(dupes)} BAŞKA subject kaydı var: "
                      + ", ".join(f"#{d.id}({getattr(d,'curriculum_model','?')})" for d in dupes))

            # StudentBook + section_progress dökümü
            sbs = (
                db.query(StudentBook)
                .options(
                    joinedload(StudentBook.book).joinedload(Book.subject),
                    joinedload(StudentBook.book).joinedload(Book.sections),
                    joinedload(StudentBook.section_progress),
                )
                .join(Book, Book.id == StudentBook.book_id)
                .filter(StudentBook.student_id == student.id, Book.subject_id == sid)
                .all()
            )
            print(f"\n  Kitaplar ({len(sbs)}):")
            for sb in sbs:
                print(f"   • {sb.book.name} (book_id={sb.book.id}, "
                      f"type={getattr(sb.book.type, 'value', sb.book.type)}) "
                      f"total={sb.total_tests} reserved={sb.reserved_tests} "
                      f"completed={sb.completed_tests}")
                for sp in sb.section_progress:
                    if sp.reserved_count or sp.completed_count:
                        sec = next((x for x in sb.book.sections if x.id == sp.book_section_id), None)
                        print(f"       - {sec.label if sec else sp.book_section_id}: "
                              f"reserved_count={sp.reserved_count} "
                              f"completed_count={sp.completed_count}")

            # Bu derse ait TÜM görevler (taslak dahil)
            tasks = (
                db.query(Task)
                .options(joinedload(Task.book_items))
                .join(TaskBookItem, TaskBookItem.task_id == Task.id)
                .join(Book, Book.id == TaskBookItem.book_id)
                .filter(Task.student_id == student.id, Book.subject_id == sid)
                .distinct()
                .order_by(Task.date)
                .all()
            )
            print(f"\n  Görevler ({len(tasks)}):")
            for t in tasks:
                past = "GEÇMİŞ" if t.date < today else ("BUGÜN" if t.date == today else "gelecek")
                items = [bi for bi in t.book_items if bi.book_id and
                         db.query(Book.subject_id).filter(Book.id == bi.book_id).scalar() == sid]
                planned = sum(bi.planned_count for bi in items)
                completed = sum(bi.completed_count for bi in items)
                print(f"   • {t.date} [{past:7}] draft={t.is_draft} "
                      f"status={getattr(t.status,'value',t.status)} "
                      f"completed_at={t.completed_at} "
                      f"planned={planned} completed={completed} title={t.title!r}")

            # last_completed_at sorgusunun BİREBİR tekrarı
            last_q = (
                db.query(func.max(Task.completed_at))
                .join(TaskBookItem, TaskBookItem.task_id == Task.id)
                .join(Book, Book.id == TaskBookItem.book_id)
                .filter(
                    Task.student_id == student.id,
                    Book.subject_id == sid,
                    Task.completed_at.isnot(None),
                )
                .scalar()
            )
            print(f"\n  TANI:")
            print(f"   - reserved (SectionProgress toplamı) = {s['reserved']}  → {'>0 ✓' if s['reserved']>0 else '0'}")
            print(f"   - completed (SectionProgress toplamı) = {s['completed']}")
            print(f"   - last_completed_at (max Task.completed_at) = {last_q}")
            if s["completed"] > 0 and last_q is None:
                print("   ⛔ ÇELİŞKİ: SectionProgress completed_count > 0 AMA Task.completed_at YOK")
                print("      → completed_count baz-çizgi (geçmiş yıl ayıklama) / drift kaynaklı olabilir;")
                print("        uyarı 'hiçbir test tamamlanmamış' der ama aslında tamamlanmış.")
            if sid in due_draft_only:
                print("   ⛔ due_subject_ids YALNIZ DRAFT görevden geliyor (yayınlanmamış program)")
                print("      → uyarı taslak göreve dayanıyor; öğrenci için henüz program yok.")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int, required=True)
    ap.add_argument("--subject", type=str, default=None, help="ders adı filtresi (içerir)")
    args = ap.parse_args()
    raise SystemExit(run(student_id=args.student_id, subject_filter=args.subject))
