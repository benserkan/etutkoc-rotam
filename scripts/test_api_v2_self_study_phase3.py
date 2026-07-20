# -*- coding: utf-8 -*-
"""Bağımsız çalışma Faz 3 smoke: deneme çapraz doğrulaması.

"Çözüldü işaretli konu <-> denemede düşük doğruluk" tutarsızlığı:
servis eşikleri (min soru + doğruluk + işlenmişlik + boş sayılmaz + pencere) ·
koç müfredat endpoint'inde rozet alanları · kurum raporunda elle-ağırlıklı
tutarsızlık tablosu (görev-kaynaklı olan girmez).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, timedelta

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, ExamResult, ExamResultQuestion, Institution,
    SectionProgress, SelfStudyEntry, StudentBook, Subject, Topic, User, UserRole,
)
from app.models.exam_result import (
    EQ_RESULT_BOS, EQ_RESULT_DOGRU, EQ_RESULT_YANLIS, ExamSection,
)
from app.routes.api_v2.schemas.self_study import SelfStudyCreateBody, SelfStudyCreateItem
from app.routes.api_v2.self_study import teacher_self_study_create_v2
from app.routes.api_v2.teacher import teacher_student_curriculum_v2
from app.services.exam_consistency import (
    curriculum_exam_mismatches, topic_exam_stats,
)
from app.services.institution_self_study import build_report
from app.services.security import hash_password

PASS = FAIL = 0


def check(n, c, e=""):
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"  [PASS] {n}")
    else:
        FAIL += 1
        print(f"  [FAIL] {n} {e}")


db = SessionLocal()
SUF = "_ssp3_tmp"


def clean():
    users = db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all()
    uids = [u.id for u in users]
    if uids:
        exam_ids = [e.id for e in db.query(ExamResult).filter(ExamResult.student_id.in_(uids)).all()]
        if exam_ids:
            db.query(ExamResultQuestion).filter(ExamResultQuestion.exam_result_id.in_(exam_ids)).delete(synchronize_session=False)
            db.query(ExamResult).filter(ExamResult.id.in_(exam_ids)).delete(synchronize_session=False)
        db.query(SelfStudyEntry).filter(SelfStudyEntry.student_id.in_(uids)).delete(synchronize_session=False)
        for u in users:
            for b in db.query(Book).filter(Book.teacher_id == u.id).all():
                sbids = [sb.id for sb in db.query(StudentBook).filter(StudentBook.book_id == b.id).all()]
                if sbids:
                    db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbids)).delete(synchronize_session=False)
                db.query(StudentBook).filter(StudentBook.book_id == b.id).delete(synchronize_session=False)
                db.query(BookSection).filter(BookSection.book_id == b.id).delete(synchronize_session=False)
            db.query(Book).filter(Book.teacher_id == u.id).delete(synchronize_session=False)
            for s in db.query(Subject).filter(Subject.teacher_id == u.id).all():
                db.query(Topic).filter(Topic.subject_id == s.id).delete(synchronize_session=False)
            db.query(Subject).filter(Subject.teacher_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.query(Institution).filter(Institution.slug.like(f"%{SUF}%")).delete(synchronize_session=False)
    db.commit()


def add_exam(student, coach, topic_results, days_ago=5, title="Deneme"):
    """topic_results: [(topic_id, result), ...] — soru satırlı deneme ekle."""
    ex = ExamResult(
        student_id=student.id, created_by_id=coach.id, title=title,
        exam_date=date.today() - timedelta(days=days_ago),
        section=ExamSection.TYT, total_correct=0, total_wrong=0, total_blank=0, net=0.0,
    )
    db.add(ex); db.flush()
    for i, (tid, res) in enumerate(topic_results, start=1):
        db.add(ExamResultQuestion(
            exam_result_id=ex.id, question_no=i, topic_id=tid, result=res,
        ))
    db.commit()
    return ex


clean()
try:
    inst = Institution(name=f"KurumP3{SUF}", slug=f"kurump3{SUF}", is_active=True)
    db.add(inst); db.flush()
    coach = User(email=f"c{SUF}@x.com", full_name="KocP3", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True, institution_id=inst.id)
    db.add(coach); db.flush()
    stu = User(email=f"s{SUF}@x.com", full_name="OgrP3", role=UserRole.STUDENT,
               password_hash=hash_password("x"), is_active=True, teacher_id=coach.id)
    db.add(stu); db.flush()

    subj = Subject(teacher_id=coach.id, name="MatP3", order=1)
    db.add(subj); db.flush()
    # 4 konu: T1 elle-ağırlıklı tutarsız · T2 görevle-işlenmiş tutarsız ·
    # T3 işlenmiş + denemede İYİ · T4 az işlenmiş
    t1 = Topic(subject_id=subj.id, name="Carpanlar", order=1, teacher_id=coach.id)
    t2 = Topic(subject_id=subj.id, name="Uslu", order=2, teacher_id=coach.id)
    t3 = Topic(subject_id=subj.id, name="Koklu", order=3, teacher_id=coach.id)
    t4 = Topic(subject_id=subj.id, name="Oran", order=4, teacher_id=coach.id)
    db.add_all([t1, t2, t3, t4]); db.flush()

    book = Book(teacher_id=coach.id, name="P3-SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
    db.add(book); db.flush()
    s1 = BookSection(book_id=book.id, label="U1", test_count=20, order=0, topic_id=t1.id)
    s2 = BookSection(book_id=book.id, label="U2", test_count=20, order=1, topic_id=t2.id)
    s3 = BookSection(book_id=book.id, label="U3", test_count=20, order=2, topic_id=t3.id)
    s4 = BookSection(book_id=book.id, label="U4", test_count=20, order=3, topic_id=t4.id)
    db.add_all([s1, s2, s3, s4]); db.flush()
    sb = StudentBook(student_id=stu.id, book_id=book.id); db.add(sb); db.flush()
    # T2 görevle işlenmiş (manual=0) · T4 az işlenmiş (2 test)
    db.add(SectionProgress(student_book_id=sb.id, book_section_id=s2.id,
                           reserved_count=0, completed_count=16, manual_count=0))
    db.add(SectionProgress(student_book_id=sb.id, book_section_id=s4.id,
                           reserved_count=0, completed_count=2, manual_count=0))
    db.commit()

    # T1'i ELLE işle (self-study koç girişi, 16 test)
    teacher_self_study_create_v2(
        student_id=stu.id,
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb.id, section_id=s1.id, test_count=16)],
            note="Tatil girişi",
        ),
        user=coach, db=db,
    )
    # T3'ü elle işle (denemede iyi çıkacak — tutarsızlık üretmemeli)
    teacher_self_study_create_v2(
        student_id=stu.id,
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb.id, section_id=s3.id, test_count=16)]),
        user=coach, db=db,
    )

    # Deneme: T1 1D/4Y (0.20) + 2 BOŞ · T2 1D/3Y (0.25) · T3 4D/1Y (0.80) ·
    # T4 0D/4Y (az işlenmiş — konu tarafı elemeli)
    add_exam(stu, coach, (
        [(t1.id, EQ_RESULT_DOGRU)] + [(t1.id, EQ_RESULT_YANLIS)] * 4 + [(t1.id, EQ_RESULT_BOS)] * 2
        + [(t2.id, EQ_RESULT_DOGRU)] + [(t2.id, EQ_RESULT_YANLIS)] * 3
        + [(t3.id, EQ_RESULT_DOGRU)] * 4 + [(t3.id, EQ_RESULT_YANLIS)]
        + [(t4.id, EQ_RESULT_YANLIS)] * 4
    ))

    # ---- 1) topic_exam_stats: boş sayılmaz ----
    stats = topic_exam_stats(db, stu.id)
    check("1. T1 istatistik: 5 cevaplanmış (2 boş HARİÇ), doğruluk %20",
          stats[t1.id]["answered"] == 5 and stats[t1.id]["correct"] == 1,
          f"{stats.get(t1.id)}")

    # ---- 2) mismatch listesi ----
    mm = curriculum_exam_mismatches(db, stu.id)
    ids = {f["topic_id"] for f in mm}
    check("2. T1 tutarsız (elle işlenmiş + %20 doğruluk)", t1.id in ids, f"{ids}")
    check("3. T2 tutarsız (görevle işlenmiş + %25) — pedagojik sinyal", t2.id in ids)
    check("4. T3 tutarsız DEĞİL (denemede %80)", t3.id not in ids)
    check("5. T4 tutarsız DEĞİL (yalnız 2 test işlenmiş)", t4.id not in ids)
    f1 = next(f for f in mm if f["topic_id"] == t1.id)
    f2 = next(f for f in mm if f["topic_id"] == t2.id)
    check("6. T1 elle-ağırlıklı (manual 16/16) · T2 değil (manual 0)",
          f1["manual_heavy"] is True and f1["manual_share_pct"] == 100
          and f2["manual_heavy"] is False, f"{f1} {f2}")
    check("7. satır alanları dolu (konu/ders adı + doğruluk)",
          f1["topic_name"] == "Carpanlar" and f1["subject_name"] == "MatP3"
          and f1["accuracy_pct"] == 20)

    # ---- 3) min cevaplanmış eşiği: 2 soruluk konu sinyal üretmez ----
    t5 = Topic(subject_id=subj.id, name="Mutlak", order=5, teacher_id=coach.id)
    db.add(t5); db.flush()
    s5 = BookSection(book_id=book.id, label="U5", test_count=20, order=4, topic_id=t5.id)
    db.add(s5); db.flush()
    db.add(SectionProgress(student_book_id=sb.id, book_section_id=s5.id,
                           reserved_count=0, completed_count=16, manual_count=16))
    db.commit()
    add_exam(stu, coach, [(t5.id, EQ_RESULT_YANLIS)] * 2, days_ago=3, title="Kisa")
    mm2 = curriculum_exam_mismatches(db, stu.id)
    check("8. 2 cevaplanmış soru yetmez (min 3) — T5 sinyalsiz",
          t5.id not in {f["topic_id"] for f in mm2})

    # ---- 4) pencere: 120 gün önceki deneme sayılmaz ----
    add_exam(stu, coach, [(t5.id, EQ_RESULT_YANLIS)] * 5, days_ago=120, title="Eski")
    mm3 = curriculum_exam_mismatches(db, stu.id)
    check("9. 90 gün penceresi: eski deneme T5'i tutarsız yapmaz",
          t5.id not in {f["topic_id"] for f in mm3})

    # ---- 5) koç müfredat endpoint'i rozet alanları ----
    cur = teacher_student_curriculum_v2(student_id=stu.id, user=coach, db=db)
    topics = [t for s in cur.subjects for t in s.topics]
    ct1 = next((t for t in topics if t.topic_id == t1.id), None)
    ct3 = next((t for t in topics if t.topic_id == t3.id), None)
    check("10. müfredat: T1 exam_mismatch=True + %20 + elle-ağırlıklı",
          ct1 is not None and ct1.exam_mismatch and ct1.exam_accuracy_pct == 20
          and ct1.exam_manual_heavy is True,
          f"{ct1}")
    check("11. müfredat: T3 işaretsiz",
          ct3 is not None and ct3.exam_mismatch is False)

    # ---- 6) kurum raporu: yalnız elle-ağırlıklı satır ----
    rep = build_report(db, inst.id, days=30)
    m_topics = {m["topic_name"] for m in rep["mismatches"]}
    check("12. rapor: T1 (elle) listede · T2 (görev-kaynaklı) YOK",
          "Carpanlar" in m_topics and "Uslu" not in m_topics, f"{m_topics}")
    m1 = next(m for m in rep["mismatches"] if m["topic_name"] == "Carpanlar")
    check("13. rapor satırı: öğrenci/koç/doğruluk dolu + özet sayacı",
          m1["student_name"] == "OgrP3" and m1["coach_name"] == "KocP3"
          and m1["accuracy_pct"] == 20
          and rep["summary"]["mismatch_count"] == len(rep["mismatches"]))

finally:
    clean()
    db.close()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
