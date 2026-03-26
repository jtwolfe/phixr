"""WebSocket handler for real-time terminal access to OpenCode sessions.

Provides terminal streaming capabilities for web-based access to running
OpenCode sessions. Supports xterm.js frontend for rendering.
"""

import logging
import asyncio
from typing import Optional, Callable, Dict
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TerminalMessage(BaseModel):
    """Message format for terminal communication."""
    type: str  # 'output', 'input', 'status', 'error'
    data: str
    timestamp: Optional[str] = None


class WebTerminalHandler:
    """Handles WebSocket connections for terminal streaming to OpenCode containers.
    
    Manages bidirectional communication between browser client (xterm.js) and
    running OpenCode container. Provides real-time terminal output streaming
    and input forwarding.
    """
    
    def __init__(self, container_manager):
        """Initialize terminal handler.
        
        Args:
            container_manager: Reference to ContainerManager for accessing sessions
        """
        self.container_manager = container_manager
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_streams: Dict[str, asyncio.StreamReader] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str) -> bool:
        """Accept and register WebSocket connection for terminal.
        
        Args:
            websocket: WebSocket connection from client
            session_id: OpenCode session ID
            
        Returns:
            True if connection successful, False otherwise
        """
        # Validate session exists
        session = self.container_manager.get_session(session_id)
        if not session:
            logger.warning(f"Terminal connection rejected: session not found {session_id}")
            await websocket.close(code=1008, reason="Session not found")
            return False
        
        try:
            await websocket.accept()
            self.active_connections[session_id] = websocket
            logger.info(f"Terminal connected: {session_id}")
            
            # Send welcome message
            await self._send_message(websocket, TerminalMessage(
                type="status",
                data=f"Connected to session {session_id}. "
                     f"Container: {session.container_id}\n"
            ))
            
            return True
        except Exception as e:
            logger.error(f"Error accepting terminal connection: {e}")
            return False
    
    async def disconnect(self, session_id: str) -> None:
        """Disconnect terminal session.
        
        Args:
            session_id: Session ID to disconnect
        """
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"Terminal disconnected: {session_id}")
        
        if session_id in self.session_streams:
            del self.session_streams[session_id]
    
    async def stream_output(self, websocket: WebSocket, session_id: str) -> None:
        """Stream container output to WebSocket client.
        
        Continuously reads container logs and sends to client in real-time.
        Supports xterm.js compatible format.
        
        Args:
            websocket: WebSocket connection
            session_id: Session ID to stream from
        """
        session = self.container_manager.get_session(session_id)
        if not session:
            await self._send_error(websocket, f"Session not found: {session_id}")
            return
        
        logger.info(f"Starting output stream for session: {session_id}")
        
        try:
            # Get initial logs
            logs = self.container_manager.get_session_logs(session_id)
            if logs:
                await self._send_message(websocket, TerminalMessage(
                    type="output",
                    data=logs
                ))
            
            # If session is still running, implement streaming updates
            # For now, send completion message
            if session.status.value in ("running", "initializing"):
                await self._send_message(websocket, TerminalMessage(
                    type="status",
                    data=f"[Session status: {session.status.value}]\r\n"
                ))
            else:
                await self._send_message(websocket, TerminalMessage(
                    type="status",
                    data=f"[Session completed with status: {session.status.value}]\r\n"
                ))
            
        except Exception as e:
            logger.error(f"Error streaming output: {e}")
            await self._send_error(websocket, str(e))
    
    async def forward_input(self, websocket: WebSocket, session_id: str, 
                           input_data: str) -> None:
        """Forward terminal input to container.
        
        In future phases, this will support interactive terminal input.
        For now, logs input for debugging.
        
        Args:
            websocket: WebSocket connection
            session_id: Session ID
            input_data: Input to forward (keyboard input, commands, etc.)
        """
        session = self.container_manager.get_session(session_id)
        if not session:
            await self._send_error(websocket, f"Session not found: {session_id}")
            return
        
        logger.debug(f"Terminal input for {session_id}: {repr(input_data[:50])}")
        
        # In Phase 3, implement stdin forwarding to container
        # For now, just acknowledge
        await self._send_message(websocket, TerminalMessage(
            type="status",
            data=f"[Input received, but session is not interactive yet]\r\n"
        ))
    
    async def handle_terminal_connection(self, websocket: WebSocket, 
                                        session_id: str) -> None:
        """Main handler for terminal WebSocket connections.
        
        Manages the full lifecycle of a terminal connection:
        1. Connect and validate session
        2. Stream output to client
        3. Receive and forward input
        4. Handle disconnection
        
        Args:
            websocket: WebSocket connection from client
            session_id: OpenCode session ID to connect to
        """
        if not await self.connect(websocket, session_id):
            return
        
        try:
            # Start streaming output
            stream_task = asyncio.create_task(self.stream_output(websocket, session_id))
            
            # Listen for incoming messages
            while True:
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                    
                    # Parse message
                    try:
                        message = TerminalMessage.model_validate_json(data)
                        
                        if message.type == "input":
                            await self.forward_input(websocket, session_id, message.data)
                        elif message.type == "ping":
                            # Heartbeat/keep-alive
                            await self._send_message(websocket, TerminalMessage(
                                type="pong",
                                data=""
                            ))
                        else:
                            logger.debug(f"Unknown message type: {message.type}")
                    
                    except Exception as e:
                        logger.warning(f"Error parsing message: {e}")
                        await self._send_error(websocket, f"Invalid message format: {e}")
                
                except asyncio.TimeoutError:
                    # Timeout waiting for message, send keep-alive
                    try:
                        await self._send_message(websocket, TerminalMessage(
                            type="ping",
                            data=""
                        ))
                    except Exception as e:
                        logger.warning(f"Error sending keep-alive: {e}")
                        break
                
        except WebSocketDisconnect:
            logger.info(f"Terminal WebSocket disconnected: {session_id}")
        except Exception as e:
            logger.error(f"Terminal handler error: {e}")
            try:
                await self._send_error(websocket, str(e))
            except:
                pass
        finally:
            await self.disconnect(session_id)
            logger.info(f"Terminal handler closed: {session_id}")
    
    async def _send_message(self, websocket: WebSocket, 
                           message: TerminalMessage) -> None:
        """Send terminal message to client.
        
        Args:
            websocket: WebSocket connection
            message: Message to send
            
        Raises:
            Exception: If send fails
        """
        try:
            if not message.timestamp:
                message.timestamp = datetime.utcnow().isoformat()
            
            await websocket.send_text(message.model_dump_json())
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def _send_error(self, websocket: WebSocket, error_msg: str) -> None:
        """Send error message to client.
        
        Args:
            websocket: WebSocket connection
            error_msg: Error message
        """
        try:
            await self._send_message(websocket, TerminalMessage(
                type="error",
                data=f"[Error: {error_msg}]\r\n"
            ))
        except Exception as e:
            logger.error(f"Error sending error message: {e}")
    
    def get_active_connections(self) -> int:
        """Get count of active terminal connections.
        
        Returns:
            Number of active WebSocket connections
        """
        return len(self.active_connections)


class TerminalSessionManager:
    """High-level manager for terminal sessions across multiple connections.
    
    Tracks and manages multiple terminal connections, provides statistics,
    and handles cleanup.
    """
    
    def __init__(self, container_manager):
        """Initialize terminal session manager.
        
        Args:
            container_manager: Reference to ContainerManager
        """
        self.container_manager = container_manager
        self.handlers: Dict[str, WebTerminalHandler] = {}
    
    def get_handler(self, session_id: str) -> WebTerminalHandler:
        """Get or create terminal handler for session.
        
        Args:
            session_id: OpenCode session ID
            
        Returns:
            WebTerminalHandler for the session
        """
        if session_id not in self.handlers:
            self.handlers[session_id] = WebTerminalHandler(self.container_manager)
        return self.handlers[session_id]
    
    def get_stats(self) -> Dict:
        """Get terminal connection statistics.
        
        Returns:
            Dictionary with connection stats
        """
        total_active = sum(h.get_active_connections() for h in self.handlers.values())
        return {
            "active_handlers": len(self.handlers),
            "total_active_connections": total_active,
            "handlers": {
                session_id: handler.get_active_connections()
                for session_id, handler in self.handlers.items()
            }
        }


if __name__ == "__main__":
    print("Terminal handler module for OpenCode WebSocket streaming")
    print("Use with FastAPI WebSocket endpoint:")
    print("  @app.websocket('/ws/terminal/{session_id}')")
    print("  async def websocket_endpoint(websocket: WebSocket, session_id: str):")
    print("    handler = WebTerminalHandler(container_manager)")
    print("    await handler.handle_terminal_connection(websocket, session_id)")
