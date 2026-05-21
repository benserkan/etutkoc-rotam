"""health_score_snapshots: owner-aware (Institution + bağımsız öğretmen User)

Revision ID: g7i0l3k4j22e
Revises: f6h9k2j3i11d
Create Date: 2026-05-17 19:00:00.000000

CRM ve Invoice ile aynı owner pattern: `owner_type` + nullable XOR FK.

Mevcut snapshot'lar institution'a aitti — server_default='institution' alır.
Yeni: bağımsız öğretmen (User role=TEACHER + institution_id=NULL) için de
günlük snapshot. UNIQUE (user_id, snapshot_date) eklenir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7i0l3k4j22e"
down_revision: Union[str, None] = "f6h9k2j3i11d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Yeni kolonlar — server_default ile mevcut satırlar 'institution' alır
    with op.batch_alter_table("health_score_snapshots") as batch:
        batch.add_column(
            sa.Column("owner_type", sa.String(length=20), nullable=False,
                      server_default=sa.text("'institution'")),
        )
        batch.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    # 2) institution_id'yi nullable yap + user_id FK + XOR check + yeni UNIQUE
    with op.batch_alter_table("health_score_snapshots") as batch:
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=True)
        batch.create_foreign_key(
            "fk_health_snapshots_user_id_users",
            "users", ["user_id"], ["id"], ondelete="CASCADE",
        )
        batch.create_unique_constraint(
            "uq_health_snapshot_user_date",
            ["user_id", "snapshot_date"],
        )
        batch.create_check_constraint(
            "ck_health_snapshots_owner_xor",
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
        )

    # 3) Yeni indeks — user_id + snapshot_date'e göre sorgular için
    op.create_index(
        "ix_health_snapshot_user_date", "health_score_snapshots",
        ["user_id", "snapshot_date"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_health_snapshot_user_date", table_name="health_score_snapshots")
    with op.batch_alter_table("health_score_snapshots") as batch:
        batch.drop_constraint("ck_health_snapshots_owner_xor", type_="check")
        batch.drop_constraint("uq_health_snapshot_user_date", type_="unique")
        batch.drop_constraint("fk_health_snapshots_user_id_users", type_="foreignkey")
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=False)
        batch.drop_column("user_id")
        batch.drop_column("owner_type")
