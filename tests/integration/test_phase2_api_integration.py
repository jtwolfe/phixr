"""Integration tests for Phase 2 API-based OpenCode integration.

Tests the refactored flow:
1. OpenCodeBridge uses HTTP API instead of Docker containers
2. ContextInjector generates context messages (no volumes)
3. Sessions are created via OpenCode API
4. Results are extracted via OpenCode API
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime

from phixr.bridge.opencode_bridge import OpenCodeBridge
from phixr.bridge.opencode_client import OpenCodeServerClient, OpenCodeServerError
from phixr.bridge.context_injector import ContextInjector
from phixr.config.sandbox_config import SandboxConfig
from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import (
    ExecutionMode, ExecutionConfig, Session, SessionStatus, ExecutionResult
)


class TestOpenCodeBridgeAPI:
    """Test OpenCodeBridge API-based session management."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenCodeServerClient."""
        client = Mock(spec=OpenCodeServerClient)
        client.health_check = AsyncMock(return_value=True)
        client.create_session = Mock(return_value={"id": "sess-123", "status": "created"})
        client.send_message = Mock(return_value={"id": "msg-1"})
        client.get_session = Mock(return_value={"id": "sess-123", "status": "running", "message_count": 2})
        client.get_messages = Mock(return_value=[
            {"role": "user", "content": "Plan the implementation"},
            {"role": "assistant", "content": "Here's the plan..."}
        ])
        client.get_diff = Mock(return_value="diff --git a/file.py b/file.py\n...")
        client.delete_session = Mock(return_value=True)
        return client
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SandboxConfig(
            opencode_server_url="http://localhost:4096",
            timeout_minutes=5,
            model="claude-3-haiku"
        )
    
    @pytest.fixture
    def bridge(self, config):
        """Create OpenCodeBridge with mocked client."""
        bridge = OpenCodeBridge(config)
        return bridge
    
    @pytest.fixture
    def sample_context(self):
        """Create sample issue context."""
        return IssueContext(
            issue_id=123,
            project_id=456,
            title="Fix authentication bug",
            description="The login endpoint is not working properly",
            url="https://gitlab.example.com/project/-/issues/123",
            author="alice",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            repo_url="https://github.com/example/project.git",
            repo_name="project",
            language="python",
            structure={
                "src/": "Application source code",
                "tests/": "Test suite",
            },
            labels=["bug", "auth"],
            assignees=["bob"],
            comments=[],
        )
    
    def test_bridge_initialization(self, bridge, config):
        """Test OpenCodeBridge initializes with HTTP client."""
        assert bridge.config == config
        assert bridge.client is not None
        assert isinstance(bridge.sessions, dict)
    
    def test_start_opencode_session(self, bridge, sample_context, mock_client):
        """Test starting an OpenCode session with context injection."""
        # Inject mock client
        bridge.client = mock_client
        
        session = bridge.start_opencode_session(
            context=sample_context,
            mode=ExecutionMode.PLAN,
            timeout_minutes=10
        )
        
        # Verify session was created
        assert session.id.startswith("sess-")
        assert session.status == SessionStatus.RUNNING
        assert session.issue_id == 123
        assert session.mode == ExecutionMode.PLAN
        assert session.repo_url == sample_context.repo_url
        
        # Verify OpenCode API was called
        mock_client.create_session.assert_called_once()
        call_kwargs = mock_client.create_session.call_args[1]
        assert "Fix authentication bug" in call_kwargs.get("title", "")
        
        # Verify context message was injected
        mock_client.send_message.assert_called_once()
        call_kwargs = mock_client.send_message.call_args[1]
        assert "Fix authentication bug" in call_kwargs.get("message", "")
        assert "github.com" in call_kwargs.get("message", "")
    
    def test_session_validation(self, bridge, sample_context, mock_client):
        """Test session validation before creation."""
        bridge.client = mock_client
        
        # Invalid issue ID
        bad_context = IssueContext(
            issue_id=-1,
            project_id=456,
            title="Test",
            description="Test",
            url="https://example.com/issues/1",
            author="user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            repo_url="https://github.com/example/repo.git",
            repo_name="repo",
            language="python",
            structure={},
            labels=[],
            assignees=[],
            comments=[]
        )
        
        with pytest.raises(ValueError, match="Invalid issue ID"):
            bridge.start_opencode_session(bad_context)
        
        # No repo URL
        bad_context2 = IssueContext(
            issue_id=123,
            project_id=456,
            title="Test",
            description="Test",
            url="https://example.com/issues/1",
            author="user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            repo_url="",
            repo_name="repo",
            language="python",
            structure={},
            labels=[],
            assignees=[],
            comments=[]
        )
        
        with pytest.raises(ValueError, match="Repository URL required"):
            bridge.start_opencode_session(bad_context2)
    
    def test_monitor_session(self, bridge, sample_context, mock_client):
        """Test session monitoring."""
        bridge.client = mock_client
        
        # Start a session first
        session = bridge.start_opencode_session(
            context=sample_context,
            mode=ExecutionMode.PLAN
        )
        
        # Monitor the session
        status = bridge.monitor_session(session.id)
        
        assert status["status"] == SessionStatus.RUNNING.value
        assert "opencode_session_id" in status
        assert status["message_count"] == 2
    
    def test_extract_results(self, bridge, sample_context, mock_client):
        """Test extracting results from completed session."""
        bridge.client = mock_client
        
        # Start a session
        session = bridge.start_opencode_session(
            context=sample_context,
            mode=ExecutionMode.PLAN
        )
        
        # Mark as completed
        session.status = SessionStatus.COMPLETED
        session.ended_at = datetime.utcnow()
        
        # Extract results
        result = bridge.extract_results(session.id)
        
        assert result is not None
        assert result.session_id == session.id
        assert result.success == True
        assert "file.py" in result.files_changed
        assert "unified" in result.diffs
    
    def test_stop_session(self, bridge, sample_context, mock_client):
        """Test stopping a session."""
        bridge.client = mock_client
        
        session = bridge.start_opencode_session(
            context=sample_context,
            mode=ExecutionMode.PLAN
        )
        
        success = bridge.stop_opencode_session(session.id)
        
        assert success == True
        mock_client.delete_session.assert_called_once()
        assert session.status == SessionStatus.STOPPED
    
    def test_get_session_logs(self, bridge, sample_context, mock_client):
        """Test retrieving session message history."""
        bridge.client = mock_client
        
        session = bridge.start_opencode_session(
            context=sample_context,
            mode=ExecutionMode.PLAN
        )
        
        logs = bridge.get_session_logs(session.id)
        
        assert "Plan the implementation" in logs
        assert "Here's the plan" in logs
    
    def test_context_message_building(self, bridge, sample_context):
        """Test context message building includes all required info."""
        message = bridge._build_context_message(
            sample_context,
            ExecutionConfig(
                session_id="test",
                issue_id=123,
                repo_url=sample_context.repo_url,
                branch="ai-work/123",
                mode=ExecutionMode.PLAN
            )
        )
        
        # Verify message includes all context
        assert sample_context.title in message
        assert sample_context.description in message
        assert sample_context.repo_url in message
        assert "ai-work/123" in message
        assert "read-only" in message  # PLAN mode indicator
    
    def test_list_sessions(self, bridge, sample_context, mock_client):
        """Test listing sessions."""
        bridge.client = mock_client
        
        # Create a few sessions
        for i in range(3):
            bridge.start_opencode_session(
                context=sample_context,
                mode=ExecutionMode.PLAN
            )
        
        all_sessions = bridge.list_sessions()
        assert len(all_sessions) == 3
        
        # Filter by status
        running = bridge.list_sessions(status_filter=SessionStatus.RUNNING)
        assert len(running) == 3


class TestContextInjectorAPI:
    """Test ContextInjector for API-based context."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SandboxConfig(timeout_minutes=5)
    
    @pytest.fixture
    def injector(self, config):
        """Create ContextInjector."""
        return ContextInjector(config)
    
    @pytest.fixture
    def sample_context(self):
        """Create sample issue context."""
        return IssueContext(
            issue_id=789,
            project_id=101,
            title="Add user profile endpoint",
            description="Implement GET /users/{id} endpoint",
            url="https://gitlab.example.com/project/-/issues/789",
            author="charlie",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            repo_url="https://github.com/example/api.git",
            repo_name="api",
            language="go",
            structure={
                "cmd/": "Command line tools",
                "internal/": "Internal packages",
                "api/": "API definitions",
            },
            labels=["feature", "api"],
            assignees=[],
            comments=[],
        )
    
    def test_build_context_message(self, injector, sample_context):
        """Test building context message for API injection."""
        config = ExecutionConfig(
            session_id="test",
            issue_id=sample_context.issue_id,
            repo_url=sample_context.repo_url,
            branch="ai-work/789",
            mode=ExecutionMode.BUILD
        )
        
        message = injector.build_context_message(sample_context, config)
        
        assert sample_context.title in message
        assert sample_context.description in message
        assert sample_context.repo_url in message
        assert "development" in message  # BUILD mode
        assert str(sample_context.issue_id) in message
    
    def test_build_system_prompt(self, injector):
        """Test building system prompts for different modes."""
        # PLAN mode
        config = ExecutionConfig(
            session_id="test",
            issue_id=1,
            repo_url="https://example.com/repo",
            branch="main",
            mode=ExecutionMode.PLAN
        )
        prompt = injector.build_system_prompt(config)
        assert "READ-ONLY" in prompt
        assert "analyze" in prompt.lower()
        
        # BUILD mode
        config.mode = ExecutionMode.BUILD
        prompt = injector.build_system_prompt(config)
        assert "DEVELOPMENT" in prompt
        assert "changes" in prompt.lower()
        
        # REVIEW mode
        config.mode = ExecutionMode.REVIEW
        prompt = injector.build_system_prompt(config)
        assert "REVIEW" in prompt
        assert "feedback" in prompt.lower()
    
    def test_environment_variables(self, injector, sample_context):
        """Test creating environment variables for context."""
        config = ExecutionConfig(
            session_id="test",
            issue_id=sample_context.issue_id,
            repo_url=sample_context.repo_url,
            branch="ai-work/789",
            mode=ExecutionMode.BUILD
        )
        
        env_vars = injector.create_environment_variables(
            sample_context,
            config,
            "git-token-123"
        )
        
        assert env_vars["PHIXR_SESSION_ID"] == "test"
        assert env_vars["PHIXR_ISSUE_ID"] == "789"
        assert env_vars["PHIXR_REPO_URL"] == sample_context.repo_url
        assert env_vars["PHIXR_BRANCH"] == "ai-work/789"
        assert env_vars["PHIXR_GIT_TOKEN"] == "git-token-123"
        assert env_vars["OPENCODE_MODEL"] == config.model
    
    def test_cleanup_all_noop(self, injector):
        """Test cleanup_all is now a no-op for API-based sessions."""
        # Should not raise any errors
        injector.cleanup_all()


class TestOpenCodeClientErrorHandling:
    """Test OpenCodeServerClient error handling."""
    
    def test_server_error_handling(self):
        """Test handling of server communication errors."""
        client = OpenCodeServerClient("http://invalid-server:9999")
        
        # Verify client initializes with invalid URL (error on actual call)
        assert client.server_url == "http://invalid-server:9999"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
