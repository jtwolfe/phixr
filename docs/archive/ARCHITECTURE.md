# Phixr Architecture

**Last Updated**: March 28, 2026

## System Overview

Phixr seamlessly bridges GitLab's issue workflow with OpenCode's AI coding sessions. GitLab issues become persistent OpenCode sessions; issue comments become session messages.

## Request Flow

```
GitLab Issue Comment (@phixr-bot ...)
  → POST /webhooks/gitlab
  → WebhookValidator (token check)
  → CommentHandler.handle_issue_comment()
  → CommandParser.parse()
    ├── /session [--vibe]  → _handle_session_start()
    ├── /end               → _handle_session_end()
    └── <message>          → _handle_message() → send_followup()

Session Creation:
  → ContextExtractor (issue details, repo state, branch)
  → OpenCodeIntegrationService.create_session()
    → POST /session (OpenCode API)
    → POST /session/{id}/prompt_async (initial prompt with issue context)
    → VibeRoomManager.create_room()
  → monitor_session() (background task)
    → GET /event (SSE stream)
    → Auto-approve permissions
    → Auto-answer questions
    → Detect idle → post results to GitLab

Message Forwarding:
  → OpenCodeIntegrationService.send_followup()
    → POST /session/{id}/prompt_async (follow-up message)
```

## Core Components

### 1. GitLab Integration Layer
- **Webhook Handler** (`webhooks/gitlab_webhook.py`): Receives GitLab note events
- **Command Parser** (`commands/parser.py`): Parses `@phixr-bot` interactions — `/session`, `/end`, or message passthrough
- **Comment Handler** (`handlers/comment_handler.py`): Routes parsed commands to session lifecycle methods
- **GitLab Client** (`utils/gitlab_client.py`): API interactions — issues, comments, branches, MRs

### 2. Orchestration Layer
- **Integration Service** (`integration/opencode_integration_service.py`): Core coordination — creates sessions, forwards messages, monitors completion, reports results
- **Context Extractor** (`context/extractor.py`): Pulls issue details, repo state, comments, and branch info
- **Branch Manager** (`git/branch_manager.py`): Creates `ai-work/issue-{id}` branches

### 3. OpenCode Integration
- **OpenCode Client** (`bridge/opencode_client.py`): HTTP + SSE client for OpenCode's REST API
- **Vibe Room Manager** (`collaboration/vibe_room_manager.py`): Tracks collaborative viewing sessions

### 4. Key Mappings

| GitLab Concept | OpenCode Concept | Phixr Bridge |
|----------------|-----------------|--------------|
| Project | Project | Shared repo URL |
| Issue | Session | `issue_sessions` dict (one session per issue) |
| Issue comment | Session message | `send_followup()` |
| Branch (`ai-work/issue-{id}`) | Working directory | System instructions with `git clone` |

## Session Lifecycle

```
CREATED → RUNNING → COMPLETED
                  → TIMEOUT (aborted after N minutes)
                  → ERROR (OpenCode error)
                  → STOPPED (user /end)
```

- **One session per issue** enforced by `issue_sessions` mapping
- Sessions persist until explicitly ended, timed out, or completed
- Issue mapping cleaned up on session end (any reason)

## Data Flow

### Context Injection
- System instructions injected via `system` field in prompt API
- Includes authenticated repo clone URL, branch checkout instructions
- Issue description, comments, and metadata in user prompt

### Session Monitoring
- Primary: SSE event stream (`GET /event`) with auto-reconnect
- Fallback: Status polling (`GET /session/status`) every 5s
- Auto-approves permissions (`POST /permission/{id}/reply`)
- Auto-answers questions (`POST /question/{id}/reply`)
- Idle detection: session absent from status dict = completed

## Technology Stack

- **Backend**: Python + FastAPI
- **OpenCode Communication**: httpx + httpx-sse
- **Git**: GitPython + GitLab API
- **Real-time**: SSE events (OpenCode) + WebSockets (vibe rooms, future)
- **Containerization**: Podman rootless

## Future Considerations

- **Multi-user vibe rooms**: Real-time WebSocket updates between users
- **External model management**: Pluggable model routing
- **Persistent storage**: PostgreSQL/Redis for session history
- **Natural language understanding**: Beyond pattern matching for smarter intent detection
