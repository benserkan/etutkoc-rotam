"""SignupAttribution — landing dönüşüm ilişkilendirme.

Bir kullanıcı üye olduğunda, geldiği anonim landing oturumunu (fc_telemetry_sid
cookie) + gördüğü A/B varyantını kaydeder. Böylece "ziyaretçi → demo → üye →
ücretli" hunisi ve hangi varyantın dönüştürdüğü ölçülebilir.

KVKK: session_id anonim telemetri tanımlayıcısıdır (kişisel veri değil, IP/UA
saklanmaz). user_id ile ilişki yalnız süper admin dönüşüm panosunda agregat
olarak kullanılır.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Kaynak
SIGNUP_SOURCE_LANDING = "landing"   # landing oturumu cookie'si vardı
SIGNUP_SOURCE_DIRECT = "direct"     # doğrudan / organik (landing izi yok)


class SignupAttribution(Base):
    __tablename__ = "signup_attributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    session_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    variant_slug: Mapped[str | None] = mapped_column(String(40), nullable=True)
    signup_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default=SIGNUP_SOURCE_DIRECT)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<SignupAttribution {self.id} user={self.user_id} src={self.source}>"
