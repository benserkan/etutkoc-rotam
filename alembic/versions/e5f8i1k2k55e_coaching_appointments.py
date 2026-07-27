"""Online görüşme / randevu sistemi (koç ↔ öğrenci)

- coaching_appointment_series : haftalık tekrarlayan randevu kuralı
- coaching_appointments       : tek görüşme randevusu (ileriye dönük)
- coach_availability_windows  : self-servis slot için koç uygunluk pencereleri
- coach_google_accounts       : koçun Google OAuth bağı (Meet linki üretimi;
                                refresh token Fernet şifreli)
- parent_notification_prefs.appointment_enabled : veli randevu bildirimi/
  hatırlatması toggle'ı (varsayılan AÇIK — opt-out)
- cron seed: appointment_maintenance (10 dk'da bir — seri roll-forward +
  D-1 / 1 saat hatırlatmaları)

Additive; mevcut veriye dokunmaz. Downgrade'li.

Revision ID: e5f8i1k2k55e
Revises: d4e7h0j1j33d
"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "e5f8i1k2k55e"
down_revision = "d4e7h0j1j33d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coaching_appointment_series",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "coach_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("meeting_link", sa.Text(), nullable=True),
        sa.Column("link_source", sa.String(length=8), nullable=True),
        sa.Column("google_event_id", sa.String(length=128), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_appt_series_coach", "coaching_appointment_series", ["coach_id"]
    )
    op.create_index(
        "ix_appt_series_student", "coaching_appointment_series", ["student_id"]
    )

    op.create_table(
        "coaching_appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "coach_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "series_id", sa.Integer(),
            sa.ForeignKey("coaching_appointment_series.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False, server_default="40"),
        sa.Column(
            "status", sa.String(length=12), nullable=False,
            server_default="scheduled",
        ),
        sa.Column(
            "source", sa.String(length=8), nullable=False, server_default="coach",
        ),
        sa.Column(
            "requested_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("meeting_link", sa.Text(), nullable=True),
        sa.Column("link_source", sa.String(length=8), nullable=True),
        sa.Column("google_event_id", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("request_note", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("reminder_d1_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_h1_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_appt_coach_date", "coaching_appointments", ["coach_id", "date"])
    op.create_index("ix_appt_student_date", "coaching_appointments", ["student_id", "date"])
    op.create_index("ix_appt_series", "coaching_appointments", ["series_id"])

    op.create_table(
        "coach_availability_windows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "coach_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(length=5), nullable=False),
        sa.Column("end_time", sa.String(length=5), nullable=False),
        sa.Column("slot_minutes", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index("ix_avail_coach", "coach_availability_windows", ["coach_id"])

    op.create_table(
        "coach_google_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "coach_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("google_email", sa.String(length=255), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column(
            "connected_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("coach_id", name="uq_coach_google"),
    )
    op.create_index("ix_coach_google_coach", "coach_google_accounts", ["coach_id"])

    # Veli randevu bildirimi toggle'ı (varsayılan AÇIK — opt-out; e-posta+push)
    with op.batch_alter_table("parent_notification_prefs") as batch:
        batch.add_column(sa.Column(
            "appointment_enabled", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ))

    # Cron seed — 10 dakikada bir: seri roll-forward + hatırlatmalar.
    # DERS: enabled BOOLEAN → Postgres'te literal 1 DatatypeMismatch verir;
    # daima bool bind param (:e=True).
    now = datetime.now(timezone.utc).isoformat()
    op.execute(sa.text(
        "INSERT INTO cron_schedules "
        "(job_key, description, hour, minute, day_of_week, "
        " interval_minutes, enabled, created_at, updated_at) "
        "VALUES (:k, :d, :h, :m, :dow, :iv, :e, :ts, :ts)"
    ).bindparams(
        k="appointment_maintenance",
        d="Randevu bakımı: haftalık seri üretimi + görüşme hatırlatmaları (D-1 ve 1 saat önce).",
        h=0, m=0, dow=None, iv=10, e=True, ts=now,
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM cron_schedules WHERE job_key = 'appointment_maintenance'"
    ))
    with op.batch_alter_table("parent_notification_prefs") as batch:
        batch.drop_column("appointment_enabled")
    op.drop_index("ix_coach_google_coach", table_name="coach_google_accounts")
    op.drop_table("coach_google_accounts")
    op.drop_index("ix_avail_coach", table_name="coach_availability_windows")
    op.drop_table("coach_availability_windows")
    op.drop_index("ix_appt_series", table_name="coaching_appointments")
    op.drop_index("ix_appt_student_date", table_name="coaching_appointments")
    op.drop_index("ix_appt_coach_date", table_name="coaching_appointments")
    op.drop_table("coaching_appointments")
    op.drop_index("ix_appt_series_student", table_name="coaching_appointment_series")
    op.drop_index("ix_appt_series_coach", table_name="coaching_appointment_series")
    op.drop_table("coaching_appointment_series")
