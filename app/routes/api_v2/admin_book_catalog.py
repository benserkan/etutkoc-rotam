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

Tüm moderasyon işlemleri `BOOK_CATALOG_UPDATE` ile audit'lenir.
Okuma ucu SENKRON def (uzun Gemini çağrısı — exam_import dersi).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
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
