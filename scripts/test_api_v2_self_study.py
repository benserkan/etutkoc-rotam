# -*- coding: utf-8 -*-
"""Bağımsız çalışma kayıtları (self-study) smoke testi.

Kapsam: koç toplu girişi (uygulama+kırpma+atlama) · öğrenci beyanı (pending ->
onay/ret) · geri çekme · silme/geri alma · eski mutlak endpoint'in izli yeni
davranışı (artış=kayıt, azalış=yalnız manual) · sahiplik 404 · envanter etkisi.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import BackgroundTasks, HTTPException

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, SelfStudyEntry, StudentBook,
    Subject, User, UserRole,
)
from app.routes.api_v2.schemas.self_study import (
    SelfStudyCreateBody, SelfStudyCreateItem, SelfStudyReviewBody,
)
from app.routes.api_v2.schemas.teacher import SectionCompletedBaselineBody
from app.routes.api_v2.self_study import (
    student_self_study_declare_v2,
    student_self_study_list_v2,
    student_self_study_options_v2,
    student_self_study_withdraw_v2,
    teacher_self_study_create_v2,
    teacher_self_study_delete_v2,
    teacher_self_study_list_v2,
    teacher_self_study_review_v2,
)
from app.routes.api_v2.teacher import teacher_set_section_completed_v2
from app.services import analytics
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
SUF = "_selfstudy_tmp"


def clean():
    users = db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all()
    uids = [u.id for u in users]
    if uids:
        db.query(SelfStudyEntry).filter(SelfStudyEntry.student_id.in_(uids)).delete(synchronize_session=False)
        for u in users:
            for b in db.query(Book).filter(Book.teacher_id == u.id).all():
                sbids = [sb.id for sb in db.query(StudentBook).filter(StudentBook.book_id == b.id).all()]
                if sbids:
                    db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbids)).delete(synchronize_session=False)
                db.query(StudentBook).filter(StudentBook.book_id == b.id).delete(synchronize_session=False)
                db.query(BookSection).filter(BookSection.book_id == b.id).delete(synchronize_session=False)
            db.query(Book).filter(Book.teacher_id == u.id).delete(synchronize_session=False)
            db.query(Subject).filter(Subject.teacher_id == u.id).delete(synchronize_session=False)
    db.query(User).filter(User.email.like(f"%{SUF}@x.com")).delete(synchronize_session=False)
    db.commit()


clean()
try:
    coach = User(email=f"c{SUF}@x.com", full_name="Koc", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    other = User(email=f"o{SUF}@x.com", full_name="Yabanci", role=UserRole.TEACHER,
                 password_hash=hash_password("x"), is_active=True)
    db.add_all([coach, other]); db.flush()
    stu = User(email=f"s{SUF}@x.com", full_name="Ogrenci", role=UserRole.STUDENT,
               password_hash=hash_password("x"), is_active=True, teacher_id=coach.id)
    db.add(stu); db.flush()
    subj = Subject(teacher_id=coach.id, name="Matematik", order=1); db.add(subj); db.flush()
    book = Book(teacher_id=coach.id, name="Tatil SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
    db.add(book); db.flush()
    sec1 = BookSection(book_id=book.id, label="Unite 1", test_count=20, order=0)
    sec2 = BookSection(book_id=book.id, label="Unite 2", test_count=30, order=1)
    sec3 = BookSection(book_id=book.id, label="Unite 3", test_count=10, order=2)
    db.add_all([sec1, sec2, sec3]); db.flush()
    sb = StudentBook(student_id=stu.id, book_id=book.id); db.add(sb); db.flush()
    # sec2'de 5 rezerv (aktif plan taahhüdü korunmalı)
    db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec2.id,
                           reserved_count=5, completed_count=0, manual_count=0))
    db.commit()

    def sp_for(section_id):
        return (
            db.query(SectionProgress)
            .filter(SectionProgress.student_book_id == sb.id,
                    SectionProgress.book_section_id == section_id)
            .first()
        )

    # ---- 1) Koç toplu giriş: uygulama + kapasite kırpma + atlama ----
    res = teacher_self_study_create_v2(
        student_id=stu.id,
        body=SelfStudyCreateBody(
            items=[
                SelfStudyCreateItem(student_book_id=sb.id, section_id=sec1.id, test_count=8),
                SelfStudyCreateItem(student_book_id=sb.id, section_id=sec2.id, test_count=30),  # rezerv 5 -> 25'e kırpılır
                SelfStudyCreateItem(student_book_id=sb.id, section_id=sec3.id, test_count=99),  # bölümde 10 var -> atlanır
            ],
            note="Yaz tatili köy çalışması",
            period_start="2026-07-01", period_end="2026-07-15",
        ),
        user=coach, db=db,
    )
    check("1. koç girişi: 2 kayıt oluştu + 1 atlandı",
          len(res.data.created) == 2 and len(res.data.skipped) == 1,
          f"created={len(res.data.created)} skipped={len(res.data.skipped)}")
    check("2. sec1 tam uygulandı (8/8)",
          sp_for(sec1.id).completed_count == 8 and sp_for(sec1.id).manual_count == 8)
    check("3. sec2 rezerve KIRPILDI (30->25) + rezerv korunur",
          sp_for(sec2.id).completed_count == 25 and sp_for(sec2.id).manual_count == 25
          and sp_for(sec2.id).reserved_count == 5,
          f"c={sp_for(sec2.id).completed_count} m={sp_for(sec2.id).manual_count}")
    check("4. applied_total doğru (8+25=33)", res.data.applied_total == 33,
          f"got {res.data.applied_total}")
    e_sec2 = next(x for x in res.data.created if x.section_id == sec2.id)
    check("5. kayıt izi: source=coach, onaylı, dönem + not saklı",
          e_sec2.source == "coach" and e_sec2.status == "approved"
          and e_sec2.applied_count == 25 and e_sec2.period_start == "2026-07-01"
          and e_sec2.note == "Yaz tatili köy çalışması")

    # ---- 2) Koç listesi ----
    lst = teacher_self_study_list_v2(student_id=stu.id, user=coach, db=db)
    check("6. koç listesi 2 kayıt + bekleyen 0",
          len(lst.items) == 2 and lst.pending_count == 0)

    # ---- 3) Eski mutlak endpoint — izli yeni davranış ----
    # sec1: 8 -> 12'ye çıkar (delta +4 -> yeni koç kaydı)
    teacher_set_section_completed_v2(stu.id, sb.id, sec1.id,
                                     SectionCompletedBaselineBody(completed_count=12), coach, db)
    check("7. mutlak artış: completed=12, manual=12",
          sp_for(sec1.id).completed_count == 12 and sp_for(sec1.id).manual_count == 12)
    n_entries = db.query(SelfStudyEntry).filter(
        SelfStudyEntry.book_section_id == sec1.id, SelfStudyEntry.student_id == stu.id).count()
    check("8. artış yeni kayıt üretti (izli)", n_entries == 2, f"got {n_entries}")
    # sec1: 12 -> 3'e düşür (azalış manual'dan; kayıtlar geriye doğru söndürülür)
    teacher_set_section_completed_v2(stu.id, sb.id, sec1.id,
                                     SectionCompletedBaselineBody(completed_count=3), coach, db)
    check("9. mutlak azalış: completed=3, manual=3",
          sp_for(sec1.id).completed_count == 3 and sp_for(sec1.id).manual_count == 3)
    # sec1: görevle çözülmüş 5 simüle et (manual dışı) -> 3+5=8; 8->2 azaltma =6 > manual 3 -> 422
    sp1 = sp_for(sec1.id); sp1.completed_count += 5; db.commit()
    try:
        teacher_set_section_completed_v2(stu.id, sb.id, sec1.id,
                                         SectionCompletedBaselineBody(completed_count=2), coach, db)
        check("10. görev kısmı azaltılamaz -> 422", False, "exception bekleniyordu")
    except HTTPException as ex:
        check("10. görev kısmı azaltılamaz -> 422 manual_reduce_exceeds",
              ex.status_code == 422 and ex.detail.get("code") == "manual_reduce_exceeds")
    # sınır aşımı hâlâ 422 (rezerv korunur): sec2 max 25
    try:
        teacher_set_section_completed_v2(stu.id, sb.id, sec2.id,
                                         SectionCompletedBaselineBody(completed_count=26), coach, db)
        check("11. rezerv aşımı 422", False)
    except HTTPException as ex:
        check("11. rezerv aşımı 422 exceeds_available",
              ex.status_code == 422 and ex.detail.get("code") == "exceeds_available")

    # ---- 4) Öğrenci beyanı -> pending, ilerlemeye DOKUNMAZ ----
    before_c = sp_for(sec3.id).completed_count if sp_for(sec3.id) else 0
    bg = BackgroundTasks()
    dres = student_self_study_declare_v2(
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb.id, section_id=sec3.id, test_count=6)],
            note="Köyde internetsiz çalıştım",
        ),
        background=bg, user=stu, db=db,
    )
    entry_id = dres.data.created[0].id
    check("12. beyan pending + ilerleme değişmedi",
          dres.data.created[0].status == "pending"
          and dres.data.pending_total == 6
          and (sp_for(sec3.id).completed_count if sp_for(sec3.id) else 0) == before_c)
    check("13. koça push planlandı", len(bg.tasks) == 1)
    lst2 = teacher_self_study_list_v2(student_id=stu.id, user=coach, db=db)
    check("14. koç listesinde bekleyen 1", lst2.pending_count == 1)

    # ---- 5) Onay -> uygulanır ----
    rres = teacher_self_study_review_v2(
        entry_id=entry_id, body=SelfStudyReviewBody(approve=True, review_note="Aferin"),
        background=BackgroundTasks(), user=coach, db=db,
    )
    check("15. onay: uygulandı (6) + durum approved",
          rres.data.status == "approved" and rres.data.applied_count == 6
          and sp_for(sec3.id).completed_count == 6 and sp_for(sec3.id).manual_count == 6)

    # ---- 6) İkinci beyan -> RET -> değişmez ----
    dres2 = student_self_study_declare_v2(
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb.id, section_id=sec3.id, test_count=2)]),
        background=BackgroundTasks(), user=stu, db=db,
    )
    rid = dres2.data.created[0].id
    rres2 = teacher_self_study_review_v2(
        entry_id=rid, body=SelfStudyReviewBody(approve=False, review_note="Görüşelim"),
        background=BackgroundTasks(), user=coach, db=db,
    )
    check("16. ret: durum rejected + ilerleme değişmedi",
          rres2.data.status == "rejected" and sp_for(sec3.id).completed_count == 6)
    # sonuçlanmış kayıt tekrar incelenemez
    try:
        teacher_self_study_review_v2(entry_id=rid, body=SelfStudyReviewBody(approve=True),
                                     background=BackgroundTasks(), user=coach, db=db)
        check("17. sonuçlanmış tekrar incelenemez 422", False)
    except HTTPException as ex:
        check("17. sonuçlanmış tekrar incelenemez 422", ex.status_code == 422)

    # ---- 7) Öğrenci geri çekme ----
    dres3 = student_self_study_declare_v2(
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb.id, section_id=sec3.id, test_count=1)]),
        background=BackgroundTasks(), user=stu, db=db,
    )
    wid = dres3.data.created[0].id
    student_self_study_withdraw_v2(entry_id=wid, user=stu, db=db)
    check("18. bekleyen beyan geri çekildi",
          db.get(SelfStudyEntry, wid) is None)
    try:
        student_self_study_withdraw_v2(entry_id=entry_id, user=stu, db=db)  # onaylanmış
        check("19. onaylanmış geri çekilemez 422", False)
    except HTTPException as ex:
        check("19. onaylanmış geri çekilemez 422", ex.status_code == 422)

    # ---- 8) Koç silme -> birebir geri alma ----
    dres_del = teacher_self_study_delete_v2(entry_id=entry_id, user=coach, db=db)
    check("20. onaylı kayıt silindi -> 6 test geri alındı",
          dres_del.data.reverted_count == 6
          and sp_for(sec3.id).completed_count == 0 and sp_for(sec3.id).manual_count == 0)

    # ---- 9) Sahiplik: yabancı koç 404 ----
    try:
        teacher_self_study_list_v2(student_id=stu.id, user=other, db=db)
        check("21. yabancı koç liste 404", False)
    except HTTPException as ex:
        check("21. yabancı koç liste 404", ex.status_code == 404)
    some_entry = db.query(SelfStudyEntry).filter(SelfStudyEntry.student_id == stu.id).first()
    try:
        teacher_self_study_delete_v2(entry_id=some_entry.id, user=other, db=db)
        check("22. yabancı koç silme 404", False)
    except HTTPException as ex:
        check("22. yabancı koç silme 404", ex.status_code == 404)

    # ---- 10) Öğrenci listesi + seçenekler ----
    slst = student_self_study_list_v2(user=stu, db=db)
    check("23. öğrenci kendi listesini görür", len(slst.items) >= 3)
    opts = student_self_study_options_v2(user=stu, db=db)
    ob = next((b for b in opts.books if b.student_book_id == sb.id), None)
    osec2 = next((s for s in ob.sections if s.section_id == sec2.id), None) if ob else None
    check("24. seçenekler: bölüm + kalan kapasite doğru (sec2 kalan 0)",
          ob is not None and osec2 is not None and osec2.remaining == 0
          and osec2.reserved_count == 5,
          f"{osec2}")

    # ---- 11) Envanter (projeksiyon/kaynak durumu) yansıması ----
    total, completed, reserved = analytics.inventory_totals(db, stu.id, tests_only=True)
    exp_completed = (sp_for(sec1.id).completed_count
                     + sp_for(sec2.id).completed_count
                     + sp_for(sec3.id).completed_count)
    check("25. inventory_totals bağımsız çalışmayı sayar",
          completed == exp_completed, f"inv={completed} exp={exp_completed}")

finally:
    clean()
    db.close()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
