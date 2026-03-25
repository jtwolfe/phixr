"""Main Phixr application."""
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from phixr.config import settings
from phixr.utils import setup_logger, GitLabClient
from phixr.handlers import AssignmentHandler, CommentHandler
from phixr.webhooks import setup_webhook_routes

# Setup logging
logger = setup_logger(__name__, settings.log_level)

# Create FastAPI app
app = FastAPI(
    title="Phixr",
    description="Hybrid Git-Integrated Collaborative AI Coding Platform",
    version="0.1.0"
)

# Global state (will move to proper DI container in later phases)
_gitlab_client = None
_assignment_handler = None
_comment_handler = None


def initialize_app():
    """Initialize the application with necessary components."""
    global _gitlab_client, _assignment_handler, _comment_handler
    
    logger.info(f"Initializing Phixr...")
    logger.info(f"GitLab URL: {settings.gitlab_url}")
    
    # Initialize GitLab client
    if not settings.gitlab_bot_token:
        logger.error("GITLAB_BOT_TOKEN not set in environment")
        raise ValueError("GITLAB_BOT_TOKEN environment variable is required")
    
    _gitlab_client = GitLabClient(settings.gitlab_url, settings.gitlab_bot_token)
    
    # Validate GitLab connection
    if not _gitlab_client.validate_connection():
        logger.error("Failed to validate GitLab connection")
        raise ConnectionError("Cannot connect to GitLab instance")
    
    # Get bot user ID
    bot_user = _gitlab_client.get_user(settings.bot_username)
    if not bot_user:
        logger.error(f"Bot user '{settings.bot_username}' not found")
        raise ValueError(f"Bot user '{settings.bot_username}' not found in GitLab")
    
    bot_user_id = bot_user['id']
    logger.info(f"Bot user ID: {bot_user_id}")
    
    # Initialize handlers
    _assignment_handler = AssignmentHandler(bot_user_id)
    _comment_handler = CommentHandler(_gitlab_client, bot_user_id, _assignment_handler)
    
    # Setup webhook routes
    webhook_router = setup_webhook_routes(_comment_handler)
    app.include_router(webhook_router)
    
    logger.info("✅ Phixr initialized successfully")


@app.on_event("startup")
async def startup_event():
    """FastAPI startup event."""
    try:
        initialize_app()
    except Exception as e:
        logger.error(f"Failed to initialize Phixr: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "version": "0.1.0",
            "gitlab_url": settings.gitlab_url
        }
    )


@app.get("/info")
async def app_info():
    """Get application information."""
    return JSONResponse(
        status_code=200,
        content={
            "name": "Phixr",
            "version": "0.1.0",
            "phase": "Phase 1 - Bot Infrastructure",
            "status": "development",
            "bot_username": settings.bot_username,
            "gitlab_url": settings.gitlab_url
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower()
    )
