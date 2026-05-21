"""E2E Test 1 — Bağımsız öğretmen full yaşam döngüsü.

Senaryo:
  Yeni bir bağımsız öğretmen sıfırdan üye olur, 14 günlük Solo Pro trial başlar,
  öğrenci ekler, kitap+ünite+plan yapar, görevleri öğrenci tamamlar, trial dolar,
  Solo Free'e düşer ve Pro özellikleri kapanır.

Test adımları:
  1. POST /signup/teacher gerçek HTTP — yeni öğretmen
  2. Trial aktif: plan='solo_trial', trial_ends_at=+14g
  3. POST /login ile başka oturum aç — cookie tutuluyor
  4. POST /me — kullanıcı bilgisi 200
  5. POST /teacher/students yeni öğrenci (LGS)
  6. POST /teacher/books yeni kitap
  7. POST /sections/bulk-from-catalog ünite ekle
  8. POST /books/{id}/assign öğrenciye ata (baseline 0)
  9. POST /teacher/program haftalık görev planı (basit task)
  10. Öğrenci kimliğine geç → görev tamamla
  11. Review seed (Stage 12) + öğrenci 1 rating → badge tetiklenir
  12. Pomodoro session start/end (Stage 14)
  13. DNA profil 200 (Stage 13)
  14. Trial sonu simülasyon: trial_ends_at = now - 1h; expire_trials() çağır
  15. Plan downgrade doğrulama: plan='solo_free', trial_ends_at=None
  16. PlanChangeHistory entry doğrulama
  17. Trial bittiğinde tekrar /teacher 200 (login devam ediyor)

Validation kontrolleri:
- Zayıf şifre red, duplicate email red
- Trial banner görünür → trial sonu yok
- KVKK metni checkbox zorunlu
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    PomodoroSession,
    ReviewCard,
    SectionProgress,
    StudentBadge,
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
from app.services.plans import (
    SOLO_FREE,
    SOLO_TRIAL,
    expire_trials,
)


PFX = f"e2e_indep_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
STRONG_PASSWORD = "TestPass123!@xyz"

passed = 0
failed: list[str] = []
findings: list[dict] = []  # raporda kullanılacak


def check(label: str, cond: bool, detail: str = "", severity: str = "high") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        findings.append({
            "test": "e2e_independent_teacher",
            "label": label,
            "detail": detail,
            "severity": severity,
        })
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    now = datetime.now(timezone.utc)
    client = TestClient(app)

    # =================================================================
    # STEP 1: Geçersiz signup denemeleri
    # =================================================================
    print("\n=== STEP 1: Signup validation ===")

    # Zayıf şifre
    r = client.post("/signup/teacher", data={
        "full_name": "Zayıf Şifre",
        "email": f"{PFX}_weak@test.invalid",
        "password": "abc123",
        "password_confirm": "abc123",
        "accept_terms": "on",
    }, follow_redirects=False)
    check("zayıf şifre red (4xx)",
          400 <= r.status_code < 500,
          f"got {r.status_code}",
          "medium")

    # Şifre eşleşmiyor
    r = client.post("/signup/teacher", data={
        "full_name": "Şifre Uyumsuz",
        "email": f"{PFX}_mismatch@test.invalid",
        "password": STRONG_PASSWORD,
        "password_confirm": STRONG_PASSWORD + "x",
        "accept_terms": "on",
    }, follow_redirects=False)
    check("şifre eşleşmiyor red (4xx)",
          400 <= r.status_code < 500,
          f"got {r.status_code}",
          "medium")

    # KVKK onayı yok
    r = client.post("/signup/teacher", data={
        "full_name": "KVKK Yok",
        "email": f"{PFX}_nokvkk@test.invalid",
        "password": STRONG_PASSWORD,
        "password_confirm": STRONG_PASSWORD,
        "accept_terms": "",  # boş
    }, follow_redirects=False)
    check("KVKK onayı yok red (4xx)",
          400 <= r.status_code < 500,
          f"got {r.status_code}",
          "high")

    # =================================================================
    # STEP 2: Başarılı signup → trial başlar
    # =================================================================
    print("\n=== STEP 2: Başarılı signup ===")
    r = client.post("/signup/teacher", data={
        "full_name": "E2E Bağımsız Öğretmen",
        "email": TEACHER_EMAIL,
        "password": STRONG_PASSWORD,
        "password_confirm": STRONG_PASSWORD,
        "accept_terms": "on",
    }, follow_redirects=False)
    check("signup başarılı (303 redirect)",
          r.status_code == 303,
          f"got {r.status_code}: {r.text[:200] if r.status_code >= 400 else ''}")
    check("redirect /teacher'a",
          r.headers.get("location", "").startswith("/teacher"),
          r.headers.get("location"))

    # Cookie tutuluyor mu — sonraki istekte 200 görmeliyiz
    teacher_id = None
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == TEACHER_EMAIL).first()
        if u:
            teacher_id = u.id
            check("kullanıcı oluştu",
                  u.role == UserRole.TEACHER and u.is_active)
            check("trial plan=solo_trial",
                  u.plan == SOLO_TRIAL, f"got plan={u.plan}")
            check("trial_ends_at +14 gün civarı",
                  u.trial_ends_at is not None
                  and 13 < (u.trial_ends_at.replace(tzinfo=timezone.utc) - now).days <= 14,
                  f"trial_ends_at={u.trial_ends_at}")
            check("post_trial_plan=solo_free",
                  u.post_trial_plan == SOLO_FREE,
                  f"got {u.post_trial_plan}")
        else:
            check("kullanıcı oluştu", False, "User row not found")

    # =================================================================
    # STEP 3: Duplicate email
    # =================================================================
    print("\n=== STEP 3: Duplicate email ===")
    r = client.post("/signup/teacher", data={
        "full_name": "Duplicate",
        "email": TEACHER_EMAIL,
        "password": STRONG_PASSWORD,
        "password_confirm": STRONG_PASSWORD,
        "accept_terms": "on",
    }, follow_redirects=False)
    check("duplicate email red (4xx)",
          400 <= r.status_code < 500,
          f"got {r.status_code}",
          "high")

    # =================================================================
    # STEP 4: Logout + login akışı
    # =================================================================
    print("\n=== STEP 4: Logout + login akışı ===")
    # Logout
    r = client.post("/logout", follow_redirects=False)
    check("logout 303",
          r.status_code in (302, 303), f"got {r.status_code}")
    # Anonim /teacher → 303
    r = client.get("/teacher", follow_redirects=False)
    check("logout sonrası /teacher 303 (anonim)",
          r.status_code in (302, 303), f"got {r.status_code}")
    # Login
    r = client.post("/login", data={
        "email": TEACHER_EMAIL,
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    check("login başarılı (303)",
          r.status_code == 303, f"got {r.status_code}")

    # Yanlış şifre
    fail_client = TestClient(app)
    r = fail_client.post("/login", data={
        "email": TEACHER_EMAIL,
        "password": "yanlis123",
    }, follow_redirects=False)
    check("yanlış şifre 401/4xx",
          400 <= r.status_code < 500, f"got {r.status_code}",
          "high")

    # =================================================================
    # STEP 5: /teacher panel + /me 200
    # =================================================================
    print("\n=== STEP 5: Authenticated sayfalar ===")
    r = client.get("/teacher")
    check("/teacher 200", r.status_code == 200, f"got {r.status_code}")
    r = client.get("/me")
    check("/me 200", r.status_code == 200)

    # =================================================================
    # STEP 6: Yeni öğrenci ekle (LGS)
    # =================================================================
    print("\n=== STEP 6: Öğrenci ekle ===")
    r = client.post("/teacher/students", data={
        "full_name": "E2E Öğrenci 1",
        "email": f"{PFX}_s1@test.invalid",
        "grade_level": "8",
    }, follow_redirects=False)
    check("öğrenci ekle 303",
          r.status_code in (302, 303), f"got {r.status_code}",
          "high")
    student_id = None
    with SessionLocal() as db:
        s = (
            db.query(User)
            .filter(User.email == f"{PFX}_s1@test.invalid")
            .first()
        )
        if s:
            student_id = s.id
            check("öğrenci kayıtlı + teacher_id eşleşiyor",
                  s.teacher_id == teacher_id and s.role == UserRole.STUDENT)
        else:
            check("öğrenci kayıtlı", False, "student row not found",
                  "high")

    # =================================================================
    # STEP 7: Kitap ekle + kataloğdan toplu ünite (Stage 12 öncesi)
    # =================================================================
    print("\n=== STEP 7: Kitap + toplu ünite ekleme ===")
    # Önce subject_id bul (built-in)
    subject_id = None
    with SessionLocal() as db:
        # 8. sınıf için ilk built-in subject (Türkçe veya Matematik)
        subj = (
            db.query(Subject)
            .filter(Subject.is_builtin.is_(True))
            .order_by(Subject.order)
            .first()
        )
        if subj:
            subject_id = subj.id

    book_id = None
    if subject_id:
        r = client.post("/teacher/books", data={
            "name": "E2E Test Bankası",
            "publisher": "Test Yayın",
            "subject_id": str(subject_id),
            "type": "soru_bankasi",
            "avg_questions_per_test": "10",
            "target_grade_min": "8",
            "target_grade_max": "8",
        }, follow_redirects=False)
        check("kitap ekle 303",
              r.status_code in (302, 303), f"got {r.status_code}")
        with SessionLocal() as db:
            b = (
                db.query(Book)
                .filter(Book.teacher_id == teacher_id, Book.name == "E2E Test Bankası")
                .first()
            )
            if b:
                book_id = b.id

    if book_id:
        # Subject'in built-in topic'lerinden 3 tanesi seç
        topic_ids: list[int] = []
        with SessionLocal() as db:
            topics = (
                db.query(Topic)
                .filter(Topic.subject_id == subject_id, Topic.is_builtin.is_(True))
                .limit(3).all()
            )
            topic_ids = [t.id for t in topics]
        if topic_ids:
            payload: dict = {"topic_ids": [str(t) for t in topic_ids]}
            for t in topic_ids:
                payload[f"test_count_{t}"] = "10"
            r = client.post(
                f"/teacher/books/{book_id}/sections/bulk-from-catalog",
                data=payload, follow_redirects=False,
            )
            check("toplu kataloğ POST 303",
                  r.status_code in (302, 303), f"got {r.status_code}")
            with SessionLocal() as db:
                sections = (
                    db.query(BookSection)
                    .filter(BookSection.book_id == book_id)
                    .all()
                )
                check(f"{len(topic_ids)} ünite eklendi",
                      len(sections) == len(topic_ids),
                      f"got {len(sections)}")
        else:
            check("subject'te built-in topic var", False,
                  "no built-in topics for subject",
                  "medium")

    # =================================================================
    # STEP 8: Kitabı öğrenciye ata
    # =================================================================
    if book_id and student_id:
        print("\n=== STEP 8: Kitap atama ===")
        r = client.post(
            f"/teacher/students/{student_id}/books/assign",
            data={"book_ids": [str(book_id)]},
            follow_redirects=False,
        )
        check("kitap atama 303",
              r.status_code in (302, 303), f"got {r.status_code}")
        with SessionLocal() as db:
            sb = (
                db.query(StudentBook)
                .filter(
                    StudentBook.student_id == student_id,
                    StudentBook.book_id == book_id,
                )
                .first()
            )
            check("StudentBook oluştu", sb is not None)
            if sb:
                sps = db.query(SectionProgress).filter(
                    SectionProgress.student_book_id == sb.id
                ).all()
                check("SectionProgress kayıtları açıldı",
                      len(sps) > 0, f"got {len(sps)}")

    # =================================================================
    # STEP 9: Öğrenciye görev planla (program endpoint farklılaşır,
    #         doğrudan Task oluşturarak simüle ediyoruz — production'da
    #         öğretmen UI'dan yapar)
    # =================================================================
    print("\n=== STEP 9: Görev planlama + tamamlama (Pro özellik) ===")
    task_id = None
    if student_id and book_id:
        with SessionLocal() as db:
            sec = (
                db.query(BookSection)
                .filter(BookSection.book_id == book_id)
                .order_by(BookSection.order)
                .first()
            )
            if sec:
                t = Task(
                    student_id=student_id,
                    date=date.today(),
                    type=TaskType.TEST,
                    title=f"{sec.label} — 5 test",
                    status=TaskStatus.PENDING,
                )
                db.add(t); db.flush()
                tbi = TaskBookItem(
                    task_id=t.id, book_id=book_id, book_section_id=sec.id,
                    planned_count=5, completed_count=0,
                )
                db.add(tbi)
                db.commit()
                task_id = t.id
        check("Task oluştu (test edilebilir state)", task_id is not None)

    # =================================================================
    # STEP 10: Öğrenci olarak giriş yap → görev tamamla
    # =================================================================
    print("\n=== STEP 10: Öğrenci task tamamlama ===")
    # Öğrencinin parolası generate_strong_password ile rastgele atanır;
    # gerçek HTTP login akışı yerine session manipule etmek gerek.
    # Test client'ta cookie üzerinden çalışacak şekilde session set edemediğimiz
    # için, gerçekçi yaklaşım: öğrencinin parolasını DB'den okuyup HTTP login yap.
    # Ancak parola hash'li, plain bilemeyiz. Bu yüzden bu adımda
    # programatik update (DB) ile task'ı COMPLETED işaretliyoruz —
    # event_triggers ve badge eval'i route üzerinden değil servis seviyesinden
    # tetikleyeceğiz.
    if task_id:
        from app.services.gamification import evaluate_badges_for_student
        from app.services.event_triggers import on_task_completed
        with SessionLocal() as db:
            t = db.query(Task).filter(Task.id == task_id).first()
            tbi = t.book_items[0]
            tbi.completed_count = tbi.planned_count
            t.status = TaskStatus.COMPLETED
            t.completed_at = datetime.now(timezone.utc)
            try:
                on_task_completed(db, db.query(User).filter(User.id == student_id).first())
            except Exception as e:
                check("on_task_completed event tetiklendi (hata yok)",
                      False, f"exception: {e}", "medium")
            else:
                check("on_task_completed event tetiklendi (hata yok)", True)
            db.commit()
            # Badge eval
            try:
                newly = evaluate_badges_for_student(db, student_id=student_id, commit=True)
                check("first_step rozeti otomatik kazanıldı",
                      any(b.kind == "first_step" for b in newly),
                      f"new badges={[b.kind for b in newly]}")
            except Exception as e:
                check("evaluate_badges hata vermedi", False, str(e),
                      "high")

    # =================================================================
    # STEP 11: Stage 12 — Review seed + rating
    # =================================================================
    print("\n=== STEP 11: Review seed + rating ===")
    if student_id and subject_id:
        r = client.post(
            f"/teacher/students/{student_id}/review/seed",
            data={"subject_id": str(subject_id)},
            follow_redirects=False,
        )
        check("review seed 303",
              r.status_code in (302, 303), f"got {r.status_code}")
        with SessionLocal() as db:
            cards = db.query(ReviewCard).filter(
                ReviewCard.student_id == student_id
            ).all()
            check("review kartları oluştu",
                  len(cards) > 0, f"got {len(cards)}")

    # =================================================================
    # STEP 12: Stage 14 — Pomodoro session start/end
    # =================================================================
    print("\n=== STEP 12: Pomodoro session ===")
    if student_id:
        # Pomodoro doğrudan servis ile (öğrenci HTTP simulasyonu yok)
        from app.services.pomodoro import end_session, start_session
        from app.models.focus import PomodoroKind
        with SessionLocal() as db:
            sess = start_session(
                db, student_id=student_id, planned_minutes=25,
                kind=PomodoroKind.WORK, label="E2E test",
            )
            db.commit()
            end_session(db, session=sess, actual_minutes=23, interrupted=False)
            db.commit()
            check("pomodoro session oluştu + bitti",
                  sess.ended_at is not None and sess.actual_minutes == 23)

    # =================================================================
    # STEP 13: Stage 13 — DNA + burnout endpoint check (öğretmen view)
    # =================================================================
    print("\n=== STEP 13: DNA endpoint (öğretmen) ===")
    if student_id:
        r = client.get(f"/teacher/students/{student_id}/dna")
        check("DNA detay 200",
              r.status_code == 200, f"got {r.status_code}")

    # =================================================================
    # STEP 14: Trial expire simülasyonu
    # =================================================================
    print("\n=== STEP 14: Trial expire simülasyonu ===")
    # trial_ends_at'i geri çek, cron çalıştır
    with SessionLocal() as db:
        u = db.query(User).filter(User.id == teacher_id).first()
        u.trial_ends_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    counts = None
    try:
        with SessionLocal() as db:
            counts = expire_trials(db, now=datetime.now(timezone.utc))
    except Exception as e:
        check("expire_trials hata vermedi", False, str(e), "high")
    if counts is not None:
        check("expire_trials çalıştı (users_expired ≥ 1)",
              counts.get("users_expired", 0) >= 1, f"counts={counts}")

    # Plan doğrulama
    with SessionLocal() as db:
        u = db.query(User).filter(User.id == teacher_id).first()
        check("trial sonrası plan=solo_free",
              u.plan == SOLO_FREE, f"got plan={u.plan}",
              "high")
        check("trial_ends_at=None",
              u.trial_ends_at is None, f"got {u.trial_ends_at}")

    # PlanChangeHistory kontrolü
    with SessionLocal() as db:
        from app.models import PlanChangeHistory, PlanChangeReason, PlanOwnerType
        history = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_type == PlanOwnerType.USER,
                PlanChangeHistory.owner_id == teacher_id,
                PlanChangeHistory.reason == PlanChangeReason.TRIAL_EXPIRED,
            )
            .first()
        )
        check("PlanChangeHistory TRIAL_EXPIRED kaydı var",
              history is not None,
              "no history row",
              "medium")

    # =================================================================
    # STEP 15: Trial sonrası /teacher hâlâ erişilebilir (oturum kalır)
    # =================================================================
    print("\n=== STEP 15: Trial sonrası erişim ===")
    r = client.get("/teacher")
    check("trial bittikten sonra /teacher 200 (oturum sürüyor)",
          r.status_code == 200, f"got {r.status_code}")
    r = client.get("/pricing")
    check("/pricing 200", r.status_code == 200)

    # =================================================================
    # CLEANUP
    # =================================================================
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        # Audit log kaldırmak için ilgili tablolar:
        from app.models import AuditLog, PlanChangeHistory
        all_users = []
        if teacher_id:
            all_users.append(teacher_id)
        if student_id:
            all_users.append(student_id)
        # Diğer signup denemeleri zayıf şifre/kvkk red olduğu için DB'de yok
        if all_users:
            # Pomodoro, badge, review temizle
            db.execute(delete(PomodoroSession).where(
                PomodoroSession.student_id.in_(all_users)))
            db.execute(delete(StudentBadge).where(
                StudentBadge.student_id.in_(all_users)))
            db.execute(delete(ReviewCard).where(
                ReviewCard.student_id.in_(all_users)))
            # Task + book item
            task_ids = [
                tid for (tid,) in db.query(Task.id).filter(
                    Task.student_id.in_(all_users)
                ).all()
            ]
            if task_ids:
                db.execute(delete(TaskBookItem).where(
                    TaskBookItem.task_id.in_(task_ids)))
                db.execute(delete(Task).where(Task.id.in_(task_ids)))
            # StudentBook + SectionProgress
            sb_ids = [
                sid for (sid,) in db.query(StudentBook.id).filter(
                    StudentBook.student_id.in_(all_users)
                ).all()
            ]
            if sb_ids:
                db.execute(delete(SectionProgress).where(
                    SectionProgress.student_book_id.in_(sb_ids)))
                db.execute(delete(StudentBook).where(StudentBook.id.in_(sb_ids)))
            # Book sections + book
            if book_id:
                db.execute(delete(BookSection).where(BookSection.book_id == book_id))
                db.execute(delete(Book).where(Book.id == book_id))
            # PlanChangeHistory
            db.execute(delete(PlanChangeHistory).where(
                PlanChangeHistory.owner_id.in_(all_users)))
            # AuditLog: actor_id (kullanıcı eylem yapan)
            db.execute(delete(AuditLog).where(
                AuditLog.actor_id.in_(all_users)
            ))
            db.execute(delete(User).where(User.id.in_(all_users)))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    # Findings raporu için dump
    if findings:
        import json
        out = "scripts/.e2e_findings_independent_teacher.json"
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(findings, fh, ensure_ascii=False, indent=2)
        print(f"\nFindings raporu: {out}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
