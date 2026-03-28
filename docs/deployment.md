---
layout: default
title: Deployment
---

# Deployment Guide

Phixr runs as a set of containers: the Phixr bot, an OpenCode server, Redis for session state, and optionally PostgreSQL.

## Architecture Overview

```
                          +-----------------+
GitLab Webhooks --------> |   Phixr Bot     | ------> GitLab API
                          |   (FastAPI)     |
                          +-------+---------+
                                  |
                    +-------------+-------------+
                    |             |             |
              +-----+----+ +-----+----+ +------+-----+
              | OpenCode  | |  Redis   | | PostgreSQL |
              |  Server   | | (state)  | | (optional) |
              +-----------+ +----------+ +------------+
```

## Container Deployment (Recommended)

### Prerequisites

- Podman or Docker with Compose support
- GitLab instance accessible from the container network
- `.env.local` configured (see [Quickstart](quickstart))

### Start All Services

```bash
podman compose --profile phase-2 up -d
```

This starts:
- **opencode-server** -- AI coding engine (port 4096)
- **redis** -- Session state persistence (port 6379)
- **postgres** -- Future session history (port 5432)
- **phixr** -- The bot itself (port 8000)

### Check Status

```bash
podman ps --format "table {% raw %}{{.Names}}\t{{.Status}}{% endraw %}"
```

All services should show "Up" with opencode-server and redis showing "(healthy)".

### View Logs

```bash
# All services
podman compose --profile phase-2 logs -f

# Specific service
podman logs -f phixr_phixr_1
```

### Stop

```bash
podman compose --profile phase-2 down
```

### Rebuild After Code Changes

```bash
podman compose --profile phase-2 build
podman compose --profile phase-2 up -d
```

## Custom Domain Setup

Phixr generates links to the OpenCode web UI in GitLab comments. By default, these point to `localhost:4096`. For production, configure a public URL.

### Configure the Public OpenCode URL

In `.env.local`:

```bash
# Internal URL (Docker service name, used for API calls between containers)
PHIXR_SANDBOX_OPENCODE_SERVER_URL=http://opencode-server:4096

# Public URL (what users click in GitLab comments)
PHIXR_SANDBOX_OPENCODE_PUBLIC_URL=https://opencode.example.com
```

For the Phixr bot itself:

```bash
PHIXR_API_URL=https://phixr.example.com
```

### Reverse Proxy (nginx example)

Put both Phixr and OpenCode behind a reverse proxy:

```nginx
# Phixr API + webhooks
server {
    listen 443 ssl;
    server_name phixr.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support for vibe rooms
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# OpenCode web UI
server {
    listen 443 ssl;
    server_name opencode.example.com;

    location / {
        proxy_pass http://localhost:4096;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }
}
```

### GitLab Webhook URL

Update the webhook in GitLab to point to your public Phixr URL:

```
https://phixr.example.com/webhooks/gitlab
```

## Podman Rootless Notes

Phixr is designed for Podman rootless. A few things to be aware of:

- **SELinux**: Volume mounts use `:Z` labels for proper SELinux context
- **UID mapping**: The container runs as root inside the user namespace, which maps to your host UID
- **Podman socket**: Mounted at `/run/podman/podman.sock` inside the container

If you see permission errors on Fedora/RHEL, ensure the `:Z` labels are present on volume mounts in `docker-compose.yml`.

## Production Checklist

- [ ] Set strong `WEBHOOK_SECRET` (not the default)
- [ ] Configure `PHIXR_SANDBOX_OPENCODE_PUBLIC_URL` for correct session links
- [ ] Set `PHIXR_API_URL` to the public-facing Phixr URL
- [ ] Set `LOG_LEVEL=INFO` (not DEBUG)
- [ ] Set up TLS termination via reverse proxy
- [ ] Configure Redis persistence (`appendonly yes` in redis.conf)
- [ ] Set `PHIXR_SANDBOX_TIMEOUT_MINUTES` appropriate for your workload
- [ ] Set `PHIXR_SANDBOX_MAX_SESSIONS` based on available resources
- [ ] Verify GitLab webhook connectivity from Phixr container
- [ ] Test a full session lifecycle (create, message, end)

## Health Checks

```bash
# Phixr health
curl https://phixr.example.com/health

# Sandbox health (includes OpenCode + Redis status)
curl https://phixr.example.com/api/v1/sandbox/health

# Session list
curl https://phixr.example.com/api/v1/sessions
```
