---
layout: default
title: Quickstart
---

# Quickstart

Get Phixr running and connected to your GitLab instance in about 10 minutes.

## Prerequisites

- Python 3.11+ (for local dev) or Podman/Docker (for containerized deployment)
- A GitLab instance with admin access
- A GitLab bot user with API token

## 1. Clone and Configure

```bash
git clone https://github.com/your-org/phixr.git
cd phixr
cp .env.example .env.local
```

Edit `.env.local` with your GitLab details:

```bash
GITLAB_URL=http://your-gitlab-instance:8080
GITLAB_BOT_TOKEN=glpat-your-bot-token-here
GITLAB_ROOT_TOKEN=glpat-your-root-token-here
WEBHOOK_SECRET=your-webhook-secret
```

## 2. Create the Bot User

If you don't have a bot user yet:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/setup_bot_user.py --gitlab-url http://your-gitlab-instance:8080
```

The script creates the `phixr-bot` user and outputs a personal access token. Add it to your `.env.local` as `GITLAB_BOT_TOKEN`.

## 3. Run Phixr

**Option A: Local development (bare Python)**

```bash
source venv/bin/activate
python -m phixr.main
```

**Option B: Containerized (recommended for testing/production)**

```bash
podman compose --profile phase-2 up -d
```

This starts all services: Phixr, OpenCode server, Redis, and PostgreSQL.

## 4. Configure GitLab Webhook

In your GitLab project:

1. Go to **Settings > Webhooks**
2. URL: `http://your-phixr-host:8000/webhooks/gitlab`
3. Secret: the `WEBHOOK_SECRET` from your `.env.local`
4. Events: check **Comments** and **Issues events**
5. Save

## 5. Test It

Open an issue in your GitLab project and comment:

```
@phixr-bot /session
```

Phixr should reply confirming the session started. Then try:

```
@phixr-bot what files are in this repository?
```

## Verify Health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/sandbox/health
```

Both should return `"status": "healthy"`.

## Next Steps

- [Usage Guide](usage) -- learn the full command set
- [Deployment Guide](deployment) -- production setup with custom domains
- [Configuration Reference](configuration) -- tune every setting
