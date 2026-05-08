from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import Book, BookSet, BookSetItem, User
from app.templating import templates

router = APIRouter(prefix="/teacher/book-sets")


def _get_set(db: Session, set_id: int, teacher_id: int) -> BookSet | None:
    return (
        db.query(BookSet)
        .options(
            joinedload(BookSet.items).joinedload(BookSetItem.book).joinedload(Book.subject)
        )
        .filter(BookSet.id == set_id, BookSet.teacher_id == teacher_id)
        .first()
    )


@router.get("")
def list_sets(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    sets = (
        db.query(BookSet)
        .options(joinedload(BookSet.items))
        .filter(BookSet.teacher_id == user.id)
        .order_by(BookSet.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "teacher/book_sets_list.html",
        {"request": request, "user": user, "sets": sets},
    )


@router.post("")
def create_set(
    name: str = Form(...),
    notes: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    if not name.strip():
        raise HTTPException(status_code=400, detail="Set adı gerekli")
    bs = BookSet(
        teacher_id=user.id,
        name=name.strip(),
        notes=notes.strip() or None,
    )
    db.add(bs)
    db.commit()
    return RedirectResponse(
        url=f"/teacher/book-sets/{bs.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/{set_id}")
def set_detail(
    set_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    bs = _get_set(db, set_id, user.id)
    if not bs:
        raise HTTPException(status_code=404, detail="Set bulunamadı")

    member_book_ids = {it.book_id for it in bs.items}
    library_books = (
        db.query(Book)
        .options(joinedload(Book.subject), joinedload(Book.sections))
        .filter(Book.teacher_id == user.id)
        .order_by(Book.name)
        .all()
    )
    available_by_subject: dict = {}
    for b in library_books:
        if b.id in member_book_ids:
            continue
        available_by_subject.setdefault(b.subject, []).append(b)

    # Sette bulunan kitaplar derslere göre gruplu
    members_by_subject: dict = {}
    for it in bs.items:
        members_by_subject.setdefault(it.book.subject, []).append(it)

    return templates.TemplateResponse(
        "teacher/book_set_detail.html",
        {
            "request": request,
            "user": user,
            "set": bs,
            "members_by_subject": members_by_subject,
            "available_by_subject": available_by_subject,
        },
    )


@router.post("/{set_id}/edit")
def edit_set(
    set_id: int,
    name: str = Form(...),
    notes: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    bs = (
        db.query(BookSet)
        .filter(BookSet.id == set_id, BookSet.teacher_id == user.id)
        .first()
    )
    if not bs:
        raise HTTPException(status_code=404)
    if not name.strip():
        raise HTTPException(status_code=400, detail="Set adı gerekli")
    bs.name = name.strip()
    bs.notes = notes.strip() or None
    db.commit()
    return RedirectResponse(
        url=f"/teacher/book-sets/{set_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{set_id}/books/add")
async def add_books_to_set(
    set_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    bs = (
        db.query(BookSet)
        .filter(BookSet.id == set_id, BookSet.teacher_id == user.id)
        .first()
    )
    if not bs:
        raise HTTPException(status_code=404)

    form = await request.form()
    raw = form.getlist("book_ids")
    selected: set[int] = set()
    for v in raw:
        try:
            selected.add(int(v))
        except (TypeError, ValueError):
            continue
    if not selected:
        return RedirectResponse(
            url=f"/teacher/book-sets/{set_id}", status_code=status.HTTP_303_SEE_OTHER
        )

    valid_book_ids = {
        b.id for b in db.query(Book)
        .filter(Book.teacher_id == user.id, Book.id.in_(selected))
        .all()
    }
    existing_ids = {it.book_id for it in bs.items}
    max_order = max((it.order for it in bs.items), default=-1)
    for bid in valid_book_ids:
        if bid in existing_ids:
            continue
        max_order += 1
        db.add(BookSetItem(set_id=bs.id, book_id=bid, order=max_order))
    db.commit()
    return RedirectResponse(
        url=f"/teacher/book-sets/{set_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{set_id}/books/{book_id}/remove")
def remove_book_from_set(
    set_id: int,
    book_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    item = (
        db.query(BookSetItem)
        .join(BookSet, BookSet.id == BookSetItem.set_id)
        .filter(
            BookSetItem.set_id == set_id,
            BookSetItem.book_id == book_id,
            BookSet.teacher_id == user.id,
        )
        .first()
    )
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(
        url=f"/teacher/book-sets/{set_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{set_id}/delete")
def delete_set(
    set_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    bs = (
        db.query(BookSet)
        .filter(BookSet.id == set_id, BookSet.teacher_id == user.id)
        .first()
    )
    if bs:
        db.delete(bs)
        db.commit()
    return RedirectResponse(
        url="/teacher/book-sets", status_code=status.HTTP_303_SEE_OTHER
    )
