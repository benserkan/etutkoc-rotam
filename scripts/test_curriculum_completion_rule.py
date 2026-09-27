"""Konu tamamlanma kuralı + mezun ders filtresi — saha (2026-09-27).

KURAL (koç): konu tamamlanması öğrencinin o konuyu içeren kaynaklarına bakar.
  * Tek kaynak → konunun testlerinin %98'i çözüldüyse tamam.
  * Birden fazla kaynak → biri tamamen bitmiş VE ikinci kaynaktan %90+ çözülmüş.
  * Deneme kitabı kaynak sayılmaz; koçun kapatma kararı her şeyin üstünde.

MEZUN (Emir #113): mezunun müfredat modeli boş → okul dersleri (İngilizce,
İnkılap Tarihi) model filtresine takılmadan "0/51" listeleniyordu. Mezunda okul
dersi YALNIZ kaynak atandıysa görünür.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    BookType,
    CurriculumModel,
    ExamSection,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services import curriculum_progress as cp
from app.services.topic_board import build_topic_board
from app.services.security import hash_password

PFX = f"ccr_{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def unit() -> None:
    f = cp.topic_sources_complete
    check("U1. tek kaynak 49/50 (%98) → tamam", f({1: (49, 50)}))
    check("U2. tek kaynak 48/50 (%96) → değil", not f({1: (48, 50)}))
    check("U3. iki kaynak 10/10 + 9/10 → tamam", f({1: (10, 10), 2: (9, 10)}))
    check("U4. iki kaynak 10/10 + 8/10 → değil", not f({1: (10, 10), 2: (8, 10)}))
    check("U5. iki kaynak 9/10 + 10/10 (sıra fark etmez) → tamam", f({1: (9, 10), 2: (10, 10)}))
    check("U6. iki kaynak 99/100 + 10/10 değil ikisi de tam değil → değil",
          not f({1: (99, 100), 2: (9, 10)}))
    check("U7. test sayısı olmayan kitap sayılmaz → tek kaynak kuralı",
          f({1: (49, 50), 2: (0, 0)}))
    check("U8. kaynak yok → değil", not f({}))


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("x"),
                     full_name="CCR Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        grad = User(email=f"{PFX}_g@test.invalid", password_hash=hash_password("x"),
                    full_name="Mezun", role=UserRole.STUDENT, is_active=True,
                    teacher_id=coach.id, is_graduate=True)
        db.add(grad)
        db.flush()
        tyt = Subject(name=f"TYT Matematik {PFX}", teacher_id=coach.id,
                      curriculum_model=None, exam_section=ExamSection.TYT,
                      min_grade_level=9, max_grade_level=12, available_for_graduate=True)
        ing = Subject(name=f"İngilizce {PFX}", teacher_id=coach.id,
                      curriculum_model=CurriculumModel.MAARIF_LISE,
                      exam_section=ExamSection.AYT_DIL,
                      min_grade_level=9, max_grade_level=12, available_for_graduate=True)
        ink = Subject(name=f"İnkılap {PFX}", teacher_id=coach.id,
                      curriculum_model=CurriculumModel.KLASIK_LISE,
                      exam_section=ExamSection.AYT_SOZ,
                      min_grade_level=12, max_grade_level=12, available_for_graduate=True)
        db.add_all([tyt, ing, ink])
        db.flush()
        tp = {}
        for i, nm in enumerate(("Çift", "Tek", "Deneme", "Kapalı")):
            t = Topic(subject_id=tyt.id, name=f"{nm} {PFX}", order=i + 1, teacher_id=coach.id)
            db.add(t)
            db.flush()
            tp[nm] = t.id
        t_ing = Topic(subject_id=ing.id, name=f"Ing {PFX}", order=1, teacher_id=coach.id)
        db.add(t_ing)
        db.flush()
        b1 = Book(name=f"A {PFX}", subject_id=tyt.id, teacher_id=coach.id, type=BookType.SORU_BANKASI)
        b2 = Book(name=f"B {PFX}", subject_id=tyt.id, teacher_id=coach.id, type=BookType.SORU_BANKASI)
        bd = Book(name=f"D {PFX}", subject_id=tyt.id, teacher_id=coach.id, type=BookType.BRANS_DENEMESI)
        bi = Book(name=f"I {PFX}", subject_id=ing.id, teacher_id=coach.id, type=BookType.SORU_BANKASI)
        db.add_all([b1, b2, bd, bi])
        db.flush()
        secs = {}

        def sec(book, topic, n):
            s = BookSection(book_id=book.id, label=f"S{book.id}-{topic}", test_count=n,
                            order=1, topic_id=topic)
            db.add(s)
            db.flush()
            return s.id
        secs["a_cift"] = sec(b1, tp["Çift"], 10)
        secs["b_cift"] = sec(b2, tp["Çift"], 10)
        secs["a_tek"] = sec(b1, tp["Tek"], 50)
        secs["a_den"] = sec(b1, tp["Deneme"], 50)
        secs["d_den"] = sec(bd, tp["Deneme"], 10)
        secs["i_ing"] = sec(bi, t_ing.id, 10)
        sbs = {}
        for bk in (b1, b2, bd):
            sb = StudentBook(student_id=grad.id, book_id=bk.id)
            db.add(sb)
            db.flush()
            sbs[bk.id] = sb.id
        db.commit()
        return {"coach": coach.id, "grad": grad.id, "tyt": tyt.id, "ing": ing.id,
                "ink": ink.id, "tp": tp, "secs": secs, "sbs": sbs,
                "b1": b1.id, "b2": b2.id, "bd": bd.id, "bi": bi.id,
                "books": [b1.id, b2.id, bd.id, bi.id]}


def set_done(db, d, book_key: str, sec_key: str, n: int) -> None:
    sbid = d["sbs"][d[book_key]]
    sp = (db.query(SectionProgress)
          .filter_by(student_book_id=sbid, book_section_id=d["secs"][sec_key]).first())
    if sp is None:
        sp = SectionProgress(student_book_id=sbid, book_section_id=d["secs"][sec_key],
                             reserved_count=0, completed_count=0)
        db.add(sp)
    sp.completed_count = n
    db.commit()


def statuses(db, d) -> tuple[dict, dict]:
    st = db.get(User, d["grad"])
    prog = cp.compute_curriculum_progress(db, st, d["coach"])
    tab = {}
    for s in prog.subjects:
        for t in s.topics:
            tab[t.topic_id] = t.status
    board = build_topic_board(db, student=st, coach_id=d["coach"], subject_id=d["tyt"])
    brd = {t.topic_id: t.status for s in board.subjects for t in s.topics}
    return tab, brd


def cleanup(d: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id.in_(list(d["sbs"].values()))))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == d["grad"]))
        for bid in d["books"]:
            db.execute(sa_delete(BookSection).where(BookSection.book_id == bid))
            db.execute(sa_delete(Book).where(Book.id == bid))
        for sj in (d["tyt"], d["ing"], d["ink"]):
            db.execute(sa_delete(Topic).where(Topic.subject_id == sj))
            db.execute(sa_delete(Subject).where(Subject.id == sj))
        db.execute(sa_delete(User).where(User.id.in_([d["grad"], d["coach"]])))
        db.commit()


def main() -> int:
    print("\n=== Konu tamamlanma kuralı ===\n")
    unit()
    d = seed()
    tp = d["tp"]
    try:
        with SessionLocal() as db:
            st = db.get(User, d["grad"])
            names = {s.name for s in cp._applicable_subjects(db, st, d["coach"])}
            check("M1. mezun → kaynaksız İngilizce GİZLİ", f"İngilizce {PFX}" not in names, str(names))
            check("M2. mezun → kaynaksız İnkılap GİZLİ", f"İnkılap {PFX}" not in names, str(names))
            check("M3. mezun → TYT dersi görünür", f"TYT Matematik {PFX}" in names)

            set_done(db, d, "b1", "a_cift", 10)
            set_done(db, d, "b2", "b_cift", 8)
            set_done(db, d, "b1", "a_tek", 49)
            tab, brd = statuses(db, d)
            check("I1. iki kaynak 10/10 + 8/10 → devam", tab.get(tp["Çift"]) == "devam", tab.get(tp["Çift"]))
            check("I2. tek kaynak 49/50 → tamamlandi", tab.get(tp["Tek"]) == "tamamlandi", tab.get(tp["Tek"]))
            check("I3. hafta paneli aynı (tek kaynak tamam, çift devam)",
                  brd.get(tp["Tek"]) == "tamamlandi" and brd.get(tp["Çift"]) == "devam", str(brd))

            set_done(db, d, "b2", "b_cift", 9)
            set_done(db, d, "b1", "a_den", 50)
            tab, brd = statuses(db, d)
            check("I4. ikinci kaynak 9/10 → tamamlandi", tab.get(tp["Çift"]) == "tamamlandi", tab.get(tp["Çift"]))
            check("I5. deneme kitabı kaynak sayılmaz (soru bankası 50/50 → tamam)",
                  tab.get(tp["Deneme"]) == "tamamlandi", tab.get(tp["Deneme"]))
            check("I6. hafta paneli ikinci kaynak sonrası da aynı",
                  brd.get(tp["Çift"]) == "tamamlandi", str(brd))

            nu = cp.next_units_for_assignment(db, st, d["coach"], per_subject=5)
            nu_ids = {u.topic_id for u in nu}
            check("I7. sıradaki üniteler tamamlananları önermez",
                  tp["Tek"] not in nu_ids and tp["Çift"] not in nu_ids, str(nu_ids))

            # kaynak atanırsa mezunda okul dersi görünür
            db.add(StudentBook(student_id=d["grad"], book_id=d["bi"]))
            db.commit()
            names = {s.name for s in cp._applicable_subjects(db, st, d["coach"])}
            check("M4. mezun + İngilizce kaynağı → İngilizce görünür", f"İngilizce {PFX}" in names)
    finally:
        cleanup(d)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
