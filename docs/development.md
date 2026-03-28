---
layout: default
title: Development
---

# Development Guide

## Local Setup

```bash
git clone https://github.com/your-org/phixr.git
cd phixr
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy and configure environment:

```bash
cp .env.example .env.local
# Edit .env.local with your GitLab details
```

## Running Locally

**Bare Python** (fastest iteration):

```bash
source venv/bin/activate
python -m phixr.main
```

This starts Phixr on `http://localhost:8000`. Redis is optional -- the session store falls back to in-memory if unavailable.

**With containers** (full stack):

```bash
podman compose --profile phase-2 up -d
```

## Running Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Single test file
pytest tests/unit/test_comment_handler.py -v

# Single test class
pytest tests/unit/test_integration_service.py::TestSessionCreation -v

# With coverage
pytest --cov=phixr --cov-report=html
```

Tests use `pytest-asyncio` for async test support. Mark async tests with `@pytest.mark.asyncio`.

Docker-dependent tests are marked `@pytest.mark.docker` and skipped without a running Docker daemon.

## Project Structure

```
phixr/
  main.py                          # FastAPI app, routes, startup
  config/
    settings.py                    # Pydantic settings (from env vars)
    sandbox_config.py              # OpenCode/sandbox configuration
  handlers/
    comment_handler.py             # Routes @phixr interactions
  commands/
    parser.py                      # Parses /session, /end, messages
  integration/
    opencode_integration_service.py  # Core orchestration
    session_store.py               # Redis-backed session persistence
  bridge/
    opencode_client.py             # HTTP + SSE client for OpenCode API
  context/
    extractor.py                   # Issue context extraction from GitLab
  git/
    branch_manager.py              # Branch creation and MR checks
  collaboration/
    vibe_room_manager.py           # Vibe room state management
  models/
    execution_models.py            # Session, VibeRoom, etc.
    issue_context.py               # IssueContext dataclass
  utils/
    gitlab_client.py               # GitLab API wrapper
  webhooks/
    gitlab_webhook.py              # Webhook routing and validation
  web/
    templates/                     # Jinja2 templates (vibe room UI)
    static/                        # CSS, JS assets

tests/
  unit/                            # Unit tests (mocked dependencies)
  integration/                     # Integration tests (Docker required)
  conftest.py                      # Shared fixtures

docs/                              # Documentation (GitHub Pages site)
docker/                            # Dockerfiles
```

## Key Patterns

### Adding a New Command

1. Add pattern to `commands/parser.py` (regex + parse method)
2. Add handler method to `handlers/comment_handler.py`
3. Add route in `handle_issue_comment()` switch
4. Add tests in `tests/unit/test_command_parser.py` and `test_comment_handler.py`

### Session Store Access

The `SessionStore` provides Redis-backed persistence with dict fallback:

```python
# Write
store.save_session(session_id, session.model_dump())
store.set_opencode_id(session_id, oc_id)
store.set_issue_session(project_id, issue_id, session_id)

# Read
data = store.get_session(session_id)
oc_id = store.get_opencode_id(session_id)
session_id = store.get_issue_session(project_id, issue_id)

# Cleanup
store.clear_issue_session(project_id, issue_id)
store.clear_issue_session_by_session_id(session_id)
```

### OpenCode Client Usage

```python
# Create session
oc_session = await client.create_session()

# Send prompt
await client.send_prompt_async(session_id, prompt, system=system_instructions)

# Subscribe to events
async for event in client.subscribe_events():
    if event["type"] == "permission.asked":
        await client.reply_permission(perm_id, approved=True)

# Get messages
messages = await client.get_messages(session_id)
```

## Building the Docker Image

```bash
podman compose --profile phase-2 build
```

The Dockerfile is at `docker/Dockerfile`. It uses `python:3.11-slim` and installs from `requirements.txt`.

## Documentation Site

The `docs/` directory is a Jekyll site for GitHub Pages. To preview locally:

```bash
cd docs
bundle install  # first time only
bundle exec jekyll serve
```

Or just push to GitHub -- Pages builds automatically from the `docs/` folder on the main branch.
