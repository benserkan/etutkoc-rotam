# -*- coding: utf-8 -*-
"""App Store / Play Store inceleme demo hesapları — IDEMPOTENT seed.

Çalıştır (yerel / prod aynı):
    PYTHONPATH=. python scripts/seed_appstore_demo.py
    PYTHONPATH=. python scripts/seed_appstore_demo.py --reset   # = idempotent (önce sil, sonra kur)

Bu script App Store Connect + Google Play "App Review" sürecinde inceleyenin
giriş yapıp uygulamayı (özellikle KOÇ panelini) zengin veriyle gezebilmesi için
tanıtım ekosistemini kurar. Tüm kayıtlar SABİT `demo_seed_id="appstore-demo"`
ile işaretlenir → her çalıştırmada önce bu seed_id'ye ait her şey
(`demo_seed.delete_demo_session` transitif kapanışıyla) silinir, sonra yeniden
kurulur. Yani tekrar çalıştırmak DAİMA güvenlidir ve aynı sonucu üretir.

ROSTER (toplam ~11 kullanıcı + 1 kurum):
  Kurum: "App Store Demo Akademi" (etut_standart)
    - 1 Kurum Yöneticisi (INSTITUTION_ADMIN)
    - 5 kuruma bağlı öğretmen (TEACHER, institution_id set) — her birine 1 öğrenci
      (kurum panelinin boş kalmaması için daha hafif veri).
  Bağımsız: "App Store Demo Bağımsız Koç" (TEACHER, institution_id=None,
    plan=solo_pro → AI özellikleri açık) — ASIL ZENGİN DEMO. İnceleyen çoğunlukla
    bu koç hesabıyla girer.
    - 5 öğrenci — 5 sınav kategorisinin her birinden BİRER:
        LGS (8. sınıf), Lise 9, Lise 10, Lise 11, Mezun (YKS).
    - 5 veli (PARENT) — koçun 5 öğrencisine ParentStudentLink ile bağlı.

KOÇUN HER ÖĞRENCİSİ İÇİN (zengin):
  - ~5 sınav-uygun demo kitap (SORU_BANKASI + 1 deneme kitabı), her biri koça ait,
    bölümlü (BookSection.test_count). Müfredat (Subject/Topic/Book/BookSection)
    `demo_seed._seed_curriculum` desenini izler ama sınav türüne göre adlandırılır.
  - 3 ayrı haftaya yayılı WeeklyProgram (geçen hafta / bu hafta / gelecek hafta),
    her hafta birkaç görev — COMPLETED / PARTIAL / PENDING karışık → SectionProgress
    .reserved_count > 0 görünür (rezerv mantığı _seed_student_data ile birebir).
    Görevler is_draft=False (yayında).
  - >=10 ExamResult, sınav türüne uygun bölüm (LGS / TYT / AYT_*), ~3 aya yayılı
    tarih + compute_net ile değişken netler.
  - Anketler: 2-3 SurveyTemplate atanır — bazısı COMPLETED (cevap + skor), bazısı
    IN_PROGRESS, bazısı sadece PENDING.
  - TaskRequest: birkaç (öğrenci→koç) — bazısı PENDING, bazısı APPROVED/RESOLVED.

KOÇ TAHSİLATI (yalnız bağımsız koç öğrencileri):
  - CoachStudentRate (session_fee=2500) + birkaç ödenmiş CoachPayment (nakit/havale,
    farklı period_month "YYYY-MM").

KURUM ÖĞRETMENLERİNİN ÖĞRENCİLERİ (daha hafif): kitap + 1 hafta görev + birkaç deneme.

Tüm demo kullanıcılar: is_demo=True, must_change_password=False, şifre Demo123!@,
email_verified_at dolu.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    BookType,
    Institution,
    ParentRelation,
    ParentStudentLink,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskRequest,
    TaskStatus,
    TaskType,
    Topic,
    Track,
    User,
    UserRole,
)
from app.models.coach_billing import CoachPayment, CoachPaymentMethod, CoachStudentRate
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult, compute_net
from app.models.survey import (
    ASSIGNMENT_COMPLETED,
    ASSIGNMENT_IN_PROGRESS,
    ASSIGNMENT_PENDING,
    SurveyAssignment,
    SurveyQuestion,
    SurveyTemplate,
)
from app.models.task_request import RequestStatus, RequestType
from app.services import survey_service
from app.services.demo_seed import DEMO_PASSWORD, _new_user, delete_demo_session
from app.services.security import hash_password


# Sabit seed_id — idempotency anahtarı. Tüm kullanıcı + kurum bu ID ile işaretlenir.
SEED_ID = "appstore-demo"
LABEL = "App Store / Play Store inceleme demosu"
EMAIL_DOMAIN = "etutkoc.app"
NAME_PREFIX = "App Store Demo"

# Deterministik veri için sabit tohum (her çalıştırmada aynı netler/sayılar)
_RNG = random.Random(20260628)


# =============================================================================
# Sınav kategorisi profilleri — öğrenci başına ders + kitap + deneme türü
# =============================================================================
# Her kategori: grade_level / is_graduate / track + dersler (ad + bölümler) +
# kitap türleri + deneme ExamSection'ları (>=10 deneme türe göre dağıtılır).

def _sections(pairs: list[tuple[str, int]]) -> list[tuple[str, int]]:
    return pairs


# Soru bankası bölümleri (label, test_count)
_LGS_SUBJECTS = [
    ("LGS Matematik", _sections([("Çarpanlar ve Katlar", 18), ("Üslü İfadeler", 16),
                                 ("Kareköklü İfadeler", 16), ("Olasılık", 14)])),
    ("LGS Türkçe", _sections([("Sözcükte Anlam", 15), ("Cümlede Anlam", 15),
                              ("Paragraf", 20), ("Fiilimsiler", 12)])),
    ("LGS Fen Bilimleri", _sections([("Mevsimler ve İklim", 14), ("DNA ve Genetik Kod", 16),
                                     ("Basınç", 12), ("Madde ve Endüstri", 14)])),
    ("LGS T.C. İnkılap Tarihi", _sections([("Bir Kahraman Doğuyor", 12),
                                           ("Milli Uyanış", 14)])),
]

_TYT_SUBJECTS = [
    ("TYT Matematik", _sections([("Temel Kavramlar", 18), ("Problemler", 20),
                                 ("Fonksiyonlar", 16), ("Olasılık", 12)])),
    ("TYT Türkçe", _sections([("Sözcükte Anlam", 16), ("Cümlede Anlam", 16),
                              ("Paragraf", 22), ("Dil Bilgisi", 14)])),
    ("TYT Fizik", _sections([("Hareket ve Kuvvet", 14), ("Enerji", 12),
                             ("Elektrostatik", 10)])),
]

_AYT_SAY_SUBJECTS = [
    ("AYT Matematik", _sections([("Türev", 18), ("İntegral", 16),
                                 ("Limit ve Süreklilik", 14), ("Diziler", 10)])),
    ("AYT Fizik", _sections([("Çembersel Hareket", 12), ("Basit Harmonik Hareket", 12),
                             ("Elektromanyetizma", 12)])),
    ("AYT Kimya", _sections([("Kimyasal Tepkimeler", 14), ("Organik Kimya", 16)])),
]

# Lise 9/10 (ara sınıf, sınav hedefi None ama hazırlık denemeleri TYT)
_LISE9_SUBJECTS = [
    ("9. Sınıf Matematik", _sections([("Kümeler", 14), ("Denklemler", 16),
                                      ("Üçgenler", 16), ("Fonksiyonlar", 12)])),
    ("9. Sınıf Fizik", _sections([("Fizik Bilimine Giriş", 10), ("Hareket", 14)])),
    ("9. Sınıf Türk Dili ve Edebiyatı", _sections([("Hikâye", 12), ("Şiir", 12)])),
]

_LISE10_SUBJECTS = [
    ("10. Sınıf Matematik", _sections([("Sayma ve Olasılık", 14), ("Fonksiyonlar", 16),
                                       ("Polinomlar", 14), ("İkinci Dereceden Denklemler", 14)])),
    ("10. Sınıf Kimya", _sections([("Kimyanın Temel Kanunları", 12), ("Karışımlar", 12)])),
    ("10. Sınıf Biyoloji", _sections([("Hücre Bölünmeleri", 14), ("Kalıtım", 14)])),
]


def _category_profiles() -> list[dict]:
    """Bağımsız koçun 5 öğrencisi — 5 sınav kategorisi.

    exam_sections: deneme sonuçlarının dağıtılacağı bölümler (>=10 deneme).
    """
    return [
        {
            "key": "lgs",
            "full_name": f"{NAME_PREFIX} Öğrenci Ayşe (LGS)",
            "email_local": "ogrenci1",
            "grade_level": 8,
            "is_graduate": False,
            "track": None,
            "subjects": _LGS_SUBJECTS,
            "exam_sections": [ExamSection.LGS],
            "exam_title": "LGS Genel Deneme",
            "deneme_book": ("LGS Genel Denemeleri", BookType.GENEL_DENEME,
                            _sections([("Deneme 1-10", 90), ("Deneme 11-20", 90)])),
            "exam_target": "LGS",
        },
        {
            "key": "lise9",
            "full_name": f"{NAME_PREFIX} Öğrenci Burak (9. Sınıf)",
            "email_local": "ogrenci2",
            "grade_level": 9,
            "is_graduate": False,
            "track": None,
            "subjects": _LISE9_SUBJECTS,
            "exam_sections": [ExamSection.TYT],
            "exam_title": "9. Sınıf Kazanım Denemesi",
            "deneme_book": ("9. Sınıf Genel Denemeleri", BookType.GENEL_DENEME,
                            _sections([("Deneme 1-8", 80)])),
            "exam_target": None,
        },
        {
            "key": "lise10",
            "full_name": f"{NAME_PREFIX} Öğrenci Ceren (10. Sınıf)",
            "email_local": "ogrenci3",
            "grade_level": 10,
            "is_graduate": False,
            "track": None,
            "subjects": _LISE10_SUBJECTS,
            "exam_sections": [ExamSection.TYT],
            "exam_title": "10. Sınıf Kazanım Denemesi",
            "deneme_book": ("10. Sınıf Genel Denemeleri", BookType.GENEL_DENEME,
                            _sections([("Deneme 1-8", 80)])),
            "exam_target": None,
        },
        {
            "key": "lise11",
            "full_name": f"{NAME_PREFIX} Öğrenci Deniz (11. Sınıf - Sayısal)",
            "email_local": "ogrenci4",
            "grade_level": 11,
            "is_graduate": False,
            "track": Track.SAYISAL,
            "subjects": _TYT_SUBJECTS + _AYT_SAY_SUBJECTS[:2],
            "exam_sections": [ExamSection.TYT, ExamSection.AYT_SAY],
            "exam_title": "TYT-AYT Deneme",
            "deneme_book": ("TYT-AYT Genel Denemeleri", BookType.GENEL_DENEME,
                            _sections([("TYT Deneme 1-10", 120), ("AYT Deneme 1-10", 80)])),
            "exam_target": None,
        },
        {
            "key": "mezun",
            "full_name": f"{NAME_PREFIX} Öğrenci Emre (Mezun - YKS)",
            "email_local": "ogrenci5",
            "grade_level": 12,
            "is_graduate": True,
            "track": Track.SAYISAL,
            "subjects": _TYT_SUBJECTS + _AYT_SAY_SUBJECTS,
            "exam_sections": [ExamSection.TYT, ExamSection.AYT_SAY],
            "exam_title": "YKS Tam Deneme",
            "deneme_book": ("YKS Tam Denemeleri", BookType.GENEL_DENEME,
                            _sections([("TYT Deneme 1-12", 120), ("AYT Deneme 1-12", 80)])),
            "exam_target": "YKS",
        },
    ]


# Sınav türü → soru sayısı (deneme net üretimi için makul tavan)
_SECTION_TOTAL_Q = {
    ExamSection.LGS: 90,
    ExamSection.TYT: 120,
    ExamSection.AYT_SAY: 80,
    ExamSection.AYT_EA: 80,
    ExamSection.AYT_SOZ: 80,
    ExamSection.AYT_DIL: 80,
}


def _email(local: str) -> str:
    return f"appstore.demo.{local}@{EMAIL_DOMAIN}"


# =============================================================================
# Müfredat + kitap kurulumu (sınav türüne özel adlar)
# =============================================================================

def _seed_books_for_owner(
    db: Session, *, owner: User, subj_specs: list[tuple[str, list]],
    deneme_spec: tuple[str, BookType, list] | None,
) -> list[Book]:
    """owner (koç/öğretmen) için ders + kitap + bölüm kur. Returns books.

    Subject UniqueConstraint (teacher_id, name, curriculum_model): owner başına
    her ders adı benzersiz olmalı → öğrenci adı eki ile çakışma önlenir
    (aynı koçun farklı öğrencileri farklı kitap setine sahip).
    """
    books: list[Book] = []
    for subj_name, sections in subj_specs:
        subj = Subject(
            name=subj_name,
            order=900,
            is_builtin=False,
            teacher_id=owner.id,
        )
        db.add(subj)
        db.flush()

        topic = Topic(name="Genel", order=0, subject_id=subj.id)
        db.add(topic)
        db.flush()

        book = Book(
            name=f"{subj_name} Soru Bankası",
            subject_id=subj.id,
            type=BookType.SORU_BANKASI,
            teacher_id=owner.id,
        )
        db.add(book)
        db.flush()
        for idx, (label, tc) in enumerate(sections):
            db.add(BookSection(
                book_id=book.id, label=label, test_count=tc, order=idx,
                topic_id=topic.id,
            ))
        db.flush()
        books.append(book)

    # Deneme kitabı (opsiyonel)
    if deneme_spec is not None:
        dname, dtype, dsections = deneme_spec
        # Deneme kitabını ilk dersin subject'ine bağla (gerçek dünyada deneme
        # kitapları derse bağlı değil ama Book.subject_id NOT NULL → ilk ders).
        first_subj_name = subj_specs[0][0]
        subj = (
            db.query(Subject)
            .filter(Subject.teacher_id == owner.id, Subject.name == first_subj_name)
            .first()
        )
        topic = (
            db.query(Topic).filter(Topic.subject_id == subj.id).first()
            if subj else None
        )
        book = Book(
            name=dname,
            subject_id=subj.id,
            type=dtype,
            teacher_id=owner.id,
        )
        db.add(book)
        db.flush()
        for idx, (label, tc) in enumerate(dsections):
            db.add(BookSection(
                book_id=book.id, label=label, test_count=tc, order=idx,
                topic_id=topic.id if topic else None,
            ))
        db.flush()
        books.append(book)

    return books


def _assign_books(db: Session, *, student: User, books: list[Book]) -> None:
    """Öğrenciye kitapları ata + her bölüm için SectionProgress (0/0)."""
    for book in books:
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb)
        db.flush()
        for sec in book.sections:
            db.add(SectionProgress(
                student_book_id=sb.id, book_section_id=sec.id,
                completed_count=0, reserved_count=0,
            ))
        db.flush()


def _sp_for(db: Session, student_id: int, section_id: int) -> SectionProgress | None:
    return (
        db.query(SectionProgress)
        .join(StudentBook, SectionProgress.student_book_id == StudentBook.id)
        .filter(
            StudentBook.student_id == student_id,
            SectionProgress.book_section_id == section_id,
        )
        .first()
    )


# =============================================================================
# Haftalık program + görevler (3 hafta; rezerv mantığı _seed_student_data gibi)
# =============================================================================

def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _seed_programs(
    db: Session, *, coach: User, student: User, books: list[Book],
    weeks: int = 3,
) -> int:
    """`weeks` ayrı haftaya (geçen/bu/gelecek) WeeklyProgram + görevler kur.

    Her hafta birkaç görev: COMPLETED / PARTIAL / PENDING karışık. PARTIAL/PENDING
    görevlerin yapılmamış kısmı SectionProgress.reserved_count'a yazılır
    (_seed_student_data rezerv mantığıyla birebir). Returns oluşturulan görev sayısı.
    """
    from app.models.weekly_program import WeeklyProgram

    today = date.today()
    this_monday = _monday(today)
    now = datetime.now(timezone.utc)

    # Yalnız soru bankası bölümlerini kullan (deneme kitabını programa katma —
    # gerçek akışta deneme ayrı atanır; burada test görevleri rezerv göstersin).
    sb_books = [b for b in books if b.type == BookType.SORU_BANKASI]
    # (book, section) düz listesi
    flat: list[tuple[Book, BookSection]] = []
    for b in sb_books:
        for sec in b.sections:
            flat.append((b, sec))
    if not flat:
        return 0

    # Hafta ofsetleri: -1 (geçen), 0 (bu hafta), +1 (gelecek)
    week_offsets = [(-1, "Geçen Hafta"), (0, "Bu Hafta"), (1, "Gelecek Hafta")][:weeks]

    # Görev şablonu: her hafta 4 görev — (gün, status, pct, planned)
    # Geçen hafta: tamamlanmış ağırlıklı; bu hafta: karışık; gelecek: pending
    week_task_specs = {
        -1: [
            (0, TaskStatus.COMPLETED, 1.0, 15),
            (1, TaskStatus.COMPLETED, 1.0, 12),
            (2, TaskStatus.PARTIAL, 0.5, 10),
            (3, TaskStatus.PENDING, 0.0, 10),
        ],
        0: [
            (0, TaskStatus.COMPLETED, 1.0, 14),
            (1, TaskStatus.PARTIAL, 0.4, 15),
            (2, TaskStatus.PENDING, 0.0, 12),
            (3, TaskStatus.PENDING, 0.0, 8),
        ],
        1: [
            (0, TaskStatus.PENDING, 0.0, 12),
            (1, TaskStatus.PENDING, 0.0, 10),
            (2, TaskStatus.PENDING, 0.0, 10),
        ],
    }

    task_count = 0
    flat_idx = 0
    for woff, wname in week_offsets:
        wk_monday = this_monday + timedelta(weeks=woff)
        prog = WeeklyProgram(
            student_id=student.id,
            coach_id=coach.id,
            start_date=wk_monday,
            end_date=wk_monday + timedelta(days=6),
            name=wname,
        )
        db.add(prog)
        db.flush()

        for day_ofs, status, pct, planned in week_task_specs[woff]:
            book, sec = flat[flat_idx % len(flat)]
            flat_idx += 1
            task_date = wk_monday + timedelta(days=day_ofs)
            completed = int(planned * pct)

            task = Task(
                student_id=student.id,
                date=task_date,
                type=TaskType.TEST,
                title=f"{sec.label} {planned} test",
                status=status,
                order=0,
                is_draft=False,
                published_at=now,
                completed_at=(now if status == TaskStatus.COMPLETED else None),
            )
            db.add(task)
            db.flush()

            db.add(TaskBookItem(
                task_id=task.id,
                book_id=book.id,
                book_section_id=sec.id,
                planned_count=planned,
                completed_count=completed,
                correct_count=(int(completed * 0.8) if completed > 0 else None),
                wrong_count=(int(completed * 0.15) if completed > 0 else None),
            ))

            sp = _sp_for(db, student.id, sec.id)
            if sp is not None:
                if status == TaskStatus.COMPLETED:
                    sp.completed_count = (sp.completed_count or 0) + planned
                elif status == TaskStatus.PARTIAL:
                    sp.completed_count = (sp.completed_count or 0) + completed
                sp.reserved_count = (sp.reserved_count or 0) + (planned - completed)
            db.flush()
            task_count += 1

    return task_count


# =============================================================================
# Deneme sonuçları (>=10, sınav türüne uygun, ~3 aya yayılı, değişken net)
# =============================================================================

def _seed_exams(
    db: Session, *, coach: User, student: User, profile: dict, count: int = 11,
) -> int:
    today = date.today()
    sections = profile["exam_sections"]
    base_title = profile["exam_title"]
    created = 0
    for i in range(count):
        section = sections[i % len(sections)]
        total_q = _SECTION_TOTAL_Q.get(section, 100)
        # İlerleme eğilimi: zamanla net artar (eski denemeler düşük, yeni yüksek)
        progress = i / max(count - 1, 1)  # 0..1
        base_correct = int(total_q * (0.45 + 0.30 * progress))
        # gürültü
        correct = max(0, min(total_q, base_correct + _RNG.randint(-6, 6)))
        wrong = max(0, min(total_q - correct, int((total_q - correct) * 0.55) + _RNG.randint(-3, 3)))
        blank = max(0, total_q - correct - wrong)
        exam_date = today - timedelta(days=(count - i) * 8)  # ~3 ay geriye yayılı
        net = compute_net(correct, wrong, section)
        db.add(ExamResult(
            student_id=student.id,
            created_by_id=coach.id,
            title=f"{base_title} {i + 1}",
            exam_date=exam_date,
            section=section,
            total_correct=correct,
            total_wrong=wrong,
            total_blank=blank,
            net=net,
        ))
        created += 1
    return created


# =============================================================================
# Anketler — 2-3 atama, karışık durum (completed / in_progress / pending)
# =============================================================================

_SURVEY_CODES = ["coklu-zeka", "ogrenme-stilleri", "calisma-aliskanliklari"]


def _plausible_answers(questions: list[SurveyQuestion]) -> dict[str, object]:
    """Tüm zorunlu sorulara makul cevap üret (likert 3-5, slider 5-9, open metin)."""
    answers: dict[str, object] = {}
    for q in questions:
        if q.qtype == "likert5":
            answers[str(q.id)] = _RNG.randint(3, 5)
        elif q.qtype == "slider10":
            answers[str(q.id)] = _RNG.randint(5, 9)
        elif q.qtype == "choice":
            opts = survey_service.parse_options(q)
            if opts:
                answers[str(q.id)] = opts[0].get("value", "")
        elif q.qtype == "open":
            answers[str(q.id)] = "Demo cevap — inceleme için örnek metin."
    return answers


def _seed_surveys(db: Session, *, coach: User, student: User) -> int:
    """Öğrenciye 3 anket ata: 1 completed (skorlu), 1 in_progress, 1 pending."""
    templates = (
        db.query(SurveyTemplate)
        .filter(SurveyTemplate.code.in_(_SURVEY_CODES))
        .all()
    )
    by_code = {t.code: t for t in templates}
    now = datetime.now(timezone.utc)
    created = 0

    plan = [
        ("coklu-zeka", ASSIGNMENT_COMPLETED),
        ("ogrenme-stilleri", ASSIGNMENT_IN_PROGRESS),
        ("calisma-aliskanliklari", ASSIGNMENT_PENDING),
    ]
    for code, target_status in plan:
        tmpl = by_code.get(code)
        if tmpl is None:
            continue
        questions = (
            db.query(SurveyQuestion)
            .filter(SurveyQuestion.template_id == tmpl.id)
            .order_by(SurveyQuestion.order_no)
            .all()
        )
        assignment = SurveyAssignment(
            template_id=tmpl.id,
            teacher_id=coach.id,
            student_id=student.id,
            status=ASSIGNMENT_PENDING,
            note="İlk görüşmemiz öncesi doldurur musun?",
            assigned_at=now,
        )
        db.add(assignment)
        db.flush()

        if target_status == ASSIGNMENT_COMPLETED:
            answers = _plausible_answers(questions)
            survey_service.save_answers(
                db, assignment, tmpl, questions, answers, complete=True,
            )
        elif target_status == ASSIGNMENT_IN_PROGRESS:
            # Yarım doldur (ilk yarısı) → in_progress
            half = {str(q.id): (_RNG.randint(3, 5) if q.qtype == "likert5"
                                else _RNG.randint(5, 9) if q.qtype == "slider10"
                                else "Demo cevap")
                    for q in questions[: max(1, len(questions) // 2)]}
            survey_service.save_answers(
                db, assignment, tmpl, questions, half, complete=False,
            )
        # PENDING → dokunma (default)
        db.flush()
        created += 1
    return created


# =============================================================================
# TaskRequest — birkaç öğrenci→koç talebi (pending + approved/resolved)
# =============================================================================

def _seed_task_requests(db: Session, *, coach: User, student: User) -> int:
    """Birkaç program talebi: 1 PENDING soru, 1 RESOLVED, 1 APPROVED change."""
    now = datetime.now(timezone.utc)
    # Öğrencinin yayında bir görevini referansla (varsa)
    sample_task = (
        db.query(Task)
        .filter(Task.student_id == student.id, Task.is_draft.is_(False))
        .order_by(Task.date.desc())
        .first()
    )
    specs = [
        dict(type=RequestType.QUESTION, status=RequestStatus.PENDING,
             message="Bu hafta matematik biraz ağır geldi, video önerebilir misiniz?",
             teacher_response=None, task_id=None),
        dict(type=RequestType.QUESTION, status=RequestStatus.RESOLVED,
             message="Deneme sonucumu nasıl yorumlamalıyım?",
             teacher_response="Netlerin yükseliyor, paragrafa biraz daha ağırlık ver.",
             task_id=None),
        dict(type=RequestType.CHANGE, status=RequestStatus.APPROVED,
             message="Bu görevdeki test sayısını azaltabilir miyiz?",
             teacher_response="Tamam, 10'a düşürdüm.",
             task_id=(sample_task.id if sample_task else None)),
    ]
    created = 0
    for s in specs:
        req = TaskRequest(
            student_id=student.id,
            teacher_id=coach.id,
            type=s["type"],
            status=s["status"],
            message=s["message"],
            teacher_response=s["teacher_response"],
            task_id=s["task_id"],
            responded_at=(now if s["status"] != RequestStatus.PENDING else None),
        )
        db.add(req)
        created += 1
    db.flush()
    return created


# =============================================================================
# Koç tahsilatı (ücret + ödemeler)
# =============================================================================

def _seed_billing(db: Session, *, coach: User, student: User) -> int:
    """Öğrenci başına ücret + 3 ödenmiş ay (nakit/havale)."""
    db.add(CoachStudentRate(coach_id=coach.id, student_id=student.id, session_fee=2500))
    today = date.today()
    created = 0
    for m in range(3, 0, -1):
        # Geçmiş m. ay
        ref = (today.replace(day=1) - timedelta(days=1))
        for _ in range(m - 1):
            ref = (ref.replace(day=1) - timedelta(days=1))
        period = ref.strftime("%Y-%m")
        method = CoachPaymentMethod.CASH if m % 2 else CoachPaymentMethod.TRANSFER
        db.add(CoachPayment(
            coach_id=coach.id,
            student_id=student.id,
            amount=2500 * 4,  # ~4 seans/ay
            paid_at=ref,
            method=method,
            period_month=period,
            note="Demo ödeme kaydı",
        ))
        created += 1
    db.flush()
    return created


# =============================================================================
# Ana kurulum
# =============================================================================

def _mk_user(**kwargs) -> User:
    """_new_user sarıcısı — sabit seed_id + label + email_verified."""
    u = _new_user(seed_id=SEED_ID, label=LABEL, **kwargs)
    return u


def build(db: Session) -> dict:
    counts = {
        "institutions": 0, "users": 0, "students": 0, "parents": 0,
        "teachers": 0, "books": 0, "programs": 0, "tasks": 0, "exams": 0,
        "surveys": 0, "requests": 0, "payments": 0,
    }

    # -------------------------------------------------------------------------
    # 1) Kurum + kurum yöneticisi
    # -------------------------------------------------------------------------
    inst = Institution(
        name=f"{NAME_PREFIX} Akademi",
        slug="appstore-demo-akademi",
        plan="etut_standart",
        is_active=True,
        contact_email=_email("kurum"),
        is_demo=True,
        demo_seed_id=SEED_ID,
        demo_label=LABEL,
    )
    db.add(inst)
    db.flush()
    counts["institutions"] += 1

    admin = _mk_user(
        email=_email("kurum"),
        full_name=f"{NAME_PREFIX} Kurum Yöneticisi",
        role=UserRole.INSTITUTION_ADMIN,
        institution_id=inst.id,
    )
    db.add(admin)
    db.flush()
    counts["users"] += 1

    # -------------------------------------------------------------------------
    # 2) Bağımsız koç (ASIL ZENGİN DEMO) + 5 öğrenci (5 sınav kategorisi) + 5 veli
    # -------------------------------------------------------------------------
    coach = _mk_user(
        email=_email("koc"),
        full_name=f"{NAME_PREFIX} Bağımsız Koç",
        role=UserRole.TEACHER,
        institution_id=None,
        plan="solo_pro",  # ücretli → AI özellikleri açık
    )
    db.add(coach)
    db.flush()
    counts["users"] += 1
    counts["teachers"] += 1

    profiles = _category_profiles()
    coach_students: list[User] = []
    for idx, prof in enumerate(profiles, start=1):
        student = _mk_user(
            email=_email(prof["email_local"]),
            full_name=prof["full_name"],
            role=UserRole.STUDENT,
            teacher_id=coach.id,
            grade_level=prof["grade_level"],
        )
        # Mezun / track alanları _new_user'da yok → doğrudan set
        student.is_graduate = prof["is_graduate"]
        student.track = prof["track"]
        db.add(student)
        db.flush()
        counts["users"] += 1
        counts["students"] += 1
        coach_students.append(student)

        # effective_exam_target doğrulama (sanity)
        expected = prof["exam_target"]
        if student.effective_exam_target != expected:
            raise RuntimeError(
                f"effective_exam_target uyuşmazlığı: {prof['key']} "
                f"beklenen={expected} gerçek={student.effective_exam_target}"
            )

        # Kitaplar + atama
        books = _seed_books_for_owner(
            db, owner=coach,
            subj_specs=prof["subjects"],
            deneme_spec=prof["deneme_book"],
        )
        counts["books"] += len(books)
        _assign_books(db, student=student, books=books)

        # 3 haftalık program + görevler (rezerv görünür)
        tcount = _seed_programs(db, coach=coach, student=student, books=books, weeks=3)
        counts["tasks"] += tcount
        counts["programs"] += 3

        # >=10 deneme
        counts["exams"] += _seed_exams(db, coach=coach, student=student, profile=prof, count=11)

        # Anketler (3 atama, karışık durum)
        counts["surveys"] += _seed_surveys(db, coach=coach, student=student)

        # TaskRequests (görev referansı için programdan SONRA)
        counts["requests"] += _seed_task_requests(db, coach=coach, student=student)

        # Koç tahsilatı
        counts["payments"] += _seed_billing(db, coach=coach, student=student)

    # 5 veli → koçun 5 öğrencisine bağla
    rel_cycle = [ParentRelation.ANNE, ParentRelation.BABA, ParentRelation.ANNE,
                 ParentRelation.BABA, ParentRelation.VASI]
    for i, student in enumerate(coach_students, start=1):
        parent = _mk_user(
            email=_email(f"veli{i}"),
            full_name=f"{NAME_PREFIX} Veli {i}",
            role=UserRole.PARENT,
        )
        db.add(parent)
        db.flush()
        counts["users"] += 1
        counts["parents"] += 1
        db.add(ParentStudentLink(
            parent_id=parent.id, student_id=student.id,
            relation=rel_cycle[(i - 1) % len(rel_cycle)],
            is_primary=True, created_by_id=coach.id,
        ))
    db.flush()

    # -------------------------------------------------------------------------
    # 3) 5 kuruma bağlı öğretmen + her birine 1 öğrenci (daha hafif veri)
    # -------------------------------------------------------------------------
    # Kurum öğretmenlerinin öğrencileri için sınav profili döngüsü (çeşitlilik)
    inst_profiles = profiles  # aynı 5 kategori
    for t in range(1, 6):
        teacher = _mk_user(
            email=_email(f"ogretmen{t}"),
            full_name=f"{NAME_PREFIX} Öğretmen {t}",
            role=UserRole.TEACHER,
            institution_id=inst.id,
        )
        db.add(teacher)
        db.flush()
        counts["users"] += 1
        counts["teachers"] += 1

        prof = inst_profiles[(t - 1) % len(inst_profiles)]
        student = _mk_user(
            email=_email(f"kurum_ogrenci{t}"),
            full_name=f"{NAME_PREFIX} Kurum Öğrencisi {t} ({prof['key'].upper()})",
            role=UserRole.STUDENT,
            institution_id=inst.id,
            teacher_id=teacher.id,
            grade_level=prof["grade_level"],
        )
        student.is_graduate = prof["is_graduate"]
        student.track = prof["track"]
        db.add(student)
        db.flush()
        counts["users"] += 1
        counts["students"] += 1

        # Hafif veri: kitaplar (deneme yok) + 1 hafta program + birkaç deneme
        books = _seed_books_for_owner(
            db, owner=teacher,
            subj_specs=prof["subjects"][:2],  # 2 ders yeterli
            deneme_spec=None,
        )
        counts["books"] += len(books)
        _assign_books(db, student=student, books=books)
        tcount = _seed_programs(db, coach=teacher, student=student, books=books, weeks=1)
        counts["tasks"] += tcount
        counts["programs"] += 1
        counts["exams"] += _seed_exams(db, coach=teacher, student=student, profile=prof, count=4)

    return counts


def _purge_uncovered(db: Session) -> dict:
    """`delete_demo_session` kapanışının KAPSAMADIĞI tabloları temizle.

    delete_demo_session şunları siler: User, Institution, Task(+items), ExamResult,
    StudentBook(+progress), Book(+sections), Subject(+topics), Coach billing,
    ParentStudentLink, davetler, seans/içgörü. AMA şu üçünü silmez:
      - WeeklyProgram   (student_id)
      - TaskRequest     (student_id / teacher_id)
      - SurveyAssignment(student_id / teacher_id)
    Dev SQLite'ta FK CASCADE kapalı + silinen User id'leri yeniden kullanılır →
    bu üç tablo eski demo satırlarını yeni demo öğrencisine MİRAS bırakırdı
    (id-reuse kontaminasyonu). Bu yüzden demo closure id'lerine göre explicit sil.
    Prod (Postgres) User silininde CASCADE bunları zaten temizler; bu fonksiyon
    her iki ortamda da güvenli (yoksa no-op).
    """
    from sqlalchemy import delete as sa_delete, or_ as sa_or

    from app.models.weekly_program import WeeklyProgram
    from app.services.demo_seed import _demo_closure

    user_ids, _inst_ids = _demo_closure(db, seed_id=SEED_ID)
    counts = {"weekly_programs": 0, "task_requests": 0, "survey_assignments": 0}
    if not user_ids:
        return counts

    counts["weekly_programs"] = (
        db.query(WeeklyProgram)
        .filter(sa_or(
            WeeklyProgram.student_id.in_(user_ids),
            WeeklyProgram.coach_id.in_(user_ids),
        )).count()
    )
    db.execute(sa_delete(WeeklyProgram).where(sa_or(
        WeeklyProgram.student_id.in_(user_ids),
        WeeklyProgram.coach_id.in_(user_ids),
    )))

    counts["task_requests"] = (
        db.query(TaskRequest)
        .filter(sa_or(
            TaskRequest.student_id.in_(user_ids),
            TaskRequest.teacher_id.in_(user_ids),
        )).count()
    )
    db.execute(sa_delete(TaskRequest).where(sa_or(
        TaskRequest.student_id.in_(user_ids),
        TaskRequest.teacher_id.in_(user_ids),
    )))

    counts["survey_assignments"] = (
        db.query(SurveyAssignment)
        .filter(sa_or(
            SurveyAssignment.student_id.in_(user_ids),
            SurveyAssignment.teacher_id.in_(user_ids),
        )).count()
    )
    db.execute(sa_delete(SurveyAssignment).where(sa_or(
        SurveyAssignment.student_id.in_(user_ids),
        SurveyAssignment.teacher_id.in_(user_ids),
    )))

    db.flush()
    return counts


def run(reset: bool = False) -> dict:
    """Idempotent: önce mevcut seed'i transitif sil, sonra kur. Tek transaction."""
    with SessionLocal() as db:
        # 1) Önce closure-DIŞI tabloları (WeeklyProgram/TaskRequest/SurveyAssignment)
        #    demo id'lerine göre temizle (id-reuse kontaminasyonunu önler)
        purge_counts = _purge_uncovered(db)
        # 2) Sonra transitif kapanışla geri kalan her şeyi sil (User dahil)
        del_counts = delete_demo_session(db, seed_id=SEED_ID)
        del_counts.update(purge_counts)
        db.commit()

        # 3) Yeniden kur (tek transaction)
        try:
            counts = build(db)
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {"deleted": del_counts, "created": counts}


def _print_summary(result: dict) -> None:
    c = result["created"]
    d = result["deleted"]
    line = "=" * 70
    print(line)
    print("APP STORE / PLAY STORE İNCELEME DEMOSU — KURULDU")
    print(line)
    print(f"Önceki demo temizlendi: {d}")
    print()
    print("SAYIMLAR:")
    print(f"  Kurum            : {c['institutions']}")
    print(f"  Toplam kullanıcı : {c['users']}  (öğretmen {c['teachers']}, "
          f"öğrenci {c['students']}, veli {c['parents']}, +1 kurum yöneticisi)")
    print(f"  Kitap            : {c['books']}")
    print(f"  Haftalık program : {c['programs']}")
    print(f"  Görev            : {c['tasks']}")
    print(f"  Deneme sonucu    : {c['exams']}")
    print(f"  Anket ataması    : {c['surveys']}")
    print(f"  Program talebi   : {c['requests']}")
    print(f"  Tahsilat ödemesi : {c['payments']}")
    print()
    print(line)
    print("GİRİŞ BİLGİLERİ — App Store Connect 'App Review Information' için")
    print(line)
    print(f"Şifre (HEPSİ AYNI): {DEMO_PASSWORD}")
    print(f"Site: https://rotam.etutkoc.com")
    print()
    print("ASIL DEMO — Bağımsız Koç (en zengin veri; inceleme için önerilen):")
    print(f"  Koç      : {_email('koc')}   → panel: /teacher")
    print()
    print("Kurum (kurum paneli):")
    print(f"  Yönetici : {_email('kurum')}   → panel: /institution")
    print()
    print("Örnek öğrenci girişleri (koça bağlı, 5 sınav kategorisi):")
    print(f"  LGS (8)    : {_email('ogrenci1')}   → panel: /student")
    print(f"  Lise 9     : {_email('ogrenci2')}")
    print(f"  Lise 10    : {_email('ogrenci3')}")
    print(f"  Lise 11    : {_email('ogrenci4')}")
    print(f"  Mezun (YKS): {_email('ogrenci5')}")
    print()
    print("Örnek veli girişleri:")
    print(f"  Veli 1     : {_email('veli1')}   → panel: /parent")
    print(f"  Veli 2     : {_email('veli2')}")
    print()
    print("Kuruma bağlı öğretmen örneği:")
    print(f"  Öğretmen 1 : {_email('ogretmen1')}   → panel: /teacher")
    print(line)


if __name__ == "__main__":
    # --reset bayrağı bilgi amaçlı: varsayılan çalıştırma zaten idempotent
    # (önce sil, sonra kur). İki durumda da aynı sonuç.
    _reset = "--reset" in sys.argv
    result = run(reset=_reset)
    _print_summary(result)
