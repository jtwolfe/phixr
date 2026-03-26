"""Main Phixr application."""
import logging
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from phixr.config import settings
from phixr.utils import setup_logger, GitLabClient
from phixr.handlers import AssignmentHandler, CommentHandler
from phixr.webhooks import setup_webhook_routes

# Phase 2 imports
from phixr.config.sandbox_config import SandboxConfig
from phixr.bridge.opencode_bridge import OpenCodeBridge
from phixr.terminal.websocket_handler import WebTerminalHandler
from phixr.models.execution_models import (
    Session, ExecutionResult, ExecutionMode, SessionStatus
)
from phixr.models.issue_context import IssueContext

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

# Phase 2 - Sandbox and OpenCode components
sandbox_config: Optional[SandboxConfig] = None
opencode_bridge: Optional[OpenCodeBridge] = None
terminal_manager: Optional[WebTerminalHandler] = None


def initialize_app():
    """Initialize the application with necessary components."""
    global _gitlab_client, _assignment_handler, _comment_handler
    global sandbox_config, opencode_bridge, terminal_manager
    
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
    
    # Phase 2: Initialize sandbox components
    _initialize_sandbox()
    
    # Inject opencode_bridge into comment handler if available
    if opencode_bridge and _comment_handler:
        _comment_handler.set_opencode_bridge(opencode_bridge)
        logger.info("  OpenCode bridge injected into CommentHandler")
    
    logger.info("✅ Phixr initialized successfully")


def _initialize_sandbox():
    """Initialize Phase 2 sandbox and OpenCode components."""
    global sandbox_config, opencode_bridge, terminal_manager
    
    try:
        logger.info("Initializing Phase 2 sandbox components...")
        sandbox_config = SandboxConfig()
        logger.info(f"  Sandbox config loaded (server: {sandbox_config.opencode_server_url})")
        
        opencode_bridge = OpenCodeBridge(sandbox_config)
        logger.info("  OpenCode bridge initialized")
        
        # Note: Terminal manager currently expects container_manager (legacy).
        # Will be updated to use opencode_bridge directly in Phase 2b
        # For now, we skip terminal_manager initialization as websocket streaming
        # will be handled via OpenCode API messages
        terminal_manager = None  # WebTerminalHandler(opencode_bridge)
        logger.info("  Terminal messaging via OpenCode API")
        
        logger.info("✅ Phase 2 sandbox initialized (API-based)")
    except Exception as e:
        logger.warning(f"Phase 2 sandbox initialization failed: {e}")
        logger.warning("Sandbox features will be unavailable")
        sandbox_config = None
        opencode_bridge = None
        terminal_manager = None


def _cleanup_sandbox():
    """Cleanup Phase 2 sandbox components."""
    global sandbox_config, opencode_bridge, terminal_manager
    
    if opencode_bridge:
        try:
            logger.info("Closing OpenCode bridge...")
            opencode_bridge.close()
        except Exception as e:
            logger.warning(f"Error closing OpenCode bridge: {e}")
        opencode_bridge = None
    
    terminal_manager = None
    sandbox_config = None
    logger.info("Phase 2 sandbox cleanup complete")


@app.on_event("startup")
async def startup_event():
    """FastAPI startup event."""
    try:
        initialize_app()
    except Exception as e:
        logger.error(f"Failed to initialize Phixr: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """FastAPI shutdown event - cleanup Phase 2 resources."""
    logger.info("Phixr shutting down...")
    _cleanup_sandbox()
    logger.info("Phixr shutdown complete")


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
    info = {
        "name": "Phixr",
        "version": "0.1.0",
        "phase": "Phase 2 - OpenCode Integration",
        "status": "development",
        "bot_username": settings.bot_username,
        "gitlab_url": settings.gitlab_url,
        "phase2": {
            "enabled": opencode_bridge is not None,
            "sandbox_configured": sandbox_config is not None,
        }
    }
    return JSONResponse(status_code=200, content=info)


# =============================================================================
# Phase 2: Sandbox and OpenCode Endpoints
# =============================================================================

def _require_sandbox():
    """Helper to require sandbox to be initialized."""
    if not opencode_bridge:
        raise HTTPException(
            status_code=503,
            detail="Sandbox not available. Check Phase 2 configuration."
        )
    return opencode_bridge


@app.post("/api/v1/sessions/start")
async def start_session(
    issue_id: int,
    repo_url: str,
    mode: ExecutionMode = ExecutionMode.BUILD,
    branch: str = None,
    initial_prompt: str = None,
    timeout_minutes: int = None,
):
    """Start a new OpenCode session for an issue.
    
    Creates a container with the issue context and starts an OpenCode session.
    """
    bridge = _require_sandbox()
    
    context = IssueContext(
        issue_id=issue_id,
        repo_url=repo_url,
        branch=branch or f"ai-work/issue-{issue_id}",
    )
    
    try:
        session = bridge.start_opencode_session(
            context=context,
            mode=mode,
            initial_prompt=initial_prompt,
            timeout_minutes=timeout_minutes,
        )
        return JSONResponse(status_code=201, content=session.model_dump())
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions")
async def list_sessions(status: SessionStatus = None):
    """List all OpenCode sessions, optionally filtered by status."""
    bridge = _require_sandbox()
    
    sessions = bridge.list_sessions(status_filter=status)
    return JSONResponse(status_code=200, content={
        "sessions": [s.model_dump() for s in sessions],
        "count": len(sessions),
    })


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get details of a specific session."""
    bridge = _require_sandbox()
    
    session = bridge.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    return JSONResponse(status_code=200, content=session.model_dump())


@app.get("/api/v1/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Get only the status of a session."""
    bridge = _require_sandbox()
    
    try:
        status = bridge.monitor_session(session_id)
        return JSONResponse(status_code=200, content=status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/sessions/{session_id}/logs")
async def get_session_logs(session_id: str):
    """Get container logs for a session."""
    bridge = _require_sandbox()
    
    logs = bridge.get_session_logs(session_id)
    return JSONResponse(status_code=200, content={"session_id": session_id, "logs": logs})


@app.get("/api/v1/sessions/{session_id}/results")
async def get_session_results(session_id: str):
    """Get execution results for a completed session."""
    bridge = _require_sandbox()
    
    result = bridge.extract_results(session_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No results available for session: {session_id}"
        )
    
    return JSONResponse(status_code=200, content=result.model_dump())


@app.post("/api/v1/sessions/{session_id}/stop")
async def stop_session(session_id: str, force: bool = False):
    """Stop a running session."""
    bridge = _require_sandbox()
    
    success = bridge.stop_opencode_session(session_id, force=force)
    return JSONResponse(status_code=200, content={
        "session_id": session_id,
        "stopped": success,
    })


@app.get("/api/v1/sandbox/health")
async def sandbox_health():
    """Check sandbox health and availability."""
    if not sandbox_config:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "reason": "Sandbox not configured"}
        )
    
    sessions = []
    if opencode_bridge:
        sessions = opencode_bridge.list_sessions()
    
    return JSONResponse(status_code=200, content={
        "status": "healthy",
        "image": sandbox_config.opencode_image,
        "active_sessions": len([s for s in sessions if s.status == SessionStatus.RUNNING]),
        "total_sessions": len(sessions),
        "max_sessions": sandbox_config.max_sessions,
    })


@app.websocket("/ws/terminal/{session_id}")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time terminal access to a session.
    
    Connect via: ws://host/ws/terminal/{session_id}
    Send JSON messages: {"type": "input", "data": "command"} or {"type": "ping"}
    Receive JSON messages: {"type": "output|status|error", "data": "...", "timestamp": "..."}
    """
    if not terminal_manager:
        await websocket.close(code=1011, reason="Terminal manager not available")
        return
    
    await terminal_manager.handle_terminal_connection(websocket, session_id)


@app.get("/api/v1/terminal/stats")
async def terminal_stats():
    """Get terminal connection statistics."""
    if not terminal_manager:
        raise HTTPException(status_code=503, detail="Terminal manager not available")
    
    return JSONResponse(status_code=200, content={
        "active_connections": len(terminal_manager.active_connections),
        "session_streams": len(terminal_manager.session_streams),
    })


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower()
    )
