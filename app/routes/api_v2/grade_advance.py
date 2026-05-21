"""API v2 — Sınıf yükseltme (grade advance) + program sıfırlama (Dalga 3 Paket 10).

Endpoint haritası (prefix `/teacher/grade-advance`):
  GET    /preview                                      → GradeAdvancePreviewResponse
  POST   /apply                                        → MutationResponse[GradeAdvanceApplyResult]
  POST   /students/{student_id}/reset-program          → MutationResponse[ResetProgramResult]
                                                          (çift onay: confirm_full_name)

Rezervasyon koruma garantisi (R-024):
  - grade-advance YALNIZ profil alanlarını günceller (grade_level, is_graduate,
    track, graduate_mode, academic_year_id) — Task / TaskBookItem /
    SectionProgress satırlarına dokunmaz.
  - reset-program ayrı endpoint'tir ve çift onay gerektirir. Dönem geçişinden
    sonra "geçen yılki görevleri silmek istiyorum" diyen öğretmen ayrıca
    bu uç noktayı çağırmalı.
"""
from __future__ import annotations

from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    AcademicYear,
    GraduateMode,
    SectionProgress,
    StudentBook,
    SuggestionFeedback,
    Task,
    TaskBookItem,
    Track,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.academic import (
    GradeAdvanceApplyBody,
    GradeAdvanceApplyResult,
    GradeAdvancePreviewItem,
    GradeAdvancePreviewResponse,
    ResetProgramConfirmBody,
    ResetProgramResult,
)
from app.routes.api_v2.schemas.common import MutationResponse


router = APIRouter(
    prefix="/teacher/grade-advance", tags=["v2-teacher-grade-advance"],
)


# =============================================================================
# Auth + helpers
# =============================================================================


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise _auth_error(
            "Bu uç nokta öğretmen hesabı bekler",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "code": code, "message": message},
    )


def _validation_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": "validation", "code": code, "message": message},
    )


def _next_grade(current: int | None, is_graduate: bool) -> tuple[int | None, bool]:
    if is_graduate:
        return (None, True)
    if current is None:
        return (8, False)
    if current >= 12:
        return (None, True)
    if 5 <= current < 12:
        return (current + 1, False)
    return (current, False)


def _has_reservations(db: Session, student_id: int) -> tuple[bool, bool]:
    """(any_reserved, any_completed) — student'ın aktif rezerv/tamam durumu."""
    row = (
        db.query(
            func.coalesce(func.sum(SectionProgress.reserved_count), 0),
            func.coalesce(func.sum(SectionProgress.completed_count), 0),
        )
        .join(StudentBook, SectionProgress.student_book_id == StudentBook.id)
        .filter(StudentBook.student_id == student_id)
        .first()
    )
    if row is None:
        return (False, False)
    return (int(row[0] or 0) > 0, int(row[1] or 0) > 0)


def _suggest_next_year_id(
    db: Session, teacher_id: int, current_year: AcademicYear | None,
) -> tuple[int | None, str | None]:
    """Bir sonraki akademik yıl önerisi (start_year > current)."""
    if current_year is None or current_year.start_year is None:
        return (None, None)
    nxt = (
        db.query(AcademicYear)
        .filter(
            AcademicYear.teacher_id == teacher_id,
            AcademicYear.start_year > current_year.start_year,
        )
        .order_by(AcademicYear.start_year.asc())
        .first()
    )
    if not nxt:
        return (None, None)
    return (nxt.id, nxt.name)


def _invalidate(teacher_id: int, student_id: int | None = None) -> list[str]:
    keys = [
        f"teacher:{teacher_id}:students",
        f"teacher:{teacher_id}:grade-advance",
    ]
    if student_id is not None:
        keys.append(f"teacher:{teacher_id}:students:{student_id}")
    return keys


# =============================================================================
# GET /preview
# =============================================================================


@router.get("/preview", response_model=GradeAdvancePreviewResponse)
def preview(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> GradeAdvancePreviewResponse:
    students = (
        db.query(User)
        .options(joinedload(User.academic_year))
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    items: list[GradeAdvancePreviewItem] = []
    suggested_year_id: int | None = None
    suggested_year_name: str | None = None

    # Çoğunluk öğrencinin AY'ından bir sonraki yılı öner
    cur_year_counter: dict[int, int] = {}
    for s in students:
        if s.academic_year_id:
            cur_year_counter[s.academic_year_id] = (
                cur_year_counter.get(s.academic_year_id, 0) + 1
            )
    if cur_year_counter:
        majority_year_id = max(cur_year_counter, key=lambda k: cur_year_counter[k])
        majority_year = (
            db.query(AcademicYear)
            .filter(AcademicYear.id == majority_year_id)
            .first()
        )
        suggested_year_id, suggested_year_name = _suggest_next_year_id(
            db, user.id, majority_year,
        )

    for s in students:
        suggested_grade, suggested_is_grad = _next_grade(
            s.grade_level, s.is_graduate,
        )
        requires_track = suggested_is_grad or (
            suggested_grade is not None and suggested_grade >= 11
        )
        has_reservations, has_completed = _has_reservations(db, s.id)
        notes: list[str] = []
        if requires_track and s.track is None:
            notes.append("Alan (Sayısal/EA/Sözel/Dil) seçilmesi gerekecek.")
        if suggested_is_grad and s.graduate_mode is None:
            notes.append("Mezun çalışma şekli (tam-zamanlı/dershane) gerekecek.")
        if has_reservations:
            notes.append("Aktif rezervasyon var — taşıma rezervi korur.")
        items.append(GradeAdvancePreviewItem(
            student_id=s.id,
            full_name=s.full_name,
            current_grade_level=s.grade_level,
            current_is_graduate=bool(s.is_graduate),
            current_academic_year_id=s.academic_year_id,
            current_academic_year_name=s.academic_year.name if s.academic_year else None,
            suggested_grade_level=suggested_grade,
            suggested_is_graduate=suggested_is_grad,
            requires_track=requires_track,
            has_track=s.track is not None,
            has_reservations=has_reservations,
            has_completed_progress=has_completed,
            blocker_notes=notes,
        ))

    return GradeAdvancePreviewResponse(
        students=items,
        suggested_year_id=suggested_year_id,
        suggested_year_name=suggested_year_name,
    )


# =============================================================================
# POST /apply
# =============================================================================


def _parse_track(value: str | None) -> Track | None:
    if not value:
        return None
    try:
        return Track(value)
    except ValueError:
        return None


def _parse_graduate_mode(value: str | None) -> GraduateMode | None:
    if not value:
        return None
    try:
        return GraduateMode(value)
    except ValueError:
        return None


@router.post(
    "/apply",
    response_model=MutationResponse[GradeAdvanceApplyResult],
)
def apply(
    body: GradeAdvanceApplyBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[GradeAdvanceApplyResult]:
    if body.target_academic_year_id is not None:
        owns = (
            db.query(AcademicYear)
            .filter(
                AcademicYear.id == body.target_academic_year_id,
                AcademicYear.teacher_id == user.id,
            )
            .first()
        )
        if not owns:
            raise _not_found("year_not_found", "Akademik yıl bulunamadı.")

    target_ids = [it.student_id for it in body.items]
    students_map: dict[int, User] = {}
    if target_ids:
        for s in (
            db.query(User)
            .filter(
                User.id.in_(target_ids),
                User.teacher_id == user.id,
                User.role == UserRole.STUDENT,
            )
            .all()
        ):
            students_map[s.id] = s

    advanced = 0
    skipped_invalid: list[str] = []
    skipped_track_missing: list[str] = []
    preserved_count = 0

    for item in body.items:
        s = students_map.get(item.student_id)
        if not s:
            skipped_invalid.append(f"#{item.student_id}: cross-tenant veya yok")
            continue
        # Grade validation
        new_grade = item.new_grade_level
        new_is_grad = bool(item.new_is_graduate)
        if not new_is_grad and new_grade is not None:
            if new_grade < 1 or new_grade > 12:
                skipped_invalid.append(
                    f"{s.full_name}: sınıf {new_grade} aralık dışı"
                )
                continue
        if new_is_grad and new_grade is not None:
            skipped_invalid.append(
                f"{s.full_name}: mezun + sınıf birlikte verilemez"
            )
            continue

        requires_track = new_is_grad or (new_grade is not None and new_grade >= 11)
        new_track = _parse_track(item.new_track)
        new_mode = _parse_graduate_mode(item.new_graduate_mode)
        if requires_track and new_track is None and s.track is None:
            skipped_track_missing.append(
                f"{s.full_name}: alan zorunlu (11+ / mezun)"
            )
            continue
        if new_is_grad and new_mode is None and s.graduate_mode is None:
            skipped_track_missing.append(
                f"{s.full_name}: mezun çalışma şekli zorunlu"
            )
            continue

        # Rezervasyonu say (sadece raporlama amacıyla — değiştirmiyoruz)
        has_reserved, _ = _has_reservations(db, s.id)
        if has_reserved:
            preserved_count += 1

        # Profil alanlarını uygula — Task/TaskBookItem/SectionProgress'a DOKUNMA
        s.grade_level = new_grade
        s.is_graduate = new_is_grad
        if new_track is not None:
            s.track = new_track
        if new_is_grad and new_mode is not None:
            s.graduate_mode = new_mode
        elif not new_is_grad:
            s.graduate_mode = None
        if body.target_academic_year_id is not None:
            s.academic_year_id = body.target_academic_year_id
        advanced += 1

    db.commit()
    return MutationResponse[GradeAdvanceApplyResult](
        data=GradeAdvanceApplyResult(
            advanced_count=advanced,
            skipped_invalid=skipped_invalid,
            skipped_track_missing=skipped_track_missing,
            preserved_reservations_count=preserved_count,
        ),
        invalidate=_invalidate(user.id),
    )


# =============================================================================
# POST /students/{id}/reset-program — geri dönülemez (çift onay)
# =============================================================================


@router.post(
    "/students/{student_id}/reset-program",
    response_model=MutationResponse[ResetProgramResult],
)
def reset_program(
    student_id: int,
    body: ResetProgramConfirmBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[ResetProgramResult]:
    s = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not s:
        raise _not_found("student_not_found", "Öğrenci bulunamadı.")

    confirm = (body.confirm_full_name or "").strip()
    if confirm != s.full_name:
        raise _validation_error(
            "confirm_name_mismatch",
            "Onay için öğrencinin tam adını birebir yazmalısınız.",
        )

    # Sayım — silmeden önce
    task_ids = [
        tid for (tid,) in
        db.query(Task.id).filter(Task.student_id == s.id).all()
    ]
    deleted_tasks = len(task_ids)
    deleted_items = 0
    if task_ids:
        deleted_items = (
            db.query(TaskBookItem)
            .filter(TaskBookItem.task_id.in_(task_ids))
            .count()
        )
        db.query(TaskBookItem).filter(
            TaskBookItem.task_id.in_(task_ids)
        ).delete(synchronize_session=False)
        db.query(Task).filter(
            Task.id.in_(task_ids)
        ).delete(synchronize_session=False)

    # SectionProgress sıfırlama (kayıt silinmiyor — reserved/completed sıfırlanır)
    sb_ids = [
        sbid for (sbid,) in
        db.query(StudentBook.id).filter(StudentBook.student_id == s.id).all()
    ]
    cleared = 0
    if sb_ids:
        rows = (
            db.query(SectionProgress)
            .filter(SectionProgress.student_book_id.in_(sb_ids))
            .all()
        )
        for sp in rows:
            if sp.reserved_count > 0 or sp.completed_count > 0:
                cleared += 1
            sp.reserved_count = 0
            sp.completed_count = 0

    deleted_fb = (
        db.query(SuggestionFeedback)
        .filter(SuggestionFeedback.student_id == s.id)
        .count()
    )
    if deleted_fb > 0:
        db.query(SuggestionFeedback).filter(
            SuggestionFeedback.student_id == s.id
        ).delete(synchronize_session=False)

    db.commit()

    return MutationResponse[ResetProgramResult](
        data=ResetProgramResult(
            student_id=s.id,
            deleted_tasks=deleted_tasks,
            deleted_task_book_items=deleted_items,
            cleared_reservations=cleared,
            deleted_suggestion_feedback=deleted_fb,
        ),
        invalidate=_invalidate(user.id, s.id) + [
            f"teacher:{user.id}:insights:overview",
            f"teacher:{user.id}:insights:student:{s.id}",
        ],
    )
