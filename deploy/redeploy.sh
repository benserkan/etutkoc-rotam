#!/usr/bin/env bash
# =============================================================================
# ETÜTKOÇ — sunucuda yeniden-deploy (düzelt → tekrar gönder döngüsü)
#
# Kullanım (sunucuda, repo kökünden veya deploy/ içinden):
#   bash deploy/redeploy.sh
#
# Akış:
#   1. git pull          — local'de commit/push edilen değişiklikleri çek
#   2. DB yedeği         — migration'dan ÖNCE pg_dump (güvenlik)
#   3. up --build        — image'leri yeniden derle + başlat
#                          (web start.sh otomatik: alembic upgrade + seed'ler)
#   4. log takibi        — web migration + sağlık çıktısı
#
# NOT: Sunucuda kod DÜZENLEME yok — hep local → commit → push → bu script.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$REPO_ROOT/deploy"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"

cd "$REPO_ROOT"

echo "==> 1/4  git pull"
git pull --ff-only

cd "$DEPLOY_DIR"

echo "==> 2/4  DB yedeği (migration öncesi)"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%F-%H%M)"
if docker compose ps db --status running >/dev/null 2>&1; then
  docker compose exec -T db pg_dump -U "${POSTGRES_USER:-lgs}" "${POSTGRES_DB:-lgs}" \
    > "$BACKUP_DIR/lgs-$STAMP.sql" \
    && echo "    yedek: $BACKUP_DIR/lgs-$STAMP.sql" \
    || echo "    [uyarı] pg_dump başarısız (db henüz ayakta değil olabilir) — devam"
else
  echo "    [bilgi] db container çalışmıyor (ilk kurulum?) — yedek atlanıyor"
fi

echo "==> 3/4  build + up (web start.sh: alembic upgrade + seed'ler)"
docker compose up -d --build

echo "==> 4/4  web logları (Ctrl+C ile çık)"
docker compose logs -f --tail=40 web
