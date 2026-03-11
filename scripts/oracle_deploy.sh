#!/usr/bin/env bash
set -euo pipefail

# Oracle VM deploy script for Social Media Agent
# Usage examples:
#   bash scripts/oracle_deploy.sh --repo-url https://github.com/<user>/<repo>.git --branch main
#   bash scripts/oracle_deploy.sh --app-dir /opt/socialmediaagent

REPO_URL=""
BRANCH="main"
APP_DIR="$HOME/socialmediaagent"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url)
      REPO_URL="$2"
      shift 2
      ;;
    --branch)
      BRANCH="$2"
      shift 2
      ;;
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: $0 [--repo-url <url>] [--branch <name>] [--app-dir <path>]"
      exit 1
      ;;
  esac
done

echo "[1/6] Installing Docker and Compose plugin if missing..."
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y docker.io docker-compose-plugin git
fi

sudo systemctl enable docker
sudo systemctl start docker

if ! groups "$USER" | grep -q "\bdocker\b"; then
  sudo usermod -aG docker "$USER"
  echo "Added $USER to docker group. Re-login may be required for group change."
fi

echo "[2/6] Preparing application directory: $APP_DIR"
mkdir -p "$APP_DIR"

if [[ -n "$REPO_URL" ]]; then
  echo "[3/6] Syncing code from Git repository..."
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" fetch origin
    git -C "$APP_DIR" checkout "$BRANCH"
    git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
  else
    rm -rf "$APP_DIR"
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
  fi
else
  echo "[3/6] No --repo-url supplied. Assuming code already exists in $APP_DIR"
fi

cd "$APP_DIR"

if [[ ! -f ".env" ]]; then
  echo "[4/6] .env not found; creating from .env.example"
  cp .env.example .env
  echo "IMPORTANT: Edit $APP_DIR/.env with real values before production use."
fi

echo "[5/6] Building and starting services..."
docker compose up -d --build

echo "[6/6] Running database migrations..."
docker compose exec -T app alembic upgrade head

echo "Deployment complete."
echo "Check status: docker compose ps"
echo "Tail logs:     docker compose logs -f app"
