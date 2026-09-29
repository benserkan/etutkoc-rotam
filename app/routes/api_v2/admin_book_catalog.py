"""API v2 — Süper admin Ortak Kitap Kataloğu yönetimi.

Endpoint haritası (prefix `/admin/book-catalog`, tümü `_require_super_admin`):
  GET    /                     → AdminCatalogListResponse (durum/arama filtreli + sayımlar)
  GET    /{entry_id}           → CatalogEntryDetail (her durum)
  POST   /read                 → StructureReadResult (okuma motoru — seed aracı, tavansız)
  POST   /                     → MutationResponse[CatalogEntryDetail] (oluştur; publish=True → verified)
  POST   /{entry_id}           → MutationResponse[CatalogEntryDetail] (düzenle; sections replace)
  POST   /{entry_id}/verify    → yayına al (pending/hidden → verified)
  POST   /{entry_id}/hide      → yayından kaldır (geri alınabilir)
  POST   /{entry_id}/delete    → sil (yalnız hiç kullanılmamış; aksi 409 → hide öner)
  POST   /scan-jobs            → tam kitap PDF'i → arka plan tarama işi (≤450 MB)
  GET    /scan-jobs            → son 20 iş (ilerleme + özet)
  GET    /scan-jobs/{job_id}   → iş + sonuç taslağı (bölümler + sağlamlık kapıları)
  POST   /scan-jobs/{job_id}/delete → iş kaydını sil (koşan iş hariç)

Tüm moderasyon işlemleri `BOOK_CATALOG_UPDATE` ile audit'lenir.
Okuma ucu SENKRON def (uzun Gemini çağrısı — exam_import dersi).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import AuditAction, BookType, User
from app.models.book import (
    CATALOG_STATUS_HIDDEN,
    CATALOG_STATUS_PENDING,
    CATALOG_STATUS_VERIFIED,
    CATALOG_STATUSES,
)
from app.routes.api_v2.admin import _require_super_admin
from app.routes.api_v2.library import (
    _catalog_brief,
    _catalog_detail,
    _collect_structure_files,
)
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.library import (
    AdminCatalogCreateBody,
    AdminCatalogListResponse,
    AdminCatalogUpdateBody,
    BookScanJobDetail,
    BookScanJobItem,
    BookScanJobListResponse,
    BookScanResultModel,
    CatalogEntryDetail,
    DeletedRef,
    StructureReadResult,
    StructureReadSection,
    SubjectListResponse,
    SubjectRef,
)
from app.services import book_catalog as catalog_svc
from app.services.audit import log_action

router = APIRouter(prefix="/admin/book-catalog", tags=["v2-admin-book-catalog"])

_INVALIDATE = ["admin:book-catalog"]


def _http_error(e: catalog_svc.CatalogError) -> HTTPException:
    if e.code == "catalog_entry_not_found":
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": e.code, "message": e.message},
        )
    if e.code == "already_in_catalog":
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": e.code,
                "message": e.message,
                "details": {"entry_id": e.entry_id},
            },
        )
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": "validation", "code": e.code, "message": e.message},
    )


def _get_entry_any_status(db: Session, entry_id: int):
    try:
        return catalog_svc.get_catalog_entry(db, entry_id, statuses=tuple(CATALOG_STATUSES))
    except catalog_svc.CatalogError as e:
        raise _http_error(e)


def _audit(db: Session, admin: User, op: str, entry, extra: dict | None = None) -> None:
    details = {"op": op, "name": entry.name, "status": entry.catalog_status}
    if extra:
        details.update(extra)
    log_action(
        db,
        action=AuditAction.BOOK_CATALOG_UPDATE,
        actor_id=admin.id,
        target_type="book_template",
        target_id=entry.id,
        details=details,
        autocommit=False,
    )


@router.get("", response_model=AdminCatalogListResponse)
def admin_catalog_list_v2(
    status_filter: str | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=120),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    rows = catalog_svc.list_entries(db, status=status_filter, q=q)
    counts = catalog_svc.status_counts(db)
    return AdminCatalogListResponse(
        items=[_catalog_brief(db, t) for t in rows],
        total=len(rows),
        verified_count=counts[CATALOG_STATUS_VERIFIED],
        pending_count=counts[CATALOG_STATUS_PENDING],
        hidden_count=counts[CATALOG_STATUS_HIDDEN],
    )


@router.post("/read", response_model=StructureReadResult)
def admin_catalog_read_v2(
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Seed aracı: örnek PDF / içindekiler fotoğrafı → yapı taslağı.

    Günlük tavan YOK (süper admin); ölçüm kaydı yine yazılır.
    """
    from app.services import ai_book_structure as abs_svc

    files_data = _collect_structure_files(files)
    try:
        result = abs_svc.read_structure(files_data)
    except abs_svc.NotATocError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "not_a_toc", "message": str(e)},
        )
    except abs_svc.AIServiceUnavailable as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "upstream_unavailable",
                "code": "ai_provider_error",
                "message": f"AI servisi kullanılamıyor: {e}",
            },
        )
    except abs_svc.AIInvalidResponse as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "upstream_unavailable",
                "code": "ai_provider_error",
                "message": f"AI yanıtı işlenemedi: {e}",
            },
        )
    abs_svc.record_book_read(
        db, user, mode="admin_toc", section_count=len(result["sections"]), autocommit=True,
    )
    return StructureReadResult(
        book_title=result["book_title"],
        publisher=result["publisher"],
        subject_hint=result["subject_hint"],
        grade_hint=result["grade_hint"],
        sections=[StructureReadSection(**s) for s in result["sections"]],
        warnings=result["warnings"],
        read_count=result["read_count"],
        reads_left_today=None,
    )


@router.post("", response_model=MutationResponse[CatalogEntryDetail])
def admin_catalog_create_v2(
    body: AdminCatalogCreateBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        book_type = BookType(body.type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_type", "message": "Geçersiz kitap tipi."},
        )
    try:
        entry = catalog_svc.create_entry(
            db,
            name=body.name,
            publisher=body.publisher,
            book_type=book_type,
            subject_id=body.subject_id,
            target_grade_min=body.target_grade_min,
            target_grade_max=body.target_grade_max,
            target_graduate=bool(body.target_graduate),
            sections=[s.model_dump() for s in (body.sections or [])],
            status=(CATALOG_STATUS_VERIFIED if body.publish else CATALOG_STATUS_PENDING),
            source="admin_seed",
            contributed_by_id=user.id,
            verified_by_id=user.id,
        )
    except catalog_svc.CatalogError as e:
        raise _http_error(e)
    ai_mapped = 0
    if body.ai_map:
        ai_mapped = catalog_svc.ai_map_sections(db, entry)
    _audit(db, user, "create", entry, extra={"ai_mapped": ai_mapped})
    db.commit()
    db.refresh(entry)
    return MutationResponse[CatalogEntryDetail](
        data=_catalog_detail(db, entry), invalidate=_INVALIDATE,
    )


@router.get("/subjects", response_model=SubjectListResponse)
def admin_catalog_subjects_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Katalog kaydına bağlanabilir dersler — YALNIZ builtin (herkese geçerli)."""
    from app.models import Subject

    subjects = (
        db.query(Subject)
        .filter(Subject.is_builtin.is_(True))
        .order_by(Subject.order, Subject.name)
        .all()
    )
    return SubjectListResponse(items=[
        SubjectRef(
            id=s.id,
            name=s.name,
            is_builtin=True,
            curriculum_model=(s.curriculum_model.value if s.curriculum_model else None),
            exam_section=(s.exam_section.value if s.exam_section else None),
            min_grade_level=s.min_grade_level,
            max_grade_level=s.max_grade_level,
            available_for_graduate=bool(s.available_for_graduate),
        )
        for s in subjects
    ])


# =============================================================================
# Tam kitap tarama işleri (arka plan) — /{entry_id} rotalarından ÖNCE
# =============================================================================


def _scan_job_item(db: Session, job, *, with_result: bool = False):
    from app.models.book_scan_job import JOB_STATUS_LABELS_TR
    from app.services import book_scan_jobs as jobs_svc

    creator = db.get(User, job.created_by_id) if job.created_by_id else None
    res = jobs_svc.job_result(job)
    data = dict(
        id=job.id,
        filename=job.filename,
        file_size=job.file_size,
        page_count=job.page_count,
        status=job.status,
        status_label=JOB_STATUS_LABELS_TR.get(job.status, job.status),
        progress=job.progress,
        stage=job.stage,
        error=job.error,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_by_name=creator.full_name if creator else None,
        section_count=len(res["sections"]) if res else None,
        total_tests=res.get("total_tests") if res else None,
        needs_review=res.get("needs_review") if res else None,
        book_title=res.get("book_title") if res else None,
    )
    if with_result:
        return BookScanJobDetail(
            **data, result=BookScanResultModel(**{k: v for k, v in res.items() if k != "scan_debug"})
            if res else None,
        )
    return BookScanJobItem(**data)


def _scan_error(e) -> HTTPException:
    return HTTPException(
        status_code=e.http,
        detail={"error": "validation" if e.http == 422 else "conflict", "code": e.code,
                "message": e.message},
    )


@router.post("/scan-jobs", response_model=MutationResponse[BookScanJobItem])
def admin_scan_job_create_v2(
    file: UploadFile = File(...),
    toc_pages: int = Form(12),
    page_offset: int | None = Form(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Tam kitap PDF'i → arka plan tarama işi. Yanıt HEMEN döner; ilerleme
    GET /scan-jobs ile izlenir. Sonuç taslaktır — kataloğa admin kaydeder."""
    from app.services import book_scan_jobs as jobs_svc

    if (file.content_type or "").lower() not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "not_pdf", "message": "Yalnız PDF yüklenebilir."},
        )
    try:
        job = jobs_svc.create_job(
            db, user.id, fileobj=file.file, filename=file.filename or "kitap.pdf",
            toc_pages=toc_pages, page_offset=page_offset,
        )
    except jobs_svc.ScanJobError as e:
        raise _scan_error(e)
    return MutationResponse(
        data=_scan_job_item(db, job), invalidate=["admin:book-catalog:scan-jobs"],
    )


@router.get("/scan-jobs", response_model=BookScanJobListResponse)
def admin_scan_job_list_v2(
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services import book_scan_jobs as jobs_svc

    return BookScanJobListResponse(items=[_scan_job_item(db, j) for j in jobs_svc.list_jobs(db)])


@router.get("/scan-jobs/{job_id}", response_model=BookScanJobDetail)
def admin_scan_job_detail_v2(
    job_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    from app.models.book_scan_job import BookScanJob

    job = db.get(BookScanJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "scan_job_not_found", "message": "İş bulunamadı."},
        )
    return _scan_job_item(db, job, with_result=True)


@router.post("/scan-jobs/{job_id}/delete", response_model=MutationResponse[DeletedRef])
def admin_scan_job_delete_v2(
    job_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    from app.models.book_scan_job import BookScanJob
    from app.services import book_scan_jobs as jobs_svc

    job = db.get(BookScanJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "scan_job_not_found", "message": "İş bulunamadı."},
        )
    try:
        jobs_svc.delete_job(db, job)
    except jobs_svc.ScanJobError as e:
        raise _scan_error(e)
    return MutationResponse(data=DeletedRef(deleted=True, id=job_id), invalidate=["admin:book-catalog:scan-jobs"])


@router.get("/{entry_id}", response_model=CatalogEntryDetail)
def admin_catalog_detail_v2(
    entry_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    entry = _get_entry_any_status(db, entry_id)
    return _catalog_detail(db, entry)


@router.post("/{entry_id}", response_model=MutationResponse[CatalogEntryDetail])
def admin_catalog_update_v2(
    entry_id: int,
    body: AdminCatalogUpdateBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    entry = _get_entry_any_status(db, entry_id)
    try:
        book_type = BookType(body.type) if body.type is not None else None
        catalog_svc.update_entry(
            db,
            entry,
            name=body.name,
            publisher=body.publisher,
            book_type=book_type,
            subject_id=body.subject_id,
            target_grade_min=body.target_grade_min,
            target_grade_max=body.target_grade_max,
            target_graduate=body.target_graduate,
            sections=(
                [s.model_dump() for s in body.sections]
                if body.sections is not None
                else None
            ),
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "validation", "code": "invalid_type", "message": "Geçersiz kitap tipi."},
        )
    except catalog_svc.CatalogError as e:
        raise _http_error(e)
    if body.ai_map and body.sections is not None:
        # Sections REPLACE edildi → ilişki koleksiyonu bayat olabilir (silinen
        # eski satırları gösterir, AI boşları göremez — 2026-08-11 bug'ı).
        # Taze yüklet, sonra eşle.
        db.flush()
        db.expire(entry, ["sections"])
        catalog_svc.ai_map_sections(db, entry)
    _audit(db, user, "update", entry)
    db.commit()
    db.refresh(entry)
    return MutationResponse[CatalogEntryDetail](
        data=_catalog_detail(db, entry), invalidate=_INVALIDATE,
    )


@router.post("/{entry_id}/verify", response_model=MutationResponse[CatalogEntryDetail])
def admin_catalog_verify_v2(
    entry_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Pending/hidden → verified (yayında; koçlar arayıp kullanabilir)."""
    entry = _get_entry_any_status(db, entry_id)
    catalog_svc.set_status(entry, CATALOG_STATUS_VERIFIED, admin_id=user.id)
    _audit(db, user, "verify", entry)
    db.commit()
    db.refresh(entry)
    return MutationResponse[CatalogEntryDetail](
        data=_catalog_detail(db, entry), invalidate=_INVALIDATE,
    )


@router.post("/{entry_id}/hide", response_model=MutationResponse[CatalogEntryDetail])
def admin_catalog_hide_v2(
    entry_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    """Yayından kaldır (geri alınabilir). Koçların mevcut kitapları ETKİLENMEZ
    (kopya bağımsız) — yalnız yeni kullanım durur."""
    entry = _get_entry_any_status(db, entry_id)
    catalog_svc.set_status(entry, CATALOG_STATUS_HIDDEN)
    _audit(db, user, "hide", entry)
    db.commit()
    db.refresh(entry)
    return MutationResponse[CatalogEntryDetail](
        data=_catalog_detail(db, entry), invalidate=_INVALIDATE,
    )


@router.post("/{entry_id}/delete", response_model=MutationResponse[DeletedRef])
def admin_catalog_delete_v2(
    entry_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    entry = _get_entry_any_status(db, entry_id)
    if (entry.usage_count or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "conflict",
                "code": "entry_in_use",
                "message": "Bu kayıt koçlar tarafından kullanılmış — silmek yerine yayından kaldırın.",
            },
        )
    _audit(db, user, "delete", entry)
    db.delete(entry)
    db.commit()
    return MutationResponse[DeletedRef](
        data=DeletedRef(deleted=True, id=entry_id), invalidate=_INVALIDATE,
    )
