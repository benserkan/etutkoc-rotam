"""P5 — Toplu WhatsApp gönderim servisi.

İki ana sorumluluk:
  1. `list_bulk_targets(sender, group_key)` — sender rolüne göre toplu gönderim
     için aday hedef listesini döndür (telefon doğrulu olanlar + olmayanlar
     ayrı raporlanır)
  2. `build_bulk_dispatch(sender, template, target_user_ids, variables, mode)` —
     verilen hedef listesi için URL'leri toplu üret, telefonu yok/yetkisiz
     olanları skipped listesine düşür, her başarılı için dispatch log yaz

Sade tut: en fazla 200 hedef güvenlik limit. allow_bulk=False şablon → 400.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import (
    ParentStudentLink,
    User,
    UserRole,
    WhatsAppDispatchLog,
    WhatsAppTemplate,
)
from app.services.whatsapp_link_service import (
    LONG_TEXT_THRESHOLD,
    WaDispatchError,
    build_wa_url,
    can_message_phone,
    can_send_wa_to,
    mask_phone_e164,
)
from app.services.whatsapp_template_service import (
    parse_variables_json,
    render_preview,
)


MAX_BULK_TARGETS = 200


# Hedef grup anahtarları — rol bazında geçerli olanlar farklı
GROUP_MY_PARENTS = "my_parents"          # TEACHER → öğrencilerinin tüm velileri
GROUP_MY_STUDENTS = "my_students"        # TEACHER → tüm öğrencileri
GROUP_INST_PARENTS = "inst_parents"      # INSTITUTION_ADMIN → kurum öğrencilerinin velileri
GROUP_INST_TEACHERS = "inst_teachers"    # INSTITUTION_ADMIN → kurum öğretmenleri
GROUP_INST_STUDENTS = "inst_students"    # INSTITUTION_ADMIN → kurum öğrencileri

GROUP_LABELS_TR: dict[str, str] = {
    GROUP_MY_PARENTS: "Tüm velilerim",
    GROUP_MY_STUDENTS: "Tüm öğrencilerim",
    GROUP_INST_PARENTS: "Kurumun tüm velileri",
    GROUP_INST_TEACHERS: "Kurumun tüm öğretmenleri",
    GROUP_INST_STUDENTS: "Kurumun tüm öğrencileri",
}

GROUPS_BY_ROLE: dict[UserRole, list[str]] = {
    UserRole.TEACHER: [GROUP_MY_PARENTS, GROUP_MY_STUDENTS],
    UserRole.INSTITUTION_ADMIN: [
        GROUP_INST_PARENTS,
        GROUP_INST_TEACHERS,
        GROUP_INST_STUDENTS,
    ],
    UserRole.SUPER_ADMIN: [
        GROUP_INST_PARENTS,
        GROUP_INST_TEACHERS,
        GROUP_INST_STUDENTS,
        GROUP_MY_PARENTS,
        GROUP_MY_STUDENTS,
    ],
}


@dataclass
class BulkTargetCandidate:
    user_id: int
    full_name: str
    role: str
    phone_masked: str
    phone_verified: bool
    can_message: bool = False


@dataclass
class BulkTargetsResult:
    """Liste sonucu — telefon doğrulu olanlar + olmayan ayrı."""
    eligible: list[BulkTargetCandidate]     # telefon doğrulu, gönderilebilir
    no_phone: list[BulkTargetCandidate]     # telefonu yok / doğrulanmamış
    total: int


@dataclass
class BulkDispatchItem:
    target_user_id: int
    target_name: str
    wa_url: str
    phone_masked: str


@dataclass
class BulkSkippedItem:
    target_user_id: int
    target_name: str
    reason: str  # "phone_not_verified" | "no_permission"


@dataclass
class BulkDispatchResult:
    mode: str                                  # "sequential" | "broadcast"
    rendered_text: str
    items: list[BulkDispatchItem] = field(default_factory=list)
    skipped: list[BulkSkippedItem] = field(default_factory=list)
    total_dispatched: int = 0
    long_text: bool = False
    warnings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# Hedef listesi
# ----------------------------------------------------------------------


def _candidate_from_user(u: User) -> BulkTargetCandidate:
    verified = u.phone is not None and u.phone_verified_at is not None
    can_msg = can_message_phone(u)
    return BulkTargetCandidate(
        user_id=u.id,
        full_name=u.full_name,
        role=u.role.value,
        phone_masked=(
            mask_phone_e164(u.phone) if u.phone else "—"
        ),
        phone_verified=verified,
        can_message=can_msg,
    )


def list_bulk_targets(
    db: Session, *, sender: User, group_key: str,
) -> BulkTargetsResult:
    """Sender rolüne göre toplu hedef adaylarını döndür.

    Rol-bazlı sızıntı önleme: sender rolüne uygun olmayan group_key → boş liste
    (UI tarafı zaten filtre listesini sender_role'a göre gösterir).
    """
    allowed_groups = GROUPS_BY_ROLE.get(sender.role, [])
    if group_key not in allowed_groups:
        return BulkTargetsResult(eligible=[], no_phone=[], total=0)

    users: list[User] = []

    if group_key == GROUP_MY_STUDENTS and sender.role == UserRole.TEACHER:
        users = (
            db.query(User)
            .filter(
                User.teacher_id == sender.id,
                User.role == UserRole.STUDENT,
                User.is_active == True,  # noqa: E712
            )
            .order_by(User.full_name)
            .all()
        )
    elif group_key == GROUP_MY_PARENTS and sender.role == UserRole.TEACHER:
        # Sender'ın öğrencilerine bağlı tüm aktif veliler (DISTINCT)
        users = (
            db.query(User)
            .join(ParentStudentLink, ParentStudentLink.parent_id == User.id)
            .join(
                # Student-side filter — student.teacher_id == sender.id
                # Aliased User join karmaşıklığı yerine alt-sorgu:
                # student_ids = db.query(...)
                User.__table__.alias("student_alias"),
                # gerçekte SQLAlchemy join'i nesneyle kuracağız; alt-sorguya geç
                ParentStudentLink.student_id == ParentStudentLink.student_id,  # placeholder
            )
            .filter(
                User.role == UserRole.PARENT,
                User.is_active == True,  # noqa: E712
            )
            .all()
        )
        # Yukarıdaki alias karmaşık — sade alt-sorgu ile yeniden kuralım:
        student_ids = [
            sid for (sid,) in db.query(User.id).filter(
                User.teacher_id == sender.id,
                User.role == UserRole.STUDENT,
                User.is_active == True,  # noqa: E712
            ).all()
        ]
        if student_ids:
            parent_ids = [
                pid for (pid,) in db.query(ParentStudentLink.parent_id)
                .filter(ParentStudentLink.student_id.in_(student_ids))
                .distinct()
                .all()
            ]
            users = (
                db.query(User)
                .filter(
                    User.id.in_(parent_ids),
                    User.role == UserRole.PARENT,
                    User.is_active == True,  # noqa: E712
                )
                .order_by(User.full_name)
                .all()
            )
        else:
            users = []

    elif group_key == GROUP_INST_TEACHERS:
        # INSTITUTION_ADMIN için aynı kurumdaki öğretmenler
        # SUPER_ADMIN için sender.institution_id None olduğundan boş döner
        # (super admin yine GROUP_MY_STUDENTS/PARENTS kullanmaz toplu için — yok)
        inst_id = sender.institution_id
        if not inst_id:
            users = []
        else:
            users = (
                db.query(User)
                .filter(
                    User.institution_id == inst_id,
                    User.role == UserRole.TEACHER,
                    User.is_active == True,  # noqa: E712
                )
                .order_by(User.full_name)
                .all()
            )

    elif group_key == GROUP_INST_STUDENTS:
        inst_id = sender.institution_id
        if not inst_id:
            users = []
        else:
            users = (
                db.query(User)
                .filter(
                    User.institution_id == inst_id,
                    User.role == UserRole.STUDENT,
                    User.is_active == True,  # noqa: E712
                )
                .order_by(User.full_name)
                .all()
            )

    elif group_key == GROUP_INST_PARENTS:
        inst_id = sender.institution_id
        if not inst_id:
            users = []
        else:
            student_ids = [
                sid for (sid,) in db.query(User.id).filter(
                    User.institution_id == inst_id,
                    User.role == UserRole.STUDENT,
                    User.is_active == True,  # noqa: E712
                ).all()
            ]
            if student_ids:
                parent_ids = [
                    pid for (pid,) in db.query(ParentStudentLink.parent_id)
                    .filter(ParentStudentLink.student_id.in_(student_ids))
                    .distinct()
                    .all()
                ]
                users = (
                    db.query(User)
                    .filter(
                        User.id.in_(parent_ids),
                        User.role == UserRole.PARENT,
                        User.is_active == True,  # noqa: E712
                    )
                    .order_by(User.full_name)
                    .all()
                )
            else:
                users = []

    eligible: list[BulkTargetCandidate] = []
    no_phone: list[BulkTargetCandidate] = []
    for u in users:
        c = _candidate_from_user(u)
        if c.can_message:
            eligible.append(c)
        else:
            no_phone.append(c)

    return BulkTargetsResult(
        eligible=eligible,
        no_phone=no_phone,
        total=len(users),
    )


# ----------------------------------------------------------------------
# Toplu URL üretici
# ----------------------------------------------------------------------


def build_bulk_dispatch(
    db: Session,
    *,
    sender: User,
    template_id: int,
    target_user_ids: list[int],
    variables: dict[str, str] | None = None,
    mode: str = "sequential",
    freeform_note: str | None = None,
    write_log: bool = True,
) -> BulkDispatchResult:
    """Bir şablon + birden çok hedef → URL listesi.

    Yetki yok / telefonu doğrulu değil → skipped'a düşer (UI'de "atlandı"
    olarak gösterilir, gönderim bütünlüğünü bozmaz).
    """
    if mode not in ("sequential", "broadcast"):
        raise WaDispatchError("invalid_mode", "Geçersiz mod.", status=400)

    if not target_user_ids:
        raise WaDispatchError(
            "no_targets", "En az bir hedef seçilmeli.", status=400,
        )

    if len(target_user_ids) > MAX_BULK_TARGETS:
        raise WaDispatchError(
            "too_many_targets",
            f"En fazla {MAX_BULK_TARGETS} hedef seçebilirsiniz.",
            status=400,
        )

    # Şablon
    tmpl = (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.id == template_id, WhatsAppTemplate.is_active == True)  # noqa: E712
        .first()
    )
    if not tmpl:
        raise WaDispatchError(
            "template_not_found", "Şablon bulunamadı veya pasif.", status=404,
        )

    if not tmpl.allow_bulk:
        raise WaDispatchError(
            "bulk_not_allowed",
            "Bu şablon toplu gönderim için işaretlenmemiş.",
            status=400,
        )

    # Freeform note kontrolü
    note_clean = (freeform_note or "").strip()
    if note_clean and not tmpl.allow_freeform_note:
        raise WaDispatchError(
            "freeform_not_allowed",
            "Bu şablona serbest not eklenemez.",
            status=400,
        )

    # Render (broadcast modunda tek metin; sequential'da her hedefe aynı metin)
    var_defs = parse_variables_json(tmpl.variables_json)
    preview = render_preview(
        template=tmpl.content_template,
        values=variables or {},
        variable_defs=var_defs,
    )
    rendered = preview.rendered
    if note_clean:
        rendered = f"{rendered}\n\n{note_clean}"

    char_count = len(rendered)
    long_text = char_count >= LONG_TEXT_THRESHOLD
    warnings = list(preview.warnings)
    if long_text:
        warnings.append(
            f"Metin {char_count} karakter — bazı uygulamalar 2000+'i kırpabilir."
        )

    # Hedefleri al, yetki + telefon kontrolü → eligible vs skipped
    targets = (
        db.query(User)
        .filter(User.id.in_(target_user_ids))
        .all()
    )
    targets_by_id = {t.id: t for t in targets}

    items: list[BulkDispatchItem] = []
    skipped: list[BulkSkippedItem] = []

    # Sıralı: target_user_ids sırası korunsun (kullanıcının seçim sırası önemli)
    for tid in target_user_ids:
        target = targets_by_id.get(tid)
        if target is None or not target.is_active:
            skipped.append(BulkSkippedItem(
                target_user_id=tid,
                target_name="(bulunamadı)",
                reason="not_found",
            ))
            continue
        if not can_send_wa_to(db, sender=sender, target=target):
            skipped.append(BulkSkippedItem(
                target_user_id=tid,
                target_name=target.full_name,
                reason="no_permission",
            ))
            continue
        if not can_message_phone(target):
            skipped.append(BulkSkippedItem(
                target_user_id=tid,
                target_name=target.full_name,
                reason="phone_not_verified",
            ))
            continue

        wa_url = build_wa_url(target.phone, rendered)
        items.append(BulkDispatchItem(
            target_user_id=target.id,
            target_name=target.full_name,
            wa_url=wa_url,
            phone_masked=mask_phone_e164(target.phone),
        ))

        if write_log:
            log = WhatsAppDispatchLog(
                sender_user_id=sender.id,
                target_user_id=target.id,
                template_key=tmpl.key,
                template_id=tmpl.id,
                params_json=json.dumps(
                    {
                        "variables": variables or {},
                        "freeform_note": note_clean or None,
                        "bulk_mode": mode,
                    },
                    ensure_ascii=False, default=str,
                ),
                character_count=char_count,
            )
            db.add(log)

    if write_log and items:
        db.flush()

    return BulkDispatchResult(
        mode=mode,
        rendered_text=rendered,
        items=items,
        skipped=skipped,
        total_dispatched=len(items),
        long_text=long_text,
        warnings=warnings,
    )
