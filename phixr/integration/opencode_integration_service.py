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

    def __init__(self, config: SandboxConfig, mode: IntegrationMode = IntegrationMode.UI_EMBED,
                 gitlab_token: Optional[str] = None, access_manager: Optional[Any] = None,
                 base_url: str = "http://localhost:8000"):
        """Initialize integration service.

        Args:
            config: Sandbox configuration
            mode: Integration mode (UI_EMBED for single user vibe coding)
            gitlab_token: GitLab bot token for repository cloning
            access_manager: Access management service
            base_url: Base URL for vibe room links
        """
        self.config = config
        self.mode = mode
        self.gitlab_token = gitlab_token
        self.access_manager = access_manager
        self.base_url = base_url
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

    async def monitor_plan_completion(self, session_id: str, gitlab_client, project_id: int, issue_id: int) -> None:
        """Monitor a planning session and send results back to GitLab.
        
        Polls OpenCode for messages and detects plan completion.
        """
        session = self.sessions.get(session_id)
        if not session:
            logger.error(f"Session not found for monitoring: {session_id}")
            return

        try:
            logger.info(f"Starting plan monitoring for session {session_id}")
            
            max_attempts = 45  # 7.5 minutes with 10s intervals
            attempts = 0
            plan_detected = False
            
            while attempts < max_attempts and not plan_detected:
                try:
                    messages = await self.client.get_messages(session.container_id)
                    message_count = len(messages)
                    
                    logger.debug(f"Session {session_id}: {message_count} messages on attempt {attempts + 1}/{max_attempts}")
                    
                    if message_count > 1:  # Initial message + AI response
                        last_message = messages[-1]
                        content = self._extract_text_from_message(last_message)
                        
                        # Check for plan completion
                        if self._detect_plan_completion(content, message_count):
                            logger.info(f"Plan completion detected for session {session_id}")
                            plan_detected = True
                            
                            # Extract plan from messages
                            plan_content = self._extract_plan_from_messages(messages)
                            
                            # Post to GitLab
                            await self._post_plan_to_gitlab(
                                gitlab_client, project_id, issue_id,
                                session, plan_content, messages
                            )
                            
                            session.status = SessionStatus.COMPLETED
                            session.ended_at = datetime.utcnow()
                            logger.info(f"Planning session completed: {session_id}")
                            return
                
                except Exception as e:
                    logger.warning(f"Error checking session {session_id} on attempt {attempts + 1}: {e}")
                    # Continue monitoring despite individual errors
                
                await asyncio.sleep(10)  # Check every 10 seconds
                attempts += 1
            
            # Handle timeout
            if not plan_detected:
                logger.warning(f"Planning session timed out after {max_attempts} attempts: {session_id}")
                await self._post_timeout_to_gitlab(gitlab_client, project_id, issue_id, session)
        
        except Exception as e:
            logger.error(f"Critical error monitoring planning session {session_id}: {e}", exc_info=True)
            await self._post_error_to_gitlab(gitlab_client, project_id, issue_id, session, str(e))

    def _extract_text_from_message(self, message: Dict[str, Any]) -> str:
        """Extract text content from an OpenCode message object.
        
        OpenCode messages have nested structure:
        {
            "info": {...},
            "parts": [
                {"type": "text", "text": "content"},
                ...
            ]
        }
        """
        # Try direct content/text fields first
        if 'content' in message and message['content']:
            return message['content']
        if 'text' in message and message['text']:
            return message['text']
        
        # Try nested parts structure
        if 'parts' in message and isinstance(message['parts'], list):
            text_parts = []
            for part in message['parts']:
                if isinstance(part, dict):
                    if 'text' in part and part['text']:
                        text_parts.append(part['text'])
                    elif 'content' in part and part['content']:
                        text_parts.append(part['content'])
            if text_parts:
                return '\n'.join(text_parts)
        
        return ''

    def _detect_plan_completion(self, content: str, message_count: int) -> bool:
        """Detect if content appears to be a completed plan."""
        if not content:
            return False
        
        content_lower = content.lower()
        
        # Check for plan indicators
        plan_indicators = [
            "implementation plan",
            "## plan",
            "## implementation plan",
            "## analysis",
            "## approach",
            "## files to",
            "## implementation steps",
            "## testing plan",
            "step 1:",
            "step-by-step plan",
        ]
        
        for indicator in plan_indicators:
            if indicator in content_lower:
                return True
        
        return False

    def _extract_plan_from_messages(self, messages: List[Dict]) -> str:
        """Extract planning content from messages."""
        plan_parts = []
        
        for message in messages[1:]:  # Skip initial context message
            content = self._extract_text_from_message(message)
            if content and len(content) > 50:  # Substantial content
                plan_parts.append(content)
        
        return '\n\n'.join(plan_parts)

    async def _post_plan_to_gitlab(self, gitlab_client, project_id: int, issue_id: int,
                                   session: Session, plan_content: str, messages: list = None) -> None:
        """Post completed plan to GitLab issue."""
        try:
            response = f"""## 📋 Implementation Plan Completed ✅

**Session ID:** `{session.id}`
**Issue:** #{issue_id}
**Branch:** `{getattr(session, 'branch', 'main')}`
**Generated at:** {datetime.utcnow().isoformat()}

### AI-Generated Implementation Plan

{plan_content}

---

### Next Steps

Reply to this comment with:
`@phixr-bot /ai-implement`

---

**Generated by Phixr + OpenCode Integration**
"""
            
            await gitlab_client.issues.update(issue_id, description=response)
            logger.info(f"Posted plan to GitLab issue #{issue_id}")
            
        except Exception as e:
            logger.error(f"Failed to post plan to GitLab: {e}")

    async def _post_timeout_to_gitlab(self, gitlab_client, project_id: int, issue_id: int, session: Session) -> None:
        """Post timeout message to GitLab issue."""
        try:
            message = f"""⏰ **Planning Session Timeout**

Session `{session.id}` did not complete within the timeout period.

Please try again with `/ai-plan` or provide additional context for refinement.
"""
            
            await gitlab_client.issues.update(issue_id, description=message)
            logger.warning(f"Posted timeout message to GitLab issue #{issue_id}")
            
        except Exception as e:
            logger.error(f"Failed to post timeout to GitLab: {e}")

    async def _post_error_to_gitlab(self, gitlab_client, project_id: int, issue_id: int, session: Session, error: str) -> None:
        """Post error message to GitLab issue."""
        try:
            message = f"""❌ **Planning Session Error**

Session `{session.id}` encountered an error:

```
{error}
```

Please try again with `/ai-plan` or contact support.
"""
            
            await gitlab_client.issues.update(issue_id, description=message)
            logger.error(f"Posted error message to GitLab issue #{issue_id}")
            
        except Exception as e:
            logger.error(f"Failed to post error to GitLab: {e}")


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