from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_student
from app.models import (
    Book,
    BookSection,
    RequestStatus,
    RequestType,
    StudentBook,
    Task,
    TaskRequest,
    User,
)
from app.services.request_service import (
    RequestError,
    create_add_request,
    create_change_request,
    create_question,
    create_remove_request,
    create_replace_request,
    withdraw_request,
)
from app.templating import templates


router = APIRouter(prefix="/student")


def _own_task(db: Session, task_id: int, student: User) -> Task:
    t = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.id == task_id, Task.student_id == student.id)
        .first()
    )
    if not t:
        raise HTTPException(status_code=404)
    return t


@router.post("/tasks/{task_id}/request-change")
def request_change(
    task_id: int,
    proposed_count: int = Form(...),
    message: str = Form(""),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = _own_task(db, task_id, user)
    try:
        create_change_request(db, student=user, task=task, proposed_count=proposed_count, message=message)
        db.commit()
    except RequestError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/student/day?date={task.date}", status_code=303)


@router.post("/tasks/{task_id}/request-replace")
def request_replace(
    task_id: int,
    new_book_id: int = Form(...),
    new_section_id: int = Form(...),
    new_count: int = Form(...),
    message: str = Form(""),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = _own_task(db, task_id, user)
    try:
        create_replace_request(
            db,
            student=user,
            task=task,
            new_book_id=new_book_id,
            new_section_id=new_section_id,
            new_count=new_count,
            message=message,
        )
        db.commit()
    except RequestError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/student/day?date={task.date}", status_code=303)


@router.post("/tasks/{task_id}/request-remove")
def request_remove(
    task_id: int,
    message: str = Form(""),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = _own_task(db, task_id, user)
    try:
        create_remove_request(db, student=user, task=task, message=message)
        db.commit()
    except RequestError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/student/day?date={task.date}", status_code=303)


@router.post("/tasks/{task_id}/question")
def ask_question(
    task_id: int,
    message: str = Form(...),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    task = _own_task(db, task_id, user)
    try:
        create_question(db, student=user, task=task, message=message)
        db.commit()
    except RequestError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/student/day?date={task.date}", status_code=303)


@router.post("/day/{day_iso}/request-add")
def request_add(
    day_iso: str,
    book_id: int = Form(...),
    section_id: int = Form(...),
    proposed_count: int = Form(...),
    message: str = Form(""),
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    try:
        target = date.fromisoformat(day_iso)
    except ValueError:
        raise HTTPException(status_code=400)
    try:
        create_add_request(
            db,
            student=user,
            target_date=target,
            book_id=book_id,
            section_id=section_id,
            proposed_count=proposed_count,
            message=message,
        )
        db.commit()
    except RequestError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/student/day?date={target}", status_code=303)


@router.get("/requests")
def list_requests(
    request: Request,
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    items = (
        db.query(TaskRequest)
        .options(
            joinedload(TaskRequest.task),
            joinedload(TaskRequest.proposed_book),
            joinedload(TaskRequest.proposed_section),
        )
        .filter(TaskRequest.student_id == user.id)
        .order_by(TaskRequest.created_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        "student/requests.html",
        {
            "request": request,
            "user": user,
            "student": user,
            "requests": items,
        },
    )


@router.post("/requests/{req_id}/withdraw")
def withdraw(
    req_id: int,
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    req = db.query(TaskRequest).filter(TaskRequest.id == req_id, TaskRequest.student_id == user.id).first()
    if not req:
        raise HTTPException(status_code=404)
    try:
        withdraw_request(db, student=user, req=req)
        db.commit()
    except RequestError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url="/student/requests", status_code=303)
