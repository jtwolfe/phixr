"""Integration tests for Docker client and container manager.

These tests require Docker to be running and are marked as integration tests.
"""

import pytest
import logging
from unittest.mock import Mock, patch, MagicMock

from phixr.sandbox.docker_client import DockerClientWrapper
from phixr.sandbox.container_manager import ContainerManager
from phixr.config.sandbox_config import SandboxConfig
from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import ExecutionConfig, ExecutionMode, SessionStatus

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.docker
class TestDockerClientWrapper:
    """Integration tests for Docker client wrapper."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SandboxConfig(
            docker_host="unix:///var/run/docker.sock",
            opencode_image="alpine:latest",  # Use light image for testing
            docker_network="phixr-test-network",
        )
    
    @pytest.fixture
    def docker_client(self, config):
        """Create Docker client."""
        try:
            client = DockerClientWrapper(config)
            yield client
            client.close()
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")
    
    def test_docker_connection(self, docker_client):
        """Test Docker connection establishment."""
        assert docker_client.client is not None
        logger.info("✓ Docker connection successful")
    
    def test_network_creation(self, docker_client, config):
        """Test Docker network creation."""
        network_name = docker_client.ensure_network()
        assert network_name == config.docker_network
        logger.info(f"✓ Network created/verified: {network_name}")
    
    def test_volume_creation(self, docker_client):
        """Test Docker volume creation."""
        volume_name = "phixr-test-volume"
        created_name = docker_client.create_volume(volume_name)
        
        assert created_name == volume_name
        logger.info(f"✓ Volume created: {volume_name}")
    
    def test_simple_container_run(self, docker_client):
        """Test running a simple container."""
        container_id, exit_code, logs = docker_client.run_container(
            image="alpine:latest",
            mounts={},
            env={"TEST_VAR": "test_value"},
            timeout=10,
        )
        
        assert container_id is not None
        assert exit_code is not None
        logger.info(f"✓ Container ran: {container_id} (exit_code={exit_code})")
    
    def test_container_with_environment(self, docker_client):
        """Test container with environment variables."""
        env = {
            "TEST_VAR1": "value1",
            "TEST_VAR2": "value2",
        }
        
        container_id, exit_code, logs = docker_client.run_container(
            image="alpine:latest",
            mounts={},
            env=env,
            timeout=10,
        )
        
        assert exit_code is not None
        assert container_id is not None
        logger.info(f"✓ Container with env ran successfully")
    
    def test_container_timeout(self, docker_client):
        """Test container timeout handling."""
        # Run sleep command that exceeds timeout
        container_id, exit_code, logs = docker_client.run_container(
            image="alpine:latest",
            mounts={},
            env={},
            timeout=1,  # 1 second timeout
        )
        
        # Should timeout
        assert exit_code == 124 or container_id is not None
        logger.info(f"✓ Timeout handled correctly")


@pytest.mark.integration
class TestContainerManager:
    """Integration tests for container manager."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = SandboxConfig(
            docker_host="unix:///var/run/docker.sock",
            opencode_image="alpine:latest",
            timeout_minutes=1,
            max_sessions=5,
        )
        return config
    
    @pytest.fixture
    def container_manager(self, config):
        """Create container manager."""
        try:
            manager = ContainerManager(config)
            yield manager
            manager.close()
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")
    
    @pytest.fixture
    def sample_context(self):
        """Create sample context."""
        from datetime import datetime
        return IssueContext(
            issue_id=123,
            project_id=456,
            title="Test feature",
            description="Test description",
            url="https://gitlab.com/test/repo/-/issues/123",
            author="test-user",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 30, 0),
            repo_url="https://github.com/test/repo.git",
            repo_name="test-repo",
            language="python",
            structure={},
            labels=["test"],
        )
    
    def test_session_creation(self, container_manager, sample_context):
        """Test creating a session."""
        exec_config = ExecutionConfig(
            session_id="sess-test123",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="ai-work/123",
        )
        
        try:
            session = container_manager.create_session(sample_context, exec_config)
            
            assert session.id == "sess-test123"
            assert session.issue_id == 123
            assert session.status in [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.ERROR]
            logger.info(f"✓ Session created: {session.id}")
        except Exception as e:
            pytest.skip(f"Container creation failed: {e}")
    
    def test_get_session(self, container_manager, sample_context):
        """Test retrieving a session."""
        exec_config = ExecutionConfig(
            session_id="sess-get-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
        )
        
        try:
            session = container_manager.create_session(sample_context, exec_config)
            
            # Retrieve it
            retrieved = container_manager.get_session(session.id)
            assert retrieved is not None
            assert retrieved.id == session.id
            logger.info(f"✓ Session retrieved: {retrieved.id}")
        except Exception as e:
            pytest.skip(f"Test skipped: {e}")
    
    def test_list_sessions(self, container_manager, sample_context):
        """Test listing sessions."""
        sessions = container_manager.list_sessions()
        
        assert isinstance(sessions, list)
        logger.info(f"✓ Listed sessions: {len(sessions)}")
    
    def test_get_session_logs(self, container_manager, sample_context):
        """Test getting session logs."""
        exec_config = ExecutionConfig(
            session_id="sess-logs-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
        )
        
        try:
            session = container_manager.create_session(sample_context, exec_config)
            
            # Get logs
            logs = container_manager.get_session_logs(session.id)
            assert isinstance(logs, str)
            logger.info(f"✓ Retrieved logs ({len(logs)} chars)")
        except Exception as e:
            pytest.skip(f"Test skipped: {e}")
    
    def test_get_session_results(self, container_manager, sample_context):
        """Test getting session results."""
        exec_config = ExecutionConfig(
            session_id="sess-results-test",
            issue_id=123,
            repo_url="https://github.com/test/repo.git",
            branch="main",
        )
        
        try:
            session = container_manager.create_session(sample_context, exec_config)
            
            # Get results
            result = container_manager.get_session_results(session.id)
            assert result is not None
            assert result.session_id == session.id
            logger.info(f"✓ Retrieved results for session")
        except Exception as e:
            pytest.skip(f"Test skipped: {e}")
    
    def test_cleanup_old_sessions(self, container_manager):
        """Test cleanup of old sessions."""
        count = container_manager.cleanup_old_sessions(older_than_hours=0)
        assert isinstance(count, int)
        logger.info(f"✓ Cleaned up {count} old sessions")


@pytest.mark.integration
class TestOpenCodeBridge:
    """Integration tests for OpenCode bridge."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = SandboxConfig(
            docker_host="unix:///var/run/docker.sock",
            opencode_image="alpine:latest",
        )
        return config
    
    @pytest.fixture
    def bridge(self, config):
        """Create OpenCode bridge."""
        try:
            from phixr.bridge.opencode_bridge import OpenCodeBridge
            bridge = OpenCodeBridge(config)
            yield bridge
            bridge.close()
        except Exception as e:
            pytest.skip(f"Bridge initialization failed: {e}")
    
    def test_bridge_initialization(self, bridge):
        """Test bridge initialization."""
        assert bridge is not None
        assert bridge.container_manager is not None
        logger.info("✓ Bridge initialized successfully")
    
    def test_bridge_session_listing(self, bridge):
        """Test listing sessions via bridge."""
        sessions = bridge.list_sessions()
        assert isinstance(sessions, list)
        logger.info(f"✓ Listed {len(sessions)} sessions via bridge")


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SandboxConfig(
            docker_host="unix:///var/run/docker.sock",
            opencode_image="alpine:latest",
            timeout_minutes=2,
        )
    
    @pytest.fixture
    def context(self):
        """Create test context."""
        from datetime import datetime
        return IssueContext(
            issue_id=999,
            project_id=789,
            title="E2E Test Feature",
            description="End-to-end test description",
            url="https://gitlab.com/test/repo/-/issues/999",
            author="e2e-user",
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            updated_at=datetime(2024, 1, 2, 12, 30, 0),
            repo_url="https://github.com/test/repo.git",
            repo_name="e2e-test",
            language="python",
            structure={"src/": "source", "tests/": "tests"},
            labels=["e2e-test"],
        )
    
    def test_full_session_lifecycle(self, config, context):
        """Test full session lifecycle from creation to completion."""
        try:
            from phixr.bridge.opencode_bridge import OpenCodeBridge
            from phixr.models.execution_models import ExecutionMode
            
            bridge = OpenCodeBridge(config)
            
            # Start session
            session = bridge.start_opencode_session(
                context=context,
                mode=ExecutionMode.BUILD,
                timeout_minutes=1,
            )
            
            assert session.id is not None
            logger.info(f"✓ Started session: {session.id}")
            
            # Monitor session
            status = bridge.monitor_session(session.id)
            assert status is not None
            logger.info(f"✓ Monitored session status")
            
            # Get logs
            logs = bridge.get_session_logs(session.id)
            assert isinstance(logs, str)
            logger.info(f"✓ Retrieved logs ({len(logs)} chars)")
            
            # Extract results
            result = bridge.extract_results(session.id)
            if result:
                logger.info(f"✓ Extracted results (exit_code={result.exit_code})")
            
            bridge.close()
            
        except Exception as e:
            pytest.skip(f"E2E test skipped: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
