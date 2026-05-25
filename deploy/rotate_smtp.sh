#!/usr/bin/env bash
# =============================================================================
# SMTP app şifresini güvenli güncelle — şifre ekrana yazılmaz, sadece .env'e gider.
# Kullanım (sunucuda interaktif):
#   ssh -t -i <key> root@SUNUCU "bash /opt/etutkoc/deploy/rotate_smtp.sh"
# Zoho'da önce eski app şifresini iptal edip yenisini üret; bu script onu sorar.
# YALNIZCA app şifresini yapıştır (~16 karakter), başka metin değil.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

read -rs -p "Yeni Zoho app sifresi: " RAW
echo
# Zoho şifreyi bazen bosluklu (gruplu) gosterir → tum bosluklari temizle
P="$(printf '%s' "$RAW" | tr -d '[:space:]')"
unset RAW
LEN=${#P}
[ "$LEN" -eq 0 ] && { echo "Bos sifre — iptal, degisiklik yok"; exit 1; }

echo "Girilen sifre: uzunluk=$LEN  onizleme=${P:0:2}***${P: -2}"
if [ "$LEN" -lt 8 ] || [ "$LEN" -gt 40 ]; then
  echo "UYARI: Zoho app sifresi tipik olarak ~16 karakter. Uzunluk ($LEN) sira disi —"
  echo "       fazladan metin yapistirmis olabilirsin. Yalnizca sifreyi yapistir."
fi
read -r -p "Bu sifreyi uygulayalim mi? (e/h): " OK
[ "$OK" = "e" ] || { echo "Iptal — degisiklik yok"; exit 1; }

grep -v '^SMTP_PASSWORD=' .env > .env.tmp
printf 'SMTP_PASSWORD=%s\n' "$P" >> .env.tmp
mv .env.tmp .env
chmod 600 .env
unset P
echo "SMTP_PASSWORD guncellendi — servisler yenileniyor..."
docker compose up -d web worker >/dev/null 2>&1
echo "TAMAM — yeni sifre aktif (yukaridaki onizleme/uzunluk dogruysa)"
