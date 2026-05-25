#!/usr/bin/env bash
# =============================================================================
# Günlük Postgres yedeği — sıkıştırılmış custom-format dump + rotasyon.
#
# Kullanım (sunucuda, deploy/ içinden veya tam yolla):
#   bash deploy/backup.sh
# Cron (günlük 03:00 UTC):
#   0 3 * * * cd /opt/etutkoc/deploy && bash backup.sh >> /var/log/lgs-backup.log 2>&1
#
# Geri yükleme (DİKKAT — mevcut veriyi değiştirir):
#   cat backups/lgs-YYYY-MM-DD-HHMM.dump | docker compose exec -T db \
#     pg_restore -U lgs -d lgs --clean --if-exists
#
# NOT: Bu yedekler sunucunun KENDİ diskinde — disk/sunucu kaybına karşı
# KORUMAZ. Disk-dışı koruma için Hetzner otomatik backup (snapshot) AÇILMALI.
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"            # deploy/
BACKUP_DIR="${BACKUP_DIR:-$DIR/../backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
PGUSER="${POSTGRES_USER:-lgs}"
PGDB="${POSTGRES_DB:-lgs}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%F-%H%M)"
FILE="$BACKUP_DIR/lgs-$STAMP.dump"

cd "$DIR"
# -Fc: custom format (sıkıştırılmış + pg_restore ile esnek/seçici geri yükleme)
docker compose exec -T db pg_dump -U "$PGUSER" -Fc "$PGDB" > "$FILE"

# Boş/başarısız dump'ı bırakma
if [ ! -s "$FILE" ]; then
    echo "HATA: yedek boş — siliniyor"; rm -f "$FILE"; exit 1
fi
echo "$(date -u +%FT%TZ) yedek alındı: $FILE ($(du -h "$FILE" | cut -f1))"

# Rotasyon: KEEP_DAYS günden eski yedekleri sil
find "$BACKUP_DIR" -name 'lgs-*.dump' -type f -mtime +"$KEEP_DAYS" -delete
echo "rotasyon: $KEEP_DAYS günden eski yedekler temizlendi ($(ls "$BACKUP_DIR"/lgs-*.dump 2>/dev/null | wc -l) yedek mevcut)"
