<div align="center">
  <img src="assets/phixr.jpg" alt="Phixr Logo" width="250" />
</div>

# Phase 2 Implementation Plan: OpenCode Integration & Sandbox Execution

**Version:** 1.0 (Draft)  
**Date:** March 26, 2026  
**Status:** Planning & Design  

---

## Overview

Phase 2 focuses on integrating OpenCode as Phixr's code execution engine. OpenCode is an open-source, terminal-based AI coding agent that will run in sandboxed Docker containers. This phase bridges the gap between Phixr's bot infrastructure (Phase 1) and actual code generation/implementation capabilities.

### Key Goals
1. Clone and containerize OpenCode for isolated execution
2. Design a context-passing mechanism from Phixr to OpenCode
3. Implement container lifecycle management (start, monitor, stop)
4. Create result capture and MR/PR generation workflow
5. Enable web terminal access to running OpenCode sessions

### Success Criteria
- OpenCode runs in Docker containers with Phixr-provided context
- Context from issues is properly serialized and injected
- Results (code changes, diffs) are captured and used to create MRs/PRs
- Web terminal can display OpenCode TUI to users
- Full integration test suite passes

---

## Phase 2a: OpenCode Containerization & Context Design

### Goals
- Create a Dockerfile variant for running OpenCode in sandboxed containers
- Design the context-passing interface between Phixr and OpenCode
- Implement configuration injection mechanism

### Deliverables

#### 1. OpenCode Docker Image (`docker/opencode.Dockerfile`)
**Purpose:** Create a containerized OpenCode environment with:
- Base image: Python 3.11 + Node.js (OpenCode is TypeScript/Bun based)
- Pre-installed dependencies (Bun, essential tools)
- Volume mounts for code repositories
- Environment variable injection for context
- Health check endpoint

**Key Considerations:**
- OpenCode uses Bun as package manager and runtime
- TUI requires terminal capabilities (must support xterm)
- File I/O permissions for git operations
- Network access only to Git provider (GitLab/GitHub) and package registries
- Graceful shutdown handling (SIGTERM)

**Entry Point Strategy:**
```dockerfile
ENTRYPOINT ["opencode"]
CMD ["--interactive", "--context-from-env"]
```

#### 2. Context Format & Serialization (`phixr/models/context_format.py`)
**Purpose:** Define how Phixr context is converted to OpenCode-compatible format

**Context Serialization Options (evaluate each):**

**Option A: Environment Variables (Simple)**
```python
# Issue context encoded in env vars
OPENCODE_ISSUE_ID=123
OPENCODE_ISSUE_TITLE="Add dark mode toggle"
OPENCODE_ISSUE_BODY="..."
OPENCODE_REPO_URL="https://gitlab.local/project/repo.git"
OPENCODE_BRANCH="ai-work/issue-123"
```
- ✅ Simple, no network dependency
- ❌ Limited by env var size limits (~256KB)
- ❌ Not suitable for very large contexts

**Option B: HTTP API (Flexible)**
```python
# OpenCode container calls back to Phixr API
# GET /api/v1/sessions/{session_id}/context
# Returns full context as JSON
```
- ✅ Unlimited context size
- ✅ Can update context dynamically
- ✅ Better error handling
- ❌ Requires network communication
- ❌ More complex authentication

**Option C: File Mount (Balanced)**
```python
# Context written to JSON file, mounted into container
/phixr-context/
  ├── issue.json        # Full issue context
  ├── repository.json   # Repo metadata
  └── config.json       # Session configuration
```
- ✅ Large context support
- ✅ Simple file-based access
- ✅ Container-native approach
- ✅ Recommended approach

**Recommendation: Use Option C with Option B fallback**
- Primary: File mount approach for simplicity
- Fallback: HTTP API for large/dynamic contexts

#### 3. Context Format Specification
```json
{
  "session": {
    "id": "sess-abc123",
    "issue_id": 456,
    "repo_url": "https://gitlab.local/project/repo.git",
    "branch": "ai-work/issue-456",
    "created_at": "2026-03-26T10:30:00Z"
  },
  "issue": {
    "id": 456,
    "title": "Add user authentication",
    "description": "Implement OAuth2 login flow",
    "labels": ["feature", "auth"],
    "milestone": "v2.0",
    "comments": [
      {
        "author": "user",
        "body": "Should support GitHub and GitLab",
        "created_at": "2026-03-26T09:00:00Z"
      }
    ]
  },
  "repository": {
    "name": "myapp",
    "language": "python",
    "structure": {
      "src/": "Source code",
      "tests/": "Test suite",
      "docs/": "Documentation"
    },
    "readme_snippet": "..."
  },
  "execution": {
    "mode": "build",
    "timeout_minutes": 30,
    "model": "claude-opus",
    "temperature": 0.7,
    "allow_destructive": false
  }
}
```

#### 4. Context Injection Mechanism (`phixr/bridge/context_injector.py`)
**Purpose:** Write context to container filesystem and prepare OpenCode launch

```python
class ContextInjector:
    def prepare_context_volume(self, context: IssueContext) -> str:
        """Create and populate context volume directory."""
        # 1. Create temp directory
        # 2. Write context files (JSON)
        # 3. Create config files
        # 4. Return volume mount path
        
    def inject_into_container(self, container, context: IssueContext) -> None:
        """Inject context into running container."""
        # Mount context directory
        # Set initial prompt/context
        # Configure git clone command
```

---

## Phase 2b: Docker Container Lifecycle Management

### Goals
- Implement container creation, execution monitoring, and cleanup
- Handle timeouts, errors, and graceful shutdown
- Capture container output and results

### Deliverables

#### 1. Container Manager (`phixr/sandbox/container_manager.py`)
**Purpose:** Manage OpenCode Docker container lifecycle

```python
class ContainerManager:
    """Manages OpenCode Docker container instances."""
    
    def create_session(self, context: IssueContext, timeout_minutes: int = 30) -> Session:
        """Create and start a new OpenCode container."""
        # 1. Validate context
        # 2. Prepare volumes/mounts
        # 3. Create container
        # 4. Start container
        # 5. Return session info
        
    def monitor_session(self, session_id: str) -> SessionStatus:
        """Monitor running container status."""
        # Check container health
        # Capture logs
        # Return status (running/completed/failed)
        
    def get_container_logs(self, session_id: str, since: Optional[datetime]) -> str:
        """Fetch container output for web terminal."""
        
    def stop_session(self, session_id: str, force: bool = False) -> bool:
        """Gracefully stop container or force kill."""
        # Send SIGTERM for graceful shutdown
        # After timeout, SIGKILL
        # Clean up volumes
        
    def get_session_results(self, session_id: str) -> ExecutionResult:
        """Extract results from container (diffs, files, status)."""
```

#### 2. Session & Execution Models (`phixr/models/execution_models.py`)
```python
class SessionStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    STOPPED = "stopped"

class Session:
    id: str
    issue_id: int
    container_id: str
    status: SessionStatus
    started_at: datetime
    ended_at: Optional[datetime]
    context: IssueContext
    logs: str = ""
    
class ExecutionResult:
    session_id: str
    status: SessionStatus
    exit_code: int
    output: str
    files_changed: List[str]
    diffs: Dict[str, str]  # filename -> unified diff
    errors: List[str]
    success: bool
```

#### 3. Docker Client Wrapper (`phixr/sandbox/docker_client.py`)
**Purpose:** Wrapper around Docker SDK with error handling

```python
class DockerClientWrapper:
    """Wraps Docker SDK with Phixr-specific logic."""
    
    def __init__(self, docker_host: str = "unix:///var/run/docker.sock"):
        """Initialize Docker client."""
        
    def build_opencode_image(self, dockerfile_path: str, tag: str) -> str:
        """Build OpenCode Docker image."""
        
    def run_container(self, image: str, mounts: Dict, env: Dict, 
                     timeout: int) -> Tuple[str, int, str]:
        """Run container and return container_id, exit_code, logs."""
        
    def create_volume(self, name: str) -> str:
        """Create named volume for sharing context/results."""
        
    def get_container_stats(self, container_id: str) -> dict:
        """Get CPU/memory stats for monitoring."""
```

#### 4. Configuration Model for Containers (`phixr/config/sandbox_config.py`)
```python
class SandboxConfig:
    """Configuration for sandbox containers."""
    
    # Docker settings
    docker_host: str = "unix:///var/run/docker.sock"
    opencode_image: str = "ghcr.io/phixr/opencode:latest"
    network: str = "phixr-network"  # Isolated Docker network
    
    # Resource limits
    memory_limit: str = "2g"
    cpu_limit: float = 1.0
    disk_limit: str = "10g"
    timeout_minutes: int = 30
    
    # Git/VCS
    git_provider_url: str  # GitLab/GitHub instance
    git_provider_token: str  # For cloning private repos
    
    # Model & LLM
    model: str = "local:ollama"  # Default model
    temperature: float = 0.7
    
    # Security
    allow_external_network: bool = False
    allow_destructive_operations: bool = False
    allowed_commands: List[str] = ["npm", "python", "git", "npm"]
```

---

## Phase 2c: OpenCode Bridge Implementation

### Goals
- Implement actual OpenCodeBridge class
- Connect context to container execution
- Handle pre/post-execution hooks

### Deliverables

#### 1. Enhanced OpenCodeBridge (`phixr/bridge/opencode_bridge.py`)
```python
class OpenCodeBridge:
    """Bridge for passing Phixr context to OpenCode containers."""
    
    def __init__(self, config: SandboxConfig):
        self.container_manager = ContainerManager(config)
        self.context_injector = ContextInjector(config)
        self.docker_client = DockerClientWrapper(config.docker_host)
        
    def start_opencode_session(self, context: IssueContext, 
                              execution_mode: str = 'build',
                              prompt: str = None) -> Session:
        """Start an OpenCode container session.
        
        Args:
            context: IssueContext with issue/repo details
            execution_mode: 'build' for full access, 'plan' for read-only
            prompt: Initial prompt to send to OpenCode
            
        Returns:
            Session object with container details
        """
        # 1. Validate context
        # 2. Prepare context for injection
        # 3. Create container
        # 4. Send initial prompt
        # 5. Return session
        
    def monitor_session(self, session_id: str) -> dict:
        """Monitor session status and return live data."""
        
    def stop_opencode_session(self, session_id: str) -> bool:
        """Gracefully stop container."""
        
    def get_terminal_stream(self, session_id: str) -> AsyncIterator[str]:
        """Stream terminal output for web UI (xterm.js)."""
        
    def extract_results(self, session_id: str) -> ExecutionResult:
        """Extract code changes and results from session."""
```

#### 2. Pre/Post Execution Hooks (`phixr/sandbox/hooks.py`)
```python
class ExecutionHooks:
    """Hooks for pre/post execution operations."""
    
    @staticmethod
    def pre_execution(context: IssueContext) -> dict:
        """Prepare execution environment."""
        # Setup git credentials
        # Clone/initialize repository
        # Create working branch
        # Return setup metadata
        
    @staticmethod
    def post_execution(session: Session, result: ExecutionResult) -> dict:
        """Process execution results."""
        # Extract diffs from container
        # Run tests/linting
        # Prepare for MR creation
        # Archive session
        # Return processing metadata
```

---

## Phase 2d: Result Capture & MR/PR Generation

### Goals
- Capture diffs and changes from container execution
- Create merge requests/pull requests automatically
- Preserve session history as Git artifacts

### Deliverables

#### 1. Result Extractor (`phixr/sandbox/result_extractor.py`)
```python
class ResultExtractor:
    """Extract and process results from OpenCode containers."""
    
    def extract_git_diff(self, container_id: str) -> dict:
        """Get git diff from container."""
        # docker exec container git diff
        # Parse into file-level diffs
        
    def extract_changed_files(self, container_id: str) -> List[str]:
        """List files that were modified."""
        # docker exec container git status
        
    def create_commit_message(self, context: IssueContext, 
                            changes: dict) -> str:
        """Generate commit message from context and changes."""
        
    def create_session_artifact(self, session: Session, 
                              result: ExecutionResult) -> str:
        """Create markdown artifact of session for archival."""
```

#### 2. MR/PR Creator (`phixr/vcs/mr_creator.py`)
```python
class MRCreator:
    """Create merge requests/pull requests from execution results."""
    
    def create_merge_request(self, gitlab_project_id: int, 
                           context: IssueContext,
                           result: ExecutionResult,
                           session: Session) -> str:
        """Create GitLab MR with execution results.
        
        Returns:
            MR URL
        """
        # 1. Push branch from container
        # 2. Create MR with:
        #    - Title: Auto-generated from issue
        #    - Description: Session summary + changes
        #    - Labels: "ai-generated", issue labels
        #    - Linked to: Original issue
        # 3. Add session artifact as comment
        # 4. Return MR URL
        
    def create_pull_request(self, github_repo: str,
                          context: IssueContext,
                          result: ExecutionResult,
                          session: Session) -> str:
        """Create GitHub PR (similar flow)."""
```

#### 3. Session Artifact Manager (`phixr/sandbox/artifact_manager.py`)
```python
class ArtifactManager:
    """Manage session history and artifacts."""
    
    def archive_session(self, session: Session, result: ExecutionResult) -> str:
        """Archive session as markdown + git commit."""
        # Generate markdown transcript
        # Create git commit with transcript
        # Store in .ai-sessions/ folder
        # Return artifact path
        
    def attach_to_issue(self, issue_id: int, artifact: str) -> bool:
        """Attach session artifact to GitLab issue as comment."""
```

---

## Phase 2e: Web Terminal Access

### Goals
- Expose OpenCode TUI to browser via WebSocket
- Implement terminal streaming (xterm.js backend)
- Support real-time interaction

### Deliverables

#### 1. Web Terminal Server (`phixr/terminal/websocket_handler.py`)
```python
class WebTerminalHandler:
    """WebSocket handler for terminal access to OpenCode containers."""
    
    async def handle_terminal_connection(self, websocket: WebSocket, 
                                        session_id: str) -> None:
        """Accept WebSocket connection and stream terminal."""
        # Connect to container's terminal
        # Stream output to WebSocket
        # Forward input from WebSocket to container
        
    async def stream_container_output(self, container_id: str,
                                     websocket: WebSocket) -> None:
        """Stream container logs/output to WebSocket client."""
        
    async def forward_terminal_input(self, container_id: str,
                                    input_data: str) -> None:
        """Forward user input (keypresses) to container."""
```

#### 2. FastAPI WebSocket Endpoint
```python
@app.websocket("/ws/terminal/{session_id}")
async def websocket_terminal(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for terminal access."""
    # Validate session exists
    # Check permissions
    # Connect via WebTerminalHandler
    # Handle connection lifecycle
```

#### 3. Frontend Terminal Component (Design only for Phase 2)
**Purpose:** Document xterm.js integration for frontend

**Architecture:**
```javascript
// Frontend connects to WebSocket
const ws = new WebSocket(`/ws/terminal/${sessionId}`);

// Use xterm.js for rendering
const term = new Terminal();
term.open(document.getElementById('terminal'));

// Stream data from server
ws.onmessage = (e) => {
  term.write(e.data);
};

// Send user input
term.onData((data) => {
  ws.send(JSON.stringify({ type: 'input', data }));
});
```

---

## Technology Stack (Phase 2)

### Container Runtime
- **Docker**: Container orchestration
- **Docker Compose**: Local development multi-container setup
- **Docker SDK for Python**: Programmatic container management

### OpenCode Integration
- **OpenCode**: Open-source AI coding agent (TypeScript/Bun-based)
- **Bun**: Runtime for OpenCode execution
- **Node.js 18+**: OpenCode dependency

### Terminal & WebSocket
- **WebSockets**: Real-time communication
- **xterm.js**: Browser terminal emulator (frontend integration)
- **ptyprocess**: Python library for pseudo-terminal management

### Storage & State
- **Redis**: Session state management
- **PostgreSQL**: Session history and artifacts

### Python Libraries
- `docker>=7.0.0` - Docker SDK
- `pydantic>=2.0` - Data validation
- `httpx>=0.26.0` - Async HTTP client
- `websockets>=12.0` - WebSocket support (if custom handler needed)
- `python-gitlab>=4.0.0` - GitLab integration (already have)

---

## Project Structure (Phase 2 Additions)

```
phixr/
├── docker/
│   ├── Dockerfile                    # Main app (existing)
│   └── opencode.Dockerfile          # NEW: OpenCode container
│
├── phixr/
│   ├── sandbox/                     # NEW: Sandbox execution
│   │   ├── __init__.py
│   │   ├── container_manager.py     # Container lifecycle
│   │   ├── docker_client.py         # Docker SDK wrapper
│   │   ├── hooks.py                 # Pre/post execution
│   │   ├── result_extractor.py      # Extract diffs & results
│   │   └── artifact_manager.py      # Archive sessions
│   │
│   ├── bridge/
│   │   ├── opencode_bridge.py       # ENHANCED: Full implementation
│   │   ├── context_injector.py      # NEW: Context serialization
│   │   └── __init__.py
│   │
│   ├── terminal/                    # NEW: Web terminal
│   │   ├── __init__.py
│   │   └── websocket_handler.py     # WebSocket for terminal
│   │
│   ├── vcs/
│   │   ├── __init__.py
│   │   └── mr_creator.py            # NEW: MR/PR creation
│   │
│   ├── models/
│   │   ├── issue_context.py         # Existing
│   │   ├── execution_models.py      # NEW: Session/Result models
│   │   └── __init__.py
│   │
│   ├── config/
│   │   ├── sandbox_config.py        # NEW: Sandbox configuration
│   │   ├── settings.py              # Existing
│   │   └── __init__.py
│   │
│   └── main.py                      # UPDATED: Add new endpoints
│
├── docs/
│   ├── PHASE_2_IMPLEMENTATION.md    # NEW: Detailed guide
│   └── TERMINAL_ARCHITECTURE.md     # NEW: Terminal design
│
└── docker-compose.yml               # UPDATED: Docker network setup
```

---

## Implementation Roadmap

### Week 1: Containerization & Context Design
- [x] Research OpenCode architecture
- [ ] Create OpenCode Dockerfile
- [ ] Design context format specification
- [ ] Implement ContextInjector
- [ ] Write comprehensive documentation

### Week 2: Container Lifecycle Management
- [ ] Implement ContainerManager
- [ ] Implement DockerClientWrapper
- [ ] Create ExecutionModels
- [ ] Add container monitoring and logging
- [ ] Handle graceful shutdown

### Week 3: OpenCode Bridge & Results
- [ ] Implement full OpenCodeBridge
- [ ] Create ResultExtractor
- [ ] Implement MRCreator
- [ ] Add ArtifactManager
- [ ] Integration with Phase 1 commands

### Week 4: Web Terminal & Integration
- [ ] Implement WebTerminalHandler
- [ ] Add WebSocket endpoint
- [ ] Create terminal streaming
- [ ] Write integration tests
- [ ] End-to-end testing

---

## Key Design Decisions

### 1. Context Passing: File Mount Approach
**Decision:** Use volume mounts with JSON files as primary method
**Rationale:**
- Simple and reliable (no network overhead)
- Container-native approach
- Suitable for most context sizes
- Easy debugging (inspect mounted files)

**Fallback:** HTTP API for very large contexts (>10MB)

### 2. Execution Model: Independent Containers
**Decision:** Each session = separate Docker container
**Rationale:**
- Isolation and security
- Easy to kill/timeout
- Independent resource limits
- No shared state between sessions

**Alternative considered:** Docker Compose per session (rejected - too heavy)

### 3. Result Capture: Git-native
**Decision:** Extract results via git diff, store as commits
**Rationale:**
- Native to all VCS providers
- Preserves full change history
- Integrates with code review
- Supports rollback

### 4. Session Persistence: Redis + PostgreSQL
**Decision:** 
- Redis: Live session state (running, status, logs)
- PostgreSQL: Long-term history (after completion)

**Rationale:**
- Fast access for live sessions
- Durable history for compliance
- Scalable architecture

---

## Success Metrics

- **Execution Success Rate**: 95%+ of container sessions complete without error
- **Result Accuracy**: 90%+ of generated diffs are valid and mergeable
- **Terminal Responsiveness**: <500ms latency for terminal input/output
- **Session Duration**: Average 10-20 minutes for typical features
- **Resource Efficiency**: <2GB RAM per container, <5GB disk per session

---

## Risk Mitigation

### Risk: Container Escape / Security Breach
**Mitigation:**
- Use AppArmor/SELinux profiles
- Network isolation (only Git provider access)
- Resource quotas (CPU, memory, disk)
- Regular security audits

### Risk: Context Size Explosion
**Mitigation:**
- Implement context size limits (max 100MB)
- Compress context using gzip
- Stream large files instead of embedding

### Risk: Long-Running Sessions
**Mitigation:**
- Hard timeout after 30 minutes (configurable)
- Periodic health checks
- Graceful shutdown on resource exhaustion
- User-initiated stop capability

### Risk: Terminal Latency / WebSocket Issues
**Mitigation:**
- Use connection pooling
- Implement heartbeats/keep-alives
- Graceful reconnection handling
- Buffer terminal output for catchup

---

## Next Steps After Phase 2

Once Phase 2 is complete:

1. **Phase 3**: Multi-user vibe rooms with real-time collaboration
2. **Phase 4**: Team dashboard and analytics
3. **Enhancement**: Fine-tuned models for code generation
4. **Scaling**: Kubernetes deployment for multi-node setups

---

## References & Resources

- OpenCode GitHub: https://github.com/anomalyco/opencode
- OpenCode Docs: https://opencode.ai/docs
- Docker SDK for Python: https://docker-py.readthedocs.io/
- xterm.js: https://xtermjs.org/
- WebSockets Protocol: RFC 6455

---

## Appendix: Docker Network Architecture

For Phase 2, we'll setup an isolated Docker network:

```yaml
# docker-compose.yml additions

networks:
  phixr-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_ip_masquerade: "true"

services:
  phixr-bot:
    networks:
      - phixr-network
    ports:
      - "8000:8000"  # Bot API
    
  phixr-redis:
    networks:
      - phixr-network
    
  phixr-postgres:
    networks:
      - phixr-network
  
  # OpenCode containers will be dynamically created on this network
  # phixr-opencode-session-{session_id}:
  #   networks:
  #     - phixr-network
```

**Network Security:**
- OpenCode containers can reach: Git provider (via whitelist), package registries
- OpenCode containers cannot reach: Internet, other containers, phixr services (read-only access)
- Phixr bot service can reach: OpenCode containers (for health checks, result extraction)

---

This completes the Phase 2 design. Ready to implement!
