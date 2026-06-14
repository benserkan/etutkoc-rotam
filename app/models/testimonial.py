"""Testimonial — sosyal kanıt (kullanıcı yorumu / kurum referansı / başarı hikâyesi).

Anasayfada (landing) yayınlanan sosyal kanıt. Üç akış:
  1. Uygulama-içi gönderim: öğrenci/veli/koç/kurum yöneticisi sistem hakkında
     yorum bırakır → `pending` (incelenmeyi bekler).
  2. Süper admin elle giriş: kurum referansı / yorum / başarı hikâyesi girer,
     doğrudan `published` yapabilir.
  3. Public: yalnız `published` kayıtlar anasayfada görünür.

KVKK: ad/rol/kurum yalnız `consent_public=True` + süper admin onayıyla yayınlanır.
Kişisel veri minimumda; öğrenci için ad yerine kısaltma (örn. "Z. A.") tercih edilir.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Tür (kind) — sade dil
TESTIMONIAL_KIND_REVIEW = "review"                  # kullanıcı yorumu
TESTIMONIAL_KIND_INSTITUTION = "institution_ref"    # kurum referansı
TESTIMONIAL_KIND_STORY = "success_story"            # başarı hikâyesi

TESTIMONIAL_KIND_LABELS_TR: dict[str, str] = {
    TESTIMONIAL_KIND_REVIEW: "Kullanıcı yorumu",
    TESTIMONIAL_KIND_INSTITUTION: "Kurum referansı",
    TESTIMONIAL_KIND_STORY: "Başarı hikâyesi",
}

# Durum (moderation)
TESTIMONIAL_STATUS_PENDING = "pending"      # geldi, incelenmedi (uygulama-içi)
TESTIMONIAL_STATUS_PUBLISHED = "published"  # anasayfada yayında
TESTIMONIAL_STATUS_HIDDEN = "hidden"        # gizli / reddedildi / arşiv

TESTIMONIAL_STATUS_LABELS_TR: dict[str, str] = {
    TESTIMONIAL_STATUS_PENDING: "Bekliyor",
    TESTIMONIAL_STATUS_PUBLISHED: "Yayında",
    TESTIMONIAL_STATUS_HIDDEN: "Gizli",
}

# Kaynak
TESTIMONIAL_SOURCE_MANUAL = "manual"        # süper admin elle girdi
TESTIMONIAL_SOURCE_IN_APP = "in_app"        # kullanıcı uygulamadan gönderdi
TESTIMONIAL_SOURCE_IMPORT = "import"        # eski siteden / dışarıdan içe aktarıldı

TESTIMONIAL_SOURCE_LABELS_TR: dict[str, str] = {
    TESTIMONIAL_SOURCE_MANUAL: "Süper admin girişi",
    TESTIMONIAL_SOURCE_IN_APP: "Uygulama içi gönderim",
    TESTIMONIAL_SOURCE_IMPORT: "İçe aktarım",
}

# Rol etiketi (yazan kişi) — anasayfada gösterilir
TESTIMONIAL_ROLE_LABELS_TR: dict[str, str] = {
    "student": "Öğrenci",
    "parent": "Veli",
    "teacher": "Koç",
    "institution_admin": "Kurum Yöneticisi",
    "other": "Kullanıcı",
}


class Testimonial(Base):
    __tablename__ = "testimonials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TESTIMONIAL_KIND_REVIEW, index=True
    )
    author_name: Mapped[str] = mapped_column(String(160), nullable=False)
    author_role: Mapped[str | None] = mapped_column(String(30), nullable=True)
    author_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    institution_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    content: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TESTIMONIAL_STATUS_PENDING, index=True
    )
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TESTIMONIAL_SOURCE_MANUAL
    )

    submitted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    consent_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Testimonial {self.id} {self.kind} {self.status}>"
