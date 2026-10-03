"""Site asistanı soru-cevap kaydı — 2026-10-03.

Sitenin her yerindeki tek yapay zekâ asistanının (ziyaretçi + 5 rol) soru ve
cevaplarını tutar: günlük soru sınırı (kullanıcı / ziyaretçi oturumu / IP özeti)
+ süper yöneticinin "en çok sorulanlar" ve ziyaretçi konuşmaları görünümü.
Ham IP SAKLANMAZ (yalnız SHA-256 özeti). 180 günden eskisi günlük temizlenir.

Additive, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "m4n7q0r1q55m"
down_revision = "l3m6p9q0p44l"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("session_key", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("audience", sa.String(24), nullable=False),
        sa.Column("page", sa.String(200), nullable=True),
        sa.Column("chip", sa.String(60), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("handoff", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_assistant_messages_created_at", "assistant_messages", ["created_at"])
    op.create_index("ix_assistant_messages_session_key", "assistant_messages", ["session_key"])
    op.create_index("ix_assistant_messages_user_id", "assistant_messages", ["user_id"])
    op.create_index("ix_assistant_messages_ip_hash", "assistant_messages", ["ip_hash"])


def downgrade() -> None:
    op.drop_index("ix_assistant_messages_ip_hash", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_user_id", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_session_key", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_created_at", table_name="assistant_messages")
    op.drop_table("assistant_messages")
