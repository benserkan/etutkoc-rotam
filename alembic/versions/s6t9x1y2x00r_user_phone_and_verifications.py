"""P1 — kullanıcı telefonu (tüm roller) + generic phone_verifications tablosu.

Eklenenler:
  - users.phone (E.164, nullable) + users.phone_verified_at
  - users.phone_secondary (yalnız veli için anne+baba ayrımı) +
    users.phone_secondary_verified_at
  - phone_verifications tablosu (user_id FK, generic — tüm roller için OTP)

Veri taşıma:
  - parent_notification_prefs.whatsapp_phone (verified_at dolu olanlar) →
    users.phone + users.phone_verified_at. Veri korunur, çift kaynağa
    yazılmamak için pref tarafındaki kolonlar bundan sonra kullanılmaz
    (deprecated — boş bırakılır, geriye uyum için silmiyoruz).

Additive + downgrade'li. Mevcut veri etkilenmez (taşıma sırasında okur+yazar,
silmez).
"""
from alembic import op
import sqlalchemy as sa


revision = "s6t9x1y2x00r"
down_revision = "r5s8w0x1w99q"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) users tablosuna 4 yeni nullable kolon
    op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users", sa.Column("phone_secondary", sa.String(20), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column(
            "phone_secondary_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # 2) Generic phone_verifications tablosu — tüm roller için OTP
    op.create_table(
        "phone_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        # "primary" | "secondary" (yalnız veli secondary kullanır)
        sa.Column(
            "slot",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'primary'"),
        ),
        # "sms" | "whatsapp" — varsayılan sms (P1: yalnız SMS desteklenir)
        sa.Column(
            "channel",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'sms'"),
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_phone_ver_user_created",
        "phone_verifications",
        ["user_id", "created_at"],
    )
    op.create_index("ix_phone_ver_phone", "phone_verifications", ["phone"])

    # 3) Veri taşıma — mevcut velilerin doğrulanmış WhatsApp telefonu User.phone'a
    # whatsapp_phone_verified_at dolu olanları al, User.phone'a yaz
    op.execute(
        """
        UPDATE users
        SET phone = pref.whatsapp_phone,
            phone_verified_at = pref.whatsapp_phone_verified_at
        FROM parent_notification_prefs pref
        WHERE users.id = pref.parent_id
          AND pref.whatsapp_phone IS NOT NULL
          AND pref.whatsapp_phone_verified_at IS NOT NULL
          AND users.phone IS NULL
        """
        if op.get_context().dialect.name == "postgresql"
        else """
        UPDATE users
        SET phone = (
                SELECT pref.whatsapp_phone
                FROM parent_notification_prefs pref
                WHERE pref.parent_id = users.id
            ),
            phone_verified_at = (
                SELECT pref.whatsapp_phone_verified_at
                FROM parent_notification_prefs pref
                WHERE pref.parent_id = users.id
            )
        WHERE EXISTS (
            SELECT 1 FROM parent_notification_prefs pref
            WHERE pref.parent_id = users.id
              AND pref.whatsapp_phone IS NOT NULL
              AND pref.whatsapp_phone_verified_at IS NOT NULL
        )
          AND users.phone IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_phone_ver_phone", table_name="phone_verifications")
    op.drop_index("ix_phone_ver_user_created", table_name="phone_verifications")
    op.drop_table("phone_verifications")

    op.drop_column("users", "phone_secondary_verified_at")
    op.drop_column("users", "phone_secondary")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone")
