#!/usr/bin/env bash
# =============================================================================
# SMTP şifresini/token'ını güvenli güncelle — değer ekrana YAZILMAZ, yalnız .env'e gider.
#
# Kullanım (sunucuda interaktif):
#   ssh -t root@SUNUCU "bash /opt/etutkoc/deploy/rotate_smtp.sh"
#
# Destekler:
#   - ZeptoMail "Send Mail Token"  (~144 karakter, wSsVR... ile başlar)
#     ZeptoMail paneli → Agents → agent_1 → SMTP/API → SMTP sekmesi
#   - Zoho Mail app şifresi        (~16 karakter)
#
# 2026-07-30 dersi: ZeptoMail deneme süresi dolunca token reddedilmeye başladı ve
# e-posta 10 GÜN sessizce durdu. Bu yüzden script artık değişiklikten sonra GERÇEK
# SMTP girişi deneyip sonucu söylüyor — "güncelledim" demek yetmez, kanıt gerekir.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

read -rs -p "Yeni SMTP sifresi/token: " RAW
echo
# Panel değeri bazen boşluklu/satır sonlu kopyalanır → tüm boşlukları temizle
P="$(printf '%s' "$RAW" | tr -d '[:space:]')"
unset RAW
LEN=${#P}
[ "$LEN" -eq 0 ] && { echo "Bos deger — iptal, degisiklik yok"; exit 1; }

echo "Girilen deger: uzunluk=$LEN  onizleme=${P:0:6}***${P: -4}"

# --- Sekil dogrulamasi (2026-07-30: SSH komut satiri token'a karisip .env'e
# 697 karakterlik cop yazilmisti; onizleme gosterildi ama gozden kacti).
# Sifre/token daima base64-benzeri: harf, rakam ve + / = . _ - . Komut satirinda
# bulunan @ " ' bosluk : gibi karakterler ASLA olmaz → uyari degil, RED.
if [ "$LEN" -lt 8 ] || [ "$LEN" -gt 200 ]; then
  echo "HATA: uzunluk ($LEN) makul araligin (8-200) disinda."
  echo "      Zoho app sifresi ~16, ZeptoMail token'i ~144 karakterdir."
  echo "      Muhtemelen fazladan metin (komut satiri?) yapistirildi. Iptal."
  exit 1
fi
case "$P" in
  ssh*|*@*|*\"*|*\'*|*bash*|*docker*)
    echo "HATA: deger komut satiri metnine benziyor (ssh/@/tirnak/bash iceriyor)."
    echo "      YALNIZCA panelden kopyaladigin sifre/token yapistirilmali. Iptal."
    exit 1 ;;
esac
if printf '%s' "$P" | grep -q '[^A-Za-z0-9+/=._-]'; then
  echo "HATA: deger beklenmeyen karakter iceriyor (yalnizca A-Z a-z 0-9 + / = . _ - olmali)."
  echo "      Yanlis alan kopyalanmis olabilir. Iptal."
  exit 1
fi

echo
echo ">>> Bu deger BASKA bir sey degil, panelden kopyaladigin sifre/token mi?"
read -r -p "    Uygulayalim mi? (e/h): " OK
[ "$OK" = "e" ] || { echo "Iptal — degisiklik yok"; exit 1; }

BACKUP=".env.bak.$(date +%Y%m%d_%H%M%S)"
cp .env "$BACKUP"
chmod 600 "$BACKUP"

grep -v '^SMTP_PASSWORD=' .env > .env.tmp
printf 'SMTP_PASSWORD=%s\n' "$P" >> .env.tmp
mv .env.tmp .env
chmod 600 .env
unset P
echo "SMTP_PASSWORD guncellendi (yedek: $BACKUP) — servisler yenileniyor..."
docker compose up -d web worker >/dev/null 2>&1

# --- Gerçek doğrulama: SMTP girişi denenir -----------------------------------
echo "SMTP girisi test ediliyor..."
sleep 3
if docker compose exec -T web python -c "
import os, smtplib, sys
h = os.getenv('SMTP_HOST'); p = int(os.getenv('SMTP_PORT', '587'))
u = os.getenv('SMTP_USER') or ''; pw = os.getenv('SMTP_PASSWORD') or ''
try:
    s = smtplib.SMTP(h, p, timeout=25); s.ehlo(); s.starttls(); s.ehlo()
    s.login(u, pw); s.quit()
    print('AUTH_OK')
except Exception as e:
    print('AUTH_FAIL', str(e)[:160]); sys.exit(1)
"; then
  echo
  echo "TAMAM — SMTP kimlik dogrulamasi BASARILI. E-posta akisi acildi."
  echo "Yedegi silebilirsin: rm $BACKUP"
else
  echo
  echo "!!! SMTP girisi HALA BASARISIZ — deger yanlis ya da saglayici hesabi kapali."
  echo "    Geri al:  cp $BACKUP .env && docker compose up -d web worker"
  exit 1
fi
