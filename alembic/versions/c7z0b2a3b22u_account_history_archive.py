"""Hesap hareketleri arşivi — PlanChangeHistory + Invoice'a archived_at.

Revision ID: c7z0b2a3b22u
Revises: b6y9a1z2a11t
Create Date: 2026-05-16 14:00:00.000000

Amaç:
  - Hesap hareket sayfasında son 3 yıl varsayılan pencere.
  - Daha eski kayıtlar otomatik gizlenir ama silinmez.
  - Admin "Arşive ekle" diyebilir veya "Arşivi göster" ile geri çıkarabilir.
  - Soft archive: archived_at + archived_by_user_id + archive_note ile yumuşak silme.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7z0b2a3b22u"
down_revision: Union[str, None] = "b6y9a1z2a11t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PlanChangeHistory
    with op.batch_alter_table("plan_change_history") as batch:
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column(
            "archived_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL",
                           name="fk_plan_history_archived_by"),
            nullable=True,
        ))
        batch.add_column(sa.Column("archive_note", sa.String(length=500), nullable=True))
    op.create_index(
        "ix_plan_history_archived_owner",
        "plan_change_history", ["archived_at", "owner_type", "owner_id"],
    )

    # Invoice
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column(
            "archived_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL",
                           name="fk_invoices_archived_by"),
            nullable=True,
        ))
        batch.add_column(sa.Column("archive_note", sa.String(length=500), nullable=True))
    op.create_index(
        "ix_invoices_archived_institution",
        "invoices", ["archived_at", "institution_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_archived_institution", table_name="invoices")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_column("archive_note")
        batch.drop_column("archived_by_user_id")
        batch.drop_column("archived_at")

    op.drop_index("ix_plan_history_archived_owner", table_name="plan_change_history")
    with op.batch_alter_table("plan_change_history") as batch:
        batch.drop_column("archive_note")
        batch.drop_column("archived_by_user_id")
        batch.drop_column("archived_at")
