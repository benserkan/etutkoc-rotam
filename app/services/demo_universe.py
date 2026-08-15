# -*- coding: utf-8 -*-
"""Dolu demo evreni üretici — "N ay kullanılmış kurum" hissi veren demo hesaplar.

Marhan Akademi demosunun (scripts/seed_marhan_demo.py, 2026-08-15) parametreli
algoritma hâli. Süper admin panelden ad + koç sayısı + koç başına öğrenci girer;
sistem birbirine bağlı tam bir evren kurar:

  - Kurum (etut_standart) + yönetici + koçlar (LGS/TYT/YKS gruplarına dağıtılır)
  - Koç başına N öğrenci (arketip döngüsü: yıldız/iyi/orta/düşen/riskli) + veliler
  - Kitaplar (LGS elle, TYT/YKS verified katalog şablonlarından — topic eşli)
  - 10 haftalık rezerv-tutarlı görev geçmişi (arketipe göre tamamlama + D/Y)
  - GERÇEK karne havuzu kopyası (sistemdeki soru-satırlı denemelerden sınıf-uyumlu)
  - Yanlış Soru Arşivi + tamamlanmış anket skorları + görev/destek talepleri
  - Öğrenci başına 5 seans raporu + AI koçluk içgörüsü cache'i
  - Rota veli yorumları (program+deneme; --with-audio ile gerçek TTS sesi)

Tüm kullanıcılar `is_demo=True + demo_seed_id` taşır → mevcut
/admin/demo-sessions listesi ve toplu silme akışı aynen çalışır.

Hesap adları PLAN aşamasında deterministik üretilir (seed_id'den) → endpoint,
kurulum arka planda sürerken hesap listesini ANINDA döndürebilir.
"""
from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import (
    Book,
    BookSection,
    BookTemplate,
    BookType,
    Institution,
    ParentStudentLink,
    SectionProgress,
    StudentBook,
    Subject,
    SupportRequest,
    Task,
    TaskBookItem,
    TaskRequest,
    TaskStatus,
    TaskType,
    User,
    UserRole,
    WrongQuestion,
)
from app.models.coaching_session import (
    CoachingChannel,
    CoachingInsight,
    CoachingSession,
    CoachingSessionStatus,
    SessionCaptureSource,
)
from app.models.exam_result import ExamResult, ExamResultQuestion
from app.models.parent_commentary import ParentCommentary
from app.models.support_request import SupportRequestMessage
from app.models.survey import (
    ASSIGNMENT_PENDING,
    QTYPE_CHOICE,
    QTYPE_LIKERT5,
    QTYPE_OPEN,
    QTYPE_SLIDER10,
    SurveyAssignment,
    SurveyQuestion,
    SurveyTemplate,
)
from app.models.task_request import RequestStatus, RequestType
from app.models.user import Track
from app.models.wrong_question import (
    WQ_SOURCE_DENEME,
    WQ_SOURCE_GOREV,
    WQ_STATUS_ACIK,
    WQ_STATUS_KAPANDI,
)
from app.services import survey_service
from app.services.security import hash_password

UNIVERSE_PASSWORD = "RotamDemo2026!"
MAX_COACHES = 6
MAX_STUDENTS_PER_COACH = 8

GROUPS = ["LGS", "TYT", "YKS"]
GRADE = {"LGS": 8, "TYT": 11, "YKS": 12}
# (tamamlama oranı, doğruluk) — kurum panolarında ayrışan 5 arketip
ARCHETYPES = [(0.92, 0.85), (0.78, 0.75), (0.60, 0.66), (0.38, 0.55), (0.15, 0.45)]
MOODS = [5, 4, 3, 3, 2]

# --- Ad havuzları (deterministik seçim; tükenirse numaralanır) ---------------
_COACH_NAMES = [
    "Ayşe Yıldız", "Mehmet Kaya", "Selin Arslan", "Burak Demir", "Elif Şahin",
    "Emre Koç", "Zehra Aslan", "Oğuz Yılmaz", "Merve Çetin", "Kaan Öz",
]
_STUDENT_FIRST = [
    "Defne", "Emir", "Zeynep", "Çınar", "Elif", "Yağmur", "Kerem", "Nehir",
    "Batuhan", "İrem", "Ege", "Selin", "Arda", "Melis", "Umut", "Duru",
    "Mert", "Ecrin", "Alperen", "Lina", "Rüzgar", "Asel", "Doruk", "Miray",
    "Aras", "Beren", "Çağan", "Derin", "Efe", "Nisan",
]
_SURNAMES = [
    "Aksoy", "Koçak", "Polat", "Erdem", "Güneş", "Şen", "Aydın", "Duman",
    "Çelik", "Kaplan", "Yalçın", "Öztürk", "Doğan", "Karaca", "Bozkurt",
    "Tekin", "Avcı", "Kurt", "Özdemir", "Acar", "Turan", "Bulut", "Sarı",
    "Keskin", "Güler", "Işık", "Taş", "Yavuz", "Ateş", "Kılıç",
]
_MOTHER_FIRST = ["Hülya", "Sevgi", "Aynur", "Nurcan", "Fatma", "Şule", "Gül",
                 "Derya", "Emine", "Hatice", "Sibel", "Nazan", "Filiz", "Serap"]
_FATHER_FIRST = ["Murat", "Hakan", "Bülent", "Orhan", "Serdar", "Volkan",
                 "Kadir", "Ahmet", "Mustafa", "Erkan", "Tolga", "Cem", "Levent"]

# Katalog şablon adayları (ada göre; ilk bulunan kullanılır)
CATALOG_BOOKS = {
    "TYT": [
        ["345 TYT Matematik Soru Bankası", "Bilgi Sarmal TYT Matematik Soru Bankası"],
        ["Twins TYT Biyoloji Soru Bankası", "Biyotik TYT Biyoloji Soru Bankası"],
        ["345 TYT Fizik Soru Bankası", "3D TYT Fizik Soru Bankası"],
    ],
    "YKS": [
        ["Aydın AYT Biyoloji Soru Bankası", "Biyotik AYT Biyoloji Soru Bankası"],
        ["345 AYT Kimya Soru Bankası"],
        ["345 TYT Kimya Soru Bankası"],
    ],
}

SURVEY_BASE = ["coklu-zeka", "ogrenme-stilleri", "sinav-kaygisi"]


def _slugify(name: str) -> str:
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    out = []
    for ch in name.translate(tr).lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return ("".join(out).strip("-") or "demo")[:24].strip("-")


def _email_key(name: str) -> str:
    # Türkçe İ tuzağı: "İ".lower() = "i̇" (combining dot) → önce çevir
    key = (name.replace("İ", "i").replace("I", "i").lower().replace(" ", ".")
           .replace("ç", "c").replace("ğ", "g").replace("ı", "i")
           .replace("ö", "o").replace("ş", "s").replace("ü", "u")
           .replace("i̇", "i"))
    return "".join(ch for ch in key if ch.isalnum() or ch == ".")


# =============================================================================
# PLAN — DB'siz, deterministik (seed_id → adlar/e-postalar)
# =============================================================================

@dataclass
class PlannedStudent:
    name: str
    email: str
    parent_name: str
    parent_email: str
    parent_relation: str  # anne | baba
    archetype_idx: int


@dataclass
class PlannedCoach:
    name: str
    email: str
    group: str  # LGS | TYT | YKS
    students: list[PlannedStudent] = field(default_factory=list)


@dataclass
class UniversePlan:
    seed_id: str
    label: str
    slug: str
    admin_name: str
    admin_email: str
    password: str
    coaches: list[PlannedCoach] = field(default_factory=list)


def plan_universe(
    *,
    label: str,
    coach_count: int,
    students_per_coach: int,
    seed_id: str | None = None,
    admin_name: str | None = None,
) -> UniversePlan:
    coach_count = max(1, min(MAX_COACHES, int(coach_count)))
    students_per_coach = max(1, min(MAX_STUDENTS_PER_COACH, int(students_per_coach)))
    seed_id = seed_id or uuid.uuid4().hex
    slug = _slugify(label)
    rng = random.Random(int(hashlib.sha256(seed_id.encode()).hexdigest()[:12], 16))

    coach_names = _COACH_NAMES[:]
    rng.shuffle(coach_names)
    firsts = _STUDENT_FIRST[:]
    rng.shuffle(firsts)
    surnames = _SURNAMES[:]
    rng.shuffle(surnames)

    plan = UniversePlan(
        seed_id=seed_id, label=label.strip() or "Demo Akademi", slug=slug,
        admin_name=admin_name or "Demo Yönetici",
        admin_email=f"{slug}-yonetici@etutkoc.demo",
        password=UNIVERSE_PASSWORD,
    )
    si = 0
    for ci in range(coach_count):
        cname = (coach_names[ci] if ci < len(coach_names)
                 else f"Koç {ci + 1} Demir")
        coach = PlannedCoach(
            name=cname,
            email=f"{slug}-koc{ci + 1}@etutkoc.demo",
            group=GROUPS[ci % len(GROUPS)],
        )
        for k in range(students_per_coach):
            fn = firsts[si % len(firsts)]
            sn = surnames[si % len(surnames)]
            suffix = "" if si < len(surnames) else str(si // len(surnames) + 1)
            sname = f"{fn} {sn}{suffix}"
            rel = "anne" if (si % 2 == 0) else "baba"
            pf = (rng.choice(_MOTHER_FIRST) if rel == "anne"
                  else rng.choice(_FATHER_FIRST))
            pname = f"{pf} {sn}{suffix}"
            coach.students.append(PlannedStudent(
                name=sname,
                email=f"{slug}-{_email_key(sname)}@etutkoc.demo",
                parent_name=pname,
                parent_email=f"{slug}-veli.{_email_key(pname)}@etutkoc.demo",
                parent_relation=rel,
                archetype_idx=k % len(ARCHETYPES),
            ))
            si += 1
        plan.coaches.append(coach)
    return plan


# =============================================================================
# BUILD — planı DB'ye kurar (tek commit; hata → rollback, hiçbir şey kalmaz)
# =============================================================================

def build_universe(db: Session, plan: UniversePlan, *,
                   with_audio: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    rng = random.Random(int(hashlib.sha256(plan.seed_id.encode()).hexdigest()[12:24], 16))

    if db.query(User).filter(User.email == plan.admin_email).first():
        raise ValueError("universe_exists")

    def mk_user(*, email, name, role, **kw) -> User:
        # "aylardır kullanılıyor" hissi + onboarding-grace'in risk sinyallerini
        # bastırmaması için hesaplar ~6 ay önce açılmış görünür
        kw.setdefault("created_at", now - timedelta(days=175))
        u = User(email=email, password_hash=hash_password(plan.password),
                 full_name=name, role=role, is_active=True,
                 email_verified_at=now, is_demo=True,
                 demo_seed_id=plan.seed_id, **kw)
        db.add(u)
        db.flush()
        return u

    # ---------- Kurum + yönetici + koçlar ----------
    slug = plan.slug
    if db.query(Institution).filter(Institution.slug == slug).first():
        slug = f"{slug}-{plan.seed_id[:6]}"
    inst = Institution(name=plan.label, slug=slug,
                       contact_email=plan.admin_email, plan="etut_standart",
                       is_active=True, is_demo=True,
                       demo_seed_id=plan.seed_id, demo_label=plan.label)
    db.add(inst)
    db.flush()
    mk_user(email=plan.admin_email, name=plan.admin_name,
            role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id,
            demo_label=plan.label,
            last_login_at=now - timedelta(hours=20))
    coaches: list[tuple[PlannedCoach, User]] = []
    for i, pc in enumerate(plan.coaches):
        coaches.append((pc, mk_user(
            email=pc.email, name=pc.name, role=UserRole.TEACHER,
            institution_id=inst.id,
            last_login_at=now - timedelta(hours=6 + i * 14))))

    # ---------- Öğrenciler + veliler ----------
    # (coach_user, PlannedStudent, student_user) üçlüleri
    roster: list[tuple[PlannedCoach, User, PlannedStudent, User, User]] = []
    for pc, cu in coaches:
        for k, ps in enumerate(pc.students):
            rate, _acc = ARCHETYPES[ps.archetype_idx]
            login_days = 1 if rate > 0.5 else (3 if rate > 0.3 else 7)
            kw = dict(teacher_id=cu.id, institution_id=inst.id,
                      grade_level=GRADE[pc.group],
                      last_login_at=now - timedelta(days=login_days, hours=k))
            if GRADE[pc.group] >= 11:
                kw["track"] = Track.SAYISAL
            stu = mk_user(email=ps.email, name=ps.name,
                          role=UserRole.STUDENT, **kw)
            par = mk_user(email=ps.parent_email, name=ps.parent_name,
                          role=UserRole.PARENT,
                          last_login_at=now - timedelta(days=2 + k))
            db.add(ParentStudentLink(parent_id=par.id, student_id=stu.id,
                                     relation=ps.parent_relation,
                                     is_primary=True, created_by_id=cu.id))
            roster.append((pc, cu, ps, stu, par))
    db.flush()

    # ---------- Kitaplar (grup başına bir kez kurulur, koça kopyalanır) -------
    def builtin_subject(name_like, model=None):
        q = db.query(Subject).filter(Subject.teacher_id.is_(None),
                                     Subject.name == name_like)
        if model is not None:
            q = q.filter(Subject.curriculum_model == model)
        return q.first()

    def book_from_template(coach: User, tpl: BookTemplate) -> Book:
        b = Book(name=tpl.name, subject_id=tpl.subject_id, teacher_id=coach.id,
                 type=tpl.type or BookType.SORU_BANKASI, publisher=tpl.publisher,
                 target_grade_min=tpl.target_grade_min,
                 target_grade_max=tpl.target_grade_max,
                 target_graduate=tpl.target_graduate)
        db.add(b)
        db.flush()
        for i, ts in enumerate(sorted(tpl.sections or [],
                                      key=lambda s: s.order or 0), start=1):
            db.add(BookSection(book_id=b.id, label=ts.label, order=i,
                               test_count=ts.default_test_count or 10,
                               topic_id=ts.topic_id))
        db.flush()
        return b

    def manual_book(coach, name, subject, sections, grade=8) -> Book:
        b = Book(name=name, subject_id=subject.id, teacher_id=coach.id,
                 type=BookType.SORU_BANKASI, target_grade_min=grade,
                 target_grade_max=grade)
        db.add(b)
        db.flush()
        for i, (label, cnt) in enumerate(sections, start=1):
            db.add(BookSection(book_id=b.id, label=label, order=i,
                               test_count=cnt))
        db.flush()
        return b

    lgs_mat = builtin_subject("Matematik", "LGS") or builtin_subject("Matematik")
    lgs_fen = (builtin_subject("Fen Bilimleri", "LGS")
               or builtin_subject("Fen Bilimleri") or lgs_mat)

    coach_books: dict[int, list[Book]] = {}
    for pc, cu in coaches:
        blist: list[Book] = []
        if pc.group == "LGS":
            blist.append(manual_book(
                cu, "LGS Matematik Soru Bankası", lgs_mat,
                [("Çarpanlar ve Katlar", 12), ("Üslü İfadeler", 12),
                 ("Kareköklü İfadeler", 12), ("Veri Analizi", 8),
                 ("Basit Olayların Olma Olasılığı", 8), ("Cebirsel İfadeler", 10),
                 ("Doğrusal Denklemler", 12), ("Eşitsizlikler", 8)]))
            blist.append(manual_book(
                cu, "LGS Fen Bilimleri Soru Bankası", lgs_fen,
                [("Mevsimler ve İklim", 8), ("DNA ve Genetik Kod", 12),
                 ("Basınç", 10), ("Madde ve Endüstri", 12),
                 ("Basit Makineler", 10), ("Enerji Dönüşümleri", 10)]))
        else:
            for cands in CATALOG_BOOKS[pc.group]:
                tpl = (db.query(BookTemplate)
                       .filter(BookTemplate.teacher_id.is_(None),
                               BookTemplate.catalog_status == "verified",
                               BookTemplate.name.in_(cands))
                       .first())
                if tpl is not None:
                    blist.append(book_from_template(cu, tpl))
            if not blist:  # katalog boşsa (dev) elle yedek
                blist.append(manual_book(
                    cu, f"{pc.group} Matematik Soru Bankası",
                    builtin_subject("TYT Matematik") or lgs_mat,
                    [(f"Bölüm {i}", 10) for i in range(1, 9)],
                    grade=GRADE[pc.group]))
        coach_books[cu.id] = blist

    # Atamalar + progress haritası
    sb_map: dict[tuple[int, int], StudentBook] = {}
    for pc, cu, ps, stu, par in roster:
        for b in coach_books[cu.id]:
            sb = StudentBook(student_id=stu.id, book_id=b.id,
                             assigned_at=now - timedelta(days=160))
            db.add(sb)
            db.flush()
            sb_map[(stu.id, b.id)] = sb

    prog_cache: dict[tuple[int, int], SectionProgress] = {}

    def progress(stu_id, book_id, sec_id) -> SectionProgress:
        key = (stu_id, sec_id)
        if key not in prog_cache:
            sb = sb_map[(stu_id, book_id)]
            p = SectionProgress(student_book_id=sb.id, book_section_id=sec_id,
                                reserved_count=0, completed_count=0)
            db.add(p)
            db.flush()
            prog_cache[key] = p
        return prog_cache[key]

    # ---------- 10 haftalık görev geçmişi ----------
    sec_lists: dict[int, list[tuple[Book, list[BookSection]]]] = {
        cu.id: [(b, sorted(b.sections, key=lambda s: s.order))
                for b in coach_books[cu.id]]
        for _, cu in coaches
    }
    sec_cursor: dict[int, int] = {}

    def next_sections(coach_id, stu_id, n):
        flat = [(b, s) for b, secs in sec_lists[coach_id] for s in secs]
        cur = sec_cursor.get(stu_id, 0)
        out = [flat[(cur + i) % len(flat)] for i in range(n)]
        sec_cursor[stu_id] = (cur + n) % len(flat)
        return out

    deneme_label = {"LGS": ("LGS Genel Deneme", 90),
                    "TYT": ("TYT Genel Deneme", 120),
                    "YKS": ("AYT Genel Deneme", 80)}

    task_count = 0
    current_week_tasks: dict[int, list[Task]] = {}
    for pc, cu, ps, stu, par in roster:
        idx = ps.archetype_idx
        rate, acc = ARCHETYPES[idx]
        for week in range(9, -1, -1):  # 9 hafta önce → cari hafta
            wstart = monday - timedelta(weeks=week)
            is_current = week == 0
            eff_rate = rate
            if idx == 3 and week <= 2:  # düşen arketip son haftalarda kopar
                eff_rate = 0.15
            if idx == 4 and week <= 3:
                eff_rate = 0.0
            day_offsets = [0, 2, 4, 5]
            picks = next_sections(cu.id, stu.id, 3)
            week_tasks = []
            for ti, (b, sec) in enumerate(picks):
                d = wstart + timedelta(days=day_offsets[ti])
                planned = rng.choice((3, 4))
                t = Task(student_id=stu.id,
                         title=f"{b.name} — {sec.label}: {planned} test",
                         type=TaskType.TEST, date=d,
                         status=TaskStatus.PENDING, is_draft=False, order=ti)
                db.add(t)
                db.flush()
                item = TaskBookItem(task_id=t.id, book_id=b.id,
                                    book_section_id=sec.id,
                                    planned_count=planned)
                db.add(item)
                p = progress(stu.id, b.id, sec.id)
                done = rng.random() < eff_rate and (not is_current or d <= today)
                if done:
                    corr = max(0, round(planned * 10 * acc + rng.uniform(-3, 3)))
                    corr = min(corr, planned * 10)
                    item.completed_count = planned
                    item.correct_count = corr
                    item.wrong_count = planned * 10 - corr
                    t.status = TaskStatus.COMPLETED
                    t.completed_at = datetime(d.year, d.month, d.day, 18, 30,
                                              tzinfo=timezone.utc)
                    p.completed_count += planned
                elif is_current and d >= today:
                    p.reserved_count += planned  # cari hafta canlı rezerv
                else:
                    item.reservation_released_at = now  # ölü rezerv serbest
                week_tasks.append(t)
                task_count += 1
            act = Task(student_id=stu.id, title="Türkçe · Paragraf çalışması",
                       type=TaskType.OTHER, date=wstart + timedelta(days=1),
                       status=TaskStatus.PENDING, is_draft=False, order=9)
            db.add(act)
            db.flush()
            if rng.random() < eff_rate + 0.1:
                act.status = TaskStatus.COMPLETED
                act.completed_at = now - timedelta(weeks=week)
            task_count += 1
            week_tasks.append(act)
            if week % 2 == 1:  # iki haftada bir kitapsız genel deneme
                dl, dq = deneme_label[pc.group]
                dt_ = Task(student_id=stu.id, title=dl, type=TaskType.OTHER,
                           date=wstart + timedelta(days=5),
                           status=TaskStatus.PENDING, is_draft=False, order=10)
                db.add(dt_)
                db.flush()
                dit = TaskBookItem(task_id=dt_.id, book_id=None,
                                   book_section_id=None, label=dl,
                                   planned_count=dq)
                db.add(dit)
                if rng.random() < eff_rate:
                    dt_.status = TaskStatus.COMPLETED
                    dit.completed_count = dq
                task_count += 1
                week_tasks.append(dt_)
            if is_current:
                current_week_tasks[stu.id] = week_tasks

    # ---------- Denemeler: gerçek karne havuzunu dağıt ----------
    # Havuz = sistemdeki soru-satırlı (pdf_import) denemeler — demo hesaplar hariç
    pool = (db.query(ExamResult)
            .join(User, User.id == ExamResult.student_id)
            .filter(User.is_demo.is_(False),
                    ~User.email.like("%@etutkoc.demo"),
                    ExamResult.id.in_(
                        db.query(ExamResultQuestion.exam_result_id)))
            .order_by(ExamResult.exam_date)
            .all())
    by_grade: dict[int, list[ExamResult]] = {8: [], 11: [], 12: []}
    for e in pool:
        sec = str(e.section or "").upper()
        if "LGS" in sec or "OKUL" in sec:
            by_grade[8].append(e)
        elif "AYT" in sec:
            by_grade[12].append(e)
        else:  # TYT ve diğerleri → 11 + 12
            by_grade[11].append(e)
            by_grade[12].append(e)
    copied = 0
    for pc, cu, ps, stu, par in roster:
        gpool = by_grade[GRADE[pc.group]] or pool
        if not gpool:
            continue
        idx = ps.archetype_idx
        n = rng.choice((3, 4)) if len(gpool) >= 3 else len(gpool)
        chosen = sorted([gpool[(idx + k) % len(gpool)] for k in range(n)],
                        key=lambda e: e.exam_date)
        for k, src in enumerate(chosen):
            when = today - timedelta(weeks=(len(chosen) - k) * 4 - idx % 3)
            copy = ExamResult(
                student_id=stu.id, created_by_id=cu.id,
                title=src.title, exam_date=when, section=src.section,
                total_correct=src.total_correct, total_wrong=src.total_wrong,
                total_blank=src.total_blank, net=src.net,
                subject_nets=src.subject_nets, note=None,
                import_source=src.import_source,
            )
            db.add(copy)
            db.flush()
            for q in (db.query(ExamResultQuestion)
                      .filter(ExamResultQuestion.exam_result_id == src.id).all()):
                db.add(ExamResultQuestion(
                    exam_result_id=copy.id, question_no=q.question_no,
                    subject_name_raw=q.subject_name_raw, subject_id=q.subject_id,
                    topic_label_raw=q.topic_label_raw, topic_id=q.topic_id,
                    correct_answer=q.correct_answer,
                    student_answer=q.student_answer, result=q.result,
                    is_suspect=q.is_suspect, manually_edited=q.manually_edited,
                ))
            copied += 1

    # ---------- Yanlış Soru Arşivi ----------
    wq_count = 0
    for pc, cu, ps, stu, par in roster:
        picks = next_sections(cu.id, stu.id, 3)
        for k, (b, sec) in enumerate(picks[:rng.choice((2, 3))]):
            closed = k == 1
            db.add(WrongQuestion(
                student_id=stu.id, created_by_id=stu.id,
                subject_id=b.subject_id, topic_id=sec.topic_id,
                book_id=b.id, book_section_id=sec.id,
                source_kind=WQ_SOURCE_GOREV if k != 2 else WQ_SOURCE_DENEME,
                error_type=rng.choice(("bilgi", "islem", "dikkat", "yorum")),
                note=f"{sec.label} — "
                     f"{'işlem sırasını karıştırdım' if k == 0 else 'kavramı yanlış hatırlamışım'}",
                status=WQ_STATUS_KAPANDI if closed else WQ_STATUS_ACIK,
                correct_streak=2 if closed else rng.choice((0, 1)),
                attempts_count=3 if closed else 1,
                due_at=now - timedelta(days=1) if not closed else None,
                closed_at=now - timedelta(days=10) if closed else None,
                created_at=now - timedelta(days=20 + k * 7),
            ))
            wq_count += 1

    # ---------- Anketler (tamamlanmış skorlarla + birkaç bekleyen) ----------
    all_codes = SURVEY_BASE + ["mesleki-ilgi", "beceri-seti"]
    templates = {t.code: t for t in db.query(SurveyTemplate)
                 .filter(SurveyTemplate.code.in_(all_codes)).all()}
    q_by_tpl = {code: (db.query(SurveyQuestion)
                       .filter(SurveyQuestion.template_id == tpl.id)
                       .order_by(SurveyQuestion.order_no).all())
                for code, tpl in templates.items()}

    def gen_answers(questions, mood_f: float):
        out = {}
        for q in questions:
            if q.qtype == QTYPE_LIKERT5:
                out[str(q.id)] = max(1, min(5, round(2 + mood_f * 2.4
                                                     + rng.uniform(-1.2, 1.2))))
            elif q.qtype == QTYPE_SLIDER10:
                out[str(q.id)] = max(1, min(10, round(4 + mood_f * 4
                                                      + rng.uniform(-2, 2))))
            elif q.qtype == QTYPE_CHOICE:
                try:
                    opts = json.loads(q.options_json or "[]")
                except (ValueError, TypeError):
                    opts = []
                v = opts[rng.randrange(len(opts))] if opts else ""
                if isinstance(v, dict):
                    v = v.get("value") or v.get("label", "")
                out[str(q.id)] = v
            elif q.qtype == QTYPE_OPEN:
                out[str(q.id)] = rng.choice(
                    ("Daha planlı çalışmak istiyorum.",
                     "Sınavda süre yetiştirmekte zorlanıyorum.",
                     "Sayısal derslerde kendime güveniyorum."))
        return out

    survey_done = survey_pending = 0
    for pc, cu, ps, stu, par in roster:
        idx = ps.archetype_idx
        codes = SURVEY_BASE[:]
        if GRADE[pc.group] == 12:
            codes += ["mesleki-ilgi", "beceri-seti"]
        elif GRADE[pc.group] == 11:
            codes += ["mesleki-ilgi"]
        for ci, code in enumerate(codes):
            tpl = templates.get(code)
            if tpl is None:
                continue
            a = SurveyAssignment(template_id=tpl.id, teacher_id=cu.id,
                                 student_id=stu.id, status=ASSIGNMENT_PENDING,
                                 assigned_at=now - timedelta(weeks=8 - ci))
            db.add(a)
            db.flush()
            # son anket düşük-performans arketiplerinde bekliyor kalsın
            if ci == len(codes) - 1 and idx in (3, 4):
                survey_pending += 1
                continue
            qs = q_by_tpl[code]
            survey_service.save_answers(db, a, tpl, qs,
                                        gen_answers(qs, ARCHETYPES[idx][0]),
                                        complete=True)
            a.completed_at = now - timedelta(weeks=8 - ci, days=-2)
            a.started_at = a.assigned_at
            survey_done += 1

    # ---------- Talepler + veli destek yazışması ----------
    req_count = 0
    for pc, cu in coaches:
        studs = [r[3] for r in roster if r[1].id == cu.id]
        if not studs:
            continue
        s_req = studs[min(1, len(studs) - 1)]
        t = next((x for x in current_week_tasks.get(s_req.id, [])
                  if x.type == TaskType.TEST and x.status != TaskStatus.COMPLETED),
                 None)
        db.add(TaskRequest(
            student_id=s_req.id, teacher_id=cu.id,
            task_id=t.id if t else None, type=RequestType.CHANGE,
            status=RequestStatus.PENDING,
            message="Bu hafta okul sınavlarım var, test sayısını azaltabilir miyiz?",
            proposed_count=2,
            task_title_snapshot=t.title if t else None,
            task_date_snapshot=t.date if t else None,
        ))
        db.add(TaskRequest(
            student_id=studs[0].id, teacher_id=cu.id,
            type=RequestType.QUESTION, status=RequestStatus.RESOLVED,
            message="Deneme analizindeki net fırsatı ne demek?",
            teacher_response="Kapatırsan deneme başına en çok net kazandıracak "
                             "konu demek — programına ekledim.",
            responded_at=now - timedelta(days=4),
        ))
        req_count += 2
        s_sup = studs[min(2, len(studs) - 1)]
        par_sup = next(r[4] for r in roster if r[3].id == s_sup.id)
        sr = SupportRequest(
            requester_id=par_sup.id, requester_role="parent", audience="teacher",
            institution_id=None, target_user_id=cu.id,
            category="progress_question",
            subject=f"{s_sup.full_name} — hafta sonu programı hakkında",
            status="answered", handled_by_id=cu.id,
            handled_at=now - timedelta(days=2),
        )
        db.add(sr)
        db.flush()
        db.add(SupportRequestMessage(
            request_id=sr.id, sender_id=par_sup.id,
            body="Hafta sonu programı biraz yoğun görünüyor, azaltma şansımız var mı?"))
        db.add(SupportRequestMessage(
            request_id=sr.id, sender_id=cu.id,
            body="Deneme haftası olduğu için yoğundu; önümüzdeki hafta dengeledim, "
                 "takip ediyorum."))
        req_count += 2

    # ---------- Seans raporları + AI içgörü + Rota veli yorumları ----------
    from app.routes.api_v2.teacher import _compute_session_prefill
    from app.services import parent_commentary as pc_svc

    counts2 = _seed_sessions_insights_commentaries(
        db, roster=roster, rng=rng, now=now, monday=monday,
        current_week_tasks=current_week_tasks, with_audio=with_audio,
        prefill=_compute_session_prefill, pc_svc=pc_svc,
    )

    db.commit()
    return {
        "institution_id": inst.id,
        "institution_name": inst.name,
        "slug": slug,
        "seed_id": plan.seed_id,
        "coaches": len(coaches),
        "students": len(roster),
        "tasks": task_count,
        "exams": copied,
        "wrong_questions": wq_count,
        "surveys_done": survey_done,
        "surveys_pending": survey_pending,
        "requests": req_count,
        **counts2,
    }


# --- İçgörü/yorum içerik kalıpları (arketip başına) --------------------------

_SESSION_AGENDAS = [
    "Tanışma ve hedef belirleme — haftalık çalışma düzeni, deneme takvimi",
    "Haftalık program değerlendirmesi — biten görevler ve aksayan günler",
    "Deneme analizi — son karne üzerinden net fırsatları",
    "Yanlış soru arşivi alışkanlığı ve tekrar rutini",
    "Motivasyon ve sınav kaygısı görüşmesi — veli beklentileri",
]
_COACH_NOTES = [
    "Programı eksiksiz götürüyor; daha zorlayıcı hedef istiyor. Deneme temposunu koruyacağız.",
    "Genel gidişat iyi; hafta sonu tekrarlarını aksatabiliyor. Pazar akşamı hatırlatma rutini kurduk.",
    "Konsantrasyon dalgalı; akşam bloklarında verim düşüyor. Sabah çalışma denemesine başladık.",
    "Son haftalarda tempo düştü; okul sınavı yoğunluğu erteleme bahanesine dönüşüyor. Küçük hedeflerle toparlama planı yaptık.",
    "Görüşmeye isteksiz katıldı; programa bağlılık çok düşük. Veliyle ortak takip kararı aldık.",
]
_NEXT_CHANGES = [
    "Deneme sayısı haftada ikiye çıkarılacak.",
    "Hafta sonu tekrar bloğu sabit saate alınacak.",
    "Akşam bloğu sabaha taşınacak, günlük hedef küçültülecek.",
    "Görev sayısı geçici azaltılıp tamamlama alışkanlığı geri kazanılacak.",
    "Günde tek küçük görevle yeniden başlangıç; veli günlük teyit verecek.",
]
_INS = [
    dict(sum_="{first} programına yüksek bağlılıkla ilerliyor; tamamlama oranı yüzde {pct} bandında ve deneme netleri istikrarlı yükseliyor. Görüşme notlarında öne çıkan tema, öğrencinin daha zorlayıcı hedef talebi.",
         ag=["Bir üst net bandı hedefi tanımlayıp deneme sıklığını haftada ikiye çıkarmayı konuş",
             "Yanlış soru arşivindeki açık soruların kapanış ritmini birlikte gözden geçir",
             "Bitmeye yaklaşan kaynaklar için yeni dönem kitap planını netleştir"],
         tips=["Başarıyı somut örneklerle takdir et — motivasyonu ilerlemeyi görmekten besleniyor",
               "Mükemmeliyetçilik sinyaline dikkat: hatayı öğrenme fırsatı olarak çerçevele",
               "Hedefi öğrencinin kendisine kurdurt; sahiplenme düzeyi yüksek"],
         wo=["Yüksek tempoda uyku ve denge ihmali başlayabilir",
             "Tek tip kaynakta sıkışma — soru çeşitliliği ihtiyacı"]),
    dict(sum_="{first} istikrarlı bir çizgide; tamamlama oranı yüzde {pct}. Hafta içi düzeni oturmuş durumda, kayıplar neredeyse tamamen hafta sonu tekrar bloklarında yaşanıyor.",
         ag=["Pazar akşamı kurulan hatırlatma rutininin ilk iki haftasını değerlendir",
             "Hafta sonu bloğunu cumartesi sabahına almayı öner",
             "Son denemedeki güçlü dersleri görünür kılıp özgüveni pekiştir"],
         tips=["Küçük ve tutarlı adımları öv; büyük hedef baskısı kurma",
               "Hafta sonu kaybını suçlamadan, düzen sorunu olarak konuş",
               "Kendi ilerleme grafiğini öğrenciyle birlikte incele"],
         wo=["Hafta sonu boşlukları alışkanlığa dönüşmeden yakalanmalı",
             "Okul yoğunlaşınca program esnetme talebi gelebilir"]),
    dict(sum_="{first} orta bantta dalgalı seyrediyor; tamamlama yüzde {pct} civarında. Görüşmelerde akşam bloklarında verim düşüşü ve dikkat dağınıklığı teması tekrarlıyor; sabah çalışma denemesi başlatıldı.",
         ag=["Sabah çalışma denemesinin ilk sonuçlarını birlikte değerlendir",
             "Günlük görev sayısını azaltıp tamamlama hissini güçlendir",
             "Telefon/çalışma ortamı düzenlemesini veliyle birlikte konuş"],
         tips=["Verim saatlerini öğrencinin kendisine keşfettir (odak kayıtları)",
               "Kısa ve sık mola düzeni öner; uzun oturumlar verimsizleşiyor",
               "Başarılı günleri örnek göstererek 'yapabiliyorsun' mesajı ver"],
         wo=["Dalgalanma derinleşirse haftalık plan güveni sarsılabilir",
             "Akşam bloklarında telefonla bölünme sinyali var"]),
    dict(sum_="{first} son haftalarda belirgin tempo kaybında; tamamlama yüzde {pct} seviyesine indi. Okul sınavı yoğunluğu erteleme davranışına dönüşmeye başlamış görünüyor; küçük hedefli toparlama planı devrede.",
         ag=["Küçültülmüş günlük hedeflerin ilk haftasını değerlendir",
             "Yapılmayan görevlerin devri yerine öncelik sıralamasını birlikte yap",
             "Okul takvimiyle çakışan haftalar için önceden esnek plan kur"],
         tips=["Suçlayıcı dilden kaçın; küçük başarıyı anında görünür kıl",
               "'Hepsi ya da hiçbiri' düşüncesini kır — yarım yapılan gün de değerlidir",
               "Kısa vadeli (bu hafta) hedeflerle çalış; uzun vade şu an bunaltıyor"],
         wo=["Erteleme kalıcılaşırsa deneme netleri de düşüşe geçer",
             "Veli baskısı arttıkça motivasyon tersine dönebilir"]),
    dict(sum_="{first} için tablo kritik: tamamlama yüzde {pct} ve son görüşmeye isteksiz katıldı. Programa bağlılık çok düşük; veli ile ortak günlük takip kararı alındı. Yeniden başlangıç stratejisi uygulanıyor.",
         ag=["Günde tek küçük görev stratejisinin ilk günlerini birlikte kontrol et",
             "Veliyle kurulan günlük teyit düzeninin işleyişini gözden geçir",
             "Öğrencinin kendi seçeceği bir dersten başlangıç yaparak direncini azalt"],
         tips=["Görüşmede ders dışı bir bağ kur; güven ilişkisi önce gelir",
               "Hedefi ulaşılabilir en küçük adıma indir — başarı hissi kritik",
               "İlerleme olduğunda anında ve somut geri bildirim ver"],
         wo=["Bir haftadan uzun sessizlik kopuş riski taşır — hızlı temas gerek",
             "Veli-öğrenci gerilimi çalışmayı bloke edebilir; dengeyi koru"]),
]
_DESTEK = [
    "Tempo çok iyi; tek ihtiyacı düzenin bozulmaması. Uyku ve dinlenme saatlerini korumasına yardımcı olun.",
    "Hafta sonu tekrar saatinde evde sakin bir ortam sağlamanız yeterli. Cumartesi sabahını birlikte sabitleyebilirsiniz.",
    "Akşam yerine sabah çalışmayı deniyoruz. Sabah kahvaltıdan sonra kısa bir çalışma bloğu için cesaretlendirin.",
    "Baskı kurmadan küçük başarıları fark edin. 'Bugün hangi görevi bitirdin?' diye sormanız bile düzeni destekler.",
    "Şu an en değerli destek ilgi: her akşam programdan tek bir görevi birlikte kontrol edin, koçuyla kurduğumuz plan bu.",
]


def _soz(n) -> str:
    """0-199 arası sayı → yazıyla (TTS kuralı: seslendirmede rakam yok)."""
    n = int(round(n))
    birler = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi",
              "sekiz", "dokuz"]
    onlar = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış",
             "yetmiş", "seksen", "doksan"]
    if n <= 0:
        return "sıfır"
    if n >= 100:
        rest = n - 100
        return "yüz" if rest == 0 else f"yüz {_soz(rest)}"
    if n < 10:
        return birler[n]
    return (onlar[n // 10] + (" " + birler[n % 10] if n % 10 else "")).strip()


def _seed_sessions_insights_commentaries(db, *, roster, rng, now, monday,
                                         current_week_tasks, with_audio,
                                         prefill, pc_svc) -> dict:
    session_count = insight_count = commentary_count = audio_count = 0
    for pc, cu, ps, stu, par in roster:
        idx = ps.archetype_idx
        rate, _acc = ARCHETYPES[idx]
        mood = MOODS[idx]
        first = stu.full_name.split()[0]
        pct = int(round(rate * 100))
        try:
            snap = json.dumps(prefill(db, stu), ensure_ascii=False, default=str)
        except Exception:
            snap = None

        # --- Seanslar (2 haftada bir, 5 görüşme) ---
        n_done = 0
        for si, wk in enumerate((9, 7, 5, 3, 1)):
            s_status = CoachingSessionStatus.DONE
            note = _COACH_NOTES[idx]
            if idx == 4 and si == 3:  # riskli öğrenci bir görüşmeye gelmedi
                s_status = CoachingSessionStatus.NO_SHOW
                note = None
            db.add(CoachingSession(
                coach_id=cu.id, student_id=stu.id,
                session_date=monday - timedelta(weeks=wk, days=-2),
                status=s_status,
                duration_min=rng.choice((40, 45, 50, 60)),
                channel=(CoachingChannel.IN_PERSON if pc.group == "LGS"
                         else rng.choice((CoachingChannel.ONLINE,
                                          CoachingChannel.IN_PERSON))),
                agenda=_SESSION_AGENDAS[si],
                next_change=_NEXT_CHANGES[idx] if si >= 2 else None,
                coach_note=note,
                mood=mood if s_status == CoachingSessionStatus.DONE else None,
                tags=json.dumps(
                    ["deneme", "program"] if si in (1, 2)
                    else (["motivasyon"] if si == 4 else ["rutin"]),
                    ensure_ascii=False),
                auto_snapshot=snap,
                capture_source=(SessionCaptureSource.VOICE if si in (1, 3)
                                else SessionCaptureSource.MANUAL),
            ))
            if s_status == CoachingSessionStatus.DONE:
                n_done += 1
            session_count += 1

        # --- AI koçluk içgörüsü (KS4 cache) ---
        db.add(CoachingInsight(
            student_id=stu.id, generated_by_id=cu.id,
            summary=_INS[idx]["sum_"].format(first=first, pct=pct),
            agenda_suggestions=json.dumps(_INS[idx]["ag"], ensure_ascii=False),
            psychological_tips=json.dumps(_INS[idx]["tips"], ensure_ascii=False),
            watch_outs=json.dumps(_INS[idx]["wo"], ensure_ascii=False),
            based_on_sessions=n_done, is_stale=False,
            generated_at=now - timedelta(days=1),
        ))
        insight_count += 1

        # --- Rota veli yorumları (program + deneme) ---
        wtasks = current_week_tasks.get(stu.id, [])
        total_w = len(wtasks)
        done_w = sum(1 for t in wtasks if t.status == TaskStatus.COMPLETED)
        undone_titles = [t.title for t in wtasks
                         if t.status != TaskStatus.COMPLETED][:2]
        done_title = next((t.title for t in wtasks
                           if t.status == TaskStatus.COMPLETED), None)

        b1 = (f"Bu hafta {first} için {total_w} görev planlandı; şu ana kadar "
              f"{done_w} tanesi tamamlandı. Son haftalardaki genel tamamlama "
              f"oranı yüzde {pct} civarında.")
        if idx <= 1:
            b2 = (f"{first} planına büyük ölçüde sadık. "
                  + (f"Örneğin “{done_title}” görevi zamanında bitti. "
                     if done_title else "")
                  + "Deneme günlerine katılımı da düzenli.")
        elif idx == 2:
            b2 = ("Sabah saatlerinde yapılan çalışmalarda verim gözle görülür "
                  "şekilde daha iyi. Deneme katılımı düzenli.")
        else:
            b2 = ("Deneme günlerine katılım sürüyor; bu, toparlanma için "
                  "elimizdeki en sağlam zemin.")
        if undone_titles:
            b3 = ("Henüz yapılmayanlar: "
                  + " · ".join(f"“{t}”" for t in undone_titles)
                  + (". Koçu takipte; hafta bitmeden telafi planlandı."
                     if idx <= 2 else
                     ". Koçuyla küçük hedefli bir toparlama planı başlattık."))
        else:
            b3 = "Bu hafta aksayan görev yok — planın tamamı zamanında ilerliyor."
        prog_sections = [
            {"title": "Bu hafta ne oldu", "body": b1},
            {"title": "İyi gidenler", "body": b2},
            {"title": "Aksayan noktalar", "body": b3},
            {"title": "Evde nasıl destek olursunuz", "body": _DESTEK[idx]},
        ]
        prog_speech = (
            f"Merhaba, ben Rota. {first} için bu haftaki programa birlikte bakalım. "
            f"Bu hafta {_soz(total_w)} görev planlandı ve şu ana kadar "
            f"{_soz(done_w)} tanesi tamamlandı. "
            f"Son haftalardaki genel tamamlama oranı yüzde {_soz(pct)} civarında. "
            + ("Planına büyük ölçüde sadık ilerliyor; bu düzeni korumak en önemli konumuz. "
               if idx <= 1 else
               ("Sabah saatlerinde yaptığı çalışmalarda verimi belirgin şekilde daha iyi görüyoruz. "
                if idx == 2 else
                "Son haftalarda temposu düştü; koçuyla küçük hedefli bir toparlama planı başlattık. "))
            + ("Bu hafta aksayan görev yok. " if not undone_titles else
               "Bazı görevler henüz yapılmadı; koçu takip ediyor ve hafta bitmeden telafi planlandı. ")
            + _DESTEK[idx] + " Sorularınız olursa bana yazabilirsiniz."
        )

        latest_exams = (db.query(ExamResult)
                        .filter(ExamResult.student_id == stu.id)
                        .order_by(ExamResult.exam_date.desc()).all())
        den_sections = den_speech = None
        if latest_exams:
            e0 = latest_exams[0]
            net_i = int(round(e0.net or 0))
            prev_same = next((e for e in latest_exams[1:]
                              if e.section == e0.section), None)
            trend_txt = trend_speech = ""
            if prev_same is not None:
                dnet = (e0.net or 0) - (prev_same.net or 0)
                if dnet > 0.5:
                    trend_txt = (f" Bir önceki aynı tür denemeye göre yaklaşık "
                                 f"{abs(round(dnet, 1))} net artış var.")
                    trend_speech = (" Bir önceki denemesine göre neti arttı; "
                                    "gidişat yukarı yönlü. ")
                elif dnet < -0.5:
                    trend_txt = (f" Bir önceki aynı tür denemeye göre yaklaşık "
                                 f"{abs(round(dnet, 1))} net düşüş var.")
                    trend_speech = (" Bir önceki denemesine göre nette bir miktar "
                                    "düşüş var; koçu nedenlerini konu bazında inceledi. ")
                else:
                    trend_txt = " Netler bir önceki denemeyle aynı bantta."
                    trend_speech = " Netleri önceki denemeyle aynı seviyede seyrediyor. "
            wq_open = (db.query(WrongQuestion)
                       .filter(WrongQuestion.student_id == stu.id,
                               WrongQuestion.status == WQ_STATUS_ACIK)
                       .first())
            weak_label = None
            if wq_open and wq_open.book_section_id:
                bs_ = db.get(BookSection, wq_open.book_section_id)
                weak_label = bs_.label if bs_ else None
            den_sections = [
                {"title": "Son denemeler ne söylüyor",
                 "body": (f"Son deneme “{e0.title}”: {net_i} net. "
                          "Net, doğru sayısından yanlışların bir kısmının "
                          "düşülmesiyle hesaplanan puan karşılığıdır." + trend_txt)},
                {"title": "Nereden puan kazanılır",
                 "body": ((f"En hızlı kazanım “{weak_label}” konusunda görünüyor; "
                           "yanlış soru arşivinde bu konudan açık sorular var ve "
                           "programda tekrarı planlandı.")
                          if weak_label else
                          "Koçu, deneme analizindeki en yüksek kazanım fırsatı "
                          "olan konuları haftalık programa ekledi.")},
                {"title": "Unutulmaya başlayan konular",
                 "body": ("Analizde belirgin bir unutma sinyali yok; tekrar "
                          "düzeni korunuyor."
                          if idx <= 1 else
                          "Önceki denemelerde doğru yapılan bazı konularda son "
                          "denemede kayıp var; aralıklı tekrar kuyruğuna alındı.")},
                {"title": "Evde nasıl destek olursunuz",
                 "body": ("Deneme akşamı sonucu değil, deneyimi konuşun: "
                          "'Hangi soru ilginçti?' gibi sorular kaygıyı azaltır. "
                          "Sayı baskısını koçuna bırakın.")},
            ]
            den_speech = (
                f"Merhaba, ben Rota. {first} için deneme sonuçlarına birlikte bakalım. "
                f"Son denemesinde yaklaşık {_soz(net_i)} net yaptı. "
                "Net dediğimiz şey, doğruların içinden yanlışların bir kısmının "
                "düşülmesiyle bulunan puan karşılığı. "
                + trend_speech
                + ((f"En hızlı kazanım {weak_label} konusunda görünüyor; koçu bu "
                    f"konuyu haftalık programa ekledi. ")
                   if weak_label else
                   "Koçu, en çok net kazandıracak konuları haftalık programa ekledi. ")
                + "Deneme akşamları sonucu değil deneyimi konuşmanız, sayı "
                  "baskısını koçuna bırakmanız en büyük destek olur. "
                  "Sorularınız olursa bana yazabilirsiniz."
            )

        for kind, sections, speech in (
            (pc_svc.PC_KIND_PROGRAM, prog_sections, prog_speech),
            (pc_svc.PC_KIND_DENEME, den_sections, den_speech),
        ):
            if sections is None:
                continue
            row = ParentCommentary(
                student_id=stu.id, kind=kind,
                speech_text=speech,
                based_on_json=json.dumps(
                    pc_svc.compute_signature(db, stu.id, kind),
                    ensure_ascii=False, default=str),
                generated_by_id=par.id,
                generated_at=now - timedelta(hours=rng.randrange(6, 60)),
            )
            row.set_sections(sections)
            if with_audio:
                try:
                    from app.services.tts import synthesize_speech
                    audio, ctype = synthesize_speech(speech)
                    row.audio = audio
                    row.audio_content_type = ctype
                    row.audio_generated_at = now
                    audio_count += 1
                except Exception:
                    pass  # ses best-effort — yorum metni yine de kurulur
            db.add(row)
            commentary_count += 1

    return {
        "coach_sessions": session_count,
        "insights": insight_count,
        "commentaries": commentary_count,
        "commentaries_with_audio": audio_count,
    }
