"""P0 — veli bildirim tercihlerine WhatsApp kanal toggle'ları + çocuk WA onayı.

Eklenen kolonlar (parent_notification_prefs, hepsi nullable=False default=False):
  - daily_summary_wa_enabled
  - weekly_report_wa_enabled
  - empty_day_alert_wa_enabled
  - drop_alert_wa_enabled
  - new_program_alert_wa_enabled
  - teacher_note_wa_enabled
  - exam_approaching_wa_enabled
  - child_whatsapp_consent  (18 yaş altı çocuk için WhatsApp gönderim onayı)

Mevcut `*_enabled` flag'leri **e-posta tarafı için** korunuyor (default=True,
geriye uyumlu — eski davranış değişmez). Yeni `*_wa_enabled` flag'leri varsayılan
KAPALI (opt-in). Veli aktivasyonda istediği WhatsApp tiplerini seçer.

Additive + downgrade'li. Mevcut veri etkilenmez.
"""
from alembic import op
import sqlalchemy as sa


revision = "r5s8w0x1w99q"
down_revision = "q4r7v0w1v99p"
branch_labels = None
depends_on = None


_WA_COLUMNS = [
    "daily_summary_wa_enabled",
    "weekly_report_wa_enabled",
    "empty_day_alert_wa_enabled",
    "drop_alert_wa_enabled",
    "new_program_alert_wa_enabled",
    "teacher_note_wa_enabled",
    "exam_approaching_wa_enabled",
]


def upgrade() -> None:
    for col_name in _WA_COLUMNS:
        op.add_column(
            "parent_notification_prefs",
            sa.Column(
                col_name,
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    op.add_column(
        "parent_notification_prefs",
        sa.Column(
            "child_whatsapp_consent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("parent_notification_prefs", "child_whatsapp_consent")
    for col_name in reversed(_WA_COLUMNS):
        op.drop_column("parent_notification_prefs", col_name)
