"""OpenCode bridge for context-to-container communication.

This module bridges Phixr's issue context with OpenCode's AI code generation
capabilities. It manages the full lifecycle of containerized OpenCode sessions,
from context injection to result extraction.
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
from phixr.sandbox.container_manager import ContainerManager

logger = logging.getLogger(__name__)


class OpenCodeBridge:
    """Bridge for passing Phixr context to OpenCode containers.
    
    Manages the full lifecycle of AI code generation sessions:
    1. Accept issue context from GitLab/GitHub
    2. Prepare and inject context into container
    3. Monitor execution
    4. Extract and return results
    
    This is the main integration point between Phixr and OpenCode.
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        """Initialize OpenCode bridge.
        
        Args:
            config: Sandbox configuration (uses default if None)
        """
        self.config = config or SandboxConfig()
        self.container_manager = ContainerManager(self.config)
        logger.info("OpenCode bridge initialized")
    
    def start_opencode_session(self, context: IssueContext, 
                              mode: ExecutionMode = ExecutionMode.BUILD,
                              initial_prompt: Optional[str] = None,
                              timeout_minutes: Optional[int] = None) -> Session:
        """Start an OpenCode container session with issue context.
        
        Prepares context, validates configuration, creates container, and
        initiates AI code generation session.
        
        Args:
            context: IssueContext with issue/repo details
            mode: Execution mode ('build' for changes, 'plan' for analysis)
            initial_prompt: Optional initial message to send to OpenCode
            timeout_minutes: Override default timeout
            
        Returns:
            Session object with container details
            
        Raises:
            ValueError: If context invalid or max sessions reached
            Exception: If container creation fails
        """
        # Generate session ID
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        
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
            # Create and start container
            session = self.container_manager.create_session(context, exec_config)
            
            # Log session details
            logger.info(f"Session started: {session.id}")
            logger.debug(f"  Container: {session.container_id}")
            logger.debug(f"  Branch: {session.branch}")
            logger.debug(f"  Timeout: {session.timeout_minutes} minutes")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {e}")
            raise
    
    def monitor_session(self, session_id: str) -> Dict:
        """Monitor running session status and retrieve live data.
        
        Args:
            session_id: Session ID
            
        Returns:
            Status dictionary with container metrics and session info
            
        Raises:
            ValueError: If session not found
        """
        status = self.container_manager.monitor_session(session_id)
        
        if not status:
            raise ValueError(f"Session not found: {session_id}")
        
        session = self.container_manager.get_session(session_id)
        
        return {
            "session_id": session_id,
            "status": status.get("session_status", "unknown"),
            "container_status": status.get("status", "unknown"),
            "memory_mb": {
                "used": status.get("memory_usage_mb", 0),
                "limit": status.get("memory_limit_mb", 0),
            },
            "cpu_percent": status.get("cpu_percent", 0),
            "started_at": session.started_at.isoformat() if session and session.started_at else None,
            "timeout_minutes": session.timeout_minutes if session else None,
        }
    
    def stop_opencode_session(self, session_id: str, force: bool = False) -> bool:
        """Gracefully stop an OpenCode container session.
        
        Args:
            session_id: Session ID
            force: Force kill if graceful stop times out
            
        Returns:
            True if stopped successfully, False otherwise
        """
        logger.info(f"Stopping OpenCode session: {session_id} (force={force})")
        
        try:
            return self.container_manager.stop_session(session_id, force=force)
        except Exception as e:
            logger.error(f"Error stopping session {session_id}: {e}")
            return False
    
    async def stream_terminal_output(self, session_id: str) -> AsyncIterator[str]:
        """Stream terminal output for web UI (xterm.js compatible).
        
        Yields terminal data suitable for streaming to browser via WebSocket.
        This enables real-time terminal viewing during OpenCode execution.
        
        Args:
            session_id: Session ID
            
        Yields:
            Terminal output chunks
            
        Raises:
            ValueError: If session not found
        """
        session = self.container_manager.get_session(session_id)
        
        if not session:
            raise ValueError(f"Session not found: {session_id}")
        
        logger.info(f"Streaming terminal output for session: {session_id}")
        
        # Stream logs
        logs = self.container_manager.get_session_logs(session_id)
        
        if logs:
            yield logs
        
        # In future phases, implement real-time streaming
        # For now, return captured logs
    
    def get_session_logs(self, session_id: str) -> str:
        """Get full session logs.
        
        Args:
            session_id: Session ID
            
        Returns:
            Full log output
        """
        return self.container_manager.get_session_logs(session_id)
    
    def extract_results(self, session_id: str) -> Optional[ExecutionResult]:
        """Extract code changes and results from completed session.
        
        Retrieves diffs, file changes, and execution status from the
        container. Results are used to create merge requests/pull requests.
        
        Args:
            session_id: Session ID
            
        Returns:
            ExecutionResult with code changes and status, or None if failed
        """
        logger.info(f"Extracting results from session: {session_id}")
        
        try:
            result = self.container_manager.get_session_results(session_id)
            
            if result:
                logger.info(f"Results extracted: {result.session_id}")
                logger.debug(f"  Success: {result.success}")
                logger.debug(f"  Exit code: {result.exit_code}")
                logger.debug(f"  Files changed: {len(result.files_changed)}")
                if result.errors:
                    logger.warning(f"  Errors: {result.errors}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting results for session {session_id}: {e}")
            return None
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session object by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session object or None if not found
        """
        return self.container_manager.get_session(session_id)
    
    def list_sessions(self, status_filter: Optional[SessionStatus] = None) -> List[Session]:
        """List all sessions, optionally filtered by status.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of Session objects
        """
        return self.container_manager.list_sessions(status_filter)
    
    def cleanup_old_sessions(self, older_than_hours: int = 24) -> int:
        """Clean up old completed sessions to free resources.
        
        Args:
            older_than_hours: Remove sessions older than this
            
        Returns:
            Number of sessions removed
        """
        count = self.container_manager.cleanup_old_sessions(older_than_hours)
        logger.info(f"Cleaned up {count} old sessions")
        return count
    
    def close(self) -> None:
        """Close bridge and clean up resources."""
        try:
            self.container_manager.close()
            logger.info("OpenCode bridge closed")
        except Exception as e:
            logger.warning(f"Error closing OpenCode bridge: {e}")
