"""crm_notes + crm_actions: owner-aware (Institution + bağımsız öğretmen User)

Revision ID: e5g8j1i2h00c
Revises: d4f7i0h1g99b
Create Date: 2026-05-17 16:00:00.000000

CRM not + aksiyon kayıtları artık hem `Institution` hem bağımsız `User`
(role=TEACHER, institution_id=NULL) için tutulabilir. Mevcut kayıtların
hepsi institution'a aitti — onlara `owner_type='institution'` set edilir.

Şema değişimi:
- `owner_type` String(20) NOT NULL DEFAULT 'institution'
- `user_id` Integer NULL → FK users.id ondelete CASCADE
- `institution_id` NOT NULL → NULL (artık opsiyonel)
- XOR check constraint: tam birinin set olması zorunlu

Mevcut indeksler korunur; user_id için ek indeksler eklenir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5g8j1i2h00c"
down_revision: Union[str, None] = "d4f7i0h1g99b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _upgrade_table(table: str) -> None:
    # 1) Yeni kolonları ekle (default ile — mevcut satırlar 'institution' alır)
    with op.batch_alter_table(table) as batch:
        batch.add_column(
            sa.Column("owner_type", sa.String(length=20), nullable=False,
                      server_default=sa.text("'institution'")),
        )
        batch.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True),
        )

    # 2) institution_id'yi nullable yap + FK'leri (batch içinde)
    #    + user_id için FK + XOR check + ek indeksler
    with op.batch_alter_table(table) as batch:
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=True)
        batch.create_foreign_key(
            f"fk_{table}_user_id_users",
            "users", ["user_id"], ["id"], ondelete="CASCADE",
        )
        batch.create_check_constraint(
            f"ck_{table}_owner_xor",
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
        )

    # 3) user_id için indeksler (created_at + follow_up_at)
    op.create_index(
        f"ix_{table}_user_id", table, ["user_id"], unique=False,
    )


def upgrade() -> None:
    _upgrade_table("crm_notes")
    op.create_index(
        "ix_crm_notes_user_created", "crm_notes",
        ["user_id", "created_at"], unique=False,
    )

    _upgrade_table("crm_actions")
    op.create_index(
        "ix_crm_actions_user_created", "crm_actions",
        ["user_id", "created_at"], unique=False,
    )
    op.create_index(
        "ix_crm_actions_user_followup", "crm_actions",
        ["user_id", "follow_up_at"], unique=False,
    )


def _downgrade_table(table: str) -> None:
    op.drop_index(f"ix_{table}_user_id", table_name=table)
    with op.batch_alter_table(table) as batch:
        batch.drop_constraint(f"ck_{table}_owner_xor", type_="check")
        batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=False)
        batch.drop_column("user_id")
        batch.drop_column("owner_type")


def downgrade() -> None:
    op.drop_index("ix_crm_actions_user_followup", table_name="crm_actions")
    op.drop_index("ix_crm_actions_user_created", table_name="crm_actions")
    _downgrade_table("crm_actions")

    op.drop_index("ix_crm_notes_user_created", table_name="crm_notes")
    _downgrade_table("crm_notes")
