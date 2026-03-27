"""OpenCode integration service — orchestrates sessions between GitLab and OpenCode.

This is the main coordination layer. It:
- Creates OpenCode sessions with GitLab issue context
- Sends prompts to OpenCode via the async API
- Monitors sessions via SSE events (completion, errors, permissions)
- Reports results back to GitLab as issue comments
- Manages vibe rooms for shared visibility
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional

from phixr.bridge.opencode_client import OpenCodeServerClient, OpenCodeServerError
from phixr.collaboration.vibe_room_manager import VibeRoomManager
from phixr.config.sandbox_config import SandboxConfig
from phixr.models.execution_models import (
    ExecutionMode, Session, SessionStatus, VibeRoom,
)
from phixr.models.issue_context import IssueContext

logger = logging.getLogger(__name__)


class OpenCodeIntegrationService:
    """Orchestrates OpenCode sessions for GitLab issue automation.

    Thin layer that translates between Phixr's domain (GitLab issues,
    commands, vibe rooms) and OpenCode's HTTP API (sessions, prompts, events).
    """

    def __init__(self, config: SandboxConfig, base_url: str = "http://localhost:8000"):
        """Initialize the integration service.

        Args:
            config: Sandbox configuration with OpenCode server URL etc.
            base_url: Phixr's own public URL (for vibe room links).
        """
        self.config = config
        self.client = OpenCodeServerClient(config.opencode_server_url)
        self.vibe_manager = VibeRoomManager()
        self.base_url = base_url

        # Track sessions: phixr_session_id -> Session model
        self.sessions: Dict[str, Session] = {}
        # Map phixr session IDs to OpenCode session IDs
        self.opencode_session_ids: Dict[str, str] = {}

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Check if the OpenCode server is reachable."""
        return await self.client.health_check()

    # ── Session Lifecycle ────────────────────────────────────────────────

    async def create_session(
        self,
        context: IssueContext,
        execution_mode: ExecutionMode = ExecutionMode.BUILD,
        timeout_minutes: int = 30,
        owner_id: str = "system",
    ) -> Session:
        """Create an OpenCode session and send the initial prompt.

        1. Creates a session on the OpenCode server
        2. Sends the issue context as an async prompt
        3. Creates a vibe room for shared visibility
        4. Returns a Phixr Session object for tracking

        Args:
            context: GitLab issue context
            execution_mode: PLAN, BUILD, or REVIEW
            timeout_minutes: Session timeout
            owner_id: Who initiated this (GitLab username or "system")
        """
        # Create session on OpenCode
        title = f"[{execution_mode.value}] {context.title} (issue #{context.issue_id})"
        oc_session = await self.client.create_session(title=title)
        oc_session_id = oc_session["id"]

        # Build Phixr session
        session_id = f"sess-{context.issue_id}-{int(datetime.utcnow().timestamp())}"
        session = Session(
            id=session_id,
            issue_id=context.issue_id,
            repo_url=context.repo_url,
            branch=context.branch or f"ai-work/issue-{context.issue_id}",
            status=SessionStatus.RUNNING,
            mode=execution_mode,
            timeout_minutes=timeout_minutes,
            started_at=datetime.utcnow(),
            container_id=oc_session_id,  # Store OpenCode session ID here
        )

        self.sessions[session_id] = session
        self.opencode_session_ids[session_id] = oc_session_id

        # Send initial prompt with context
        agent = "plan" if execution_mode == ExecutionMode.PLAN else "build"
        prompt = self._build_prompt(context, execution_mode)
        system_instructions = self._build_system_instructions(context, execution_mode)

        await self.client.send_prompt(
            session_id=oc_session_id,
            message=prompt,
            agent=agent,
            system=system_instructions,
        )

        # Create vibe room
        try:
            self.vibe_manager.create_room(
                session=session,
                owner_id=owner_id,
                room_name=f"Issue #{context.issue_id}: {context.title[:50]}",
            )
        except Exception as e:
            logger.warning(f"Failed to create vibe room: {e}")

        logger.info(
            f"Session {session_id} created (opencode={oc_session_id}, "
            f"mode={execution_mode.value}, agent={agent})"
        )
        return session

    async def monitor_session(
        self,
        session_id: str,
        gitlab_client,
        project_id: int,
        issue_id: int,
    ) -> None:
        """Monitor an OpenCode session via SSE until completion.

        Subscribes to the event stream, auto-approves permissions,
        and posts results back to GitLab when done.

        This runs as a background asyncio task — it blocks until the
        session completes, errors, or times out.
        """
        session = self.sessions.get(session_id)
        if not session:
            logger.error(f"Cannot monitor unknown session: {session_id}")
            return

        oc_session_id = self.opencode_session_ids.get(session_id)
        if not oc_session_id:
            logger.error(f"No OpenCode session ID for: {session_id}")
            return

        timeout = session.timeout_minutes * 60
        mode_label = session.mode if isinstance(session.mode, str) else session.mode

        try:
            await asyncio.wait_for(
                self._monitor_events(oc_session_id, session_id),
                timeout=timeout,
            )

            # Session completed — extract and post results
            session.status = SessionStatus.COMPLETED
            session.ended_at = datetime.utcnow()
            await self._post_results_to_gitlab(
                gitlab_client, project_id, issue_id, session, mode_label
            )

        except asyncio.TimeoutError:
            logger.warning(f"Session {session_id} timed out after {timeout}s")
            session.status = SessionStatus.TIMEOUT
            session.ended_at = datetime.utcnow()

            # Try to abort the OpenCode session
            try:
                await self.client.abort_session(oc_session_id)
            except Exception:
                pass

            self._post_comment(
                gitlab_client, project_id, issue_id,
                f"⏰ **Session Timed Out**\n\n"
                f"Session `{session_id}` exceeded the {session.timeout_minutes} minute limit.\n"
                f"The session has been aborted. You can retry with `/ai-{mode_label}`."
            )

        except Exception as e:
            logger.error(f"Error monitoring session {session_id}: {e}", exc_info=True)
            session.status = SessionStatus.ERROR
            session.ended_at = datetime.utcnow()
            session.errors.append(str(e))

            self._post_comment(
                gitlab_client, project_id, issue_id,
                f"❌ **Session Error**\n\n"
                f"Session `{session_id}` encountered an error:\n```\n{str(e)[:500]}\n```"
            )

    async def _monitor_events(self, oc_session_id: str, phixr_session_id: str) -> None:
        """Internal event loop: watch SSE stream until the target session goes idle."""
        # Give the prompt a moment to start processing
        await asyncio.sleep(1)

        try:
            async for event in self.client.subscribe_events():
                event_type = event.get("type", "")

                # Filter to events for our session
                properties = event.get("properties", event)
                event_session_id = properties.get("sessionID", "")

                if event_session_id and event_session_id != oc_session_id:
                    continue

                # Auto-approve permissions
                if event_type == "permission.asked":
                    perm_id = properties.get("id")
                    if perm_id:
                        logger.info(
                            f"Auto-approving permission {perm_id} "
                            f"({properties.get('permission', '?')})"
                        )
                        await self.client.reply_permission(perm_id, "always")
                    continue

                # Auto-answer questions (select first option for each)
                if event_type == "question.asked":
                    q_id = properties.get("id")
                    if q_id:
                        questions = properties.get("questions", [])
                        answers = []
                        for q in questions:
                            options = q.get("options", [])
                            # Pick first option label as the answer
                            first = options[0]["label"] if options else "yes"
                            answers.append([first])
                            logger.info(
                                f"Auto-answering question {q_id}: "
                                f"{q.get('question', '?')[:80]} → {first}"
                            )
                        await self.client.reply_question(q_id, answers)
                    continue

                # Session error
                if event_type == "session.error":
                    error_msg = properties.get("error", "Unknown error")
                    logger.error(f"Session error for {oc_session_id}: {error_msg}")
                    session = self.sessions.get(phixr_session_id)
                    if session:
                        session.errors.append(str(error_msg))
                    raise OpenCodeServerError(f"OpenCode session error: {error_msg}")

                # Check if session went idle (meaning prompt processing finished)
                # Only check on events that belong to our session
                if event_type in ("session.updated", "session.status", "message.updated") and (
                    event_session_id == oc_session_id or not event_session_id
                ):
                    try:
                        statuses = await self.client.get_session_status()
                        # OpenCode returns {} when all sessions are idle,
                        # or {id: {type: "busy"|"retry"}} for active sessions.
                        # Session is idle when it's NOT in the status dict.
                        if oc_session_id not in statuses:
                            logger.info(f"Session {oc_session_id} is idle — processing complete")
                            return
                        status_info = statuses.get(oc_session_id, {})
                        if status_info.get("type") == "idle":
                            logger.info(f"Session {oc_session_id} is idle — processing complete")
                            return
                    except Exception as e:
                        logger.debug(f"Status check failed: {e}")

                # Log tool activity
                if event_type == "message.part.updated":
                    part = properties.get("part", {})
                    if part.get("type") == "tool":
                        state = part.get("state", {})
                        tool_name = part.get("tool", "?")
                        status = state.get("status", "?")
                        if status == "running":
                            title = state.get("title", "")
                            logger.info(f"  Tool: {tool_name} — {title}")
                        elif status == "completed":
                            logger.debug(f"  Tool: {tool_name} — completed")

        except OpenCodeServerError:
            raise
        except Exception as e:
            # If SSE dies, fall back to polling
            logger.warning(f"SSE stream lost, falling back to polling: {e}")
            await self._poll_until_idle(oc_session_id)

    async def _poll_until_idle(self, oc_session_id: str) -> None:
        """Fallback: poll session status until idle."""
        while True:
            await asyncio.sleep(5)
            try:
                # Auto-approve permissions and answer questions while polling
                try:
                    pending = await self.client.list_permissions()
                    for perm in pending:
                        if perm.get("sessionID") == oc_session_id:
                            await self.client.reply_permission(perm["id"], "always")
                except Exception:
                    pass
                try:
                    questions = await self.client.list_questions()
                    for q in questions:
                        if q.get("sessionID") == oc_session_id:
                            qs = q.get("questions", [])
                            answers = [[opts[0]["label"]] if (opts := qn.get("options", [])) else ["yes"] for qn in qs]
                            await self.client.reply_question(q["id"], answers)
                except Exception:
                    pass

                statuses = await self.client.get_session_status()
                # Session is idle when NOT in status dict, or type is "idle"
                if oc_session_id not in statuses:
                    logger.info(f"Session {oc_session_id} is idle (polled)")
                    return
                status_info = statuses.get(oc_session_id, {})
                status_type = status_info.get("type", "idle")
                if status_type == "idle":
                    logger.info(f"Session {oc_session_id} is idle (polled)")
                    return
                elif status_type == "retry":
                    logger.warning(
                        f"Session {oc_session_id} retrying: "
                        f"{status_info.get('message', '?')}"
                    )
            except Exception as e:
                logger.warning(f"Poll status check failed: {e}")

    # ── GitLab Reporting ─────────────────────────────────────────────────

    async def _post_results_to_gitlab(
        self, gitlab_client, project_id: int, issue_id: int,
        session: Session, mode_label: str,
    ) -> None:
        """Extract messages from completed session and post summary to GitLab."""
        oc_session_id = self.opencode_session_ids.get(session.id)
        if not oc_session_id:
            return

        try:
            messages = await self.client.get_messages(oc_session_id, limit=50)
        except Exception as e:
            logger.error(f"Failed to get messages for results: {e}")
            self._post_comment(
                gitlab_client, project_id, issue_id,
                f"✅ **Session Complete** (`{session.id}`)\n\n"
                f"The {mode_label} session finished but results could not be retrieved."
            )
            return

        # Extract the assistant's text content from messages
        result_text = self._extract_assistant_text(messages)

        if mode_label == "plan":
            comment = (
                f"📋 **Implementation Plan Ready**\n\n"
                f"**Session:** `{session.id}`\n\n"
                f"---\n\n{result_text[:15000]}"
            )
        else:
            # Get diff summary if available
            diff_summary = await self._get_diff_summary(oc_session_id, messages)
            comment = (
                f"✅ **{mode_label.title()} Complete**\n\n"
                f"**Session:** `{session.id}`\n"
                f"**Branch:** `{session.branch}`\n\n"
                f"{diff_summary}"
                f"---\n\n{result_text[:12000]}"
            )

        self._post_comment(gitlab_client, project_id, issue_id, comment)

    async def _get_diff_summary(self, oc_session_id: str,
                                messages: List[dict]) -> str:
        """Try to get a file diff summary from the session."""
        try:
            for msg in reversed(messages):
                if msg.get("info", {}).get("role") == "assistant":
                    msg_id = msg["info"]["id"]
                    diffs = await self.client.get_diff(oc_session_id, msg_id)
                    if diffs:
                        files = [d.get("path", "?") for d in diffs]
                        additions = sum(d.get("additions", 0) for d in diffs)
                        deletions = sum(d.get("deletions", 0) for d in diffs)
                        return (
                            f"**Files changed:** {len(files)}\n"
                            f"**Changes:** +{additions} / -{deletions}\n\n"
                        )
                    break
        except Exception as e:
            logger.debug(f"Could not get diff summary: {e}")
        return ""

    @staticmethod
    def _extract_assistant_text(messages: List[dict]) -> str:
        """Extract text content from the last assistant message."""
        for msg in reversed(messages):
            info = msg.get("info", {})
            if info.get("role") != "assistant":
                continue

            parts = msg.get("parts", [])
            text_parts = []
            for part in parts:
                if part.get("type") == "text":
                    text = part.get("text", "")
                    if text:
                        text_parts.append(text)

            if text_parts:
                return "\n\n".join(text_parts)

        return "_No text output from AI._"

    @staticmethod
    def _post_comment(gitlab_client, project_id: int, issue_id: int, body: str) -> None:
        """Post a comment to a GitLab issue (sync helper)."""
        try:
            gitlab_client.add_issue_comment(project_id, issue_id, body)
        except Exception as e:
            logger.error(f"Failed to post GitLab comment: {e}")

    # ── Prompt Building ──────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(context: IssueContext, mode: ExecutionMode) -> str:
        """Build the user prompt from issue context."""
        comments_text = ""
        if context.comments:
            comments_text = "\n\n**Recent Comments:**\n"
            for c in context.comments[-10:]:
                author = c.get("author", "unknown")
                body = c.get("body", "")[:500]
                comments_text += f"- **{author}**: {body}\n"

        if mode == ExecutionMode.PLAN:
            task = (
                "Analyze this issue and create a detailed implementation plan.\n"
                "Review the codebase, identify files to modify, and outline steps."
            )
        elif mode == ExecutionMode.REVIEW:
            task = (
                "Review the code changes related to this issue.\n"
                "Check for bugs, code quality, security, and test coverage."
            )
        else:
            task = (
                "Implement the changes described in this issue.\n"
                "Write code, create tests, and ensure everything works."
            )

        return f"""## Issue #{context.issue_id}: {context.title}

**URL:** {context.url}
**Author:** {context.author}
**Assignees:** {', '.join(context.assignees) or 'None'}
**Labels:** {', '.join(context.labels) or 'None'}

## Description

{context.description or 'No description provided.'}
{comments_text}

## Task

{task}
"""

    @staticmethod
    def _build_system_instructions(context: IssueContext, mode: ExecutionMode) -> str:
        """Build system instructions injected via the 'system' field."""
        instructions = [
            "You are Phixr, an AI coding assistant integrated with GitLab.",
            f"You are working on issue #{context.issue_id} in repository {context.repo_name or 'unknown'}.",
            f"The target branch is: {context.branch}",
        ]

        if mode == ExecutionMode.PLAN:
            instructions.append(
                "You are in PLAN mode. Analyze the codebase and produce a structured "
                "implementation plan. Do not make changes — only analyze and plan."
            )
        elif mode == ExecutionMode.BUILD:
            instructions.append(
                "You are in BUILD mode. Implement the requested changes. "
                "Write clean, tested code. Commit your changes when done."
            )
        elif mode == ExecutionMode.REVIEW:
            instructions.append(
                "You are in REVIEW mode. Review code changes for quality, "
                "correctness, security, and test coverage."
            )

        return "\n".join(instructions)

    # ── Session Queries ──────────────────────────────────────────────────

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get a Phixr session by ID."""
        return self.sessions.get(session_id)

    async def list_sessions(
        self, status_filter: Optional[SessionStatus] = None
    ) -> List[Session]:
        """List tracked Phixr sessions, optionally filtered by status."""
        sessions = list(self.sessions.values())
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]
        return sessions

    async def get_session_results(self, session_id: str) -> Optional[dict]:
        """Get results for a completed session."""
        session = self.sessions.get(session_id)
        if not session:
            return None

        oc_session_id = self.opencode_session_ids.get(session_id)
        if not oc_session_id:
            return None

        try:
            messages = await self.client.get_messages(oc_session_id)
            text = self._extract_assistant_text(messages)
            return {
                "session_id": session_id,
                "status": session.status,
                "mode": session.mode,
                "text": text,
                "message_count": len(messages),
            }
        except Exception as e:
            logger.error(f"Failed to get results: {e}")
            return None

    async def stop_session(self, session_id: str) -> bool:
        """Stop a running session."""
        session = self.sessions.get(session_id)
        if not session:
            return False

        oc_session_id = self.opencode_session_ids.get(session_id)
        if oc_session_id:
            try:
                await self.client.abort_session(oc_session_id)
            except Exception as e:
                logger.warning(f"Failed to abort OpenCode session: {e}")

        session.status = SessionStatus.STOPPED
        session.ended_at = datetime.utcnow()
        return True

    # ── Vibe Room Delegation ─────────────────────────────────────────────

    def get_vibe_room(self, room_id: str) -> Optional[VibeRoom]:
        return self.vibe_manager.get_room(room_id)

    def get_vibe_room_by_session(self, session_id: str) -> Optional[VibeRoom]:
        return self.vibe_manager.get_room_by_session(session_id)

    def create_vibe_session_url(self, session_id: str) -> Optional[str]:
        """Generate a URL for the vibe room associated with a session."""
        room = self.vibe_manager.get_room_by_session(session_id)
        if room:
            return f"{self.base_url}/vibe/{room.id}"
        return None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Shutdown: close HTTP client."""
        await self.client.close()
        logger.info("OpenCode integration service closed")
