"""Invoice plan <-> owner_type tutarlılık CHECK constraint

Revision ID: m0n3r5s6r55l
Revises: l9m2p4q5p33j
Create Date: 2026-05-26

Sözleşme:
  - owner_type='institution' → plan ∈ {institution_free, etut_standart,
    dershane_pro, enterprise} (solo_ ile başlamayan herhangi bir kod)
  - owner_type='user'        → plan ∈ {solo_*} (solo_ ile başlayan)

Bu CHECK, demo seed script'inin yanlış kombinasyon (institution+solo_pro vb.)
yaratmasını DB seviyesinde reddeder. ORM'da @validates ile defense-in-depth.

Migration upgrade'inde önce tutarsız satırlar SİLİNİR (constraint eklenebilsin
diye). ETUTKOC kurumu için bunlar 26.05.2026'da zaten CANCELLED yapılmıştı;
veri kaybı yok (cancelled = ödeme akışından çıkmış).
"""
from alembic import op
from sqlalchemy import text


revision = "m0n3r5s6r55l"
down_revision = "l9m2p4q5p33j"
branch_labels = None
depends_on = None


_CHECK_NAME = "ck_invoices_plan_owner_match"
_CHECK_EXPR = (
    r"(owner_type = 'institution' AND plan NOT LIKE 'solo\_%' ESCAPE '\') "
    r"OR (owner_type = 'user' AND plan LIKE 'solo\_%' ESCAPE '\')"
)


def upgrade() -> None:
    # 1) Tutarsız satırları temizle — CHECK eklenmeden önce şart.
    op.execute(text(
        r"DELETE FROM invoices "
        r"WHERE (owner_type = 'institution' AND plan LIKE 'solo\_%' ESCAPE '\') "
        r"   OR (owner_type = 'user' AND plan NOT LIKE 'solo\_%' ESCAPE '\')"
    ))

    # 2) CHECK constraint
    op.create_check_constraint(_CHECK_NAME, "invoices", _CHECK_EXPR)


def downgrade() -> None:
    op.drop_constraint(_CHECK_NAME, "invoices", type_="check")
    # Silinen satırlar geri yüklenemez (demo verisi olduğu için tutulmadı).
