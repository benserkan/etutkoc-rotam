"""metric_snapshots + follow_ups + 2 cron seed

Ölçüm geçmişi (günlük) + tarihli takip listesi (2026-11-08). Additive.

Revision ID: b2d5i8j9i44e
Revises: a1c4h7i8h33d
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from alembic import op

revision = "b2d5i8j9i44e"
down_revision = "a1c4h7i8h33d"
branch_labels = None
depends_on = None

CRONS = (
    ("metrics_snapshot_daily",
     "Günlük 02:30 UTC — ölçüm listesi: tanımlı ölçülerin günlük değeri (koç + sistem)",
     2, 30),
    ("follow_up_daily",
     "Günlük 06:00 UTC (09:00 TR) — takip listesi: vadesi gelenleri değerlendir + süper admine bildir",
     6, 0),
)


def upgrade() -> None:
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("metric_key", sa.String(64), nullable=False),
        sa.Column("owner_type", sa.String(16), nullable=False, server_default="system"),
        sa.Column("owner_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("measured_on", sa.Date(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("sample_n", sa.Integer(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("metric_key", "owner_type", "owner_id", "measured_on",
                            name="uq_metric_snapshot_day"),
    )
    op.create_index("ix_metric_snapshots_metric_key", "metric_snapshots", ["metric_key"])
    op.create_index("ix_metric_snapshots_measured_on", "metric_snapshots", ["measured_on"])

    op.create_table(
        "follow_ups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(80), nullable=True, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(24), nullable=False, server_default="diger"),
        sa.Column("priority", sa.String(8), nullable=False, server_default="normal"),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("snoozed_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="open"),
        sa.Column("recurrence_days", sa.Integer(), nullable=True),
        sa.Column("check_kind", sa.String(48), nullable=True),
        sa.Column("check_params_json", sa.Text(), nullable=True),
        sa.Column("baseline_on", sa.Date(), nullable=True),
        sa.Column("last_report_json", sa.Text(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_on", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result_note", sa.Text(), nullable=True),
        sa.Column("previous_id", sa.Integer(),
                  sa.ForeignKey("follow_ups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_follow_ups_due_on", "follow_ups", ["due_on"])
    op.create_index("ix_follow_ups_status", "follow_ups", ["status"])

    bind = op.get_bind()
    for key, desc, h, m in CRONS:
        if bind.execute(sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
                        {"k": key}).first() is None:
            bind.execute(
                sa.text("INSERT INTO cron_schedules (job_key, description, hour, minute, day_of_week, enabled) "
                        "VALUES (:k, :d, :h, :m, :w, :e)"),
                {"k": key, "d": desc, "h": h, "m": m, "w": None, "e": True},  # bool bind
            )


def downgrade() -> None:
    bind = op.get_bind()
    for key, *_ in CRONS:
        bind.execute(sa.text("DELETE FROM cron_schedules WHERE job_key = :k"), {"k": key})
    op.drop_index("ix_follow_ups_status", table_name="follow_ups")
    op.drop_index("ix_follow_ups_due_on", table_name="follow_ups")
    op.drop_table("follow_ups")
    op.drop_index("ix_metric_snapshots_measured_on", table_name="metric_snapshots")
    op.drop_index("ix_metric_snapshots_metric_key", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")
