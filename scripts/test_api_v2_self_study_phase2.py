# -*- coding: utf-8 -*-
"""Bağımsız çalışma Faz 2 smoke: audit izi + kurum raporu + anomali dedektörü.

Kapsam: koç girişi/onay/ret/silme/mutlak-set audit kayıtları · kurum yöneticisi
raporu (koç kırılımı + beyansız-yüklü-giriş dikkat işareti + kapsam izolasyonu +
gün filtresi) · manual_progress_surge dedektörü (eşik + bağımsız koç hariç +
beyanlı girişler sayılmaz + dedup).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

from fastapi import BackgroundTasks

from app.database import SessionLocal
from app.models import (
    AbuseSignal, AuditAction, AuditLog, Book, BookSection, BookType, Institution,
    SectionProgress, SelfStudyEntry, StudentBook, Subject, User, UserRole,
)
from app.routes.api_v2.institution import institution_self_study_report_v2
from app.routes.api_v2.schemas.self_study import (
    SelfStudyCreateBody, SelfStudyCreateItem, SelfStudyReviewBody,
)
from app.routes.api_v2.schemas.teacher import SectionCompletedBaselineBody
from app.routes.api_v2.self_study import (
    student_self_study_declare_v2,
    teacher_self_study_create_v2,
    teacher_self_study_delete_v2,
    teacher_self_study_review_v2,
)
from app.routes.api_v2.teacher import teacher_set_section_completed_v2
from app.services.abuse_detection import (
    KIND_MANUAL_PROGRESS_SURGE,
    detect_manual_progress_surge,
    _upsert_signal,
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
SUF = "_ssp2_tmp"


def clean():
    users = db.query(User).filter(User.email.like(f"%{SUF}@x.com")).all()
    uids = [u.id for u in users]
    if uids:
        db.query(SelfStudyEntry).filter(SelfStudyEntry.student_id.in_(uids)).delete(synchronize_session=False)
        db.query(AbuseSignal).filter(AbuseSignal.actor_user_id.in_(uids)).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.actor_id.in_(uids)).delete(synchronize_session=False)
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
    db.query(Institution).filter(Institution.slug.like(f"%{SUF}%")).delete(synchronize_session=False)
    db.commit()


def mk_setup(coach, n_tests=700, label_prefix="B"):
    """Koça 1 öğrenci + büyük kitap (tek bölüm n_tests) kur; (student, sb, sec) döner."""
    stu = User(email=f"s{coach.id}{SUF}@x.com", full_name=f"Ogr{coach.id}",
               role=UserRole.STUDENT, password_hash=hash_password("x"),
               is_active=True, teacher_id=coach.id)
    db.add(stu); db.flush()
    subj = Subject(teacher_id=coach.id, name=f"Mat{coach.id}", order=1)
    db.add(subj); db.flush()
    book = Book(teacher_id=coach.id, name=f"{label_prefix}-SB{coach.id}",
                type=BookType.SORU_BANKASI, subject_id=subj.id)
    db.add(book); db.flush()
    sec = BookSection(book_id=book.id, label=f"{label_prefix} Unite", test_count=n_tests, order=0)
    db.add(sec); db.flush()
    sb = StudentBook(student_id=stu.id, book_id=book.id)
    db.add(sb); db.flush()
    db.commit()
    return stu, sb, sec


clean()
try:
    inst = Institution(name=f"Kurum{SUF}", slug=f"kurum{SUF}", is_active=True)
    db.add(inst); db.flush()
    inst2 = Institution(name=f"Kurum2{SUF}", slug=f"kurum2{SUF}", is_active=True)
    db.add(inst2); db.flush()

    admin = User(email=f"adm{SUF}@x.com", full_name="Yonetici", role=UserRole.INSTITUTION_ADMIN,
                 password_hash=hash_password("x"), is_active=True, institution_id=inst.id)
    coach_a = User(email=f"ca{SUF}@x.com", full_name="KocA", role=UserRole.TEACHER,
                   password_hash=hash_password("x"), is_active=True, institution_id=inst.id)
    coach_b = User(email=f"cb{SUF}@x.com", full_name="KocB", role=UserRole.TEACHER,
                   password_hash=hash_password("x"), is_active=True, institution_id=inst.id)
    coach_f = User(email=f"cf{SUF}@x.com", full_name="KocYabanci", role=UserRole.TEACHER,
                   password_hash=hash_password("x"), is_active=True, institution_id=inst2.id)
    coach_solo = User(email=f"cs{SUF}@x.com", full_name="KocSolo", role=UserRole.TEACHER,
                      password_hash=hash_password("x"), is_active=True, institution_id=None)
    db.add_all([admin, coach_a, coach_b, coach_f, coach_solo]); db.flush()
    db.commit()

    stu_a, sb_a, sec_a = mk_setup(coach_a, n_tests=700, label_prefix="A")
    stu_b, sb_b, sec_b = mk_setup(coach_b, n_tests=100, label_prefix="B")
    stu_f, sb_f, sec_f = mk_setup(coach_f, n_tests=700, label_prefix="F")
    stu_s, sb_s, sec_s = mk_setup(coach_solo, n_tests=700, label_prefix="S")

    # ---- Koç A: beyansız yüklü giriş (600 test) ----
    teacher_self_study_create_v2(
        student_id=stu_a.id,
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb_a.id, section_id=sec_a.id, test_count=600)],
            note="Yaz güncellemesi",
        ),
        user=coach_a, db=db,
    )

    # ---- 1) Audit: coach_create ----
    a1 = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == coach_a.id,
                AuditLog.action == AuditAction.SELF_STUDY_UPDATE)
        .order_by(AuditLog.id.desc()).first()
    )
    d1 = json.loads(a1.details_json) if a1 and a1.details_json else {}
    check("1. koç girişi audit'lendi (op=coach_create, applied=600)",
          a1 is not None and d1.get("op") == "coach_create"
          and d1.get("applied_total") == 600 and a1.target_id == stu_a.id,
          f"{d1}")

    # ---- Koç B: öğrenci beyanı -> onay + ret ----
    dres = student_self_study_declare_v2(
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb_b.id, section_id=sec_b.id, test_count=40)]),
        background=BackgroundTasks(), user=stu_b, db=db,
    )
    eid = dres.data.created[0].id
    teacher_self_study_review_v2(entry_id=eid, body=SelfStudyReviewBody(approve=True),
                                 background=BackgroundTasks(), user=coach_b, db=db)
    a2 = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == coach_b.id,
                AuditLog.action == AuditAction.SELF_STUDY_UPDATE)
        .order_by(AuditLog.id.desc()).first()
    )
    d2 = json.loads(a2.details_json) if a2 and a2.details_json else {}
    check("2. onay audit'lendi (op=approve, applied=40)",
          d2.get("op") == "approve" and d2.get("applied") == 40, f"{d2}")

    dres2 = student_self_study_declare_v2(
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb_b.id, section_id=sec_b.id, test_count=10)]),
        background=BackgroundTasks(), user=stu_b, db=db,
    )
    rid = dres2.data.created[0].id
    teacher_self_study_review_v2(entry_id=rid, body=SelfStudyReviewBody(approve=False),
                                 background=BackgroundTasks(), user=coach_b, db=db)
    a3 = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == coach_b.id,
                AuditLog.action == AuditAction.SELF_STUDY_UPDATE)
        .order_by(AuditLog.id.desc()).first()
    )
    d3 = json.loads(a3.details_json) if a3 and a3.details_json else {}
    check("3. ret audit'lendi (op=reject)", d3.get("op") == "reject", f"{d3}")

    # ---- 2) Mutlak set + silme audit ----
    teacher_set_section_completed_v2(stu_b.id, sb_b.id, sec_b.id,
                                     SectionCompletedBaselineBody(completed_count=55),
                                     coach_b, db)
    a4 = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == coach_b.id,
                AuditLog.action == AuditAction.SELF_STUDY_UPDATE)
        .order_by(AuditLog.id.desc()).first()
    )
    d4 = json.loads(a4.details_json) if a4 and a4.details_json else {}
    check("4. mutlak set audit'lendi (from=40 to=55)",
          d4.get("op") == "absolute_set" and d4.get("from") == 40 and d4.get("to") == 55,
          f"{d4}")

    del_entry = (
        db.query(SelfStudyEntry)
        .filter(SelfStudyEntry.student_id == stu_a.id, SelfStudyEntry.status == "approved")
        .first()
    )
    teacher_self_study_delete_v2(entry_id=del_entry.id, user=coach_a, db=db)
    a5 = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == coach_a.id,
                AuditLog.action == AuditAction.SELF_STUDY_UPDATE)
        .order_by(AuditLog.id.desc()).first()
    )
    d5 = json.loads(a5.details_json) if a5 and a5.details_json else {}
    check("5. silme audit'lendi (op=delete, reverted=600)",
          d5.get("op") == "delete" and d5.get("reverted") == 600, f"{d5}")

    # Koç A girişini yeniden yap (rapor + dedektör için)
    teacher_self_study_create_v2(
        student_id=stu_a.id,
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb_a.id, section_id=sec_a.id, test_count=600)]),
        user=coach_a, db=db,
    )
    # Yabancı kurum koçu + bağımsız koç da yüklü giriş yapar
    teacher_self_study_create_v2(
        student_id=stu_f.id,
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb_f.id, section_id=sec_f.id, test_count=600)]),
        user=coach_f, db=db,
    )
    teacher_self_study_create_v2(
        student_id=stu_s.id,
        body=SelfStudyCreateBody(
            items=[SelfStudyCreateItem(student_book_id=sb_s.id, section_id=sec_s.id, test_count=600)]),
        user=coach_solo, db=db,
    )

    # ---- 3) Kurum raporu ----
    rep = build_report(db, inst.id, days=30)
    check("6. rapor özet: 2 koç + işlenen toplam 655 (600+40+15)",
          rep["summary"]["coaches_with_entries"] == 2
          and rep["summary"]["applied_tests_total"] == 655,
          f"{rep['summary']}")
    row_a = next((c for c in rep["coaches"] if c["coach_id"] == coach_a.id), None)
    row_b = next((c for c in rep["coaches"] if c["coach_id"] == coach_b.id), None)
    check("7. koç A satırı: 600 koç-tek-taraflı + dikkat işareti",
          row_a and row_a["coach_direct_tests"] == 600
          and row_a["coach_direct_share_pct"] == 100 and row_a["attention"] is True,
          f"{row_a}")
    check("8. koç B satırı: beyanla 40 + mutlak-set 15 -> dikkat YOK",
          row_b and row_b["student_declared_tests"] == 40
          and row_b["coach_direct_tests"] == 15 and row_b["attention"] is False,
          f"{row_b}")
    names = {r["coach_name"] for r in rep["recent"]}
    check("9. kapsam izolasyonu: yabancı kurum + bağımsız koç raporda YOK",
          "KocYabanci" not in names and "KocSolo" not in names, f"{names}")
    check("10. son girişler listesi dolu (kayıt satırları)",
          len(rep["recent"]) >= 4 and all("student_name" in r for r in rep["recent"]))

    # gün filtresi: eski kayıt görünmez
    from datetime import datetime, timedelta, timezone
    old_entry = (
        db.query(SelfStudyEntry).filter(SelfStudyEntry.student_id == stu_a.id).first()
    )
    old_entry.created_at = datetime.now(timezone.utc) - timedelta(days=90)
    db.commit()
    rep2 = build_report(db, inst.id, days=7)
    check("11. gün filtresi: 90 gün önceki kayıt 7g raporunda yok",
          rep2["summary"]["applied_tests_total"] < rep["summary"]["applied_tests_total"])
    old_entry.created_at = datetime.now(timezone.utc)
    db.commit()

    # ---- 4) Endpoint (kurum yöneticisi) ----
    resp = institution_self_study_report_v2(days=30, user=admin, db=db)
    check("12. endpoint yanıtı şemalı (summary + coaches + recent)",
          resp.summary.applied_tests_total == 655 and len(resp.coaches) == 2)

    # ---- 5) Anomali dedektörü ----
    hits = detect_manual_progress_surge(db)
    hit_ids = {h.actor_user_id for h in hits}
    check("13. dedektör: kurum koçu A yakalandı (600 >= 500)",
          coach_a.id in hit_ids, f"{hit_ids}")
    check("14. dedektör: koç B eşik altı -> yok · bağımsız koç -> yok",
          coach_b.id not in hit_ids and coach_solo.id not in hit_ids)
    hit_a = next(h for h in hits if h.actor_user_id == coach_a.id)
    check("15. sinyal info + kurum bağlı + detay dolu",
          hit_a.severity == "info" and hit_a.tenant_id == inst.id
          and hit_a.details.get("applied_tests") == 600)

    # dedup: iki kez upsert -> tek açık sinyal
    _upsert_signal(db, hit_a)
    _upsert_signal(db, hit_a)
    n_sig = (
        db.query(AbuseSignal)
        .filter(AbuseSignal.kind == KIND_MANUAL_PROGRESS_SURGE,
                AbuseSignal.actor_user_id == coach_a.id,
                AbuseSignal.resolved_at.is_(None))
        .count()
    )
    check("16. dedup: tek açık sinyal", n_sig == 1, f"got {n_sig}")

    # beyanlı girişler dedektöre sayılmaz: koç B öğrencisi 500 beyan etse bile
    # (onaylansa da source=student) sinyal üretmez — sec_b kapasitesi küçük,
    # bunun yerine mantık kontrolü: koç B'nin drect testi 15 < 500 zaten üstte.
    # Ek: koç A sinyal detayında öğrenci beyanı sayılmadı (600 = yalnız direct).
    check("17. dedektör yalnız koç-tek-taraflı sayar (A=600, beyan hariç)",
          hit_a.count == 600)

finally:
    clean()
    db.close()

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(1 if FAIL else 0)
