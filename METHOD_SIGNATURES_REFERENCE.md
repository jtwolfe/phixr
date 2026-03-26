# Phixr Phase 2 - Exact Method Signatures Reference

This document provides exact method signatures and usage examples for Phase 2 integration.

---

## 1. CONTEXT EXTRACTION

### Source: `phixr/context/extractor.py`

#### Method: `ContextExtractor.extract_issue_context()`

```python
# Signature
def extract_issue_context(self, project_id: int, issue_id: int) -> Optional[IssueContext]:
    """Extract full context from a GitLab issue.
    
    Args:
        project_id: GitLab project ID
        issue_id: GitLab issue ID (IID, not global ID)
        
    Returns:
        IssueContext object or None if issue not found
        
    Raises:
        No exceptions - returns None on error
    """

# Usage
context = comment_handler.context_extractor.extract_issue_context(
    project_id=123,
    issue_id=456
)

if context:
    print(f"Issue: {context.title}")
    print(f"Author: {context.author}")
    print(f"Repo: {context.repo_url}")
else:
    print("Failed to extract context")
```

#### Returned IssueContext Structure

```python
IssueContext(
    # Issue identification (required)
    issue_id: int,
    project_id: int,
    title: str,
    description: str,
    url: str,
    author: str,
    created_at: datetime,
    updated_at: datetime,
    
    # Issue metadata (optional, defaults to empty)
    assignees: List[str] = [],
    labels: List[str] = [],
    milestone: Optional[str] = None,
    comments: List[dict] = [],
    linked_issues: List[dict] = [],
    
    # Repository context (optional, defaults to empty strings)
    repo_url: str = "",
    repo_name: str = "",
    language: str = "",
    structure: Dict[str, str] = {}
)
```

#### Example Full Context Object

```python
{
    "issue_id": 123,
    "project_id": 456,
    "title": "Add dark mode support",
    "description": "Implement dark mode toggle in settings",
    "url": "https://gitlab.local/project/repo/-/issues/123",
    "author": "john.doe",
    "created_at": datetime(2024, 3, 26, 10, 0, 0),
    "updated_at": datetime(2024, 3, 26, 11, 30, 0),
    "assignees": ["jane.smith", "dev-team"],
    "labels": ["feature", "ui", "enhancement"],
    "milestone": "v2.0",
    "comments": [
        {
            "id": 1001,
            "author": "jane.smith",
            "body": "This should use React theme provider",
            "created_at": "2024-03-26T10:30:00Z",
            "system": False
        }
    ],
    "linked_issues": [],
    "repo_url": "https://gitlab.local/project/repo.git",
    "repo_name": "repo",
    "language": "typescript",
    "structure": {
        "src/": "Source code",
        "tests/": "Test suite",
        "docs/": "Documentation"
    }
}
```

---

## 2. OPENCODE BRIDGE

### Source: `phixr/bridge/opencode_bridge.py`

#### Method: `OpenCodeBridge.__init__()`

```python
# Signature
def __init__(self, config: Optional[SandboxConfig] = None):
    """Initialize OpenCode bridge.
    
    Args:
        config: SandboxConfig instance, or None to use defaults from environment
        
    Raises:
        Exception: If Docker cannot be reached (from DockerClientWrapper)
    """

# Usage - Option 1: With explicit config
from phixr.config.sandbox_config import SandboxConfig
from phixr.bridge import OpenCodeBridge

config = SandboxConfig(
    docker_host="unix:///var/run/docker.sock",
    opencode_image="ghcr.io/phixr/opencode:latest",
    timeout_minutes=30
)
bridge = OpenCodeBridge(config)

# Usage - Option 2: With environment-based config
from phixr.config.sandbox_config import get_sandbox_config
from phixr.bridge import OpenCodeBridge

config = get_sandbox_config()  # Reads from PHIXR_SANDBOX_* env vars
bridge = OpenCodeBridge(config)

# Usage - Option 3: With defaults
bridge = OpenCodeBridge()  # Uses all defaults
```

---

#### Method: `OpenCodeBridge.start_opencode_session()`

```python
# Signature
def start_opencode_session(
    self,
    context: IssueContext,
    mode: ExecutionMode = ExecutionMode.BUILD,
    initial_prompt: Optional[str] = None,
    timeout_minutes: Optional[int] = None
) -> Session:
    """Start an OpenCode container session with issue context.
    
    Args:
        context: IssueContext object from ContextExtractor
        mode: Execution mode
            - ExecutionMode.BUILD: Full access, can make changes (default)
            - ExecutionMode.PLAN: Read-only, analysis only
            - ExecutionMode.REVIEW: Code review mode
        initial_prompt: Optional initial message/instructions for OpenCode
        timeout_minutes: Override default timeout (config.timeout_minutes)
        
    Returns:
        Session object with container details:
            id: Session ID (e.g., "sess-abc12345")
            container_id: Docker container ID
            status: SessionStatus (CREATED, INITIALIZING, RUNNING, etc.)
            started_at: Timestamp when container started
            logs: Container output logs
            exit_code: Exit code (None if still running)
            
    Raises:
        ValueError: If context invalid, max sessions exceeded, etc.
        Exception: If container creation fails
    """

# Usage - Basic
from phixr.models.execution_models import ExecutionMode

session = bridge.start_opencode_session(
    context=issue_context,
    mode=ExecutionMode.BUILD
)

print(f"Session started: {session.id}")
print(f"Container: {session.container_id}")
print(f"Status: {session.status}")

# Usage - With custom instructions
session = bridge.start_opencode_session(
    context=issue_context,
    mode=ExecutionMode.BUILD,
    initial_prompt="Focus on performance optimizations. Add benchmarks.",
    timeout_minutes=45
)

# Usage - Read-only analysis mode
session = bridge.start_opencode_session(
    context=issue_context,
    mode=ExecutionMode.PLAN
)
```

#### Session Object Structure

```python
Session(
    id: str,                              # "sess-abc12345"
    issue_id: int,                        # 123
    repo_url: str,                        # "https://gitlab.local/..."
    branch: str,                          # "ai-work/issue-123"
    container_id: Optional[str],          # Docker container ID
    status: SessionStatus,                # CREATED, INITIALIZING, RUNNING, etc.
    mode: ExecutionMode,                  # BUILD, PLAN, REVIEW
    created_at: datetime,                 # When session was created
    started_at: Optional[datetime],       # When container started
    ended_at: Optional[datetime],         # When container ended
    timeout_minutes: int,                 # 30 (default)
    model: str,                           # "claude-3-opus"
    temperature: float,                   # 0.7
    allow_destructive: bool,              # False
    logs: str,                            # Container output
    exit_code: Optional[int],             # Exit code (None if running)
    errors: List[str]                     # Any errors encountered
)
```

---

#### Method: `OpenCodeBridge.monitor_session()`

```python
# Signature
def monitor_session(self, session_id: str) -> Dict:
    """Monitor running session status and retrieve live data.
    
    Args:
        session_id: Session ID from start_opencode_session()
        
    Returns:
        Dictionary with real-time metrics:
        {
            "session_id": str,
            "status": str,                    # "running", "completed", etc.
            "container_status": str,          # Docker container status
            "memory_mb": {
                "used": float,                # Memory used in MB
                "limit": float                # Memory limit in MB
            },
            "cpu_percent": float,             # CPU usage percentage
            "started_at": str,                # ISO format timestamp
            "timeout_minutes": int
        }
        
    Raises:
        ValueError: If session not found
    """

# Usage
try:
    status = bridge.monitor_session(session.id)
    print(f"Status: {status['status']}")
    print(f"Memory: {status['memory_mb']['used']}/{status['memory_mb']['limit']} MB")
    print(f"CPU: {status['cpu_percent']}%")
except ValueError:
    print("Session not found")
```

---

#### Method: `OpenCodeBridge.get_session_logs()`

```python
# Signature
def get_session_logs(self, session_id: str) -> str:
    """Get full session logs.
    
    Args:
        session_id: Session ID from start_opencode_session()
        
    Returns:
        Full stdout/stderr output from container as string
        
    Raises:
        None (returns empty string if not found)
    """

# Usage
logs = bridge.get_session_logs(session.id)
print(logs)

# Can also stream/save to file
with open(f"session_{session.id}_logs.txt", "w") as f:
    f.write(logs)
```

---

#### Method: `OpenCodeBridge.extract_results()`

```python
# Signature
def extract_results(self, session_id: str) -> Optional[ExecutionResult]:
    """Extract code changes and results from completed session.
    
    Args:
        session_id: Session ID from start_opencode_session()
        
    Returns:
        ExecutionResult object with:
        {
            "session_id": str,
            "status": SessionStatus,              # COMPLETED, FAILED, TIMEOUT, etc.
            "exit_code": int,                     # Process exit code
            "output": str,                        # Full output
            "success": bool,                      # True if exit_code == 0
            "files_changed": List[str],           # ["src/main.py", "tests/test.py"]
            "diffs": Dict[str, str],              # {"src/main.py": "unified diff..."}
            "summary": str,                       # Human-readable summary
            "errors": List[str],                  # Any errors
            "warnings": List[str],                # Non-fatal warnings
            "duration_seconds": int               # How long it took
        }
        or None if session not found
        
    Raises:
        None (returns None on error)
    """

# Usage
result = bridge.extract_results(session.id)

if result:
    if result.success:
        print(f"✅ Session succeeded (exit code: {result.exit_code})")
        print(f"Files changed: {result.files_changed}")
        print(f"Duration: {result.duration_seconds}s")
        
        # Can use diffs for PR creation
        for filename, diff in result.diffs.items():
            print(f"\nChanges to {filename}:")
            print(diff)
    else:
        print(f"❌ Session failed (exit code: {result.exit_code})")
        print(f"Errors: {result.errors}")
else:
    print("Session not found")
```

---

#### Method: `OpenCodeBridge.stop_opencode_session()`

```python
# Signature
def stop_opencode_session(self, session_id: str, force: bool = False) -> bool:
    """Gracefully stop an OpenCode container session.
    
    Args:
        session_id: Session ID from start_opencode_session()
        force: Force kill if graceful stop times out
        
    Returns:
        True if stopped successfully, False otherwise
        
    Raises:
        None
    """

# Usage - Graceful stop
if bridge.stop_opencode_session(session.id):
    print("Session stopped gracefully")
else:
    print("Failed to stop session")

# Usage - Force kill if needed
if bridge.stop_opencode_session(session.id, force=True):
    print("Session force-killed")
```

---

## 3. GITLAB CLIENT

### Source: `phixr/utils/gitlab_client.py`

#### Method: `GitLabClient.get_issue()`

```python
# Signature
def get_issue(self, project_id: int, issue_id: int) -> Optional[Dict[str, Any]]:
    """Get issue details.
    
    Args:
        project_id: GitLab project ID
        issue_id: GitLab issue IID (not global ID)
        
    Returns:
        Dictionary or None if issue not found:
        {
            "id": int,                  # Issue IID
            "project_id": int,
            "title": str,
            "description": str,
            "url": str,                 # web_url for linking
            "assignees": [str],         # List of usernames
            "labels": [str],
            "milestone": Optional[str],
            "author": str,              # Username of creator
            "created_at": datetime,
            "updated_at": datetime,
            "state": str                # "opened" or "closed"
        }
    """

# Usage
issue = gitlab_client.get_issue(project_id=123, issue_id=456)
if issue:
    print(f"Issue: {issue['title']}")
    print(f"Author: {issue['author']}")
    print(f"State: {issue['state']}")
```

---

#### Method: `GitLabClient.get_issue_notes()`

```python
# Signature
def get_issue_notes(self, project_id: int, issue_id: int) -> List[Dict[str, Any]]:
    """Get all comments/notes for an issue.
    
    Args:
        project_id: GitLab project ID
        issue_id: GitLab issue IID
        
    Returns:
        List of comment dictionaries:
        [
            {
                "id": int,
                "body": str,              # Comment text
                "author": str,            # Username
                "created_at": datetime,
                "updated_at": datetime,
                "system": bool            # True if system message
            },
            ...
        ]
        Empty list if no comments or issue not found
    """

# Usage
comments = gitlab_client.get_issue_notes(project_id=123, issue_id=456)
for comment in comments:
    print(f"{comment['author']}: {comment['body']}")
```

---

#### Method: `GitLabClient.add_issue_comment()`

```python
# Signature
def add_issue_comment(
    self,
    project_id: int,
    issue_id: int,
    comment_text: str
) -> Optional[Dict[str, Any]]:
    """Add a comment to an issue.
    
    Args:
        project_id: GitLab project ID
        issue_id: GitLab issue IID
        comment_text: Text of the comment (supports Markdown)
        
    Returns:
        Dictionary if successful, None on error:
        {
            "id": int,                  # Comment ID
            "body": str,
            "created_at": datetime
        }
    """

# Usage - Simple comment
result = gitlab_client.add_issue_comment(
    project_id=123,
    issue_id=456,
    comment_text="Starting AI implementation..."
)

# Usage - With Markdown formatting
result = gitlab_client.add_issue_comment(
    project_id=123,
    issue_id=456,
    comment_text="""
✅ **Session Status**

Session ID: sess-abc12345
Container: abc123def456
Status: **RUNNING**

- Memory: 1.2 / 2.0 GB
- CPU: 65%
- Duration: 2m 30s
""".strip()
)

if result:
    print(f"Comment posted (ID: {result['id']})")
else:
    print("Failed to post comment")
```

---

## 4. EXECUTION MODELS

### Source: `phixr/models/execution_models.py`

#### Enum: `ExecutionMode`

```python
class ExecutionMode(str, Enum):
    """Execution mode for OpenCode session."""
    BUILD = "build"        # Full access, can make changes (default)
    PLAN = "plan"         # Read-only, analysis and planning only
    REVIEW = "review"     # Code review mode

# Usage
from phixr.models.execution_models import ExecutionMode

# Check mode
if session.mode == ExecutionMode.BUILD:
    print("Session has full write access")
elif session.mode == ExecutionMode.PLAN:
    print("Session is read-only")
```

---

#### Enum: `SessionStatus`

```python
class SessionStatus(str, Enum):
    """Status of an execution session."""
    CREATED = "created"           # Session created but not started
    INITIALIZING = "initializing" # Container starting
    RUNNING = "running"           # Container running
    COMPLETED = "completed"       # Successfully completed
    FAILED = "failed"             # Failed with error
    TIMEOUT = "timeout"           # Timed out
    STOPPED = "stopped"           # User stopped
    ERROR = "error"               # Unexpected error

# Usage
if session.status == SessionStatus.COMPLETED:
    result = bridge.extract_results(session.id)
elif session.status == SessionStatus.RUNNING:
    status = bridge.monitor_session(session.id)
elif session.status == SessionStatus.FAILED:
    logs = bridge.get_session_logs(session.id)
```

---

## 5. INTEGRATION PATTERN

### The Complete Flow

```python
# Step 1: Extract context from GitLab
context = comment_handler.context_extractor.extract_issue_context(
    project_id=123,
    issue_id=456
)

if not context:
    gitlab_client.add_issue_comment(
        123, 456,
        "❌ Failed to extract issue context"
    )
    return

# Step 2: Post status update
gitlab_client.add_issue_comment(
    123, 456,
    "🚀 Starting AI implementation session..."
)

# Step 3: Start OpenCode session
try:
    session = opencode_bridge.start_opencode_session(
        context=context,
        mode=ExecutionMode.BUILD,
        timeout_minutes=30
    )
    
    # Step 4: Notify user of session start
    gitlab_client.add_issue_comment(
        123, 456,
        f"""
✅ **Session Started**

Session ID: {session.id}
Container: {session.container_id}
Status: {session.status}

Execution will timeout in {session.timeout_minutes} minutes.
""".strip()
    )
    
    # Step 5: Monitor session (optional - in production, do async)
    while session.status in (SessionStatus.INITIALIZING, SessionStatus.RUNNING):
        import time
        time.sleep(5)
        status = opencode_bridge.monitor_session(session.id)
        # Update UI/logs as needed
    
    # Step 6: Get results
    result = opencode_bridge.extract_results(session.id)
    
    if result and result.success:
        gitlab_client.add_issue_comment(
            123, 456,
            f"""
✅ **Implementation Complete**

- Files changed: {len(result.files_changed)}
- Duration: {result.duration_seconds}s
- Exit code: {result.exit_code}

Changes:
{', '.join(result.files_changed)}
""".strip()
        )
    else:
        gitlab_client.add_issue_comment(
            123, 456,
            f"""
❌ **Session Failed**

Exit code: {result.exit_code}
Errors: {', '.join(result.errors)}

See logs for details.
""".strip()
        )
        
except Exception as e:
    gitlab_client.add_issue_comment(
        123, 456,
        f"❌ Error starting session: {str(e)}"
    )
```

---

## 6. ERROR HANDLING

### Common Exceptions

```python
# Context extraction errors
try:
    context = extractor.extract_issue_context(123, 456)
    if not context:
        print("Context is None - issue not found or API error")
except Exception as e:
    print(f"Unexpected error: {e}")

# Session creation errors
try:
    session = bridge.start_opencode_session(context)
except ValueError as e:
    print(f"Invalid configuration: {e}")
    # Possible messages:
    # - "Invalid issue ID"
    # - "Repository URL required"
    # - "Max concurrent sessions (10) reached"
except Exception as e:
    print(f"Container creation failed: {e}")

# GitLab API errors
try:
    result = gitlab_client.add_issue_comment(123, 456, "text")
except Exception as e:
    print(f"Failed to post comment: {e}")
```

---

## 7. CONFIGURATION REFERENCE

### SandboxConfig Environment Variables

```bash
# Docker Configuration
PHIXR_SANDBOX_DOCKER_HOST=unix:///var/run/docker.sock
PHIXR_SANDBOX_OPENCODE_IMAGE=ghcr.io/phixr/opencode:latest
PHIXR_SANDBOX_DOCKER_NETWORK=phixr-network

# Resource Limits
PHIXR_SANDBOX_MEMORY_LIMIT=2g          # 2GB per container
PHIXR_SANDBOX_CPU_LIMIT=1.0             # 1 CPU per container
PHIXR_SANDBOX_TIMEOUT_MINUTES=30        # Default timeout

# Session Management
PHIXR_SANDBOX_MAX_SESSIONS=10           # Max concurrent sessions

# Git Provider
PHIXR_SANDBOX_GIT_PROVIDER_URL=http://localhost:8080
PHIXR_SANDBOX_GIT_PROVIDER_TOKEN=your-token
PHIXR_SANDBOX_GIT_PROVIDER_TYPE=gitlab  # gitlab, github, gitea

# Model Configuration
PHIXR_SANDBOX_MODEL=local:ollama        # LLM model
PHIXR_SANDBOX_MODEL_TEMPERATURE=0.7     # Creativity (0-1)

# Storage
PHIXR_SANDBOX_CONTEXT_VOLUME_SIZE=104857600  # 100MB
PHIXR_SANDBOX_RESULTS_VOLUME_SIZE=524288000  # 500MB
```

### Loading Configuration

```python
from phixr.config.sandbox_config import SandboxConfig, get_sandbox_config

# Option 1: Load from environment
config = get_sandbox_config()

# Option 2: Create with custom values
config = SandboxConfig(
    docker_host="unix:///var/run/docker.sock",
    memory_limit="2g",
    timeout_minutes=45,
    max_sessions=20
)

# Option 3: Access values
print(config.docker_host)
print(config.timeout_minutes)
print(config.opencode_image)
```

---

## 8. QUICK REFERENCE TABLE

| Component | Method | Returns | Key Args |
|-----------|--------|---------|----------|
| ContextExtractor | `extract_issue_context()` | `Optional[IssueContext]` | project_id, issue_id |
| OpenCodeBridge | `start_opencode_session()` | `Session` | context, mode |
| OpenCodeBridge | `monitor_session()` | `Dict` | session_id |
| OpenCodeBridge | `get_session_logs()` | `str` | session_id |
| OpenCodeBridge | `extract_results()` | `Optional[ExecutionResult]` | session_id |
| OpenCodeBridge | `stop_opencode_session()` | `bool` | session_id, force |
| GitLabClient | `get_issue()` | `Optional[Dict]` | project_id, issue_id |
| GitLabClient | `get_issue_notes()` | `List[Dict]` | project_id, issue_id |
| GitLabClient | `add_issue_comment()` | `Optional[Dict]` | project_id, issue_id, text |

---

**Generated:** March 26, 2026
**For Phase 2 Integration Implementation**
