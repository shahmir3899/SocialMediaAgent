# Oracle Cloud Deployment Guide

## Infrastructure Overview

| Component | Value |
|-----------|-------|
| **VM IP** | `161.153.110.194` |
| **Domain** | `socialmediaagent.duckdns.org` |
| **SSH Key** | `D:\Personal\socialmediaagent\ssh-key-2026-03-12.key` |
| **SSH User** | `ubuntu` |
| **OS** | Ubuntu (Oracle Cloud Free Tier) |
| **App Path on VM** | `~/SocialMediaAgent` |
| **GitHub Repo** | `https://github.com/shahmir3899/SocialMediaAgent.git` |
| **Branch** | `main` |

## Services (Docker Compose)

| Service | Role | Ports |
|---------|------|-------|
| **nginx** | Reverse proxy + SSL termination | 80, 443 (public) |
| **app** | FastAPI web server | 8000 (internal) |
| **celery-worker** | Async task processing | — |
| **celery-beat** | Scheduled task triggers | — |
| **certbot** | SSL certificate renewal | — |
| **db** | PostgreSQL 16 (unused, app uses Neon) | 5432 (internal) |
| **redis** | Redis 7 (unused, app uses Upstash) | 6379 (internal) |

## External Services

| Service | Purpose | Dashboard |
|---------|---------|-----------|
| **Neon** | PostgreSQL database | https://console.neon.tech |
| **Upstash** | Redis (Celery broker/backend) | https://console.upstash.com |
| **Groq** | LLM (Llama 3.3-70b) | https://console.groq.com |
| **Pollinations.ai** | Image generation (free, no key) | https://pollinations.ai |
| **DuckDNS** | Free domain → VM IP | https://www.duckdns.org |
| **Let's Encrypt** | SSL certificate (expires 2026-06-10) | — |
| **Meta/Facebook** | Social media publishing | https://developers.facebook.com |

## .env on Oracle

The `.env` on Oracle (`~/SocialMediaAgent/.env`) differs from local in these overrides:
```
APP_ENV=production
DEBUG=false
SECRET_KEY=<secure-random-key>
META_REDIRECT_URI=https://socialmediaagent.duckdns.org/api/auth/meta/callback
```

---

## Quick Reference Commands

### SSH into the VM

```powershell
ssh -i "D:\Personal\socialmediaagent\ssh-key-2026-03-12.key" ubuntu@161.153.110.194
```

### Check Connectivity

**From PowerShell (local):**

```powershell
# Test if port 443 is reachable
Test-NetConnection 161.153.110.194 -Port 443

# Test HTTPS health endpoint
Invoke-WebRequest -Uri "https://socialmediaagent.duckdns.org/health" -TimeoutSec 10

# Quick SSH test
ssh -o ConnectTimeout=10 -i "D:\Personal\socialmediaagent\ssh-key-2026-03-12.key" ubuntu@161.153.110.194 "echo ok"
```

**From the VM (after SSH):**

```bash
# Check all containers
sudo docker compose ps

# Check app logs
sudo docker compose logs --tail=50 app

# Check celery worker logs
sudo docker compose logs --tail=50 celery-worker

# Check celery beat logs
sudo docker compose logs --tail=50 celery-beat

# Check nginx logs
sudo docker compose logs --tail=50 nginx

# Health check from inside
curl -s http://localhost:8000/health
```

### Push Code Changes (Full Workflow)

**Step 1: Commit and push locally (PowerShell):**

```powershell
cd D:\Personal\socialmediaagent
git add -A
git commit -m "description of changes"
git push origin main
```

**Step 2: Deploy on Oracle (one-liner from PowerShell):**

```powershell
ssh -i "D:\Personal\socialmediaagent\ssh-key-2026-03-12.key" ubuntu@161.153.110.194 "cd ~/SocialMediaAgent && git pull origin main && sudo docker compose up -d --build && sudo docker compose ps"
```

**Or step-by-step after SSH:**

```bash
cd ~/SocialMediaAgent
git pull origin main
sudo docker compose up -d --build
sudo docker compose ps
```

### Restart All Services (without rebuild)

```bash
cd ~/SocialMediaAgent
sudo docker compose restart
sudo docker compose ps
```

### Restart a Single Service

```bash
sudo docker compose restart app          # just the FastAPI app
sudo docker compose restart celery-worker # just the worker
sudo docker compose restart nginx         # just nginx
```

### View Real-Time Logs

```bash
sudo docker compose logs -f app celery-worker celery-beat
```

---

## Troubleshooting

### VM Unreachable (SSH/HTTPS timeout)

1. **Check VM status**: Oracle Console → Compute → Instances → check if Running or Stopped
2. **If Stopped**: Click "Start" — Oracle Free Tier may reclaim idle Always Free instances
3. **If Running but unreachable**:
   - Click "Reboot" from the Console
   - Check VCN → Security Lists → Ingress Rules include ports 22, 80, 443
   - Check VCN → Route Tables → has `0.0.0.0/0` → Internet Gateway

### Containers Not Starting

```bash
cd ~/SocialMediaAgent
sudo docker compose down
sudo docker compose up -d --build
sudo docker compose logs --tail=100
```

### SSL Certificate Renewal

Certificate expires **2026-06-10**. To renew:

```bash
cd ~/SocialMediaAgent
sudo docker compose run --rm --entrypoint certbot certbot renew
sudo docker compose exec nginx nginx -s reload
```

To automate (add to crontab on VM):

```bash
crontab -e
# Add this line:
0 3 * * 0 cd ~/SocialMediaAgent && sudo docker compose run --rm --entrypoint certbot certbot renew && sudo docker compose exec nginx nginx -s reload
```

### Nginx Config

- **Live config on VM**: `~/SocialMediaAgent/nginx/conf.d/active.conf`
- **Templates in repo**: `nginx/conf.d/default.conf` (HTTPS), `nginx/conf.d/default-http-only.conf` (HTTP)
- `active.conf` is in `.gitignore` — it's generated on the server

### Updating .env on Oracle

The Oracle `.env` is **not in git**. To update it:

```powershell
# Copy local .env to Oracle (then manually edit production overrides)
scp -i "D:\Personal\socialmediaagent\ssh-key-2026-03-12.key" .env ubuntu@161.153.110.194:~/SocialMediaAgent/.env
```

Then SSH in and fix production values:

```bash
cd ~/SocialMediaAgent
nano .env
# Change: APP_ENV=production, DEBUG=false, META_REDIRECT_URI=https://...
sudo docker compose up -d --build
```

---

## Celery Beat Schedule

| Task | Interval | Purpose |
|------|----------|---------|
| `generate-daily-posts` | 24 hours | Generate daily content for all accounts |
| `schedule-ready-posts` | 5 minutes | Assign times to APPROVED posts |
| `publish-scheduled-posts` | 60 seconds | Publish posts whose time has come |
| `retry-failed-posts` | 5 minutes | Retry any failed publications |

## Oracle Security List (Ingress Rules)

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | 0.0.0.0/0 | SSH |
| 80 | TCP | 0.0.0.0/0 | HTTP (redirects to HTTPS) |
| 443 | TCP | 0.0.0.0/0 | HTTPS |
| 8000 | TCP | 0.0.0.0/0 | *(can be removed — nginx handles traffic)* |
