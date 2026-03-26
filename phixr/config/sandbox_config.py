"""Sandbox configuration for OpenCode container execution."""

import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


def _load_env_file():
    """Load environment variables from .env.local file."""
    env_path = Path("/app/.env.local")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    if key and value:
                        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


class SandboxConfig(BaseSettings):
    """Configuration for sandbox container execution."""
    
    # ==================== Phase 2 OpenCode API ====================
    opencode_server_url: str = Field(
        default="http://localhost:4096",
        description="OpenCode HTTP API server URL (Phase 2)"
    )
    
    # ==================== Docker Settings ====================
    docker_host: str = Field(
        default="unix:///var/run/docker.sock",
        description="Docker daemon connection string"
    )
    
    opencode_image: str = Field(
        default="ghcr.io/phixr/opencode:latest",
        description="OpenCode Docker image URI"
    )
    
    docker_network: str = Field(
        default="phixr-network",
        description="Docker network for containers"
    )
    
    # ==================== Resource Limits ====================
    memory_limit: str = Field(
        default="2g",
        description="Memory limit per container (e.g., '2g', '1024m')"
    )
    
    cpu_limit: float = Field(
        default=1.0,
        description="CPU limit per container (in CPUs)"
    )
    
    disk_limit: str = Field(
        default="10g",
        description="Disk limit per container"
    )
    
    timeout_minutes: int = Field(
        default=30,
        description="Default timeout for sessions (minutes)"
    )
    
    max_sessions: int = Field(
        default=10,
        description="Maximum concurrent sessions allowed"
    )
    
    # ==================== Git / VCS ====================
    git_provider_url: str = Field(
        default="http://localhost:8080",
        description="GitLab/GitHub instance URL"
    )
    
    git_provider_token: str = Field(
        default="",
        description="Token for cloning private repositories"
    )
    
    git_provider_type: str = Field(
        default="gitlab",
        description="Type of git provider (gitlab, github, gitea)"
    )
    
    # ==================== Model Configuration ====================
    model: str = Field(
        default="opencode/big-pickle",
        description="Default LLM model to use"
    )
    
    # OpenCode Zen API key - loaded via environment variable
    # Note: env_prefix="PHIXR_SANDBOX_" adds prefix, so field name without prefix
    opencode_zen_api_key: str = Field(
        default="",
        description="OpenCode Zen API key for big-pickle model"
    )
    
    @property
    def zen_api_key(self) -> str:
        """Get the Zen API key."""
        return self.opencode_zen_api_key
    
    model_temperature: float = Field(
        default=0.7,
        description="Temperature for model responses"
    )
    
    model_context_window: int = Field(
        default=4096,
        description="LLM context window size"
    )
    
    # ==================== Execution Policies ====================
    allow_external_network: bool = Field(
        default=False,
        description="Allow containers to access external networks"
    )
    
    allow_destructive_operations: bool = Field(
        default=False,
        description="Allow destructive operations (force push, etc.)"
    )
    
    allowed_commands: List[str] = Field(
        default_factory=lambda: ["npm", "python", "git", "node", "bun"],
        description="List of allowed shell commands in container"
    )
    
    # ==================== Security ====================
    enable_apparmor: bool = Field(
        default=True,
        description="Enable AppArmor security profile"
    )
    
    enable_seccomp: bool = Field(
        default=True,
        description="Enable seccomp security profile"
    )
    
    readonly_root: bool = Field(
        default=False,
        description="Use read-only root filesystem"
    )
    
    privileged: bool = Field(
        default=False,
        description="Run containers in privileged mode (dangerous!)"
    )
    
    # ==================== Storage ====================
    context_volume_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB
        description="Maximum context volume size (bytes)"
    )
    
    results_volume_size: int = Field(
        default=500 * 1024 * 1024,  # 500MB
        description="Maximum results volume size (bytes)"
    )
    
    persist_volumes: bool = Field(
        default=False,
        description="Persist volumes after session completion"
    )
    
    # ==================== Monitoring & Logging ====================
    enable_metrics: bool = Field(
        default=True,
        description="Enable container metrics collection"
    )
    
    log_level: str = Field(
        default="info",
        description="Logging level (debug, info, warning, error)"
    )
    
    collect_logs: bool = Field(
        default=True,
        description="Collect and store container logs"
    )
    
    # ==================== Redis & Database ====================
    redis_url: str = Field(
        default="redis://localhost:6379/1",
        description="Redis connection string for session state"
    )
    
    database_url: str = Field(
        default="postgresql://phixr:phixr@localhost:5432/phixr",
        description="PostgreSQL connection for session history"
    )
    
    model_config = ConfigDict(
        env_prefix="PHIXR_SANDBOX_",
        case_sensitive=False,
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra fields from .env.local
    )
    
    def validate_limits(self) -> None:
        """Validate resource limit configuration."""
        if self.timeout_minutes < 1 or self.timeout_minutes > 480:
            raise ValueError("timeout_minutes must be between 1 and 480")
        
        if self.cpu_limit < 0.1 or self.cpu_limit > 4.0:
            raise ValueError("cpu_limit must be between 0.1 and 4.0 CPUs")
        
        if self.max_sessions < 1 or self.max_sessions > 100:
            raise ValueError("max_sessions must be between 1 and 100")
    
    def get_docker_memory_limit(self) -> int:
        """Convert memory_limit to Docker API format (bytes)."""
        limit = self.memory_limit.lower()
        multipliers = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}
        
        for suffix, mult in multipliers.items():
            if limit.endswith(suffix):
                try:
                    value = int(limit[:-1])
                    return value * mult
                except ValueError:
                    raise ValueError(f"Invalid memory_limit: {self.memory_limit}")
        
        raise ValueError(f"Invalid memory_limit format: {self.memory_limit}")


def get_sandbox_config() -> SandboxConfig:
    """Get or create sandbox configuration."""
    config = SandboxConfig()
    config.validate_limits()
    return config


if __name__ == "__main__":
    # Example usage
    config = get_sandbox_config()
    print(f"Docker host: {config.docker_host}")
    print(f"Memory limit: {config.memory_limit} ({config.get_docker_memory_limit()} bytes)")
    print(f"Timeout: {config.timeout_minutes} minutes")
    print(f"Max concurrent sessions: {config.max_sessions}")
