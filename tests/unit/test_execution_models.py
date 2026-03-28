"""Unit tests for execution models."""

import pytest
from datetime import datetime, timedelta
from phixr.models.execution_models import (
    Session, ExecutionResult, SessionStatus, ExecutionMode,
    ExecutionConfig, ContainerStats, SandboxError
)


class TestSessionModel:
    """Test Session model."""
    
    def test_session_creation_defaults(self):
        """Test creating a session with defaults."""
        session = Session(
            id="sess-test123",
            issue_id=456,
            repo_url="https://github.com/test/repo.git",
            branch="ai-work/issue-456",
        )
        
        assert session.id == "sess-test123"
        assert session.issue_id == 456
        assert session.status == SessionStatus.CREATED
        assert session.mode is None
        assert session.created_at is not None
        assert session.started_at is None
    
    def test_session_status_values(self):
        """Test all session status values."""
        statuses = [
            SessionStatus.CREATED,
            SessionStatus.INITIALIZING,
            SessionStatus.RUNNING,
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.TIMEOUT,
            SessionStatus.STOPPED,
            SessionStatus.ERROR,
        ]
        
        for status in statuses:
            session = Session(
                id="test",
                issue_id=1,
                repo_url="https://test.git",
                branch="main",
                status=status,
            )
            assert session.status == status
    
    def test_session_execution_modes(self):
        """Test execution modes."""
        for mode in [ExecutionMode.BUILD, ExecutionMode.PLAN, ExecutionMode.REVIEW]:
            session = Session(
                id="test",
                issue_id=1,
                repo_url="https://test.git",
                branch="main",
                mode=mode,
            )
            assert session.mode == mode
    
    def test_session_serialization(self):
        """Test session JSON serialization."""
        session = Session(
            id="sess-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
            status=SessionStatus.RUNNING,
            model="claude-3-opus",
        )
        
        # Convert to dict
        session_dict = session.model_dump()
        assert session_dict["id"] == "sess-test"
        assert session_dict["status"] == "running"
        
        # Convert to JSON and back
        json_str = session.model_dump_json()
        assert isinstance(json_str, str)
        
        # Recreate from dict
        new_session = Session(**session_dict)
        assert new_session.id == session.id
    
    def test_session_error_tracking(self):
        """Test error tracking in session."""
        session = Session(
            id="test",
            issue_id=1,
            repo_url="https://test.git",
            branch="main",
        )
        
        assert session.errors == []
        
        session.errors.append("Test error 1")
        session.errors.append("Test error 2")
        
        assert len(session.errors) == 2
        assert "Test error 1" in session.errors


class TestExecutionResultModel:
    """Test ExecutionResult model."""
    
    def test_result_creation(self):
        """Test creating an execution result."""
        result = ExecutionResult(
            session_id="sess-test",
            status=SessionStatus.COMPLETED,
            exit_code=0,
            success=True,
        )
        
        assert result.session_id == "sess-test"
        assert result.status == SessionStatus.COMPLETED
        assert result.exit_code == 0
        assert result.success is True
    
    def test_result_with_changes(self):
        """Test result with file changes."""
        result = ExecutionResult(
            session_id="sess-test",
            status=SessionStatus.COMPLETED,
            exit_code=0,
            success=True,
            files_changed=["src/main.py", "tests/test_main.py"],
            diffs={
                "src/main.py": "diff content here",
                "tests/test_main.py": "test diff here",
            },
        )
        
        assert len(result.files_changed) == 2
        assert len(result.diffs) == 2
        assert "src/main.py" in result.files_changed
    
    def test_result_failed_status(self):
        """Test failed execution result."""
        result = ExecutionResult(
            session_id="sess-test",
            status=SessionStatus.FAILED,
            exit_code=1,
            success=False,
            errors=["Container failed to execute"],
        )
        
        assert result.success is False
        assert result.exit_code == 1
        assert len(result.errors) == 1
    
    def test_result_timeout_status(self):
        """Test timeout execution result."""
        result = ExecutionResult(
            session_id="sess-test",
            status=SessionStatus.TIMEOUT,
            exit_code=124,
            success=False,
        )
        
        assert result.status == SessionStatus.TIMEOUT
        assert result.exit_code == 124
    
    def test_result_serialization(self):
        """Test result JSON serialization."""
        result = ExecutionResult(
            session_id="sess-test",
            status=SessionStatus.COMPLETED,
            exit_code=0,
            success=True,
            files_changed=["file.py"],
            diffs={"file.py": "diff"},
            duration_seconds=60,
        )
        
        json_str = result.model_dump_json()
        assert isinstance(json_str, str)
        
        result_dict = result.model_dump()
        new_result = ExecutionResult(**result_dict)
        assert new_result.session_id == result.session_id
        assert new_result.duration_seconds == 60


class TestExecutionConfigModel:
    """Test ExecutionConfig model."""
    
    def test_config_creation(self):
        """Test creating execution configuration."""
        config = ExecutionConfig(
            session_id="sess-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="ai-work/123",
        )
        
        assert config.session_id == "sess-test"
        assert config.issue_id == 123
        assert config.mode == ExecutionMode.BUILD
        assert config.timeout_minutes == 30
    
    def test_config_with_custom_params(self):
        """Test config with custom parameters."""
        config = ExecutionConfig(
            session_id="sess-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
            mode=ExecutionMode.PLAN,
            timeout_minutes=60,
            model="gpt-4",
            temperature=0.5,
            allow_destructive=True,
            initial_prompt="Custom prompt here",
        )
        
        assert config.mode == ExecutionMode.PLAN
        assert config.timeout_minutes == 60
        assert config.model == "gpt-4"
        assert config.temperature == 0.5
        assert config.allow_destructive is True
        assert config.initial_prompt == "Custom prompt here"
    
    def test_config_serialization(self):
        """Test config serialization."""
        config = ExecutionConfig(
            session_id="sess-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
        )
        
        json_str = config.model_dump_json()
        config_dict = config.model_dump()
        new_config = ExecutionConfig(**config_dict)
        assert new_config.session_id == config.session_id


class TestContainerStatsModel:
    """Test ContainerStats model."""
    
    def test_stats_creation(self):
        """Test creating container stats."""
        stats = ContainerStats(
            container_id="abc123def",
            status="running",
            memory_usage_mb=512.5,
            memory_limit_mb=2048.0,
            cpu_percent=25.5,
            uptime_seconds=3600,
        )
        
        assert stats.container_id == "abc123def"
        assert stats.status == "running"
        assert stats.memory_usage_mb == 512.5
        assert stats.cpu_percent == 25.5
        assert stats.uptime_seconds == 3600
    
    def test_stats_high_usage(self):
        """Test stats with high resource usage."""
        stats = ContainerStats(
            container_id="test",
            status="running",
            memory_usage_mb=1800.0,
            memory_limit_mb=2048.0,
            cpu_percent=95.0,
            uptime_seconds=1800,
        )
        
        # Assert high usage
        assert stats.memory_usage_mb / stats.memory_limit_mb > 0.85
        assert stats.cpu_percent > 90


class TestSandboxErrorModel:
    """Test SandboxError model."""
    
    def test_error_creation(self):
        """Test creating a sandbox error."""
        error = SandboxError(
            code="CONTAINER_START_FAILED",
            message="Failed to start container",
        )
        
        assert error.code == "CONTAINER_START_FAILED"
        assert error.message == "Failed to start container"
        assert error.timestamp is not None
    
    def test_error_with_details(self):
        """Test error with additional details."""
        error = SandboxError(
            code="RESOURCE_LIMIT_EXCEEDED",
            message="Memory limit exceeded",
            details={
                "memory_used": 2048,
                "memory_limit": 2048,
                "container_id": "abc123",
            },
        )
        
        assert error.details is not None
        assert error.details["memory_used"] == 2048


class TestModelEnums:
    """Test model enumerations."""
    
    def test_session_status_enum(self):
        """Test SessionStatus enum."""
        status_values = [status.value for status in SessionStatus]
        assert "created" in status_values
        assert "running" in status_values
        assert "completed" in status_values
        assert "failed" in status_values
    
    def test_execution_mode_enum(self):
        """Test ExecutionMode enum."""
        modes = [mode.value for mode in ExecutionMode]
        assert "build" in modes
        assert "plan" in modes
        assert "review" in modes


class TestModelValidation:
    """Test model validation."""
    
    def test_session_issue_id_required(self):
        """Test that issue_id is required."""
        with pytest.raises(Exception):  # ValidationError
            Session(
                id="test",
                issue_id=None,  # type: ignore
                repo_url="https://test.git",
                branch="main",
            )
    
    def test_result_exit_code_required(self):
        """Test that exit_code is required."""
        with pytest.raises(Exception):  # ValidationError
            ExecutionResult(
                session_id="test",
                status=SessionStatus.COMPLETED,
                exit_code=None,  # type: ignore
                success=True,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
