"""API v2 — CSV import (preview → commit) + export (Dalga 3 Paket 10).

Endpoint haritası:
  POST /teacher/csv/import/students/preview      → CsvPreviewResponse
  POST /teacher/csv/import/students/commit       → MutationResponse[CsvCommitResult]
  GET  /teacher/csv/import/students/template     → text/csv (örnek şablon)
  GET  /teacher/csv/export/students              → text/csv (filtrelenmiş)
  GET  /teacher/csv/export/program?student_id=N  → text/csv (öğrenci haftalık)

Tasarım:
  - Preview JSON döndürür; commit önizleme metnini ALAN TARAFINDAN TEKRAR parse
    eder (tamper koruması) ve `bulk_create_students` ile yeniden uygular.
  - Export'lar `text/csv; charset=utf-8` + BOM (Excel TR uyumu).
  - Cross-tenant 404: sadece öğretmenin kendi öğrencileri export edilir.
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import (
    Task,
    TaskBookItem,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.academic import (
    CsvCommitBody,
    CsvCommitResult,
    CsvCreatedStudent,
    CsvParsedRow,
    CsvPreviewResponse,
)
from app.routes.api_v2.schemas.common import MutationResponse
from app.services.csv_import import (
    ParsedStudent,
    bulk_create_students,
    parse_students_csv,
)


router = APIRouter(prefix="/teacher/csv", tags=["v2-teacher-csv"])


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


def _adapt_parsed_row(p: ParsedStudent) -> CsvParsedRow:
    return CsvParsedRow(
        row_num=p.row_num,
        full_name=p.full_name,
        email=p.email,
        grade_level=p.grade_level,
        track=p.track.value if p.track else None,
        is_graduate=bool(p.is_graduate),
        graduate_mode=p.graduate_mode.value if p.graduate_mode else None,
        is_valid=p.is_valid,
        errors=list(p.errors),
        warnings=list(p.warnings),
        raw=dict(p.raw),
    )


# =============================================================================
# CSV import — template + preview + commit
# =============================================================================


@router.get("/import/students/template")
def import_template(user: User = Depends(_require_teacher)) -> Response:
    sample = (
        "full_name,email,grade_level,track,is_graduate,graduate_mode\n"
        "Ali Veli,ali.veli@example.com,8,,,\n"
        "Ayşe Yılmaz,ayse.yilmaz@example.com,11,sayisal,,\n"
        "Mehmet Demir,mehmet@example.com,12,ea,,\n"
        "Mezun Ogrenci,mezun@example.com,,sozel,evet,dershane\n"
    )
    body = "﻿" + sample
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                'attachment; filename="ogrenci_import_sablon.csv"',
        },
    )


@router.post("/import/students/preview", response_model=CsvPreviewResponse)
def import_preview(
    body: CsvCommitBody,
    user: User = Depends(_require_teacher),
) -> CsvPreviewResponse:
    parse_result = parse_students_csv(body.csv_text or "")
    return CsvPreviewResponse(
        rows=[_adapt_parsed_row(r) for r in parse_result.rows],
        valid_count=parse_result.valid_count,
        invalid_count=parse_result.invalid_count,
        header_errors=list(parse_result.header_errors),
        total_rows=len(parse_result.rows),
    )


@router.post(
    "/import/students/commit",
    response_model=MutationResponse[CsvCommitResult],
)
def import_commit(
    body: CsvCommitBody,
    request: Request,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[CsvCommitResult]:
    parse_result = parse_students_csv(body.csv_text or "")
    if parse_result.has_fatal_error:
        return MutationResponse[CsvCommitResult](
            data=CsvCommitResult(
                created=[],
                skipped_existing_email=[],
                skipped_invalid=[],
                created_count=0,
                skipped_count=0,
                header_errors=list(parse_result.header_errors),
            ),
            invalidate=[f"teacher:{user.id}:students"],
        )

    valid_rows = [r for r in parse_result.rows if r.is_valid]

    # Kurum kuotası — Jinja akışıyla aynı
    header_errors: list[str] = list(parse_result.header_errors)
    if user.institution_id is not None and user.institution is not None and valid_rows:
        from app.services.quotas import QuotaExceeded, check_quota_for_create
        try:
            check_quota_for_create(
                db, institution=user.institution, quota_key="students",
                extra_count=len(valid_rows),
            )
        except QuotaExceeded as e:
            header_errors.append(f"Kuota: {e.message}")
            return MutationResponse[CsvCommitResult](
                data=CsvCommitResult(
                    created=[],
                    skipped_existing_email=[],
                    skipped_invalid=[_adapt_parsed_row(r) for r in valid_rows],
                    created_count=0,
                    skipped_count=len(valid_rows),
                    header_errors=header_errors,
                ),
                invalidate=[f"teacher:{user.id}:students"],
            )

    bulk_result = bulk_create_students(
        db, teacher=user, parsed_rows=valid_rows, request=request,
    )

    # bulk_create_students User'a id verir; eşleme için email→id ihtiyacımız var
    created_emails = {c.email for c in bulk_result.created}
    created_ids: dict[str, int] = {}
    if created_emails:
        for u in (
            db.query(User)
            .filter(User.email.in_(created_emails))
            .all()
        ):
            created_ids[u.email] = u.id

    created_dtos = [
        CsvCreatedStudent(
            row_num=c.row_num,
            student_id=created_ids.get(c.email, 0),
            full_name=c.full_name,
            email=c.email,
            grade_label=c.grade_label,
            temp_password=c.temp_password,
        )
        for c in bulk_result.created
    ]
    return MutationResponse[CsvCommitResult](
        data=CsvCommitResult(
            created=created_dtos,
            skipped_existing_email=[
                _adapt_parsed_row(p) for p in bulk_result.skipped_existing_email
            ],
            skipped_invalid=[
                _adapt_parsed_row(p) for p in bulk_result.skipped_invalid
            ],
            created_count=bulk_result.created_count,
            skipped_count=bulk_result.skipped_count,
            header_errors=header_errors,
        ),
        invalidate=[f"teacher:{user.id}:students"],
    )


# =============================================================================
# CSV export — students + program (haftalık)
# =============================================================================


def _csv_response(rows: list[list[str]], filename: str) -> Response:
    buf = io.StringIO()
    buf.write("﻿")  # BOM
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow(r)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="{quote(filename)}"',
        },
    )


@router.get("/export/students")
def export_students(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
    grade_level: int | None = Query(None, ge=1, le=12),
    is_graduate: bool | None = None,
    q: str | None = None,
) -> Response:
    qry = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
    )
    if grade_level is not None:
        qry = qry.filter(User.grade_level == grade_level)
    if is_graduate is True:
        qry = qry.filter(User.is_graduate.is_(True))
    elif is_graduate is False:
        qry = qry.filter(User.is_graduate.is_(False))
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(
            (User.full_name.ilike(like)) | (User.email.ilike(like)),
        )
    students = qry.order_by(User.full_name).all()

    rows: list[list[str]] = [[
        "id", "full_name", "email", "grade_level", "is_graduate",
        "track", "graduate_mode", "academic_year",
    ]]
    for s in students:
        rows.append([
            str(s.id),
            s.full_name,
            s.email,
            str(s.grade_level) if s.grade_level is not None else "",
            "evet" if s.is_graduate else "hayir",
            s.track.value if s.track else "",
            s.graduate_mode.value if s.graduate_mode else "",
            s.academic_year.name if s.academic_year else "",
        ])
    return _csv_response(rows, "ogrenciler.csv")


@router.get("/export/program")
def export_program(
    student_id: int = Query(..., ge=1),
    start: str | None = Query(None, description="ISO YYYY-MM-DD"),
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> Response:
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise _not_found("student_not_found", "Öğrenci bulunamadı.")

    today = date.today()
    if start:
        try:
            start_d = date.fromisoformat(start)
        except ValueError:
            start_d = today
    else:
        start_d = today - timedelta(days=today.weekday())  # Pazartesi
    end_d = start_d + timedelta(days=6)

    tasks = (
        db.query(Task)
        .filter(
            Task.student_id == student.id,
            Task.date >= start_d,
            Task.date <= end_d,
        )
        .order_by(Task.date.asc(), Task.order.asc())
        .all()
    )
    task_ids = [t.id for t in tasks]
    items_by_task: dict[int, list[TaskBookItem]] = {}
    if task_ids:
        for it in (
            db.query(TaskBookItem)
            .filter(TaskBookItem.task_id.in_(task_ids))
            .all()
        ):
            items_by_task.setdefault(it.task_id, []).append(it)

    rows: list[list[str]] = [[
        "date", "task_id", "title", "status", "is_draft",
        "book_id", "section_id", "planned_count", "completed_count",
    ]]
    for t in tasks:
        items = items_by_task.get(t.id, [])
        if not items:
            rows.append([
                t.date.isoformat(), str(t.id), t.title or "",
                t.status.value, "evet" if t.is_draft else "hayir",
                "", "", "", "",
            ])
            continue
        for it in items:
            rows.append([
                t.date.isoformat(), str(t.id), t.title or "",
                t.status.value, "evet" if t.is_draft else "hayir",
                str(it.book_id),
                str(it.book_section_id),
                str(it.planned_count or 0),
                str(it.completed_count or 0),
            ])

    fname = f"program_{student.id}_{start_d.isoformat()}.csv"
    return _csv_response(rows, fname)
