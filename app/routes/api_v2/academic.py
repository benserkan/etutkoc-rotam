"""API v2 — Akademik yıl + faz CRUD + öğrenci atama (Dalga 3 Paket 10).

Endpoint haritası (prefix `/teacher/academic`):
  GET    /years                                    → AcademicYearListResponse
  GET    /years/choices                            → AcademicYearChoicesResponse
  POST   /years                                    → MutationResponse[AcademicYearDetailResponse]
  GET    /years/{id}                               → AcademicYearDetailResponse
  PATCH  /years/{id}                               → MutationResponse[AcademicYearDetailResponse]
  DELETE /years/{id}                               → MutationResponse[DeletedRef]
  POST   /years/{id}/phases                        → MutationResponse[PhaseItem]
  PATCH  /years/{id}/phases/{phase_id}             → MutationResponse[PhaseItem]
  DELETE /years/{id}/phases/{phase_id}             → MutationResponse[DeletedRef]
  PATCH  /years/{id}/students                      → MutationResponse[AcademicYearAssignResult]

Cross-tenant 404: tüm uçlar teacher_id == user.id şartını sürdürür.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    AcademicPhase,
    AcademicPhaseKind,
    AcademicYear,
    User,
    UserRole,
)
from app.models.academic import ExamTarget
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.academic import (
    AcademicYearAssignBody,
    AcademicYearAssignedStudent,
    AcademicYearAssignResult,
    AcademicYearChoicesResponse,
    AcademicYearCreateBody,
    AcademicYearDetailResponse,
    AcademicYearListChoiceItem,
    AcademicYearListItem,
    AcademicYearListResponse,
    AcademicYearPatchBody,
    PhaseCreateBody,
    PhaseItem,
    PhasePatchBody,
)
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.library import DeletedRef


router = APIRouter(prefix="/teacher/academic", tags=["v2-teacher-academic"])


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


def _conflict(code: str, message: str, details: dict | None = None) -> HTTPException:
    detail = {"error": "conflict", "code": code, "message": message}
    if details:
        detail["details"] = details
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _current_academic_start_year(today: date | None = None) -> int:
    if today is None:
        today = date.today()
    return today.year if today.month >= 9 else today.year - 1


def _invalidate(teacher_id: int, year_id: int | None = None) -> list[str]:
    keys = [f"teacher:{teacher_id}:academic:years"]
    if year_id is not None:
        keys.append(f"teacher:{teacher_id}:academic:years:{year_id}")
    return keys


def _get_owned_year(db: Session, year_id: int, teacher_id: int) -> AcademicYear:
    y = (
        db.query(AcademicYear)
        .options(joinedload(AcademicYear.phases))
        .filter(
            AcademicYear.id == year_id,
            AcademicYear.teacher_id == teacher_id,
        )
        .first()
    )
    if not y:
        raise _not_found("year_not_found", "Akademik yıl bulunamadı.")
    return y


def _build_phase_item(p: AcademicPhase) -> PhaseItem:
    return PhaseItem(
        id=p.id,
        name=p.name,
        start_date=p.start_date,
        end_date=p.end_date,
        kind=p.kind.value,
        kind_label=p.kind_label,
        kind_badge=p.kind_badge,
        notes=p.notes,
        capacity_multiplier=p.capacity_multiplier,
        is_no_school=p.is_no_school,
    )


def _build_year_detail(db: Session, y: AcademicYear) -> AcademicYearDetailResponse:
    students = (
        db.query(User)
        .filter(User.academic_year_id == y.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    phases = sorted(y.phases or [], key=lambda p: p.start_date)
    return AcademicYearDetailResponse(
        id=y.id,
        name=y.name,
        start_year=y.start_year,
        exam_target=y.exam_target.value if y.exam_target else "none",
        exam_label=y.exam_label,
        is_active=bool(y.is_active),
        created_at=y.created_at,
        phases=[_build_phase_item(p) for p in phases],
        assigned_students=[
            AcademicYearAssignedStudent(
                student_id=s.id,
                full_name=s.full_name,
                grade_level=s.grade_level,
                is_graduate=bool(s.is_graduate),
            )
            for s in students
        ],
    )


def _build_year_list_item(
    y: AcademicYear, student_counts: dict[int, int],
) -> AcademicYearListItem:
    return AcademicYearListItem(
        id=y.id,
        name=y.name,
        start_year=y.start_year,
        exam_target=y.exam_target.value if y.exam_target else "none",
        exam_label=y.exam_label,
        is_active=bool(y.is_active),
        phase_count=len(y.phases or []),
        student_count=student_counts.get(y.id, 0),
        created_at=y.created_at,
    )


# =============================================================================
# GET /years + /years/choices
# =============================================================================


@router.get("/years", response_model=AcademicYearListResponse)
def list_years(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> AcademicYearListResponse:
    years = (
        db.query(AcademicYear)
        .options(joinedload(AcademicYear.phases))
        .filter(AcademicYear.teacher_id == user.id)
        .order_by(AcademicYear.name.desc())
        .all()
    )
    # Tek query'de tüm yıllar için öğrenci sayısı
    year_ids = [y.id for y in years]
    counts: dict[int, int] = {}
    if year_ids:
        from sqlalchemy import func
        rows = (
            db.query(User.academic_year_id, func.count(User.id))
            .filter(
                User.academic_year_id.in_(year_ids),
                User.role == UserRole.STUDENT,
            )
            .group_by(User.academic_year_id)
            .all()
        )
        counts = {yid: int(c) for yid, c in rows}
    return AcademicYearListResponse(
        items=[_build_year_list_item(y, counts) for y in years],
        current_start_year=_current_academic_start_year(),
    )


@router.get("/years/choices", response_model=AcademicYearChoicesResponse)
def list_year_choices(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> AcademicYearChoicesResponse:
    today = date.today()
    current = _current_academic_start_year(today)
    existing_names = {
        n for (n,) in db.query(AcademicYear.name)
        .filter(AcademicYear.teacher_id == user.id)
        .all()
    }
    items: list[AcademicYearListChoiceItem] = []
    for y in range(current - 2, current + 4):
        name = f"{y}-{y + 1}"
        suffix = ""
        if y == current:
            suffix = " · şu an"
        elif y < current:
            suffix = " · geçmiş"
        elif y == current + 1:
            suffix = " · gelecek yıl"
        items.append(AcademicYearListChoiceItem(
            start_year=y,
            name=name,
            label=name + suffix,
            exists=name in existing_names,
        ))
    return AcademicYearChoicesResponse(items=items, current_start_year=current)


# =============================================================================
# POST /years + GET/PATCH/DELETE /years/{id}
# =============================================================================


@router.post(
    "/years",
    response_model=MutationResponse[AcademicYearDetailResponse],
)
def create_year(
    body: AcademicYearCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[AcademicYearDetailResponse]:
    sy = body.start_year
    if sy < 2020 or sy > 2050:
        raise _validation_error(
            "invalid_start_year", "Yıl 2020-2050 aralığında olmalı.",
        )
    name = f"{sy}-{sy + 1}"
    existing = (
        db.query(AcademicYear)
        .filter(AcademicYear.teacher_id == user.id, AcademicYear.name == name)
        .first()
    )
    if existing:
        if existing.start_year != sy:
            existing.start_year = sy
            db.commit()
        return MutationResponse[AcademicYearDetailResponse](
            data=_build_year_detail(db, existing),
            invalidate=_invalidate(user.id, existing.id),
        )
    y = AcademicYear(
        teacher_id=user.id, name=name, start_year=sy,
        exam_target=ExamTarget.NONE,
    )
    db.add(y)
    db.commit()
    db.refresh(y)
    return MutationResponse[AcademicYearDetailResponse](
        data=_build_year_detail(db, y),
        invalidate=_invalidate(user.id, y.id),
    )


@router.get("/years/{year_id}", response_model=AcademicYearDetailResponse)
def get_year(
    year_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> AcademicYearDetailResponse:
    y = _get_owned_year(db, year_id, user.id)
    return _build_year_detail(db, y)


@router.patch(
    "/years/{year_id}",
    response_model=MutationResponse[AcademicYearDetailResponse],
)
def patch_year(
    year_id: int,
    body: AcademicYearPatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[AcademicYearDetailResponse]:
    y = _get_owned_year(db, year_id, user.id)
    if body.name is not None:
        name_clean = body.name.strip()
        if not name_clean:
            raise _validation_error("name_required", "Yıl adı boş olamaz.")
        # Aynı öğretmenin başka yılında çakışma var mı?
        dup = (
            db.query(AcademicYear)
            .filter(
                AcademicYear.teacher_id == user.id,
                AcademicYear.name == name_clean,
                AcademicYear.id != y.id,
            )
            .first()
        )
        if dup:
            raise _conflict(
                "duplicate_name", f"Bu öğretmende '{name_clean}' adlı yıl zaten var.",
            )
        y.name = name_clean
    if body.start_year is not None:
        if body.start_year < 2020 or body.start_year > 2050:
            raise _validation_error(
                "invalid_start_year", "Yıl 2020-2050 aralığında olmalı.",
            )
        y.start_year = body.start_year
    if body.exam_target is not None:
        try:
            y.exam_target = ExamTarget(body.exam_target)
        except ValueError:
            raise _validation_error(
                "invalid_exam_target", "Hedef sınav geçersiz.",
            )
    if body.is_active is not None:
        y.is_active = bool(body.is_active)
    db.commit()
    db.refresh(y)
    return MutationResponse[AcademicYearDetailResponse](
        data=_build_year_detail(db, y),
        invalidate=_invalidate(user.id, y.id),
    )


@router.delete(
    "/years/{year_id}",
    response_model=MutationResponse[DeletedRef],
)
def delete_year(
    year_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[DeletedRef]:
    y = _get_owned_year(db, year_id, user.id)
    # Öğrenci atanmışsa silme → 409 has_students
    cnt = (
        db.query(User)
        .filter(User.academic_year_id == y.id, User.role == UserRole.STUDENT)
        .count()
    )
    if cnt > 0:
        raise _conflict(
            "has_students",
            f"Bu yıla {cnt} öğrenci atanmış. Önce atamayı kaldırın.",
            {"student_count": cnt},
        )
    deleted_id = y.id
    db.delete(y)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=deleted_id),
        invalidate=_invalidate(user.id, deleted_id),
    )


# =============================================================================
# Phases — POST/PATCH/DELETE /years/{id}/phases[/{phase_id}]
# =============================================================================


def _parse_phase_kind(value: str) -> AcademicPhaseKind:
    try:
        return AcademicPhaseKind(value)
    except ValueError:
        raise _validation_error("invalid_phase_kind", "Dönem tipi geçersiz.")


@router.post(
    "/years/{year_id}/phases",
    response_model=MutationResponse[PhaseItem],
)
def create_phase(
    year_id: int,
    body: PhaseCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[PhaseItem]:
    y = _get_owned_year(db, year_id, user.id)
    name_clean = body.name.strip()
    if not name_clean:
        raise _validation_error("name_required", "Dönem adı zorunlu.")
    if body.start_date > body.end_date:
        raise _validation_error(
            "invalid_date_range",
            "Başlangıç tarihi bitiş tarihinden sonra olamaz.",
        )
    kind_enum = _parse_phase_kind(body.kind)
    p = AcademicPhase(
        academic_year_id=y.id,
        name=name_clean,
        start_date=body.start_date,
        end_date=body.end_date,
        kind=kind_enum,
        notes=(body.notes or "").strip() or None,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return MutationResponse[PhaseItem](
        data=_build_phase_item(p),
        invalidate=_invalidate(user.id, y.id),
    )


def _get_owned_phase(
    db: Session, year_id: int, phase_id: int, teacher_id: int,
) -> AcademicPhase:
    p = (
        db.query(AcademicPhase)
        .join(AcademicYear, AcademicPhase.academic_year_id == AcademicYear.id)
        .filter(
            AcademicPhase.id == phase_id,
            AcademicPhase.academic_year_id == year_id,
            AcademicYear.teacher_id == teacher_id,
        )
        .first()
    )
    if not p:
        raise _not_found("phase_not_found", "Dönem bulunamadı.")
    return p


@router.patch(
    "/years/{year_id}/phases/{phase_id}",
    response_model=MutationResponse[PhaseItem],
)
def patch_phase(
    year_id: int,
    phase_id: int,
    body: PhasePatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[PhaseItem]:
    p = _get_owned_phase(db, year_id, phase_id, user.id)
    if body.name is not None:
        nc = body.name.strip()
        if not nc:
            raise _validation_error("name_required", "Dönem adı boş olamaz.")
        p.name = nc
    if body.start_date is not None:
        p.start_date = body.start_date
    if body.end_date is not None:
        p.end_date = body.end_date
    if p.start_date > p.end_date:
        raise _validation_error(
            "invalid_date_range",
            "Başlangıç tarihi bitiş tarihinden sonra olamaz.",
        )
    if body.kind is not None:
        p.kind = _parse_phase_kind(body.kind)
    if body.notes is not None:
        p.notes = body.notes.strip() or None
    db.commit()
    db.refresh(p)
    return MutationResponse[PhaseItem](
        data=_build_phase_item(p),
        invalidate=_invalidate(user.id, year_id),
    )


@router.delete(
    "/years/{year_id}/phases/{phase_id}",
    response_model=MutationResponse[DeletedRef],
)
def delete_phase(
    year_id: int,
    phase_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[DeletedRef]:
    p = _get_owned_phase(db, year_id, phase_id, user.id)
    deleted_id = p.id
    db.delete(p)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=deleted_id),
        invalidate=_invalidate(user.id, year_id),
    )


# =============================================================================
# PATCH /years/{id}/students — toplu atama diff
# =============================================================================


@router.patch(
    "/years/{year_id}/students",
    response_model=MutationResponse[AcademicYearAssignResult],
)
def assign_students_to_year(
    year_id: int,
    body: AcademicYearAssignBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[AcademicYearAssignResult]:
    y = _get_owned_year(db, year_id, user.id)
    # Cross-tenant safety: sadece öğretmenin kendi öğrencileri
    target_ids: set[int] = set()
    if body.student_ids:
        rows = (
            db.query(User.id)
            .filter(
                User.id.in_(body.student_ids),
                User.teacher_id == user.id,
                User.role == UserRole.STUDENT,
            )
            .all()
        )
        target_ids = {r[0] for r in rows}

    current = (
        db.query(User)
        .filter(
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .all()
    )
    assigned = 0
    removed = 0
    unchanged = 0
    for s in current:
        if s.id in target_ids:
            if s.academic_year_id != y.id:
                s.academic_year_id = y.id
                assigned += 1
            else:
                unchanged += 1
        else:
            if s.academic_year_id == y.id:
                s.academic_year_id = None
                removed += 1
    db.commit()
    return MutationResponse[AcademicYearAssignResult](
        data=AcademicYearAssignResult(
            assigned_count=assigned,
            removed_count=removed,
            unchanged_count=unchanged,
        ),
        invalidate=_invalidate(user.id, year_id) + [
            f"teacher:{user.id}:students",
        ],
    )
