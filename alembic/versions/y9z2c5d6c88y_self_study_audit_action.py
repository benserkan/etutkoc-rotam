"""auditaction enum'una SELF_STUDY_UPDATE üyesi (bağımsız çalışma audit izi)

Faz 2 — elle/bağımsız ilerleme girişlerinin (koç toplu girişi, beyan onay/ret,
silme/geri alma, eski mutlak set) AuditLog'a yazılması için yeni aksiyon.
Postgres native enum'a üye eklenmezse bu audit'i yazan uçlar prod'da 500 verir
(dev SQLite VARCHAR — görünmez). Downgrade'de üye kalır (PG enum üyesi
düşürülemez — zararsız).

Revision ID: y9z2c5d6c88y
Revises: x8y1b4c5b77x
Create Date: 2026-07-20
"""
from alembic import op

revision = "y9z2c5d6c88y"
down_revision = "x8y1b4c5b77x"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'SELF_STUDY_UPDATE'")
    # SQLite: Enum VARCHAR olarak saklanır — işlem gerekmez.


def downgrade() -> None:
    # PG enum üyesi güvenle düşürülemez; üye kalır (zararsız).
    pass
