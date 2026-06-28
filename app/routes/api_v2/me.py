"""API v2 — /me + KVKK self-serve.

app/routes/me.py (Jinja sürümü) DOKUNULMAZ. Bu modül aynı veriyi JSON döndürür;
service katmanı `app/services/kvkk` çağrıları birebir korunur.

Referans:
  - MIGRATION_INVENTORY.md (me.py satırı)
  - API_CONTRACTS_DRAFT.md §2
  - MIGRATION_RISKS.md R-006 (mutation `invalidate` desenli)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.deps import get_db
from pydantic import BaseModel, Field

from app.models import (
    DATA_REQUEST_KIND_LABELS_TR,
    DATA_REQUEST_STATUS_LABELS_TR,
    PARENT_RELATION_LABELS,
    DataRequestKind,
    DataRequestStatus,
    DataSubjectRequest,
    DevicePushToken,  # noqa: F401 — push token endpoint
    Institution,
    ParentStudentLink,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import (
    get_current_user_v2,
    get_current_user_v2_allow_pwchange,
)
from app.routes.api_v2.schemas.common import MutationResponse, SimpleOk
from app.routes.api_v2.schemas.me import (
    DataDeleteRequestBody,
    DataDeleteResponse,
    DataRequestSummary,
    InstitutionRef,
    KvkkStatus,
    ActiveSessionItem,
    MyAccountResponse,
    MyPhoneInfo,
    ParentLinkRef,
    PasswordChangeBody,
    PasswordChangeResult,
    PhoneMutationResult,
    SessionRevokeResult,
    SessionsResponse,
    StartPhoneVerificationBody,
    TwoFactorCodeBody,
    TwoFactorMutationResult,
    TwoFactorSetupResult,
    TwoFactorStatus,
    UserPublic,
    VerifyPhoneBody,
)
from app.services.kvkk import (
    cancel_request as kvkk_cancel_request,
    request_deletion as kvkk_request_deletion,
    request_export as kvkk_request_export,
)
from app.services.phone_service import (
    PhoneError,
    PhoneSlot,
    delete_phone,
    pending_verification_for,
    save_phone_unverified,
    start_phone_verification,
    verify_phone,
)
from app.services.sms_provider import is_sms_enabled


router = APIRouter(tags=["v2-me"])


# ============================================================================
# Helpers
# ============================================================================


def _to_request_summary(
    req: DataSubjectRequest, *, viewer_id: int
) -> DataRequestSummary:
    """DataSubjectRequest ORM → DataRequestSummary şeması."""
    return DataRequestSummary(
        id=req.id,
        kind=req.kind.value,
        kind_label_tr=DATA_REQUEST_KIND_LABELS_TR.get(req.kind, req.kind.value),
        status=req.status.value,
        status_label_tr=DATA_REQUEST_STATUS_LABELS_TR.get(req.status, req.status.value),
        reason=req.reason,
        created_at=req.created_at,
        process_after=req.process_after,
        processed_at=req.processed_at,
        can_cancel=(
            req.status in (DataRequestStatus.PENDING, DataRequestStatus.PROCESSING)
            and req.target_user_id == viewer_id
        ),
    )


def _build_parent_links(db: Session, user: User) -> list[ParentLinkRef]:
    """Veli ise children, öğrenci ise parents — counterpart adı ile beraber.

    ParentStudentLink modelinin relationship attribute'ları yok (sadece FK).
    Counterpart user'ları ayrı query ile yükler (N+1 kabul edilebilir — tipik
    veli 1-3 çocuk, tipik öğrenci 1-2 veli).
    """
    if user.role == UserRole.PARENT:
        rows = (
            db.query(ParentStudentLink)
            .filter(ParentStudentLink.parent_id == user.id)
            .all()
        )
        counterpart_ids = [r.student_id for r in rows]
    elif user.role == UserRole.STUDENT:
        rows = (
            db.query(ParentStudentLink)
            .filter(ParentStudentLink.student_id == user.id)
            .all()
        )
        counterpart_ids = [r.parent_id for r in rows]
    else:
        return []

    if not counterpart_ids:
        return []

    users = {
        u.id: u for u in db.query(User).filter(User.id.in_(counterpart_ids)).all()
    }
    out: list[ParentLinkRef] = []
    for r in rows:
        counterpart_id = (
            r.student_id if user.role == UserRole.PARENT else r.parent_id
        )
        counterpart = users.get(counterpart_id)
        out.append(
            ParentLinkRef(
                link_id=r.id,
                counterpart_id=counterpart_id,
                counterpart_name=(counterpart.full_name if counterpart else "—"),
                relation=r.relation.value,
                relation_label_tr=PARENT_RELATION_LABELS.get(r.relation, r.relation.value),
                is_primary=r.is_primary,
            )
        )
    return out


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/me", response_model=MyAccountResponse)
def get_me(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Profil + kurum + veli bağları + KVKK durumu + son 20 talep.

    Eşdeğer Jinja: app/routes/me.py:44-81 (me_page). Aynı veri, JSON şeklinde.
    """
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

    institution_ref: InstitutionRef | None = None
    if user.institution_id:
        inst = db.get(Institution, user.institution_id)
        if inst is not None:
            institution_ref = InstitutionRef(
                id=inst.id, name=inst.name, slug=inst.slug,
                has_logo=inst.has_logo,
                logo_url=(f"/api/v2/institution/logo/{inst.id}" if inst.has_logo else None),
            )

    return MyAccountResponse(
        user=UserPublic.from_user(user),
        institution=institution_ref,
        parent_links=_build_parent_links(db, user),
        kvkk_status=KvkkStatus(
            has_pending_delete=pending_delete is not None,
            pending_delete_request_id=pending_delete.id if pending_delete else None,
            pending_delete_scheduled_at=(
                pending_delete.process_after if pending_delete else None
            ),
        ),
        recent_requests=[
            _to_request_summary(r, viewer_id=user.id) for r in requests
        ],
        phone=_build_phone_info(db, user),
    )


# ============================================================================
# P1 — Telefon doğrulama (/me/phone/*) — tüm roller
# ============================================================================


def _is_dev_sms_stub() -> bool:
    """Yalnız GERÇEK dev'de (DEBUG=true) + SMS kapalıyken OTP kodunu UI'a göster.

    Prod'da (DEBUG=false) kod asla yanıta konmaz — eskiden `not is_sms_enabled()`
    olduğu için SMS kapalı prod'da OTP UI'da sızıyordu (soft mod düzeltmesi).
    """
    from app.config import settings
    return bool(settings.debug) and not is_sms_enabled()


def _build_phone_info(db: Session, user: User) -> MyPhoneInfo:
    """User.phone + phone_secondary durumunu UI için topla.

    secondary_slot_available yalnız PARENT için True (UI ikinci kart gösterir).
    """
    dev = _is_dev_sms_stub()
    # Birincil slot
    pv = pending_verification_for(db, user=user, slot=PhoneSlot.PRIMARY)
    info = MyPhoneInfo(
        phone=user.phone,
        phone_verified_at=user.phone_verified_at,
        phone_pending_verify=pv is not None,
        phone_pending_phone=pv.phone if pv else None,
        phone_pending_expires_at=pv.expires_at if pv else None,
        phone_dev_test_code=(pv.code if pv and dev else None),
        secondary_slot_available=(user.role == UserRole.PARENT),
        # Soft mod: SMS doğrulama operasyonel mi? False iken frontend banner'ı
        # gizler + doğrulama formu yerine bilgilendirme gösterir (kullanıcı zorla
        # doğrulamaya itilmez). SMS sağlayıcısı (VatanSMS) açılınca otomatik True.
        verification_available=is_sms_enabled(),
    )
    # İkincil slot (yalnız PARENT için zaten verili anlamlı; bilgi yine doldurulur)
    if user.role == UserRole.PARENT:
        pv2 = pending_verification_for(db, user=user, slot=PhoneSlot.SECONDARY)
        info.phone_secondary = user.phone_secondary
        info.phone_secondary_verified_at = user.phone_secondary_verified_at
        info.phone_secondary_pending_verify = pv2 is not None
        info.phone_secondary_pending_phone = pv2.phone if pv2 else None
        info.phone_secondary_pending_expires_at = pv2.expires_at if pv2 else None
        info.phone_secondary_dev_test_code = (pv2.code if pv2 and dev else None)
    return info


def _phone_error_http(err: PhoneError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": "invalid", "code": err.code, "message": err.message},
    )


def _require_parent_for_secondary(user: User) -> None:
    if user.role != UserRole.PARENT:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "code": "secondary_slot_parent_only",
                "message": "İkinci telefon yalnız veli hesaplarına özeldir.",
            },
        )


# ---- Birincil telefon ----


@router.post("/me/phone/start", response_model=MutationResponse[PhoneMutationResult])
def me_phone_start(
    body: StartPhoneVerificationBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Birincil telefon için OTP başlat — SMS gönderir."""
    try:
        start_phone_verification(db, user=user, phone=body.phone, slot=PhoneSlot.PRIMARY)
    except PhoneError as e:
        db.rollback()
        raise _phone_error_http(e)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="Doğrulama kodu gönderildi.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


@router.post("/me/phone/verify", response_model=MutationResponse[PhoneMutationResult])
def me_phone_verify(
    body: VerifyPhoneBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Birincil telefon doğrulama kodunu kontrol et."""
    try:
        verify_phone(db, user=user, code=body.code, slot=PhoneSlot.PRIMARY)
    except PhoneError as e:
        db.commit()  # attempts artırımını koru
        raise _phone_error_http(e)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="Telefon doğrulandı.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


@router.post("/me/phone/delete", response_model=MutationResponse[PhoneMutationResult])
def me_phone_delete(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Birincil telefonu kaldır."""
    delete_phone(db, user=user, slot=PhoneSlot.PRIMARY)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="Telefon kaldırıldı.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


@router.post("/me/phone/save", response_model=MutationResponse[PhoneMutationResult])
def me_phone_save(
    body: StartPhoneVerificationBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Soft mod: numarayı doğrulamadan kaydet (SMS doğrulama henüz canlı değil).

    SMS doğrulama açıkken (is_sms_enabled) kullanılamaz — o zaman start/verify
    akışı ile kod doğrulanır.
    """
    if is_sms_enabled():
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "code": "verification_required",
                    "message": "SMS doğrulama aktif — lütfen kod ile doğrulayın."},
        )
    try:
        save_phone_unverified(db, user=user, phone=body.phone, slot=PhoneSlot.PRIMARY)
    except PhoneError as e:
        db.rollback()
        raise _phone_error_http(e)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="Telefon numarası kaydedildi.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


# ---- İkincil telefon (yalnız PARENT) ----


@router.post(
    "/me/phone-secondary/start",
    response_model=MutationResponse[PhoneMutationResult],
)
def me_phone_secondary_start(
    body: StartPhoneVerificationBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    _require_parent_for_secondary(user)
    try:
        start_phone_verification(
            db, user=user, phone=body.phone, slot=PhoneSlot.SECONDARY,
        )
    except PhoneError as e:
        db.rollback()
        raise _phone_error_http(e)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="Doğrulama kodu gönderildi.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


@router.post(
    "/me/phone-secondary/verify",
    response_model=MutationResponse[PhoneMutationResult],
)
def me_phone_secondary_verify(
    body: VerifyPhoneBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    _require_parent_for_secondary(user)
    try:
        verify_phone(db, user=user, code=body.code, slot=PhoneSlot.SECONDARY)
    except PhoneError as e:
        db.commit()
        raise _phone_error_http(e)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="İkinci telefon doğrulandı.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


@router.post(
    "/me/phone-secondary/delete",
    response_model=MutationResponse[PhoneMutationResult],
)
def me_phone_secondary_delete(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    _require_parent_for_secondary(user)
    delete_phone(db, user=user, slot=PhoneSlot.SECONDARY)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="İkinci telefon kaldırıldı.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


@router.post(
    "/me/phone-secondary/save",
    response_model=MutationResponse[PhoneMutationResult],
)
def me_phone_secondary_save(
    body: StartPhoneVerificationBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Soft mod: ikinci numarayı doğrulamadan kaydet (yalnız PARENT)."""
    _require_parent_for_secondary(user)
    if is_sms_enabled():
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "code": "verification_required",
                    "message": "SMS doğrulama aktif — lütfen kod ile doğrulayın."},
        )
    try:
        save_phone_unverified(db, user=user, phone=body.phone, slot=PhoneSlot.SECONDARY)
    except PhoneError as e:
        db.rollback()
        raise _phone_error_http(e)
    db.commit()
    return MutationResponse[PhoneMutationResult](
        data=PhoneMutationResult(
            message="İkinci telefon numarası kaydedildi.",
            info=_build_phone_info(db, user),
        ),
        invalidate=["me"],
    )


@router.get("/me/data-export")
def export_my_data(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """KVKK madde 11 — kişisel veri ihracı.

    Eşdeğer Jinja: app/routes/me.py:84-107. Anlık üretilir; DataSubjectRequest
    kayıt edilir (denetim izi). JSON dosyası attachment olarak iner.
    """
    req = kvkk_request_export(db, target=user, requester=user)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"etutkoc-verim-{user.id}-{today}.json"
    return Response(
        content=req.payload_json or "{}",
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/me/data-delete",
    response_model=MutationResponse[DataDeleteResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def request_data_delete(
    body: DataDeleteRequestBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """30 günlük grace period'lu silme talebi (RTBF).

    Eşdeğer Jinja: app/routes/me.py:110-129. İdempotent (kvkk.py:348-361):
    bekleyen talep varsa onu döner.
    """
    if not body.confirm:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "confirmation_required",
                "message": "Silme talebini onaylamanız gerekiyor.",
            },
        )

    reason = (body.reason or "").strip()[:500] or None
    req = kvkk_request_deletion(db, target=user, requester=user, reason=reason)

    return MutationResponse[DataDeleteResponse](
        data=DataDeleteResponse(
            request_id=req.id,
            scheduled_at=req.process_after,
            can_cancel_until=req.process_after,
        ),
        invalidate=["me:kvkk", "me:requests"],
    )


@router.post(
    "/me/data-delete/{request_id}/cancel",
    response_model=MutationResponse[SimpleOk],
)
def cancel_my_delete_request(
    request_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Bekleyen silme talebini iptal et.

    Eşdeğer Jinja: app/routes/me.py:132-151. Yetki kontrolü
    `app/services/kvkk.py:385-420` içinde (kendi talebi + admin yetkileri).
    """
    try:
        result = kvkk_cancel_request(
            db,
            request_id=request_id,
            by_user=user,
            note="Kullanıcı kendisi iptal etti",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "code": "not_owner",
                "message": "Bu talebi iptal etme yetkiniz yok.",
            },
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "code": "request_not_found",
                "message": "Talep bulunamadı.",
            },
        )
    return MutationResponse[SimpleOk](
        data=SimpleOk(message="Silme talebi iptal edildi."),
        invalidate=["me:kvkk", "me:requests"],
    )


# =============================================================================
# Paket 3.5d.2 — Şifre değiştirme
# =============================================================================


@router.post(
    "/me/password-change",
    response_model=MutationResponse[PasswordChangeResult],
)
def change_password(
    body: PasswordChangeBody,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user_v2_allow_pwchange),
    db: Session = Depends(get_db),
):
    """Mevcut şifreyi değiştir. Politika + breach check + lockout korunur.

    Eşdeğer Jinja: app/routes/password.py:54 (password_change_submit).
    Validation kodları:
      - locked: hesap kilitli (423)
      - wrong_current_password: mevcut şifre yanlış (422)
      - password_mismatch: new != confirm (422)
      - password_weak: politika ihlal (422)
      - password_same: yeni == eski (422)
      - password_breached: HaveIBeenPwned sızıntı (422)
    """
    from app.services.auth_security import (
        is_locked,
        lockout_seconds_remaining,
        register_failed_login,
        validate_password_strength,
    )
    from app.services.password_breach import (
        breach_check_message,
        check_password_breach,
    )
    from app.services.security import hash_password, verify_password

    # Demo hesapları (App Store / Play incelemesi) şifrelerini DEĞİŞTİREMEZ —
    # mağaza incelemecisine verilen sabit giriş bilgileri korunmalı.
    if user.is_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "forbidden",
                "code": "demo_account_readonly",
                "message": "Demo hesabının şifresi değiştirilemez.",
            },
        )

    if is_locked(user):
        secs = lockout_seconds_remaining(user)
        mins = max(1, (secs + 59) // 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": "locked",
                "code": "account_locked",
                "message": f"Çok fazla başarısız deneme — hesap {mins} dakika kilitli.",
            },
        )

    # must_change_password=False ise current_password zorunlu
    if not user.must_change_password:
        cp = (body.current_password or "").strip()
        if not cp or not verify_password(cp, user.password_hash):
            register_failed_login(user)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "validation",
                    "code": "wrong_current_password",
                    "message": "Mevcut şifre yanlış.",
                },
            )

    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "password_mismatch",
                "message": "Yeni şifreler birbiriyle eşleşmiyor.",
            },
        )

    policy_err = validate_password_strength(body.new_password, user.role)
    if policy_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "password_weak",
                "message": policy_err,
            },
        )

    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "password_same",
                "message": "Yeni şifre eski şifreyle aynı olamaz.",
            },
        )

    breach_count = check_password_breach(body.new_password)
    if breach_count and breach_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation",
                "code": "password_breached",
                "message": breach_check_message(breach_count),
            },
        )

    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    db.commit()
    db.refresh(user)

    # KRİTİK: Şifre değişimi pwd_stamp'i döndürür → tarayıcının elindeki eski
    # access/refresh token'ları ANINDA geçersizleşir (token_revoke). Yeni cookie
    # basılmazsa kullanıcı bir sonraki istekte 401 alır ve panele giremez
    # (yeni üyenin ilk-giriş + şifre-değiştir akışında /me/account'a düşme bug'ı).
    # Çözüm: değişimden hemen sonra TAZE oturum kur (yeni pwd_stamp'li cookie +
    # yeni ActiveSession). Diğer cihazlardaki oturumlar pwd_stamp ile düşer
    # (güvenlik: şifre değişince başka oturumlar kapanır), bu cihaz devam eder.
    from app.routes.api_v2.auth import _establish_bff_session

    _establish_bff_session(db, user, request, response)

    return MutationResponse[PasswordChangeResult](
        data=PasswordChangeResult(
            must_change_password=False,
            password_changed_at=user.password_changed_at,
            role=user.role.value if hasattr(user.role, "value") else str(user.role),
        ),
        invalidate=["me:account"],
    )


# ============================================================================
# 2FA / TOTP (Dalga 7 P4) — yalnız Süper Admin + Kurum Yöneticisi
# ============================================================================


@router.get("/me/2fa/status", response_model=TwoFactorStatus)
def two_factor_status(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """2FA durumu — frontend kart için."""
    from app.services.totp import can_use_2fa, remaining_backup_codes

    available = can_use_2fa(user)
    enabled = user.two_factor_enabled
    return TwoFactorStatus(
        available=available,
        enabled=enabled,
        pending_setup=bool(user.totp_secret) and not enabled,
        remaining_backup_codes=remaining_backup_codes(db, user=user) if enabled else 0,
    )


@router.post("/me/2fa/setup", response_model=TwoFactorSetupResult)
def two_factor_setup(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Yeni secret + QR + yedek kodlar üret (henüz aktif değil — enable ile aktiflenir).

    Yedek kodların plain hali yalnız BU yanıtta döner; sonra hash'li saklanır."""
    from app.services.totp import can_use_2fa, setup as totp_setup

    if not can_use_2fa(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "two_factor_not_available",
                    "message": "İki faktörlü doğrulama yalnız yönetici rolleri için kullanılabilir."},
        )
    secret, uri, backup_codes = totp_setup(db, user=user)
    return TwoFactorSetupResult(secret=secret, provisioning_uri=uri, backup_codes=backup_codes)


@router.post("/me/2fa/enable", response_model=MutationResponse[TwoFactorMutationResult])
def two_factor_enable(
    body: TwoFactorCodeBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Setup secret'ını doğrula → 2FA'yı aktifleştir."""
    from app.services.totp import can_use_2fa, enable as totp_enable

    if not can_use_2fa(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "two_factor_not_available",
                    "message": "Bu rol için kullanılamaz."},
        )
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid", "code": "two_factor_not_setup",
                    "message": "Önce kurulum yapın."},
        )
    if not totp_enable(db, user=user, code=body.code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "invalid_2fa_code",
                    "message": "Doğrulama kodu hatalı. Authenticator uygulamasındaki güncel kodu girin."},
        )
    return MutationResponse[TwoFactorMutationResult](
        data=TwoFactorMutationResult(message="İki faktörlü doğrulama etkinleştirildi.", enabled=True),
        invalidate=["me:account"],
    )


@router.post("/me/2fa/disable", response_model=MutationResponse[TwoFactorMutationResult])
def two_factor_disable(
    body: TwoFactorCodeBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """2FA'yı kapat — güncel TOTP/yedek kod doğrulaması gerekir."""
    from app.services.totp import disable as totp_disable, verify_login as totp_verify_login

    if not user.two_factor_enabled:
        return MutationResponse[TwoFactorMutationResult](
            data=TwoFactorMutationResult(message="İki faktörlü doğrulama zaten kapalı.", enabled=False),
            invalidate=["me:account"],
        )
    if not totp_verify_login(db, user=user, code=body.code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "invalid_2fa_code",
                    "message": "Kapatmak için geçerli bir doğrulama kodu girin."},
        )
    totp_disable(db, user=user)
    return MutationResponse[TwoFactorMutationResult](
        data=TwoFactorMutationResult(message="İki faktörlü doğrulama kapatıldı.", enabled=False),
        invalidate=["me:account"],
    )


# ============================================================================
# Aktif oturumlar (Dalga 7 P5) — kullanıcının kendi cihazları
# ============================================================================


def _current_session_token(request: Request) -> str | None:
    """Bu isteğin BFF access cookie'sindeki sid (current cihaz işareti)."""
    from app.config import settings
    from app.services.jwt_auth import decode_token
    token = request.cookies.get(settings.auth_cookie_access_name)
    if not token:
        return None
    try:
        return decode_token(token.strip()).session_id
    except Exception:
        return None


@router.get("/me/sessions", response_model=SessionsResponse)
def my_sessions(
    request: Request,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Kullanıcının son 24 saatte aktif (kapatılmamış) oturumları."""
    from datetime import datetime, timedelta, timezone
    from app.models import ActiveSession

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)
    current_sid = _current_session_token(request)
    rows = (
        db.query(ActiveSession)
        .filter(
            ActiveSession.user_id == user.id,
            ActiveSession.terminated_at.is_(None),
            ActiveSession.last_seen_at >= cutoff,
        )
        .order_by(ActiveSession.last_seen_at.desc())
        .all()
    )
    out: list[ActiveSessionItem] = []
    for r in rows:
        ls = r.last_seen_at
        if ls is not None and ls.tzinfo is None:
            ls = ls.replace(tzinfo=timezone.utc)
        idle = int((now - ls).total_seconds()) if ls else 0
        out.append(ActiveSessionItem(
            session_token=r.session_token,
            ip=r.ip,
            user_agent=r.user_agent,
            login_at=r.login_at,
            last_seen_at=r.last_seen_at,
            idle_seconds=max(0, idle),
            is_current=(r.session_token == current_sid),
        ))
    return SessionsResponse(sessions=out)


@router.post(
    "/me/sessions/{session_token}/revoke",
    response_model=MutationResponse[SessionRevokeResult],
)
def revoke_my_session(
    session_token: str,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Kullanıcı kendi bir oturumunu uzaktan kapatır (çalınmış/unutulmuş cihaz).

    Yalnız kendi oturumu — başka kullanıcının token'ı 404 (sahiplik kontrolü)."""
    from app.models import ActiveSession
    from app.services.security_monitor import terminate_session

    row = (
        db.query(ActiveSession)
        .filter(
            ActiveSession.session_token == session_token,
            ActiveSession.user_id == user.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "session_not_found",
                    "message": "Oturum bulunamadı."},
        )
    terminate_session(db, session_token=session_token, reason="self_revoke", by_user_id=user.id)
    return MutationResponse[SessionRevokeResult](
        data=SessionRevokeResult(message="Oturum kapatıldı."),
        invalidate=["me:sessions"],
    )


# --- Mobil push bildirim token'ı (Expo) ---
class PushTokenBody(BaseModel):
    token: str = Field(min_length=1, max_length=255)
    platform: str | None = Field(default=None, max_length=16)


@router.post("/me/push-token", response_model=SimpleOk)
def register_push_token_v2(
    body: PushTokenBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Mobil uygulamanın Expo push token'ını kaydet/güncelle (upsert)."""
    from app.services.push_notifications import register_token

    register_token(db, user_id=user.id, token=body.token, platform=body.platform)
    db.commit()
    return SimpleOk(ok=True)


@router.delete("/me/push-token", response_model=SimpleOk)
def unregister_push_token_v2(
    token: str,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Çıkışta token'ı sil (yalnız kendi token'ı)."""
    from app.services.push_notifications import unregister_token

    unregister_token(db, token=token, user_id=user.id)
    db.commit()
    return SimpleOk(ok=True)
