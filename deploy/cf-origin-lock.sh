#!/bin/sh
# Origin kilidi: 80/443 yalnız Cloudflare'den kabul edilir (SSH dokunulmaz).
# IPv4 Docker yayını DNAT ile FORWARD → DOCKER-USER zincirinden geçer (ufw görmez),
# bu yüzden kural orada. IPv6 docker-proxy ile INPUT'a gelir → ufw kuralları (ayrı).
# Kurulum: deploy/CLOUDFLARE_PROXY_SETUP.md · systemd: cf-origin-lock.service
# Geri alma: iptables -D DOCKER-USER -i eth0 -p tcp -m multiport --dports 80,443 -j CF-ORIGIN
set -e
IF=${CF_LOCK_IFACE:-eth0}
V4="173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18 108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17 162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22"

iptables -N CF-ORIGIN 2>/dev/null || iptables -F CF-ORIGIN
iptables -A CF-ORIGIN -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
for n in $V4; do iptables -A CF-ORIGIN -s "$n" -j RETURN; done
iptables -A CF-ORIGIN -j DROP

iptables -N DOCKER-USER 2>/dev/null || true
while iptables -D DOCKER-USER -i "$IF" -p tcp -m multiport --dports 80,443 -j CF-ORIGIN 2>/dev/null; do :; done
iptables -I DOCKER-USER 1 -i "$IF" -p tcp -m multiport --dports 80,443 -j CF-ORIGIN
echo "cf-origin-lock: IPv4 80/443 yalnız Cloudflare"
