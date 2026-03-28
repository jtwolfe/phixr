# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Phixr seamlessly bridges GitLab's issue workflow with OpenCode's AI coding sessions. It runs as a FastAPI bot that listens for GitLab webhooks and responds to `@phixr` mentions in issue comments.

**Core concept:** GitLab issues are OpenCode sessions. Comments are messages. Three commands total.

Two operating modes:
- **Independent Mode**: Comment-driven -- AI works autonomously, posts results back to the issue
- **Vibe Mode**: `@phixr /session --vibe` -- returns a live OpenCode UI link for interactive use

## User Interaction

| Input | What Happens |
|-------|-------------|
| `@phixr /session` | Start a persistent session (one per issue) |
| `@phixr /session --vibe` | Start session + get live OpenCode UI link |
| `@phixr <any message>` | Forward to active session |
| `@phixr /end` | Close session |

No mode selection -- the AI reads the issue and figures out what to do.

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
pytest tests/unit/test_command_parser.py -v

# Run a single test class
pytest tests/unit/test_command_parser.py::TestCommandParser -v

# Run with coverage
pytest --cov=phixr --cov-report=html

# Run with Podman Compose
podman compose --profile full-stack up -d
```

## Architecture

### Entry Point & Request Flow

`phixr/main.py` -- FastAPI app. On startup, initializes GitLab client, registers webhook routes, and sets up OpenCode integration.

```
GitLab Issue Comment (@phixr ...)
  -> POST /webhooks/gitlab
  -> WebhookValidator (token check)
  -> CommentHandler.handle_issue_comment()
  -> CommandParser.parse()
    |-- /session [--vibe]  -> create OpenCode session, start monitoring
    |-- /end               -> stop session, clean up
    +-- <message>          -> forward to active session via send_followup()
  -> monitor_session() (background task)
    -> SSE event stream from OpenCode
    -> Auto-approves permissions and questions
    -> Detects idle -> posts results to GitLab
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `phixr/handlers/comment_handler.py` | Routes `@phixr` interactions: session start, message forward, session end |
| `phixr/commands/parser.py` | Parses `/session`, `/end`, and bare `@phixr` messages |
| `phixr/integration/opencode_integration_service.py` | Orchestrates sessions, forwards messages, monitors completion, reports to GitLab |
| `phixr/bridge/opencode_client.py` | Async HTTP + SSE client for OpenCode's REST API |
| `phixr/git/branch_manager.py` | Creates `ai-work/issue-{id}` branches, checks for existing MRs |
| `phixr/context/` | Extracts issue details from GitLab |
| `phixr/collaboration/vibe_room_manager.py` | Vibe room state management |
| `phixr/config/settings.py` | Pydantic settings loaded from environment |
| `phixr/webhooks/` | Webhook routing and validation |

### OpenCode Integration

Phixr communicates with OpenCode via its HTTP API (default port 4096):

- **Session CRUD**: `POST/GET/DELETE /session` (no trailing slashes)
- **Async prompts**: `POST /session/{id}/prompt_async` (fire-and-forget, returns 204)
- **SSE events**: `GET /event` (real-time: message updates, tool execution, permission requests)
- **Permissions**: `POST /permission/{id}/reply` (auto-approve tool execution)
- **Questions**: `POST /question/{id}/reply` (auto-answer with first option)
- **Messages**: `GET /session/{id}/message` (retrieve conversation history)
- **Status**: `GET /session/status` (idle = absent from dict)

Context is injected via the `system` field in prompt requests.

### Session Model

```python
Session(
    id="sess-{issue_id}-{timestamp}",
    branch="ai-work/issue-{id}",
    container_id=opencode_session_id,
    status=SessionStatus,  # RUNNING, COMPLETED, TIMEOUT, ERROR, STOPPED
)
```

One session per issue enforced via `issue_sessions` dict in the integration service.

## Key Environment Variables

Copy `.env.example` to `.env.local` before running locally.

| Variable | Default | Purpose |
|----------|---------|---------|
| `GITLAB_URL` | `http://localhost:8080` | GitLab instance |
| `GITLAB_BOT_TOKEN` | -- | Bot user PAT |
| `WEBHOOK_SECRET` | -- | Webhook validation |
| `PHIXR_SANDBOX_OPENCODE_SERVER_URL` | `http://localhost:4096` | OpenCode server |
| `PHIXR_SANDBOX_GIT_PROVIDER_TOKEN` | -- | Git token for repo cloning |
| `PHIXR_API_URL` | -- | Public URL for vibe room links |

## Test Configuration

`pytest.ini` configures asyncio mode and test markers. Tests use `pytest-asyncio`; mark async tests with `@pytest.mark.asyncio`. Docker-dependent tests are marked `@pytest.mark.docker` and skipped by default without a running Docker daemon.

## Docs

Primary references for design intent and requirements:
- `docs/PROJECT_GOALS.md` -- current vision and feature requirements
- `docs/ARCHITECTURE.md` -- technical architecture details
- `docs/GETTING_STARTED.md` -- setup and installation guide
