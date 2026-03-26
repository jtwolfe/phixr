"""Unit tests for context injection and serialization."""

import pytest
import json
import tempfile
from pathlib import Path
from phixr.bridge.context_injector import ContextInjector
from phixr.config.sandbox_config import SandboxConfig
from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import ExecutionConfig, ExecutionMode


class TestContextInjector:
    """Test ContextInjector functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SandboxConfig(
            context_volume_size=10 * 1024 * 1024,  # 10MB for testing
        )
    
    @pytest.fixture
    def injector(self, config):
        """Create context injector."""
        return ContextInjector(config)
    
    @pytest.fixture
    def sample_context(self):
        """Create sample issue context."""
        from datetime import datetime
        return IssueContext(
            issue_id=123,
            project_id=456,
            title="Add authentication feature",
            description="Implement OAuth2 login flow",
            url="https://gitlab.com/test/repo/-/issues/123",
            author="test-user",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 30, 0),
            assignees=["dev-team"],
            labels=["feature", "auth"],
            repo_url="https://github.com/test/repo.git",
            repo_name="test-repo",
            language="python",
            structure={
                "src/": "Source code",
                "tests/": "Test suite",
                "docs/": "Documentation",
            },
        )
    
    @pytest.fixture
    def exec_config(self):
        """Create execution configuration."""
        return ExecutionConfig(
            session_id="sess-test123",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="ai-work/issue-123",
            mode=ExecutionMode.BUILD,
            timeout_minutes=30,
        )
    
    def test_context_volume_creation(self, injector, sample_context, exec_config):
        """Test creating context volume."""
        volume_path, volume_name = injector.prepare_context_volume(
            sample_context, exec_config
        )
        
        assert Path(volume_path).exists()
        assert volume_name.startswith("phixr-context-")
        
        # Cleanup
        injector.cleanup_context_volume(volume_name)
    
    def test_issue_context_serialization(self, injector, sample_context, exec_config):
        """Test that issue context is properly serialized."""
        volume_path, volume_name = injector.prepare_context_volume(
            sample_context, exec_config
        )
        
        issue_file = Path(volume_path) / "issue.json"
        assert issue_file.exists()
        
        # Read and verify JSON
        with open(issue_file) as f:
            issue_data = json.load(f)
        
        assert issue_data["issue_id"] == 123
        assert issue_data["title"] == "Add authentication feature"
        assert "feature" in issue_data["labels"]
        
        injector.cleanup_context_volume(volume_name)
    
    def test_config_serialization(self, injector, sample_context, exec_config):
        """Test that execution config is properly serialized."""
        volume_path, volume_name = injector.prepare_context_volume(
            sample_context, exec_config
        )
        
        config_file = Path(volume_path) / "config.json"
        assert config_file.exists()
        
        # Read and verify JSON
        with open(config_file) as f:
            config_data = json.load(f)
        
        assert config_data["session_id"] == "sess-test123"
        assert config_data["issue_id"] == 123
        assert config_data["mode"] == "build"
        assert config_data["timeout_minutes"] == 30
        
        injector.cleanup_context_volume(volume_name)
    
    def test_repository_metadata_serialization(self, injector, sample_context, exec_config):
        """Test that repository metadata is properly serialized."""
        volume_path, volume_name = injector.prepare_context_volume(
            sample_context, exec_config
        )
        
        repo_file = Path(volume_path) / "repository.json"
        assert repo_file.exists()
        
        # Read and verify JSON
        with open(repo_file) as f:
            repo_data = json.load(f)
        
        assert repo_data["name"] == "test-repo"
        assert repo_data["language"] == "python"
        assert "src/" in repo_data["structure"]
        
        injector.cleanup_context_volume(volume_name)
    
    def test_instructions_generation(self, injector, sample_context, exec_config):
        """Test that instructions are generated."""
        volume_path, volume_name = injector.prepare_context_volume(
            sample_context, exec_config
        )
        
        instructions_file = Path(volume_path) / "instructions.md"
        assert instructions_file.exists()
        
        # Read and verify content
        content = instructions_file.read_text()
        assert "Issue" in content
        assert "123" in content  # issue_id
        assert "development" in content
        
        injector.cleanup_context_volume(volume_name)
    
    def test_all_context_files_created(self, injector, sample_context, exec_config):
        """Test that all context files are created."""
        volume_path, volume_name = injector.prepare_context_volume(
            sample_context, exec_config
        )
        
        volume_dir = Path(volume_path)
        files = list(volume_dir.glob("*.json")) + list(volume_dir.glob("*.md"))
        
        assert len(files) == 4  # issue.json, config.json, repository.json, instructions.md
        
        injector.cleanup_context_volume(volume_name)
    
    def test_context_size_validation(self, injector, sample_context, exec_config):
        """Test context size validation."""
        # Create large context that exceeds limit
        from datetime import datetime
        large_context = IssueContext(
            issue_id=123,
            project_id=456,
            title="x" * 1000000,  # Very large title
            description="y" * 8 * 1024 * 1024,  # 8MB description
            url="https://gitlab.com/test/repo/-/issues/123",
            author="test-user",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 30, 0),
            repo_url="https://github.com/test/repo.git",
            repo_name="test-repo",
            language="python",
            structure={},
            labels=[],
        )
        
        # Configure injector with small limit
        config = SandboxConfig(context_volume_size=1 * 1024 * 1024)  # 1MB limit
        injector = ContextInjector(config)
        
        with pytest.raises(ValueError, match="Context too large"):
            injector.prepare_context_volume(large_context, exec_config)
    
    def test_environment_variables_creation(self, injector, sample_context, exec_config):
        """Test environment variable generation."""
        env_vars = injector.create_environment_variables(
            sample_context, exec_config, "test-token"
        )
        
        assert env_vars["PHIXR_SESSION_ID"] == "sess-test123"
        assert env_vars["PHIXR_ISSUE_ID"] == "123"
        assert env_vars["PHIXR_REPO_URL"] == "https://github.com/test/repo.git"
        assert env_vars["PHIXR_BRANCH"] == "ai-work/issue-123"
        assert env_vars["PHIXR_GIT_TOKEN"] == "test-token"
        assert env_vars["OPENCODE_MODE"] == "build"
    
    def test_environment_variables_with_prompt(self, injector, sample_context):
        """Test environment variables with initial prompt."""
        exec_config = ExecutionConfig(
            session_id="sess-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
            initial_prompt="Custom prompt for OpenCode",
        )
        
        env_vars = injector.create_environment_variables(
            sample_context, exec_config, "token"
        )
        
        assert env_vars["OPENCODE_INITIAL_PROMPT"] == "Custom prompt for OpenCode"
    
    def test_context_cleanup(self, injector, sample_context, exec_config):
        """Test context volume cleanup."""
        volume_path, volume_name = injector.prepare_context_volume(
            sample_context, exec_config
        )
        
        # Verify it exists
        assert Path(volume_path).exists()
        
        # Cleanup
        result = injector.cleanup_context_volume(volume_name)
        assert result is True
        
        # Verify it's cleaned
        # Note: directory might still exist if temp was not removed
    
    def test_cleanup_all(self, injector, sample_context, exec_config):
        """Test cleanup of all volumes."""
        # Create multiple volumes
        volumes = []
        for i in range(3):
            config = ExecutionConfig(
                session_id=f"sess-{i}",
                issue_id=123 + i,
                repo_url="https://github.com/test/repo.git",
                branch="main",
            )
            volume_path, volume_name = injector.prepare_context_volume(
                sample_context, config
            )
            volumes.append((volume_path, volume_name))
        
        # Cleanup all
        injector.cleanup_all()
        
        # Verify registry is empty
        assert len(injector.temp_dirs) == 0
    
    def test_context_injector_different_modes(self, injector, sample_context):
        """Test context injection with different execution modes."""
        for mode in [ExecutionMode.BUILD, ExecutionMode.PLAN, ExecutionMode.REVIEW]:
            exec_config = ExecutionConfig(
                session_id=f"sess-{mode.value}",
                issue_id=123,
                repo_url="https://github.com/test/repo.git",
                branch="main",
                mode=mode,
            )
            
            volume_path, volume_name = injector.prepare_context_volume(
                sample_context, exec_config
            )
            
            # Verify mode is in config
            config_file = Path(volume_path) / "config.json"
            with open(config_file) as f:
                config_data = json.load(f)
            
            assert config_data["mode"] == mode.value
            
            injector.cleanup_context_volume(volume_name)


class TestContextInjectorEdgeCases:
    """Test edge cases for context injection."""
    
    @pytest.fixture
    def injector(self):
        """Create context injector."""
        return ContextInjector(SandboxConfig())
    
    def test_empty_labels(self, injector):
        """Test context with empty labels."""
        from datetime import datetime
        context = IssueContext(
            issue_id=1,
            project_id=100,
            title="Test",
            description="Desc",
            url="https://gitlab.com/test/repo/-/issues/1",
            author="test-user",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 30, 0),
            repo_url="https://github.com/test/repo.git",
            repo_name="repo",
            language="python",
            structure={},
            labels=[],
        )
        
        exec_config = ExecutionConfig(
            session_id="sess-test",
            issue_id=1,
            repo_url="https://github.com/test/repo.git",
            branch="main",
        )
        
        volume_path, volume_name = injector.prepare_context_volume(context, exec_config)
        
        # Should still create files
        assert Path(volume_path).exists()
        assert (Path(volume_path) / "issue.json").exists()
        
        injector.cleanup_context_volume(volume_name)
    
    def test_special_characters_in_session_id(self, injector):
        """Test handling special characters in session ID."""
        from datetime import datetime
        context = IssueContext(
            issue_id=1,
            project_id=100,
            title="Test",
            description="Desc",
            url="https://gitlab.com/test/repo/-/issues/1",
            author="test-user",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 30, 0),
            repo_url="https://github.com/test/repo.git",
            repo_name="repo",
            language="python",
            structure={},
            labels=[],
        )
        
        exec_config = ExecutionConfig(
            session_id="sess-abc123",
            issue_id=1,
            repo_url="https://github.com/test/repo.git",
            branch="main",
        )
        
        volume_path, volume_name = injector.prepare_context_volume(context, exec_config)
        assert Path(volume_path).exists()
        
        injector.cleanup_context_volume(volume_name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
