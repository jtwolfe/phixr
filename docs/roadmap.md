---
layout: default
title: Roadmap
---

# Roadmap

Phixr is under active development. This page tracks planned features and the direction of the project.

## Current Status

Phixr today supports:
- GitLab issue-driven AI sessions with OpenCode
- Independent mode (AI works autonomously) and Vibe mode (live UI link)
- Multi-provider AI (Ollama, Zen, OpenAI-compatible)
- Redis-backed session state with in-memory fallback
- Containerized deployment with Podman/Docker Compose

## Planned Features

### Multi-Provider Inference via LiteLLM

Replace the current direct provider configuration with a [LiteLLM](https://docs.litellm.ai/) proxy endpoint. This enables:

- **Unified API** -- single endpoint that routes to any LLM provider
- **Load balancing** -- distribute requests across multiple model instances
- **Fallback chains** -- automatically retry with a different provider/model on failure
- **Cost tracking** -- per-session and per-user token usage and cost reporting
- **Rate limiting** -- enforce quotas at the user, project, or organization level

### User Authentication via GitLab

Integrate user identity and access control through GitLab's authentication system:

- **GitLab JWT validation** -- verify user identity from webhook payloads and API requests
- **Project-level permissions** -- respect GitLab's role-based access (only maintainers can start sessions, etc.)
- **User quotas** -- per-user session limits and token budgets
- **Audit trail** -- log who started which session, what was requested, and resource usage

### Gitea Support

Extend Phixr beyond GitLab to support [Gitea](https://gitea.com/) as a git provider:

- **Gitea webhooks** -- listen for Gitea issue comment events
- **Gitea API** -- post comments, create branches, open pull requests
- **Shared command syntax** -- same `@phixr` commands work across platforms
- **Provider abstraction** -- clean separation between git platform and AI orchestration

### Additional Planned Improvements

- **Session history** -- PostgreSQL-backed session logs for review and replay
- **Merge request workflows** -- AI-assisted code review on MR comments
- **Multi-model routing** -- use different models for different task types (planning vs. implementation)
- **Webhook auto-registration** -- automatically configure GitLab/Gitea webhooks on first use
- **Session resume** -- reconnect to a previous session after Phixr restart
- **Metrics and observability** -- Prometheus metrics for session throughput, latency, and error rates

## Contributing

Phixr is open source. If you're interested in contributing to any of these features, check the [Development Guide](development) to get set up, then open an issue or pull request on [GitHub](https://github.com/jtwolfe/phixr).
