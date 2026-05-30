"""P3-P4 — Mesajlaşma API (Click-to-WhatsApp).

Endpoint'ler:
  - GET  /api/v2/messaging/templates  (P4 — rol filtreli aktif şablonlar)
  - GET  /api/v2/messaging/target/{user_id}  (P4 — hedef bilgisi + yetki check)
  - POST /api/v2/messaging/wa-link  (P3 — URL üret + log)

Auth: TEACHER / INSTITUTION_ADMIN / SUPER_ADMIN.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import (
    User,
    UserRole,
    WA_TEMPLATE_CATEGORY_LABELS_TR,
    WhatsAppTemplate,
)
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.messaging import (
    BulkDispatchItemModel,
    BulkGroupOption,
    BulkSendBody,
    BulkSendResponse,
    BulkSkippedItemModel,
    BulkTargetCandidateModel,
    BulkTargetsResponse,
    DispatchStatsResponse,
    WaLinkRequestBody,
    WaLinkResult,
    WaTargetBrief,
    WaTemplateBrief,
    WaTemplateVarBrief,
    WaTemplatesListResponse,
)
from app.services.whatsapp_spam_guard import compute_dispatch_stats
from app.services.whatsapp_bulk_service import (
    GROUP_LABELS_TR,
    GROUPS_BY_ROLE,
    build_bulk_dispatch,
    list_bulk_targets,
)
from app.services.whatsapp_link_service import (
    WaDispatchError,
    build_wa_dispatch,
    can_send_wa_to,
    mask_phone_e164,
)
from app.services.whatsapp_template_service import parse_variables_json


router = APIRouter(prefix="/messaging", tags=["api-v2-messaging"])


def _require_messaging_sender(
    user: User = Depends(get_current_user_v2),
) -> User:
    """Click-to-WA gönderim yetkisi olan roller — TEACHER + INSTITUTION_ADMIN +
    SUPER_ADMIN. Veli/öğrenci gönderemez (P3 kapsamı)."""
    if user.role not in (
        UserRole.TEACHER,
        UserRole.INSTITUTION_ADMIN,
        UserRole.SUPER_ADMIN,
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "code": "role_not_allowed",
                "message": "Bu özellik yalnız öğretmen / yönetici / süper admin hesaplarına açıktır.",
            },
        )
    return user


@router.get("/templates", response_model=WaTemplatesListResponse)
def messaging_templates(
    category: str | None = None,
    sender: User = Depends(_require_messaging_sender),
    db: Session = Depends(get_db),
):
    """Gönderim dialog'u için aktif şablon listesi.

    Rol filtresi: TEACHER → teacher | any; INSTITUTION_ADMIN →
    institution_admin | any; SUPER_ADMIN → hepsi. Bu sayede koç paneli yalnız
    koça yönelik şablonları görür, kurum yön. yalnız kendi seti.
    """
    q = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.is_active == True)  # noqa: E712

    if sender.role == UserRole.TEACHER:
        q = q.filter(WhatsAppTemplate.target_role.in_(["teacher", "any"]))
    elif sender.role == UserRole.INSTITUTION_ADMIN:
        q = q.filter(WhatsAppTemplate.target_role.in_(["institution_admin", "any"]))
    # SUPER_ADMIN: hepsi (filtre yok)

    if category:
        q = q.filter(WhatsAppTemplate.category == category)

    rows = q.order_by(WhatsAppTemplate.category, WhatsAppTemplate.sort_order).all()

    items: list[WaTemplateBrief] = []
    for r in rows:
        defs = parse_variables_json(r.variables_json)
        var_briefs = [
            WaTemplateVarBrief(
                key=str(d.get("key", ""))[:40],
                label_tr=str(d.get("label_tr", "") or d.get("key", ""))[:120],
                example=str(d.get("example", "") or "")[:200],
            )
            for d in defs if isinstance(d, dict)
        ]
        items.append(WaTemplateBrief(
            id=r.id,
            key=r.key,
            category=r.category,
            category_label_tr=WA_TEMPLATE_CATEGORY_LABELS_TR.get(r.category, r.category),
            name_tr=r.name_tr,
            description=r.description or "",
            content_template=r.content_template,
            variables=var_briefs,
            requires_date=bool(r.requires_date),
            allow_bulk=bool(r.allow_bulk),
            allow_freeform_note=bool(r.allow_freeform_note),
        ))

    return WaTemplatesListResponse(
        items=items,
        total=len(items),
        categories=dict(WA_TEMPLATE_CATEGORY_LABELS_TR),
    )


@router.get("/target/{target_user_id}", response_model=WaTargetBrief)
def messaging_target_info(
    target_user_id: int,
    sender: User = Depends(_require_messaging_sender),
    db: Session = Depends(get_db),
):
    """Hedef kullanıcı özeti — dialog header'ı için. Yetki yoksa 404."""
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target or not target.is_active:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "target_not_found",
                    "message": "Hedef kullanıcı bulunamadı."},
        )
    if not can_send_wa_to(db, sender=sender, target=target):
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "target_not_found",
                    "message": "Hedef kullanıcı bulunamadı."},
        )
    verified = target.phone is not None and target.phone_verified_at is not None
    return WaTargetBrief(
        user_id=target.id,
        full_name=target.full_name,
        role=target.role.value,
        phone_masked=(
            mask_phone_e164(target.phone) if verified else "Telefon doğrulanmamış"
        ),
        phone_verified=verified,
    )


@router.post("/wa-link", response_model=WaLinkResult)
def messaging_wa_link(
    body: WaLinkRequestBody,
    sender: User = Depends(_require_messaging_sender),
    db: Session = Depends(get_db),
):
    """Şablon + değişkenler + hedef → wa.me URL'i."""
    try:
        result = build_wa_dispatch(
            db,
            sender=sender,
            template_id=body.template_id,
            target_user_id=body.target_user_id,
            variables=body.variables,
            freeform_note=body.freeform_note,
        )
    except WaDispatchError as e:
        db.rollback()
        raise HTTPException(
            status_code=e.status,
            detail={"error": "invalid", "code": e.code, "message": e.message},
        )

    db.commit()

    return WaLinkResult(
        wa_url=result.wa_url,
        rendered_text=result.rendered_text,
        target_name=result.target_name,
        target_phone_masked=result.target_phone_masked,
        character_count=result.character_count,
        long_text=result.long_text,
        warnings=result.warnings,
        log_id=result.log_id,
    )


# ============================================================================
# P5 — Toplu gönderim endpoint'leri
# ============================================================================


def _available_groups_for(sender: User) -> list[BulkGroupOption]:
    """Sender rolüne göre seçilebilir grup listesi (UI filter chip'leri)."""
    keys = GROUPS_BY_ROLE.get(sender.role, [])
    return [
        BulkGroupOption(key=k, label_tr=GROUP_LABELS_TR.get(k, k))
        for k in keys
    ]


@router.get("/bulk-targets", response_model=BulkTargetsResponse)
def messaging_bulk_targets(
    group: str,
    sender: User = Depends(_require_messaging_sender),
    db: Session = Depends(get_db),
):
    """Sender rolüne göre toplu hedef adayları (telefonu doğrulu + olmayan ayrı).

    Geçersiz grup veya sender'ın yetkisinde olmayan grup → boş liste +
    available_groups dönmesi (frontend hangi grupları gösterebileceğini bilir).
    """
    result = list_bulk_targets(db, sender=sender, group_key=group)
    return BulkTargetsResponse(
        group_key=group,
        group_label_tr=GROUP_LABELS_TR.get(group, group),
        eligible=[
            BulkTargetCandidateModel(
                user_id=c.user_id, full_name=c.full_name, role=c.role,
                phone_masked=c.phone_masked, phone_verified=c.phone_verified,
            )
            for c in result.eligible
        ],
        no_phone=[
            BulkTargetCandidateModel(
                user_id=c.user_id, full_name=c.full_name, role=c.role,
                phone_masked=c.phone_masked, phone_verified=c.phone_verified,
            )
            for c in result.no_phone
        ],
        total=result.total,
        available_groups=_available_groups_for(sender),
    )


@router.post("/bulk-link", response_model=BulkSendResponse)
def messaging_bulk_link(
    body: BulkSendBody,
    sender: User = Depends(_require_messaging_sender),
    db: Session = Depends(get_db),
):
    """Bir şablonu birden çok hedefe → URL listesi.

    Sıralı mod: koç UI'da kişi-kişi gönderir (her item için ayrı wa.me URL).
    Broadcast mod: tek metin döner; koç WA Business'ta broadcast list'e
    yapıştırır (items yine her hedef için URL döner ama UI farklı kullanır).
    """
    try:
        result = build_bulk_dispatch(
            db,
            sender=sender,
            template_id=body.template_id,
            target_user_ids=body.target_user_ids,
            variables=body.variables,
            mode=body.mode,
            freeform_note=body.freeform_note,
        )
    except WaDispatchError as e:
        db.rollback()
        raise HTTPException(
            status_code=e.status,
            detail={"error": "invalid", "code": e.code, "message": e.message},
        )

    db.commit()

    return BulkSendResponse(
        mode=result.mode,
        rendered_text=result.rendered_text,
        items=[
            BulkDispatchItemModel(
                target_user_id=it.target_user_id,
                target_name=it.target_name,
                wa_url=it.wa_url,
                phone_masked=it.phone_masked,
            )
            for it in result.items
        ],
        skipped=[
            BulkSkippedItemModel(
                target_user_id=sk.target_user_id,
                target_name=sk.target_name,
                reason=sk.reason,
            )
            for sk in result.skipped
        ],
        total_dispatched=result.total_dispatched,
        total_skipped=len(result.skipped),
        long_text=result.long_text,
        warnings=result.warnings,
    )


# ============================================================================
# P6 — Spam guard (koç görür)
# ============================================================================


@router.get("/dispatch-stats", response_model=DispatchStatsResponse)
def messaging_dispatch_stats(
    sender: User = Depends(_require_messaging_sender),
    db: Session = Depends(get_db),
):
    """Sender'ın bugün ve bu hafta gönderim sayıları + spam uyarı seviyesi.

    Eşikler: <50 ok | 50-99 yogun | 100+ cok_yogun. Engelleme YOK — yalnız
    bilgilendirme (Faz 1 manuel akış, koçun kendi telefonu)."""
    stats = compute_dispatch_stats(db, sender=sender)
    return DispatchStatsResponse(
        today_count=stats.today_count,
        week_count=stats.week_count,
        week_start_iso=stats.week_start_iso,
        warning_level=stats.warning_level,
        warning_message=stats.warning_message,
    )
