"""Maarif sınav türleri — ExamSection'a 5 yeni üye

Revision ID: x9y2b5c6b00x
Revises: w8x1a4b5a99w
Create Date: 2026-09-09

Maarif Modeli'nde sınav SİSTEMİ değişmiyor, karşılıkları şöyle (kullanıcı,
2026-09-09): 1. Basamak ≈ TYT (9-10 konuları) · 2. Basamak ≈ AYT (11-12).
Şu an 9-10-11 Maarif modelde; 12 ve mezunlar hâlâ klasik YKS'de. Yayınevleri
bu yıl "Maarif Model Birinci Basamak Sınavı" + sınıf düzeyi denemeleri
(9/10/11) basıyor — sistemde karşılığı olmadığı için koç ne beyan edebiliyor
ne de tespit tutuyordu (ÇAP karnesi, öğrenci #34).

Postgres native enum → ALTER TYPE ADD VALUE
([[feedback-postgres-enum-new-member-migration]]); SQLite'ta ExamSection düz
VARCHAR olduğundan no-op. Additive: mevcut kayıtlara DOKUNMAZ.

MAARIF_2 (2. Basamak) şimdiden eklenir — 12. sınıf seneye Maarif'e geçtiğinde
migration'sız açılabilsin diye; beyan listesinde BU YIL gösterilmez.

Downgrade: Postgres enum'dan üye DÜŞÜRÜLEMEZ (tipi yeniden kurmak gerekir);
additive olduğu için downgrade no-op bırakıldı.
"""
from alembic import op

revision = "x9y2b5c6b00x"
down_revision = "w8x1a4b5a99w"
branch_labels = None
depends_on = None


_YENI_UYELER = (
    "MAARIF_1",   # Maarif 1. Basamak (TYT muadili — 9-10 konuları)
    "MAARIF_2",   # Maarif 2. Basamak (AYT muadili — 11-12; seneye)
    "MAARIF_9",   # Maarif 9. Sınıf denemesi
    "MAARIF_10",  # Maarif 10. Sınıf denemesi
    "MAARIF_11",  # Maarif 11. Sınıf denemesi
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite: ExamSection VARCHAR olarak saklanır, ek iş yok
    for uye in _YENI_UYELER:
        op.execute(f"ALTER TYPE examsection ADD VALUE IF NOT EXISTS '{uye}'")


def downgrade() -> None:
    # Postgres enum üyesi düşürülemez; additive olduğu için no-op.
    pass
