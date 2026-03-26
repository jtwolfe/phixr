"""OpenCode Integration Service.

Clean rearchitecture of OpenCode integration that supports both API-based and UI embedding modes.
Replaces the problematic OpenCodeBridge with proper async architecture.
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime

from phixr.bridge.context_injector import ContextInjector
from phixr.bridge.opencode_client import OpenCodeServerClient, OpenCodeServerError
from phixr.collaboration.vibe_room_manager import VibeRoomManager
from phixr.config.sandbox_config import SandboxConfig
from phixr.models.execution_models import (
    Session, SessionStatus, ExecutionResult, ExecutionMode, VibeRoom, ExecutionConfig
)
from phixr.models.issue_context import IssueContext

logger = logging.getLogger(__name__)


class IntegrationMode(str, Enum):
    """Integration modes for OpenCode."""
    API = "api"         # Use OpenCode API only
    UI_EMBED = "ui_embed"  # Embed OpenCode web UI in iframe
    HYBRID = "hybrid"   # API + UI embedding


class OpenCodeIntegrationService:
    """Clean, async integration service for OpenCode.

    Supports multiple integration modes:
    - API: Pure API-based interaction
    - UI_EMBED: Embed OpenCode web UI in iframe
    - HYBRID: Combined approach

    Replaces the problematic OpenCodeBridge with proper architecture.
    """

    def __init__(self, config: SandboxConfig, mode: IntegrationMode = IntegrationMode.UI_EMBED):
        """Initialize integration service.

        Args:
            config: Sandbox configuration
            mode: Integration mode (UI_EMBED for single user vibe coding)
        """
        self.config = config
        self.mode = mode
        self.client = OpenCodeServerClient(self.config.opencode_server_url)
        self.context_injector = ContextInjector(config)
        self.vibe_manager = VibeRoomManager()

        # Session tracking
        self.sessions: Dict[str, Session] = {}

        logger.info(f"OpenCode integration service initialized (mode: {mode.value})")

    async def health_check(self) -> bool:
        """Check if OpenCode server is healthy."""
        try:
            return await self.client.health_check()
        except Exception as e:
            logger.warning(f"OpenCode health check failed: {e}")
            return False

    async def create_session(
        self,
        context: IssueContext,
        execution_mode: ExecutionMode = ExecutionMode.BUILD,
        timeout_minutes: Optional[int] = None,
        owner_id: str = "single-user"
    ) -> Session:
        """Create a new OpenCode session with proper async handling.

        Args:
            context: Issue context from GitLab
            execution_mode: Execution mode (BUILD, PLAN, etc.)
            timeout_minutes: Session timeout
            owner_id: User ID for session ownership

        Returns:
            Created Session object

        Raises:
            OpenCodeServerError: If session creation fails
        """
        session_id = f"sess-{context.issue_id}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # Create Phixr session object
        session = Session(
            id=session_id,
            issue_id=context.issue_id,
            repo_url=context.repo_url,
            branch=f"ai-work/issue-{context.issue_id}",
            status=SessionStatus.INITIALIZING,
            mode=execution_mode,
            timeout_minutes=timeout_minutes or self.config.timeout_minutes,
            model=self.config.model,
            temperature=self.config.model_temperature,
            allow_destructive=self.config.allow_destructive_operations,
        )

        session.started_at = datetime.utcnow()
        self.sessions[session_id] = session

        logger.info(f"Creating OpenCode session: {session_id} (mode: {execution_mode.value})")

        try:
            if self.mode in [IntegrationMode.UI_EMBED, IntegrationMode.HYBRID]:
                # For UI embedding mode, create a session that will be managed via UI
                opencode_session = await self.client.create_session(
                    project_path=context.repo_url,  # This will be handled differently in UI mode
                    title=f"Issue {context.issue_id}: {context.title}"
                )

                # Store OpenCode session ID
                session.container_id = opencode_session.get("id", "")

                # Create vibe room for UI embedding
                vibe_room = self.vibe_manager.create_room(session, owner_id)
                session.vibe_room_id = vibe_room.id

                logger.info(f"Created UI-embedded session: {session_id} (opencode: {session.container_id}, vibe: {vibe_room.id})")

            elif self.mode == IntegrationMode.API:
                # Pure API mode - create session and inject context immediately
                opencode_session = await self.client.create_session(
                    project_path=context.repo_url,
                    title=f"Issue {context.issue_id}: {context.title}"
                )

                session.container_id = opencode_session.get("id", "")

                # Build and inject context message
                context_message = self.context_injector.build_context_message(
                    context,
                    ExecutionConfig(
                        session_id=session_id,
                        issue_id=context.issue_id,
                        repo_url=context.repo_url,
                        branch=session.branch,
                        mode=execution_mode
                    )
                )

                # Send initial message with context
                await self.client.send_message(
                    session_id=session.container_id,
                    message=context_message,
                    model=session.model,
                    temperature=session.temperature
                )

                logger.info(f"Created API session: {session_id} (opencode: {session.container_id})")

            session.status = SessionStatus.RUNNING
            return session

        except Exception as e:
            session.status = SessionStatus.ERROR
            session.errors.append(str(e))
            session.ended_at = datetime.utcnow()
            logger.error(f"Failed to create session {session_id}: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    async def list_sessions(self, status_filter: Optional[SessionStatus] = None) -> List[Session]:
        """List sessions with optional status filter."""
        sessions = list(self.sessions.values())
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]
        return sessions

    async def stop_session(self, session_id: str, force: bool = False) -> bool:
        """Stop an OpenCode session."""
        session = self.sessions.get(session_id)
        if not session or not session.container_id:
            logger.warning(f"Session not found or no OpenCode session: {session_id}")
            return False

        try:
            await self.client.delete_session(session.container_id)
            session.status = SessionStatus.STOPPED
            session.ended_at = datetime.utcnow()
            logger.info(f"Stopped session: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop session {session_id}: {e}")
            return False

    async def get_session_results(self, session_id: str) -> Optional[ExecutionResult]:
        """Get results from completed session."""
        session = self.sessions.get(session_id)
        if not session or not session.container_id:
            return None

        try:
            # Get diff from OpenCode
            diff = await self.client.get_diff(session.container_id)

            # Create result object
            result = ExecutionResult(
                session_id=session.id,
                status=session.status,
                exit_code=0 if session.status == SessionStatus.COMPLETED else 1,
                output="",  # Will be populated from messages
                success=(session.status == SessionStatus.COMPLETED),
                files_changed=self._parse_diff_files(diff) if diff else [],
                diffs={"unified": diff} if diff else {},
                errors=session.errors,
                duration_seconds=int((session.ended_at - session.started_at).total_seconds())
                                if session.started_at and session.ended_at else 0,
            )

            return result

        except Exception as e:
            logger.error(f"Error getting results for session {session_id}: {e}")
            return None

    async def stream_messages(self, session_id: str) -> AsyncGenerator[str, None]:
        """Stream messages for real-time updates."""
        session = self.sessions.get(session_id)
        if not session or not session.container_id:
            yield f"Error: Session not found or not active: {session_id}"
            return

        try:
            # In UI_EMBED mode, messages are handled via the embedded UI
            if self.mode in [IntegrationMode.UI_EMBED, IntegrationMode.HYBRID]:
                # For now, just yield status updates
                yield f"Session active: {session_id} (UI embedded mode)"

                # Could implement polling or websocket here for message updates
                # But for MVP, the embedded UI handles this
                return

            # In API mode, stream messages from OpenCode
            messages = await self.client.get_messages(session.container_id)
            for message in messages:
                role = message.get("role", "unknown")
                content = message.get("content", "")
                yield f"[{role}] {content}\n"

        except Exception as e:
            logger.error(f"Error streaming messages for {session_id}: {e}")
            yield f"Error: {str(e)}\n"

    def get_vibe_room(self, room_id: str) -> Optional[VibeRoom]:
        """Get vibe room by room ID (for UI embedding)."""
        return self.vibe_manager.get_room(room_id)

    def get_vibe_room_by_session(self, session_id: str) -> Optional[VibeRoom]:
        """Get vibe room associated with a session."""
        return self.vibe_manager.get_room_by_session(session_id)

    def create_vibe_session_url(self, session_id: str, base_url: str = "http://localhost:8000") -> Optional[str]:
        """Create URL for accessing the vibe coding session."""
        session = self.sessions.get(session_id)
        if not session or not session.vibe_room_id:
            return None

        # For UI embedding mode, return the vibe room URL
        return f"{base_url}/vibe/{session.vibe_room_id}"

    async def cleanup_old_sessions(self, older_than_hours: int = 24) -> int:
        """Clean up old sessions."""
        cutoff_time = datetime.utcnow().replace(hour=datetime.utcnow().hour - older_than_hours)

        cleaned = 0
        for session_id, session in list(self.sessions.items()):
            if session.ended_at and session.ended_at < cutoff_time:
                try:
                    if session.container_id:
                        await self.client.delete_session(session.container_id)
                    del self.sessions[session_id]
                    cleaned += 1
                except Exception as e:
                    logger.warning(f"Error cleaning up session {session_id}: {e}")

        logger.info(f"Cleaned up {cleaned} old sessions")
        return cleaned

    def _parse_diff_files(self, diff: str) -> List[str]:
        """Parse diff output to extract changed files."""
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

    async def close(self) -> None:
        """Close the integration service and cleanup."""
        logger.info("Closing OpenCode integration service")

        # Stop all active sessions
        for session in list(self.sessions.values()):
            if session.status in [SessionStatus.RUNNING, SessionStatus.INITIALIZING]:
                try:
                    await self.stop_session(session.id)
                except Exception as e:
                    logger.warning(f"Error stopping session {session.id}: {e}")

        self.sessions.clear()
        logger.info("OpenCode integration service closed")

    # Sync wrappers for synchronous callers (like comment handler)
    def create_session_sync(
        self,
        context: IssueContext,
        execution_mode: ExecutionMode = ExecutionMode.BUILD,
        timeout_minutes: Optional[int] = None,
        owner_id: str = "single-user"
    ) -> Session:
        """Synchronous wrapper for create_session."""
        return asyncio.run(self.create_session(
            context=context,
            execution_mode=execution_mode,
            timeout_minutes=timeout_minutes,
            owner_id=owner_id
        ))

    def stop_session_sync(self, session_id: str, force: bool = False) -> bool:
        """Synchronous wrapper for stop_session."""
        return asyncio.run(self.stop_session(session_id, force))

    def get_session_results_sync(self, session_id: str) -> Optional[ExecutionResult]:
        """Synchronous wrapper for get_session_results."""
        return asyncio.run(self.get_session_results(session_id))