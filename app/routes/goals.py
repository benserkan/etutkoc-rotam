"""Stage 11 — Goal tree route'ları.

Üç görünüm:
- /student/goals (öğrenci kendi ağacını görür + sayısal current_value günceller)
- /teacher/students/{id}/goals (öğretmen öğrencinin ağacını görür/düzenler)
- /institution/goals (institution_admin kurum geneli özet)

Yetki:
- Öğrenci yalnız kendi hedeflerine erişir
- Öğretmen kendi öğrencilerine (teacher_id eşleşen) erişir
- Institution admin kendi kurumundaki öğrencilerin ağacına okuma (kurum genel
  düzeyde özet — tek tek detaya inmez, gizlilik kuralı)
- Super admin her şeye erişir (admin paneli üzerinden)
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import (
    get_current_user, get_db,
    require_institution_admin, require_teacher,
)
from app.models import (
    GOAL_KIND_EMOJIS,
    GOAL_KIND_LABELS_TR,
    GOAL_STATUS_LABELS_TR,
    GoalKind,
    GoalStatus,
    StudentGoal,
    User,
    UserRole,
)
from app.services.goals import (
    build_tree,
    create_goal,
    delete_goal,
    institution_goal_summary,
    list_student_goals,
    mark_abandoned,
    mark_achieved,
    student_goal_summary,
    update_goal,
)
from app.services.goals_auto import seed_for_exam_target
from app.templating import templates


router = APIRouter()


# ============================ Yardımcı ============================


def _ensure_teacher_can_access_student(
    db: Session, *, teacher: User, student_id: int,
) -> User:
    """Öğretmenin öğrenciye erişim yetkisini kontrol et."""
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.STUDENT:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    if student.teacher_id != teacher.id:
        raise HTTPException(
            status_code=403,
            detail="Bu öğrenci sizin değil",
        )
    return student


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _parse_float(s: str) -> float | None:
    s = (s or "").strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ============================ Öğrenci görünümü ============================


@router.get("/student/goals")
def student_goals_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Öğrencinin kendi hedef ağacı."""
    if user is None or user.role != UserRole.STUDENT:
        return RedirectResponse(url="/login", status_code=303)

    roots = build_tree(db, student_id=user.id)
    summary = student_goal_summary(db, student_id=user.id)
    return templates.TemplateResponse(
        "goals/student_tree.html",
        {
            "request": request,
            "user": user,
            "roots": roots,
            "summary": summary,
            "kind_labels": GOAL_KIND_LABELS_TR,
            "kind_emojis": GOAL_KIND_EMOJIS,
            "status_labels": GOAL_STATUS_LABELS_TR,
            "is_owner": True,
            "back_url": "/student",
        },
    )


@router.post("/student/goals/{goal_id}/update-progress")
def student_update_progress(
    goal_id: int,
    request: Request,
    current_value: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Öğrenci kendi yaprak hedefin sayısal ilerlemesini günceller."""
    if user is None or user.role != UserRole.STUDENT:
        return RedirectResponse(url="/login", status_code=303)

    goal = db.get(StudentGoal, goal_id)
    if goal is None or goal.student_id != user.id:
        raise HTTPException(status_code=404)

    cv = _parse_float(current_value)
    if cv is not None:
        update_goal(db, goal=goal, current_value=cv)
    return RedirectResponse(url="/student/goals", status_code=303)


# ============================ Öğretmen görünümü ============================


@router.get("/teacher/students/{student_id}/goals")
def teacher_student_goals(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öğretmen öğrencinin hedef ağacını görüntüler ve yönetir."""
    student = _ensure_teacher_can_access_student(
        db, teacher=user, student_id=student_id,
    )
    roots = build_tree(db, student_id=student.id, include_abandoned=True)
    summary = student_goal_summary(db, student_id=student.id)
    return templates.TemplateResponse(
        "goals/teacher_tree.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "roots": roots,
            "summary": summary,
            "kind_labels": GOAL_KIND_LABELS_TR,
            "kind_emojis": GOAL_KIND_EMOJIS,
            "status_labels": GOAL_STATUS_LABELS_TR,
            "kind_options": list(GoalKind),
            "is_owner": False,
            "back_url": f"/teacher/students/{student.id}",
        },
    )


@router.post("/teacher/students/{student_id}/goals/seed")
def teacher_seed_goals(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrencinin sınav hedefinden otomatik subject ağacını türet.

    İdempotent — mevcut EXAM_TARGET kök hedefi varsa hiç dokunmaz.
    """
    student = _ensure_teacher_can_access_student(
        db, teacher=user, student_id=student_id,
    )
    result = seed_for_exam_target(
        db, student=student, created_by_user_id=user.id,
    )
    if result.get("exam_target") is None:
        return RedirectResponse(
            url=f"/teacher/students/{student.id}/goals?err=no_exam_target",
            status_code=303,
        )
    if result.get("skipped_existing"):
        return RedirectResponse(
            url=f"/teacher/students/{student.id}/goals?err=already_seeded",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/teacher/students/{student.id}/goals?ok=seeded",
        status_code=303,
    )


@router.post("/teacher/students/{student_id}/goals/create")
def teacher_create_goal(
    student_id: int,
    request: Request,
    title: str = Form(...),
    kind: str = Form("custom"),
    parent_id: str = Form(""),
    description: str = Form(""),
    target_value: str = Form(""),
    current_value: str = Form(""),
    unit: str = Form(""),
    target_date: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = _ensure_teacher_can_access_student(
        db, teacher=user, student_id=student_id,
    )

    title_clean = (title or "").strip()
    if not title_clean:
        return RedirectResponse(
            url=f"/teacher/students/{student.id}/goals?err=title",
            status_code=303,
        )

    try:
        kind_enum = GoalKind(kind)
    except ValueError:
        kind_enum = GoalKind.CUSTOM

    parent_id_int: int | None = None
    if parent_id and parent_id.strip():
        try:
            parent_id_int = int(parent_id)
        except ValueError:
            parent_id_int = None

    try:
        create_goal(
            db, student=student, kind=kind_enum, title=title_clean,
            parent_id=parent_id_int,
            description=description,
            target_value=_parse_float(target_value),
            current_value=_parse_float(current_value),
            unit=(unit or "").strip() or None,
            target_date=_parse_date(target_date),
            created_by_user_id=user.id,
        )
    except (ValueError, PermissionError) as e:
        return RedirectResponse(
            url=f"/teacher/students/{student.id}/goals?err={e}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/teacher/students/{student.id}/goals?ok=created",
        status_code=303,
    )


@router.post("/teacher/goals/{goal_id}/update")
def teacher_update_goal(
    goal_id: int,
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    target_value: str = Form(""),
    current_value: str = Form(""),
    unit: str = Form(""),
    target_date: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    goal = db.get(StudentGoal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404)
    student = _ensure_teacher_can_access_student(
        db, teacher=user, student_id=goal.student_id,
    )

    update_goal(
        db, goal=goal,
        title=(title.strip() or None),
        description=(description if description else None),
        target_value=_parse_float(target_value),
        current_value=_parse_float(current_value),
        unit=(unit or "").strip() or None,
        target_date=_parse_date(target_date),
    )
    return RedirectResponse(
        url=f"/teacher/students/{student.id}/goals?ok=updated",
        status_code=303,
    )


@router.post("/teacher/goals/{goal_id}/achieve")
def teacher_achieve_goal(
    goal_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    goal = db.get(StudentGoal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404)
    student = _ensure_teacher_can_access_student(
        db, teacher=user, student_id=goal.student_id,
    )
    mark_achieved(db, goal=goal)
    return RedirectResponse(
        url=f"/teacher/students/{student.id}/goals?ok=achieved",
        status_code=303,
    )


@router.post("/teacher/goals/{goal_id}/abandon")
def teacher_abandon_goal(
    goal_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    goal = db.get(StudentGoal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404)
    student = _ensure_teacher_can_access_student(
        db, teacher=user, student_id=goal.student_id,
    )
    mark_abandoned(db, goal=goal)
    return RedirectResponse(
        url=f"/teacher/students/{student.id}/goals?ok=abandoned",
        status_code=303,
    )


@router.post("/teacher/goals/{goal_id}/delete")
def teacher_delete_goal(
    goal_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    goal = db.get(StudentGoal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404)
    student = _ensure_teacher_can_access_student(
        db, teacher=user, student_id=goal.student_id,
    )
    delete_goal(db, goal=goal)
    return RedirectResponse(
        url=f"/teacher/students/{student.id}/goals?ok=deleted",
        status_code=303,
    )


# ============================ Veli görünümü ============================


@router.get("/parent/students/{student_id}/goals")
def parent_student_goals(
    student_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Veli, çocuğunun hedef ağacını yalnız okur."""
    if user is None or user.role != UserRole.PARENT:
        return RedirectResponse(url="/login", status_code=303)

    # Yetki: parent_student_links kontrolü
    from app.models import ParentStudentLink
    link = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.parent_id == user.id,
            ParentStudentLink.student_id == student_id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(status_code=403, detail="Bu öğrenci sizin değil")

    student = db.get(User, student_id)
    if student is None:
        raise HTTPException(status_code=404)

    roots = build_tree(db, student_id=student.id)
    summary = student_goal_summary(db, student_id=student.id)

    return templates.TemplateResponse(
        "goals/parent_view.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "roots": roots,
            "summary": summary,
            "kind_labels": GOAL_KIND_LABELS_TR,
            "kind_emojis": GOAL_KIND_EMOJIS,
            "status_labels": GOAL_STATUS_LABELS_TR,
            "is_owner": False,
            "back_url": f"/parent/students/{student.id}",
        },
    )


# ============================ Kurum görünümü ============================


@router.get("/institution/goals")
def institution_goals_page(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum admin'i için kurum geneli hedef özeti."""
    summary = institution_goal_summary(db, institution_id=user.institution_id)
    return templates.TemplateResponse(
        "goals/institution_summary.html",
        {
            "request": request,
            "user": user,
            "summary": summary,
        },
    )
