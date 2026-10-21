"""Öğrenci "Gelişim" sayfası uçları (2026-10-21).

Koçun öğrenci detayındaki göstergelerin öğrenciye görünen hâli — hesap koç ekranıyla AYNI
servislerden (build_student_analytics + build_weekly_progress), sayılar iki yüzde birebir.
Koça yönelik parçalar (uyarı kartları, "Seansa ekle" önlemleri) öğrenciye gönderilmez.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User
from app.routes.api_v2.schemas.teacher import TeacherStudentAnalyticsResponse
from app.routes.api_v2.student import _require_student
from app.routes.api_v2.weekly_progress import WeeklyProgressResponse

router = APIRouter(prefix="/student", tags=["v2-student-progress"])


@router.get("/analytics", response_model=TeacherStudentAnalyticsResponse)
def student_analytics(user: User = Depends(_require_student), db: Session = Depends(get_db)):
    from app.routes.api_v2.teacher import build_student_analytics

    out = build_student_analytics(db, user, user.teacher_id)
    out.warnings = []  # koç dili ("öğrenciyle konuş") — öğrenci görmez
    return out


@router.get("/weekly-progress", response_model=WeeklyProgressResponse)
def student_weekly_progress(user: User = Depends(_require_student), db: Session = Depends(get_db)):
    from app.services.weekly_progress import build_weekly_progress

    data = build_weekly_progress(db, user)
    data["actions"] = []  # koçun "Seansa ekle" önlemleri
    return data


# ---------------------------------------------------------------- PDF bağlantısı (mobil)
#
# Mobil uygulama PDF üretemez: öğrenci "PDF" dediğinde 15 dk geçerli imzalı bir bağlantı alır;
# bağlantı telefonun tarayıcısında/PDF görüntüleyicisinde açılır (paylaş → WhatsApp, kaydet).
# Bağlantı yalnız o öğrencinin o çıktısını üretir; süresi dolunca 410.

import jwt as _jwt  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app.config import settings  # noqa: E402

PDF_LINK_MINUTES = 15
_PDF_TYP = "student_pdf"


class PdfLinkBody(BaseModel):
    kind: str = Field(pattern="^(week|day|exams)$")
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class PdfLinkOut(BaseModel):
    url: str
    expires_in_minutes: int


@router.post("/pdf-link", response_model=PdfLinkOut)
def student_pdf_link(body: PdfLinkBody, user: User = Depends(_require_student)):
    exp = datetime.now(timezone.utc) + timedelta(minutes=PDF_LINK_MINUTES)
    token = _jwt.encode({"sub": str(user.id), "typ": _PDF_TYP, "k": body.kind, "d": body.date, "exp": exp},
                        settings.session_secret, algorithm="HS256")
    return PdfLinkOut(url=f"/api/v2/pdf/{token}", expires_in_minutes=PDF_LINK_MINUTES)


pdf_router = APIRouter(prefix="/pdf", tags=["v2-student-progress"])


@pdf_router.get("/{token}")
def student_pdf(token: str, db: Session = Depends(get_db)):
    from app.services.program_pdf import PdfUnavailable, build_pdf

    try:
        data = _jwt.decode(token, settings.session_secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(410, detail={"code": "link_expired", "message": "Bağlantının süresi doldu; uygulamadan yeniden aç."})
    except _jwt.PyJWTError:
        raise HTTPException(404, detail={"code": "not_found", "message": "Bağlantı geçersiz."})
    if data.get("typ") != _PDF_TYP:
        raise HTTPException(404, detail={"code": "not_found", "message": "Bağlantı geçersiz."})
    user = db.get(User, int(data["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(404, detail={"code": "not_found", "message": "Bağlantı geçersiz."})
    try:
        pdf, name = build_pdf(db, user, data.get("k"), data.get("d"))
    except PdfUnavailable:
        raise HTTPException(503, detail={"code": "pdf_unavailable", "message": "PDF şu an üretilemiyor."})
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{name}"', "Cache-Control": "no-store"})
