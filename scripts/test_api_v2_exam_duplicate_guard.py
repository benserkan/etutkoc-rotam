"""Deneme mükerrer koruması — üç katman + karar kuralı (2026-09-19).

Saha: aynı karne PDF'i iki kez aktarıldı (öğrenci #163); eski koruma yalnız
"aynı ad + tarih" bakıyor, "yine de kaydet" ile geçiliyordu → iki kayıt,
analiz ikisini de saydı. Bu test korumanın üç katmanını ve karar kuralını
kilitler:

  1. aynı PDF → analizde, Gemini'den ÖNCE 409 (kredi harcanmaz)
  2. farklı dosya, aynı cevaplar → exact; force ile bile 409; "yerine yaz" 200
  3. %97,5 aynı cevaplar → likely; force olmadan 409, force ile ayrı kayıt
  4. elle giriş: aynı ad+tarih → 409, ±3 gün → 409, force → 200
  5. başka öğrencinin aynı PDF'i serbest (kontrol öğrenci-bazlı)

Gemini monkeypatch'lenir — GERÇEK AI çağrısı YAPILMAZ.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import copy
import json
import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    CreditAccount,
    ExamResult,
    ExamResultQuestion,
    ExamTopicAlias,
    SuspiciousIp,
    UsageEvent,
    User,
    UserRole,
)
from app.services import ai_exam_import, exam_duplicate
from app.services import exam_import_service as svc
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"exdup{secrets.token_hex(3)}"
PASSWORD = "ExamDup!2026Xy"
PDF_A = b"%PDF-1.4 fake karne A " + b"0" * 200
PDF_B = b"%PDF-1.4 fake karne B (yeniden tarama) " + b"1" * 200
PDF_C = b"%PDF-1.4 fake karne C " + b"2" * 200
PDF_D = b"%PDF-1.4 fake karne D " + b"3" * 200

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


def build_read(title: str, *, date: str = "2026-09-10", flip: int = 0, shift: bool = False) -> dict:
    """40 soruluk TYT karnesi. flip=N → ilk N sorunun cevabı/sonucu değişir
    (%97,5 = 39/40 aynı). shift=True → tüm cevaplar farklı (aynı ad+tarih testi)."""
    qs = []
    for i in range(1, 41):
        ans = "A" if i % 2 else "B"
        res = "dogru"
        if shift:
            ans, res = ("C", "yanlis")
        elif i <= flip:
            ans, res = ("D", "yanlis")
        qs.append({"subject": "Türkçe" if i <= 20 else "Matematik", "no": i,
                   "topic": "Sözcükte Anlam" if i <= 20 else "Rasyonel Sayılar",
                   "correct_answer": "A" if i % 2 else "B",
                   "student_answer": ans, "result": res})
    return {"exam_title": title, "exam_date": date, "grade_hint": 12,
            "type_hints": ["TYT"], "subjects": [], "questions": qs,
            "score_info": None}


def main() -> int:
    print(f"\n=== Deneme mükerrer koruması smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False,
                     ai_capture_consent_at=datetime.now(timezone.utc))
        s1 = User(email=f"{PFX}-s1@t.invalid", password_hash=hash_password(PASSWORD),
                  full_name="Öğrenci Bir", role=UserRole.STUDENT, is_active=True,
                  grade_level=12, must_change_password=False)
        s2 = User(email=f"{PFX}-s2@t.invalid", password_hash=hash_password(PASSWORD),
                  full_name="Öğrenci İki", role=UserRole.STUDENT, is_active=True,
                  grade_level=12, must_change_password=False)
        db.add_all([coach, s1, s2])
        db.flush()
        s1.teacher_id = coach.id
        s2.teacher_id = coach.id
        db.commit()
        ids = {"coach": coach.id, "s1": s1.id, "s2": s2.id}
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()
    get_login_limiter().reset()

    read_behavior: dict = {"read": build_read(f"{PFX} TYT Deneme 1")}

    def fake_double(pdf_b64: str):
        r1 = ai_exam_import._normalize_read(copy.deepcopy(read_behavior["read"]))
        r2 = ai_exam_import._normalize_read(copy.deepcopy(read_behavior["read"]))
        return r1, r2

    def fake_generate(parts, *, personal_data, json_mode=True, timeout=45.0,
                      max_output_tokens=8192, prefer_paid=True, **kw):
        return json.dumps({"mappings": []})

    orig_double = ai_exam_import.read_exam_pdf_double
    orig_generate = svc.gemini.generate
    ai_exam_import.read_exam_pdf_double = fake_double
    svc.gemini.generate = fake_generate

    def usage_count() -> int:
        with SessionLocal() as db:
            return db.query(UsageEvent).filter(
                UsageEvent.actor_user_id == ids["coach"]).count()

    def exam_count(sid: int) -> int:
        with SessionLocal() as db:
            return db.query(ExamResult).filter(ExamResult.student_id == sid).count()

    def conf_payload(draft: dict, **extra) -> dict:
        rows = [{
            "subject_raw": r["subject_raw"], "question_no": r["question_no"],
            "topic_raw": r["topic_raw"], "topic_id": r.get("topic_id"),
            "correct_answer": r.get("correct_answer"),
            "student_answer": r.get("student_answer"), "result": r["result"],
            "is_suspect": r.get("is_suspect", False), "manually_edited": False,
        } for r in draft["rows"]]
        p = {"title": draft["title"], "exam_date": draft["exam_date"],
             "section": draft["section"], "scope": draft["scope"],
             "grade_hint": draft["grade_hint"], "score_info": draft["score_info"],
             "rows": rows}
        p.update(extra)
        return p

    try:
        ct = TestClient(app)
        r = ct.post("/api/v2/auth/login",
                    json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        assert r.status_code == 200, r.text[:200]
        s1 = ids["s1"]
        analyze = f"/api/v2/teacher/students/{s1}/exams/import-analyze"
        confirm = f"/api/v2/teacher/students/{s1}/exams/import-confirm"
        f_a = ("karne.pdf", PDF_A, "application/pdf")
        f_b = ("karne-tekrar.pdf", PDF_B, "application/pdf")
        f_c = ("karne-c.pdf", PDF_C, "application/pdf")
        f_d = ("karne-d.pdf", PDF_D, "application/pdf")

        # --- 1) ilk aktarma temiz ---
        r = ct.post(analyze, files={"file": f_a})
        d1 = r.json() if r.status_code == 200 else {}
        check("1a. ilk analiz 200 + mükerrer bilgisi YOK",
              r.status_code == 200 and d1.get("duplicate") is None
              and d1.get("duplicate_exam_id") is None, str(d1)[:160])
        r = ct.post(confirm, data={"payload": json.dumps(conf_payload(d1))}, files={"file": f_a})
        exam1 = (r.json().get("data") or {}).get("exam_id") if r.status_code == 200 else None
        check("1b. onay 200 → kayıt açıldı", r.status_code == 200 and exam1, r.text[:160])
        with SessionLocal() as db:
            e = db.get(ExamResult, exam1) if exam1 else None
            sha_ok = e is not None and e.import_pdf_sha256 == exam_duplicate.pdf_sha256(PDF_A)
        check("1c. PDF parmak izi (SHA-256) kayda yazıldı", sha_ok)

        # --- 2) AYNI DOSYA → Gemini'den önce 409, kredi harcanmaz ---
        u_before = usage_count()
        r = ct.post(analyze, files={"file": f_a})
        det = (r.json().get("detail") or {}) if r.status_code == 409 else {}
        dd = det.get("details") or {}
        check("2a. aynı PDF yeniden → 409 duplicate_exam (analiz adımında)",
              r.status_code == 409 and det.get("code") == "duplicate_exam", r.text[:200])
        check("2b. seviye exact · sebep same_file · mevcut kayıt id doğru",
              dd.get("level") == "exact" and dd.get("reason") == "same_file"
              and dd.get("exam_id") == exam1, str(dd))
        check("2c. KREDİ HARCANMADI (Gemini'ye gidilmedi)",
              usage_count() == u_before, f"{u_before}→{usage_count()}")

        # --- 3) FARKLI DOSYA, AYNI CEVAPLAR (yeniden tarama) → exact ---
        r = ct.post(analyze, files={"file": f_b})
        d3 = r.json() if r.status_code == 200 else {}
        dup3 = d3.get("duplicate") or {}
        check("3a. yeniden taranmış kopya: önizleme 'exact · same_answers' söyler",
              r.status_code == 200 and dup3.get("level") == "exact"
              and dup3.get("reason") == "same_answers" and dup3.get("exam_id") == exam1,
              str(dup3))
        r = ct.post(confirm, data={"payload": json.dumps(conf_payload(d3, force=True))},
                    files={"file": f_b})
        det = (r.json().get("detail") or {}) if r.status_code == 409 else {}
        check("3b. exact'te force GEÇERSİZ → yine 409, kayıt açılmadı",
              r.status_code == 409 and det.get("code") == "duplicate_exam"
              and exam_count(s1) == 1, f"{r.status_code} n={exam_count(s1)}")
        # yerine yaz
        r = ct.post(confirm, data={"payload": json.dumps(conf_payload(d3, replace_exam_id=exam1))},
                    files={"file": f_b})
        rid = (r.json().get("data") or {}).get("exam_id") if r.status_code == 200 else None
        with SessionLocal() as db:
            e = db.get(ExamResult, exam1)
            sha_b = e is not None and e.import_pdf_sha256 == exam_duplicate.pdf_sha256(PDF_B)
            qn = db.query(ExamResultQuestion).filter(
                ExamResultQuestion.exam_result_id == exam1).count()
        check("3c. 'yerine yaz' → aynı kayıt güncellendi (id aynı, kayıt sayısı 1)",
              r.status_code == 200 and rid == exam1 and exam_count(s1) == 1,
              f"{r.status_code} rid={rid} n={exam_count(s1)}")
        check("3d. yerine yazınca PDF kanıtı + parmak izi yenilendi, 40 satır durur",
              sha_b and qn == 40, f"sha_b={sha_b} q={qn}")
        # yabancı hedef
        r = ct.post(confirm, data={"payload": json.dumps(conf_payload(d3, replace_exam_id=99999999))},
                    files={"file": f_b})
        check("3e. yabancı/yok kayda 'yerine yaz' → 404", r.status_code == 404, r.text[:120])

        # --- 4) %97,5 aynı (39/40) → likely ---
        read_behavior["read"] = build_read(f"{PFX} TYT Deneme 1 Düzeltilmiş", flip=1)
        r = ct.post(analyze, files={"file": f_c})
        d4 = r.json() if r.status_code == 200 else {}
        dup4 = d4.get("duplicate") or {}
        check("4a. 39/40 aynı cevap → 'likely · near_answers' (%97,5)",
              dup4.get("level") == "likely" and dup4.get("reason") == "near_answers"
              and 0.97 <= float(dup4.get("similarity") or 0) <= 0.98, str(dup4))
        r = ct.post(confirm, data={"payload": json.dumps(conf_payload(d4))}, files={"file": f_c})
        check("4b. likely + force yok → 409 (uyarı)", r.status_code == 409, r.text[:120])
        r = ct.post(confirm, data={"payload": json.dumps(conf_payload(d4, force=True))},
                    files={"file": f_c})
        exam2 = (r.json().get("data") or {}).get("exam_id") if r.status_code == 200 else None
        check("4c. likely + force → AYRI kayıt (koç kararı)",
              r.status_code == 200 and exam2 and exam2 != exam1 and exam_count(s1) == 2,
              f"{r.status_code} n={exam_count(s1)}")

        # --- 5) AD + TARİH: cevaplar tamamen farklı, ad+tarih aynı → likely ---
        read_behavior["read"] = build_read(f"{PFX} TYT Deneme 1", shift=True)
        r = ct.post(analyze, files={"file": f_d})
        d5 = r.json() if r.status_code == 200 else {}
        dup5 = d5.get("duplicate") or {}
        check("5a. farklı cevaplar, aynı ad+tarih → 'likely · same_title_date'",
              dup5.get("level") == "likely" and dup5.get("reason") == "same_title_date",
              str(dup5))

        # --- 6) ELLE GİRİŞ ---
        manual = f"/api/v2/teacher/students/{s1}/exams"
        body = {"title": f"{PFX} TYT DENEME 1", "exam_date": "2026-09-10",
                "section": "tyt", "total_correct": 30, "total_wrong": 5, "total_blank": 5}
        r = ct.post(manual, json=body)
        det = (r.json().get("detail") or {}) if r.status_code == 409 else {}
        check("6a. elle giriş, aynı ad (büyük/küçük harf farkı) + aynı tarih → 409",
              r.status_code == 409 and det.get("code") == "duplicate_exam"
              and (det.get("details") or {}).get("reason") == "same_title_date",
              r.text[:160])
        r = ct.post(manual, json={**body, "exam_date": "2026-09-12"})
        det = (r.json().get("detail") or {}) if r.status_code == 409 else {}
        check("6b. aynı ad, 2 gün sonra → 409 near_title_date",
              r.status_code == 409 and (det.get("details") or {}).get("reason") == "near_title_date",
              r.text[:160])
        r = ct.post(manual, json={**body, "exam_date": "2026-09-20"})
        check("6c. aynı ad, 10 gün sonra → serbest (meşru tekrar)", r.status_code == 200, r.text[:120])
        r = ct.post(manual, json={**body, "force": True})
        check("6d. force ile aynı ad+tarih → 200 (koç kararı)", r.status_code == 200, r.text[:120])

        # --- 7) BAŞKA ÖĞRENCİ: aynı PDF serbest ---
        read_behavior["read"] = build_read(f"{PFX} TYT Deneme 1")
        r = ct.post(f"/api/v2/teacher/students/{ids['s2']}/exams/import-analyze",
                    files={"file": f_a})
        d7 = r.json() if r.status_code == 200 else {}
        check("7a. başka öğrenciye aynı PDF → 200, mükerrer değil",
              r.status_code == 200 and d7.get("duplicate") is None, str(d7)[:120])

        # --- 8) servis birimi: normalize + imza ---
        check("8a. ad normalizasyonu Türkçe/İ-ı/noktalama duyarsız",
              exam_duplicate.normalize_title("TYT DENEME-1 (İkinci)") ==
              exam_duplicate.normalize_title("tyt deneme 1 ikinci"))
        sig = exam_duplicate.answer_signature(
            [{"question_no": 2, "student_answer": "b", "result": "DOGRU"},
             {"question_no": 1, "student_answer": "A", "result": "dogru"}])
        check("8b. cevap imzası soru no'ya göre sıralı + büyük/küçük harf nötr",
              sig == ((1, "A", "dogru"), (2, "B", "dogru")), str(sig))
    finally:
        ai_exam_import.read_exam_pdf_double = orig_double
        svc.gemini.generate = orig_generate
        with SessionLocal() as db:
            uids = list(ids.values())
            exam_ids = [e.id for e in db.query(ExamResult).filter(
                ExamResult.student_id.in_(uids)).all()]
            if exam_ids:
                db.execute(sa_delete(ExamResultQuestion).where(
                    ExamResultQuestion.exam_result_id.in_(exam_ids)))
                db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exam_ids)))
            db.execute(sa_delete(ExamTopicAlias).where(
                ExamTopicAlias.created_by_id.in_(uids)))
            db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id.in_(uids)))
            db.execute(sa_delete(CreditAccount).where(
                CreditAccount.owner_id.in_(uids), CreditAccount.owner_type == "user"))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.commit()

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
