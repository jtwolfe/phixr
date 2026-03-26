<div align="center">
  <img src="assets/phixr.jpg" alt="Phixr Logo" width="250" />
</div>

# Phase 2 Integration Guide: Adding API Endpoints

**Version:** 1.0  
**Date:** March 26, 2026  
**Purpose:** Step-by-step guide to integrate Phase 2 components into Phixr bot

---

## Overview

This guide explains how to integrate the Phase 2 sandbox and terminal components into the existing Phixr FastAPI application. This enables the bot to trigger OpenCode sessions and expose session management via HTTP/WebSocket APIs.

---

## Components to Integrate

### Existing Phase 1 Components
- ✅ `phixr/main.py` - FastAPI application
- ✅ `phixr/config/settings.py` - Application settings
- ✅ `phixr/utils/gitlab_client.py` - GitLab integration
- ✅ `phixr/handlers/comment_handler.py` - Comment event handling

### New Phase 2 Components
- ✅ `phixr/sandbox/container_manager.py` - Container lifecycle
- ✅ `phixr/bridge/opencode_bridge.py` - Main integration bridge
- ✅ `phixr/terminal/websocket_handler.py` - Terminal streaming
- ✅ `phixr/config/sandbox_config.py` - Sandbox configuration

---

## Integration Steps

### Step 1: Update FastAPI Application Initialization

**File:** `phixr/main.py`

Add imports and initialize managers:

```python
# At top of file, add imports:
from phixr.bridge.opencode_bridge import OpenCodeBridge
from phixr.terminal.websocket_handler import TerminalSessionManager
from phixr.config.sandbox_config import SandboxConfig

# After FastAPI app creation, add:
# Initialize sandbox configuration
try:
    sandbox_config = SandboxConfig()
    sandbox_config.validate_limits()
except Exception as e:
    logger.error(f"Failed to load sandbox config: {e}")
    sandbox_config = None

# Initialize OpenCode bridge
opencode_bridge = None
terminal_manager = None

if sandbox_config:
    try:
        opencode_bridge = OpenCodeBridge(sandbox_config)
        terminal_manager = TerminalSessionManager(
            opencode_bridge.container_manager
        )
        logger.info("✓ OpenCode bridge initialized")
        logger.info("✓ Terminal manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize sandbox: {e}")

# Add startup event
@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Phixr bot starting up...")
    if opencode_bridge:
        logger.info("✓ Sandbox system ready")

# Add shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Phixr bot shutting down...")
    if opencode_bridge:
        try:
            opencode_bridge.close()
            logger.info("✓ Sandbox system closed")
        except Exception as e:
            logger.error(f"Error closing sandbox: {e}")
```

### Step 2: Add Session Management Endpoints

**File:** `phixr/main.py` (continue adding)

```python
from fastapi import HTTPException, Query
from typing import Optional

# ==================== Session Management Endpoints ====================

@app.post("/api/v1/sessions/start")
async def start_session(
    issue_id: int,
    repo_url: str,
    mode: str = Query("build", regex="^(build|plan|review)$"),
    timeout_minutes: Optional[int] = None,
    initial_prompt: Optional[str] = None,
):
    """Start a new OpenCode session.
    
    Args:
        issue_id: GitLab/GitHub issue ID
        repo_url: Git repository URL
        mode: Execution mode (build, plan, review)
        timeout_minutes: Override default timeout
        initial_prompt: Initial message to send to OpenCode
        
    Returns:
        Session details
        
    Raises:
        HTTPException: If sandbox not available or validation fails
    """
    if not opencode_bridge:
        raise HTTPException(
            status_code=503,
            detail="Sandbox system not available"
        )
    
    try:
        # Create minimal context (in production, fetch from GitLab)
        from phixr.models.issue_context import IssueContext
        
        context = IssueContext(
            issue_id=issue_id,
            issue_title=f"Issue #{issue_id}",
            issue_description="Context to be populated from issue",
            repo_url=repo_url,
            repo_name=repo_url.split("/")[-1].replace(".git", ""),
            language="unknown",
            structure={},
            issue_labels=[],
        )
        
        # Convert mode string to enum
        from phixr.models.execution_models import ExecutionMode
        execution_mode = ExecutionMode(mode)
        
        # Start session
        session = opencode_bridge.start_opencode_session(
            context=context,
            mode=execution_mode,
            initial_prompt=initial_prompt,
            timeout_minutes=timeout_minutes,
        )
        
        logger.info(f"Session started: {session.id}")
        
        return {
            "session_id": session.id,
            "status": session.status.value,
            "container_id": session.container_id,
            "branch": session.branch,
            "started_at": session.started_at.isoformat() if session.started_at else None,
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail="Failed to start session")


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details.
    
    Args:
        session_id: Session ID
        
    Returns:
        Session information
        
    Raises:
        HTTPException: If session not found
    """
    if not opencode_bridge:
        raise HTTPException(status_code=503, detail="Sandbox not available")
    
    session = opencode_bridge.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "id": session.id,
        "issue_id": session.issue_id,
        "status": session.status.value,
        "mode": session.mode.value,
        "container_id": session.container_id,
        "created_at": session.created_at.isoformat(),
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "exit_code": session.exit_code,
        "timeout_minutes": session.timeout_minutes,
        "branch": session.branch,
    }


@app.get("/api/v1/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Get session and container status.
    
    Args:
        session_id: Session ID
        
    Returns:
        Real-time status including resource usage
        
    Raises:
        HTTPException: If session not found
    """
    if not opencode_bridge:
        raise HTTPException(status_code=503, detail="Sandbox not available")
    
    try:
        status = opencode_bridge.monitor_session(session_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/sessions/{session_id}/logs")
async def get_session_logs(
    session_id: str,
    tail: Optional[int] = Query(None, description="Last N lines")
):
    """Get session logs.
    
    Args:
        session_id: Session ID
        tail: Optional limit to last N lines
        
    Returns:
        Log content
        
    Raises:
        HTTPException: If session not found
    """
    if not opencode_bridge:
        raise HTTPException(status_code=503, detail="Sandbox not available")
    
    logs = opencode_bridge.get_session_logs(session_id)
    
    if tail:
        lines = logs.split('\n')
        logs = '\n'.join(lines[-tail:])
    
    return {
        "session_id": session_id,
        "logs": logs,
        "lines": len(logs.split('\n')),
    }


@app.post("/api/v1/sessions/{session_id}/stop")
async def stop_session(
    session_id: str,
    force: bool = Query(False)
):
    """Stop a running session.
    
    Args:
        session_id: Session ID
        force: Force kill if graceful stop times out
        
    Returns:
        Confirmation
        
    Raises:
        HTTPException: If session not found or stop fails
    """
    if not opencode_bridge:
        raise HTTPException(status_code=503, detail="Sandbox not available")
    
    try:
        success = opencode_bridge.stop_opencode_session(session_id, force=force)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to stop session")
        
        return {
            "session_id": session_id,
            "status": "stopped",
            "force": force,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/sessions/{session_id}/results")
async def get_session_results(session_id: str):
    """Get execution results from completed session.
    
    Args:
        session_id: Session ID
        
    Returns:
        ExecutionResult with code changes and status
        
    Raises:
        HTTPException: If session not found or still running
    """
    if not opencode_bridge:
        raise HTTPException(status_code=503, detail="Sandbox not available")
    
    session = opencode_bridge.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status.value in ("running", "initializing", "created"):
        raise HTTPException(
            status_code=409,
            detail="Session still running, results not available"
        )
    
    result = opencode_bridge.extract_results(session_id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to extract results")
    
    return {
        "session_id": result.session_id,
        "status": result.status.value,
        "success": result.success,
        "exit_code": result.exit_code,
        "files_changed": result.files_changed,
        "num_files_changed": len(result.files_changed),
        "duration_seconds": result.duration_seconds,
        "has_errors": len(result.errors) > 0,
        "errors": result.errors,
        "warnings": result.warnings,
    }


@app.get("/api/v1/sessions")
async def list_sessions(
    status_filter: Optional[str] = Query(None, regex="^(running|completed|failed|stopped)$")
):
    """List all sessions.
    
    Args:
        status_filter: Optional status to filter by
        
    Returns:
        List of sessions
    """
    if not opencode_bridge:
        raise HTTPException(status_code=503, detail="Sandbox not available")
    
    from phixr.models.execution_models import SessionStatus
    
    status_enum = None
    if status_filter:
        status_enum = SessionStatus(status_filter)
    
    sessions = opencode_bridge.list_sessions(status_filter=status_enum)
    
    return {
        "count": len(sessions),
        "sessions": [
            {
                "id": s.id,
                "issue_id": s.issue_id,
                "status": s.status.value,
                "container_id": s.container_id,
                "created_at": s.created_at.isoformat(),
                "started_at": s.started_at.isoformat() if s.started_at else None,
            }
            for s in sessions
        ]
    }

# ==================== WebSocket Terminal Endpoints ====================

from fastapi import WebSocket

@app.websocket("/ws/terminal/{session_id}")
async def websocket_terminal(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for terminal access to OpenCode sessions.
    
    Enables real-time terminal viewing via xterm.js frontend.
    
    Args:
        websocket: WebSocket connection
        session_id: OpenCode session ID
    """
    if not terminal_manager:
        await websocket.close(code=1008, reason="Terminal service not available")
        return
    
    handler = terminal_manager.get_handler(session_id)
    await handler.handle_terminal_connection(websocket, session_id)

# ==================== Terminal Statistics ====================

@app.get("/api/v1/terminal/stats")
async def terminal_stats():
    """Get terminal connection statistics.
    
    Returns:
        Active connections and handlers
    """
    if not terminal_manager:
        raise HTTPException(status_code=503, detail="Terminal service not available")
    
    return terminal_manager.get_stats()

# ==================== Health Check Endpoints ====================

@app.get("/api/v1/sandbox/health")
async def sandbox_health():
    """Check sandbox system health.
    
    Returns:
        Health status
    """
    return {
        "sandbox_available": opencode_bridge is not None,
        "terminal_available": terminal_manager is not None,
        "active_sessions": len(opencode_bridge.list_sessions()) if opencode_bridge else 0,
        "active_terminals": terminal_manager.get_stats()["total_active_connections"] if terminal_manager else 0,
    }
```

### Step 3: Add Session Integration with Phase 1

**File:** `phixr/handlers/comment_handler.py`

Add command to trigger OpenCode session:

```python
# At top of file, add:
from phixr.bridge.opencode_bridge import OpenCodeBridge
from phixr.models.execution_models import ExecutionMode

async def handle_ai_implement_command(issue_id: int, comment_id: int, 
                                      gitlab_client, opencode_bridge: Optional[OpenCodeBridge]):
    """Handle /ai-implement command to start OpenCode session.
    
    Args:
        issue_id: Issue ID
        comment_id: Comment ID
        gitlab_client: GitLab client
        opencode_bridge: OpenCode bridge (if available)
    """
    if not opencode_bridge:
        await gitlab_client.add_issue_comment(
            issue_id, 
            "⚠️ Sandbox system not available. Cannot start code generation session."
        )
        return
    
    try:
        # Get issue context
        issue = gitlab_client.get_issue(issue_id)
        
        # Create Phixr context
        from phixr.models.issue_context import IssueContext
        from phixr.context.extractor import ContextExtractor
        
        context_extractor = ContextExtractor(gitlab_client)
        context = await context_extractor.extract_issue_context(issue_id)
        
        # Start OpenCode session
        session = opencode_bridge.start_opencode_session(
            context=context,
            mode=ExecutionMode.BUILD,
            initial_prompt=f"Implement the requested feature in issue #{issue_id}"
        )
        
        # Reply to issue with session info
        message = f"""
🚀 Started AI coding session!

- Session ID: `{session.id}`
- Status: {session.status.value}
- Container: {session.container_id}
- Branch: `{session.branch}`
- Timeout: {session.timeout_minutes} minutes

**View in real-time:** http://localhost:8000/terminal?session={session.id}

**API Endpoint:** `/api/v1/sessions/{session.id}`
"""
        
        await gitlab_client.add_issue_comment(issue_id, message)
        
    except Exception as e:
        logger.error(f"Error starting OpenCode session: {e}")
        await gitlab_client.add_issue_comment(
            issue_id,
            f"❌ Error starting session: {str(e)}"
        )
```

### Step 4: Update Docker Compose

**File:** `docker-compose.yml`

Ensure proper network setup:

```yaml
version: '3.8'

services:
  phixr-bot:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GITLAB_URL=http://gitlab.local
      - GITLAB_TOKEN=${GITLAB_TOKEN}
      - PHIXR_SANDBOX_DOCKER_HOST=unix:///var/run/docker.sock
      - PHIXR_SANDBOX_OPENCODE_IMAGE=ghcr.io/phixr/opencode:latest
      - PHIXR_SANDBOX_DOCKER_NETWORK=phixr-network
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - phixr-network
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    networks:
      - phixr-network

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=phixr
      - POSTGRES_USER=phixr
      - POSTGRES_PASSWORD=phixr
    networks:
      - phixr-network

networks:
  phixr-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_ip_masquerade: "true"
```

### Step 5: Update Requirements and Installation

**File:** `requirements.txt` (already updated)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Testing Integration

### Test Endpoint Health

```bash
# Check sandbox health
curl http://localhost:8000/api/v1/sandbox/health

# Response:
{
  "sandbox_available": true,
  "terminal_available": true,
  "active_sessions": 0,
  "active_terminals": 0
}
```

### Test Session Creation

```bash
# Start a session
curl -X POST http://localhost:8000/api/v1/sessions/start \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": 123,
    "repo_url": "https://github.com/test/repo.git",
    "mode": "build",
    "timeout_minutes": 30
  }'

# Response:
{
  "session_id": "sess-abc12345",
  "status": "initializing",
  "container_id": "a1b2c3d4",
  "branch": "ai-work/issue-123"
}
```

### Test Session Monitoring

```bash
# Get session status
curl http://localhost:8000/api/v1/sessions/sess-abc12345/status

# Response:
{
  "session_id": "sess-abc12345",
  "status": "running",
  "memory_mb": {"used": 512, "limit": 2048},
  "cpu_percent": 25.5
}
```

### Test Terminal Connection

```bash
# Connect to terminal (example with wscat)
npm install -g wscat
wscat -c ws://localhost:8000/ws/terminal/sess-abc12345

# Then observe output streaming
```

---

## Configuration Summary

### Key Environment Variables

```bash
# OpenCode image (must be built)
PHIXR_SANDBOX_OPENCODE_IMAGE=ghcr.io/phixr/opencode:latest

# Docker connection
PHIXR_SANDBOX_DOCKER_HOST=unix:///var/run/docker.sock

# Resource limits
PHIXR_SANDBOX_MEMORY_LIMIT=2g
PHIXR_SANDBOX_CPU_LIMIT=1.0
PHIXR_SANDBOX_TIMEOUT_MINUTES=30

# Git provider
PHIXR_SANDBOX_GIT_PROVIDER_URL=http://localhost:8080
PHIXR_SANDBOX_GIT_PROVIDER_TOKEN=glpat-...
```

---

## Troubleshooting

### Issue: "Sandbox system not available"
- Check Docker daemon is running: `docker ps`
- Verify Docker socket permissions: `ls -la /var/run/docker.sock`
- Check logs: `docker logs phixr-bot`

### Issue: Container fails to start
- Verify OpenCode image exists: `docker images | grep opencode`
- Check Docker network: `docker network ls | grep phixr`
- Review container logs: `docker logs <container_id>`

### Issue: Terminal not connecting
- Check WebSocket URL format
- Verify session exists: `curl http://localhost:8000/api/v1/sessions/<session_id>`
- Check browser console for errors

---

## Next Steps

1. **Build OpenCode Image:**
   ```bash
   docker build -f docker/opencode.Dockerfile -t ghcr.io/phixr/opencode:latest .
   ```

2. **Test in Local Environment:**
   - Start bot: `python -m phixr.main`
   - Test endpoints
   - Monitor logs

3. **Add Result Extraction (Phase 2d):**
   - Implement `result_extractor.py`
   - Add MR/PR creation

4. **Deploy Frontend (Phase 3):**
   - Build terminal UI with xterm.js
   - Add session dashboard

---

This integration enables the full Phase 2 sandbox functionality while maintaining backward compatibility with Phase 1 bot infrastructure.
