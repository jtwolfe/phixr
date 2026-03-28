---
layout: default
title: Quickstart
---

# Quickstart

Get Phixr running and connected to your GitLab instance in about 10 minutes.

## Prerequisites

- Python 3.11+ (for local dev) or Podman/Docker (for containerized deployment)
- A GitLab instance with admin access (for creating the bot user)
- An AI provider: [Ollama](https://ollama.com) (local, default), OpenCode Zen, or any OpenAI-compatible API

## 1. Clone and Install

```bash
git clone https://github.com/jtwolfe/phixr.git
cd phixr
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 2. Create the Bot User in GitLab

Phixr needs a dedicated GitLab user to post comments and manage branches.

**Option A: Use the setup script** (requires a root/admin personal access token):

```bash
python scripts/setup_bot_user.py --gitlab-url http://your-gitlab-instance:8080
```

The script will prompt for a root token, create the `phixr` user, and output a bot token.

**Option B: Create manually:**

1. Log into GitLab as admin
2. Go to **Admin Area > Users > New User**
3. Username: `phixr`, Name: `Phixr`, Email: `phixr@localhost`
4. Save, then go to the user's profile and create a **Personal Access Token** with scopes: `api`, `read_api`, `write_repository`
5. Copy the token

## 3. Configure Environment

```bash
cp .env.example .env.local
```

Edit `.env.local` with your values -- at minimum you need:

```bash
# Your GitLab instance
GITLAB_URL=http://your-gitlab-instance:8080

# Bot token from step 2
GITLAB_BOT_TOKEN=glpat-your-bot-token-here

# Webhook secret (choose any strong random string)
WEBHOOK_SECRET=your-webhook-secret

# Git token for cloning repos in sessions (usually same as bot token)
PHIXR_SANDBOX_GIT_PROVIDER_TOKEN=glpat-your-bot-token-here
```

The defaults work for everything else. See the [Configuration Reference](configuration) for all options.

## 4. Set Up the AI Provider

**Ollama (default, local):**

```bash
ollama pull qwen2.5-coder
```

No additional configuration needed -- Phixr defaults to Ollama on `localhost:11434`.

**Other providers:** See the provider examples in `.env.example` or the [Configuration Reference](configuration).

## 5. Configure GitLab Webhook

Phixr needs to receive GitLab events when someone mentions `@phixr` in an issue comment.

**Option A: Use the setup script** (creates an instance-level webhook):

```bash
bash scripts/setup-webhook.sh
```

This reads your `.env.local` and creates the webhook automatically.

**Option B: Configure manually** (project-level webhook):

1. In your GitLab project, go to **Settings > Webhooks**
2. URL: `http://your-phixr-host:8000/webhooks/gitlab`
3. Secret token: the `WEBHOOK_SECRET` from your `.env.local`
4. Trigger events: check **Comments** and **Issues events**
5. Click **Add webhook**

> **Note:** The script creates an *instance-level* webhook (all projects). Manual setup creates a *project-level* webhook (one project at a time). Either works.

## 6. Start Phixr

**Local development:**

```bash
source venv/bin/activate
python -m phixr.main
```

**Containerized (full stack with OpenCode, Redis, PostgreSQL):**

```bash
podman compose --profile full-stack up -d
```

## 7. Test It

Open an issue in your GitLab project and comment:

```
@phixr /session
```

Phixr should reply confirming the session started. Then try:

```
@phixr what files are in this repository?
```

## Verify Health

```bash
# Phixr is running
curl http://localhost:8000/health

# OpenCode integration is connected
curl http://localhost:8000/api/v1/sandbox/health
```

Both should return `"status": "healthy"`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "GITLAB_BOT_TOKEN not set" | Check `.env.local` exists and has the token |
| "Bot user 'phixr' not found" | Create the bot user (step 2) and ensure the username matches `BOT_USERNAME` |
| "Cannot connect to GitLab" | Verify `GITLAB_URL` is reachable from the Phixr host |
| Webhook not firing | Check the webhook URL is reachable from GitLab; test with GitLab's "Test" button |
| Session starts but AI doesn't respond | Verify your AI provider is running (e.g., `ollama list` for Ollama) |

## Next Steps

- [Usage Guide](usage) -- learn the full command set
- [Deployment Guide](deployment) -- production setup with custom domains
- [Configuration Reference](configuration) -- tune every setting
