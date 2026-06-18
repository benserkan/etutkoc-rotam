"""Ölü rezerv telafisi (carryover) smoke — Part A reconcile + Part B candidates.

Senaryo: koç geçen hafta test rezerv etti, öğrenci yapmadı (hasta), bu hafta
yeniden atamak istiyor. reconcile_past_reservations geçmiş haftanın yapılmamış
rezervini serbest bırakmalı (kapasite geri dönsün); idempotent; tamamlanan kısım
korunsun; bugün/gelecek görevler dokunulmasın; serbest bırakılan görev silinince
çift-iade olmasın; create_program tetiklesin.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    BookType,
    CoachWorkBlock,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
    WeeklyProgram,
)
from app.services import task_service as ts
from app.services import weekly_program_service as wps
from app.services.security import hash_password

PFX = f"resv{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def _reserved(db, sp_id) -> int:
    return db.get(SectionProgress, sp_id).reserved_count


def main() -> int:
    print(f"\n=== reservation carryover smoke — {PFX} ===\n")
    today = date.today()
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="T", role=UserRole.TEACHER, is_active=True, plan="solo_free")
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="S", role=UserRole.STUDENT, is_active=True, grade_level=10)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        subj = Subject(name=f"{PFX} Ders", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Konu", order=0, subject_id=subj.id); db.add(topic); db.flush()
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book); db.flush()
        # sec_a: 3 test (tam kapasite geçmiş rezervle dolu) ; sec_b: 10 test (kısmi)
        sec_a = BookSection(book_id=book.id, label="Bölüm A", test_count=3, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="Bölüm B", test_count=10, order=1, topic_id=topic.id)
        sec_c = BookSection(book_id=book.id, label="Bölüm C", test_count=5, order=2, topic_id=topic.id)
        db.add_all([sec_a, sec_b, sec_c]); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id); db.add(sb); db.flush()
        sp_a = SectionProgress(student_book_id=sb.id, book_section_id=sec_a.id, reserved_count=3, completed_count=0)
        sp_b = SectionProgress(student_book_id=sb.id, book_section_id=sec_b.id, reserved_count=5, completed_count=2)
        # sec_c: t_today(2) + t_block(1) = 3 rezerv
        sp_c = SectionProgress(student_book_id=sb.id, book_section_id=sec_c.id, reserved_count=3, completed_count=0)
        db.add_all([sp_a, sp_b, sp_c]); db.flush()

        # GEÇMİŞ görev (geçen hafta, PENDING) — sec_a'dan 3 test, hiç yapılmadı (HASTA)
        t_past = Task(student_id=student.id, date=today - timedelta(days=5), type=TaskType.TEST,
                      title="Geçen hafta math", status=TaskStatus.PENDING, order=0, is_draft=False)
        db.add(t_past); db.flush()
        i_past = TaskBookItem(task_id=t_past.id, book_id=book.id, book_section_id=sec_a.id,
                              planned_count=3, completed_count=0)
        db.add(i_past)
        # GEÇMİŞ kısmi görev (PARTIAL) — sec_b planned 5, completed 2 → 3 serbest kalmalı
        t_partial = Task(student_id=student.id, date=today - timedelta(days=5), type=TaskType.TEST,
                         title="Geçen hafta kısmi", status=TaskStatus.PARTIAL, order=1, is_draft=False)
        db.add(t_partial); db.flush()
        i_partial = TaskBookItem(task_id=t_partial.id, book_id=book.id, book_section_id=sec_b.id,
                                 planned_count=5, completed_count=2)
        db.add(i_partial)
        # BUGÜNKÜ görev — sec_c'den 2 (DOKUNULMAMALI)
        t_today = Task(student_id=student.id, date=today, type=TaskType.TEST,
                       title="Bugün", status=TaskStatus.PENDING, order=0, is_draft=False)
        db.add(t_today); db.flush()
        i_today = TaskBookItem(task_id=t_today.id, book_id=book.id, book_section_id=sec_c.id,
                               planned_count=2, completed_count=0)
        db.add(i_today)
        # GEÇMİŞ BLOK görevi (work_block) — section'lı ama blok → LİSTEDE OLMALI
        blk = CoachWorkBlock(coach_id=teacher.id, student_id=student.id,
                             title="Mat Blok", total_count=10, unit="test", status="active")
        db.add(blk); db.flush()
        t_block = Task(student_id=student.id, date=today - timedelta(days=5), type=TaskType.TEST,
                       title="Mat·Blok", status=TaskStatus.PENDING, order=2, is_draft=False,
                       work_block_id=blk.id)
        db.add(t_block); db.flush()
        db.add(TaskBookItem(task_id=t_block.id, book_id=book.id, book_section_id=sec_c.id,
                            planned_count=1, completed_count=0))
        # GEÇMİŞ ETKİNLİK görevi (video, kalemsiz) → LİSTEDE OLMALI
        t_video = Task(student_id=student.id, date=today - timedelta(days=5), type=TaskType.VIDEO,
                       title="Konu videosu", status=TaskStatus.PENDING, order=3, is_draft=False)
        db.add(t_video); db.flush()
        db.commit()
        ids = {"student": student.id, "teacher_obj": teacher.id, "book": book.id,
               "sec_a": sec_a.id, "sec_b": sec_b.id, "sec_c": sec_c.id,
               "sp_a": sp_a.id, "sp_b": sp_b.id, "sp_c": sp_c.id,
               "t_past": t_past.id, "t_partial": t_partial.id, "t_today": t_today.id,
               "i_past": i_past.id, "blk": blk.id, "t_block": t_block.id, "t_video": t_video.id}

    try:
        with SessionLocal() as db:
            cutoff = today  # bugünden öncekiler ölü
            # Başlangıç: sec_a tam dolu (3/3 rezerv) → yeni atanamaz
            check("0. başlangıç sec_a reserved=3 (tam kapasite)", _reserved(db, ids["sp_a"]) == 3)

            res = ts.reconcile_past_reservations(db, student_id=ids["student"], cutoff_date=cutoff)
            db.commit()
            check("1. reconcile serbest bıraktı (3 + 3 + 1 blok = 7 test)",
                  res["released_tests"] == 7, f"got {res}")
            check("2. sec_a reserved → 0 (geçen hafta tam serbest)", _reserved(db, ids["sp_a"]) == 0)
            check("3. sec_b reserved → 2 (5'ten 3 serbest, completed 2 korundu)",
                  _reserved(db, ids["sp_b"]) == 2, f"got {_reserved(db, ids['sp_b'])}")
            check("4. sec_c reserved → 2 DEĞİŞMEDİ (bugünkü görev)", _reserved(db, ids["sp_c"]) == 2)
            it = db.get(TaskBookItem, ids["i_past"])
            check("5. geçmiş kalem reservation_released_at işaretlendi",
                  it.reservation_released_at is not None)
            # planned/completed geçmiş kaydı korundu
            check("6. geçmiş kalem planned=3/completed=0 KORUNDU (veri kaybı yok)",
                  it.planned_count == 3 and it.completed_count == 0)

            # idempotent
            res2 = ts.reconcile_past_reservations(db, student_id=ids["student"], cutoff_date=cutoff)
            db.commit()
            check("7. ikinci reconcile → 0 (idempotent)", res2["released_tests"] == 0, f"got {res2}")
            check("8. sec_a hâlâ 0 (çift serbest yok)", _reserved(db, ids["sp_a"]) == 0)

            # artık yeniden atanabilir: sec_a'ya 3 rezerv başarılı
            ts.reserve_item(db, student_id=ids["student"], book_id=ids["book"],
                            section_id=ids["sec_a"], count=3)
            db.commit()
            check("9. reconcile sonrası sec_a yeniden atanabilir (reserve 3 OK)",
                  _reserved(db, ids["sp_a"]) == 3)

            # carryover candidates (GÖREV düzeyi) — YENİ FİLTRE: düz test görevleri
            # LİSTEDE YOK (rezerv iade edildi, kitapta çözülmedi görünür); yalnız
            # blok + etkinlik (video/özet/...) + kitapsız deneme listelenir.
            cands = ts.list_carryover_candidates(db, student_id=ids["student"], cutoff_date=cutoff)
            task_ids = {c["task_id"] for c in cands}
            check("10. düz TEST görevleri (t_past + t_partial) listede YOK (rezerv iade edildi)",
                  ids["t_past"] not in task_ids and ids["t_partial"] not in task_ids, f"got {task_ids}")
            check("11. BLOK görevi (t_block) listede VAR",
                  ids["t_block"] in task_ids, f"got {task_ids}")
            check("11a. ETKİNLİK görevi (t_video) listede VAR",
                  ids["t_video"] in task_ids, f"got {task_ids}")
            check("11e. bugünkü görev listede YOK (geçmiş değil)", ids["t_today"] not in task_ids)
            # browse modu (include_plain_tests=True): düz test görevleri DE listelenir
            browse = ts.list_carryover_candidates(
                db, student_id=ids["student"], cutoff_date=cutoff, include_plain_tests=True)
            btids = {c["task_id"] for c in browse}
            check("11g. browse modu: düz TEST görevleri (t_past+t_partial) DE listede (bilgi amaçlı)",
                  ids["t_past"] in btids and ids["t_partial"] in btids
                  and ids["t_block"] in btids and ids["t_video"] in btids, f"got {btids}")

            # since_date kapsamı: today-3'ten itibaren → today-5 görevleri DIŞARIDA
            # (geçen hafta sınırı), ama kapasiteleri yine serbest (reconcile tüm geçmiş).
            scoped = ts.list_carryover_candidates(
                db, student_id=ids["student"], cutoff_date=cutoff,
                since_date=today - timedelta(days=3))
            check("11b. since_date=today-3 → today-5 görevleri listede YOK (geçen hafta sınırı)",
                  len(scoped) == 0, f"got {len(scoped)}")
            check("11c. ama kapasiteleri yine serbest (reconcile tüm geçmiş): sec_a reserved hâlâ 0/3 atanabilir",
                  db.get(SectionProgress, ids["sp_a"]).reserved_count == 3)  # test 9'da yeniden atanmıştı

            # carried işareti: t_block'u taşınmış işaretle → listeden düşer
            tb = db.get(Task, ids["t_block"])
            ts.mark_task_carried(db, tb); db.commit()
            cands2 = ts.list_carryover_candidates(db, student_id=ids["student"], cutoff_date=cutoff)
            check("11d. mark_task_carried sonrası t_block listeden DÜŞTÜ",
                  ids["t_block"] not in {c["task_id"] for c in cands2}, "carried görünmemeli")
            # geri-al: carried_at temizle → tekrar listede
            tb.carried_at = None; db.commit()
            cands3 = ts.list_carryover_candidates(db, student_id=ids["student"], cutoff_date=cutoff)
            check("11f. carried_at temizlenince t_block listeye GERİ döndü (geri-al)",
                  ids["t_block"] in {c["task_id"] for c in cands3})

            # çift-iade koruması: serbest bırakılmış geçmiş görevi sil → reserved bozulmasın
            # (sec_a şu an 3 = yeniden atanan reserve; geçmiş görevi silmek bunu düşürmemeli)
            past_items = db.query(TaskBookItem).filter(
                TaskBookItem.task_id == ids["t_past"]).all()
            ts.release_task_items(db, ids["student"], past_items)
            db.commit()
            check("12. serbest bırakılmış geçmiş görev silinince sec_a reserved KORUNDU (3, çift-iade yok)",
                  _reserved(db, ids["sp_a"]) == 3, f"got {_reserved(db, ids['sp_a'])}")
    finally:
        with SessionLocal() as db:
            tids = [ids["t_past"], ids["t_partial"], ids["t_today"],
                    ids.get("t_block"), ids.get("t_video")]
            tids = [t for t in tids if t]
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            if ids.get("blk"):
                db.execute(sa_delete(CoachWorkBlock).where(CoachWorkBlock.id == ids["blk"]))
            db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id == ids["student"]))
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.book_section_id.in_([ids["sec_a"], ids["sec_b"], ids["sec_c"]])))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.id.in_([ids["sec_a"], ids["sec_b"], ids["sec_c"]])))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id.in_(
                db.query(Subject.id).filter(Subject.teacher_id == ids["teacher_obj"]).scalar_subquery())))
            db.execute(sa_delete(Subject).where(Subject.teacher_id == ids["teacher_obj"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher_obj"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
