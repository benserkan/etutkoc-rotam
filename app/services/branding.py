"""Kurumsal kimlik (co-branding) — TEK MERKEZ (2026-09-30).

Kuruma bağlı her kullanıcı (kurum yöneticisi, öğretmen, öğrenci, veli) sistemi
KURUMUN markasıyla görür: e-postaların başlığında kurum logosu (yoksa kurum
adı), gönderen adı kurum, "Yanıtla" kurumun iletişim adresi; panel ve yazdırma
çıktılarında kurum logosu. ETÜTKOÇ Rotam yalnız altta "altyapı sağlayıcısı"
cümlesiyle geçer (logo YOK).

Kurum çözümü:
  - kullanıcının kendi institution_id'si
  - öğrenci: yoksa koçunun kurumu
  - veli: bağlı çocuklarından ilkinin (birincil bağ önce) kurumu
Bağımsız koç ve öğrencileri/velileri → None (ETÜTKOÇ markası).

Gönderen e-posta ADRESİ ETÜTKOÇ alan adında kalır (SPF/DKIM doğrulaması o
alan adı için); yalnız görünen ad kurumdur.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings

PLATFORM_NAME = "ETÜTKOÇ Rotam"


@dataclass(frozen=True)
class Brand:
    institution_id: int
    name: str
    has_logo: bool
    logo_version: int
    reply_to: str | None

    @property
    def logo_path(self) -> str | None:
        """Herkese açık logo yolu (e-posta istemcileri çerezsiz çeker)."""
        if not self.has_logo:
            return None
        return f"/api/v2/brand/logo/{self.institution_id}?v={self.logo_version}"

    @property
    def logo_url(self) -> str | None:
        p = self.logo_path
        return f"{settings.app_base_url.rstrip('/')}{p}" if p else None

    def as_email_ctx(self) -> dict:
        return {
            "name": self.name,
            "logo_url": self.logo_url,
            "reply_to": self.reply_to,
            "platform_name": PLATFORM_NAME,
        }


def brand_for_institution(inst) -> Brand | None:
    if inst is None or not getattr(inst, "is_active", True):
        return None
    updated = getattr(inst, "logo_updated_at", None)
    return Brand(
        institution_id=inst.id,
        name=inst.name,
        has_logo=bool(inst.logo_content_type),
        logo_version=int(updated.timestamp()) if updated else 0,
        reply_to=(inst.contact_email or None),
    )


def institution_id_for_user(db: Session, user) -> int | None:
    from app.models import ParentStudentLink, User, UserRole

    if user is None:
        return None
    if user.institution_id:
        return user.institution_id
    role = getattr(user.role, "value", user.role)
    if role == UserRole.STUDENT.value and user.teacher_id:
        teacher = db.get(User, user.teacher_id)
        return teacher.institution_id if teacher else None
    if role == UserRole.PARENT.value:
        links = (
            db.query(ParentStudentLink)
            .filter(ParentStudentLink.parent_id == user.id)
            .order_by(ParentStudentLink.is_primary.desc(), ParentStudentLink.id)
            .all()
        )
        for link in links:
            child = db.get(User, link.student_id)
            if child is None:
                continue
            iid = institution_id_for_user(db, child)
            if iid:
                return iid
    return None


def brand_for_user(db: Session, user) -> Brand | None:
    from app.models import Institution

    iid = institution_id_for_user(db, user)
    return brand_for_institution(db.get(Institution, iid)) if iid else None


def brand_for_email(db: Session, email: str) -> Brand | None:
    from app.models import User

    if not email:
        return None
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    return brand_for_user(db, user) if user else None


def brand_for_institution_id(db: Session, institution_id: int | None) -> Brand | None:
    from app.models import Institution

    if not institution_id:
        return None
    return brand_for_institution(db.get(Institution, institution_id))
