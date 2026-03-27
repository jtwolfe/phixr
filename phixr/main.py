"""Main Phixr application."""
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from phixr.config import settings
from phixr.utils import setup_logger, GitLabClient
from phixr.handlers import AssignmentHandler, CommentHandler
from phixr.webhooks import setup_webhook_routes

from phixr.config.sandbox_config import SandboxConfig
from phixr.integration.opencode_integration_service import OpenCodeIntegrationService
from phixr.access_management import AccessManagementService
from phixr.models.execution_models import SessionStatus

# Setup logging
logger = setup_logger(__name__, settings.log_level)

# Create FastAPI app
app = FastAPI(
    title="Phixr",
    description="Hybrid Git-Integrated Collaborative AI Coding Platform",
    version="0.2.0"
)

# Setup templates and static files
templates = Jinja2Templates(directory="phixr/web/templates")
app.mount("/static", StaticFiles(directory="phixr/web/static"), name="static")

# Global state
_gitlab_client = None
_assignment_handler = None
_comment_handler = None

# OpenCode integration
sandbox_config: Optional[SandboxConfig] = None
opencode_integration: Optional[OpenCodeIntegrationService] = None

# Access management
access_manager: Optional[AccessManagementService] = None


async def initialize_app():
    """Initialize the application with necessary components."""
    global _gitlab_client, _assignment_handler, _comment_handler
    global sandbox_config, opencode_integration, access_manager

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
    bot_user = await _gitlab_client.get_user(settings.bot_username)
    if not bot_user:
        logger.error(f"Bot user '{settings.bot_username}' not found")
        raise ValueError(f"Bot user '{settings.bot_username}' not found in GitLab")

    bot_user_id = bot_user['id']
    logger.info(f"Bot user ID: {bot_user_id}")

    # Initialize handlers
    _assignment_handler = AssignmentHandler(bot_user_id, _gitlab_client)
    _comment_handler = CommentHandler(_gitlab_client, bot_user_id, _assignment_handler)

    # Setup webhook routes
    webhook_router = setup_webhook_routes(_comment_handler)
    app.include_router(webhook_router)

    # Initialize sandbox components
    _initialize_sandbox()

    # Inject integration into comment handler
    if opencode_integration and _comment_handler:
        _comment_handler.set_opencode_integration(opencode_integration)
        logger.info("  OpenCode integration injected into CommentHandler")

    logger.info("Phixr initialized successfully")


def _initialize_sandbox():
    """Initialize OpenCode integration components."""
    global sandbox_config, opencode_integration, access_manager

    try:
        logger.info("Initializing OpenCode integration...")
        sandbox_config = SandboxConfig()
        logger.info(f"  OpenCode server URL: {sandbox_config.opencode_server_url}")

        # Access management (optional, needs root token)
        if settings.gitlab_root_token:
            try:
                access_manager = AccessManagementService(
                    gitlab_url=settings.gitlab_url,
                    root_token=settings.gitlab_root_token,
                    bot_username=settings.bot_username
                )
                logger.info("  Access management service initialized")
            except Exception as e:
                logger.warning(f"  Access management init failed (non-fatal): {e}")
                access_manager = None
        else:
            logger.warning("  No GITLAB_ROOT_TOKEN — access management disabled")

        # OpenCode integration service
        opencode_integration = OpenCodeIntegrationService(
            config=sandbox_config,
            base_url=settings.phixr_api_url,
        )
        logger.info("  OpenCode integration service initialized")

    except Exception as e:
        logger.warning(f"OpenCode integration initialization failed: {e}")
        logger.warning("OpenCode features will be unavailable")
        sandbox_config = None
        opencode_integration = None


async def _cleanup_sandbox():
    """Cleanup OpenCode integration components."""
    global sandbox_config, opencode_integration, access_manager

    if opencode_integration:
        try:
            await opencode_integration.close()
        except Exception as e:
            logger.warning(f"Error closing OpenCode integration: {e}")
        opencode_integration = None

    sandbox_config = None
    access_manager = None
    logger.info("OpenCode integration cleanup complete")


@app.on_event("startup")
async def startup_event():
    """FastAPI startup event."""
    try:
        await initialize_app()

        if access_manager:
            await access_manager.start_monitoring()
            logger.info("Access management monitoring started")

    except Exception as e:
        logger.error(f"Failed to initialize Phixr: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event."""
    logger.info("Phixr shutting down...")

    if access_manager:
        await access_manager.stop_monitoring()

    await _cleanup_sandbox()
    logger.info("Phixr shutdown complete")


# =============================================================================
# Core Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    health_data = {
        "status": "healthy",
        "version": "0.2.0",
        "gitlab_url": settings.gitlab_url,
        "opencode_available": opencode_integration is not None,
    }

    if access_manager:
        try:
            access_health = await access_manager.health_check()
            health_data["access_management"] = access_health
            if not access_health.get("healthy", False):
                health_data["status"] = "degraded"
        except Exception as e:
            health_data["access_management"] = {"healthy": False, "error": str(e)}
            health_data["status"] = "degraded"

    return JSONResponse(status_code=200, content=health_data)


@app.get("/info")
async def app_info():
    """Get application information."""
    return JSONResponse(status_code=200, content={
        "name": "Phixr",
        "version": "0.2.0",
        "status": "development",
        "bot_username": settings.bot_username,
        "gitlab_url": settings.gitlab_url,
        "opencode_enabled": opencode_integration is not None,
        "sandbox_configured": sandbox_config is not None,
    })


# =============================================================================
# Session API
# =============================================================================

def _require_integration() -> OpenCodeIntegrationService:
    """Require OpenCode integration to be available."""
    if not opencode_integration:
        raise HTTPException(
            status_code=503,
            detail="OpenCode integration not available. Check configuration."
        )
    return opencode_integration


@app.get("/api/v1/sessions")
async def list_sessions(status: Optional[str] = None):
    """List all tracked sessions."""
    integration = _require_integration()

    status_filter = SessionStatus(status) if status else None
    sessions = await integration.list_sessions(status_filter=status_filter)
    return JSONResponse(status_code=200, content={
        "sessions": [s.model_dump() for s in sessions],
        "count": len(sessions),
    })


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get details of a specific session."""
    integration = _require_integration()

    session = await integration.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return JSONResponse(status_code=200, content=session.model_dump())


@app.get("/api/v1/sessions/{session_id}/results")
async def get_session_results(session_id: str):
    """Get results for a completed session."""
    integration = _require_integration()

    result = await integration.get_session_results(session_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No results for session: {session_id}")

    return JSONResponse(status_code=200, content=result)


@app.post("/api/v1/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop a running session."""
    integration = _require_integration()

    success = await integration.stop_session(session_id)
    return JSONResponse(status_code=200, content={
        "session_id": session_id,
        "stopped": success,
    })


@app.get("/api/v1/sandbox/health")
async def sandbox_health():
    """Check sandbox health and availability."""
    if not sandbox_config or not opencode_integration:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "Not configured"}
        )

    opencode_healthy = await opencode_integration.health_check()
    sessions = await opencode_integration.list_sessions()

    return JSONResponse(status_code=200, content={
        "status": "healthy" if opencode_healthy else "degraded",
        "opencode_server": sandbox_config.opencode_server_url,
        "opencode_reachable": opencode_healthy,
        "active_sessions": len([s for s in sessions if s.status == SessionStatus.RUNNING]),
        "total_sessions": len(sessions),
        "max_sessions": sandbox_config.max_sessions,
    })


# =============================================================================
# Vibe Room Web Interface
# =============================================================================

@app.get("/vibe/{room_id}", response_class=HTMLResponse)
async def get_vibe_room(request: Request, room_id: str):
    """Serve the vibe coding room web interface."""
    integration = _require_integration()

    room = integration.get_vibe_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Vibe room not found")

    session = integration.sessions.get(room.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Build OpenCode web UI URL for embedding
    oc_session_id = integration.opencode_session_ids.get(session.id)
    opencode_url = integration.config.opencode_server_url

    if oc_session_id:
        try:
            oc_session = await integration.client.get_session(oc_session_id)
            if oc_session:
                slug = oc_session.get("slug")
                if slug:
                    opencode_url = f"{integration.config.opencode_server_url}/s/{slug}"
        except Exception as e:
            logger.warning(f"Could not get OpenCode session details: {e}")

    return templates.TemplateResponse("vibe_room.html", {
        "request": request,
        "room": room,
        "session": session,
        "opencode_url": opencode_url,
        "participant_count": len(room.participants),
        "message_count": len(room.messages)
    })


@app.get("/api/v1/vibe/rooms/{room_id}")
async def get_vibe_room_api(room_id: str):
    """Get vibe room information via API."""
    integration = _require_integration()

    room = integration.get_vibe_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Vibe room not found")

    session = integration.sessions.get(room.session_id)
    return JSONResponse(status_code=200, content={
        "room": room.model_dump(),
        "session": session.model_dump() if session else None,
    })


@app.post("/api/v1/vibe/rooms/{room_id}/messages")
async def add_vibe_message(room_id: str, message: str, user_id: str = "anonymous"):
    """Add a message to a vibe room."""
    integration = _require_integration()

    room = integration.get_vibe_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Vibe room not found")

    msg = integration.vibe_manager.add_message(
        room_id=room_id,
        content=message,
        user_id=user_id,
        username=f"user-{user_id[:8]}"
    )

    return JSONResponse(status_code=200, content={"message": msg.model_dump()})


@app.post("/vibe/{room_id}/closeout")
async def close_out_vibe_room(room_id: str):
    """Close out a vibe room session."""
    integration = _require_integration()

    room = integration.get_vibe_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Vibe room not found")

    session = integration.sessions.get(room.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(f"Closing out vibe room {room_id} for session {session.id}")

    success = await integration.stop_session(session.id)
    integration.vibe_manager.archive_room(room_id)

    return JSONResponse(status_code=200, content={
        "status": "success" if success else "error",
        "message": "Session stopped and room archived" if success else "Failed to stop session",
    })


@app.get("/api/v1/vibe/rooms")
async def list_vibe_rooms():
    """List all vibe rooms."""
    integration = _require_integration()

    rooms = integration.vibe_manager.list_rooms()
    return JSONResponse(status_code=200, content={
        "rooms": [room.model_dump() for room in rooms]
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower()
    )
