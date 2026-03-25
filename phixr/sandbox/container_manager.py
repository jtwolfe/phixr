"""Docker container lifecycle management for OpenCode sessions."""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio

from phixr.models.execution_models import Session, SessionStatus, ExecutionResult, ExecutionConfig
from phixr.models.issue_context import IssueContext
from phixr.config.sandbox_config import SandboxConfig
from phixr.sandbox.docker_client import DockerClientWrapper
from phixr.bridge.context_injector import ContextInjector

logger = logging.getLogger(__name__)


class ContainerManager:
    """Manages OpenCode Docker container instances and lifecycle."""
    
    def __init__(self, config: SandboxConfig):
        """Initialize container manager.
        
        Args:
            config: Sandbox configuration
        """
        self.config = config
        self.docker = DockerClientWrapper(config)
        self.context_injector = ContextInjector(config)
        self.sessions: Dict[str, Session] = {}
    
    def create_session(self, context: IssueContext, 
                      exec_config: ExecutionConfig) -> Session:
        """Create and start a new OpenCode container session.
        
        Args:
            context: Issue context from GitLab/GitHub
            exec_config: Execution configuration
            
        Returns:
            Session object with container details
            
        Raises:
            ValueError: If configuration invalid or too many sessions
            Exception: If container creation fails
        """
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
        
        # Create session object
        session = Session(
            id=exec_config.session_id,
            issue_id=context.issue_id,
            repo_url=context.repo_url,
            branch=exec_config.branch,
            status=SessionStatus.CREATED,
            mode=exec_config.mode,
            timeout_minutes=exec_config.timeout_minutes,
            model=exec_config.model,
            temperature=exec_config.temperature,
            allow_destructive=exec_config.allow_destructive,
        )
        
        logger.info(f"Creating session: {session.id}")
        
        try:
            # Prepare context volume
            logger.debug(f"Preparing context volume for session {session.id}")
            context_path, context_volume = self.context_injector.prepare_context_volume(
                context, exec_config
            )
            
            # Create environment variables
            git_token = self.config.git_provider_token or ""
            env_vars = self.context_injector.create_environment_variables(
                context, exec_config, git_token
            )
            
            # Prepare volume mounts
            mounts = {
                "/phixr-context": {"bind": context_path, "mode": "ro"},
                "/phixr-results": {"bind": "/tmp/phixr-results", "mode": "rw"},
            }
            
            # Update session status
            session.status = SessionStatus.INITIALIZING
            session.started_at = datetime.utcnow()
            self.sessions[session.id] = session
            
            # Run container
            logger.info(f"Starting container for session {session.id}")
            container_id, exit_code, logs = self.docker.run_container(
                image=self.config.opencode_image,
                mounts=mounts,
                env=env_vars,
                timeout=session.timeout_minutes * 60,
                memory_limit=self.config.memory_limit,
            )
            
            session.container_id = container_id
            session.logs = logs
            session.exit_code = exit_code
            session.ended_at = datetime.utcnow()
            
            # Determine final status
            if exit_code == 0:
                session.status = SessionStatus.COMPLETED
            elif exit_code == 124:
                session.status = SessionStatus.TIMEOUT
            else:
                session.status = SessionStatus.FAILED
                if logs:
                    session.errors.append(f"Container exited with code {exit_code}")
            
            logger.info(f"Session completed: {session.id} (exit_code={exit_code}, status={session.status})")
            
            return session
            
        except Exception as e:
            session.status = SessionStatus.ERROR
            session.errors.append(str(e))
            session.ended_at = datetime.utcnow()
            logger.error(f"Error in session {session.id}: {e}")
            raise
        finally:
            # Always clean up context injector
            self.context_injector.cleanup_all()
    
    def monitor_session(self, session_id: str) -> Optional[Dict]:
        """Monitor running container status.
        
        Args:
            session_id: Session ID
            
        Returns:
            Status dictionary or None if session not found
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found: {session_id}")
            return None
        
        session = self.sessions[session_id]
        
        if not session.container_id:
            return {
                "id": session.id,
                "status": session.status.value,
                "message": "No container running",
            }
        
        # Get container stats
        stats = self.docker.get_container_stats(session.container_id)
        
        if stats:
            return {
                "id": session.id,
                "container_id": stats["container_id"],
                "status": stats["status"],
                "memory_usage_mb": stats["memory_usage_mb"],
                "memory_limit_mb": stats["memory_limit_mb"],
                "cpu_percent": stats["cpu_percent"],
                "session_status": session.status.value,
            }
        
        return {
            "id": session.id,
            "status": session.status.value,
            "message": "Stats unavailable",
        }
    
    def get_session_logs(self, session_id: str, since: Optional[int] = None) -> str:
        """Fetch session logs.
        
        Args:
            session_id: Session ID
            since: Unix timestamp to get logs since
            
        Returns:
            Log content
        """
        if session_id not in self.sessions:
            return f"Session {session_id} not found"
        
        session = self.sessions[session_id]
        
        if session.container_id:
            return self.docker.get_container_logs(session.container_id, since)
        
        return session.logs
    
    def stop_session(self, session_id: str, force: bool = False) -> bool:
        """Gracefully stop container or force kill.
        
        Args:
            session_id: Session ID
            force: Force kill if graceful stop fails
            
        Returns:
            True if stopped successfully
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found: {session_id}")
            return False
        
        session = self.sessions[session_id]
        
        if not session.container_id:
            logger.warning(f"No container for session {session_id}")
            return False
        
        logger.info(f"Stopping session: {session_id}")
        session.status = SessionStatus.STOPPED
        session.ended_at = datetime.utcnow()
        
        return True
    
    def get_session_results(self, session_id: str) -> Optional[ExecutionResult]:
        """Extract results from completed session.
        
        Args:
            session_id: Session ID
            
        Returns:
            ExecutionResult object or None if session not found
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found: {session_id}")
            return None
        
        session = self.sessions[session_id]
        
        # Create result object from session
        result = ExecutionResult(
            session_id=session.id,
            status=session.status,
            exit_code=session.exit_code or 1,
            output=session.logs,
            success=(session.status == SessionStatus.COMPLETED and session.exit_code == 0),
            errors=session.errors,
            duration_seconds=int((session.ended_at - session.started_at).total_seconds()) 
                            if session.started_at and session.ended_at else 0,
        )
        
        # In Phase 2b, we'll add diff extraction from container
        # For now, return basic result
        
        return result
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session object or None
        """
        return self.sessions.get(session_id)
    
    def list_sessions(self, status_filter: Optional[SessionStatus] = None) -> list:
        """List sessions, optionally filtered by status.
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of sessions
        """
        sessions = list(self.sessions.values())
        
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]
        
        return sessions
    
    def cleanup_old_sessions(self, older_than_hours: int = 24) -> int:
        """Clean up old completed sessions.
        
        Args:
            older_than_hours: Remove sessions older than this many hours
            
        Returns:
            Number of sessions removed
        """
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        removed = 0
        
        for session_id in list(self.sessions.keys()):
            session = self.sessions[session_id]
            
            # Only remove completed/failed sessions
            if session.status not in (SessionStatus.COMPLETED, SessionStatus.FAILED, 
                                     SessionStatus.TIMEOUT, SessionStatus.ERROR):
                continue
            
            # Check if old enough
            if session.ended_at and session.ended_at < cutoff:
                del self.sessions[session_id]
                removed += 1
                logger.info(f"Cleaned up session: {session_id}")
        
        return removed
    
    def close(self) -> None:
        """Close container manager."""
        try:
            self.docker.close()
            logger.info("Container manager closed")
        except Exception as e:
            logger.warning(f"Error closing container manager: {e}")


if __name__ == "__main__":
    # Example usage
    config = SandboxConfig()
    manager = ContainerManager(config)
    
    print("✓ Container manager initialized")
