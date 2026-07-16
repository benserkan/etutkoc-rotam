"""Yanlış Soru Arşivi Faz 3 — AI etiketleme + öneri motoru sinyali.

Kapsam:
- Kapılar: fotoğrafsız kayıt 422 · koçsuz öğrenci 403 · koç ücretsiz plan 403 ·
  koç rıza vermemiş 403 · kredi bitti 402 · foto okunamadı 422 · servis yok 502.
- Mutlu yol: AI konu eşler + zorluk + Sokratik ipucu → kayda uygulanır; KOÇUN
  kredisinden 2 düşer (öğrenci tetiklese bile).
- Güvenlik: AI listede OLMAYAN topic_id uydurursa DÜŞÜRÜLÜR (uydurma konu
  sisteme girmez). Elle seçilmiş konu AI tarafından EZİLMEZ.
- Koç da tetikleyebilir (kendi kredisinden); yabancı koç 404.
- Öneri motoru: açık yanlışı biriken konu, görev önerilerinde "Arşivde açık
  yanlışı var" gerekçesiyle öne çıkar; kapanınca sinyal düşer.

Gemini monkeypatch'lenir — GERÇEK AI çağrısı YAPILMAZ.
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
    CreditAccount,
    StudentBook,
    Subject,
    SuspiciousIp,
    Topic,
    UsageEvent,
    User,
    UserRole,
    WrongQuestion,
    WrongQuestionImage,
)
from app.services import ai_wrong_question as aiwq
from app.services import wrong_question_service as svc
from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"wqai{secrets.token_hex(3)}"
PASSWORD = "WrongAI!2026X"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 300
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


def credits_used(db, coach_id: int) -> int:
    return sum(
        e.credits for e in db.query(UsageEvent).filter(
            UsageEvent.actor_user_id.isnot(None)).all()
        if e.kind and "wrong_tag" in str(e.kind)
    )


def main() -> int:
    print(f"\n=== YSA Faz 3 — AI etiketleme smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        # Ücretli koç (AI açık) + rıza
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False,
                     ai_capture_consent_at=datetime.now(timezone.utc))
        # Ücretsiz koç (AI kapalı)
        free_coach = User(email=f"{PFX}-tf@t.invalid", password_hash=hash_password(PASSWORD),
                          full_name="Ücretsiz Koç", role=UserRole.TEACHER, is_active=True,
                          plan="solo_free", must_change_password=False,
                          ai_capture_consent_at=datetime.now(timezone.utc))
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True,
                       grade_level=12, must_change_password=False)
        free_student = User(email=f"{PFX}-sf@t.invalid", password_hash=hash_password(PASSWORD),
                            full_name="Ücretsiz Öğr", role=UserRole.STUDENT, is_active=True,
                            grade_level=12, must_change_password=False)
        db.add_all([coach, free_coach, student, free_student]); db.flush()
        student.teacher_id = coach.id
        free_student.teacher_id = free_coach.id
        subj = Subject(name=f"{PFX} TYT Matematik", order=999, is_builtin=False,
                       teacher_id=coach.id, min_grade_level=9, max_grade_level=12)
        db.add(subj); db.flush()
        # NOT: Topic.is_builtin varsayılanı False → müfredat sorgusu
        # (or_(is_builtin, teacher_id==coach)) koç sahipliği ister.
        t_ok = Topic(name="Bölme ve Bölünebilme", order=1, subject_id=subj.id,
                     grade_level=12, teacher_id=coach.id)
        t_other = Topic(name="Rasyonel Sayılar", order=2, subject_id=subj.id,
                        grade_level=12, teacher_id=coach.id)
        db.add_all([t_ok, t_other]); db.flush()
        book = Book(name=f"{PFX} Soru Bankası", subject_id=subj.id,
                    type=BookType.SORU_BANKASI, teacher_id=coach.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Bölme", test_count=20, order=1,
                          topic_id=t_ok.id)
        sec2 = BookSection(book_id=book.id, label="Rasyonel", test_count=20, order=2,
                           topic_id=t_other.id)
        db.add_all([sec, sec2]); db.flush()
        db.add(StudentBook(student_id=student.id, book_id=book.id))
        db.commit()
        ids = {"coach": coach.id, "free_coach": free_coach.id,
               "student": student.id, "free_student": free_student.id,
               "subj": subj.id, "t_ok": t_ok.id, "t_other": t_other.id,
               "book": book.id, "sec": sec.id, "sec2": sec2.id}

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    # --- Gemini monkeypatch (gerçek AI çağrısı YOK) ---
    calls: dict = {"n": 0}
    ai_behavior = {"mode": "ok", "topic_id": None}

    def fake_tag(image_base64, media_type, *, candidates, timeout=45.0):
        calls["n"] += 1
        if ai_behavior["mode"] == "unreadable":
            raise AIInvalidResponse("Fotoğraf okunamadı")
        if ai_behavior["mode"] == "down":
            raise AIServiceUnavailable("anahtar yok")
        return {
            "question_text": "Bostanlı iskelesinden kalkan vapurlar…",
            "topic_id": ai_behavior["topic_id"],
            "difficulty": "orta",
            "hint": "EBOB/EKOK kavramını hatırla; sefer aralıklarının ortak katını düşün.",
        }

    import app.routes.api_v2.wrong_questions as wq_router
    orig = aiwq.tag_wrong_question_photo
    aiwq.tag_wrong_question_photo = fake_tag  # servis düzeyi (router import eder)

    try:
        cs = TestClient(app); ct = TestClient(app)
        cfs = TestClient(app); cft = TestClient(app)
        cs.post("/api/v2/auth/login",
                json={"email": f"{PFX}-s@t.invalid", "password": PASSWORD})
        ct.post("/api/v2/auth/login",
                json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        cfs.post("/api/v2/auth/login",
                 json={"email": f"{PFX}-sf@t.invalid", "password": PASSWORD})
        cft.post("/api/v2/auth/login",
                 json={"email": f"{PFX}-tf@t.invalid", "password": PASSWORD})

        # --- Fotoğrafsız kayıt → 422 no_photo ---
        r = cs.post("/api/v2/student/wrong-questions", data={"note": "fotosuz"})
        ids["wq_nophoto"] = r.json()["data"]["id"]
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq_nophoto']}/ai-tag")
        check("1. fotoğrafsız kayıt → 422 no_photo",
              r.status_code == 422 and r.json()["detail"]["code"] == "no_photo",
              r.text[:120])

        # --- Ücretsiz koçun öğrencisi → 403 plan_upgrade_required ---
        r = cfs.post("/api/v2/student/wrong-questions",
                     files=[("photos", ("s.png", PNG, "image/png"))])
        wq_free = r.json()["data"]["id"]
        ids["wq_free"] = wq_free
        r = cfs.post(f"/api/v2/student/wrong-questions/{wq_free}/ai-tag")
        check("2. koçu ücretsiz pakette → 403 plan_upgrade_required",
              r.status_code == 403
              and r.json()["detail"]["code"] == "plan_upgrade_required",
              r.text[:120])

        # --- Ana kayıt (fotoğraflı, konu bağlamı YOK → AI eşleyecek) ---
        r = cs.post("/api/v2/student/wrong-questions",
                    data={"error_type": "yorum"},
                    files=[("photos", ("soru.png", PNG, "image/png"))])
        wq = r.json()["data"]
        ids["wq"] = wq["id"]
        check("3. fotoğraflı kayıt (etiketsiz) oluştu",
              r.status_code == 200 and wq["topic_id"] is None
              and wq["ai_hint"] is None, r.text[:120])

        # --- AI uydurma topic_id → DÜŞÜRÜLÜR (uydurma konu sisteme girmez) ---
        # Servis katmanı normalizasyonu (aday listesinde olmayan id atılır):
        norm = aiwq._normalize(
            {"topic_id": 999_999, "question_text": "x", "hint": "y",
             "difficulty": "orta"},
            {ids["t_ok"], ids["t_other"]},
        )
        check("4a. servis normalizasyonu: aday listesinde OLMAYAN topic_id atılır",
              norm["topic_id"] is None and norm["hint"] == "y", f"norm={norm}")
        # Uç katman savunması: yine de gelse DB'de olmayan konu uygulanmaz
        ai_behavior["topic_id"] = 999_999
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/ai-tag")
        d = r.json()["data"]
        check("4b. uydurma konu kayda UYGULANMAZ + 'eşleşti' RAPORLANMAZ",
              r.status_code == 200 and d["item"]["topic_id"] is None
              and d["matched_topic"] is False, r.text[:200])
        check("5. ipucu + zorluk yine de uygulandı (AI çözüm VERMEZ, yol gösterir)",
              d["item"]["ai_hint"] and d["item"]["difficulty_guess"] == "orta"
              and d["credits_charged"] == 2, r.text[:200])

        # --- Geçerli topic_id → eşleşir ---
        with SessionLocal() as db:  # ipucu/AI izini temizle → tekrar etiketlenebilsin
            w = db.get(WrongQuestion, ids["wq"])
            w.ai_hint = None; w.ai_tagged_at = None; w.ai_question_text = None
            db.commit()
        ai_behavior["topic_id"] = ids["t_ok"]
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/ai-tag")
        d = r.json()["data"]
        check("6. AI GEÇERLİ konuyu eşledi → konu + ders otomatik doldu",
              r.status_code == 200 and d["item"]["topic_id"] == ids["t_ok"]
              and d["item"]["subject_id"] == ids["subj"]
              and d["matched_topic"] is True and d["hint_created"] is True,
              r.text[:220])

        # --- Elle seçilmiş konu AI tarafından EZİLMEZ + FARKLI konu ÖNERİLİR ---
        with SessionLocal() as db:
            w = db.get(WrongQuestion, ids["wq"])
            w.topic_id = ids["t_other"]   # öğrenci elle başka konu seçti
            w.ai_tagged_at = None
            db.commit()
        ai_behavior["topic_id"] = ids["t_ok"]
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/ai-tag")
        d = r.json()["data"]
        check("7. öğrencinin elle seçtiği konu AI tarafından EZİLMEZ",
              d["item"]["topic_id"] == ids["t_other"], r.text[:150])
        check("7b. AI FARKLI konu görürse ÖNERİ olarak döner (elle seçim ezilmez)",
              d["suggested_topic_id"] == ids["t_ok"]
              and d["suggested_topic_name"] == "Bölme ve Bölünebilme",
              f"suggested={d.get('suggested_topic_id')}")

        # --- Kredi KOÇUN havuzundan düşüyor (öğrenci tetiklese de) ---
        with SessionLocal() as db:
            evs = db.query(UsageEvent).filter(
                UsageEvent.kind == "ai_wrong_tag").all()
            total = sum(e.credits for e in evs)
            check("8. kredi koçun havuzundan düştü (3 çağrı × 2 kredi = 6)",
                  len(evs) == 3 and total == 6, f"events={len(evs)} credits={total}")

        # --- Koç da tetikleyebilir; yabancı koç 404 ---
        with SessionLocal() as db:
            w = db.get(WrongQuestion, ids["wq"])
            w.ai_hint = None; w.ai_tagged_at = None
            db.commit()
        r = ct.post(f"/api/v2/teacher/wrong-questions/{ids['wq']}/ai-tag")
        check("9. koç kendi öğrencisinin kaydını etiketleyebilir",
              r.status_code == 200 and r.json()["data"]["item"]["ai_hint"],
              r.text[:150])
        r = cft.post(f"/api/v2/teacher/wrong-questions/{ids['wq']}/ai-tag")
        check("10. YABANCI koç 404 (sızıntı yok)", r.status_code == 404)

        # --- AI hataları ---
        ai_behavior["mode"] = "unreadable"
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/ai-tag")
        check("11. fotoğraf okunamadı → 422 photo_unreadable",
              r.status_code == 422
              and r.json()["detail"]["code"] == "photo_unreadable", r.text[:120])
        ai_behavior["mode"] = "down"
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/ai-tag")
        check("12. AI servisi yok → 502 ai_unavailable",
              r.status_code == 502
              and r.json()["detail"]["code"] == "ai_unavailable", r.text[:120])
        ai_behavior["mode"] = "ok"

        # --- Rıza kapısı ---
        with SessionLocal() as db:
            db.get(User, ids["coach"]).ai_capture_consent_at = None
            db.commit()
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/ai-tag")
        check("13. koç rıza vermemiş → 403 consent_required",
              r.status_code == 403
              and r.json()["detail"]["code"] == "consent_required", r.text[:120])
        with SessionLocal() as db:
            db.get(User, ids["coach"]).ai_capture_consent_at = datetime.now(timezone.utc)
            db.commit()

        # --- Kredi bitti → 402 ---
        with SessionLocal() as db:
            acc = db.query(CreditAccount).filter(
                CreditAccount.owner_id == ids["coach"]).first()
            if acc is not None:
                acc.used_credits = acc.allocated_credits + acc.bonus_credits
                db.commit()
        r = cs.post(f"/api/v2/student/wrong-questions/{ids['wq']}/ai-tag")
        check("14. kredi bitti → 402 ai_credit_exhausted",
              r.status_code == 402
              and r.json()["detail"]["code"] == "ai_credit_exhausted", r.text[:120])
        with SessionLocal() as db:
            acc = db.query(CreditAccount).filter(
                CreditAccount.owner_id == ids["coach"]).first()
            if acc is not None:
                acc.used_credits = 0
                db.commit()

        # --- Aday konular gerçek müfredattan gelir (uydurma yok) ---
        with SessionLocal() as db:
            stu = db.get(User, ids["student"])
            cands = svc.candidate_topics(db, stu, ids["coach"])
            cand_ids = {c["id"] for c in cands}
            check("15. AI'a verilen aday konular öğrencinin GERÇEK müfredatından",
                  ids["t_ok"] in cand_ids and ids["t_other"] in cand_ids
                  and all(isinstance(c["id"], int) for c in cands),
                  f"n={len(cands)}")

        # --- Öneri motoru sinyali ---
        from app.services.suggestions import build_student_model, suggest_for_date
        with SessionLocal() as db:
            # wq → t_ok konusunda AÇIK yanlış (elle konu t_other'dı; düzelt)
            w = db.get(WrongQuestion, ids["wq"])
            w.topic_id = ids["t_ok"]; w.status = "acik"
            db.commit()
            m = svc.open_wrong_topic_map(db, ids["student"])
            check("16. open_wrong_topic_map: açık yanlışı olan konu sinyal veriyor",
                  ids["t_ok"] in m and m[ids["t_ok"]] > 0, f"map={m}")

            target = date.today() + timedelta(days=1)
            model = build_student_model(db, ids["student"])
            sugg = suggest_for_date(db, ids["student"], target, model=model)
            by_sec = {s.section_id: s for s in sugg}
            s_ok = by_sec.get(ids["sec"])
            check("17. yanlış biriken konunun bölümü öneride 'Arşivde açık yanlışı var'",
                  s_ok is not None
                  and any("açık yanlışı var" in r for r in s_ok.reasons),
                  f"reasons={s_ok.reasons if s_ok else None}")
            s_other = by_sec.get(ids["sec2"])
            check("18. yanlışı olan bölüm, olmayandan DAHA YÜKSEK skorlu",
                  s_ok is not None and s_other is not None
                  and s_ok.score > s_other.score,
                  f"ok={s_ok.score if s_ok else None} other={s_other.score if s_other else None}")

            # Kapanınca sinyal düşer
            w = db.get(WrongQuestion, ids["wq"])
            w.status = "kapandi"
            db.commit()
            m2 = svc.open_wrong_topic_map(db, ids["student"])
            check("19. yanlış KAPANINCA sinyal düşer (kapanış öğrenmenin kanıtı)",
                  ids["t_ok"] not in m2, f"map={m2}")

        # --- ÇIKMAZ DÜZELTMESİ: liste yanıtı AI erişim durumu (doğruluk testi) ---
        # (koç rızası olan öğrenci) → available
        r = cs.get("/api/v2/student/wrong-questions")
        check("20. rıza+paket tam → liste ai.available=true, reason=ok",
              r.json()["ai"]["available"] is True and r.json()["ai"]["reason"] == "ok",
              str(r.json().get("ai")))
        # rıza kaldırılınca → available=false, reason=consent_required
        with SessionLocal() as db:
            db.get(User, ids["coach"]).ai_capture_consent_at = None
            db.commit()
        r = cs.get("/api/v2/student/wrong-questions")
        check("21. koç rızası yoksa → ai.available=false, reason=consent_required "
              "(öğrenci çıkmaz mesaj yerine net durum görür)",
              r.json()["ai"]["available"] is False
              and r.json()["ai"]["reason"] == "consent_required",
              str(r.json().get("ai")))
        with SessionLocal() as db:
            db.get(User, ids["coach"]).ai_capture_consent_at = datetime.now(timezone.utc)
            db.commit()
        # ücretsiz koçun öğrencisi → reason=plan_upgrade_required
        r = cfs.get("/api/v2/student/wrong-questions")
        check("22. koç ücretsiz pakette → ai.available=false, "
              "reason=plan_upgrade_required",
              r.json()["ai"]["available"] is False
              and r.json()["ai"]["reason"] == "plan_upgrade_required",
              str(r.json().get("ai")))
    finally:
        aiwq.tag_wrong_question_photo = orig
        with SessionLocal() as db:
            wq_ids = [r[0] for r in db.query(WrongQuestion.id).filter(
                WrongQuestion.student_id.in_([ids["student"], ids["free_student"]])).all()]
            if wq_ids:
                db.execute(sa_delete(WrongQuestionImage).where(
                    WrongQuestionImage.wrong_question_id.in_(wq_ids)))
                db.execute(sa_delete(WrongQuestion).where(WrongQuestion.id.in_(wq_ids)))
            db.execute(sa_delete(UsageEvent).where(UsageEvent.kind == "ai_wrong_tag"))
            db.execute(sa_delete(CreditAccount).where(
                CreditAccount.owner_id.in_([ids["coach"], ids["free_coach"]])))
            db.execute(sa_delete(StudentBook).where(
                StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(
                BookSection.id.in_([ids["sec"], ids["sec2"]])))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.execute(sa_delete(User).where(User.id.in_(
                [ids["student"], ids["coach"], ids["free_student"], ids["free_coach"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
