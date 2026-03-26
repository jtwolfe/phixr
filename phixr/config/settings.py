"""Pydantic settings for Phixr application."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import os
from pathlib import Path


def load_env_file():
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


load_env_file()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        case_sensitive=False,
        extra="ignore"
    )

    # GitLab Configuration
    gitlab_url: str = "http://localhost:8080"
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
    
    # Database Configuration
    postgres_url: str = "postgresql://phixr:phixr@localhost:5432/phixr"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Logging
    log_level: str = "INFO"
    
    # OpenCode Zen Configuration
    opencode_zen_api_key: str = ""
    
    # Phase 2: Sandbox Configuration
    phixr_sandbox_docker_host: str = "unix:///var/run/docker.sock"
    phixr_sandbox_opencode_image: str = "phixr-opencode:latest"
    phixr_sandbox_docker_network: str = "phixr-network"
    phixr_sandbox_memory_limit: str = "2g"
    phixr_sandbox_cpu_limit: float = 1.0
    phixr_sandbox_timeout_minutes: int = 30
    phixr_sandbox_max_sessions: int = 10


settings = Settings()
