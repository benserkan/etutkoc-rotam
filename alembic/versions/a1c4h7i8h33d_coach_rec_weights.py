"""coach_rec_weights + rec_weights_train cron seed

Koç başına öğrenilen öneri ağırlıkları (2026-11-08). Gece işi her koçun
öğrencilerinde son 12 haftayı yeniden oynatır; öğrenilen ağırlık ayrılmış son
günlerde varsayılanı geçerse kullanılır. Additive.

Revision ID: a1c4h7i8h33d
Revises: z0b3g6h7g22c
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op

revision = "a1c4h7i8h33d"
down_revision = "z0b3g6h7g22c"
branch_labels = None
depends_on = None

JOB_KEY = "rec_weights_train"


def upgrade() -> None:
    op.create_table(
        "coach_rec_weights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="insufficient"),
        sa.Column("weights_json", sa.Text(), nullable=True),
        sa.Column("n_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_students", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shown_default", sa.Float(), nullable=True),
        sa.Column("shown_learned", sa.Float(), nullable=True),
        sa.Column("top3_default", sa.Float(), nullable=True),
        sa.Column("top3_learned", sa.Float(), nullable=True),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_coach_rec_weights_coach_id", "coach_rec_weights", ["coach_id"], unique=True)

    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
                    {"k": JOB_KEY}).first() is None:
        bind.execute(
            sa.text("INSERT INTO cron_schedules (job_key, description, hour, minute, day_of_week, enabled) "
                    "VALUES (:k, :d, :h, :m, :w, :e)"),
            {"k": JOB_KEY,
             "d": "Günlük 01:40 UTC — koç başına öneri ağırlığı öğrenimi (son 12 hafta)",
             "h": 1, "m": 40, "w": None,
             "e": True},  # bind param — Postgres bool
        )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM cron_schedules WHERE job_key = :k"), {"k": JOB_KEY})
    op.drop_index("ix_coach_rec_weights_coach_id", table_name="coach_rec_weights")
    op.drop_table("coach_rec_weights")
