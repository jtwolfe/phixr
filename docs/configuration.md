---
layout: default
title: Configuration
---

# Configuration Reference

All configuration is via environment variables. Copy `.env.example` to `.env.local` and edit.

## Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GITLAB_URL` | `http://192.168.1.145:8080` | Your GitLab instance URL |
| `GITLAB_BOT_TOKEN` | *(required)* | Personal access token for the bot user |
| `GITLAB_ROOT_TOKEN` | *(optional)* | Root token for access management (PAT rotation, user creation) |
| `BOT_USERNAME` | `phixr-bot` | GitLab username of the bot account |
| `BOT_EMAIL` | `phixr-bot@localhost` | Email for the bot account |

## Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | Bind address |
| `SERVER_PORT` | `8000` | Listen port |
| `PHIXR_API_URL` | `http://localhost:8000` | Public-facing Phixr URL (used in vibe room links) |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Webhook Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBHOOK_SECRET` | `phixr-webhook-secret` | Secret for validating GitLab webhooks |
| `WEBHOOK_URL` | `http://localhost:8000/webhooks/gitlab` | Webhook callback URL (configured in GitLab) |

## OpenCode / Sandbox Settings

These use the `PHIXR_SANDBOX_` prefix.

### Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `PHIXR_SANDBOX_OPENCODE_SERVER_URL` | `http://opencode-server:4096` | Internal OpenCode API URL |
| `PHIXR_SANDBOX_OPENCODE_PUBLIC_URL` | *(empty -- falls back to server URL)* | Public URL for session links in GitLab comments. **Set this in production** when the server URL is a Docker-internal hostname. |
| `PHIXR_SANDBOX_OPENCODE_ZEN_API_KEY` | *(empty)* | API key for OpenCode Zen model provider |

### Git Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `PHIXR_SANDBOX_GIT_PROVIDER_URL` | `http://192.168.1.145:8080` | Git provider URL |
| `PHIXR_SANDBOX_GIT_PROVIDER_TOKEN` | *(empty)* | Token for cloning private repositories |
| `PHIXR_SANDBOX_GIT_PROVIDER_TYPE` | `gitlab` | Git provider type (`gitlab`, `github`, `gitea`) |

### Resource Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `PHIXR_SANDBOX_MEMORY_LIMIT` | `2g` | Memory limit per session container |
| `PHIXR_SANDBOX_CPU_LIMIT` | `1.0` | CPU limit per session container |
| `PHIXR_SANDBOX_TIMEOUT_MINUTES` | `30` | Session timeout in minutes (1-480) |
| `PHIXR_SANDBOX_MAX_SESSIONS` | `10` | Maximum concurrent sessions (1-100) |

### Container Runtime

| Variable | Default | Description |
|----------|---------|-------------|
| `PHIXR_SANDBOX_DOCKER_HOST` | `unix:///run/user/1000/podman/podman.sock` | Container runtime socket |
| `PHIXR_SANDBOX_OPENCODE_IMAGE` | `ghcr.io/phixr/opencode:latest` | OpenCode container image |
| `PHIXR_SANDBOX_DOCKER_NETWORK` | `phixr-network` | Container network name |

### Model Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PHIXR_SANDBOX_MODEL` | `opencode/big-pickle` | Default LLM model |
| `PHIXR_SANDBOX_MODEL_TEMPERATURE` | `0.7` | Model temperature |
| `PHIXR_SANDBOX_MODEL_CONTEXT_WINDOW` | `4096` | Context window size |

## Data Stores

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Redis URL for session state. If Redis is unavailable, falls back to in-memory storage. |
| `PHIXR_SANDBOX_REDIS_URL` | `redis://redis:6379/1` | Redis URL for sandbox config (separate DB) |
| `POSTGRES_URL` | `postgresql://phixr:phixr@postgres:5432/phixr` | PostgreSQL URL (reserved for future use) |

## Docker Compose Environment

When running with `podman compose --profile phase-2`, the `docker-compose.yml` overrides these values for the container network:

| Variable | Container Override | Why |
|----------|-------------------|-----|
| `OPENCODE_SERVER_URL` | `http://opencode-server:4096` | Use Docker DNS instead of localhost |
| `PHIXR_API_URL` | `http://phixr-bot:8000` | Internal container name |
| `REDIS_URL` | `redis://redis:6379/0` | Redis service name |

All other values (tokens, secrets, GitLab URL) are read from `.env.local` without override.

## Example `.env.local`

```bash
# GitLab
GITLAB_URL=http://192.168.1.145:8080
GITLAB_BOT_TOKEN=glpat-your-token-here
GITLAB_ROOT_TOKEN=glpat-your-root-token-here
WEBHOOK_SECRET=a-strong-random-secret

# Server
PHIXR_API_URL=https://phixr.example.com
LOG_LEVEL=INFO

# OpenCode
PHIXR_SANDBOX_OPENCODE_SERVER_URL=http://localhost:4096
PHIXR_SANDBOX_OPENCODE_PUBLIC_URL=https://opencode.example.com
PHIXR_SANDBOX_GIT_PROVIDER_TOKEN=glpat-your-token-here
PHIXR_SANDBOX_OPENCODE_ZEN_API_KEY=sk-your-api-key

# Redis
REDIS_URL=redis://localhost:6379/0

# Limits
PHIXR_SANDBOX_TIMEOUT_MINUTES=30
PHIXR_SANDBOX_MAX_SESSIONS=10
```
