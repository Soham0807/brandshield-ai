#!/usr/bin/env bash
# BrandShield AI — one-shot installer for a fresh Ubuntu 22.04/24.04 server.
#
#   sudo bash deploy/install.sh yourdomain.me you@email.com
#
# Sets up Python + the app, downloads the DistilBERT model, runs it as a
# systemd service, and puts Caddy in front for automatic HTTPS and a password
# gate (the app has no user accounts yet, so the gate is what keeps it private).

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
APP_USER="brandshield"
APP_DIR="/opt/brandshield"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
  echo "Usage: sudo bash deploy/install.sh <domain> <email-for-https-certificate>"
  exit 1
fi
if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo."
  exit 1
fi

echo "==> 1/8  System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip build-essential curl rsync ufw debian-keyring \
                      debian-archive-keyring apt-transport-https gnupg

# Node is needed once, to build the dashboard
if ! command -v node &>/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1
  apt-get install -y -qq nodejs
fi

echo "==> 2/8  Swap (protects against out-of-memory while the model loads)"
if [[ ! -f /swapfile ]]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap -q /swapfile
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> 3/8  Application user and files"
id -u "$APP_USER" &>/dev/null || useradd --system --create-home --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"
rsync -a --delete \
      --exclude 'env/' --exclude 'node_modules/' --exclude '__pycache__/' \
      --exclude 'backend/data/' --exclude '.git/' \
      "$REPO_DIR"/ "$APP_DIR"/
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

echo "==> 3b/8 Building the dashboard"
if [[ ! -f "$APP_DIR/frontend/dist/index.html" ]]; then
  (cd "$APP_DIR/frontend" && npm install --no-audit --no-fund --silent && npm run build --silent)
  chown -R "$APP_USER:$APP_USER" "$APP_DIR/frontend"
fi

echo "==> 4/8  Python environment (this takes a few minutes)"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/venv/bin/pip" install -q \
     --extra-index-url https://download.pytorch.org/whl/cpu -r "$APP_DIR/backend/requirements.txt"
sudo -u "$APP_USER" "$APP_DIR/venv/bin/python" -c \
     "import nltk; [nltk.download(p, quiet=True) for p in ('stopwords','wordnet','omw-1.4')]"

echo "==> 5/8  Downloading the sentiment model (~500 MB, once)"
sudo -u "$APP_USER" HF_HOME="$APP_DIR/.cache/huggingface" "$APP_DIR/venv/bin/python" - <<'PY'
from transformers import pipeline
pipeline("text-classification", model="tabularisai/multilingual-sentiment-analysis", top_k=None)
print("model ready")
PY

echo "==> 6/8  Configuration"
ENV_FILE="$APP_DIR/backend/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$APP_DIR/backend/.env.example" "$ENV_FILE"
fi
# the public address matters for the Instagram OAuth redirect
sed -i "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://$DOMAIN|" "$ENV_FILE" || true
grep -q '^PUBLIC_BASE_URL=' "$ENV_FILE" || echo "PUBLIC_BASE_URL=https://$DOMAIN" >> "$ENV_FILE"
chown "$APP_USER:$APP_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"
mkdir -p "$APP_DIR/backend/data"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/backend/data"

echo "==> 7/8  systemd service"
cp "$APP_DIR/deploy/brandshield.service" /etc/systemd/system/brandshield.service
systemctl daemon-reload
systemctl enable --now brandshield

echo "==> 8/8  Caddy (HTTPS + password gate)"
if ! command -v caddy &>/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy
fi

read -rsp "Choose a dashboard password: " DASH_PASS; echo
HASH=$(caddy hash-password --plaintext "$DASH_PASS")
sed -e "s|{{DOMAIN}}|$DOMAIN|g" -e "s|{{EMAIL}}|$EMAIL|g" -e "s|{{HASH}}|$HASH|g" \
    "$APP_DIR/deploy/Caddyfile.template" > /etc/caddy/Caddyfile
systemctl reload caddy || systemctl restart caddy

ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 80,443/tcp >/dev/null 2>&1 || true
yes | ufw enable >/dev/null 2>&1 || true

echo
echo "================================================================"
echo " BrandShield AI is live at:  https://$DOMAIN"
echo " Username: admin    Password: (the one you just typed)"
echo
echo " Logs:     journalctl -u brandshield -f"
echo " Restart:  systemctl restart brandshield"
echo " First start downloads nothing more, but give it ~60s to load the model."
echo "================================================================"
