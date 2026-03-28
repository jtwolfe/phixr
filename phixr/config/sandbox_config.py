"""Sandbox configuration for OpenCode container execution."""

import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


def _load_env_file():
    """Load environment variables from .env.local file."""
    candidates = [
        Path(".env.local"),        # local dev (cwd)
        Path("/app/.env.local"),   # Docker container
    ]
    for env_path in candidates:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        if key and value:
                            os.environ.setdefault(key.strip(), value.strip())
            break


_load_env_file()


class SandboxConfig(BaseSettings):
    """Configuration for sandbox container execution."""
    
    # ==================== OpenCode API ====================
    opencode_server_url: str = Field(
        default="http://opencode-server:4096",
        description="OpenCode HTTP API server URL - use service name for Docker, localhost for dev"
    )

    opencode_public_url: str = Field(
        default="",
        description="Public-facing OpenCode URL for session links in GitLab comments. "
                    "If empty, falls back to opencode_server_url. "
                    "Set this when the server URL is a Docker-internal hostname."
    )

    # ==================== Phixr Web Interface ====================
    phixr_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for Phixr web interface (for vibe room links)"
    )
    
    # ==================== Docker Settings ====================
    docker_host: str = Field(
        default="unix:///run/user/1000/podman/podman.sock",
        description="Container runtime socket (Podman rootless)"
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
        description="GitLab/GitHub instance URL - adjust for your environment"
    )
    
    git_provider_token: str = Field(
        default="",
        description="Token for cloning private repositories"
    )
    
    git_provider_type: str = Field(
        default="gitlab",
        description="Type of git provider (gitlab, github, gitea)"
    )
    
    # ==================== SSH Key Management ====================
    git_ssh_key_path: str = Field(
        default="/root/.ssh/id_rsa",
        description="Path to SSH private key for git operations"
    )
    
    git_ssh_key_passphrase: str = Field(
        default="",
        description="SSH key passphrase (if needed)"
    )
    
    # ==================== Model / Provider Configuration ====================
    # Only one provider is active at a time. Set the provider and its
    # corresponding API key / base URL.
    #
    # Supported providers:
    #   "zen"    — OpenCode Zen (cloud, needs API key)
    #   "ollama" — Local Ollama instance (needs base URL, no API key)
    #   "openai" — OpenAI-compatible API (needs API key + optional base URL)
    #
    # The provider and model are passed to OpenCode per-prompt so the
    # OpenCode server itself doesn't need provider configuration.

    provider: str = Field(
        default="ollama",
        description="LLM provider: 'zen', 'ollama', or 'openai'"
    )

    model: str = Field(
        default="qwen2.5-coder",
        description="Model ID for the configured provider"
    )

    provider_api_key: str = Field(
        default="",
        description="API key for the provider (not needed for Ollama)"
    )

    provider_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for the provider API (Ollama default: http://localhost:11434)"
    )

    model_temperature: float = Field(
        default=0.7,
        description="Temperature for model responses"
    )

    model_context_window: int = Field(
        default=4096,
        description="LLM context window size"
    )

    @property
    def opencode_provider_id(self) -> str:
        """Map our provider name to OpenCode's providerID."""
        return {
            "zen": "opencode",
            "ollama": "ollama",
            "openai": "openai",
        }.get(self.provider, self.provider)

    @property
    def opencode_model_id(self) -> str:
        """Map our model name to OpenCode's modelID."""
        if self.provider == "zen":
            return f"opencode/{self.model}"
        return self.model
    
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
        default="redis://redis:6379/1",
        description="Redis connection string for session state - use service name in Docker"
    )
    
    database_url: str = Field(
        default="postgresql://phixr:phixr@postgres:5432/phixr",
        description="PostgreSQL connection for session history - use service name in Docker"
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
