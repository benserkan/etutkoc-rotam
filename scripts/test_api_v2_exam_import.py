"""Deneme PDF içe aktarma (Faz 1) — smoke.

Kapsam:
- Kapılar: anon 401 · koç ücretsiz 403 · rıza yok 403 · PDF değil 422 ·
  yabancı öğrenci 404 · kredi 6 (koç havuzundan).
- Okuma/birleştirme: çift okuma uyuşmazlığı → şüpheli · DC/ÖC'den sonuç
  türetme sembol okumasını EZER (çelişki → şüpheli) · boş ÖC → "bos".
- Tespit: TYT (anahtar kelime + öğrenci bağlamı) · LGS (8. sınıf) + ceza /3.
- NORMALİZASYON (sistemin kalbi): birebir + bağlaç + kesik-etiket ön-eki
  (deterministik) · evren-tekil geometri dersine YENİDEN ATAMA · kapalı-küme
  AI ("İşlem Yeteneği" → "Temel Kavramlar") · uydurma id DÜŞÜRÜLÜR ·
  belirsiz etiket eşleşmez (asla tahmin).
- ÖĞRENEN SÖZLÜK: confirm sonrası alias yazılır → ikinci analizde AI'sız
  (topic_source=alias) çözülür · koç düzeltmesi AI'ı ezer, AI koçu EZEMEZ.
- Confirm: net yeniden hesap + subject_nets + soru satırları + PDF kanıt ·
  mükerrer 409 / force · evren-dışı topic_id enjeksiyonu düşürülür ·
  geçersiz sonuç 422.

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
import re
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
    Subject,
    SuspiciousIp,
    Topic,
    UsageEvent,
    User,
    UserRole,
)
from app.services import ai_exam_import
from app.services import exam_import_service as svc
from app.services.exam_import_service import _subject_key as _subject_key_test
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"exim{secrets.token_hex(3)}"
PASSWORD = "ExamImport!2026X"
PDF = b"%PDF-1.4 fake exam report " + b"0" * 200
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


def topic_id(db, subject_name: str, topic_name: str) -> int:
    t = (
        db.query(Topic).join(Subject, Subject.id == Topic.subject_id)
        .filter(Subject.is_builtin.is_(True), Subject.name == subject_name,
                Topic.name == topic_name)
        .first()
    )
    assert t is not None, f"builtin konu yok: {subject_name} / {topic_name}"
    return t.id


def exam_credits(db, actor_ids: list[int]) -> int:
    # kind ORM'de enum member döner → value ile karşılaştır (str() ad verir)
    return sum(
        e.credits for e in db.query(UsageEvent)
        .filter(UsageEvent.actor_user_id.in_(actor_ids)).all()
        if e.kind and "ai_exam_import" in getattr(e.kind, "value", str(e.kind))
    )


# --- Sentetik TYT okuması (Apotemi yapısını KÜÇÜK örnekle taklit eder) ---

def build_tyt_read() -> dict:
    return {
        "exam_title": f"{PFX} MOMENTUM TYT",
        "exam_date": "2026-04-02",
        "grade_hint": 12,
        "type_hints": ["TYT"],
        "subjects": [
            # Matematik özeti BİLEREK yanlış (correct=4, gerçek 5) → çapraz sağlama yakalar
            {"name": "Matematik", "questions": 8, "correct": 4, "wrong": 2, "blank": 1, "net": 4.5},
            {"name": "TYT-TÜRKÇE", "questions": 2, "correct": 1, "wrong": 1, "blank": 0, "net": 0.75},
            {"name": "Fizik", "questions": 2, "correct": 1, "wrong": 0, "blank": 1, "net": 1.0},
        ],
        "questions": [
            # Türkçe — ders adı "TYT-TÜRKÇE" (önek temizleme testi)
            {"subject": "TYT-TÜRKÇE", "no": 1, "topic": "Sözcükte Anlam",
             "correct_answer": "C", "student_answer": "C", "result": "dogru"},
            {"subject": "TYT-TÜRKÇE", "no": 2, "topic": "Paragrafta Yardımcı Düşü",
             "correct_answer": "A", "student_answer": "B", "result": "yanlis"},
            # Matematik
            {"subject": "Matematik", "no": 1, "topic": "Rasyonel Sayılar",
             "correct_answer": "D", "student_answer": "D", "result": "dogru"},
            {"subject": "Matematik", "no": 2, "topic": "Tek Çift Sayılar",
             "correct_answer": "B", "student_answer": "C", "result": "yanlis"},
            {"subject": "Matematik", "no": 3, "topic": "Birinci Dereceden Denk",
             "correct_answer": "A", "student_answer": None, "result": None},
            {"subject": "Matematik", "no": 4, "topic": "İşlem Yeteneği",
             "correct_answer": "E", "student_answer": "E", "result": "dogru"},
            {"subject": "Matematik", "no": 5, "topic": "Üçgende Alan",
             "correct_answer": "C", "student_answer": "E", "result": "yanlis"},
            {"subject": "Matematik", "no": 6, "topic": "Zzz Gizemli Konu",
             "correct_answer": "B", "student_answer": "B", "result": "dogru"},
            {"subject": "Matematik", "no": 7, "topic": "Sayı Basamakları",
             "correct_answer": "B", "student_answer": "B", "result": "dogru"},
            # sembol "yanlis" ama DC==ÖC → türetme DOĞRU der + şüpheli işaretler
            {"subject": "Matematik", "no": 8, "topic": "Yüzde Problemleri",
             "correct_answer": "A", "student_answer": "A", "result": "yanlis"},
            # Fizik
            {"subject": "Fizik", "no": 1, "topic": "Isı ve Sıcaklık",
             "correct_answer": "D", "student_answer": "D", "result": "dogru"},
            {"subject": "Fizik", "no": 2, "topic": "Hareket ve Kuvvet",
             "correct_answer": "B", "student_answer": None, "result": "bos"},
        ],
        "score_info": {"score": 356.48, "rank_overall": 6150, "participants": 20573,
                       "extra": None},
    }


def build_lgs_read() -> dict:
    """K12-tarzı LGS okuma taklidi: ders kısaltmaları ("Din K.ve A.B.", "Tarih")
    + virgüllü ondalık net + kazanım-cümlesi etiket (gerçek 30.03.2026.pdf'ten)."""
    return {
        "exam_title": f"{PFX} LGS DENEME 1",
        "exam_date": "2026-04-10",
        "grade_hint": 8,
        "type_hints": ["LGS"],
        "subjects": [
            {"name": "Türkçe", "questions": 1, "correct": 0, "wrong": 1,
             "blank": 0, "net": "14,67"},   # virgüllü ondalık (TR belgesi)
        ],
        "questions": [
            {"subject": "Matematik", "no": 1, "topic": "Çarpanlar ve Katlar",
             "correct_answer": "A", "student_answer": "A", "result": "dogru"},
            {"subject": "Matematik", "no": 2, "topic": "Üslü İfadeler",
             "correct_answer": "B", "student_answer": "B", "result": "dogru"},
            {"subject": "Türkçe", "no": 1, "topic": "Sözcükte Anlam",
             "correct_answer": "C", "student_answer": "D", "result": "yanlis"},
            # K12 ders kısaltmaları — çözüm sistem dersine gitmeli
            {"subject": "Tarih", "no": 1,
             "topic": "Mustafa Kemal'in çocukluk ve öğrenim hayatı",
             "correct_answer": "D", "student_answer": "D", "result": "dogru"},
            {"subject": "Din K.ve A.B.", "no": 1,
             "topic": "Zekât ve sadaka ibadetini ayet ve hadislerle açıklar",
             "correct_answer": "B", "student_answer": "B", "result": "dogru"},
        ],
        "score_info": None,
    }


def build_combined_read() -> dict:
    """Birleşik TG kitapçığı taklidi (gerçek ÖZDEBİR TG AYT-4 TYT: TYT-19
    vakası): tek PDF'te TYT + AYT oturumu; ders adları çakışır (Matematik),
    soru numaraları çakışır; sayısal öğrenci sözel bölümü BOŞ bırakır."""
    return {
        "exam_title": f"{PFX} ÖZDEBİR TG AYT-4 TYT: TYT-19",
        "exam_date": "2026-02-16",
        "grade_hint": 12,
        "type_hints": ["AYT", "TYT"],
        "subjects": [],
        "questions": [
            # TYT oturumu (5 soru)
            {"subject": "Matematik", "part": "tyt", "no": 1, "topic": "Rasyonel Sayılar",
             "correct_answer": "A", "student_answer": "A", "result": "dogru"},
            {"subject": "Matematik", "part": "tyt", "no": 2, "topic": "Yüzde Problemleri",
             "correct_answer": "B", "student_answer": "C", "result": "yanlis"},
            {"subject": "Türkçe", "part": "tyt", "no": 1, "topic": "Sözcükte Anlam",
             "correct_answer": "D", "student_answer": "D", "result": "dogru"},
            {"subject": "Türkçe", "part": "tyt", "no": 2, "topic": "Cümlede Anlam",
             "correct_answer": "A", "student_answer": "A", "result": "dogru"},
            {"subject": "Türkçe", "part": "tyt", "no": 3, "topic": "Yazım Kuralları",
             "correct_answer": "E", "student_answer": "B", "result": "yanlis"},
            # AYT oturumu (9 soru) — Matematik AYNI numaralarla (çakışma testi)
            {"subject": "Matematik", "part": "ayt", "no": 1, "topic": "Trigonometri",
             "correct_answer": "E", "student_answer": "E", "result": "dogru"},
            {"subject": "Matematik", "part": "ayt", "no": 2, "topic": "Limit ve Süreklilik",
             "correct_answer": "A", "student_answer": "B", "result": "yanlis"},
            {"subject": "Matematik", "part": "ayt", "no": 3, "topic": "Trigonometri",
             "correct_answer": "C", "student_answer": "C", "result": "dogru"},
            {"subject": "Fizik", "part": "ayt", "no": 1, "topic": "Vektörler",
             "correct_answer": "B", "student_answer": "B", "result": "dogru"},
            {"subject": "Fizik", "part": "ayt", "no": 2, "topic": "Vektörler",
             "correct_answer": "D", "student_answer": "A", "result": "yanlis"},
            {"subject": "Fizik", "part": "ayt", "no": 3, "topic": "İtme ve Momentum",
             "correct_answer": "A", "student_answer": "A", "result": "dogru"},
            # Edebiyat — sayısal öğrenci BOŞ bıraktı (alt-tür tespiti + halüsinasyon)
            {"subject": "Edebiyat", "part": "ayt", "no": 1, "topic": "Divan Edebiyatı",
             "correct_answer": "C", "student_answer": None, "result": "bos"},
            {"subject": "Edebiyat", "part": "ayt", "no": 2, "topic": "Halk Edebiyatı",
             "correct_answer": "A", "student_answer": None, "result": "bos"},
            {"subject": "Edebiyat", "part": "ayt", "no": 3, "topic": "Edebi Türler",
             "correct_answer": "B", "student_answer": None, "result": "bos"},
        ],
        "score_info": None,
    }


def build_phantom_parts_read() -> dict:
    """TEK AYT belgesi ama başlıkta iki sınav adı anılıyor → Gemini'nin sayısal
    bölümü "tyt", sözeli "ayt" diye HAYALİ oturumlara böldüğü gerçek Berra
    ÖZDEBİR vakası (AYT-18 / özdebir-özel-ayt-2026.pdf). TYT tarafında Türkçe
    yok → etiketler inandırıcı değil; servis silmeli (tek oturum + AYT tespiti)."""
    return {
        "exam_title": f"{PFX} AYT: ÖZDEBİR ÖZEL DERECE AYT-1 TYT: TYT-19",
        "exam_date": "2026-04-29",
        "grade_hint": 12,
        "type_hints": ["AYT", "TYT"],
        "subjects": [
            # özet tablo da hayalî "tyt" etiketi taşıyor — o da temizlenmeli
            {"name": "Matematik", "part": "tyt", "questions": 4, "correct": 3,
             "wrong": 1, "blank": 0, "net": 2.75},
        ],
        "questions": [
            # sayısal bölüm — HAYALİ "tyt" etiketi (gerçekte AYT-MAT/AYT-FEN)
            {"subject": "Matematik", "part": "tyt", "no": 1, "topic": "Trigonometri",
             "correct_answer": "A", "student_answer": "A", "result": "dogru"},
            {"subject": "Matematik", "part": "tyt", "no": 2, "topic": "Limit ve Süreklilik",
             "correct_answer": "B", "student_answer": "C", "result": "yanlis"},
            {"subject": "Matematik", "part": "tyt", "no": 3, "topic": "Trigonometri",
             "correct_answer": "C", "student_answer": "C", "result": "dogru"},
            {"subject": "Matematik", "part": "tyt", "no": 4, "topic": "Belirsiz İntegral",
             "correct_answer": "D", "student_answer": "D", "result": "dogru"},
            {"subject": "Fizik", "part": "tyt", "no": 1, "topic": "Vektörler",
             "correct_answer": "B", "student_answer": "B", "result": "dogru"},
            {"subject": "Fizik", "part": "tyt", "no": 2, "topic": "İtme ve Momentum",
             "correct_answer": "E", "student_answer": "A", "result": "yanlis"},
            {"subject": "Fizik", "part": "tyt", "no": 3, "topic": "Vektörler",
             "correct_answer": "D", "student_answer": "D", "result": "dogru"},
            # sözel bölüm — "ayt" etiketi; sayısal öğrenci BOŞ bıraktı
            {"subject": "Edebiyat", "part": "ayt", "no": 1, "topic": "Divan Edebiyatı",
             "correct_answer": "C", "student_answer": None, "result": "bos"},
            {"subject": "Edebiyat", "part": "ayt", "no": 2, "topic": "Halk Edebiyatı",
             "correct_answer": "A", "student_answer": None, "result": "bos"},
            {"subject": "Edebiyat", "part": "ayt", "no": 3, "topic": "Edebi Türler",
             "correct_answer": "B", "student_answer": None, "result": "bos"},
            {"subject": "Tarih", "part": "ayt", "no": 1, "topic": "Milli Mücadele",
             "correct_answer": "D", "student_answer": None, "result": "bos"},
            {"subject": "Tarih", "part": "ayt", "no": 2, "topic": "Dünya Gücü Osmanlı",
             "correct_answer": "E", "student_answer": None, "result": "bos"},
        ],
        "score_info": None,
    }


def main() -> int:
    print(f"\n=== Deneme PDF içe aktarma smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False,
                     ai_capture_consent_at=datetime.now(timezone.utc))
        free_coach = User(email=f"{PFX}-tf@t.invalid", password_hash=hash_password(PASSWORD),
                          full_name="Ücretsiz Koç", role=UserRole.TEACHER, is_active=True,
                          plan="solo_free", must_change_password=False,
                          ai_capture_consent_at=datetime.now(timezone.utc))
        noconsent_coach = User(email=f"{PFX}-tn@t.invalid", password_hash=hash_password(PASSWORD),
                               full_name="Rızasız Koç", role=UserRole.TEACHER, is_active=True,
                               plan="solo_pro", must_change_password=False)
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci 12", role=UserRole.STUDENT, is_active=True,
                       grade_level=12, must_change_password=False)
        lgs_student = User(email=f"{PFX}-s8@t.invalid", password_hash=hash_password(PASSWORD),
                           full_name="Öğrenci 8", role=UserRole.STUDENT, is_active=True,
                           grade_level=8, must_change_password=False)
        free_student = User(email=f"{PFX}-sf@t.invalid", password_hash=hash_password(PASSWORD),
                            full_name="Ücretsiz Öğr", role=UserRole.STUDENT, is_active=True,
                            grade_level=12, must_change_password=False)
        nc_student = User(email=f"{PFX}-sn@t.invalid", password_hash=hash_password(PASSWORD),
                          full_name="Rızasız Öğr", role=UserRole.STUDENT, is_active=True,
                          grade_level=12, must_change_password=False)
        db.add_all([coach, free_coach, noconsent_coach, student, lgs_student,
                    free_student, nc_student])
        db.flush()
        student.teacher_id = coach.id
        lgs_student.teacher_id = coach.id
        free_student.teacher_id = free_coach.id
        nc_student.teacher_id = noconsent_coach.id
        db.commit()
        ids = {
            "coach": coach.id, "free_coach": free_coach.id,
            "noconsent_coach": noconsent_coach.id,
            "student": student.id, "lgs_student": lgs_student.id,
            "free_student": free_student.id, "nc_student": nc_student.id,
            # builtin konu id'leri (gerçek TYT taksonomisi)
            "temel": topic_id(db, "TYT Matematik", "Temel Kavramlar"),
            "rasyonel": topic_id(db, "TYT Matematik", "Rasyonel Sayılar"),
            "tekcift": topic_id(db, "TYT Matematik", "Tek ve Çift Sayılar"),
            "birinci": topic_id(db, "TYT Matematik", "Birinci Dereceden Denklemler"),
            "ucgen_alan": topic_id(db, "TYT Geometri", "Üçgende Alan"),
            "paragraf": topic_id(db, "TYT Türkçe", "Paragraf"),
            "trigonometri": topic_id(db, "AYT Matematik", "Trigonometri"),
            "limit": topic_id(db, "AYT Matematik", "Limit ve Süreklilik"),
        }

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    # --- monkeypatch: PDF okuma + kapalı-küme AI eşleme (gerçek Gemini YOK) ---
    read_behavior: dict = {"read": build_tyt_read()}
    gem_calls = {"label_match": 0}
    ai_label_map: dict[str, int] = {}  # etiket → dönecek topic_id

    def fake_double(pdf_b64: str):
        r1 = ai_exam_import._normalize_read(copy.deepcopy(read_behavior["read"]))
        r2 = ai_exam_import._normalize_read(copy.deepcopy(read_behavior["read"]))
        for q in r2["questions"]:
            # çift-okuma uyuşmazlığı: TYT setinde Matematik no 7 ÖC farklı
            if q["subject"] == "Matematik" and q.get("no") == 7 and q.get("part") is None:
                q["student_answer"] = "D"
            # halüsinasyon simülasyonu: boş Edebiyat no 1'e 2. okuma ÖC=DC yazdı
            if q["subject"] == "Edebiyat" and q.get("no") == 1:
                q["student_answer"] = "C"
            # ders adı GÜRÜLTÜSÜ simülasyonu: 2. okuma Fizik'i bölüm koduyla
            # yazdı (gerçek ÖZDEBİR AYT'de yaşandı) — kanonik anahtar eşlemeli
            if q["subject"] == "Fizik" and q.get("part") == "ayt":
                q["subject"] = "Fizik (SAY-2)"
        return r1, r2

    def fake_generate(parts, *, personal_data, json_mode=True, timeout=45.0,
                      max_output_tokens=8192, prefer_paid=True):
        gem_calls["label_match"] += 1
        prompt = parts[-1]["text"]
        mappings = []
        for m in re.finditer(r"^(\d+): (.+?) \(dersi", prompt, re.M):
            key, label = int(m.group(1)), m.group(2).strip()
            tid = ai_label_map.get(label)
            mappings.append({"key": key, "topic_id": tid})
        return json.dumps({"mappings": mappings})

    orig_double = ai_exam_import.read_exam_pdf_double
    orig_generate = svc.gemini.generate
    ai_exam_import.read_exam_pdf_double = fake_double
    svc.gemini.generate = fake_generate

    try:
        cs = TestClient(app)
        ct = TestClient(app)
        cfs = TestClient(app)
        cns = TestClient(app)
        anon = TestClient(app)
        for cli, mail in ((cs, f"{PFX}-s@t.invalid"), (ct, f"{PFX}-t@t.invalid"),
                          (cfs, f"{PFX}-sf@t.invalid"), (cns, f"{PFX}-sn@t.invalid")):
            cli.post("/api/v2/auth/login", json={"email": mail, "password": PASSWORD})

        pdf_file = ("deneme.pdf", PDF, "application/pdf")

        # 1) anon 401
        r = anon.post("/api/v2/student/exams/import-analyze", files={"file": pdf_file})
        check("1. anonim → 401", r.status_code == 401, r.text[:100])

        # 2) ücretsiz koçun öğrencisi → 403 plan_upgrade_required
        r = cfs.post("/api/v2/student/exams/import-analyze", files={"file": pdf_file})
        check("2. koç ücretsiz pakette → 403 plan_upgrade_required",
              r.status_code == 403
              and r.json()["detail"]["code"] == "plan_upgrade_required", r.text[:120])

        # 3) rıza vermemiş koçun öğrencisi → 403 consent_required
        r = cns.post("/api/v2/student/exams/import-analyze", files={"file": pdf_file})
        check("3. koç rızasız → 403 consent_required",
              r.status_code == 403
              and r.json()["detail"]["code"] == "consent_required", r.text[:120])

        # 4) PDF olmayan dosya → 422
        r = cs.post("/api/v2/student/exams/import-analyze",
                    files={"file": ("resim.png", b"x" * 50, "image/png")})
        check("4. PDF değil → 422 invalid_file_type",
              r.status_code == 422
              and r.json()["detail"]["code"] == "invalid_file_type", r.text[:120])

        # 5) yabancı öğrenci → 404 (koç yolunda sızıntı yok)
        r = ct.post(f"/api/v2/teacher/students/{ids['free_student']}/exams/import-analyze",
                    files={"file": pdf_file})
        check("5. yabancı öğrenci → 404", r.status_code == 404, r.text[:120])

        # --- 6) MUTLU YOL: analiz (öğrenci tetikler, kredi KOÇTAN) ---
        ai_label_map.update({
            "İşlem Yeteneği": ids["temel"],
            "Paragrafta Yardımcı Düşü": ids["paragraf"],
            "Zzz Gizemli Konu": 999_999,   # uydurma id — düşürülmeli
        })
        r = cs.post("/api/v2/student/exams/import-analyze", files={"file": pdf_file})
        check("6. analiz 200 + TYT tespiti",
              r.status_code == 200 and r.json()["universe"] == "tyt"
              and r.json()["section"] == "tyt" and r.json()["scope"] == "full",
              r.text[:200])
        draft = r.json() if r.status_code == 200 else {}
        rows = {(x["subject_raw"], x["question_no"]): x for x in draft.get("rows", [])}

        def row(subj, no):
            return rows.get((subj, no), {})

        # 7) deterministik katman
        check("7a. birebir eşleşme (Rasyonel Sayılar, source=auto)",
              row("Matematik", 1).get("topic_id") == ids["rasyonel"]
              and row("Matematik", 1).get("topic_source") == "auto",
              str(row("Matematik", 1))[:160])
        check("7b. bağlaç farkı eşleşti (Tek Çift → Tek ve Çift)",
              row("Matematik", 2).get("topic_id") == ids["tekcift"],
              str(row("Matematik", 2))[:160])
        check("7c. KESİK etiket ön-ek eşleşmesi (Birinci Dereceden Denk…)",
              row("Matematik", 3).get("topic_id") == ids["birinci"],
              str(row("Matematik", 3))[:160])

        # 8) geometri dersine YENİDEN ATAMA (belge Matematik bölümünde verdi)
        g = row("Matematik", 5)
        check("8. geometri sorusu TYT Geometri dersine atandı",
              g.get("topic_id") == ids["ucgen_alan"]
              and g.get("subject_name") == "TYT Geometri", str(g)[:160])

        # 9) kapalı-küme AI: İşlem Yeteneği → Temel Kavramlar; uydurma id düşer
        check("9a. AI anlamsal eşleme (İşlem Yeteneği → Temel Kavramlar)",
              row("Matematik", 4).get("topic_id") == ids["temel"]
              and row("Matematik", 4).get("topic_source") == "ai",
              str(row("Matematik", 4))[:160])
        check("9b. uydurma topic_id DÜŞÜRÜLDÜ (Zzz → eşleşmedi)",
              row("Matematik", 6).get("topic_id") is None
              and row("Matematik", 6).get("topic_source") == "none",
              str(row("Matematik", 6))[:160])
        check("9c. kesik Türkçe etiketi AI ile Paragraf'a eşlendi",
              row("TYT-TÜRKÇE", 2).get("topic_id") == ids["paragraf"],
              str(row("TYT-TÜRKÇE", 2))[:160])

        # 10) çift okuma uyuşmazlığı → şüpheli
        check("10. çift okuma uyuşmazlığı (M-7 ÖC farklı) → is_suspect",
              row("Matematik", 7).get("is_suspect") is True,
              str(row("Matematik", 7))[:160])

        # 11) DC/ÖC türetmesi sembolü ezer (+ şüpheli)
        y = row("Matematik", 8)
        check("11. DC==ÖC ama sembol 'yanlış' → sonuç DOĞRU + şüpheli",
              y.get("result") == "dogru" and y.get("is_suspect") is True,
              str(y)[:160])

        # 12) boş ÖC → bos
        check("12. ÖC boş → sonuç 'bos'",
              row("Matematik", 3).get("result") == "bos"
              and row("Fizik", 2).get("result") == "bos",
              str(row("Fizik", 2))[:160])

        # 13) çapraz sağlama: Matematik özeti (bilerek yanlış) yakalandı
        chk = {c["code"]: c for c in draft.get("checks", [])}
        mat_check = next((c for k, c in chk.items()
                          if k.startswith("subject_counts:matematik")), None)
        tr_check = next((c for k, c in chk.items()
                         if k.startswith("subject_counts:tyt turkce")), None)
        check("13a. özet↔satır çapraz sağlama Matematik'te UYUŞMAZLIK yakaladı",
              mat_check is not None and mat_check["ok"] is False,
              str(mat_check)[:160])
        check("13b. Türkçe özeti tutarlı (ok=True)",
              tr_check is not None and tr_check["ok"] is True, str(tr_check)[:160])
        check("13c. tür↔müfredat uyumu kontrolü OK (11/12 eşleşti)",
              chk.get("universe_match", {}).get("ok") is True,
              str(chk.get("universe_match"))[:160])

        # 14) kredi: koç havuzundan 6
        with SessionLocal() as db:
            used = exam_credits(db, [ids["student"], ids["coach"]])
        check("14. kredi KOÇUN havuzundan 6 düştü", used == 6, f"used={used}")

        # 15) section_choices okul dahil (manuel tür seçici)
        vals = {c["value"] for c in draft.get("section_choices", [])}
        check("15. tür seçici okul dahil tüm türleri sunar",
              {"tyt", "ayt_say", "lgs", "okul"} <= vals, str(vals))

        # --- 16) CONFIRM: Zzz satırını koç elle Rasyonel'e bağlar ---
        conf_rows = []
        for x in draft["rows"]:
            rr = {k: x[k] for k in ("subject_raw", "question_no", "topic_raw",
                                    "topic_id", "correct_answer", "student_answer",
                                    "result", "is_suspect")}
            if x["topic_raw"] == "Zzz Gizemli Konu":
                rr["topic_id"] = ids["rasyonel"]
                rr["manually_edited"] = True
            conf_rows.append(rr)
        payload = {
            "title": draft["title"], "exam_date": draft["exam_date"],
            "section": draft["section"], "scope": draft["scope"],
            "grade_hint": draft["grade_hint"], "score_info": draft["score_info"],
            "rows": conf_rows,
        }
        r = cs.post("/api/v2/student/exams/import-confirm",
                    data={"payload": json.dumps(payload)}, files={"file": pdf_file})
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        check("16a. confirm 200 + net doğru (7D 3Y 2B → 6.25)",
              r.status_code == 200 and d.get("net") == 6.25
              and d.get("total_correct") == 7 and d.get("total_wrong") == 3
              and d.get("total_blank") == 2, r.text[:250])
        check("16b. 12 soru satırı + hepsi konuya bağlandı (elle düzeltme dahil)",
              d.get("question_count") == 12 and d.get("matched_topic_count") == 12,
              str(d)[:200])
        check("16c. yanlış konu id'leri (YSA köprüsü verisi) doğru",
              sorted(d.get("wrong_topic_ids", [])) == sorted(
                  [ids["paragraf"], ids["tekcift"], ids["ucgen_alan"]]),
              str(d.get("wrong_topic_ids")))
        exam_id = d.get("exam_id")

        with SessionLocal() as db:
            exam = db.get(ExamResult, exam_id)
            subj_nets = json.loads(exam.subject_nets or "[]")
            names = {s["name"] for s in subj_nets}
            check("16d. kayıt izleri: import_source + PDF kanıt + ders grupları",
                  exam.import_source == "pdf_import"
                  and (exam.import_pdf_size or 0) > 0
                  and {"TYT Türkçe", "TYT Matematik", "TYT Geometri", "TYT Fizik"} <= names,
                  f"src={exam.import_source} names={names}")
            qs = db.query(ExamResultQuestion).filter(
                ExamResultQuestion.exam_result_id == exam_id).all()
            edited = [q for q in qs if q.manually_edited]
            check("16e. soru satırları DB'de (ham etiket + normalize konu + elle iz)",
                  len(qs) == 12 and len(edited) == 1
                  and edited[0].topic_id == ids["rasyonel"]
                  and edited[0].topic_label_raw == "Zzz Gizemli Konu",
                  f"n={len(qs)} edited={len(edited)}")

        # 17) mükerrer: aynı ad+tarih → 409; force → 200
        r = cs.post("/api/v2/student/exams/import-confirm",
                    data={"payload": json.dumps(payload)}, files={"file": pdf_file})
        check("17a. mükerrer deneme → 409 duplicate_exam",
              r.status_code == 409
              and r.json()["detail"]["code"] == "duplicate_exam", r.text[:150])
        r = cs.post("/api/v2/student/exams/import-confirm",
                    data={"payload": json.dumps({**payload, "force": True})},
                    files={"file": pdf_file})
        check("17b. force=True → yine de kaydeder", r.status_code == 200, r.text[:150])
        force_exam_id = r.json().get("data", {}).get("exam_id")

        # 18) ÖĞRENEN SÖZLÜK: alias'lar yazıldı (AI→ai, elle→coach)
        with SessionLocal() as db:
            a_islem = db.query(ExamTopicAlias).filter(
                ExamTopicAlias.scope == "tyt",
                ExamTopicAlias.label_key == "islem yetenegi").first()
            a_zzz = db.query(ExamTopicAlias).filter(
                ExamTopicAlias.scope == "tyt",
                ExamTopicAlias.label_key == "zzz gizemli konu").first()
            check("18. sözlük: İşlem Yeteneği (ai) + Zzz (coach) öğrenildi",
                  a_islem is not None and a_islem.topic_id == ids["temel"]
                  and a_islem.source == "ai"
                  and a_zzz is not None and a_zzz.topic_id == ids["rasyonel"]
                  and a_zzz.source == "coach",
                  f"islem={a_islem} zzz={a_zzz}")

        # 19) ikinci analiz: sözlük çözer, AI'ya HİÇ gidilmez
        before = gem_calls["label_match"]
        r = cs.post("/api/v2/student/exams/import-analyze", files={"file": pdf_file})
        d2 = r.json() if r.status_code == 200 else {}
        rows2 = {(x["subject_raw"], x["question_no"]): x for x in d2.get("rows", [])}
        islem2 = rows2.get(("Matematik", 4), {})
        zzz2 = rows2.get(("Matematik", 6), {})
        check("19a. ikinci analizde İşlem Yeteneği SÖZLÜKTEN çözüldü (alias)",
              islem2.get("topic_id") == ids["temel"]
              and islem2.get("topic_source") == "alias", str(islem2)[:160])
        check("19b. koç düzeltmesi (Zzz→Rasyonel) sözlükten uygulandı",
              zzz2.get("topic_id") == ids["rasyonel"]
              and zzz2.get("topic_source") == "alias", str(zzz2)[:160])
        check("19c. AI çağrısı GEREKMEDİ (maliyet düştü)",
              gem_calls["label_match"] == before,
              f"before={before} after={gem_calls['label_match']}")
        check("19d. mükerrer uyarısı önizlemede (duplicate_exam_id dolu)",
              d2.get("duplicate_exam_id") == exam_id,
              str(d2.get("duplicate_exam_id")))

        # 20) AI koç kaydını EZEMEZ: Zzz'yi ai-kaynaklı Temel'e çevirme girişimi
        conf3 = [dict(rr) for rr in conf_rows]
        for rr in conf3:
            if rr["topic_raw"] == "Zzz Gizemli Konu":
                rr["topic_id"] = ids["temel"]
                rr["manually_edited"] = False   # ai kaynaklı gibi
        r = cs.post("/api/v2/student/exams/import-confirm",
                    data={"payload": json.dumps(
                        {**payload, "title": payload["title"] + " B",
                         "rows": conf3})},
                    files={"file": pdf_file})
        with SessionLocal() as db:
            a_zzz = db.query(ExamTopicAlias).filter(
                ExamTopicAlias.scope == "tyt",
                ExamTopicAlias.label_key == "zzz gizemli konu").first()
            check("20. AI, koç düzeltmesini SÖZLÜKTE ezemedi (coach kalır)",
                  r.status_code == 200 and a_zzz is not None
                  and a_zzz.topic_id == ids["rasyonel"]
                  and a_zzz.source == "coach", f"zzz={a_zzz}")
        exam3_id = r.json().get("data", {}).get("exam_id")

        # 21) evren-dışı topic_id enjeksiyonu → düşürülür (kayıt topic'siz)
        inj_rows = [dict(rr) for rr in conf_rows]
        inj_target = next(rr for rr in inj_rows
                          if rr["subject_raw"] == "TYT-TÜRKÇE"
                          and rr["question_no"] == 1)
        inj_target["topic_id"] = 999_999
        r = cs.post("/api/v2/student/exams/import-confirm",
                    data={"payload": json.dumps(
                        {**payload, "title": payload["title"] + " C",
                         "rows": inj_rows})},
                    files={"file": pdf_file})
        inj_ok = False
        if r.status_code == 200:
            inj_exam_id = r.json()["data"]["exam_id"]
            with SessionLocal() as db:
                q0 = (db.query(ExamResultQuestion)
                      .filter(ExamResultQuestion.exam_result_id == inj_exam_id,
                              ExamResultQuestion.subject_name_raw == "TYT-TÜRKÇE",
                              ExamResultQuestion.question_no == 1).first())
                inj_ok = q0 is not None and q0.topic_id is None
        check("21. evren-dışı topic_id enjeksiyonu DÜŞÜRÜLDÜ", inj_ok, r.text[:150])

        # 22) geçersiz sonuç değeri → 422
        bad = [dict(rr) for rr in conf_rows]
        bad[0]["result"] = "belki"
        r = cs.post("/api/v2/student/exams/import-confirm",
                    data={"payload": json.dumps(
                        {**payload, "title": payload["title"] + " D", "rows": bad})},
                    files={"file": pdf_file})
        check("22. geçersiz sonuç → 422 invalid_result",
              r.status_code == 422
              and r.json()["detail"]["code"] == "invalid_result", r.text[:150])

        # --- 23) LGS: 8. sınıf öğrencisi + koç yüzeyi + ceza /3 ---
        read_behavior["read"] = build_lgs_read()
        ai_label_map.clear()
        r = ct.post(f"/api/v2/teacher/students/{ids['lgs_student']}/exams/import-analyze",
                    files={"file": pdf_file})
        dl = r.json() if r.status_code == 200 else {}
        check("23a. LGS tespiti (8. sınıf + anahtar kelime)",
              r.status_code == 200 and dl.get("universe") == "lgs"
              and dl.get("section") == "lgs", r.text[:200])
        lrows = {(x["subject_raw"], x["question_no"]): x for x in dl.get("rows", [])}
        check("23b. K12 ders kısaltmaları çözüldü (Tarih→İnkılap · Din K.ve A.B.→Din)",
              lrows.get(("Tarih", 1), {}).get("subject_name")
              == "T.C. İnkılap Tarihi ve Atatürkçülük"
              and lrows.get(("Din K.ve A.B.", 1), {}).get("subject_name")
              == "Din Kültürü ve Ahlak Bilgisi",
              str({k: v.get("subject_name") for k, v in lrows.items()})[:200])
        tr_sum = next((s for s in dl.get("subjects", [])
                       if s["name"] == "Türkçe"), None)
        check("23c. virgüllü ondalık net parse edildi (14,67 → 14.67)",
              tr_sum is not None and tr_sum.get("doc_net") == 14.67,
              str(tr_sum)[:160])
        lgs_payload = {
            "title": dl.get("title"), "exam_date": dl.get("exam_date"),
            "section": "lgs",
            "rows": [{k: x[k] for k in ("subject_raw", "question_no", "topic_raw",
                                        "topic_id", "correct_answer",
                                        "student_answer", "result", "is_suspect")}
                     for x in dl.get("rows", [])],
        }
        r = ct.post(f"/api/v2/teacher/students/{ids['lgs_student']}/exams/import-confirm",
                    data={"payload": json.dumps(lgs_payload)}, files={"file": pdf_file})
        dnet = r.json().get("data", {}).get("net") if r.status_code == 200 else None
        check("23d. LGS net cezası /3 (4D 1Y → 3.67)",
              r.status_code == 200 and dnet == 3.67, r.text[:200])

        # 24) koç deneme listesi yeni kaydı görür (mevcut KP4a ucu — entegrasyon)
        r = ct.get(f"/api/v2/teacher/students/{ids['lgs_student']}/exams")
        titles = [x["title"] for x in r.json().get("rows", [])] if r.status_code == 200 else []
        check("24. içe aktarılan deneme mevcut Denemeler listesinde",
              r.status_code == 200 and any(PFX in t for t in titles),
              str(titles)[:150])

        # --- 25) BİRLEŞİK TG BELGESİ (TYT+AYT tek PDF) — gerçek ÖZDEBİR vakası ---
        read_behavior["read"] = build_combined_read()
        ai_label_map.clear()
        r = cs.post("/api/v2/student/exams/import-analyze", files={"file": pdf_file})
        dcm = r.json() if r.status_code == 200 else {}
        pmap = {p["part"]: p for p in dcm.get("parts", [])}
        check("25a. iki oturum ayrıştı (tyt 5 + ayt 9)",
              r.status_code == 200 and set(pmap) == {"tyt", "ayt"}
              and pmap["tyt"]["question_count"] == 5
              and pmap["ayt"]["question_count"] == 9, r.text[:200])
        check("25b. AYT alt-türü CEVAPLARDAN tespit (sözel boş → AYT Sayısal)",
              pmap.get("ayt", {}).get("section") == "ayt_say",
              str(pmap.get("ayt"))[:150])
        rows25 = dcm.get("rows", [])
        tyt_mat = next((x for x in rows25 if x["exam_part"] == "tyt"
                        and x["subject_raw"] == "Matematik" and x["question_no"] == 1), {})
        ayt_mat = next((x for x in rows25 if x["exam_part"] == "ayt"
                        and x["subject_raw"] == "Matematik" and x["question_no"] == 1), {})
        check("25c. aynı ders adı iki EVRENDE ayrı normalize (TYT Mat ↔ AYT Mat)",
              tyt_mat.get("topic_id") == ids["rasyonel"]
              and tyt_mat.get("subject_name") == "TYT Matematik"
              and ayt_mat.get("topic_id") == ids["trigonometri"]
              and ayt_mat.get("subject_name") == "AYT Matematik",
              f"tyt={tyt_mat.get('topic_id')}/{tyt_mat.get('subject_name')} "
              f"ayt={ayt_mat.get('topic_id')}/{ayt_mat.get('subject_name')}")
        edb = next((x for x in rows25 if x["subject_raw"] == "Edebiyat"
                    and x["question_no"] == 1), {})
        guard_chk = next((c for c in dcm.get("checks", [])
                          if c["code"] == "blank_answer_guard"), None)
        check("25d. boş-uydurma koruması: BOŞ kalır + satır sarı DEĞİL + TOPLU uyarı",
              edb.get("result") == "bos" and edb.get("student_answer") is None
              and edb.get("is_suspect") is False
              and guard_chk is not None and guard_chk["ok"] is False,
              f"edb={str(edb)[:120]} guard={guard_chk}")
        mat_sus = [x for x in rows25 if x["subject_raw"] == "Matematik" and x["is_suspect"]]
        check("25e. oturumlar arası aynı-numara çakışması ŞÜPHELİ üretmedi",
              len(mat_sus) == 0, f"{len(mat_sus)} şüpheli")
        # ders adı gürültüsü: r2 "Fizik (SAY-2)" yazdı → kanonik anahtar eşledi
        fiz = [x for x in rows25 if x["exam_part"] == "ayt"
               and _subject_key_test(x["subject_raw"]) == "fizik"]
        check("25g. ders adı bölüm-kodu gürültüsü eşleşmeyi BOZMADI (Fizik)",
              len(fiz) == 3 and all(not x["is_suspect"] for x in fiz)
              and all(x.get("subject_name") == "AYT Fizik" for x in fiz),
              f"n={len(fiz)} sus={[x['is_suspect'] for x in fiz]} "
              f"names={[x.get('subject_name') for x in fiz]}")
        # yalnız AYT oturumunu kaydet (net /4: 4D 2Y 3B → 3.5)
        ayt_rows = [x for x in rows25 if x["exam_part"] == "ayt"]
        p25 = {
            "title": (dcm.get("title") or "") + " — AYT", "exam_date": dcm.get("exam_date"),
            "section": "ayt_say",
            "rows": [{k: x[k] for k in ("subject_raw", "question_no", "topic_raw",
                                        "topic_id", "correct_answer",
                                        "student_answer", "result", "is_suspect")}
                     for x in ayt_rows],
        }
        for x in p25["rows"]:
            # 27c hazırlığı: bir satır eşleşmeden kaydedilsin (düzenleme
            # akışında güncel taksonomiyle yeniden eşlenecek)
            if x["subject_raw"] == "Matematik" and x["question_no"] == 2:
                x["topic_id"] = None
        r = cs.post("/api/v2/student/exams/import-confirm",
                    data={"payload": json.dumps(p25)}, files={"file": pdf_file})
        d25 = r.json().get("data", {}) if r.status_code == 200 else {}
        check("25f. yalnız AYT oturumu kaydedildi (ayt_say · 9 soru · net 3.5)",
              r.status_code == 200 and d25.get("section") == "ayt_say"
              and d25.get("question_count") == 9 and d25.get("net") == 3.5
              and d25.get("total_blank") == 3, r.text[:250])

        # --- 26) HAYALİ OTURUM ETİKETİ (tek AYT belgesi, başlıkta iki sınav adı) ---
        # Gerçek Berra ÖZDEBİR vakası: Gemini sayısal bölümü "tyt" diye
        # etiketledi; TYT tarafında Türkçe olmadığından etiketler İNANDIRICI
        # DEĞİL → servis siler, belge TEK AYT oturumu olarak işlenir.
        read_behavior["read"] = build_phantom_parts_read()
        ai_label_map.clear()
        r = cs.post("/api/v2/student/exams/import-analyze", files={"file": pdf_file})
        d26 = r.json() if r.status_code == 200 else {}
        parts26 = d26.get("parts", [])
        check("26a. hayalet oturum bölünmesi YOK (tek oturum, part=None)",
              r.status_code == 200 and len(parts26) == 1
              and parts26[0]["part"] is None, r.text[:200])
        check("26b. tespit AYT / Sayısal (TYT DEĞİL — cevaplanan bölümlerden)",
              d26.get("universe") == "ayt" and d26.get("section") == "ayt_say",
              f"{d26.get('universe')}/{d26.get('section')}")
        rows26 = d26.get("rows", [])
        parts_set26 = {x["exam_part"] for x in rows26}
        mat26 = next((x for x in rows26 if x["subject_raw"] == "Matematik"
                      and x["question_no"] == 1), {})
        check("26c. 'tyt' etiketli satırlar AYT evreninde normalize edildi",
              parts_set26 == {None}
              and mat26.get("topic_id") == ids["trigonometri"]
              and mat26.get("subject_name") == "AYT Matematik",
              f"parts={parts_set26} mat={mat26.get('topic_id')}"
              f"/{mat26.get('subject_name')}")
        # özet tablodaki hayalî part da temizlendi → çapraz sağlama hizalı çalıştı
        sc26 = next((c for c in d26.get("checks", [])
                     if c["code"].startswith("subject_counts:")
                     and "matematik" in c["code"]), None)
        check("26d. özet ↔ satır çapraz sağlaması part'sız hizalandı (Matematik OK)",
              sc26 is not None and sc26["ok"] is True, str(sc26)[:150])

        # --- 27) KAYITLI İÇE AKTARIMI DÜZENLE (satır düzeyi; kredi düşmez) ---
        exam25_id = d25.get("exam_id")
        r = ct.get(f"/api/v2/teacher/exams/{exam25_id}/import-rows")
        d27 = r.json() if r.status_code == 200 else {}
        rows27 = d27.get("rows", [])
        check("27a. düzenleme taslağı açıldı (9 satır · kredi 0 · tek oturum)",
              r.status_code == 200 and len(rows27) == 9
              and d27.get("credits_charged") == 0
              and len(d27.get("parts", [])) == 1
              and d27.get("section") == "ayt_say", r.text[:200])
        m1 = next((x for x in rows27 if x["subject_raw"] == "Matematik"
                   and x["question_no"] == 1), {})
        check("27b. kayıtlı konu eşleşmesi KORUNDU (kaynak: kayıtlı)",
              m1.get("topic_id") == ids["trigonometri"]
              and m1.get("topic_source") == "kayitli", str(m1)[:150])
        m2 = next((x for x in rows27 if x["subject_raw"] == "Matematik"
                   and x["question_no"] == 2), {})
        check("27c. eşleşmemiş satır güncel taksonomi/sözlükle YENİDEN eşlendi",
              m2.get("topic_id") == ids["limit"]
              and m2.get("topic_source") in ("auto", "alias"), str(m2)[:150])

        # sonuç düzeltmesi: Mat no1 dogru→yanlis → net 3.5 → 2.25 (AYT /4)
        upd_rows = []
        for x in rows27:
            row = {k: x[k] for k in ("subject_raw", "question_no", "topic_raw",
                                     "topic_id", "correct_answer",
                                     "student_answer", "result", "is_suspect")}
            if x["subject_raw"] == "Matematik" and x["question_no"] == 1:
                row["result"] = "yanlis"
                row["manually_edited"] = True
            upd_rows.append(row)
        r = ct.post(f"/api/v2/teacher/exams/{exam25_id}/import-rows", json={
            "title": d27["title"], "exam_date": d27["exam_date"],
            "section": "ayt_say", "rows": upd_rows,
        })
        d27u = r.json().get("data", {}) if r.status_code == 200 else {}
        check("27d. yeniden kaydet → net/toplamlar güncellendi (3.5 → 2.25)",
              r.status_code == 200 and d27u.get("net") == 2.25
              and d27u.get("total_correct") == 3 and d27u.get("total_wrong") == 3
              and d27u.get("question_count") == 9, r.text[:250])
        r = ct.get(f"/api/v2/teacher/students/{ids['student']}/exams")
        lst = r.json().get("rows", []) if r.status_code == 200 else []
        ex27 = next((x for x in lst if x["id"] == exam25_id), {})
        check("27e. deneme listesi güncellendi + import_source görünür",
              ex27.get("net") == 2.25
              and ex27.get("import_source") == "pdf_import",
              str({k: ex27.get(k) for k in ("net", "import_source")}))

        # sahiplik + rol + tür kapıları
        cft = TestClient(app)
        cft.post("/api/v2/auth/login",
                 json={"email": f"{PFX}-tf@t.invalid", "password": PASSWORD})
        r1b = cft.get(f"/api/v2/teacher/exams/{exam25_id}/import-rows")
        r2b = cs.get(f"/api/v2/teacher/exams/{exam25_id}/import-rows")
        check("27f. yabancı koç 404 + öğrenci 403",
              r1b.status_code == 404 and r2b.status_code == 403,
              f"{r1b.status_code}/{r2b.status_code}")
        r = ct.post(f"/api/v2/teacher/students/{ids['student']}/exams", json={
            "title": f"{PFX} manuel deneme", "exam_date": "2026-03-01",
            "section": "ayt_say", "total_correct": 10, "total_wrong": 5,
            "total_blank": 5})
        man_id = ((r.json().get("data") or {}).get("id")
                  if r.status_code == 200 else None)
        rman = (ct.get(f"/api/v2/teacher/exams/{man_id}/import-rows")
                if man_id else r)
        check("27g. manuel deneme satır-düzenlemeye kapalı (422 not_imported)",
              man_id is not None and rman.status_code == 422
              and (rman.json().get("detail") or {}).get("code") == "not_imported",
              rman.text[:150])

    finally:
        ai_exam_import.read_exam_pdf_double = orig_double
        svc.gemini.generate = orig_generate
        # --- temizlik (SQLite FK cascade kapalı → explicit) ---
        with SessionLocal() as db:
            uids = [v for k, v in ids.items()
                    if k in ("coach", "free_coach", "noconsent_coach", "student",
                             "lgs_student", "free_student", "nc_student")]
            exam_ids = [e.id for e in db.query(ExamResult).filter(
                ExamResult.student_id.in_(uids)).all()]
            if exam_ids:
                db.execute(sa_delete(ExamResultQuestion).where(
                    ExamResultQuestion.exam_result_id.in_(exam_ids)))
                db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exam_ids)))
            db.execute(sa_delete(ExamTopicAlias).where(
                ExamTopicAlias.created_by_id.in_(uids)))
            db.execute(sa_delete(UsageEvent).where(
                UsageEvent.actor_user_id.in_(uids)))
            db.execute(sa_delete(CreditAccount).where(
                CreditAccount.owner_id.in_(uids),
                CreditAccount.owner_type == "user"))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAILED: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
