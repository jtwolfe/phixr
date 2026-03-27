"""Pydantic settings for Phixr application."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import os
from pathlib import Path


def load_env_file():
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


load_env_file()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        case_sensitive=False,
        extra="ignore"
    )

    # ==================== Service URLs ====================
    # These should be configured via environment variables for deployment
    
    # GitLab Configuration
    gitlab_url: str = "http://192.168.1.145:8080"
    gitlab_root_password: str = ""
    gitlab_bot_token: str = ""
    gitlab_root_token: str = ""
    
    # Bot Configuration
    bot_username: str = "phixr-bot"
    bot_email: str = "phixr-bot@localhost"
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    debug: bool = False
    
    # Webhook Configuration
    webhook_secret: str = "phixr-webhook-secret"
    webhook_url: str = "http://localhost:8000/webhooks/gitlab"
    
    # OpenCode Server URL (for container environments, can be different host)
    opencode_server_url: str = "http://localhost:4096"
    
    # Phixr API Base URL (used in vibe room links, public-facing URL)
    phixr_api_url: str = "http://localhost:8000"
    
    # Database Configuration (with defaults for Docker network)
    postgres_url: str = "postgresql://phixr:phixr@postgres:5432/phixr"
    
    # Redis Configuration (with defaults for Docker network)
    redis_url: str = "redis://redis:6379/0"
    
    # Logging
    log_level: str = "DEBUG"
    
    # OpenCode Zen Configuration
    opencode_zen_api_key: str = ""
    
    # Phase 2: Sandbox Configuration
    phixr_sandbox_docker_host: str = "unix:///run/user/1000/podman/podman.sock"
    phixr_sandbox_opencode_image: str = "phixr-opencode:latest"
    phixr_sandbox_docker_network: str = "phixr-network"
    phixr_sandbox_memory_limit: str = "2g"
    phixr_sandbox_cpu_limit: float = 1.0
    phixr_sandbox_timeout_minutes: int = 30
    phixr_sandbox_max_sessions: int = 10


settings = Settings()
