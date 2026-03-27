"""Unit tests for sandbox configuration system."""

import pytest
from phixr.config.sandbox_config import SandboxConfig, get_sandbox_config


class TestSandboxConfig:
    """Test SandboxConfig validation and configuration."""
    
    def test_default_config_creation(self):
        """Test creating config with default values."""
        config = SandboxConfig()
        
        assert config.docker_host == "unix:///run/user/1000/podman/podman.sock"
        assert config.timeout_minutes == 30
        assert config.max_sessions == 10
        assert config.memory_limit == "2g"
        assert config.cpu_limit == 1.0
    
    def test_config_validation_timeout(self):
        """Test timeout validation."""
        # Valid timeout
        config = SandboxConfig(timeout_minutes=15)
        config.validate_limits()  # Should not raise
        
        # Invalid timeout (too low)
        config = SandboxConfig(timeout_minutes=0)
        with pytest.raises(ValueError, match="timeout_minutes must be between"):
            config.validate_limits()
        
        # Invalid timeout (too high)
        config = SandboxConfig(timeout_minutes=500)
        with pytest.raises(ValueError, match="timeout_minutes must be between"):
            config.validate_limits()
    
    def test_config_validation_cpu(self):
        """Test CPU limit validation."""
        # Valid CPU
        config = SandboxConfig(cpu_limit=2.0)
        config.validate_limits()  # Should not raise
        
        # Invalid CPU (too low)
        config = SandboxConfig(cpu_limit=0.05)
        with pytest.raises(ValueError, match="cpu_limit must be between"):
            config.validate_limits()
        
        # Invalid CPU (too high)
        config = SandboxConfig(cpu_limit=5.0)
        with pytest.raises(ValueError, match="cpu_limit must be between"):
            config.validate_limits()
    
    def test_config_validation_max_sessions(self):
        """Test max sessions validation."""
        # Valid max sessions
        config = SandboxConfig(max_sessions=25)
        config.validate_limits()  # Should not raise
        
        # Invalid (too low)
        config = SandboxConfig(max_sessions=0)
        with pytest.raises(ValueError, match="max_sessions must be between"):
            config.validate_limits()
        
        # Invalid (too high)
        config = SandboxConfig(max_sessions=150)
        with pytest.raises(ValueError, match="max_sessions must be between"):
            config.validate_limits()
    
    def test_memory_limit_conversion(self):
        """Test memory limit conversion to bytes."""
        config = SandboxConfig(memory_limit="2g")
        assert config.get_docker_memory_limit() == 2 * 1024 ** 3
        
        config = SandboxConfig(memory_limit="512m")
        assert config.get_docker_memory_limit() == 512 * 1024 ** 2
        
        config = SandboxConfig(memory_limit="1024k")
        assert config.get_docker_memory_limit() == 1024 * 1024
    
    def test_memory_limit_invalid_format(self):
        """Test invalid memory limit format."""
        config = SandboxConfig(memory_limit="invalid")
        with pytest.raises(ValueError, match="Invalid memory_limit"):
            config.get_docker_memory_limit()
    
    def test_config_environment_variables(self):
        """Test loading config from environment variables."""
        # This would require setting env vars, skipping for now
        # In practice, pydantic-settings handles this
        pass
    
    def test_get_sandbox_config(self):
        """Test helper function to get config."""
        config = get_sandbox_config()
        assert isinstance(config, SandboxConfig)
        assert config.docker_host == "unix:///run/user/1000/podman/podman.sock"
    
    def test_config_security_defaults(self):
        """Test security configuration defaults."""
        config = SandboxConfig()
        assert config.enable_apparmor is True
        assert config.enable_seccomp is True
        assert config.readonly_root is False
        assert config.privileged is False
    
    def test_config_network_defaults(self):
        """Test network configuration defaults."""
        config = SandboxConfig()
        assert config.allow_external_network is False
        assert config.docker_network == "phixr-network"
    
    def test_allowed_commands_defaults(self):
        """Test allowed commands list."""
        config = SandboxConfig()
        assert "npm" in config.allowed_commands
        assert "python" in config.allowed_commands
        assert "git" in config.allowed_commands


class TestSandboxConfigEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_config_with_custom_values(self):
        """Test config with all custom values."""
        config = SandboxConfig(
            timeout_minutes=45,
            cpu_limit=2.5,
            memory_limit="4g",
            max_sessions=20,
            docker_network="custom-network",
        )
        
        assert config.timeout_minutes == 45
        assert config.cpu_limit == 2.5
        assert config.memory_limit == "4g"
        assert config.max_sessions == 20
        assert config.docker_network == "custom-network"
    
    def test_config_validation_boundary(self):
        """Test config validation at boundaries."""
        # Minimum valid timeout
        config = SandboxConfig(timeout_minutes=1)
        config.validate_limits()  # Should not raise
        
        # Maximum valid timeout
        config = SandboxConfig(timeout_minutes=480)
        config.validate_limits()  # Should not raise
        
        # Minimum valid CPU
        config = SandboxConfig(cpu_limit=0.1)
        config.validate_limits()  # Should not raise
        
        # Maximum valid CPU
        config = SandboxConfig(cpu_limit=4.0)
        config.validate_limits()  # Should not raise
    
    def test_config_git_provider_types(self):
        """Test different git provider configurations."""
        for provider in ["gitlab", "github", "gitea"]:
            config = SandboxConfig(git_provider_type=provider)
            assert config.git_provider_type == provider
    
    def test_config_execution_modes(self):
        """Test execution mode configuration."""
        config = SandboxConfig(model="gpt-4")
        assert config.model == "gpt-4"
        
        config = SandboxConfig(model_temperature=0.5)
        assert config.model_temperature == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
