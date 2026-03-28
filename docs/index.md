---
layout: default
title: Home
---

# Phixr

**Seamless GitLab-AI Integration Platform**

Phixr bridges GitLab's issue workflow with [OpenCode](https://opencode.ai)'s AI coding sessions. GitLab issues become persistent AI sessions. Comments become messages. Three commands total.

```
Alice:   @phixr-bot /session
Phixr:   Session started. Branch: ai-work/issue-42

Alice:   @phixr-bot add user authentication with JWT tokens
Phixr:   [implements changes, posts summary with diff stats]

Alice:   @phixr-bot push your changes and create an MR
Phixr:   [pushes to branch, creates merge request, posts link]

Alice:   @phixr-bot /end
Phixr:   Session ended.
```

## How It Works

1. **Start a session** on any GitLab issue with `@phixr-bot /session`
2. **Talk to the AI** by mentioning `@phixr-bot` in issue comments
3. **Watch it work** with `--vibe` flag for a live OpenCode UI link
4. **End the session** with `@phixr-bot /end` when you're done

The AI reads the issue, clones the repo, creates a working branch, and handles everything from planning to implementation. All through natural conversation in GitLab comments.

## Key Features

- **Persistent sessions** -- iterate across multiple comments, the AI remembers everything
- **One session per issue** -- clean resource management, no confusion
- **Automatic branch management** -- each issue gets a dedicated `ai-work/issue-{id}` branch
- **Vibe mode** -- get a live link to the OpenCode web UI for real-time observation
- **Redis-backed state** -- sessions survive restarts, in-memory fallback for simple deployments
- **Enterprise ready** -- self-hosted, private models, no data leaves your infrastructure

## Quick Links

- [Quickstart Guide](quickstart) -- get running in 10 minutes
- [Usage Guide](usage) -- commands, workflows, and examples
- [Deployment Guide](deployment) -- production deployment with Podman/Docker
- [Architecture](architecture) -- how it all fits together
- [Development](development) -- contributing and local development
- [Configuration Reference](configuration) -- all environment variables
