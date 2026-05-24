"""Institution (kurum) modeli — Sprint 11+ multi-tenant başlangıcı.

Bir kurum dershane / etüt merkezi / koçluk firması gibi bir tüzel kişiliği
temsil eder. Kurumun altında öğretmenler (User.role=TEACHER, institution_id
=kurum.id) ve onların öğrencileri yaşar.

Yetkilendirme prensipleri:
- INSTITUTION_ADMIN: yalnız kendi kurumunun roster + agrega verisini görür
- TEACHER (kurum-altı): mevcut UI'ı kullanır, sadece kendi öğrencilerini yönetir
- TEACHER (bağımsız, institution_id=NULL): aynı UI, kurum yok
- SUPER_ADMIN: bütün kurumları + tüm kullanıcıları görür/yönetir

Migration default: "ETUTKOC" adında bir kurum oluşturulur ve mevcut tüm
öğretmenler ona bağlanır (kullanıcı kararı, 2026-05-08).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Institution(Base):
    __tablename__ = "institutions"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_institution_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # URL/handle olarak kullanılır — sadece a-z, 0-9, hyphen kabul edilir
    # (route prefix'lerinde kullanılabilir, ileride subdomain için).
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Plan placeholder — billing entegrasyonu Sprint 14+ olabilir.
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Stage 9 (Faz 2) — Pilot/trial: kurum başvurusunda 30 gün
    # 'pilot' süreci aktif. Süre dolduğunda plana göre devam eder veya
    # 'free' (institution_free) olur. NULL = trial yok / bitmiş.
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    post_trial_plan: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    # Abonelik tipi: 'monthly' (varsayılan, aylık) | 'academic_year'
    # (Eylül-Haziran 10 ay peşin) | 'paused' (yaz pause modunda, %20 saklama)
    subscription_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="monthly"
    )
    # Aboneliğin aktif olduğu dönem sonu (akademik yıl bitişi vb.)
    subscription_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Pause modunda dönüş tarihi
    subscription_pause_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 60 gün performans garantisi seçili mi (yıllık planlarda)
    performance_guarantee: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # Garanti hak kazanımı tarihi (uzatma uygulandı mı kontrolü için)
    guarantee_extended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Kurum logosu (co-branding) — DB'de saklanır (support-attachment deseni).
    # deferred: liste/detay sorgularında yüklenmez; yalnız serve ucu okur.
    logo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    logo_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_content_type)

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="institution",
        foreign_keys="User.institution_id",
    )

    def __repr__(self) -> str:
        return f"<Institution {self.slug}>"
