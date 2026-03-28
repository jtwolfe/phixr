"""OpenCode integration service — orchestrates sessions between GitLab and OpenCode.

This is the main coordination layer. It:
- Creates persistent OpenCode sessions linked to GitLab issues (one per issue)
- Forwards messages from GitLab comments to the active session
- Monitors sessions via SSE events (completion, errors, permissions)
- Reports results back to GitLab as issue comments
- Manages vibe rooms for shared visibility

Session state is persisted in Redis (via SessionStore) so it survives restarts.
"""

import asyncio
import base64
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from phixr.bridge.opencode_client import OpenCodeServerClient, OpenCodeServerError
from phixr.collaboration.vibe_room_manager import VibeRoomManager
from phixr.config.sandbox_config import SandboxConfig
from phixr.integration.session_store import SessionStore
from phixr.models.execution_models import (
    Session, SessionStatus, VibeRoom,
)
from phixr.models.issue_context import IssueContext

logger = logging.getLogger(__name__)


class OpenCodeIntegrationService:
    """Orchestrates OpenCode sessions for GitLab issue automation."""

    def __init__(
        self,
        config: SandboxConfig,
        base_url: str = "http://localhost:8000",
        redis_url: Optional[str] = None,
    ):
        self.config = config
        self.client = OpenCodeServerClient(config.opencode_server_url)
        self.vibe_manager = VibeRoomManager()
        self.base_url = base_url
        self.store = SessionStore(redis_url)

        # In-memory cache of live Session objects (for monitoring tasks).
        # The store is the source of truth; this is the hot cache.
        self.sessions: Dict[str, Session] = {}
        # Keep these as convenience accessors backed by the store
        self.opencode_session_ids = _StoreProxy(self.store, "oc_id")
        self.opencode_session_slugs = _StoreProxy(self.store, "oc_slug")

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        return await self.client.health_check()

    # ── Issue-Session Mapping ────────────────────────────────────────────

    def get_active_session_for_issue(
        self, project_id: int, issue_id: int
    ) -> Optional[Session]:
        """Return the active session for an issue, or None."""
        session_id = self.store.get_issue_session(project_id, issue_id)
        if not session_id:
            return None
        session = self._get_session(session_id)
        if session and session.status == SessionStatus.RUNNING:
            return session
        # Stale mapping — clean up
        self.store.clear_issue_session(project_id, issue_id)
        return None

    def _get_session(self, session_id: str) -> Optional[Session]:
        """Get session from in-memory cache, falling back to store."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        # Try to reconstruct from store
        data = self.store.get_session(session_id)
        if data:
            try:
                session = Session(**data)
                self.sessions[session_id] = session
                return session
            except Exception as e:
                logger.warning(f"Failed to reconstruct session {session_id}: {e}")
        return None

    def _persist_session(self, session: Session) -> None:
        """Save session to both in-memory cache and store."""
        self.sessions[session.id] = session
        self.store.save_session(session.id, session.model_dump())

    # ── Session Lifecycle ────────────────────────────────────────────────

    async def create_session(
        self,
        context: IssueContext,
        project_id: int,
        timeout_minutes: int = 30,
        owner_id: str = "system",
        vibe: bool = False,
    ) -> Session:
        """Create an OpenCode session linked to a GitLab issue.

        Enforces one active session per issue.
        """
        existing = self.get_active_session_for_issue(project_id, context.issue_id)
        if existing:
            raise ValueError(
                f"Session already active for issue {context.issue_id}: {existing.id}"
            )

        # Create session on OpenCode
        title = f"Issue #{context.issue_id}: {context.title}"
        oc_session = await self.client.create_session(title=title)
        oc_session_id = oc_session["id"]

        # Build Phixr session
        session_id = f"sess-{context.issue_id}-{uuid.uuid4().hex[:8]}"
        session = Session(
            id=session_id,
            issue_id=context.issue_id,
            repo_url=context.repo_url,
            branch=context.branch or f"ai-work/issue-{context.issue_id}",
            status=SessionStatus.RUNNING,
            timeout_minutes=timeout_minutes,
            started_at=datetime.utcnow(),
            container_id=oc_session_id,
        )

        # Persist everything
        self._persist_session(session)
        self.store.set_opencode_id(session_id, oc_session_id)
        self.store.set_opencode_slug(session_id, oc_session.get("slug", ""))
        self.store.set_issue_session(project_id, context.issue_id, session_id)

        # Send initial prompt
        prompt = self._build_initial_prompt(context)
        system_instructions = self._build_system_instructions(context)

        await self.client.send_prompt(
            session_id=oc_session_id,
            message=prompt,
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
            f"issue={context.issue_id}, vibe={vibe})"
        )
        return session

    async def send_followup(
        self, session_id: str, message: str, author: str = "user"
    ) -> bool:
        """Forward a message from a GitLab comment to the active session."""
        session = self._get_session(session_id)
        if not session or session.status != SessionStatus.RUNNING:
            return False

        oc_session_id = self.store.get_opencode_id(session_id)
        if not oc_session_id:
            return False

        prompt = f"**{author}** says:\n\n{message}"
        await self.client.send_prompt(session_id=oc_session_id, message=prompt)

        logger.info(f"Forwarded message to session {session_id} from {author}")
        return True

    async def monitor_session(
        self,
        session_id: str,
        gitlab_client,
        project_id: int,
        issue_id: int,
    ) -> None:
        """Monitor an OpenCode session via SSE until completion."""
        session = self._get_session(session_id)
        if not session:
            logger.error(f"Cannot monitor unknown session: {session_id}")
            return

        oc_session_id = self.store.get_opencode_id(session_id)
        if not oc_session_id:
            logger.error(f"No OpenCode session ID for: {session_id}")
            return

        timeout = session.timeout_minutes * 60

        try:
            await asyncio.wait_for(
                self._monitor_events(oc_session_id, session_id),
                timeout=timeout,
            )
            session.status = SessionStatus.COMPLETED
            session.ended_at = datetime.utcnow()
            self._persist_session(session)
            await self._post_results_to_gitlab(
                gitlab_client, project_id, issue_id, session
            )

        except asyncio.TimeoutError:
            logger.warning(f"Session {session_id} timed out after {timeout}s")
            session.status = SessionStatus.TIMEOUT
            session.ended_at = datetime.utcnow()
            self._persist_session(session)
            try:
                await self.client.abort_session(oc_session_id)
            except Exception:
                pass
            self._post_comment(
                gitlab_client, project_id, issue_id,
                f"⏰ **Session Timed Out**\n\n"
                f"Session `{session_id}` exceeded the {session.timeout_minutes} minute limit.\n"
                f"The session has been aborted. Start a new one with `@phixr-bot /session`."
            )

        except Exception as e:
            logger.error(f"Error monitoring session {session_id}: {e}", exc_info=True)
            session.status = SessionStatus.ERROR
            session.ended_at = datetime.utcnow()
            session.errors.append(str(e))
            self._persist_session(session)
            self._post_comment(
                gitlab_client, project_id, issue_id,
                f"❌ **Session Error**\n\n"
                f"Session `{session_id}` encountered an error:\n```\n{str(e)[:500]}\n```"
            )

        finally:
            self.store.clear_issue_session(project_id, issue_id)

    async def _monitor_events(self, oc_session_id: str, phixr_session_id: str) -> None:
        """Watch SSE stream until the target session goes idle."""
        await asyncio.sleep(1)

        try:
            async for event in self.client.subscribe_events():
                event_type = event.get("type", "")
                properties = event.get("properties", event)
                event_session_id = properties.get("sessionID", "")

                if event_session_id and event_session_id != oc_session_id:
                    continue

                if event_type == "permission.asked":
                    perm_id = properties.get("id")
                    if perm_id:
                        logger.info(
                            f"Auto-approving permission {perm_id} "
                            f"({properties.get('permission', '?')})"
                        )
                        await self.client.reply_permission(perm_id, "always")
                    continue

                if event_type == "question.asked":
                    q_id = properties.get("id")
                    if q_id:
                        questions = properties.get("questions", [])
                        answers = []
                        for q in questions:
                            options = q.get("options", [])
                            first = options[0]["label"] if options else "yes"
                            answers.append([first])
                            logger.info(
                                f"Auto-answering question {q_id}: "
                                f"{q.get('question', '?')[:80]} → {first}"
                            )
                        await self.client.reply_question(q_id, answers)
                    continue

                if event_type == "session.error":
                    error_msg = properties.get("error", "Unknown error")
                    logger.error(f"Session error for {oc_session_id}: {error_msg}")
                    session = self.sessions.get(phixr_session_id)
                    if session:
                        session.errors.append(str(error_msg))
                    raise OpenCodeServerError(f"OpenCode session error: {error_msg}")

                if event_type in ("session.updated", "session.status", "message.updated") and (
                    event_session_id == oc_session_id or not event_session_id
                ):
                    try:
                        statuses = await self.client.get_session_status()
                        if oc_session_id not in statuses:
                            logger.info(f"Session {oc_session_id} is idle — processing complete")
                            return
                        status_info = statuses.get(oc_session_id, {})
                        if status_info.get("type") == "idle":
                            logger.info(f"Session {oc_session_id} is idle — processing complete")
                            return
                    except Exception as e:
                        logger.debug(f"Status check failed: {e}")

                if event_type == "message.part.updated":
                    part = properties.get("part", {})
                    if part.get("type") == "tool":
                        state = part.get("state", {})
                        tool_name = part.get("tool", "?")
                        status = state.get("status", "?")
                        if status == "running":
                            logger.info(f"  Tool: {tool_name} — {state.get('title', '')}")
                        elif status == "completed":
                            logger.debug(f"  Tool: {tool_name} — completed")

        except OpenCodeServerError:
            raise
        except Exception as e:
            logger.warning(f"SSE stream lost, falling back to polling: {e}")
            await self._poll_until_idle(oc_session_id)

    async def _poll_until_idle(self, oc_session_id: str) -> None:
        """Fallback: poll session status until idle."""
        while True:
            await asyncio.sleep(5)
            try:
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
                            answers = [
                                [opts[0]["label"]] if (opts := qn.get("options", [])) else ["yes"]
                                for qn in qs
                            ]
                            await self.client.reply_question(q["id"], answers)
                except Exception:
                    pass

                statuses = await self.client.get_session_status()
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
        self, gitlab_client, project_id: int, issue_id: int, session: Session,
    ) -> None:
        oc_session_id = self.store.get_opencode_id(session.id)
        if not oc_session_id:
            return
        try:
            messages = await self.client.get_messages(oc_session_id, limit=50)
        except Exception as e:
            logger.error(f"Failed to get messages for results: {e}")
            self._post_comment(
                gitlab_client, project_id, issue_id,
                f"✅ **Session Complete** (`{session.id}`)\n\n"
                f"Session finished but results could not be retrieved."
            )
            return

        result_text = self._extract_assistant_text(messages)
        diff_summary = await self._get_diff_summary(oc_session_id, messages)
        comment = (
            f"✅ **Session Complete**\n\n"
            f"**Session:** `{session.id}`\n"
            f"**Branch:** `{session.branch}`\n\n"
            f"{diff_summary}"
            f"---\n\n{result_text[:15000]}"
        )
        self._post_comment(gitlab_client, project_id, issue_id, comment)

    async def _get_diff_summary(self, oc_session_id: str, messages: List[dict]) -> str:
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
        all_text = []
        for msg in messages:
            info = msg.get("info", {})
            if info.get("role") != "assistant":
                continue
            parts = msg.get("parts", [])
            for part in parts:
                if part.get("type") == "text":
                    text = part.get("text", "").strip()
                    if text:
                        all_text.append(text)
        return "\n\n---\n\n".join(all_text) if all_text else "_No text output from AI._"

    @staticmethod
    def _post_comment(gitlab_client, project_id: int, issue_id: int, body: str) -> None:
        try:
            gitlab_client.add_issue_comment(project_id, issue_id, body)
        except Exception as e:
            logger.error(f"Failed to post GitLab comment: {e}")

    # ── Prompt Building ──────────────────────────────────────────────────

    @staticmethod
    def _build_initial_prompt(context: IssueContext) -> str:
        comments_text = ""
        if context.comments:
            comments_text = "\n\n**Recent Comments:**\n"
            for c in context.comments[-10:]:
                author = c.get("author", "unknown")
                body = c.get("body", "")[:500]
                comments_text += f"- **{author}**: {body}\n"

        return f"""## Issue #{context.issue_id}: {context.title}

**URL:** {context.url}
**Author:** {context.author}
**Assignees:** {', '.join(context.assignees) or 'None'}
**Labels:** {', '.join(context.labels) or 'None'}

## Description

{context.description or 'No description provided.'}
{comments_text}

## Your Task

Read the issue above and work on it. Analyse the codebase, create a plan, and implement the changes as needed. Use your judgement — if the issue asks for a plan, produce a plan. If it asks for implementation, implement it. If it asks for a review, review.

When you're done, summarise what you did.
"""

    def _build_system_instructions(self, context: IssueContext) -> str:
        instructions = [
            "You are Phixr, an AI coding assistant integrated with GitLab.",
            f"You are working on issue #{context.issue_id} in repository {context.repo_name or 'unknown'}.",
            f"The target branch is: {context.branch}",
            "",
            "You are in a persistent session linked to this GitLab issue.",
            "The user may send follow-up messages — treat this as an ongoing conversation.",
            "When you finish a piece of work, summarise what you did clearly.",
        ]
        if context.repo_url:
            repo_url = context.repo_url
            git_token = self.config.git_provider_token
            if git_token and '://' in repo_url:
                scheme, rest = repo_url.split('://', 1)
                repo_url = f"{scheme}://oauth2:{git_token}@{rest}"
            instructions.append(
                f"\nIMPORTANT: First clone the repository and switch to the working branch:\n"
                f"  git clone {repo_url} /tmp/workspace && cd /tmp/workspace\n"
                f"  git checkout -b {context.branch} origin/main || git checkout {context.branch}\n"
                f"All work must be done inside /tmp/workspace."
            )
        return "\n".join(instructions)

    # ── Session Queries ──────────────────────────────────────────────────

    async def get_session(self, session_id: str) -> Optional[Session]:
        return self._get_session(session_id)

    async def list_sessions(
        self, status_filter: Optional[SessionStatus] = None
    ) -> List[Session]:
        all_data = self.store.list_sessions()
        sessions = []
        for data in all_data:
            try:
                s = Session(**data)
                sessions.append(s)
            except Exception:
                continue
        if status_filter:
            sessions = [s for s in sessions if s.status == status_filter]
        return sessions

    async def get_session_results(self, session_id: str) -> Optional[dict]:
        session = self._get_session(session_id)
        if not session:
            return None
        oc_session_id = self.store.get_opencode_id(session_id)
        if not oc_session_id:
            return None
        try:
            messages = await self.client.get_messages(oc_session_id)
            text = self._extract_assistant_text(messages)
            return {
                "session_id": session_id,
                "status": session.status,
                "text": text,
                "message_count": len(messages),
            }
        except Exception as e:
            logger.error(f"Failed to get results: {e}")
            return None

    async def stop_session(self, session_id: str) -> bool:
        session = self._get_session(session_id)
        if not session:
            return False
        oc_session_id = self.store.get_opencode_id(session_id)
        if oc_session_id:
            try:
                await self.client.abort_session(oc_session_id)
            except Exception as e:
                logger.warning(f"Failed to abort OpenCode session: {e}")
        session.status = SessionStatus.STOPPED
        session.ended_at = datetime.utcnow()
        self._persist_session(session)
        self.store.clear_issue_session_by_session_id(session_id)
        return True

    # ── OpenCode Session URLs ────────────────────────────────────────────

    def get_opencode_session_url(self, session_id: str) -> Optional[str]:
        """Build the correct OpenCode web UI URL for a session.

        Uses opencode_public_url if configured (for when the server URL
        is a Docker-internal hostname like opencode-server:4096).
        """
        oc_session_id = self.store.get_opencode_id(session_id)
        if not oc_session_id:
            return None
        base = self.config.opencode_public_url or self.config.opencode_server_url
        encoded_dir = base64.urlsafe_b64encode(b"/").decode().rstrip("=")
        return f"{base}/{encoded_dir}/session/{oc_session_id}"

    # ── Vibe Room Delegation ─────────────────────────────────────────────

    def get_vibe_room(self, room_id: str) -> Optional[VibeRoom]:
        return self.vibe_manager.get_room(room_id)

    def get_vibe_room_by_session(self, session_id: str) -> Optional[VibeRoom]:
        return self.vibe_manager.get_room_by_session(session_id)

    def create_vibe_session_url(self, session_id: str) -> Optional[str]:
        room = self.vibe_manager.get_room_by_session(session_id)
        if room:
            return f"{self.base_url}/vibe/{room.id}"
        return None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def close(self) -> None:
        await self.client.close()
        logger.info("OpenCode integration service closed")


class _StoreProxy:
    """Dict-like proxy that reads/writes through SessionStore.

    Provides backward compatibility for code that accesses
    opencode_session_ids[key] and opencode_session_slugs[key].
    """

    def __init__(self, store: SessionStore, kind: str):
        self._store = store
        self._kind = kind  # "oc_id" or "oc_slug"

    def get(self, session_id: str, default=None):
        if self._kind == "oc_id":
            return self._store.get_opencode_id(session_id) or default
        return self._store.get_opencode_slug(session_id) or default

    def __getitem__(self, session_id: str):
        val = self.get(session_id)
        if val is None:
            raise KeyError(session_id)
        return val

    def __setitem__(self, session_id: str, value: str):
        if self._kind == "oc_id":
            self._store.set_opencode_id(session_id, value)
        else:
            self._store.set_opencode_slug(session_id, value)

    def __contains__(self, session_id: str):
        return self.get(session_id) is not None
