"""Data models for sandbox execution and session management."""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Status of an execution session."""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    STOPPED = "stopped"
    ERROR = "error"


class ExecutionMode(str, Enum):
    """OpenCode execution modes."""
    BUILD = "build"  # Full access, can make changes
    PLAN = "plan"    # Read-only, analysis only
    REVIEW = "review"  # Review existing code


class Session(BaseModel):
    """Represents an OpenCode execution session."""
    id: str = Field(..., description="Unique session identifier")
    issue_id: int = Field(..., description="Associated GitLab/GitHub issue ID")
    repo_url: str = Field(..., description="Git repository URL to clone")
    branch: str = Field(..., description="Git branch for work")
    container_id: Optional[str] = Field(None, description="Docker container ID")
    status: SessionStatus = Field(default=SessionStatus.CREATED)
    mode: ExecutionMode = Field(default=ExecutionMode.BUILD)
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    timeout_minutes: int = Field(default=30)
    
    # Configuration
    model: str = Field(default="claude-3-opus")  # LLM model to use
    temperature: float = Field(default=0.7)
    allow_destructive: bool = Field(default=False)
    
    # Output
    logs: str = Field(default="")
    exit_code: Optional[int] = None
    errors: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class ExecutionResult(BaseModel):
    """Results from a completed execution session."""
    session_id: str = Field(..., description="Associated session ID")
    status: SessionStatus = Field(..., description="Final status")
    exit_code: int = Field(..., description="Process exit code")
    
    # Output
    output: str = Field(default="", description="Full stdout/stderr output")
    success: bool = Field(..., description="Whether execution succeeded")
    
    # Code changes
    files_changed: List[str] = Field(default_factory=list, description="Files that were modified")
    diffs: Dict[str, str] = Field(default_factory=dict, description="filename -> unified diff")
    
    # Summary
    summary: str = Field(default="", description="Human-readable summary of changes")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    
    # Duration
    duration_seconds: int = Field(default=0, description="Total execution time")
    
    class Config:
        use_enum_values = True


class ContainerStats(BaseModel):
    """Resource usage statistics for a container."""
    container_id: str
    status: str
    memory_usage_mb: float
    memory_limit_mb: float
    cpu_percent: float
    uptime_seconds: int
    
    class Config:
        arbitrary_types_allowed = True


class SandboxError(BaseModel):
    """Error information from sandbox execution."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ContextSnapshot(BaseModel):
    """Snapshot of issue context at session creation."""
    session_id: str
    issue_id: int
    repo_url: str
    branch: str
    issue_title: str
    issue_description: str
    issue_labels: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionConfig(BaseModel):
    """Configuration for executing a session."""
    session_id: str
    issue_id: int
    repo_url: str
    branch: str
    mode: ExecutionMode = ExecutionMode.BUILD
    timeout_minutes: int = 30
    model: str = "claude-3-opus"
    temperature: float = 0.7
    allow_destructive: bool = False
    initial_prompt: Optional[str] = None
    
    class Config:
        use_enum_values = True


if __name__ == "__main__":
    # Example usage
    session = Session(
        id="sess-abc123",
        issue_id=456,
        repo_url="https://gitlab.local/project/repo.git",
        branch="ai-work/issue-456",
    )
    print(f"Session created: {session.id}")
    
    result = ExecutionResult(
        session_id="sess-abc123",
        status=SessionStatus.COMPLETED,
        exit_code=0,
        success=True,
        files_changed=["src/main.py", "tests/test_main.py"],
        output="Successfully generated feature implementation",
    )
    print(f"Result: {result.status}")
