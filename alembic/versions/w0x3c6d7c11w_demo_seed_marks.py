"""M5 ext — Demo etiketleri: is_demo + demo_seed_id + demo_label

users + institutions tablolarına 3 opsiyonel alan:
  - is_demo: bool default False — listede rozet + filtre için
  - demo_seed_id: str(32) nullable — aynı seansın tüm kayıtlarını gruplar (UUID hex)
  - demo_label: str(120) nullable — süper admin notu ("ABC Etüt için demo")

**Önemli (kullanıcı 2026-05-31 kararı):** Bu flag yalnız **görsel ayrım + toplu
temizlik** içindir. İstatistik filtrelerinde (revenue/health/activity) KULLANILMAZ.
Demo hesaplar sistemde gerçek hesap gibi görünür; süper admin görüşme sonrası
"Demo Hesaplar" sayfasından tek tıkla seansı siler.

Additive + downgrade'li, mevcut veriyi etkilemez.
"""
from alembic import op
import sqlalchemy as sa


revision = "w0x3c6d7c11w"
down_revision = "v9w2b5c6b00v"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("demo_seed_id", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("demo_label", sa.String(length=120), nullable=True)
        )

    with op.batch_alter_table("institutions") as batch_op:
        batch_op.add_column(
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("demo_seed_id", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("demo_label", sa.String(length=120), nullable=True)
        )

    # İndeks — demo seansları listeleme + toplu silme için
    op.create_index(
        "ix_users_demo_seed_id", "users", ["demo_seed_id"], unique=False,
    )
    op.create_index(
        "ix_institutions_demo_seed_id", "institutions", ["demo_seed_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_institutions_demo_seed_id", table_name="institutions")
    op.drop_index("ix_users_demo_seed_id", table_name="users")

    with op.batch_alter_table("institutions") as batch_op:
        batch_op.drop_column("demo_label")
        batch_op.drop_column("demo_seed_id")
        batch_op.drop_column("is_demo")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("demo_label")
        batch_op.drop_column("demo_seed_id")
        batch_op.drop_column("is_demo")
