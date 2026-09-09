"""Maarif Modeli deneme türleri — smoke (2026-09-09, saha vakası).

SAHA HATASI (kullanıcı, öğrenci #34 Elif Demirci, 11. sınıf Maarif):
"ÇAP Maarif Model Birinci Basamak Sınavı" karnesi yüklenemedi — beyan
listesinde Maarif türü YOKtu, otomatik tespit "emin olamadım" dedi, konular
eşleşmedi. Üç kök neden:
  1) ExamSection'da Maarif türü yok (lgs/tyt/ayt×4/okul)
  2) tespit motoru "maarif"/"basamak" kelimelerini tanımıyor + yapı kuralı
     100-130 soruda ≥6 ders istiyordu (karnede 4 BİRLEŞİK ders var) → tek oy
  3) karnedeki "Fen Bilimleri" / "Sosyal Bilimler" birleşik ders adlarının
     Maarif müfredatında karşılığı yok (Fizik/Kimya/Biyoloji ayrı) → ders
     çözülemeyince konu havuzu da bulunamıyordu

Kapsam: tür tespiti (kelime + yapı imzası) · alt-tür kuralı (9. sınıfta
1. Basamak OLMAZ) · birleşik ders köprüsü · sınıf kapsamı (1. Basamak 9-10,
11. Sınıf 9-11) · sunum birleştirme · net cezası 4 · kayıt · TYT regresyonu.

Gemini monkeypatch'lenir — GERÇEK AI çağrısı YAPILMAZ (AI katmanı bilerek
BOŞ döner: eşleşmeler DETERMİNİSTİK katmandan gelmeli).
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
    CurriculumModel,
    ExamResult,
    ExamResultQuestion,
    ExamTopicAlias,
    Subject,
    SuspiciousIp,
    Topic,
    UsageEvent,
    User,
    UserRole,
)
from app.services import ai_exam_import
from app.services import exam_import_service as svc
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"exmaa{secrets.token_hex(3)}"
PASSWORD = "ExamMaarif!2026X"
PDF = b"%PDF-1.4 fake maarif report " + b"0" * 200
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


def maarif_topic_id(db, subject_name: str, topic_name: str) -> int:
    t = (
        db.query(Topic).join(Subject, Subject.id == Topic.subject_id)
        .filter(Subject.is_builtin.is_(True), Subject.name == subject_name,
                Subject.curriculum_model == CurriculumModel.MAARIF_LISE,
                Topic.name == topic_name)
        .first()
    )
    assert t is not None, f"Maarif konu yok: {subject_name} / {topic_name}"
    return t.id


# --- ÇAP karnesinin küçük taklidi (gerçek belge: TDE 40 · Sosyal 25 ·
#     Matematik 40 · Fen 20 = 125 soru; konular MEB kazanım cümleleri) ---

def build_maarif_read(title: str, *, grade_hint: int | None = 10) -> dict:
    return {
        "exam_title": title,
        "exam_date": "2026-09-05",
        "grade_hint": grade_hint,
        "type_hints": [],
        "subjects": [
            {"name": "Türk Dili ve Edebiyatı", "questions": 1, "correct": 1,
             "wrong": 0, "blank": 0, "net": 1.0},
            {"name": "Fen Bilimleri", "questions": 2, "correct": 1,
             "wrong": 1, "blank": 0, "net": 0.75},
        ],
        "questions": [
            {"subject": "Türk Dili ve Edebiyatı", "no": 1, "topic": "Koşuk",
             "correct_answer": "A", "student_answer": "A", "result": "dogru"},
            # BİRLEŞİK ders — Maarif'te Fizik/Kimya/Biyoloji ayrı derstir
            {"subject": "Fen Bilimleri", "no": 2, "topic": "Sabit İvmeli Hareket",
             "correct_answer": "B", "student_answer": "B", "result": "dogru"},
            # 11. sınıf konusu: 1. Basamak kapsamı DIŞINDA (9-10) olmalı
            {"subject": "Fen Bilimleri", "no": 3, "topic": "Çembersel Hareket",
             "correct_answer": "C", "student_answer": "D", "result": "yanlis"},
            # BİRLEŞİK ders — Maarif'te Tarih/Coğrafya/Felsefe ayrı
            {"subject": "Sosyal Bilimler", "no": 4, "topic": "Osmanlı'nın Kuruluşu",
             "correct_answer": "D", "student_answer": "E", "result": "yanlis"},
            {"subject": "Matematik", "no": 5, "topic": "Karesel Fonksiyonlar",
             "correct_answer": "E", "student_answer": None, "result": "bos"},
        ],
        "score_info": None,
    }


def build_structure_read() -> dict:
    """Başlıkta 'maarif' GEÇMEYEN ama yapı imzası taşıyan belge:
    TDE + birleşik ders adları + ~125 soru → yine Maarif olarak tanınmalı."""
    qs = []
    plan = [("Türk Dili ve Edebiyatı", "Koşuk", 40),
            ("Sosyal Bilimler", "Osmanlı'nın Kuruluşu", 25),
            ("Matematik", "Karesel Fonksiyonlar", 40),
            ("Fen Bilimleri", "Sabit İvmeli Hareket", 20)]
    n = 0
    for subj, topic, count in plan:
        for _ in range(count):
            n += 1
            qs.append({"subject": subj, "no": n, "topic": topic,
                       "correct_answer": "A", "student_answer": "A",
                       "result": "dogru"})
    return {
        "exam_title": f"{PFX} YAYIN DENEMESİ 3",
        "exam_date": "2026-09-06", "grade_hint": 11, "type_hints": [],
        "subjects": [], "questions": qs, "score_info": None,
    }


def build_pure_tyt_read() -> dict:
    """REGRESYON: klasik TYT belgesi (Türkçe dersi, birleşik ad yok) —
    Maarif kuralları devreye GİRMEMELİ."""
    return {
        "exam_title": f"{PFX} MOMENTUM TYT DENEME",
        "exam_date": "2026-09-07", "grade_hint": 12, "type_hints": ["TYT"],
        "subjects": [],
        "questions": [
            {"subject": "Türkçe", "no": 1, "topic": "Sözcükte Anlam",
             "correct_answer": "A", "student_answer": "A", "result": "dogru"},
            {"subject": "Matematik", "no": 2, "topic": "Rasyonel Sayılar",
             "correct_answer": "B", "student_answer": "C", "result": "yanlis"},
        ],
        "score_info": None,
    }


def main() -> int:
    print(f"\n=== Maarif deneme türleri smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False,
                     ai_capture_consent_at=datetime.now(timezone.utc))
        s11 = User(email=f"{PFX}-s11@t.invalid", password_hash=hash_password(PASSWORD),
                   full_name="Maarif 11", role=UserRole.STUDENT, is_active=True,
                   grade_level=11, must_change_password=False)
        s9 = User(email=f"{PFX}-s9@t.invalid", password_hash=hash_password(PASSWORD),
                  full_name="Maarif 9", role=UserRole.STUDENT, is_active=True,
                  grade_level=9, must_change_password=False)
        db.add_all([coach, s11, s9])
        db.flush()
        s11.teacher_id = coach.id
        s9.teacher_id = coach.id
        db.commit()
        ids = {
            "coach": coach.id, "s11": s11.id, "s9": s9.id,
            "fizik10": maarif_topic_id(db, "Fizik", "Sabit İvmeli Hareket"),
            "fizik11": maarif_topic_id(db, "Fizik", "Çembersel Hareket"),
            "tarih10": maarif_topic_id(db, "Tarih", "Osmanlı'nın Kuruluşu"),
            "mat10": maarif_topic_id(db, "Matematik", "Karesel Fonksiyonlar"),
            "tde10": maarif_topic_id(db, "Türk Dili ve Edebiyatı", "Koşuk"),
        }

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    read_behavior: dict = {"read": build_maarif_read(f"{PFX} ÇAP Maarif Model Birinci Basamak Sınavı")}

    def fake_double(pdf_b64: str):
        r1 = ai_exam_import._normalize_read(copy.deepcopy(read_behavior["read"]))
        r2 = ai_exam_import._normalize_read(copy.deepcopy(read_behavior["read"]))
        return r1, r2

    def fake_generate(parts, *, personal_data, json_mode=True, timeout=45.0,
                      max_output_tokens=8192, prefer_paid=True, **kw):
        # AI katmanı BİLEREK boş — eşleşmeler deterministik katmandan gelmeli
        return json.dumps({"mappings": []})

    orig_double = ai_exam_import.read_exam_pdf_double
    orig_generate = svc.gemini.generate
    ai_exam_import.read_exam_pdf_double = fake_double
    svc.gemini.generate = fake_generate

    try:
        ct = TestClient(app)
        r = ct.post("/api/v2/auth/login",
                    json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        assert r.status_code == 200, r.text[:200]
        pdf_file = ("karne.pdf", PDF, "application/pdf")
        base = f"/api/v2/teacher/students/{ids['s11']}/exams/import-analyze"

        # --- 1) TESPİT: başlıkta "Maarif ... Birinci Basamak" ---
        r = ct.post(base, files={"file": pdf_file})
        d = r.json() if r.status_code == 200 else {}
        check("1a. Maarif belgesi tanındı (universe=maarif, section=maarif_1)",
              r.status_code == 200 and d.get("universe") == "maarif"
              and d.get("section") == "maarif_1", f"{r.status_code} {str(d)[:200]}")
        check("1b. güven YÜKSEK (eski davranış: tek oyla düşük güven uyarısı)",
              d.get("confidence") == "high", str(d.get("confidence")))
        rows = {x["topic_raw"]: x for x in d.get("rows", [])}

        # --- 2) BİRLEŞİK DERS KÖPRÜSÜ ---
        fen = rows.get("Sabit İvmeli Hareket", {})
        check("2a. 'Fen Bilimleri' satırı Maarif Fizik konusuna bağlandı",
              fen.get("topic_id") == ids["fizik10"], str(fen)[:200])
        check("2b. nihai ders KONUdan türedi (Fizik) — ham ad 'Fen Bilimleri'",
              fen.get("subject_name") == "Fizik"
              and fen.get("subject_raw") == "Fen Bilimleri", str(fen)[:200])
        check("2c. deterministik katman çözdü (AI boş döndürüldü)",
              fen.get("topic_source") in ("auto", "alias"), str(fen.get("topic_source")))
        sos = rows.get("Osmanlı'nın Kuruluşu", {})
        check("2d. 'Sosyal Bilimler' satırı Maarif Tarih konusuna bağlandı",
              sos.get("topic_id") == ids["tarih10"] and sos.get("subject_name") == "Tarih",
              str(sos)[:200])

        # --- 3) SINIF KAPSAMI: 1. Basamak 9-10 ölçer ---
        cem = rows.get("Çembersel Hareket", {})
        check("3a. 11. sınıf konusu 1. Basamak havuzunda YOK (eşleşmedi)",
              cem.get("topic_id") is None, str(cem)[:200])

        # --- 4) SUNUM: birleşik ders adı korunur (alt derslere bölünmez) ---
        gnames = {g["name"] for g in d.get("subjects", [])}
        check("4a. ders kırılımı belgedeki gibi 'Fen Bilimleri'",
              "Fen Bilimleri" in gnames and "Fizik" not in gnames, str(gnames))
        check("4b. 'Sosyal Bilimler' de birleşik kaldı",
              "Sosyal Bilimler" in gnames and "Tarih" not in gnames, str(gnames))

        # --- 5) BEYAN: maarif_11 seçilirse 11. sınıf konusu aday olur ---
        r = ct.post(base, files={"file": pdf_file},
                    data={"declared_section": "maarif_11", "declared_grade": "11"})
        d2 = r.json() if r.status_code == 200 else {}
        rows2 = {x["topic_raw"]: x for x in d2.get("rows", [])}
        check("5a. beyan maarif_11 → tür beyandan (high)",
              d2.get("section") == "maarif_11" and d2.get("confidence") == "high",
              str(d2)[:160])
        check("5b. kapsam 11'e açıldı → 'Çembersel Hareket' eşleşti",
              rows2.get("Çembersel Hareket", {}).get("topic_id") == ids["fizik11"],
              str(rows2.get("Çembersel Hareket"))[:200])

        # --- 6) ALT TÜR KURALI: 9. sınıfta 1. Basamak OLMAZ ---
        read_behavior["read"] = build_maarif_read(
            f"{PFX} Maarif Model Deneme", grade_hint=9)
        r = ct.post(f"/api/v2/teacher/students/{ids['s9']}/exams/import-analyze",
                    files={"file": pdf_file})
        d3 = r.json() if r.status_code == 200 else {}
        check("6a. 9. sınıf + basamak yazmayan başlık → Maarif 9. Sınıf",
              d3.get("section") == "maarif_9", str(d3.get("section")))

        # --- 7) İKİNCİ BASAMAK başlığı ---
        read_behavior["read"] = build_maarif_read(
            f"{PFX} Maarif Model İkinci Basamak Sınavı", grade_hint=12)
        r = ct.post(base, files={"file": pdf_file})
        d4 = r.json() if r.status_code == 200 else {}
        check("7a. 'İkinci Basamak' → maarif_2",
              d4.get("section") == "maarif_2", str(d4.get("section")))

        # --- 8) YAPI İMZASI: başlıkta 'maarif' yok, yapı Maarif ---
        read_behavior["read"] = build_structure_read()
        r = ct.post(base, files={"file": pdf_file})
        d5 = r.json() if r.status_code == 200 else {}
        check("8a. TDE + birleşik dersler + 125 soru → maarif (kelimesiz)",
              d5.get("universe") == "maarif", str(d5)[:160])
        check("8b. tam basamak formatı → maarif_1",
              d5.get("section") == "maarif_1", str(d5.get("section")))

        # --- 9) REGRESYON: saf TYT belgesi TYT kalmalı ---
        read_behavior["read"] = build_pure_tyt_read()
        r = ct.post(base, files={"file": pdf_file})
        d6 = r.json() if r.status_code == 200 else {}
        check("9a. klasik TYT belgesi hâlâ TYT (Maarif kuralları sızmadı)",
              d6.get("universe") == "tyt" and d6.get("section") == "tyt",
              str(d6)[:160])

        # --- 10) KAYIT: net cezası 4 + section + birleşik ders kırılımı ---
        read_behavior["read"] = build_maarif_read(
            f"{PFX} ÇAP Maarif Model Birinci Basamak Sınavı")
        r = ct.post(base, files={"file": pdf_file})
        draft = r.json()
        conf_rows = [
            {k: x[k] for k in ("subject_raw", "question_no", "topic_raw", "topic_id",
                               "correct_answer", "student_answer", "result", "is_suspect")}
            for x in draft["rows"]
        ]
        payload = {
            "title": draft["title"], "exam_date": draft["exam_date"],
            "section": draft["section"], "scope": draft["scope"],
            "grade_hint": draft["grade_hint"], "score_info": draft["score_info"],
            "rows": conf_rows,
        }
        r = ct.post(f"/api/v2/teacher/students/{ids['s11']}/exams/import-confirm",
                    data={"payload": json.dumps(payload)}, files={"file": pdf_file})
        dc = r.json().get("data", {}) if r.status_code == 200 else {}
        # 2 doğru, 2 yanlış, 1 boş → net = 2 - 2/4 = 1.5 (YKS cezası)
        check("10a. confirm 200 + net = D − Y/4 (Maarif cezası TYT ile aynı)",
              r.status_code == 200 and dc.get("net") == 1.5
              and dc.get("total_correct") == 2 and dc.get("total_wrong") == 2
              and dc.get("total_blank") == 1, f"{r.status_code} {str(dc)[:220]}")
        exam_id = dc.get("exam_id")
        with SessionLocal() as db:
            exam = db.get(ExamResult, exam_id)
            names = {s["name"] for s in json.loads(exam.subject_nets or "[]")}
            check("10b. kayıt türü maarif_1 + PDF kanıtı",
                  exam is not None and exam.section.value == "maarif_1"
                  and (exam.import_pdf_size or 0) > 0,
                  f"{exam.section if exam else None}")
            check("10c. kayıtlı ders kırılımı birleşik ('Fen Bilimleri')",
                  "Fen Bilimleri" in names and "Fizik" not in names, str(names))
            qrows = db.query(ExamResultQuestion).filter(
                ExamResultQuestion.exam_result_id == exam_id).all()
            fen_q = [q for q in qrows if q.subject_name_raw == "Fen Bilimleri"]
            check("10d. soru satırında ham ad 'Fen Bilimleri' + normalize konu Fizik",
                  any(q.topic_id == ids["fizik10"] for q in fen_q), str(len(fen_q)))

    finally:
        ai_exam_import.read_exam_pdf_double = orig_double
        svc.gemini.generate = orig_generate
        with SessionLocal() as db:
            uids = [v for k, v in ids.items() if k in ("coach", "s11", "s9")]
            exam_ids = [e.id for e in db.query(ExamResult).filter(
                ExamResult.student_id.in_(uids)).all()]
            if exam_ids:
                db.execute(sa_delete(ExamResultQuestion).where(
                    ExamResultQuestion.exam_result_id.in_(exam_ids)))
                db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exam_ids)))
            db.execute(sa_delete(ExamTopicAlias).where(
                ExamTopicAlias.created_by_id.in_(uids)))
            db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id.in_(uids)))
            db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
