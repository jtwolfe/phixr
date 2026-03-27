# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Phixr is a GitLab-integrated AI coding platform that bridges GitLab's workflow with OpenCode's web UI. It runs as a FastAPI bot that listens for GitLab webhooks and responds to `@phixr` mentions or `/ai-*` slash commands in issue comments.

Two operating modes:
- **Independent Mode**: Comment-driven automation — AI creates branches, implements changes, commits, and opens MRs autonomously
- **Vibe Mode**: Shared-visibility collaborative sessions — multiple users observe the same OpenCode session in real-time

## Commands

```bash
# Activate the venv first
source venv/bin/activate

# Run the application
python -m phixr.main

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run a single test file
pytest tests/unit/test_sandbox_config.py -v

# Run a single test class
pytest tests/unit/test_sandbox_config.py::TestSandboxConfig -v

# Run with coverage
pytest --cov=phixr --cov-report=html

# Run with Podman Compose
podman compose up

# Run with Phase 2 services (OpenCode server, etc.)
podman compose --profile phase-2 up
```

## Architecture

### Entry Point & Request Flow

`phixr/main.py` — FastAPI app. On startup, initializes GitLab client, registers webhook routes, and sets up OpenCode integration.

```
GitLab Issue Comment
  → POST /webhooks/gitlab
  → WebhookValidator (HMAC signature check)
  → CommentHandler.handle_issue_comment()
  → CommandParser (recognizes /ai-* commands and @phixr-bot mentions)
  → Context extraction (GitLab issue details, repo state)
  → OpenCodeIntegrationService.create_session()
    → Creates session on OpenCode server via HTTP API
    → Sends prompt with issue context via prompt_async
    → Creates vibe room for shared visibility
  → monitor_session() (background task)
    → SSE event stream from OpenCode server
    → Auto-approves tool permissions
    → Detects completion (session goes idle)
    → Posts results back to GitLab as comment
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `phixr/handlers/comment_handler.py` | Webhook event handlers — routes `/ai-*` commands |
| `phixr/commands/parser.py` | Parses natural language and `/ai-*` slash commands |
| `phixr/integration/opencode_integration_service.py` | Orchestrates OpenCode sessions, SSE monitoring, GitLab reporting |
| `phixr/bridge/opencode_client.py` | Async HTTP + SSE client for OpenCode's REST API |
| `phixr/git/branch_manager.py` | Creates `ai-work/issue-{id}` branches, checks for existing MRs |
| `phixr/context/` | Extracts issue details from GitLab |
| `phixr/collaboration/vibe_room_manager.py` | Vibe room state management for multi-user sessions |
| `phixr/config/settings.py` | Pydantic settings loaded from environment |
| `phixr/webhooks/` | Webhook routing and validation |

### OpenCode Integration

Phixr communicates with OpenCode via its HTTP API (default port 4096):

- **Session CRUD**: `POST/GET/DELETE /session/`
- **Async prompts**: `POST /session/{id}/prompt_async` (fire-and-forget, returns 204)
- **SSE events**: `GET /event` (real-time: message updates, tool execution, permission requests)
- **Permissions**: `POST /permission/{id}/reply` (auto-approve tool execution)
- **Messages**: `GET /session/{id}/message` (retrieve conversation history)

Context is injected via the `system` field in prompt requests (custom system instructions per-message).

### Session Model

```python
Session(
    id="sess-{issue_id}-{timestamp}",
    branch="ai-work/issue-{id}",
    container_id=opencode_session_id,  # maps to OpenCode session
    status=SessionStatus,
    mode=ExecutionMode,  # BUILD / PLAN / REVIEW
)
```

## Key Environment Variables

Copy `.env.example` to `.env.local` before running locally.

| Variable | Default | Purpose |
|----------|---------|---------|
| `GITLAB_URL` | `http://192.168.1.145:8080` | GitLab instance |
| `GITLAB_BOT_TOKEN` | — | Bot user PAT |
| `WEBHOOK_SECRET` | — | HMAC webhook validation |
| `OPENCODE_SERVER_URL` | `http://localhost:4096` | OpenCode server |
| `PHIXR_API_URL` | — | Public URL for vibe room links |
| `POSTGRES_URL` | — | Optional PostgreSQL |
| `REDIS_URL` | — | Optional Redis |

## Test Configuration

`pytest.ini` configures asyncio mode and test markers. Tests use `pytest-asyncio`; mark async tests with `@pytest.mark.asyncio`. Docker-dependent tests are marked `@pytest.mark.docker` and skipped by default without a running Docker daemon.

## Docs

Primary references for design intent and requirements:
- `docs/PROJECT_GOALS.md` — current vision and feature requirements
- `docs/ARCHITECTURE.md` — technical architecture details
- `docs/GETTING_STARTED.md` — setup and installation guide
- OpenCode source: `opencodecode/` — full source for understanding the API surface
