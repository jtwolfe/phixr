"""Data models for Phixr."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class IssueContext(BaseModel):
    """Context extracted from a GitLab issue."""
    
    # Issue identification
    issue_id: int
    project_id: int
    title: str
    description: str
    url: str
    author: str
    created_at: datetime
    updated_at: datetime
    
    # Issue metadata
    assignees: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)
    milestone: Optional[str] = None
    comments: List[dict] = Field(default_factory=list)
    linked_issues: List[dict] = Field(default_factory=list)
    
    # Repository context
    repo_url: str = Field(default="", description="Repository URL for cloning")
    repo_name: str = Field(default="", description="Repository name/slug")
    language: str = Field(default="", description="Primary programming language")
    structure: Dict[str, str] = Field(default_factory=dict, description="Repository structure")
    
    class Config:
        arbitrary_types_allowed = True


class Command(BaseModel):
    """Parsed slash command from issue comment."""
    
    name: str
    args: List[str] = Field(default_factory=list)
    raw_text: str
    author: str
    issue_id: int
    project_id: int
    comment_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True


class Session(BaseModel):
    """User session for context and state tracking."""
    
    session_id: str
    issue_id: int
    project_id: int
    bot_user_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "active"  # active, closed, archived
    participants: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True
