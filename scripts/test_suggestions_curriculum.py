"""Öneri motoru müfredat-öncelik smoke'u.

Kullanıcı şikâyeti (2026-07-13): öğrenci müfredatın başındayken (örn. Matematik
"Temel Kavramlar") öneri sistemi çok ilerideki konuları öneriyordu. Yeni davranış:
  - Aday havuzu + skorlama müfredat frontier'ına (Topic order) bağlı.
  - rank 0 (sıradaki konu) en üstte; başlanan konuya bitirme bonusu.
  - Müfredatta çok ileride (rank >= 3) + o güne hiç desenli değil → önerilmez;
    öğretmen deseni (geçmişte o güne atamış) varsa düşük skorla kalır.
  - Hiç SectionProgress kaydı olmayan yeni kitap bölümleri de öneriye girer
    (eski _progress_map bug'ı: hiç rezerv edilmemiş kitap görünmezdi).
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
)
from app.services.security import hash_password
from app.services.suggestions import build_student_model, suggest_for_date

PFX = f"sugcur{secrets.token_hex(3)}"
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


def main() -> int:
    print(f"\n=== suggestions curriculum smoke — {PFX} ===\n")
    today = date.today()
    # Hedef gün: gelecek Pazartesi (dow sabit — pattern testinde aynı dow kullanılır)
    target = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="T", role=UserRole.TEACHER, is_active=True, plan="solo_free")
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="S", role=UserRole.STUDENT, is_active=True, grade_level=10)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        subj = Subject(name=f"{PFX} Matematik", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topics = []
        for i in range(1, 6):
            t = Topic(name=f"Konu {i}", order=i, subject_id=subj.id)
            db.add(t); topics.append(t)
        db.flush()
        book = Book(name=f"{PFX} Soru Bankası", subject_id=subj.id,
                    type=BookType.SORU_BANKASI, teacher_id=teacher.id)
        db.add(book); db.flush()
        secs = []
        for i, t in enumerate(topics, start=1):
            s = BookSection(book_id=book.id, label=f"Bölüm {i}", test_count=20,
                            order=i, topic_id=t.id)
            db.add(s); secs.append(s)
        # Konuya eşlenmemiş ekstra bölüm (nötr davranmalı)
        s_free = BookSection(book_id=book.id, label="Karma Testler", test_count=20,
                             order=99, topic_id=None)
        db.add(s_free); db.flush()
        db.add(StudentBook(student_id=student.id, book_id=book.id))
        db.commit()
        ids = {
            "teacher": teacher.id, "student": student.id, "subj": subj.id,
            "book": book.id,
            "secs": [s.id for s in secs], "s_free": s_free.id,
            "topics": [t.id for t in topics],
        }

    try:
        with SessionLocal() as db:
            sid = ids["student"]
            sec_ids = ids["secs"]

            # --- 1) Sıfır geçmiş + sıfır SectionProgress: frontier yine önerilir ---
            model = build_student_model(db, sid)
            sugg = suggest_for_date(db, sid, target, model=model, max_suggestions=10)
            check("1a. yeni öğrenci/yeni kitap: öneri listesi BOŞ DEĞİL (frontier havuzu)",
                  len(sugg) > 0, "öneri yok")
            by_sec = {s.section_id: s for s in sugg}
            top = sugg[0] if sugg else None
            check("1b. en üst öneri müfredatın İLK konusu (Bölüm 1)",
                  top is not None and top.section_id == sec_ids[0],
                  f"top={getattr(top, 'section_label', None)}")
            check("1c. en üst öneride 'Müfredatta sıradaki konu' gerekçesi + rank 0",
                  top is not None and top.curriculum_rank == 0
                  and any("sıradaki konu" in r for r in top.reasons),
                  f"reasons={getattr(top, 'reasons', [])}")
            check("1d. müfredatta ÇOK ilerideki konular (rank>=3: Bölüm 4-5) ÖNERİLMEZ",
                  sec_ids[3] not in by_sec and sec_ids[4] not in by_sec,
                  f"öneriler={[s.section_label for s in sugg]}")
            check("1e. sıralama müfredat sırasını izler (Bölüm 1 > Bölüm 2 > Bölüm 3)",
                  [s.section_id for s in sugg if s.section_id in sec_ids[:3]]
                  == [sec_ids[0], sec_ids[1], sec_ids[2]],
                  f"sıra={[s.section_label for s in sugg]}")

            # --- 2) Konu 1 bitti + Konu 2 başlandı → frontier ilerler ---
            sb = db.query(StudentBook).filter(StudentBook.student_id == sid).first()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec_ids[0],
                                   reserved_count=0, completed_count=20))
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec_ids[1],
                                   reserved_count=0, completed_count=6))
            db.commit()
            sugg2 = suggest_for_date(db, sid, target, model=model, max_suggestions=10)
            by_sec2 = {s.section_id: s for s in sugg2}
            top2 = sugg2[0] if sugg2 else None
            check("2a. Konu 1 bitince frontier Konu 2'ye ilerledi (en üst öneri Bölüm 2)",
                  top2 is not None and top2.section_id == sec_ids[1],
                  f"top={getattr(top2, 'section_label', None)}")
            check("2b. başlanan konuya 'Başlanan konuyu tamamlama' gerekçesi",
                  top2 is not None and any("Başlanan konuyu" in r for r in top2.reasons),
                  f"reasons={getattr(top2, 'reasons', [])}")
            check("2c. bitmiş Konu 1 (kalan 0) artık ÖNERİLMEZ",
                  sec_ids[0] not in by_sec2, "bitmiş konu önerildi")
            check("2d. yeni frontier'da rank>=3'e kayan Bölüm 5 hâlâ önerilmez",
                  sec_ids[4] not in by_sec2,
                  f"öneriler={[s.section_label for s in sugg2]}")

            # --- 3) Öğretmen deseni ileri konuyu kurtarır ama frontier'ı geçemez ---
            past_same_dow = target - timedelta(days=7)
            t_past = Task(student_id=sid, date=past_same_dow, type=TaskType.TEST,
                          title="Geçen hafta ileri konu", status=TaskStatus.PENDING,
                          order=0, is_draft=False)
            db.add(t_past); db.flush()
            db.add(TaskBookItem(task_id=t_past.id, book_id=ids["book"],
                                book_section_id=sec_ids[4], planned_count=2,
                                completed_count=0))
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec_ids[4],
                                   reserved_count=2, completed_count=0))
            db.commit()
            ids["t_past"] = t_past.id
            model3 = build_student_model(db, sid)
            sugg3 = suggest_for_date(db, sid, target, model=model3, max_suggestions=10)
            by_sec3 = {s.section_id: s for s in sugg3}
            check("3a. o güne desenli (1× atanmış) ileri konu artık listede",
                  sec_ids[4] in by_sec3,
                  f"öneriler={[s.section_label for s in sugg3]}")
            check("3b. ileri konu 'Müfredatta ileride' diye işaretli",
                  sec_ids[4] in by_sec3
                  and any("ileride" in r for r in by_sec3[sec_ids[4]].reasons),
                  f"reasons={by_sec3.get(sec_ids[4]) and by_sec3[sec_ids[4]].reasons}")
            check("3c. frontier (Bölüm 2) desenli ileri konudan yine ÜSTTE",
                  sugg3 and sugg3[0].section_id == sec_ids[1]
                  and by_sec3[sec_ids[4]].score < sugg3[0].score,
                  f"sıra={[(s.section_label, round(s.score, 2)) for s in sugg3]}")

            # --- 4) Konuya eşlenmemiş bölüm nötr — engellenmez ---
            check("4. konuya eşlenmemiş bölüm (Karma Testler) nötr skorla listede",
                  ids["s_free"] in by_sec3
                  and by_sec3[ids["s_free"]].curriculum_rank is None,
                  f"öneriler={[s.section_label for s in sugg3]}")
    finally:
        with SessionLocal() as db:
            if ids.get("t_past"):
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id == ids["t_past"]))
                db.execute(sa_delete(Task).where(Task.id == ids["t_past"]))
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.book_section_id.in_(ids["secs"] + [ids["s_free"]])))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(
                BookSection.id.in_(ids["secs"] + [ids["s_free"]])))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
