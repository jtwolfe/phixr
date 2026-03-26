"""OpenCode bridge for context-to-API communication.

This module bridges Phixr's issue context with OpenCode's AI code generation
capabilities. It manages the full lifecycle of OpenCode API sessions,
from context injection to result extraction.

Uses the OpenCode HTTP API for session management instead of ephemeral containers,
providing proper session isolation and concurrent request support.
"""

import logging
import uuid
from typing import Optional, Dict, List, AsyncIterator
from datetime import datetime

from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import (
    Session, ExecutionResult, ExecutionMode, ExecutionConfig, SessionStatus
)
from phixr.config.sandbox_config import SandboxConfig
from phixr.bridge.opencode_client import OpenCodeServerClient, OpenCodeServerError

logger = logging.getLogger(__name__)


class OpenCodeBridge:
    """Bridge for passing Phixr context to OpenCode API sessions.
    
    Manages the full lifecycle of AI code generation sessions:
    1. Accept issue context from GitLab/GitHub
    2. Create OpenCode session via HTTP API
    3. Inject context and initial prompt
    4. Monitor execution
    5. Extract and return results
    
    Uses OpenCode's native session isolation for concurrent requests.
    This is the main integration point between Phixr and OpenCode.
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        """Initialize OpenCode bridge.
        
        Args:
            config: Sandbox configuration (uses default if None)
        """
        self.config = config or SandboxConfig()
        self.client = OpenCodeServerClient(self.config.opencode_server_url)
        self.sessions: Dict[str, Session] = {}  # Track Phixr sessions
        logger.info(f"OpenCode bridge initialized (server: {self.config.opencode_server_url})")
    
    async def health_check(self) -> bool:
        """Check if OpenCode server is available.
        
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            await self.client.health_check()
            logger.debug("OpenCode server health check passed")
            return True
        except OpenCodeServerError as e:
            logger.warning(f"OpenCode server health check failed: {e}")
            return False
    
    def start_opencode_session(self, context: IssueContext, 
                              mode: ExecutionMode = ExecutionMode.BUILD,
                              initial_prompt: Optional[str] = None,
                              timeout_minutes: Optional[int] = None) -> Session:
        """Start an OpenCode API session with issue context.
        
        Creates a new OpenCode session via HTTP API and injects issue context
        through an initial message.
        
        Args:
            context: IssueContext with issue/repo details
            mode: Execution mode ('build' for changes, 'plan' for analysis)
            initial_prompt: Optional initial message to send to OpenCode
            timeout_minutes: Override default timeout
            
        Returns:
            Session object with OpenCode session details
            
        Raises:
            ValueError: If context invalid or max sessions reached
            OpenCodeServerError: If server communication fails
        """
        # Generate session ID
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        
        # Validate context
        if context.issue_id <= 0:
            raise ValueError("Invalid issue ID")
        
        if not context.repo_url:
            raise ValueError("Repository URL required")
        
        # Check concurrent session limit
        active_sessions = [s for s in self.sessions.values() 
                          if s.status in (SessionStatus.RUNNING, SessionStatus.INITIALIZING)]
        if len(active_sessions) >= self.config.max_sessions:
            raise ValueError(f"Max concurrent sessions ({self.config.max_sessions}) reached")
        
        # Prepare execution configuration
        exec_config = ExecutionConfig(
            session_id=session_id,
            issue_id=context.issue_id,
            repo_url=context.repo_url,
            branch=f"ai-work/issue-{context.issue_id}",
            mode=mode,
            timeout_minutes=timeout_minutes or self.config.timeout_minutes,
            model=self.config.model,
            temperature=self.config.model_temperature,
            allow_destructive=self.config.allow_destructive_operations,
            initial_prompt=initial_prompt,
        )
        
        logger.info(f"Starting OpenCode session: {session_id} (mode={mode.value}, issue={context.issue_id})")
        
        try:
            # Create Phixr session object
            session = Session(
                id=session_id,
                issue_id=context.issue_id,
                repo_url=context.repo_url,
                branch=exec_config.branch,
                status=SessionStatus.INITIALIZING,
                mode=mode,
                timeout_minutes=exec_config.timeout_minutes,
                model=exec_config.model,
                temperature=exec_config.temperature,
                allow_destructive=exec_config.allow_destructive,
            )
            
            session.started_at = datetime.utcnow()
            self.sessions[session.id] = session
            
            # Create OpenCode session via API
            logger.debug(f"Creating OpenCode session via API for {session_id}")
            opencode_session = self.client.create_session(
                title=f"Issue {context.issue_id}: {context.title}",
                description=f"Repository: {context.repo_url}\nBranch: {exec_config.branch}",
            )
            
            # Store OpenCode session ID for future reference
            session.container_id = opencode_session.get("id", "")  # Reuse field for opencode_session_id
            
            logger.info(f"OpenCode session created: {session.container_id}")
            
            # Inject context and initial prompt in first message
            context_message = self._build_context_message(context, exec_config)
            full_message = context_message
            if initial_prompt:
                full_message = f"{context_message}\n\n---\n\n{initial_prompt}"
            
            logger.debug(f"Injecting context message for {session_id}")
            self.client.send_message(
                session_id=session.container_id,
                message=full_message,
                model=exec_config.model,
                temperature=exec_config.temperature,
            )
            
            session.status = SessionStatus.RUNNING
            logger.info(f"Session started: {session.id} (opencode_session: {session.container_id})")
            
            return session
            
        except Exception as e:
            session.status = SessionStatus.ERROR
            session.errors.append(str(e))
            session.ended_at = datetime.utcnow()
            logger.error(f"Failed to start session {session_id}: {e}")
            raise
    
    def _build_context_message(self, context: IssueContext, 
                               exec_config: ExecutionConfig) -> str:
        """Build initial context message to inject into OpenCode session.
        
        Args:
            context: Issue context
            exec_config: Execution configuration
            
        Returns:
            Formatted context message
        """
        mode_str = "analysis and exploration (read-only)" if exec_config.mode == ExecutionMode.PLAN else "development"
        
        message = f"""# Phixr OpenCode Session

## Issue
**ID:** {context.issue_id}
**Title:** {context.title}

### Description
{context.description}

### Labels
{', '.join(context.labels) if context.labels else '(none)'}

## Task
You are in **{mode_str}** mode.

### Context
- **Repository:** {context.repo_url}
- **Branch:** {exec_config.branch}
- **Timeout:** {exec_config.timeout_minutes} minutes
- **Model:** {exec_config.model}

### Important Notes
1. All work should be done in the `{exec_config.branch}` branch
2. Commit your changes with clear, atomic commits
3. Use git diff to prepare your work for review
4. Follow the repository's coding standards and patterns
5. Add tests for new functionality

### Repository Structure
{self._format_repo_structure(context)}

---
Generated at {datetime.utcnow().isoformat()}Z by Phixr
"""
        return message
    
    def _format_repo_structure(self, context: IssueContext) -> str:
        """Format repository structure for display.
        
        Args:
            context: Issue context
            
        Returns:
            Formatted structure string
        """
        if not context.structure:
            return "Structure not available"
        
        if isinstance(context.structure, dict):
            lines = []
            for path, description in context.structure.items():
                lines.append(f"- **{path}**: {description}")
            return "\n".join(lines)
        
        return str(context.structure)
    
    def monitor_session(self, session_id: str) -> Dict:
        """Monitor running session status and retrieve live data.
        
        Args:
            session_id: Session ID
            
        Returns:
            Status dictionary with session info
            
        Raises:
            ValueError: If session not found
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")
        
        session = self.sessions[session_id]
        
        if not session.container_id:
            return {
                "session_id": session_id,
                "status": session.status.value,
                "message": "No OpenCode session assigned",
            }
        
        try:
            # Get session info from OpenCode API
            opencode_session = self.client.get_session(session.container_id)
            
            if not opencode_session:
                raise ValueError(f"OpenCode session not found: {session.container_id}")
            
            return {
                "session_id": session_id,
                "opencode_session_id": session.container_id,
                "status": session.status.value,
                "opencode_status": opencode_session.get("status", "unknown"),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "timeout_minutes": session.timeout_minutes,
                "message_count": opencode_session.get("message_count", 0),
            }
        except Exception as e:
            logger.warning(f"Error monitoring session {session_id}: {e}")
            return {
                "session_id": session_id,
                "status": session.status.value,
                "error": str(e),
            }
    
    def stop_opencode_session(self, session_id: str, force: bool = False) -> bool:
        """Stop an OpenCode session.
        
        Args:
            session_id: Session ID
            force: Force stop (ignored for API sessions, included for compatibility)
            
        Returns:
            True if stopped successfully, False otherwise
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found: {session_id}")
            return False
        
        session = self.sessions[session_id]
        
        if not session.container_id:
            logger.warning(f"No OpenCode session to stop for {session_id}")
            return False
        
        logger.info(f"Stopping OpenCode session: {session_id} (opencode_session: {session.container_id})")
        
        try:
            self.client.delete_session(session.container_id)
            session.status = SessionStatus.STOPPED
            session.ended_at = datetime.utcnow()
            logger.info(f"Session stopped: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error stopping session {session_id}: {e}")
            return False
    
    async def stream_terminal_output(self, session_id: str) -> AsyncIterator[str]:
        """Stream message output for web UI.
        
        Yields session messages suitable for streaming to client.
        
        Args:
            session_id: Session ID
            
        Yields:
            Session messages and output
            
        Raises:
            ValueError: If session not found
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session not found: {session_id}")
        
        session = self.sessions[session_id]
        
        if not session.container_id:
            raise ValueError(f"No OpenCode session for {session_id}")
        
        logger.info(f"Streaming messages for session: {session_id}")
        
        try:
            # Get all messages from OpenCode session
            messages = self.client.get_messages(session.container_id)
            
            for message in messages:
                # Format message for streaming
                formatted = f"{message.get('role', 'unknown')}: {message.get('content', '')}\n"
                yield formatted
        except Exception as e:
            logger.error(f"Error streaming messages for {session_id}: {e}")
            yield f"Error retrieving messages: {e}\n"
    
    def get_session_logs(self, session_id: str) -> str:
        """Get full session message history.
        
        Args:
            session_id: Session ID
            
        Returns:
            Full message history
        """
        if session_id not in self.sessions:
            return f"Session {session_id} not found"
        
        session = self.sessions[session_id]
        
        if not session.container_id:
            return session.logs
        
        try:
            # Get all messages from OpenCode session
            messages = self.client.get_messages(session.container_id)
            
            lines = []
            for message in messages:
                role = message.get("role", "unknown")
                content = message.get("content", "")
                lines.append(f"[{role}] {content}")
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error retrieving logs for {session_id}: {e}")
            return f"Error retrieving logs: {e}"
    
    def extract_results(self, session_id: str) -> Optional[ExecutionResult]:
        """Extract code changes and results from completed session.
        
        Retrieves diffs and file changes from OpenCode session.
        
        Args:
            session_id: Session ID
            
        Returns:
            ExecutionResult with code changes and status, or None if failed
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found: {session_id}")
            return None
        
        session = self.sessions[session_id]
        
        logger.info(f"Extracting results from session: {session_id}")
        
        try:
            if not session.container_id:
                raise ValueError(f"No OpenCode session for {session_id}")
            
            # Get diff from OpenCode
            diff = self.client.get_diff(session.container_id)
            
            # Parse diff to extract files changed
            files_changed = self._parse_diff_files(diff)
            
            result = ExecutionResult(
                session_id=session.id,
                status=session.status,
                exit_code=0 if session.status == SessionStatus.COMPLETED else 1,
                output=self.get_session_logs(session_id),
                success=(session.status == SessionStatus.COMPLETED),
                files_changed=files_changed,
                diffs={"unified": diff} if diff else {},
                errors=session.errors,
                duration_seconds=int((session.ended_at - session.started_at).total_seconds()) 
                                if session.started_at and session.ended_at else 0,
            )
            
            logger.info(f"Results extracted: {result.session_id}")
            logger.debug(f"  Success: {result.success}")
            logger.debug(f"  Files changed: {len(result.files_changed)}")
            if result.errors:
                logger.warning(f"  Errors: {result.errors}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting results for session {session_id}: {e}")
            return None
    
    def _parse_diff_files(self, diff: str) -> List[str]:
        """Parse diff output to extract changed files.
        
        Args:
            diff: Unified diff output
            
        Returns:
            List of changed files
        """
        files = []
        if not diff:
            return files
        
        for line in diff.split("\n"):
            if line.startswith("diff --git"):
                # Extract filename from "diff --git a/path b/path"
                parts = line.split()
                if len(parts) >= 4:
                    # Remove a/ prefix
                    filename = parts[3][2:]
                    if filename not in files:
                        files.append(filename)
        
        return files
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session object by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session object or None if not found
        """
        return self.sessions.get(session_id)
    
    def list_sessions(self, status_filter: Optional[SessionStatus] = None) -> List[Session]:
        """List all sessions, optionally filtered by status.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of Session objects
        """
        sessions = list(self.sessions.values())
        
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]
        
        return sessions
    
    def cleanup_old_sessions(self, older_than_hours: int = 24) -> int:
        """Clean up old completed sessions to free resources.
        
        Args:
            older_than_hours: Remove sessions older than this
            
        Returns:
            Number of sessions removed
        """
        cutoff_time = datetime.utcnow() - __import__('datetime').timedelta(hours=older_than_hours)
        removed = 0
        
        for session_id in list(self.sessions.keys()):
            session = self.sessions[session_id]
            
            # Only remove completed/failed sessions
            if session.status not in (SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.TIMEOUT):
                continue
            
            # Check if session is old enough
            ended_at = session.ended_at or session.started_at
            if ended_at and ended_at < cutoff_time:
                try:
                    if session.container_id:
                        self.client.delete_session(session.container_id)
                    del self.sessions[session_id]
                    removed += 1
                    logger.info(f"Cleaned up old session: {session_id}")
                except Exception as e:
                    logger.warning(f"Error cleaning up session {session_id}: {e}")
        
        logger.info(f"Cleaned up {removed} old sessions")
        return removed
    
    def close(self) -> None:
        """Close bridge and clean up resources."""
        try:
            # Try to close all active sessions
            for session in list(self.sessions.values()):
                if session.status in (SessionStatus.RUNNING, SessionStatus.INITIALIZING):
                    try:
                        self.stop_opencode_session(session.id)
                    except Exception as e:
                        logger.warning(f"Error closing session {session.id}: {e}")
            
            logger.info("OpenCode bridge closed")
        except Exception as e:
            logger.warning(f"Error closing OpenCode bridge: {e}")
