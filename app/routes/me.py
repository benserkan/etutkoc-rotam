"""Stage 10 — Kullanıcının kendi hesabı + KVKK haklarına ilişkin self-serve route'lar.

Tüm rolleri kapsar (super_admin hariç — onun hesabı kurum bağlamında değil,
admin paneli üzerinden yönetilir). Endpointler:

- GET  /me                 → "Hesabım ve Verilerim" sayfası — KVKK haklarım,
                             ihraç ve silme talep butonları
- GET  /me/data-export     → JSON download (anlık üretilir)
- POST /me/data-delete     → Silme talebi aç (30g grace)
- POST /me/data-delete/cancel/{request_id} → Bekleyen talebi iptal et

Yetki: get_current_user. Admin/öğretmen vb. ayırt etmeden tüm authenticated
kullanıcılar kendi verilerine erişir.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import (
    DATA_REQUEST_KIND_LABELS_TR,
    DATA_REQUEST_STATUS_LABELS_TR,
    DataRequestKind,
    DataRequestStatus,
    DataSubjectRequest,
    User,
)
from app.services.kvkk import (
    cancel_request,
    request_deletion,
    request_export,
)
from app.templating import templates


router = APIRouter()


@router.get("/me")
def me_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının kendi hesabı + KVKK hakları."""
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    # Kullanıcının kendi geçmiş talepleri
    requests = (
        db.query(DataSubjectRequest)
        .filter(DataSubjectRequest.target_user_id == user.id)
        .order_by(DataSubjectRequest.created_at.desc())
        .limit(20)
        .all()
    )
    pending_delete = next(
        (
            r for r in requests
            if r.kind == DataRequestKind.DELETE
            and r.status in (DataRequestStatus.PENDING, DataRequestStatus.PROCESSING)
        ),
        None,
    )

    return templates.TemplateResponse(
        "me/account.html",
        {
            "request": request,
            "user": user,
            "requests": requests,
            "pending_delete": pending_delete,
            "kind_labels": DATA_REQUEST_KIND_LABELS_TR,
            "status_labels": DATA_REQUEST_STATUS_LABELS_TR,
        },
    )


@router.get("/me/data-export")
def me_data_export(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının verisini JSON olarak indir.

    Anlık üretilir (DataSubjectRequest kayıt edilir, payload_json snapshot
    yazılır, dosya direkt browser'a indirilir).
    """
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    req = request_export(db, target=user, requester=user)
    filename = f"etutkoc-verim-{user.id}-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return Response(
        content=req.payload_json or "{}",
        media_type="application/json; charset=utf-8",
        headers=headers,
    )


@router.post("/me/data-delete")
def me_data_delete_request(
    request: Request,
    reason: str = Form(""),
    confirm: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hesap silme talebi aç (30g grace period'lu RTBF)."""
    if user is None:
        return RedirectResponse(url="/login", status_code=303)

    if not confirm.strip():
        return RedirectResponse(url="/me?err=confirm", status_code=303)

    request_deletion(
        db, target=user, requester=user,
        reason=(reason or "").strip()[:500] or None,
    )
    return RedirectResponse(url="/me?delete_requested=1", status_code=303)


@router.post("/me/data-delete/cancel/{request_id}")
def me_data_delete_cancel(
    request_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bekleyen silme talebini iptal et."""
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    try:
        result = cancel_request(
            db, request_id=request_id, by_user=user,
            note="Kullanıcı kendisi iptal etti",
        )
    except PermissionError:
        raise HTTPException(status_code=403)
    if result is None:
        raise HTTPException(status_code=404)
    return RedirectResponse(url="/me?delete_cancelled=1", status_code=303)
