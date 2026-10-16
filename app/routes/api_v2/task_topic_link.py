"""Konusuz test görevleri → müfredat konusu (2026-10-16, Açı Seçkin Kurs saha bulgusu).

  POST /api/v2/teacher/students/{id}/task-topic-suggest   — görev formu: metinden konu + test sayısı önerisi
  GET  /api/v2/teacher/students/{id}/subject-topics       — dersin alt konuları (elle seçim)
  GET  /api/v2/teacher/unlinked-test-tasks                — koçun konusuz test görevleri (+ öneri)
  POST /api/v2/teacher/unlinked-test-tasks/convert        — seçilenleri kaynaksız konu kalemine çevir

Karar koçta: sistem öneri verir, hiçbir görev onaysız dönüştürülmez.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import AuditAction, Task, User, UserRole
from app.models.curriculum import Subject
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.task_topic_link import (
    ConvertBody,
    ConvertResponse,
    ConvertResultItem,
    SubjectTopicsResponse,
    TopicOptionOut,
    TopicSuggestBody,
    TopicSuggestionOut,
    UnlinkedTaskOut,
    UnlinkedTasksResponse,
)
from app.routes.api_v2.teacher import _get_owned_student, _require_teacher
from app.services import task_topic_link as ttl
from app.services.audit import log_action
from app.models.task import TaskStatus

router = APIRouter(prefix="/teacher", tags=["v2-task-topic-link"])


def _opt_out(o: ttl.TopicOption) -> TopicOptionOut:
    return TopicOptionOut(topic_id=o.topic_id, name=o.name, grade_level=o.grade_level,
                          parent_name=o.parent_name, subject_name=o.subject_name)


def _sug_out(s: ttl.TopicSuggestion) -> TopicSuggestionOut:
    return TopicSuggestionOut(
        subject_id=s.subject_id, subject_name=s.subject_name, test_count=s.test_count,
        topic=_opt_out(s.topic) if s.topic else None, confident=s.confident,
        options=[_opt_out(o) for o in s.options], reason=s.reason,
    )


def _student_subject(db: Session, student: User, subject_id: int) -> Subject:
    subj = db.get(Subject, subject_id)
    if subj is None or not (subj.is_builtin or subj.teacher_id == student.teacher_id):
        raise HTTPException(status_code=404, detail={"error": "not_found", "code": "subject_not_found",
                                                     "message": "Ders bulunamadı."})
    return subj


@router.post("/students/{student_id}/task-topic-suggest", response_model=TopicSuggestionOut)
def task_topic_suggest(student_id: int, body: TopicSuggestBody, user: User = Depends(_require_teacher),
                       db: Session = Depends(get_db)) -> TopicSuggestionOut:
    student = _get_owned_student(db, student_id, user.id)
    subj = _student_subject(db, student, body.subject_id)
    return _sug_out(ttl.suggest_topic(db, student, subj, body.text, body.notes))


@router.get("/students/{student_id}/subject-topics", response_model=SubjectTopicsResponse)
def subject_topics(student_id: int, subject_id: int = Query(...), user: User = Depends(_require_teacher),
                   db: Session = Depends(get_db)) -> SubjectTopicsResponse:
    student = _get_owned_student(db, student_id, user.id)
    subj = _student_subject(db, student, subject_id)
    topics, parents, by_id = ttl._subject_topics(db, student, subj.id)
    own = student.grade_level
    leaves = [t for t in topics if t.id not in parents]
    # öğrencinin kendi sınıfı önde, sonra müfredat sırası
    leaves.sort(key=lambda t: (0 if (own is None or t.grade_level in (own, None)) else 1,
                               -(t.grade_level or 0), t.order, t.id))
    return SubjectTopicsResponse(subject_id=subj.id, subject_name=subj.name,
                                 topics=[_opt_out(ttl._opt(t, by_id)) for t in leaves])


def _coach_students(db: Session, coach: User, student_id: int | None) -> list[User]:
    if student_id is not None:
        return [_get_owned_student(db, student_id, coach.id)]
    return (db.query(User)
            .filter(User.teacher_id == coach.id, User.role == UserRole.STUDENT, User.is_active.is_(True))
            .order_by(User.full_name).all())


@router.get("/unlinked-test-tasks", response_model=UnlinkedTasksResponse)
def unlinked_test_tasks(student_id: int | None = Query(default=None), user: User = Depends(_require_teacher),
                        db: Session = Depends(get_db)) -> UnlinkedTasksResponse:
    students = _coach_students(db, user, student_id)
    rows = ttl.unlinked_test_tasks(db, students)
    items = [
        UnlinkedTaskOut(
            task_id=r.task.id, student_id=r.student.id, student_name=r.student.full_name,
            date=r.task.date.isoformat(), title=r.task.title, notes=r.task.notes,
            status=r.task.status.value, is_draft=bool(r.task.is_draft),
            subject_id=r.subject.id if r.subject else None,
            subject_name=r.subject.name if r.subject else None,
            suggestion=_sug_out(r.suggestion),
        )
        for r in rows
    ]
    return UnlinkedTasksResponse(
        total=len(items),
        completed=sum(1 for r in rows if r.task.status == TaskStatus.COMPLETED),
        students=len({r.student.id for r in rows}),
        items=items,
    )


@router.post("/unlinked-test-tasks/convert", response_model=MutationResponse[ConvertResponse])
def convert_unlinked(body: ConvertBody, request: Request, user: User = Depends(_require_teacher),
                     db: Session = Depends(get_db)) -> MutationResponse[ConvertResponse]:
    results: list[ConvertResultItem] = []
    touched: set[int] = set()
    for it in body.items:
        task = db.get(Task, it.task_id)
        student = db.get(User, task.student_id) if task else None
        if task is None or student is None or student.teacher_id != user.id:
            results.append(ConvertResultItem(task_id=it.task_id, ok=False, code="task_not_found",
                                             message="Görev bulunamadı."))
            continue
        try:
            with db.begin_nested():
                ttl.convert_task(db, task, student, it.topic_id, it.planned_count)
        except ttl.LinkError as e:
            results.append(ConvertResultItem(task_id=it.task_id, ok=False, code=e.code, message=e.message))
            continue
        touched.add(student.id)
        results.append(ConvertResultItem(task_id=it.task_id, ok=True))
    converted = sum(1 for r in results if r.ok)
    if converted:
        log_action(db, action=AuditAction.USER_UPDATE, actor_id=user.id, target_type="task",
                   request=request, autocommit=False,
                   details={"op": "task_topic_link", "converted": converted,
                            "task_ids": [r.task_id for r in results if r.ok][:200]})
    db.commit()
    inv = [f"teacher:{user.id}:unlinked-test-tasks", f"teacher:{user.id}:dashboard"]
    for sid in touched:
        inv += [f"teacher:{user.id}:students:{sid}", f"student:{sid}"]
    return MutationResponse(
        data=ConvertResponse(converted=converted, failed=len(results) - converted, results=results),
        invalidate=inv,
    )
