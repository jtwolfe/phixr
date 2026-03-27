"""HTTP + SSE client for OpenCode server API.

Communicates with OpenCode server running in headless mode.
Handles session CRUD, prompt sending, SSE event streaming,
and permission management.
"""

import json
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator

import httpx
from httpx_sse import aconnect_sse

logger = logging.getLogger(__name__)


class OpenCodeServerError(Exception):
    """Exception raised when OpenCode server API call fails."""
    pass


class OpenCodeServerClient:
    """Async client for OpenCode's HTTP API.

    Covers:
    - Session lifecycle (create, get, list, abort, delete)
    - Prompts (async fire-and-forget via prompt_async)
    - Messages (retrieve conversation history)
    - SSE event streaming (real-time session monitoring)
    - Permissions (list pending, auto-approve)
    - Diffs (file changes per message)
    """

    def __init__(self, server_url: str = "http://localhost:4096", timeout: int = 300):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"OpenCode client initialized: {self.server_url}")

    # ── Health ───────────────────────────────────────────────────────────

    async def health_check(self) -> bool:
        """Check if OpenCode server is responding."""
        try:
            response = await self.client.get(f"{self.server_url}/global/health")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"OpenCode health check failed: {e}")
            return False

    # ── Sessions ─────────────────────────────────────────────────────────

    async def create_session(self, title: Optional[str] = None,
                             parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new OpenCode session.

        Returns Session.Info dict with id, slug, title, time, etc.
        """
        payload = {}
        if title:
            payload["title"] = title
        if parent_id:
            payload["parentID"] = parent_id

        try:
            response = await self.client.post(
                f"{self.server_url}/session",
                json=payload if payload else None
            )
            response.raise_for_status()
            session = response.json()
            logger.info(f"Created OpenCode session: {session.get('id')}")
            return session
        except httpx.HTTPError as e:
            logger.error(f"Failed to create session: {e}")
            raise OpenCodeServerError(f"Session creation failed: {e}")

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details. Returns None if not found."""
        try:
            response = await self.client.get(f"{self.server_url}/session/{session_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise OpenCodeServerError(f"Failed to get session: {e}")
        except httpx.HTTPError as e:
            raise OpenCodeServerError(f"Failed to get session: {e}")

    async def list_sessions(self, directory: Optional[str] = None,
                            roots: bool = False,
                            limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List sessions, optionally filtered."""
        params = {}
        if directory:
            params["directory"] = directory
        if roots:
            params["roots"] = "true"
        if limit:
            params["limit"] = limit

        try:
            response = await self.client.get(
                f"{self.server_url}/session",
                params=params or None
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list sessions: {e}")
            raise OpenCodeServerError(f"Failed to list sessions: {e}")

    async def get_session_status(self) -> Dict[str, Any]:
        """Get status of all sessions.

        Returns dict of {session_id: {type: "idle"|"busy"|"retry", ...}}.
        """
        try:
            response = await self.client.get(f"{self.server_url}/session/status")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get session status: {e}")
            raise OpenCodeServerError(f"Failed to get session status: {e}")

    async def abort_session(self, session_id: str) -> bool:
        """Abort a running session."""
        try:
            response = await self.client.post(
                f"{self.server_url}/session/{session_id}/abort"
            )
            response.raise_for_status()
            logger.info(f"Session aborted: {session_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to abort session {session_id}: {e}")
            raise OpenCodeServerError(f"Failed to abort session: {e}")

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data."""
        try:
            response = await self.client.delete(
                f"{self.server_url}/session/{session_id}"
            )
            response.raise_for_status()
            logger.info(f"Session deleted: {session_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise OpenCodeServerError(f"Failed to delete session: {e}")

    # ── Prompts & Messages ───────────────────────────────────────────────

    async def send_prompt(self, session_id: str, message: str,
                          agent: Optional[str] = None,
                          system: Optional[str] = None,
                          provider_id: Optional[str] = None,
                          model_id: Optional[str] = None) -> None:
        """Send a prompt asynchronously (fire-and-forget).

        Uses POST /session/{id}/prompt_async which returns 204 immediately.
        Monitor progress via subscribe_events().

        Args:
            session_id: OpenCode session ID
            message: The prompt text
            agent: Agent to use ("plan", "build", etc.)
            system: Custom system instructions appended to agent prompt
            provider_id: LLM provider (e.g. "anthropic")
            model_id: Model ID (e.g. "claude-sonnet-4-20250514")
        """
        payload: Dict[str, Any] = {
            "parts": [{"type": "text", "text": message}]
        }
        if agent:
            payload["agent"] = agent
        if system:
            payload["system"] = system
        if provider_id and model_id:
            payload["model"] = {"providerID": provider_id, "modelID": model_id}

        try:
            response = await self.client.post(
                f"{self.server_url}/session/{session_id}/prompt_async",
                json=payload
            )
            response.raise_for_status()
            logger.info(f"Prompt sent to session {session_id} (agent={agent})")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send prompt: {e}")
            raise OpenCodeServerError(f"Prompt send failed: {e}")

    async def get_messages(self, session_id: str,
                           limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages from a session.

        Returns list of MessageV2.WithParts objects.
        """
        try:
            response = await self.client.get(
                f"{self.server_url}/session/{session_id}/message",
                params={"limit": limit}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            raise OpenCodeServerError(f"Failed to get messages: {e}")

    async def get_diff(self, session_id: str,
                       message_id: str) -> List[Dict[str, Any]]:
        """Get file diffs for a specific message."""
        try:
            response = await self.client.get(
                f"{self.server_url}/session/{session_id}/diff",
                params={"messageID": message_id}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get diff: {e}")
            raise OpenCodeServerError(f"Failed to get diff: {e}")

    # ── SSE Event Stream ─────────────────────────────────────────────────

    async def subscribe_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to the SSE event stream.

        Yields parsed event dicts. Each has at minimum a "type" field.
        Reconnects on connection drop.

        Events include:
        - message.updated, message.part.updated, message.part.delta
        - permission.asked, permission.replied
        - session.updated, session.error
        - server.heartbeat
        """
        while True:
            try:
                async with aconnect_sse(
                    self.client, "GET", f"{self.server_url}/event"
                ) as event_source:
                    async for sse in event_source.aiter_sse():
                        if not sse.data:
                            continue
                        try:
                            event = json.loads(sse.data)
                            yield event
                        except json.JSONDecodeError:
                            logger.debug(f"Non-JSON SSE data: {sse.data[:100]}")
                            continue
            except httpx.ReadTimeout:
                logger.debug("SSE stream timeout, reconnecting...")
                continue
            except httpx.HTTPError as e:
                logger.warning(f"SSE connection error: {e}, reconnecting in 2s...")
                import asyncio
                await asyncio.sleep(2)
                continue
            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                raise

    # ── Permissions ──────────────────────────────────────────────────────

    async def list_permissions(self) -> List[Dict[str, Any]]:
        """List pending permission requests."""
        try:
            response = await self.client.get(f"{self.server_url}/permission")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list permissions: {e}")
            raise OpenCodeServerError(f"Failed to list permissions: {e}")

    async def reply_permission(self, request_id: str,
                               reply: str = "always",
                               message: Optional[str] = None) -> bool:
        """Reply to a permission request.

        Args:
            request_id: The permission request ID
            reply: "once", "always", or "reject"
            message: Optional feedback message (useful for rejections)
        """
        payload: Dict[str, Any] = {"reply": reply}
        if message:
            payload["message"] = message

        try:
            response = await self.client.post(
                f"{self.server_url}/permission/{request_id}/reply",
                json=payload
            )
            response.raise_for_status()
            logger.debug(f"Permission {request_id} replied: {reply}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to reply to permission {request_id}: {e}")
            return False

    # ── Questions ────────────────────────────────────────────────────────

    async def list_questions(self) -> List[Dict[str, Any]]:
        """List pending questions from OpenCode agents."""
        try:
            response = await self.client.get(f"{self.server_url}/question")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list questions: {e}")
            raise OpenCodeServerError(f"Failed to list questions: {e}")

    async def reply_question(self, question_id: str,
                             answers: List[List[str]]) -> bool:
        """Reply to a question from an OpenCode agent.

        Args:
            question_id: The question ID
            answers: Nested list — one list of selected option labels per question.
        """
        try:
            response = await self.client.post(
                f"{self.server_url}/question/{question_id}/reply",
                json={"answers": answers}
            )
            response.raise_for_status()
            logger.debug(f"Question {question_id} answered")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to reply to question {question_id}: {e}")
            return False

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("OpenCode client closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
