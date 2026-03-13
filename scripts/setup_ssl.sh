#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# setup_ssl.sh — One-time HTTPS setup for Oracle VM
#
# Usage:
#   chmod +x scripts/setup_ssl.sh
#   ./scripts/setup_ssl.sh  socialmediaagent.duckdns.org  you@email.com
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${1:?Usage: $0 <domain> <email>}"
EMAIL="${2:?Usage: $0 <domain> <email>}"
PROJECT_DIR="$HOME/SocialMediaAgent"

echo "══════════════════════════════════════════"
echo "  Setting up HTTPS for: $DOMAIN"
echo "══════════════════════════════════════════"

cd "$PROJECT_DIR"

# ── Step 1: Replace ${DOMAIN} placeholder in nginx config ──
echo "[1/5] Configuring Nginx for $DOMAIN ..."
# Start with HTTP-only config for cert issuance
cp nginx/conf.d/default-http-only.conf.template nginx/conf.d/active.conf
sed -i "s|\${DOMAIN}|$DOMAIN|g" nginx/conf.d/active.conf
# Prepare the HTTPS config (used after cert is obtained)
cp nginx/conf.d/default.conf.template nginx/conf.d/https.conf
sed -i "s|\${DOMAIN}|$DOMAIN|g" nginx/conf.d/https.conf

# ── Step 2: Update .env with HTTPS redirect URI ──
echo "[2/5] Updating .env with HTTPS redirect ..."
sed -i "s|^META_REDIRECT_URI=.*|META_REDIRECT_URI=https://$DOMAIN/api/auth/meta/callback|" .env

# ── Step 3: Open firewall ports 80 + 443 ──
echo "[3/5] Opening firewall ports 80 and 443 ..."
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT 2>/dev/null || true

# ── Step 4: Start containers with HTTP-only nginx ──
echo "[4/5] Starting services (HTTP mode) ..."
sudo docker compose up -d --build

echo "Waiting 5s for Nginx to start ..."
sleep 5

# ── Step 5: Obtain SSL certificate ──
echo "[5/5] Requesting Let's Encrypt certificate ..."
sudo docker compose run --rm --entrypoint certbot certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  -d "$DOMAIN"

# ── Switch to HTTPS config and reload ──
echo "Switching Nginx to HTTPS mode ..."
mv nginx/conf.d/https.conf nginx/conf.d/active.conf
sudo docker compose exec nginx nginx -s reload

echo ""
echo "══════════════════════════════════════════"
echo "  HTTPS is live! https://$DOMAIN"
echo "══════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Add https://$DOMAIN/api/auth/meta/callback"
echo "     to Facebook Developer Console → Valid OAuth Redirect URIs"
echo ""
echo "  2. Set up auto-renewal (add to crontab):"
echo "     0 3 * * 0 cd $PROJECT_DIR && sudo docker compose run --rm --entrypoint certbot certbot renew && sudo docker compose exec nginx nginx -s reload"
