#!/usr/bin/env bash
set -euo pipefail

APT_LOCK_TIMEOUT=600

apt_safe() {
  local tries=0
  local max_tries=5
  while true; do
    if sudo DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=${APT_LOCK_TIMEOUT} "$@"; then
      return 0
    fi

    tries=$((tries + 1))
    if [[ ${tries} -ge ${max_tries} ]]; then
      echo "apt-get gagal setelah ${max_tries} percobaan: apt-get $*"
      return 1
    fi

    echo "apt-get belum berhasil (kemungkinan lock masih aktif), ulangi percobaan ${tries}/${max_tries}..."
  done
}

echo "[1/6] apt update"
apt_safe update

echo "[2/6] install nginx + modsecurity module"
apt_safe install -y nginx libnginx-mod-http-modsecurity modsecurity-crs

echo "[3/6] enable nginx service"
sudo systemctl enable nginx || true

echo "[4/6] ensure modsecurity conf files"
sudo mkdir -p /etc/nginx/modsec
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
sudo cp "$PROJECT_ROOT/infra/modsecurity/main.conf" /etc/nginx/modsec/main.conf
sudo mkdir -p /var/log/modsecurity
sudo touch /var/log/modsecurity/audit.log
sudo chgrp adm /var/log/modsecurity/audit.log || true
sudo chmod 644 /var/log/modsecurity/audit.log

echo "[5/6] copy app nginx config"
sudo cp "$PROJECT_ROOT/infra/nginx/waf_observatory.conf" /etc/nginx/sites-available/waf_observatory.conf
sudo ln -sf /etc/nginx/sites-available/waf_observatory.conf /etc/nginx/sites-enabled/waf_observatory.conf

if [[ -f /etc/nginx/sites-enabled/default ]]; then
  sudo rm -f /etc/nginx/sites-enabled/default
fi

echo "[6/7] test and restart nginx"
sudo nginx -t
if ! sudo systemctl restart nginx; then
  sudo service nginx restart
fi

echo "[7/7] install and start backend service"
sudo cp "$PROJECT_ROOT/infra/systemd/waf-observatory-backend.service" /etc/systemd/system/waf-observatory-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now waf-observatory-backend.service

echo "Setup selesai. Cek:"
echo "  sudo systemctl status nginx --no-pager"
echo "  sudo systemctl status waf-observatory-backend --no-pager"
