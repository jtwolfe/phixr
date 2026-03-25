# Phase 1 Implementation Plan: Bot Infrastructure & Command Layer

## Overview
Phase 1 focuses on establishing the foundation for Phixr's bot layer - automated robot user creation, GitLab webhook integration, slash command handling, and context capture.

## Phase 1a: Robot User Setup & Automation

### Goals
- Create an automated process to set up a bot user in GitLab
- Manage bot credentials securely
- Enable bot authentication with proper scopes/permissions

### Deliverables
1. **Setup Script** (`scripts/setup_bot_user.py`)
   - Takes GitLab instance URL and admin token as input
   - Creates a new bot user (e.g., "phixr-bot")
   - Generates a personal access token for the bot
   - Stores credentials in secure config
   - Validates permissions

2. **Bot Configuration Module** (`phixr/config/bot_config.py`)
   - Manages bot credentials and connection details
   - Loads from environment variables or secure store
   - Validates required scopes

### Required Permissions for Bot
- `api` - For webhook creation and API access
- `read_api` - Read access to projects/issues/MRs
- `write_repository` - To create branches/commits for MRs
- `maintainer` - To be assigned to issues and comment

---

## Phase 1b: Bot Command Triggering System

### Goals
- Establish webhook receiving and processing
- Implement slash command parser
- Ensure bot only responds when assigned to an issue

### Deliverables
1. **Webhook Gateway** (`phixr/webhooks/gitlab_webhook.py`)
   - FastAPI endpoint to receive GitLab webhooks
   - Event validation and signature verification
   - Routes events to appropriate handlers

2. **Command Parser** (`phixr/commands/parser.py`)
   - Identifies slash commands in issue comments
   - Extracts command and arguments
   - Validates command syntax

3. **Issue Assignment Handler** (`phixr/handlers/assignment_handler.py`)
   - Tracks which issues the bot is assigned to
   - Only processes commands from assigned issues
   - Manages bot's assignee status

### Commands (Phase 1)
- `/ai-status` - Show current bot status and context
- `/ai-help` - List available commands
- `/ai-acknowledge` - Bot acknowledges it's ready
- (Implementation placeholders for future: `/ai-plan`, `/ai-implement`, etc.)

---

## Phase 1c: Issue Context Capture

### Goals
- Extract and structure full issue context
- Create context object that can be passed to OpenCode

### Deliverables
1. **Context Extractor** (`phixr/context/extractor.py`)
   - Fetches full issue details (title, description, labels, milestone)
   - Captures entire issue comment thread
   - Retrieves linked issues/epics if available
   - Collects repo metadata (language, structure hints)

2. **Context Model** (`phixr/models/issue_context.py`)
   - Dataclass/Pydantic model for normalized context
   - Supports serialization (JSON, environment variables)
   - Tracks context version for future updates

3. **Context Storage** (Redis/SQLite)
   - Temporary storage of session contexts
   - Maps session IDs to issue contexts
   - Supports context retrieval during OpenCode execution

---

## Phase 1d: OpenCode Integration Preparation

### Goals
- Design interface for passing context to OpenCode
- Prepare Docker containerization strategy
- Create placeholders for Phase 2 implementation

### Deliverables
1. **OpenCode Adapter** (`phixr/adapters/opencode_adapter.py`)
   - Interface definition for triggering OpenCode
   - Context serialization for OpenCode consumption
   - Response handling (future: MR creation, feedback)

2. **Docker Build Configuration** (`docker/opencode.Dockerfile`)
   - Preliminary Dockerfile for modified OpenCode
   - Build arguments for context injection
   - Entry point design

3. **Context-to-OpenCode Bridge** (`phixr/bridge/opencode_bridge.py`)
   - Converts Phixr context to OpenCode-compatible format
   - Manages OpenCode container lifecycle (start, monitor, stop)
   - Captures output/results

---

## Phase 1e: Web Terminal Access (Design Only)

### Goals
- Design the architecture for accessing OpenCode terminal via web UI
- Create placeholder for implementation in Phase 2

### Deliverables
1. **Web Terminal Design Document** (`docs/web_terminal_design.md`)
   - Architecture overview
   - Technology choices (xterm.js, WebSocket server, etc.)
   - Security considerations

---

## Technology Stack (Phase 1)

- **Backend**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL (session/context storage) + Redis (temporary state)
- **VCS Integration**: `python-gitlab` library
- **HTTP**: Uvicorn + FastAPI
- **Containerization**: Docker
- **Configuration**: Python-dotenv + Pydantic Settings

---

## Project Structure (Phase 1)

```
phixr/
├── phixr/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entrypoint
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py            # Pydantic settings
│   │   └── bot_config.py          # Bot-specific config
│   ├── models/
│   │   ├── __init__.py
│   │   ├── issue_context.py       # Context data model
│   │   └── command.py             # Command model
│   ├── webhooks/
│   │   ├── __init__.py
│   │   └── gitlab_webhook.py      # GitLab event receiver
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── assignment_handler.py  # Assignment tracking
│   │   └── comment_handler.py     # Comment event handler
│   ├── commands/
│   │   ├── __init__.py
│   │   └── parser.py              # Command parsing logic
│   ├── context/
│   │   ├── __init__.py
│   │   └── extractor.py           # Issue context extraction
│   ├── adapters/
│   │   ├── __init__.py
│   │   └── opencode_adapter.py    # OpenCode interface
│   ├── bridge/
│   │   ├── __init__.py
│   │   └── opencode_bridge.py     # Context-to-OpenCode
│   └── utils/
│       ├── __init__.py
│       ├── gitlab_client.py       # GitLab API wrapper
│       └── logger.py              # Logging setup
├── scripts/
│   ├── setup_bot_user.py          # Bot user creation script
│   └── requirements_scripts.txt
├── docker/
│   ├── Dockerfile                 # Main app container
│   └── opencode.Dockerfile        # OpenCode variant
├── docker-compose.yml             # Local dev environment
├── requirements.txt               # Python dependencies
├── .env.example                   # Example environment
├── .gitignore
├── README.md
├── DESIGN.md
└── docs/
    └── web_terminal_design.md     # Web terminal planning
```

---

## Implementation Roadmap

### Week 1: Foundation
- [ ] Project structure setup
- [ ] Dependencies and requirements.txt
- [ ] Configuration/settings module
- [ ] Basic FastAPI app scaffolding
- [ ] Docker Compose for local dev (PostgreSQL + Redis)

### Week 2: Bot User Setup
- [ ] setup_bot_user.py script
- [ ] GitLab client wrapper
- [ ] Bot configuration loading
- [ ] Tests for bot setup

### Week 3: Webhook & Commands
- [ ] GitLab webhook endpoint
- [ ] Webhook signature validation
- [ ] Command parser
- [ ] Basic command handlers (/ai-status, /ai-help, /ai-acknowledge)

### Week 4: Context & Integration
- [ ] Issue context extraction
- [ ] Context storage (Redis)
- [ ] OpenCode adapter skeleton
- [ ] Integration tests

---

## Success Criteria for Phase 1

✅ Bot user can be created automatically via script  
✅ Bot can receive GitLab webhook events  
✅ Slash commands work in issue comments  
✅ Bot only responds when assigned to an issue  
✅ Full issue context can be extracted and structured  
✅ System is designed to pass context to OpenCode in Phase 2  
✅ Web terminal architecture is documented for Phase 2  

---

## Next: Phase 2 (Future)
- Containerize modified OpenCode
- Context passing to OpenCode container
- OpenCode execution and monitoring
- Web terminal for OpenCode access
