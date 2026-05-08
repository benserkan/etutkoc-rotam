"""subjects unique constraint: (teacher_id, name) → (teacher_id, name, curriculum_model)

Revision ID: k3f9j1g2h22c
Revises: j2e8h0f1g11b
Create Date: 2026-05-08 02:00:00.000000

Aynı ders adı ("Matematik") farklı müfredat modellerinde paralel yaşamalı:
- LGS Matematik (5-8)
- KLASIK_LISE Matematik (11-12 son nesil)
- MAARIF_LISE Matematik (9-12 yeni nesil)

Eski constraint (teacher_id, name) bu üç kaydın birlikte var olmasını engelliyordu;
yeni constraint (teacher_id, name, curriculum_model) izin verir.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "k3f9j1g2h22c"
down_revision: Union[str, None] = "j2e8h0f1g11b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("subjects") as batch:
        batch.drop_constraint("uq_subject_teacher_name", type_="unique")
        batch.create_unique_constraint(
            "uq_subject_teacher_name_model",
            ["teacher_id", "name", "curriculum_model"],
        )


def downgrade() -> None:
    with op.batch_alter_table("subjects") as batch:
        batch.drop_constraint("uq_subject_teacher_name_model", type_="unique")
        batch.create_unique_constraint(
            "uq_subject_teacher_name",
            ["teacher_id", "name"],
        )
