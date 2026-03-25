"""Bot configuration management."""
from pydantic import BaseModel


class BotConfig(BaseModel):
    """Configuration for the Phixr bot."""
    
    username: str
    email: str
    token: str
    gitlab_url: str
    bot_user_id: int | None = None
    
    class Config:
        arbitrary_types_allowed = True
