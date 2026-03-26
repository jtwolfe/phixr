"""HTTP client for OpenCode server API.

Communicates with OpenCode server running in headless mode via HTTP API.
Handles session creation, message sending, and result extraction.
"""

import logging
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class OpenCodeServerError(Exception):
    """Exception raised when OpenCode server API call fails."""
    pass


class OpenCodeServerClient:
    """Client for OpenCode HTTP server API.
    
    Provides high-level interface to OpenCode server for:
    - Session management (create, list, get, delete)
    - Message sending (with plan/build mode support)
    - Results extraction (diffs, files, output)
    - Provider and model management
    """
    
    def __init__(self, server_url: str = "http://localhost:4096", timeout: int = 300):
        """Initialize OpenCode server client.
        
        Args:
            server_url: URL to OpenCode server (e.g., http://localhost:4096)
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        logger.info(f"OpenCode client initialized: {self.server_url}")
    
    async def health_check(self) -> bool:
        """Check if OpenCode server is healthy.
        
        Returns:
            True if server is reachable and healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.server_url}/global/health")
            response.raise_for_status()
            data = response.json()
            return data.get("healthy", False)
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False
    
    async def create_session(self, project_path: str, 
                           title: Optional[str] = None,
                           parent_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new OpenCode session.
        
        Args:
            project_path: Path to the project directory
            title: Optional session title
            parent_id: Optional parent session ID (for child sessions)
            
        Returns:
            Session object with id, title, created_at, etc.
            
        Raises:
            OpenCodeServerError: If session creation fails
        """
        payload = {"title": title or "Phixr Session"}
        if parent_id:
            payload["parentID"] = parent_id
        
        try:
            response = await self.client.post(
                f"{self.server_url}/session",
                json=payload
            )
            response.raise_for_status()
            session = response.json()
            logger.info(f"Created session: {session.get('id')}")
            return session
        except httpx.HTTPError as e:
            logger.error(f"Failed to create session: {e}")
            raise OpenCodeServerError(f"Session creation failed: {e}")
    
    async def get_session(self, session_id: str) -> Dict[str, Any]:
        """Get session details.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session object
            
        Raises:
            OpenCodeServerError: If session not found or request fails
        """
        try:
            response = await self.client.get(f"{self.server_url}/session/{session_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            raise OpenCodeServerError(f"Failed to get session: {e}")
    
    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions.
        
        Returns:
            List of session objects
            
        Raises:
            OpenCodeServerError: If request fails
        """
        try:
            response = await self.client.get(f"{self.server_url}/session")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to list sessions: {e}")
            raise OpenCodeServerError(f"Failed to list sessions: {e}")
    
    async def send_message(self, session_id: str, message: str,
                          model: Optional[str] = None,
                          agent: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to OpenCode and get response.
        
        Args:
            session_id: Session ID
            message: Message/prompt to send
            model: Optional model override (e.g., "opencode/big-pickle")
            agent: Optional agent to use
            
        Returns:
            Response with message info and parts (output, edits, etc.)
            
        Raises:
            OpenCodeServerError: If request fails
        """
        payload = {
            "parts": [{"type": "text", "content": message}]
        }
        if model:
            payload["model"] = model
        if agent:
            payload["agent"] = agent
        
        try:
            logger.debug(f"Sending message to session {session_id}: {message[:100]}...")
            response = await self.client.post(
                f"{self.server_url}/session/{session_id}/message",
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send message: {e}")
            raise OpenCodeServerError(f"Message send failed: {e}")
    
    async def send_message_async(self, session_id: str, message: str,
                                 model: Optional[str] = None) -> None:
        """Send a message asynchronously (no wait for response).
        
        Args:
            session_id: Session ID
            message: Message/prompt to send
            model: Optional model override
            
        Raises:
            OpenCodeServerError: If request fails
        """
        payload = {
            "parts": [{"type": "text", "content": message}]
        }
        if model:
            payload["model"] = model
        
        try:
            response = await self.client.post(
                f"{self.server_url}/session/{session_id}/prompt_async",
                json=payload
            )
            response.raise_for_status()
            logger.debug(f"Async message sent to session {session_id}")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send async message: {e}")
            raise OpenCodeServerError(f"Async message send failed: {e}")
    
    async def get_diff(self, session_id: str, 
                      message_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get file diffs from session.
        
        Args:
            session_id: Session ID
            message_id: Optional specific message ID to get diff from
            
        Returns:
            List of file diff objects with path, additions, deletions, etc.
            
        Raises:
            OpenCodeServerError: If request fails
        """
        try:
            params = {}
            if message_id:
                params["messageID"] = message_id
            
            response = await self.client.get(
                f"{self.server_url}/session/{session_id}/diff",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get diff for session {session_id}: {e}")
            raise OpenCodeServerError(f"Failed to get diff: {e}")
    
    async def get_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all messages from a session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message objects with info and parts
            
        Raises:
            OpenCodeServerError: If request fails
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
    
    async def abort_session(self, session_id: str) -> bool:
        """Abort a running session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if aborted successfully
            
        Raises:
            OpenCodeServerError: If request fails
        """
        try:
            response = await self.client.post(f"{self.server_url}/session/{session_id}/abort")
            response.raise_for_status()
            logger.info(f"Session aborted: {session_id}")
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to abort session {session_id}: {e}")
            raise OpenCodeServerError(f"Failed to abort session: {e}")
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if deleted successfully
            
        Raises:
            OpenCodeServerError: If request fails
        """
        try:
            response = await self.client.delete(f"{self.server_url}/session/{session_id}")
            response.raise_for_status()
            logger.info(f"Session deleted: {session_id}")
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise OpenCodeServerError(f"Failed to delete session: {e}")
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("OpenCode client closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
