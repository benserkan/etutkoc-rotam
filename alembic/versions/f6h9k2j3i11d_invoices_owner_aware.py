"""invoices: owner-aware (Institution + bağımsız öğretmen User)

Revision ID: f6h9k2j3i11d
Revises: e5g8j1i2h00c
Create Date: 2026-05-17 18:00:00.000000

Bağımsız öğretmen (User role=TEACHER + institution_id=NULL) için fatura
desteği. CRM (CrmNote/CrmAction) ile aynı owner pattern: `owner_type`
('institution' | 'user') + nullable XOR FK'ler.

Mevcut tüm faturalar institution'a aitti → otomatik `owner_type='institution'`
alır (server_default). institution_id nullable yapılır, user_id eklenir.
XOR check constraint: tam birinin set olması zorunlu.

Yeni indeks: ix_invoices_user_status (user_id, status) — dunning cron'unun
owner-aware sorgularını hızlandırmak için.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6h9k2j3i11d"
down_revision: Union[str, None] = "e5g8j1i2h00c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Yeni kolonlar — server_default ile mevcut satırlar 'institution' alır
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(
            sa.Column("owner_type", sa.String(length=20), nullable=False,
                      server_default=sa.text("'institution'")),
        )
        batch.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    # 2) institution_id'yi nullable yap + user_id FK + XOR check
    with op.batch_alter_table("invoices") as batch:
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=True)
        batch.create_foreign_key(
            "fk_invoices_user_id_users",
            "users", ["user_id"], ["id"], ondelete="CASCADE",
        )
        batch.create_check_constraint(
            "ck_invoices_owner_xor",
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
        )

    # 3) Yeni indeks — dunning/listing sorguları için (user_id, status)
    op.create_index(
        "ix_invoices_user_status", "invoices",
        ["user_id", "status"], unique=False,
    )
    op.create_index(
        "ix_invoices_user_id", "invoices", ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_user_id", table_name="invoices")
    op.drop_index("ix_invoices_user_status", table_name="invoices")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("ck_invoices_owner_xor", type_="check")
        batch.drop_constraint("fk_invoices_user_id_users", type_="foreignkey")
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=False)
        batch.drop_column("user_id")
        batch.drop_column("owner_type")
