"""CRM not + aksiyon tabloları (Sprint B — Kurum 360).

Revision ID: d8a1c3b4c33v
Revises: c7z0b2a3b22u
Create Date: 2026-05-16 14:30:00.000000

Yeni tablolar:
  - crm_notes: kurum bazlı kronolojik notlar (pinned bayrağı ile)
  - crm_actions: kurum bazlı temas/aksiyon kayıtları (telefon, e-posta,
    teklif, takip tarihi vb.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8a1c3b4c33v"
down_revision: Union[str, None] = "c7z0b2a3b22u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # crm_notes
    op.create_table(
        "crm_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "institution_id", sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE",
                          name="fk_crm_notes_institution"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "created_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL",
                          name="fk_crm_notes_created_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_notes_institution_id", "crm_notes", ["institution_id"])
    op.create_index("ix_crm_notes_inst_created", "crm_notes",
                    ["institution_id", "created_at"])
    op.create_index("ix_crm_notes_pinned", "crm_notes",
                    ["institution_id", "pinned"])

    # crm_actions
    op.create_table(
        "crm_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "institution_id", sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE",
                          name="fk_crm_actions_institution"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum("call", "email", "whatsapp", "meeting",
                    "offer_sent", "onboarding", "other",
                    name="crmactionkind"),
            nullable=False,
        ),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "result",
            sa.Enum("success", "no_answer", "declined",
                    "scheduled", "done", "pending", "other",
                    name="crmactionresult"),
            nullable=False, server_default="pending",
        ),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL",
                          name="fk_crm_actions_created_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_crm_actions_institution_id", "crm_actions",
                    ["institution_id"])
    op.create_index("ix_crm_actions_inst_created", "crm_actions",
                    ["institution_id", "created_at"])
    op.create_index("ix_crm_actions_followup", "crm_actions",
                    ["institution_id", "follow_up_at"])


def downgrade() -> None:
    op.drop_index("ix_crm_actions_followup", table_name="crm_actions")
    op.drop_index("ix_crm_actions_inst_created", table_name="crm_actions")
    op.drop_index("ix_crm_actions_institution_id", table_name="crm_actions")
    op.drop_table("crm_actions")

    op.drop_index("ix_crm_notes_pinned", table_name="crm_notes")
    op.drop_index("ix_crm_notes_inst_created", table_name="crm_notes")
    op.drop_index("ix_crm_notes_institution_id", table_name="crm_notes")
    op.drop_table("crm_notes")

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        sa.Enum(name="crmactionkind").drop(bind, checkfirst=True)
        sa.Enum(name="crmactionresult").drop(bind, checkfirst=True)
