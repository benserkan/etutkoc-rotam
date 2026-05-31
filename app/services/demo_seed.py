"""Demo Ekosistem Oluşturucu — süper admin "Demo Kurum/Koç Aç" akışı.

Tasarım kararı (kullanıcı 2026-05-31):
  - `is_demo` flag YOK; üretilen hesaplar **gerçek hesap** gibi davranır
  - İstatistik filtre yok, "hayalet kuralı" yok — tanıtım hesapları sayım'a katılır
  - Süper admin görüşme sonrası mevcut "Kurum Sil" akışıyla cascade temizler
  - Email pattern `demo-{uuid8}-{role}@etutkoc.com` ile görsel ayrım yapılır
  - Standart şifre `Demo123!@` — kopya-yapıştır kolay (must_change=False)

3 kind:
  - `institution`: 1 kurum + 1 admin + 1 koç + 1 öğrenci + 1 veli + örnek veri
  - `solo_coach`: 1 bağımsız koç + 2 öğrenci + 2 veli + örnek veri
  - `institution_teacher`: "Demo Etüt Kurumu" + 1 öğretmen + 1 öğrenci + 1 veli
    (kurum yöneticisi yok — sade akış)

Örnek veri (her senaryoda):
  - 2 ders (Matematik + Türkçe)
  - 1 kitap (her ders için bir tane, 4 bölüm)
  - 5-8 görev (geçmiş 3 gün + bugün + yarın)
  - 1-2 deneme sonucu
  - 1 koçluk seansı

Şifre değişimi: gerçek kullanıcı akışıyla aynı (Demo123!@ ile login; isteğe bağlı
şifre değiştirme akışı işliyor). must_change=False bırakıyoruz çünkü demo
gösteren kişi şifreyi değiştirmeden kullanmak ister.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import (
    Book,
    BookSection,
    BookType,
    Institution,
    ParentStudentLink,
    SectionProgress,
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
from app.models.coach_billing import CoachStudentRate
from app.models.coaching_session import (
    CoachingChannel,
    CoachingSession,
    CoachingSessionStatus,
)
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult, compute_net
from app.services.security import hash_password


logger = logging.getLogger(__name__)


DemoKind = Literal["institution", "solo_coach", "institution_teacher"]
VALID_KINDS: set[str] = {"institution", "solo_coach", "institution_teacher"}

DEMO_PASSWORD = "Demo123!@"
DEMO_EMAIL_DOMAIN = "etutkoc.com"


@dataclass
class DemoCredential:
    """Tek kullanıcı için demo kimlik bilgisi (response için)."""
    role_label: str         # "Kurum Yöneticisi", "Koç", "Öğrenci", "Veli"
    full_name: str
    email: str
    password: str
    user_id: int
    panel_path: str         # "/institution", "/teacher", "/student", "/parent"


@dataclass
class DemoSeedResult:
    """Demo ekosistem oluşturma sonucu."""
    kind: DemoKind
    institution_id: int | None
    institution_name: str | None
    seed_id: str = ""              # M5 ext — aynı seansın UUID hex'i (32 char)
    label: str | None = None       # M5 ext — süper admin etiketi
    credentials: list[DemoCredential] = field(default_factory=list)
    student_count: int = 0
    summary: str = ""


# =============================================================================
# Yardımcılar
# =============================================================================


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def _make_email(prefix: str, uid: str) -> str:
    return f"demo-{uid}-{prefix}@{DEMO_EMAIL_DOMAIN}"


def _panel_for(role: UserRole) -> str:
    return {
        UserRole.SUPER_ADMIN: "/admin",
        UserRole.INSTITUTION_ADMIN: "/institution",
        UserRole.TEACHER: "/teacher",
        UserRole.STUDENT: "/student",
        UserRole.PARENT: "/parent",
    }.get(role, "/me/account")


def _role_label(role: UserRole) -> str:
    return {
        UserRole.SUPER_ADMIN: "Süper Admin",
        UserRole.INSTITUTION_ADMIN: "Kurum Yöneticisi",
        UserRole.TEACHER: "Koç",
        UserRole.STUDENT: "Öğrenci",
        UserRole.PARENT: "Veli",
    }.get(role, str(role))


def _new_user(
    *,
    email: str,
    full_name: str,
    role: UserRole,
    seed_id: str,
    label: str | None,
    institution_id: int | None = None,
    teacher_id: int | None = None,
    grade_level: int | None = None,
    plan: str | None = None,
) -> User:
    """Demo kullanıcı objesi — şifre + standart alanlar + demo etiketleri."""
    now = datetime.now(timezone.utc)
    return User(
        email=email,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name=full_name,
        role=role,
        is_active=True,
        institution_id=institution_id,
        teacher_id=teacher_id,
        grade_level=grade_level,
        plan=plan,
        # Demo hesabın must_change=False — kopya-yapıştır şifreyle direkt kullansın
        must_change_password=False,
        email_verified_at=now,
        created_at=now,
        # M5 ext — Demo etiketleri
        is_demo=True,
        demo_seed_id=seed_id,
        demo_label=label,
    )


def _slugify_demo(name: str) -> str:
    """Demo kurum için sade slug üretici (tutarlı, çakışma minimal)."""
    return f"demo-{_short_uuid()}"


# =============================================================================
# Örnek veri kurulumu
# =============================================================================


def _seed_curriculum(db: Session, coach: User) -> tuple[list[Subject], list[Book]]:
    """Koç için 2 ders + 2 kitap (her birinde 4 bölüm) ekler.

    Returns (subjects, books).
    """
    subjects: list[Subject] = []
    books: list[Book] = []

    subj_data = [
        ("Matematik", [
            ("Sayılar", 20),
            ("Eşitsizlikler", 20),
            ("Üçgenler", 20),
            ("Olasılık", 20),
        ]),
        ("Türkçe", [
            ("Sözcükte Anlam", 15),
            ("Cümlede Anlam", 15),
            ("Paragraf", 15),
            ("Cümlenin Ögeleri", 15),
        ]),
    ]
    for subj_name, sections in subj_data:
        subj = Subject(
            name=f"{subj_name} (Demo)",
            order=999,
            is_builtin=False,
            teacher_id=coach.id,
        )
        db.add(subj)
        db.flush()
        subjects.append(subj)

        # Her ders için 1 topic + N section
        topic = Topic(name="Genel", order=0, subject_id=subj.id)
        db.add(topic)
        db.flush()

        book = Book(
            name=f"Demo {subj_name} Soru Bankası",
            subject_id=subj.id,
            type=BookType.SORU_BANKASI,
            teacher_id=coach.id,
        )
        db.add(book)
        db.flush()
        books.append(book)

        for idx, (sec_label, test_count) in enumerate(sections):
            sec = BookSection(
                book_id=book.id,
                label=sec_label,
                test_count=test_count,
                order=idx,
                topic_id=topic.id,
            )
            db.add(sec)
        db.flush()

    return subjects, books


def _seed_student_data(
    db: Session, *, coach: User, student: User, books: list[Book]
) -> None:
    """Öğrenciye kitap ataması + 5 örnek görev (geçmiş+bugün+yarın) + 1 deneme."""
    today = date.today()

    # Kitap ataması + section progress
    book_section_ids: list[int] = []
    for book in books:
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb)
        db.flush()

        for sec in book.sections:
            sp = SectionProgress(
                student_book_id=sb.id,
                book_section_id=sec.id,
                completed_count=0,
                reserved_count=0,
            )
            db.add(sp)
            book_section_ids.append((book.id, sec.id))
        db.flush()

    # 5 görev: 3 geçmiş (tamamlanmış+kısmen+pending) + bugün + yarın
    task_specs = [
        # (gün_ofseti, status, completed_pct, kitap_idx, bölüm_idx, planlı, başlık)
        (-3, TaskStatus.COMPLETED, 1.0, 0, 0, 15, "Görev"),
        (-2, TaskStatus.PARTIAL, 0.5, 0, 1, 10, "Görev"),
        (-1, TaskStatus.PENDING, 0.0, 1, 0, 8, "Görev"),
        (0, TaskStatus.PENDING, 0.0, 0, 2, 12, "Görev"),
        (1, TaskStatus.PENDING, 0.0, 1, 1, 10, "Görev"),
    ]
    for ofs, st, pct, book_idx, sec_idx, planlı, title in task_specs:
        task_date = today + timedelta(days=ofs)
        # Çakışma engellemek için (book_idx, sec_idx) güvenli erişim
        if book_idx >= len(books):
            continue
        book = books[book_idx]
        sections = list(book.sections)
        if sec_idx >= len(sections):
            continue
        sec = sections[sec_idx]
        task = Task(
            student_id=student.id,
            date=task_date,
            type=TaskType.TEST,
            title=title,
            status=st,
            order=0,
            is_draft=False,
            published_at=datetime.now(timezone.utc) if not (task_date > today) else None,
            completed_at=(datetime.now(timezone.utc) if st == TaskStatus.COMPLETED else None),
        )
        db.add(task)
        db.flush()
        completed_count = int(planlı * pct)
        item = TaskBookItem(
            task_id=task.id,
            book_id=book.id,
            book_section_id=sec.id,
            planned_count=planlı,
            completed_count=completed_count,
            correct_count=(int(completed_count * 0.8) if completed_count > 0 else None),
            wrong_count=(int(completed_count * 0.15) if completed_count > 0 else None),
        )
        db.add(item)
        # SectionProgress'i güncelle (rezerv + tamam)
        sp = (
            db.query(SectionProgress)
            .filter(SectionProgress.book_section_id == sec.id)
            .join(StudentBook, SectionProgress.student_book_id == StudentBook.id)
            .filter(StudentBook.student_id == student.id)
            .first()
        )
        if sp is not None:
            if st == TaskStatus.COMPLETED:
                sp.completed_count = (sp.completed_count or 0) + planlı
            elif st == TaskStatus.PARTIAL:
                sp.completed_count = (sp.completed_count or 0) + completed_count
                sp.reserved_count = (sp.reserved_count or 0) + (planlı - completed_count)
            else:
                sp.reserved_count = (sp.reserved_count or 0) + planlı
        db.flush()

    # 1 deneme sonucu (geçen hafta)
    exam = ExamResult(
        student_id=student.id,
        created_by_id=coach.id if coach else None,
        title="Demo LGS Tam Deneme",
        exam_date=today - timedelta(days=7),
        section=ExamSection.LGS,
        total_correct=68,
        total_wrong=12,
        total_blank=10,
        net=compute_net(68, 12, ExamSection.LGS),
    )
    db.add(exam)


def _seed_session(
    db: Session, *, coach: User, student: User
) -> None:
    """1 örnek koçluk seansı + cari ücret kaydı."""
    today = date.today()
    rate = CoachStudentRate(
        coach_id=coach.id,
        student_id=student.id,
        session_fee=2500,
    )
    db.add(rate)

    sess = CoachingSession(
        coach_id=coach.id,
        student_id=student.id,
        session_date=today - timedelta(days=2),
        status=CoachingSessionStatus.DONE,
        duration_min=45,
        channel=CoachingChannel.ONLINE,
        agenda="Hafta gözden geçirme + matematik plan revizyonu",
        next_change="Üçgenler konusunu öne çek",
    )
    db.add(sess)


# =============================================================================
# Ana giriş — kind seçimi
# =============================================================================


def create_demo_ecosystem(
    db: Session, *, kind: str, label: str | None = None,
) -> DemoSeedResult:
    """Süper admin için 3 kind'tan birini üret.

    Tutarlı ilişkiler kurulur. Tek transaction — bir hata olursa rollback
    çağrı yerinde yapılır.

    `label`: süper admin notu ("ABC Etüt için demo"); listede + dialog'da görünür.
    Boşaltılırsa NULL kayıt edilir.
    """
    if kind not in VALID_KINDS:
        raise ValueError(f"Geçersiz kind: {kind}")

    # M5 ext — Aynı seansın tüm kayıtları için ortak UUID hex (32 char).
    # demo_seed_id alanına yazılır; toplu silme ve listeleme bu ID üzerinden.
    seed_id = uuid.uuid4().hex
    uid = seed_id[:8]
    label_clean = (label or "").strip() or None
    creds: list[DemoCredential] = []
    result: DemoSeedResult

    if kind == "institution":
        # 1 kurum + 1 admin + 1 koç + 1 öğrenci + 1 veli
        inst = Institution(
            name=f"Demo Etüt Kurumu ({uid})",
            slug=_slugify_demo("kurum"),
            plan="etut_standart",
            is_active=True,
            contact_email=_make_email("kurum", uid),
            is_demo=True,
            demo_seed_id=seed_id,
            demo_label=label_clean,
        )
        db.add(inst)
        db.flush()

        admin_user = _new_user(
            email=_make_email("yonetici", uid),
            full_name="Demo Kurum Yöneticisi",
            role=UserRole.INSTITUTION_ADMIN,
            seed_id=seed_id,
            label=label_clean,
            institution_id=inst.id,
        )
        coach = _new_user(
            email=_make_email("koc", uid),
            full_name="Demo Koç Mehmet",
            role=UserRole.TEACHER,
            seed_id=seed_id,
            label=label_clean,
            institution_id=inst.id,
        )
        db.add_all([admin_user, coach])
        db.flush()

        student = _new_user(
            email=_make_email("ogrenci", uid),
            full_name="Demo Öğrenci Ayşe",
            role=UserRole.STUDENT,
            seed_id=seed_id,
            label=label_clean,
            institution_id=inst.id,
            teacher_id=coach.id,
            grade_level=8,
        )
        parent = _new_user(
            email=_make_email("veli", uid),
            full_name="Demo Veli (Anne)",
            role=UserRole.PARENT,
            seed_id=seed_id,
            label=label_clean,
        )
        db.add_all([student, parent])
        db.flush()

        # Veli ↔ öğrenci bağı
        db.add(ParentStudentLink(parent_id=parent.id, student_id=student.id))

        # Müfredat + öğrenci verisi + seans
        _, books = _seed_curriculum(db, coach)
        _seed_student_data(db, coach=coach, student=student, books=books)
        _seed_session(db, coach=coach, student=student)

        for u in (admin_user, coach, student, parent):
            creds.append(DemoCredential(
                role_label=_role_label(u.role),
                full_name=u.full_name,
                email=u.email,
                password=DEMO_PASSWORD,
                user_id=u.id,
                panel_path=_panel_for(u.role),
            ))

        result = DemoSeedResult(
            kind="institution",
            institution_id=inst.id,
            institution_name=inst.name,
            seed_id=seed_id,
            label=label_clean,
            credentials=creds,
            student_count=1,
            summary=f"Demo kurum #{inst.id} (1 admin + 1 koç + 1 öğr + 1 veli + örnek veri)",
        )

    elif kind == "solo_coach":
        # 1 bağımsız koç + 2 öğrenci + 2 veli (her öğrenciye 1)
        coach = _new_user(
            email=_make_email("koc", uid),
            full_name="Demo Bağımsız Koç Selin",
            role=UserRole.TEACHER,
            seed_id=seed_id,
            label=label_clean,
            plan="solo_pro",  # ücretli paket — AI özellikleri açık
        )
        db.add(coach)
        db.flush()

        student1 = _new_user(
            email=_make_email("ogrenci1", uid),
            full_name="Demo Öğrenci Yusuf",
            role=UserRole.STUDENT,
            seed_id=seed_id,
            label=label_clean,
            teacher_id=coach.id,
            grade_level=8,
        )
        student2 = _new_user(
            email=_make_email("ogrenci2", uid),
            full_name="Demo Öğrenci Zeynep",
            role=UserRole.STUDENT,
            seed_id=seed_id,
            label=label_clean,
            teacher_id=coach.id,
            grade_level=8,
        )
        parent1 = _new_user(
            email=_make_email("veli1", uid),
            full_name="Demo Veli (Yusuf'un Annesi)",
            role=UserRole.PARENT,
            seed_id=seed_id,
            label=label_clean,
        )
        parent2 = _new_user(
            email=_make_email("veli2", uid),
            full_name="Demo Veli (Zeynep'in Babası)",
            role=UserRole.PARENT,
            seed_id=seed_id,
            label=label_clean,
        )
        db.add_all([student1, student2, parent1, parent2])
        db.flush()

        db.add_all([
            ParentStudentLink(parent_id=parent1.id, student_id=student1.id),
            ParentStudentLink(parent_id=parent2.id, student_id=student2.id),
        ])

        _, books = _seed_curriculum(db, coach)
        _seed_student_data(db, coach=coach, student=student1, books=books)
        _seed_student_data(db, coach=coach, student=student2, books=books)
        _seed_session(db, coach=coach, student=student1)

        for u in (coach, student1, student2, parent1, parent2):
            creds.append(DemoCredential(
                role_label=_role_label(u.role),
                full_name=u.full_name,
                email=u.email,
                password=DEMO_PASSWORD,
                user_id=u.id,
                panel_path=_panel_for(u.role),
            ))

        result = DemoSeedResult(
            kind="solo_coach",
            institution_id=None,
            institution_name=None,
            seed_id=seed_id,
            label=label_clean,
            credentials=creds,
            student_count=2,
            summary=f"Demo bağımsız koç #{coach.id} (1 koç + 2 öğr + 2 veli + örnek veri)",
        )

    else:  # institution_teacher
        # "Demo Etüt Kurumu" + 1 öğretmen + 1 öğrenci + 1 veli (kurum admin yok)
        inst = Institution(
            name=f"Demo Kurum (Öğretmen) ({uid})",
            slug=_slugify_demo("ogretmen"),
            plan="etut_standart",
            is_active=True,
            contact_email=_make_email("kurum", uid),
            is_demo=True,
            demo_seed_id=seed_id,
            demo_label=label_clean,
        )
        db.add(inst)
        db.flush()

        coach = _new_user(
            email=_make_email("ogretmen", uid),
            full_name="Demo Öğretmen Emre",
            role=UserRole.TEACHER,
            seed_id=seed_id,
            label=label_clean,
            institution_id=inst.id,
        )
        db.add(coach)
        db.flush()

        student = _new_user(
            email=_make_email("ogrenci", uid),
            full_name="Demo Öğrenci Elif",
            role=UserRole.STUDENT,
            seed_id=seed_id,
            label=label_clean,
            institution_id=inst.id,
            teacher_id=coach.id,
            grade_level=8,
        )
        parent = _new_user(
            email=_make_email("veli", uid),
            full_name="Demo Veli (Anne)",
            role=UserRole.PARENT,
            seed_id=seed_id,
            label=label_clean,
        )
        db.add_all([student, parent])
        db.flush()

        db.add(ParentStudentLink(parent_id=parent.id, student_id=student.id))

        _, books = _seed_curriculum(db, coach)
        _seed_student_data(db, coach=coach, student=student, books=books)
        _seed_session(db, coach=coach, student=student)

        for u in (coach, student, parent):
            creds.append(DemoCredential(
                role_label=_role_label(u.role),
                full_name=u.full_name,
                email=u.email,
                password=DEMO_PASSWORD,
                user_id=u.id,
                panel_path=_panel_for(u.role),
            ))

        result = DemoSeedResult(
            kind="institution_teacher",
            institution_id=inst.id,
            institution_name=inst.name,
            seed_id=seed_id,
            label=label_clean,
            credentials=creds,
            student_count=1,
            summary=f"Demo öğretmen senaryosu #{coach.id} (1 öğretmen + 1 öğr + 1 veli + örnek veri)",
        )

    logger.info("demo_seed: %s", result.summary)
    return result


# =============================================================================
# M5 ext — Liste + Toplu Silme
# =============================================================================


@dataclass
class DemoSessionListItem:
    """Bir demo seansı (kart için)."""
    seed_id: str
    kind: str
    label: str | None
    institution_id: int | None
    institution_name: str | None
    user_count: int
    student_count: int
    created_at: datetime


def list_demo_sessions(db: Session) -> list[DemoSessionListItem]:
    """Tüm demo seanslarını gruplayarak listele (yenisi → eskisi).

    Her unique `demo_seed_id` için bir DemoSessionListItem üretilir. Aynı
    seansa ait Institution (varsa) + User'lar tek satırda özetlenir.
    """
    from sqlalchemy import case as sa_case, func as sa_func

    # Önce User tablosundan seed_id'leri + örnek satırları topla
    rows = (
        db.query(
            User.demo_seed_id,
            sa_func.min(User.demo_label).label("label"),
            sa_func.count(User.id).label("user_count"),
            sa_func.sum(
                # SQLite-uyumlu CASE — STUDENT rolünde sayım
                sa_case(
                    (User.role == UserRole.STUDENT, 1),
                    else_=0,
                )
            ).label("student_count"),
            sa_func.min(User.created_at).label("created_at"),
        )
        .filter(
            User.is_demo.is_(True),
            User.demo_seed_id.is_not(None),
        )
        .group_by(User.demo_seed_id)
        .all()
    )

    out: list[DemoSessionListItem] = []
    for r in rows:
        # Kurum bilgisi (varsa) — aynı seed_id ile
        inst = (
            db.query(Institution)
            .filter(Institution.demo_seed_id == r.demo_seed_id)
            .first()
        )
        # Kind tahmini: kurum varsa "institution" veya "institution_teacher",
        # kurum yoksa "solo_coach". Daha hassas ayrım için INSTITUTION_ADMIN
        # rolü kontrolü:
        if inst is not None:
            has_inst_admin = (
                db.query(User.id)
                .filter(
                    User.demo_seed_id == r.demo_seed_id,
                    User.role == UserRole.INSTITUTION_ADMIN,
                )
                .first()
                is not None
            )
            kind = "institution" if has_inst_admin else "institution_teacher"
        else:
            kind = "solo_coach"

        out.append(DemoSessionListItem(
            seed_id=r.demo_seed_id,
            kind=kind,
            label=r.label,
            institution_id=inst.id if inst else None,
            institution_name=inst.name if inst else None,
            user_count=int(r.user_count or 0),
            student_count=int(r.student_count or 0),
            created_at=r.created_at,
        ))

    # En yeni → en eski
    out.sort(key=lambda x: x.created_at, reverse=True)
    return out


def delete_demo_session(db: Session, *, seed_id: str) -> dict:
    """Bir demo seansının tüm kayıtlarını cascade sil.

    Sıra (FK dependency):
      1. Öğrencilerin örnek verisi (ExamResult, CoachingSession, CoachStudentRate,
         TaskBookItem, Task, SectionProgress, StudentBook, ParentStudentLink)
      2. Müfredat (BookSection, Topic, Book, Subject — koçlar üzerinden)
      3. User'lar
      4. Institution

    Sadece is_demo=True kayıtlara dokunur. Gerçek hesaplara erişmez.

    Returns: silinen sayım dict'i {users, institutions, tasks, exams, sessions}.
    """
    from sqlalchemy import delete as sa_delete

    from app.models import (
        ParentStudentLink as _PSL,
        SectionProgress as _SP,
        StudentBook as _SB,
        Task as _Task,
        TaskBookItem as _TBI,
        Subject as _Subject,
        Topic as _Topic,
        Book as _Book,
        BookSection as _BS,
    )
    from app.models.coach_billing import CoachPayment, CoachStudentRate
    from app.models.coaching_session import CoachingInsight, CoachingSession
    from app.models.exam_result import ExamResult

    # Önce seansa ait tüm User ID'leri bul
    user_rows = (
        db.query(User)
        .filter(User.demo_seed_id == seed_id, User.is_demo.is_(True))
        .all()
    )
    user_ids = [u.id for u in user_rows]

    inst_rows = (
        db.query(Institution)
        .filter(Institution.demo_seed_id == seed_id, Institution.is_demo.is_(True))
        .all()
    )
    inst_ids = [i.id for i in inst_rows]

    if not user_ids and not inst_ids:
        return {"users": 0, "institutions": 0, "tasks": 0, "exams": 0, "sessions": 0}

    counts: dict[str, int] = {}

    if user_ids:
        # Öğrenci verisi
        counts["exams"] = db.query(ExamResult).filter(
            ExamResult.student_id.in_(user_ids)
        ).count()
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(user_ids)))

        counts["sessions"] = db.query(CoachingSession).filter(
            (CoachingSession.student_id.in_(user_ids))
            | (CoachingSession.coach_id.in_(user_ids))
        ).count()
        db.execute(sa_delete(CoachingSession).where(
            (CoachingSession.student_id.in_(user_ids))
            | (CoachingSession.coach_id.in_(user_ids))
        ))

        # CoachingInsight — student_id'ye bağlı
        db.execute(sa_delete(CoachingInsight).where(
            CoachingInsight.student_id.in_(user_ids)
        ))

        # Coach billing
        db.execute(sa_delete(CoachPayment).where(
            CoachPayment.student_id.in_(user_ids)
        ))
        db.execute(sa_delete(CoachStudentRate).where(
            CoachStudentRate.student_id.in_(user_ids)
        ))

        # Task → TaskBookItem
        task_ids = [
            tid for (tid,) in db.query(_Task.id)
            .filter(_Task.student_id.in_(user_ids)).all()
        ]
        counts["tasks"] = len(task_ids)
        if task_ids:
            db.execute(sa_delete(_TBI).where(_TBI.task_id.in_(task_ids)))
            db.execute(sa_delete(_Task).where(_Task.id.in_(task_ids)))

        # ParentStudentLink (her iki yön)
        db.execute(sa_delete(_PSL).where(
            (_PSL.parent_id.in_(user_ids)) | (_PSL.student_id.in_(user_ids))
        ))

        # StudentBook + SectionProgress
        sb_ids = [
            sid for (sid,) in db.query(_SB.id)
            .filter(_SB.student_id.in_(user_ids)).all()
        ]
        if sb_ids:
            db.execute(sa_delete(_SP).where(_SP.student_book_id.in_(sb_ids)))
            db.execute(sa_delete(_SB).where(_SB.id.in_(sb_ids)))

        # Müfredat (koçun yarattığı)
        book_ids = [
            bid for (bid,) in db.query(_Book.id)
            .filter(_Book.teacher_id.in_(user_ids)).all()
        ]
        if book_ids:
            db.execute(sa_delete(_BS).where(_BS.book_id.in_(book_ids)))
            db.execute(sa_delete(_Book).where(_Book.id.in_(book_ids)))

        subject_ids = [
            sid for (sid,) in db.query(_Subject.id)
            .filter(_Subject.teacher_id.in_(user_ids)).all()
        ]
        if subject_ids:
            db.execute(sa_delete(_Topic).where(_Topic.subject_id.in_(subject_ids)))
            db.execute(sa_delete(_Subject).where(_Subject.id.in_(subject_ids)))

        # Son: User'lar
        counts["users"] = len(user_ids)
        db.execute(sa_delete(User).where(User.id.in_(user_ids)))

    if inst_ids:
        counts["institutions"] = len(inst_ids)
        db.execute(sa_delete(Institution).where(Institution.id.in_(inst_ids)))

    db.flush()
    return counts
