# Phixr Architecture

**Last Updated**: March 27, 2026

## System Overview

Phixr is a hybrid AI coding platform that combines GitLab-native interaction with OpenCode's excellent web UI. The system supports two distinct modes of operation while maintaining a clean separation of concerns.

## Core Components

### 1. GitLab Integration Layer
- **Webhook Handler**: Receives GitLab events (comments, assignments, etc.)
- **Command Parser**: Understands natural language commands directed at `@phixr`
- **Comment Handler**: Processes commands and coordinates responses
- **GitLab Client**: Manages API interactions, branch creation, MRs, etc.

### 2. Orchestration Layer (Phixr Core)
- **Session Manager**: Manages independent and vibe mode sessions
- **Mode Router**: Determines whether to use independent or vibe mode
- **Context Extractor**: Pulls issue context and repository state
- **Plan Detector**: Identifies when AI has generated plans

### 3. OpenCode Integration
- **OpenCode WebUI**: Embedded for vibe mode (preserved as-is)
- **File-based Context Injection**: Reliable method for providing context
- **Session Manager**: Creates and manages OpenCode sessions per issue/branch
- **Vibe Room Manager**: Handles collaborative viewing sessions

### 4. Git Operations
- **Branch Manager**: Creates `ai-work/issue-XXX` branches per issue
- **Commit Manager**: Creates clear, atomic commits
- **MR Creator**: Automatically creates merge requests
- **Conflict Handler**: Manages merge conflicts professionally

## Two-Mode Architecture

### Independent Mode (Comment-Driven)
```
GitLab Comment (@phixr command) → Command Parser → Session Manager → 
OpenCode Session (file-based context) → Git Operations → GitLab Comment
```

**Detailed Flow:**
1. User comments with natural language: `@phixr make a plan for this issue`
2. Command parser identifies intent and extracts context
3. Session manager creates dedicated branch (`ai-work/issue-{id}`)
4. Context extractor pulls issue details and repository state
5. Context is injected via files (`CONTEXT.md`, `.phixr/requirements.json`)
6. OpenCode processes the request using its built-in agent capabilities
7. Results are captured (plans, code changes, commit messages)
8. Git operations create commits and push to branch
9. Merge request is created with comprehensive description
10. Status and results posted back to original GitLab issue

### Vibe Mode (Shared Web Interface)
```
GitLab Comment (@phixr vibe) → Vibe Room Manager → OpenCode Session → 
Embedded WebUI + Phixr Wrapper → Real-time Updates
```

**Detailed Flow:**
1. User comments: `@phixr vibe on this issue`
2. Vibe room is created with session association
3. OpenCode session is initialized with proper branch context
4. OpenCode WebUI is embedded within Phixr's unified interface
5. Multiple users can access the same vibe room URL
6. Real-time visibility: changes by any user or AI are visible to all
7. Users can take turns interacting with the OpenCode interface
8. Session state and history are preserved

**Key Difference**: Vibe mode is about **shared visibility**, not simultaneous multi-user editing.

## Data Flow

### Context Injection
- Primary method: File-based (`CONTEXT.md`, `.phixr/context.json`)
- Fallback: HTTP API when reliable
- Environment variables for model configuration

### Branch Strategy
- Every issue gets: `ai-work/issue-{issue_id}`
- AI manages the branch lifecycle
- Conflicts resolved as a professional developer would

## Future Considerations

### Model Management
- External model configuration system (Phase 3)
- Support for local models only
- Model routing layer in Phixr

### Multi-user Enhancements
- While not requiring true multi-user editing, plan for shared visibility
- Real-time updates between users in vibe rooms
- Session sharing capabilities

## Technology Stack

- **Backend**: Python + FastAPI
- **UI**: OpenCode WebUI (embedded) + Phixr wrapper
- **Git**: GitPython + direct GitLab API
- **Real-time**: WebSockets for vibe rooms
- **Database**: PostgreSQL (for sessions, history)
- **Caching**: Redis

---

This architecture aligns with the project goals while preserving OpenCode's excellent web interface and providing the GitLab-native experience users expect.
