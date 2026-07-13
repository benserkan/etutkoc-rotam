"""Yanlış Soru Arşivi (Faz 1) smoke — model + servis + API uçtan uca.

Kapsam:
- Öğrenci: foto ile / fotosuz ekleme, bağlamdan otomatik konu etiketi,
  görev/deneme bağlama, filtre + sayaçlar, etiket düzeltme, yeniden çözme
  (FSRS + kapanış + yeniden açılma + aynı-gün streak koruması), foto servisi,
  silme (cascade).
- Koç: liste + özet analitik + öğrenci adına kayıt + koç açıklaması + foto.
- Güvenlik: anonim 401, veli 403, yabancı koç 404 (sızıntı yok), yabancı
  öğrenci kaydına erişim 404, dosya tipi/boyut kapıları.
- Öneri beslemesi: open_wrong_topic_map sözleşmesi.
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
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    ExamResult,
    StudentBook,
    Subject,
    SuspiciousIp,
    Task,
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
    WrongQuestion,
    WrongQuestionImage,
    compute_net,
)
from app.models.exam_result import ExamSection
from app.services import wrong_question_service as svc
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"wq{secrets.token_hex(3)}"
PASSWORD = "Wrong!2026X"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200   # sahte ama tip-etiketli küçük görsel
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
    print(f"\n=== wrong questions smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_free", must_change_password=False)
        coach2 = User(email=f"{PFX}-t2@t.invalid", password_hash=hash_password(PASSWORD),
                      full_name="Yabancı Koç", role=UserRole.TEACHER, is_active=True,
                      plan="solo_free", must_change_password=False)
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True,
                       grade_level=10, must_change_password=False)
        parent = User(email=f"{PFX}-p@t.invalid", password_hash=hash_password(PASSWORD),
                      full_name="Veli", role=UserRole.PARENT, is_active=True,
                      must_change_password=False)
        db.add_all([coach, coach2, student, parent]); db.flush()
        student.teacher_id = coach.id
        subj = Subject(name=f"{PFX} Matematik", order=999, is_builtin=False,
                       teacher_id=coach.id)
        db.add(subj); db.flush()
        t1 = Topic(name="Konu 1", order=1, subject_id=subj.id)
        t2 = Topic(name="Konu 2", order=2, subject_id=subj.id)
        db.add_all([t1, t2]); db.flush()
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id,
                    type=BookType.SORU_BANKASI, teacher_id=coach.id)
        db.add(book); db.flush()
        sec1 = BookSection(book_id=book.id, label="Bölüm 1", test_count=10,
                           order=1, topic_id=t1.id)
        db.add(sec1); db.flush()
        db.add(StudentBook(student_id=student.id, book_id=book.id))
        task = Task(student_id=student.id, date=date.today(), type=TaskType.TEST,
                    title="Görev", status=TaskStatus.PENDING, order=0, is_draft=False)
        db.add(task); db.flush()
        exam = ExamResult(student_id=student.id, created_by_id=coach.id,
                          title="TYT Deneme 1", exam_date=date.today(),
                          section=ExamSection.TYT, total_correct=80,
                          total_wrong=20, total_blank=20,
                          net=compute_net(80, 20, ExamSection.TYT))
        db.add(exam); db.commit()
        ids = {"coach": coach.id, "coach2": coach2.id, "student": student.id,
               "parent": parent.id, "subj": subj.id, "t1": t1.id, "t2": t2.id,
               "book": book.id, "sec1": sec1.id, "task": task.id, "exam": exam.id}

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    try:
        cs = TestClient(app)   # öğrenci
        ct = TestClient(app)   # koç
        cf = TestClient(app)   # yabancı koç
        cp = TestClient(app)   # veli
        ca = TestClient(app)   # anonim

        # --- Girişler + rol kapıları ---
        r = cs.post("/api/v2/auth/login", json={"email": f"{PFX}-s@t.invalid", "password": PASSWORD})
        check("1. öğrenci login", r.status_code == 200, r.text[:120])
        ct.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        cf.post("/api/v2/auth/login", json={"email": f"{PFX}-t2@t.invalid", "password": PASSWORD})
        cp.post("/api/v2/auth/login", json={"email": f"{PFX}-p@t.invalid", "password": PASSWORD})
        check("2. anonim liste 401", ca.get("/api/v2/student/wrong-questions").status_code == 401)
        check("3. veli erişemez 403 (özel çalışma alanı)",
              cp.get("/api/v2/student/wrong-questions").status_code == 403)

        # --- Foto + bölüm bağlamıyla ekleme → konu otomatik ---
        r = cs.post(
            "/api/v2/student/wrong-questions",
            data={"book_section_id": str(ids["sec1"])},
            files=[("photos", ("soru.png", PNG, "image/png"))],
        )
        check("4. foto+bölüm ile ekleme 200", r.status_code == 200, r.text[:200])
        wq1 = r.json()["data"]
        ids["wq1"] = wq1["id"]
        check("5. bölümden KONU otomatik etiketlendi (sıfır sürtünme)",
              wq1["topic_id"] == ids["t1"] and wq1["subject_id"] == ids["subj"]
              and wq1["book_name"] and wq1["section_label"] == "Bölüm 1",
              f"topic={wq1['topic_id']}")
        check("6. foto kaydedildi + due yarına kuruldu (taze yanlış hemen sorulmaz)",
              len(wq1["images"]) == 1 and wq1["due_at"] is not None
              and wq1["is_due"] is False and wq1["status"] == "acik",
              f"imgs={len(wq1['images'])}, due={wq1['due_at']}")

        # --- Fotosuz hızlı kayıt + görev/deneme bağlama ---
        r = cs.post("/api/v2/student/wrong-questions",
                    data={"task_id": str(ids["task"]), "error_type": "islem"})
        check("7. fotosuz+görev bağlamlı kayıt → source=gorev",
              r.status_code == 200 and r.json()["data"]["source_kind"] == "gorev",
              r.text[:150])
        ids["wq2"] = r.json()["data"]["id"]
        r = cs.post("/api/v2/student/wrong-questions",
                    data={"exam_result_id": str(ids["exam"]), "topic_id": str(ids["t1"])})
        check("8. deneme bağlamlı kayıt → source=deneme + konu elle",
              r.status_code == 200 and r.json()["data"]["source_kind"] == "deneme",
              r.text[:150])
        ids["wq3"] = r.json()["data"]["id"]

        # --- Dosya kapıları ---
        r = cs.post("/api/v2/student/wrong-questions",
                    files=[("photos", ("v.pdf", b"%PDF", "application/pdf"))])
        check("9. PDF/yanlış tip → 422 invalid_image_type",
              r.status_code == 422 and r.json()["detail"]["code"] == "invalid_image_type",
              r.text[:150])
        old_max = svc.MAX_IMAGE_BYTES
        svc.MAX_IMAGE_BYTES = 64
        r = cs.post("/api/v2/student/wrong-questions",
                    files=[("photos", ("big.png", PNG, "image/png"))])
        svc.MAX_IMAGE_BYTES = old_max
        check("10. boyut tavanı → 422 image_too_large",
              r.status_code == 422 and r.json()["detail"]["code"] == "image_too_large",
              r.text[:150])

        # --- Liste + sayaçlar + filtre ---
        r = cs.get("/api/v2/student/wrong-questions")
        d = r.json()
        check("11. liste + sayaçlar (3 kayıt, hepsi açık, due=0)",
              d["counts"]["total"] == 3 and d["counts"]["open"] == 3
              and d["counts"]["due"] == 0 and len(d["items"]) == 3,
              f"counts={d['counts']}")
        r = cs.get(f"/api/v2/student/wrong-questions?error_type=islem")
        check("12. hata türü filtresi", len(r.json()["items"]) == 1)

        # --- Vade + due filtresi (due_at'i geçmişe çek) ---
        with SessionLocal() as db:
            w = db.get(WrongQuestion, ids["wq1"])
            w.due_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.commit()
        r = cs.get("/api/v2/student/wrong-questions?due=true")
        check("13. vadesi gelen 'yeniden çöz' kuyruğu (1 kayıt)",
              r.json()["counts"]["due"] == 1 and len(r.json()["items"]) == 1
              and r.json()["items"][0]["id"] == ids["wq1"],
              r.text[:150])

        # --- Yeniden çözme: FSRS + kapanış mekaniği ---
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq1']}/attempt",
                    json={"rating": 3})
        d = r.json()["data"]
        check("14. çözdüm(3) → streak=1, hâlâ açık, yeni vade kuruldu",
              r.status_code == 200 and d["correct_streak"] == 1
              and d["status"] == "acik" and d["due_at"] is not None,
              r.text[:200])
        # aynı gün ikinci 'çözdüm' → streak ŞİŞMEZ (gap < 20 saat)
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq1']}/attempt",
                    json={"rating": 3})
        check("15. aynı gün tekrar basma streak'i şişirmez",
              r.json()["data"]["correct_streak"] == 1,
              f"streak={r.json()['data']['correct_streak']}")
        # 2 gün sonra ikinci başarılı → KAPANIR (servis seviyesi, zaman kontrollü)
        with SessionLocal() as db:
            w = db.get(WrongQuestion, ids["wq1"])
            svc.record_attempt(db, w, 3,
                               now=datetime.now(timezone.utc) + timedelta(days=2))
            db.commit()
            check("16. aralıklı 2. başarılı çözüm → KAPANDI + closed_at",
                  w.status == "kapandi" and w.closed_at is not None
                  and w.correct_streak == 2,
                  f"status={w.status} streak={w.correct_streak}")
            # 5 gün sonra yine yanlış → YENİDEN AÇILIR
            svc.record_attempt(db, w, 1,
                               now=datetime.now(timezone.utc) + timedelta(days=5))
            db.commit()
            check("17. kapalı soruya 'yine yanlış' → yeniden AÇILIR + streak 0",
                  w.status == "acik" and w.closed_at is None and w.correct_streak == 0,
                  f"status={w.status}")

        # --- Etiket düzeltme ---
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq2']}",
                    json={"topic_id": ids["t2"], "note": "üslü sayılarda dağılma"})
        d = r.json()["data"]
        check("18. konu değişimi ders'i de günceller + not yazılır",
              d["topic_id"] == ids["t2"] and d["subject_id"] == ids["subj"]
              and d["note"] == "üslü sayılarda dağılma", r.text[:150])
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq2']}",
                    json={"error_type": "sacmasapan"})
        check("19. geçersiz hata türü 422", r.status_code == 422)

        # --- Foto servisi + erişim izolasyonu ---
        img_id = wq1["images"][0]["id"]
        r = cs.get(f"/api/v2/student/wrong-questions/{ids['wq1']}/images/{img_id}")
        check("20. öğrenci kendi fotoğrafını görür (image/png)",
              r.status_code == 200 and r.headers["content-type"].startswith("image/png"))
        r = ct.get(f"/api/v2/teacher/wrong-questions/{ids['wq1']}/images/{img_id}")
        check("21. koç öğrencisinin fotoğrafını görür", r.status_code == 200)
        r = cf.get(f"/api/v2/teacher/wrong-questions/{ids['wq1']}/images/{img_id}")
        check("22. YABANCI koç 404 (varlık sızıntısı yok)", r.status_code == 404)

        # --- Koç yüzü: liste + özet + koç kaydı + koç notu ---
        r = ct.get(f"/api/v2/teacher/students/{ids['student']}/wrong-questions")
        check("23. koç listesi 200 + 3 kayıt",
              r.status_code == 200 and r.json()["counts"]["total"] == 3, r.text[:150])
        r = cf.get(f"/api/v2/teacher/students/{ids['student']}/wrong-questions")
        check("24. yabancı koç öğrenci listesine 404", r.status_code == 404)
        r = ct.get(f"/api/v2/teacher/students/{ids['student']}/wrong-questions/summary")
        s = r.json()
        topic_ids = {t["topic_id"] for t in s["by_topic"]}
        check("25. koç özeti: konu birikimi + hata türü dağılımı + 30g sayaçları",
              r.status_code == 200 and ids["t1"] in topic_ids
              and s["by_error_type"].get("islem") == 1
              and s["added_last_30d"] == 3,
              r.text[:250])
        r = ct.post(f"/api/v2/teacher/students/{ids['student']}/wrong-questions",
                    json={"topic_id": ids["t1"], "error_type": "bilgi",
                          "note": "seansta tespit"})
        check("26. koç öğrenci adına kayıt açar (seans senaryosu)",
              r.status_code == 200 and r.json()["data"]["error_type"] == "bilgi",
              r.text[:150])
        ids["wq4"] = r.json()["data"]["id"]
        r = ct.post(f"/api/v2/teacher/wrong-questions/{ids['wq4']}/coach-note",
                    json={"coach_note": "Önce paydaları eşitle."})
        check("27. koç açıklaması yazılır", r.json()["data"]["coach_note"] == "Önce paydaları eşitle.")
        r = cs.get(f"/api/v2/student/wrong-questions/{ids['wq4']}")
        check("28. öğrenci koç açıklamasını görür",
              r.json()["coach_note"] == "Önce paydaları eşitle.")

        # --- Öneri motoru beslemesi sözleşmesi ---
        with SessionLocal() as db:
            m = svc.open_wrong_topic_map(db, ids["student"])
            check("29. open_wrong_topic_map: açık yanlış birikimi 0..1 skor",
                  ids["t1"] in m and 0 < m[ids["t1"]] <= 1.0, f"map={m}")

        # --- Silme + cascade ---
        r = cs.delete(f"/api/v2/student/wrong-questions/{ids['wq1']}")
        check("30. öğrenci kaydı siler", r.status_code == 200)
        with SessionLocal() as db:
            gone = db.get(WrongQuestion, ids["wq1"]) is None
            orphan = db.query(WrongQuestionImage).filter(
                WrongQuestionImage.wrong_question_id == ids["wq1"]).count()
            check("31. silinen kaydın fotoğrafları da silindi (cascade, yetim yok)",
                  gone and orphan == 0, f"gone={gone} orphan={orphan}")
        r = cs.get(f"/api/v2/student/wrong-questions/{ids['wq1']}")
        check("32. silinen kayıt 404", r.status_code == 404)
    finally:
        with SessionLocal() as db:
            wq_ids = [r[0] for r in db.query(WrongQuestion.id).filter(
                WrongQuestion.student_id == ids["student"]).all()]
            if wq_ids:
                db.execute(sa_delete(WrongQuestionImage).where(
                    WrongQuestionImage.wrong_question_id.in_(wq_ids)))
                db.execute(sa_delete(WrongQuestion).where(WrongQuestion.id.in_(wq_ids)))
            db.execute(sa_delete(ExamResult).where(ExamResult.id == ids["exam"]))
            db.execute(sa_delete(Task).where(Task.id == ids["task"]))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.id == ids["sec1"]))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.execute(sa_delete(User).where(User.id.in_(
                [ids["student"], ids["coach"], ids["coach2"], ids["parent"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
