"""Unit tests for WebSocket terminal handler."""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

from phixr.terminal.websocket_handler import (
    TerminalMessage, WebTerminalHandler, TerminalSessionManager
)
from phixr.models.execution_models import Session, SessionStatus


class TestTerminalMessage:
    """Test TerminalMessage model."""
    
    def test_message_creation(self):
        """Test creating a terminal message."""
        msg = TerminalMessage(
            type="output",
            data="Hello, terminal!",
        )
        
        assert msg.type == "output"
        assert msg.data == "Hello, terminal!"
    
    def test_message_serialization(self):
        """Test message JSON serialization."""
        msg = TerminalMessage(
            type="output",
            data="Test output",
        )
        
        json_str = msg.model_dump_json()
        assert isinstance(json_str, str)
        
        # Deserialize
        data = json.loads(json_str)
        assert data["type"] == "output"
        assert data["data"] == "Test output"
    
    def test_message_types(self):
        """Test all message types."""
        message_types = ["output", "input", "status", "error", "ping", "pong"]
        
        for msg_type in message_types:
            msg = TerminalMessage(type=msg_type, data="test")
            assert msg.type == msg_type
    
    def test_message_timestamp(self):
        """Test message timestamp handling."""
        msg = TerminalMessage(
            type="status",
            data="test",
            timestamp="2026-03-26T10:00:00Z",
        )
        
        assert msg.timestamp == "2026-03-26T10:00:00Z"


class TestWebTerminalHandler:
    """Test WebSocket terminal handler."""
    
    @pytest.fixture
    def mock_container_manager(self):
        """Create mock container manager."""
        manager = Mock()
        manager.get_session = Mock(return_value=Session(
            id="sess-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
            status=SessionStatus.RUNNING,
        ))
        manager.get_session_logs = Mock(return_value="Container output\n")
        return manager
    
    @pytest.fixture
    def handler(self, mock_container_manager):
        """Create terminal handler."""
        return WebTerminalHandler(mock_container_manager)
    
    def test_handler_creation(self, handler):
        """Test handler initialization."""
        assert handler.container_manager is not None
        assert len(handler.active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_connect_valid_session(self, handler, mock_container_manager):
        """Test connecting with valid session."""
        websocket = AsyncMock()
        
        result = await handler.connect(websocket, "sess-test")
        
        assert result is True
        websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_invalid_session(self, handler, mock_container_manager):
        """Test connecting with invalid session."""
        mock_container_manager.get_session.return_value = None
        websocket = AsyncMock()
        
        result = await handler.connect(websocket, "sess-invalid")
        
        assert result is False
        websocket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, handler):
        """Test disconnecting."""
        handler.active_connections["sess-test"] = AsyncMock()
        
        await handler.disconnect("sess-test")
        
        assert "sess-test" not in handler.active_connections
    
    @pytest.mark.asyncio
    async def test_stream_output(self, handler, mock_container_manager):
        """Test streaming output."""
        websocket = AsyncMock()
        
        await handler.stream_output(websocket, "sess-test")
        
        # Should send output message
        websocket.send_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_forward_input(self, handler):
        """Test forwarding input."""
        websocket = AsyncMock()
        
        await handler.forward_input(websocket, "sess-test", "test input")
        
        # Should send acknowledgment
        websocket.send_text.assert_called()
    
    @pytest.mark.asyncio
    async def test_send_message(self, handler):
        """Test sending message."""
        websocket = AsyncMock()
        msg = TerminalMessage(type="status", data="Test message")
        
        await handler._send_message(websocket, msg)
        
        websocket.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_error(self, handler):
        """Test sending error message."""
        websocket = AsyncMock()
        
        await handler._send_error(websocket, "Test error")
        
        websocket.send_text.assert_called()
        
        # Get the called argument
        call_args = websocket.send_text.call_args
        message_json = call_args[0][0] if call_args else None
        assert message_json is not None
    
    def test_get_active_connections(self, handler):
        """Test getting active connection count."""
        handler.active_connections = {
            "sess-1": AsyncMock(),
            "sess-2": AsyncMock(),
        }
        
        count = handler.get_active_connections()
        assert count == 2


class TestTerminalSessionManager:
    """Test terminal session manager."""
    
    @pytest.fixture
    def mock_container_manager(self):
        """Create mock container manager."""
        return Mock()
    
    @pytest.fixture
    def manager(self, mock_container_manager):
        """Create session manager."""
        return TerminalSessionManager(mock_container_manager)
    
    def test_manager_creation(self, manager):
        """Test manager initialization."""
        assert manager.container_manager is not None
        assert len(manager.handlers) == 0
    
    def test_get_handler_new(self, manager):
        """Test getting handler for new session."""
        handler = manager.get_handler("sess-test")
        
        assert handler is not None
        assert "sess-test" in manager.handlers
    
    def test_get_handler_existing(self, manager):
        """Test getting handler for existing session."""
        handler1 = manager.get_handler("sess-test")
        handler2 = manager.get_handler("sess-test")
        
        assert handler1 is handler2  # Same instance
    
    def test_get_stats_empty(self, manager):
        """Test getting stats with no handlers."""
        stats = manager.get_stats()
        
        assert stats["active_handlers"] == 0
        assert stats["total_active_connections"] == 0
    
    def test_get_stats_with_handlers(self, manager):
        """Test getting stats with active handlers."""
        handler1 = manager.get_handler("sess-1")
        handler2 = manager.get_handler("sess-2")
        
        # Mock active connections
        handler1.get_active_connections = Mock(return_value=2)
        handler2.get_active_connections = Mock(return_value=1)
        
        stats = manager.get_stats()
        
        assert stats["active_handlers"] == 2
        assert stats["total_active_connections"] == 3


class TestTerminalMessageProtocol:
    """Test terminal message protocol."""
    
    def test_output_message(self):
        """Test output message."""
        msg = TerminalMessage(type="output", data="command output here")
        assert msg.type == "output"
    
    def test_input_message(self):
        """Test input message."""
        msg = TerminalMessage(type="input", data="user input")
        assert msg.type == "input"
    
    def test_status_message(self):
        """Test status message."""
        msg = TerminalMessage(type="status", data="[Session running]")
        assert msg.type == "status"
    
    def test_error_message(self):
        """Test error message."""
        msg = TerminalMessage(type="error", data="[Error: Connection failed]")
        assert msg.type == "error"
    
    def test_ping_pong(self):
        """Test ping/pong keep-alive."""
        ping = TerminalMessage(type="ping", data="")
        pong = TerminalMessage(type="pong", data="")
        
        assert ping.type == "ping"
        assert pong.type == "pong"
    
    def test_message_with_timestamp(self):
        """Test message with timestamp."""
        now = datetime.utcnow().isoformat()
        msg = TerminalMessage(type="output", data="test", timestamp=now)
        
        assert msg.timestamp == now
    
    def test_ansi_escape_sequences(self):
        """Test handling ANSI escape sequences."""
        # Terminal colors
        colored_text = "\x1b[1;32mSuccess\x1b[0m"
        msg = TerminalMessage(type="output", data=colored_text)
        
        assert msg.data == colored_text
    
    def test_multiline_output(self):
        """Test multiline output."""
        multiline = "Line 1\nLine 2\nLine 3\n"
        msg = TerminalMessage(type="output", data=multiline)
        
        assert msg.data.count('\n') == 3


class TestTerminalEdgeCases:
    """Test edge cases for terminal handling."""
    
    def test_empty_message_data(self):
        """Test message with empty data."""
        msg = TerminalMessage(type="output", data="")
        assert msg.data == ""
    
    def test_large_message_data(self):
        """Test message with large data."""
        large_data = "x" * 1000000  # 1MB
        msg = TerminalMessage(type="output", data=large_data)
        
        assert len(msg.data) == 1000000
    
    def test_special_characters_in_data(self):
        """Test message with special characters."""
        special_data = "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?"
        msg = TerminalMessage(type="output", data=special_data)
        
        assert msg.data == special_data
    
    def test_unicode_in_message(self):
        """Test message with unicode characters."""
        unicode_data = "Unicode: 你好世界 مرحبا بالعالم"
        msg = TerminalMessage(type="output", data=unicode_data)
        
        assert msg.data == unicode_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
