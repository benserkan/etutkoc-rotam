"""Rezerv takılma teşhisi — bir öğrencinin neden hâlâ rezerv tuttuğunu açıklar.

SALT-OKUMA. Hiçbir şey commit edilmez (reconcile yalnız DRY-RUN olarak hesaplanır).

Her rezervli (SectionProgress.reserved_count > 0) bölüm için:
  - O rezervi tutan TaskBookItem'leri (görev tarihi/durumu/draft/released) listeler.
  - Her tutucu kalemi SINIFLANDIRIR:
      * TASLAK        → reconcile is_draft=False filtreler → ASLA düşmez (kalıcı kilit)
      * CARİ/GELECEK  → task.date >= cutoff → doğru tutuluyor (henüz ölü değil)
      * ÖLÜ           → task.date < cutoff, yayında, yapılmamış → reconcile DÜŞÜRMELİ
                        ama hiç tetiklenmemiş (yaz/program-arası açığı)
  - Beklenen rezerv (tutucu kalemlerden) ile gerçek reserved_count'u kıyaslar
    → eşit değilse DRIFT (canlı görev yok ama rezerv takılı) işaretler.
  - reconcile_past_reservations DRY-RUN: şimdi cron/yeni-program olsaydı kaç test
    serbest kalırdı, gösterir (commit YOK).

Çalıştırma (prod, lgs-web container içinde):
  python -m scripts.diagnose_elif_reserves --student-id 34
  python -m scripts.diagnose_elif_reserves --name "Elif"
  python -m scripts.diagnose_elif_reserves --all   # sistem geneli sağlık + cron etkisi

NOT: Mevcut diagnose_section_progress_drift.py BAYAT — reservation_released_at'i
hesaba katmaz (carryover/l5m8p1q2p44k öncesi) → released rezervleri 'drift' sanır.
Bu araç release-aware: tutucu = (released değil) AND (görev tamamlanmamış) AND rem>0.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
    TaskStatus,
    User,
    UserRole,
)
from app.models import WeeklyProgram
from app.services.weekly_program_service import (
    get_active_program,
    get_most_recent_program,
)


def _find_student(db, student_id: int | None, name: str | None) -> User | None:
    if student_id is not None:
        s = db.query(User).filter(User.id == student_id).first()
        if s:
            return s
    if name:
        return (
            db.query(User)
            .filter(User.role == UserRole.STUDENT, User.full_name.ilike(f"%{name}%"))
            .order_by(User.id)
            .first()
        )
    return None


def run(student_id: int | None, name: str | None) -> int:
    db = SessionLocal()
    try:
        student = _find_student(db, student_id, name)
        if not student:
            print(f"Öğrenci bulunamadı (id={student_id}, name={name!r}).")
            return 1

        today = date.today()
        this_monday = today - timedelta(days=today.weekday())
        active = get_active_program(db, student_id=student.id, today=today)
        recent = get_most_recent_program(db, student_id=student.id, today=today)
        cutoff = active.start_date if active else this_monday

        print(f"=== REZERV TEŞHİSİ: {student.full_name} (id={student.id}) ===")
        print(f"Bugün={today} · bu Pazartesi={this_monday} · sınıf={student.grade_level} "
              f"mezun={student.is_graduate}")
        if active:
            print(f"AKTİF program: #{active.id} {active.start_date}→{active.end_date}")
        else:
            print("AKTİF program: YOK (bu yüzden cutoff = bu haftanın Pazartesi'si)")
        if recent:
            print(f"En yakın program: #{recent.id} {recent.start_date}→{recent.end_date} "
                  f"(oluşturma={recent.created_at})")
        print(f"reconcile cutoff = {cutoff}  (task.date < cutoff olan yapılmamış görevler ölü sayılır)")
        print()

        # --- Tüm rezervli bölümler ---
        sbs = (
            db.query(StudentBook)
            .options(
                joinedload(StudentBook.book).joinedload(Book.subject),
                joinedload(StudentBook.book).joinedload(Book.sections),
                joinedload(StudentBook.section_progress),
            )
            .filter(StudentBook.student_id == student.id)
            .all()
        )

        total_reserved = 0
        rows: list[tuple] = []  # (subject_name, book_name, book_id, section, sp)
        for sb in sbs:
            sec_by_id = {x.id: x for x in sb.book.sections}
            for sp in sb.section_progress:
                if sp.reserved_count and sp.reserved_count > 0:
                    total_reserved += sp.reserved_count
                    rows.append((
                        sb.book.subject.name if sb.book.subject else "?",
                        sb.book.name, sb.book.id,
                        sec_by_id.get(sp.book_section_id), sp,
                    ))

        if not rows:
            print("Bu öğrencide rezervli bölüm YOK (tüm reserved_count = 0). Temiz.")
            return 0

        print(f"--- REZERVLİ BÖLÜMLER ({len(rows)} bölüm · toplam rezerv {total_reserved}) ---\n")

        dry_release_tests = 0
        dry_release_items = 0
        stuck_dead = 0
        stuck_draft = 0
        held_live = 0
        drift_sections = 0

        for (subj, book_name, book_id, section, sp) in rows:
            sec_label = (getattr(section, "label", None)
                         or getattr(section, "name", None)
                         or f"section#{sp.book_section_id}")
            test_count = getattr(section, "test_count", "?")
            print(f"[{subj}] {book_name}")
            print(f"   Bölüm: {sec_label}  → reserved={sp.reserved_count} "
                  f"completed={sp.completed_count} test_count={test_count}")

            # Bu (book, section)'ı tutan kalemler
            items = (
                db.query(TaskBookItem)
                .join(Task, Task.id == TaskBookItem.task_id)
                .filter(
                    Task.student_id == student.id,
                    TaskBookItem.book_id == book_id,
                    TaskBookItem.book_section_id == sp.book_section_id,
                )
                .options(joinedload(TaskBookItem.task))
                .order_by(Task.date.asc())
                .all()
            )

            expected_reserved = 0
            print(f"   Bu bölümü içeren görev kalemleri ({len(items)}):")
            for it in items:
                t = it.task
                rem = max(0, it.planned_count - it.completed_count)
                released = it.reservation_released_at is not None
                completed_task = t.status == TaskStatus.COMPLETED
                # Tutucu mu? (rezerve hâlâ katkı yapıyor mu)
                holds = (not released) and (not completed_task) and rem > 0
                if holds:
                    expected_reserved += rem
                # sınıflandır
                if t.date < cutoff:
                    when = "GEÇMİŞ"
                elif t.date == today:
                    when = "BUGÜN"
                else:
                    when = "gelecek"
                if holds:
                    if t.is_draft:
                        cls = "TASLAK→kalıcı kilit"
                        stuck_draft += rem
                    elif t.date < cutoff:
                        cls = "ÖLÜ→reconcile düşürmeli"
                        stuck_dead += rem
                        dry_release_tests += rem
                        dry_release_items += 1
                    else:
                        cls = "canlı (doğru tutuluyor)"
                        held_live += rem
                else:
                    cls = ("released" if released
                           else "tamamlandı" if completed_task
                           else "yapılmış/boş")
                print(f"      task#{t.id} {t.date}[{when:7}] draft={t.is_draft} "
                      f"status={getattr(t.status,'value',t.status)} carried={t.carried_at is not None} "
                      f"released={released} planned={it.planned_count} completed={it.completed_count} "
                      f"rem={rem}  → {cls}")

            # Drift kontrolü
            if expected_reserved != sp.reserved_count:
                drift_sections += 1
                print(f"   ⛔ DRIFT: beklenen rezerv (canlı kalemlerden)={expected_reserved} "
                      f"≠ gerçek reserved_count={sp.reserved_count} "
                      f"→ {sp.reserved_count - expected_reserved} kadar 'sahipsiz' rezerv takılı")
            else:
                print(f"   ✓ rezerv canlı kalemlerle tutarlı ({expected_reserved})")
            print()

        # --- reconcile DRY-RUN (gerçek filtre — commit YOK) ---
        dead_q = (
            db.query(TaskBookItem)
            .join(Task, Task.id == TaskBookItem.task_id)
            .filter(
                Task.student_id == student.id,
                Task.date < cutoff,
                Task.status != TaskStatus.COMPLETED,
                Task.is_draft.is_(False),
                TaskBookItem.book_section_id.isnot(None),
                TaskBookItem.reservation_released_at.is_(None),
            )
            .all()
        )
        recon_tests = sum(max(0, it.planned_count - it.completed_count) for it in dead_q)
        recon_items = sum(1 for it in dead_q if max(0, it.planned_count - it.completed_count) > 0)

        print("=== ÖZET ===")
        print(f"Toplam takılı rezerv: {total_reserved} test")
        print(f"  • ÖLÜ (reconcile düşürmeli, hiç tetiklenmemiş): {stuck_dead}")
        print(f"  • TASLAK (kalıcı kilit — reconcile asla düşürmez): {stuck_draft}")
        print(f"  • CANLI (doğru tutuluyor): {held_live}")
        if drift_sections:
            print(f"  • DRIFT'li bölüm sayısı (sahipsiz rezerv): {drift_sections}")
        print()
        print(f"reconcile_past_reservations DRY-RUN (cutoff={cutoff}):")
        print(f"  → ŞU AN cron/yeni-program olsaydı: {recon_tests} test / {recon_items} kalem serbest kalırdı")
        if recon_tests > 0:
            print("  → SONUÇ: Bu rezervler 'ölü'; yalnızca tetik (cron/yeni program/görev-ekle)")
            print("           çalışmadığı için takılı. Günlük cron bunları otomatik düşürür.")
        if stuck_draft > 0:
            print("  → DİKKAT: TASLAK kaynaklı rezerv var → reconcile bunlara DOKUNMAZ;")
            print("            ayrı ele alınmalı (draft yayınla/sil veya draft'ı da reconcile et).")
        if drift_sections > 0:
            print("  → DİKKAT: DRIFT var → reconcile_section_progress ile düzeltilmeli")
            print("            (canlı görev yok ama rezerv takılı — veri tutarsızlığı).")
        return 0
    finally:
        db.close()


def run_all() -> int:
    """Sistem geneli release-aware tarama: kaç öğrencide rezerv var, ölü/taslak/
    canlı kırılımı, gerçek drift (sahipsiz rezerv), ve günlük cron'un ŞU AN ne kadar
    serbest bırakacağı. SALT-OKUMA."""
    db = SessionLocal()
    try:
        today = date.today()
        this_monday = today - timedelta(days=today.weekday())
        print(f"=== SİSTEM GENELİ REZERV SAĞLIĞI === (bugün={today}, bu Pzt={this_monday})\n")

        # Rezervli (reserved_count>0) section'ı olan öğrenciler
        student_ids = [
            r[0] for r in (
                db.query(StudentBook.student_id)
                .join(SectionProgress, SectionProgress.student_book_id == StudentBook.id)
                .filter(SectionProgress.reserved_count > 0)
                .distinct()
                .all()
            )
        ]
        print(f"Rezervli bölümü olan öğrenci sayısı: {len(student_ids)}")

        tot_reserved = tot_dead = tot_draft = tot_live = 0
        tot_drift_sections = 0
        drift_examples: list[str] = []
        cron_release_tests = cron_release_items = 0

        for sid in student_ids:
            active = get_active_program(db, student_id=sid, today=today)
            cutoff = active.start_date if active else this_monday
            sbs = (
                db.query(StudentBook)
                .options(joinedload(StudentBook.section_progress),
                         joinedload(StudentBook.book))
                .filter(StudentBook.student_id == sid)
                .all()
            )
            book_id_by_sb = {sb.id: sb.book_id for sb in sbs}
            sname = None
            for sb in sbs:
                for sp in sb.section_progress:
                    if not sp.reserved_count or sp.reserved_count <= 0:
                        continue
                    tot_reserved += sp.reserved_count
                    book_id = book_id_by_sb[sb.id]
                    items = (
                        db.query(TaskBookItem)
                        .join(Task, Task.id == TaskBookItem.task_id)
                        .filter(
                            Task.student_id == sid,
                            TaskBookItem.book_id == book_id,
                            TaskBookItem.book_section_id == sp.book_section_id,
                        )
                        .options(joinedload(TaskBookItem.task))
                        .all()
                    )
                    expected = 0
                    for it in items:
                        t = it.task
                        rem = max(0, it.planned_count - it.completed_count)
                        if (it.reservation_released_at is None
                                and t.status != TaskStatus.COMPLETED and rem > 0):
                            expected += rem
                            if t.is_draft:
                                tot_draft += rem
                            elif t.date < cutoff:
                                tot_dead += rem
                            else:
                                tot_live += rem
                    if expected != sp.reserved_count:
                        tot_drift_sections += 1
                        if len(drift_examples) < 20:
                            if sname is None:
                                u = db.query(User).filter(User.id == sid).first()
                                sname = u.full_name if u else f"#{sid}"
                            drift_examples.append(
                                f"  - {sname} (id={sid}) {sb.book.name[:30]} sec#{sp.book_section_id}: "
                                f"stored={sp.reserved_count} beklenen={expected} "
                                f"(fark {sp.reserved_count - expected})"
                            )
            # cron dry-run (bu öğrenci için)
            dead = (
                db.query(TaskBookItem)
                .join(Task, Task.id == TaskBookItem.task_id)
                .filter(
                    Task.student_id == sid,
                    Task.date < cutoff,
                    Task.status != TaskStatus.COMPLETED,
                    Task.is_draft.is_(False),
                    TaskBookItem.book_section_id.isnot(None),
                    TaskBookItem.reservation_released_at.is_(None),
                )
                .all()
            )
            for it in dead:
                rem = max(0, it.planned_count - it.completed_count)
                if rem > 0:
                    cron_release_tests += rem
                    cron_release_items += 1

        print(f"Toplam aktif rezerv: {tot_reserved} test")
        print(f"  • ÖLÜ (geçmiş hafta, yapılmamış — reconcile düşürmeli): {tot_dead}")
        print(f"  • TASLAK (kalıcı kilit — reconcile asla düşürmez):       {tot_draft}")
        print(f"  • CANLI (cari/gelecek hafta — doğru tutuluyor):          {tot_live}")
        print(f"  • DRIFT'li bölüm (sahipsiz rezerv — gerçek tutarsızlık): {tot_drift_sections}")
        print()
        print("GÜNLÜK CRON DRY-RUN (her öğrenci cutoff = aktif program / bu Pzt):")
        print(f"  → ŞU AN serbest kalacak: {cron_release_tests} test / {cron_release_items} kalem")
        if drift_examples:
            print(f"\nDRIFT örnekleri ({tot_drift_sections} bölüm, ilk {len(drift_examples)}):")
            print("\n".join(drift_examples))
            print("→ Bunlar günlük cron ile DÜZELMEZ (release-only); reconcile_section_progress gerekir.")
        else:
            print("\n✓ Gerçek drift YOK — tüm aktif rezervler canlı görev kalemleriyle tutarlı.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int, default=None)
    ap.add_argument("--name", type=str, default=None, help="ad filtresi (içerir)")
    ap.add_argument("--all", action="store_true", help="sistem geneli sağlık taraması")
    args = ap.parse_args()
    if args.all:
        raise SystemExit(run_all())
    if args.student_id is None and not args.name:
        ap.error("--student-id, --name veya --all gerekli")
    raise SystemExit(run(student_id=args.student_id, name=args.name))
