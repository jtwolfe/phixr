"""Pydantic settings for Phixr application."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # GitLab Configuration
    gitlab_url: str = "http://localhost:8080"
    gitlab_root_password: str = ""
    gitlab_bot_token: str = ""
    
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
    
    class Config:
        env_file = ".env.local"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
