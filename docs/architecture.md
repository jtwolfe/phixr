---
layout: default
title: Architecture
---

# Architecture

## System Overview

Phixr is a FastAPI application that bridges GitLab's issue workflow with OpenCode's AI coding sessions. It translates GitLab webhooks into OpenCode API calls and posts results back as issue comments.

## Request Flow

```
GitLab Issue Comment (@phixr ...)
  --> POST /webhooks/gitlab
  --> WebhookValidator (token check)
  --> CommentHandler.handle_issue_comment()
  --> CommandParser.parse()
    |-- /session [--vibe]  --> _handle_session_start()
    |-- /end               --> _handle_session_end()
    +-- <message>          --> _handle_message() --> send_followup()
```

### Session Creation

```
_handle_session_start()
  --> ContextExtractor.extract_issue_context()
      (issue details, repo URL, branch, comments)
  --> OpenCodeIntegrationService.create_session()
      --> POST /session (OpenCode API -- creates AI session)
      --> POST /session/{id}/prompt_async (inject issue context)
      --> VibeRoomManager.create_room() (if --vibe)
  --> monitor_session() (background asyncio task)
      --> GET /event (SSE stream -- real-time events)
      --> Auto-approve permissions and questions
      --> Detect idle --> post results to GitLab
```

### Message Forwarding

```
_handle_message()
  --> get_active_session_for_issue()
  --> OpenCodeIntegrationService.send_followup()
      --> POST /session/{id}/prompt_async
```

## Core Components

### GitLab Integration Layer

| Module | File | Role |
|--------|------|------|
| Webhook Handler | `webhooks/gitlab_webhook.py` | Receives GitLab note events |
| Command Parser | `commands/parser.py` | Parses `/session`, `/end`, and message passthrough |
| Comment Handler | `handlers/comment_handler.py` | Routes commands to session lifecycle methods |
| GitLab Client | `utils/gitlab_client.py` | API wrapper for issues, comments, branches, MRs |

### Orchestration Layer

| Module | File | Role |
|--------|------|------|
| Integration Service | `integration/opencode_integration_service.py` | Core coordinator -- sessions, messages, monitoring, results |
| Session Store | `integration/session_store.py` | Redis-backed session persistence with in-memory fallback |
| Context Extractor | `context/extractor.py` | Pulls issue details, repo state, branch info |
| Branch Manager | `git/branch_manager.py` | Creates `ai-work/issue-{id}` branches |

### OpenCode Integration

| Module | File | Role |
|--------|------|------|
| OpenCode Client | `bridge/opencode_client.py` | HTTP + SSE client for OpenCode's REST API |
| Vibe Room Manager | `collaboration/vibe_room_manager.py` | Tracks collaborative viewing sessions |

## Key Mappings

| GitLab Concept | OpenCode Concept | Phixr Bridge |
|----------------|-----------------|--------------|
| Project | Repository | Shared repo URL (cloned via system instructions) |
| Issue | Session | `issue_sessions` mapping (one session per issue) |
| Issue comment | Session message | `send_followup()` via prompt API |
| Branch (`ai-work/issue-{id}`) | Working directory | System instructions with `git clone` + `git checkout` |

## Session Lifecycle

```
CREATED --> RUNNING --> COMPLETED (AI went idle)
                    --> TIMEOUT (exceeded time limit)
                    --> ERROR (OpenCode error)
                    --> STOPPED (user ran /end)
```

- **One session per issue** enforced via Redis-backed `issue_sessions` mapping
- Sessions persist in Redis with 24-hour TTL
- In-memory cache provides fast lookups for active monitoring tasks
- Issue mapping cleaned up on session end regardless of reason

## OpenCode API

Phixr communicates with OpenCode via its HTTP API (default port 4096):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/session` | POST | Create new session |
| `/session` | GET | List sessions |
| `/session/{id}` | DELETE | Delete session |
| `/session/{id}/prompt_async` | POST | Send prompt (fire-and-forget, returns 204) |
| `/session/{id}/message` | GET | Retrieve conversation history |
| `/session/status` | GET | Session status (idle = absent from dict) |
| `/event` | GET | SSE event stream (messages, tools, permissions) |
| `/permission/{id}/reply` | POST | Auto-approve tool execution |
| `/question/{id}/reply` | POST | Auto-answer with first option |
| `/global/health` | GET | Health check |

### SSE Events

The monitor task subscribes to `/event` and handles:
- `message.updated` -- track AI progress
- `permission.asked` -- auto-approve tool execution
- `question.asked` -- auto-answer with first option
- Events are filtered by session ID to avoid cross-session interference

### OpenCode Web UI URLs

The OpenCode web UI uses URL pattern: `/{base64url(directory)}/session/{sessionID}`

For sessions running in `/` (container root), the encoded directory is `Lw` (base64url of "/").

Example: `https://opencode.example.com/Lw/session/ses_abc123`

## Data Persistence

### Redis (Primary Store)

Keys and their purposes:

| Key Pattern | Value | TTL |
|-------------|-------|-----|
| `phixr:session:{id}` | JSON session data | 24h |
| `phixr:oc_id:{id}` | OpenCode session ID | 24h |
| `phixr:oc_slug:{id}` | OpenCode session slug | 24h |
| `phixr:issue:{project}:{issue}` | Phixr session ID | 24h |

### In-Memory Fallback

If Redis is unavailable, all data is stored in Python dicts. Functional but lost on restart.

## Technology Stack

- **Backend**: Python 3.11 + FastAPI + Uvicorn
- **OpenCode Communication**: httpx + httpx-sse
- **Session State**: Redis 7 (with in-memory fallback)
- **Git**: GitLab API (python-gitlab)
- **Containerization**: Podman rootless + Compose
- **Real-time**: SSE events (OpenCode) + WebSockets (vibe rooms, future)
