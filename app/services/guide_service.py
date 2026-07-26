"""Rehber (rol bazlı onboarding guide) servisi — TEK MERKEZ.

İki sorumluluk:
1) İlerleme durumu (user_guide_states): başlat / bölüm tamamla / bitir /
   kapat (dismiss) / sıfırla. Cihazdan bağımsız — mobil ve web aynı durumu görür.
2) "Şimdi sen yap" kontrol listesi: SAKLANMAZ, her istekte GERÇEK veriden
   hesaplanır (kitap eklendi mi, öğrenciye atandı mı, program yayınlandı mı,
   deneme girildi mi). Rehber oynatıcısı bölüm geçişlerini buna göre kilitler/açar.

Rol eşlemesi: guide_key hangi role aitse yalnız o rol erişir (aksi 404 —
varlık ifşası yok).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Book,
    ExamResult,
    StudentBook,
    Task,
    User,
    UserGuideState,
    WeeklyProgram,
)
from app.models.guide import (
    GUIDE_COACH_ONBOARDING,
    GUIDE_STATUS_COMPLETED,
    GUIDE_STATUS_DISMISSED,
    GUIDE_STATUS_IN_PROGRESS,
    GUIDE_STUDENT_ONBOARDING,
)
from app.models.user import UserRole

# guide_key → erişebilen rol
GUIDE_ROLES: dict[str, UserRole] = {
    GUIDE_COACH_ONBOARDING: UserRole.TEACHER,
    GUIDE_STUDENT_ONBOARDING: UserRole.STUDENT,
}

# Rehber bölüm anahtarları (frontend içerikle eşleşir; sıra önemli)
COACH_CHAPTERS = [
    "hosgeldin",
    "kitap-ekle",
    "ogrenci-ata",
    "program-kur",
    "yayinla-duyur",
    "hafta-takip",
    "deneme-gir",
]

STUDENT_CHAPTERS = [
    "ogr-hosgeldin",
    "ogr-bugun",
    "ogr-kitaplar",
    "ogr-yanlislar",
    "ogr-denemeler",
    "ogr-gelisim",
    "ogr-iletisim",
]

CHAPTERS_BY_GUIDE: dict[str, list[str]] = {
    GUIDE_COACH_ONBOARDING: COACH_CHAPTERS,
    GUIDE_STUDENT_ONBOARDING: STUDENT_CHAPTERS,
}

PROGRESS_ACTIONS = {"start", "chapter_done", "watch", "complete", "dismiss", "reset"}


def guide_for_role(user: User) -> str | None:
    """Kullanıcının rolüne ait rehber anahtarı (yoksa None)."""
    for key, role in GUIDE_ROLES.items():
        if user.role == role:
            return key
    return None


def can_access(user: User, guide_key: str) -> bool:
    role = GUIDE_ROLES.get(guide_key)
    return role is not None and user.role == role


def get_state(db: Session, user: User, guide_key: str) -> UserGuideState | None:
    return db.execute(
        select(UserGuideState).where(
            UserGuideState.user_id == user.id,
            UserGuideState.guide_key == guide_key,
        )
    ).scalar_one_or_none()


def _get_or_create(db: Session, user: User, guide_key: str) -> UserGuideState:
    state = get_state(db, user, guide_key)
    if state is None:
        state = UserGuideState(
            user_id=user.id,
            guide_key=guide_key,
            status=GUIDE_STATUS_IN_PROGRESS,
        )
        db.add(state)
        db.flush()
    return state


def apply_progress(
    db: Session,
    user: User,
    guide_key: str,
    action: str,
    chapter: str | None = None,
    step: int | None = None,
) -> UserGuideState:
    """İlerleme aksiyonunu uygular; commit ÇAĞIRANIN sorumluluğunda değil —
    burada commit edilir (router tek çağrı yapar)."""
    now = datetime.now(timezone.utc)
    state = _get_or_create(db, user, guide_key)
    chapters = CHAPTERS_BY_GUIDE.get(guide_key, [])

    if action == "start":
        # Kapatılmış/bitmiş rehberi yeniden açmak da "start" ile olur.
        state.status = GUIDE_STATUS_IN_PROGRESS
        state.dismissed_at = None
        if chapter:
            state.current_chapter = chapter
        elif not state.current_chapter and chapters:
            state.current_chapter = chapters[0]
    elif action == "watch":
        # Adım sonuna kadar izlendi — KONUM kaydı (kapı değil): oturum düşse de
        # rehber kaldığı adımdan devam eder.
        if not chapter or step is None or step < 0:
            raise ValueError("chapter_required")
        watched = state.steps_watched_map
        lst = set(watched.get(chapter, []))
        lst.add(int(step))
        watched[chapter] = sorted(lst)
        state.set_steps_watched(watched)
        state.current_chapter = chapter
        if state.status != GUIDE_STATUS_COMPLETED:
            state.status = GUIDE_STATUS_IN_PROGRESS
            state.dismissed_at = None
    elif action == "chapter_done":
        if not chapter:
            raise ValueError("chapter_required")
        done = state.chapters_done_list
        if chapter not in done:
            done.append(chapter)
            state.set_chapters_done(done)
        # Sıradaki bölüme ilerlet (bilinen bölüm listesinde ise)
        if chapter in chapters:
            idx = chapters.index(chapter)
            if idx + 1 < len(chapters):
                state.current_chapter = chapters[idx + 1]
            else:
                state.current_chapter = chapter
                state.status = GUIDE_STATUS_COMPLETED
                state.completed_at = now
        if state.status != GUIDE_STATUS_COMPLETED:
            state.status = GUIDE_STATUS_IN_PROGRESS
    elif action == "complete":
        state.status = GUIDE_STATUS_COMPLETED
        state.completed_at = now
    elif action == "dismiss":
        state.status = GUIDE_STATUS_DISMISSED
        state.dismissed_at = now
    elif action == "reset":
        state.status = GUIDE_STATUS_IN_PROGRESS
        state.current_chapter = chapters[0] if chapters else None
        state.set_chapters_done([])
        state.set_steps_watched({})
        state.completed_at = None
        state.dismissed_at = None
        # Taban çizgisi de sıfırlanır: "baştan başlat" = kontroller yeniden
        # gerçek eylem ister (eski eylemler taze sayılmaz).
        state.started_at = now
    else:
        raise ValueError("invalid_action")

    state.updated_at = now
    db.commit()
    db.refresh(state)
    return state


def coach_checklist(
    db: Session, coach: User, since: datetime | None
) -> tuple[dict[str, bool], dict[str, bool]]:
    """Koç rehberi 'şimdi sen yap' kontrol listesi — gerçek veriden.

    İKİ sinyal döner (frontend bölüm sonunda ayrı sunar):
      - fresh:      REHBER BAŞLADIKTAN SONRA (since) yapılan gerçek eylem —
                    "şimdi yaptın, harika" + devam kilidini bu açar.
      - preexisting: rehberden ÖNCE zaten mevcut veri (deneyimli koç) —
                    "zaten yapmışsın" dürüst mesajı + geçişe izin.

    since=None (rehber hiç başlamadı) → fresh tümü False. Sorgular hafif (EXISTS).
    """

    def _exists(stmt) -> bool:
        return db.execute(select(stmt.exists())).scalar() or False

    def _pair(base_stmt, fresh_col) -> tuple[bool, bool]:
        """(fresh, any) — aynı sorgunun since'li ve since'siz hali."""
        any_ = _exists(base_stmt)
        if since is None or not any_:
            return False, any_
        return _exists(base_stmt.where(fresh_col > since)), any_

    book_fresh, book_any = _pair(
        select(Book.id).where(Book.teacher_id == coach.id), Book.created_at
    )
    student_fresh, student_any = _pair(
        select(User.id).where(
            User.teacher_id == coach.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        ),
        User.created_at,
    )
    assign_fresh, assign_any = _pair(
        select(StudentBook.id)
        .join(User, User.id == StudentBook.student_id)
        .where(User.teacher_id == coach.id),
        StudentBook.assigned_at,
    )
    program_fresh, program_any = _pair(
        select(WeeklyProgram.id)
        .join(User, User.id == WeeklyProgram.student_id)
        .where(User.teacher_id == coach.id),
        WeeklyProgram.created_at,
    )
    task_fresh, task_any = _pair(
        select(Task.id)
        .join(User, User.id == Task.student_id)
        .where(User.teacher_id == coach.id),
        Task.created_at,
    )
    pub_fresh, pub_any = _pair(
        select(Task.id)
        .join(User, User.id == Task.student_id)
        .where(User.teacher_id == coach.id, Task.is_draft.is_(False)),
        # Yayın anı esas: taslak rehberden önce kurulmuş olsa bile YAYIN
        # rehber sırasında yapıldıysa taze sayılır.
        Task.published_at,
    )
    exam_fresh, exam_any = _pair(
        select(ExamResult.id).where(ExamResult.created_by_id == coach.id),
        ExamResult.created_at,
    )

    fresh = {
        "kitap-ekle": book_fresh,
        # Atama tazeyse öğrenci eskiden beri var olabilir — beceri kanıtı atamadır.
        "ogrenci-ata": (student_fresh or student_any) and assign_fresh,
        "program-kur": program_fresh or task_fresh,
        "yayinla-duyur": pub_fresh,
        "hafta-takip": pub_fresh or pub_any,
        "deneme-gir": exam_fresh,
    }
    existing = {
        "kitap-ekle": book_any,
        "ogrenci-ata": student_any and assign_any,
        "program-kur": program_any or task_any,
        "yayinla-duyur": pub_any,
        "hafta-takip": pub_any,
        "deneme-gir": exam_any,
    }
    preexisting = {k: (existing[k] and not fresh[k]) for k in fresh}
    return fresh, preexisting


def checklist_for(
    db: Session, user: User, guide_key: str, state: UserGuideState | None
) -> tuple[dict[str, bool], dict[str, bool]]:
    if guide_key == GUIDE_COACH_ONBOARDING:
        since = state.started_at if state is not None else None
        return coach_checklist(db, user, since)
    return {}, {}


def state_payload(state: UserGuideState | None) -> dict:
    """Router serileştirmesi için sade dict (state yoksa not_started)."""
    if state is None:
        return {
            "status": "not_started",
            "current_chapter": None,
            "chapters_done": [],
            "steps_watched": {},
            "completed_at": None,
            "dismissed_at": None,
        }
    return {
        "status": state.status,
        "current_chapter": state.current_chapter,
        "chapters_done": state.chapters_done_list,
        "steps_watched": state.steps_watched_map,
        "completed_at": state.completed_at.isoformat() if state.completed_at else None,
        "dismissed_at": state.dismissed_at.isoformat() if state.dismissed_at else None,
    }
