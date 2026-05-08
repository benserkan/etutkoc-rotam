from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import (
    RequestStatus,
    Task,
    TaskRequest,
    User,
)
from app.services.request_service import (
    RequestError,
    approve_request,
    reject_request,
    respond_question,
)
from app.templating import templates


router = APIRouter(prefix="/teacher")


def _own_request(db: Session, req_id: int, teacher: User) -> TaskRequest:
    r = (
        db.query(TaskRequest)
        .options(
            joinedload(TaskRequest.task),
            joinedload(TaskRequest.student),
            joinedload(TaskRequest.proposed_book),
            joinedload(TaskRequest.proposed_section),
        )
        .filter(TaskRequest.id == req_id, TaskRequest.teacher_id == teacher.id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404)
    return r


@router.get("/requests")
def list_requests(
    request: Request,
    only_pending: int = 1,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    q = (
        db.query(TaskRequest)
        .options(
            joinedload(TaskRequest.task),
            joinedload(TaskRequest.student),
            joinedload(TaskRequest.proposed_book),
            joinedload(TaskRequest.proposed_section),
        )
        .filter(TaskRequest.teacher_id == user.id)
    )
    if only_pending:
        q = q.filter(TaskRequest.status == RequestStatus.PENDING)
    items = q.order_by(TaskRequest.created_at.desc()).limit(200).all()

    pending_total = (
        db.query(TaskRequest)
        .filter(TaskRequest.teacher_id == user.id, TaskRequest.status == RequestStatus.PENDING)
        .count()
    )
    return templates.TemplateResponse(
        "teacher/requests.html",
        {
            "request": request,
            "user": user,
            "requests": items,
            "only_pending": bool(only_pending),
            "pending_total": pending_total,
        },
    )


def _redirect_with_error(msg: str) -> RedirectResponse:
    """Hata mesajını URL'ye encode ederek talepler sayfasına geri dön."""
    from urllib.parse import quote
    return RedirectResponse(url=f"/teacher/requests?err={quote(msg)}", status_code=303)


def _redirect_with_ok(msg: str) -> RedirectResponse:
    from urllib.parse import quote
    return RedirectResponse(url=f"/teacher/requests?ok={quote(msg)}", status_code=303)


@router.post("/requests/{req_id}/approve")
def approve(
    req_id: int,
    response: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    req = _own_request(db, req_id, user)
    try:
        approve_request(db, teacher=user, req=req, response=response)
        db.commit()
    except RequestError as e:
        db.rollback()
        return _redirect_with_error(str(e))
    return _redirect_with_ok("Talep onaylandı ve uygulandı.")


@router.post("/requests/{req_id}/reject")
def reject(
    req_id: int,
    response: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    req = _own_request(db, req_id, user)
    try:
        reject_request(db, teacher=user, req=req, response=response)
        db.commit()
    except RequestError as e:
        db.rollback()
        return _redirect_with_error(str(e))
    return _redirect_with_ok("Talep reddedildi.")


@router.post("/requests/{req_id}/respond")
def respond(
    req_id: int,
    response: str = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    req = _own_request(db, req_id, user)
    try:
        respond_question(db, teacher=user, req=req, response=response)
        db.commit()
    except RequestError as e:
        db.rollback()
        return _redirect_with_error(str(e))
    return _redirect_with_ok("Cevap gönderildi.")
