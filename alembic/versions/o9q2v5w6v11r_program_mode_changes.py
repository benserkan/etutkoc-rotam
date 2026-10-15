"""Program modu geçiş geçmişi (gün gün ↔ haftalık havuz, 2026-10-15).

Her mod geçişi bir kayıt: hangi gün (`effective_on`), hangi yönde, kim, hangi tetikle
(elle / "Seansı bitir"), geçişte ne yapıldı (`summary_json`: silinen/serbest bırakılan görev
ve rezerv sayıları). Uyarı motoru (gün güne geçişten sonraki ilk günler), raporlar ve veli
özetleri bir tarihin hangi moda ait olduğunu buradan okur. Additive, downgrade'li.

Revision ID: o9q2v5w6v11r
Revises: n8p1u4v5u99q
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o9q2v5w6v11r"
down_revision: Union[str, None] = "n8p1u4v5u99q"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "program_mode_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_mode", sa.String(16), nullable=False),
        sa.Column("to_mode", sa.String(16), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("trigger", sa.String(24), nullable=False, server_default="manual"),
        sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("study_periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("summary_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_program_mode_changes_student", "program_mode_changes", ["student_id", "effective_on"])


def downgrade() -> None:
    op.drop_index("ix_program_mode_changes_student", table_name="program_mode_changes")
    op.drop_table("program_mode_changes")
