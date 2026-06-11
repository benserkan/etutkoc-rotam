"""panel_quick_access — davranıştan öğrenen hızlı erişim kartları (QA-1)

Revision ID: g0h3k6l7k44b
Revises: f9g2j5k6j33a
Create Date: 2026-06-11

Panel ana sayfalarına (5 rol) kullanıcı davranışından öğrenen dinamik hızlı
erişim kartları. İki tablo:
  - panel_visit_events: ham ziyaret olayı (normalize route_key + entity_id;
    ham URL SAKLANMAZ). 180 gün saklanır (panel_events_purge cron'u siler).
  - panel_route_stats: kullanıcı+rota+entity başına TEK satır agregat
    (EWMA skor + sayaçlar + kullanıcı kararları: sabitle/kaldır).
+ panel_events_purge günlük cron seed (03:30 UTC).
Additive, downgrade'li — mevcut veriyi ETKİLEMEZ.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g0h3k6l7k44b"
down_revision: Union[str, None] = "f9g2j5k6j33a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "panel_visit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("route_key", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("dwell_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(16), nullable=False, server_default="web"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_panel_visit_events_user_created",
        "panel_visit_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_panel_visit_events_route_created",
        "panel_visit_events",
        ["route_key", "created_at"],
    )

    op.create_table(
        "panel_route_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("route_key", sa.String(64), nullable=False),
        # UNIQUE constraint'te NULL'lar eşit sayılmadığı için entity'siz satırda 0
        sa.Column("entity_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("days_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dwell_ms_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_visit_date", sa.Date(), nullable=True),
        sa.Column("card_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "route_key", "entity_id", name="uq_panel_route_stat"
        ),
    )

    # panel_events_purge günlük cron seed (idempotent INSERT)
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "panel_events_purge"},
    ).first()
    if existing is None:
        bind.execute(
            sa.text(
                "INSERT INTO cron_schedules "
                "(job_key, description, hour, minute, day_of_week, enabled) "
                "VALUES (:k, :d, :h, :m, :w, :e)"
            ),
            {
                "k": "panel_events_purge",
                "d": "Günlük 03:30 UTC — 180 günden eski panel ziyaret olaylarını sil",
                "h": 3,
                "m": 30,
                "w": None,  # her gün
                # bool param — Postgres'te enabled BOOLEAN (literal 1 integer
                # sayılıp DatatypeMismatch verir), SQLite'ta 1'e çözülür
                "e": True,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "panel_events_purge"},
    )
    op.drop_table("panel_route_stats")
    op.drop_index("ix_panel_visit_events_route_created", table_name="panel_visit_events")
    op.drop_index("ix_panel_visit_events_user_created", table_name="panel_visit_events")
    op.drop_table("panel_visit_events")
