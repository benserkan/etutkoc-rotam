"""P3 — WhatsApp Click-to-WA dispatch log.

URL üretilen her tetik için audit/spam guard girişi. P6'da bu tablodan
hesaplanır: bu hafta kaç mesaj, günlük tavan aşıldı mı, hangi velilere
art arda. P3'te yalnız yazılır.

Yeni tablo: whatsapp_dispatch_logs
  - sender_user_id (FK CASCADE — gönderen koç/yön./admin)
  - target_user_id (FK SET NULL — hedef öğr/veli/koç)
  - template_key (str — eski şablon silinse bile audit korunsun)
  - template_id (FK SET NULL — analiz için)
  - params_json (Text — değişken değerleri, debug için)
  - character_count (int — uzunluk istatistiği)
  - created_at

Additive + downgrade'li.
"""
from alembic import op
import sqlalchemy as sa


revision = "u8v1z3a4z22t"
down_revision = "t7u0y2z3y11s"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_dispatch_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sender_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("template_key", sa.String(80), nullable=False),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("whatsapp_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("params_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("character_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_wadlog_sender_created",
        "whatsapp_dispatch_logs",
        ["sender_user_id", "created_at"],
    )
    op.create_index(
        "ix_wadlog_target_created",
        "whatsapp_dispatch_logs",
        ["target_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wadlog_target_created", table_name="whatsapp_dispatch_logs")
    op.drop_index("ix_wadlog_sender_created", table_name="whatsapp_dispatch_logs")
    op.drop_table("whatsapp_dispatch_logs")
