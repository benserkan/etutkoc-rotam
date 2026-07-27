"""F4 — randevu → seans köprüsü: coaching_sessions.appointment_id

Koç, biten online görüşmeyi tek adımda KS1 seans kaydına çevirir
("Seansı kaydet"): seans randevuya bağlanır (mükerrer kayıt engeli +
"bu randevunun seansı girildi" durumu) ve DONE seans KS2 tahsilata
otomatik sayılır. Additive, downgrade'li.

Revision ID: f6g9j2l3l66f
Revises: e5f8i1k2k55e
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6g9j2l3l66f"
down_revision = "e5f8i1k2k55e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("coaching_sessions") as batch:
        batch.add_column(sa.Column(
            "appointment_id", sa.Integer(),
            sa.ForeignKey(
                "coaching_appointments.id",
                ondelete="SET NULL",
                name="fk_session_appointment",
            ),
            nullable=True,
        ))
    op.create_index(
        "ix_session_appointment", "coaching_sessions", ["appointment_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_session_appointment", table_name="coaching_sessions")
    with op.batch_alter_table("coaching_sessions") as batch:
        batch.drop_column("appointment_id")
