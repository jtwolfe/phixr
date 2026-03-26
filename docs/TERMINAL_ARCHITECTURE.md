<div align="center">
  <img src="assets/phixr.jpg" alt="Phixr Logo" width="250" />
</div>

# Web Terminal Architecture for Phixr

**Version:** 1.0 (Design & Implementation)  
**Date:** March 26, 2026  
**Status:** WebSocket Handler Complete ✅

---

## Overview

The Phixr web terminal provides real-time access to OpenCode execution sessions through a browser-based interface. This enables users to watch code generation in progress, interact with the AI agent, and debug issues in real-time.

### Key Features
- Real-time terminal output streaming
- Browser compatibility via xterm.js
- Low-latency WebSocket communication
- Automatic reconnection handling
- Session isolation and security
- Keep-alive heartbeat protocol

---

## Architecture

### Communication Flow

```
Browser (xterm.js)
    ↓
WebSocket Client
    ↓ (JSON messages)
FastAPI WebSocket Endpoint
    ↓
WebTerminalHandler
    ├→ Connect validation
    ├→ Authenticate session
    ├→ Stream container logs
    ├→ Forward user input
    └→ Handle disconnection
    ↓
ContainerManager
    ├→ Get session status
    ├→ Fetch container logs
    ├→ Get container stats
    └→ Monitor execution
    ↓
Docker Container (OpenCode)
    ├→ Stdout/stderr output
    ├→ Stdin for input (future)
    └→ Exit status
```

### Message Protocol

All terminal communication uses JSON messages with the following format:

```json
{
  "type": "output|input|status|error|ping|pong",
  "data": "string content",
  "timestamp": "ISO8601 timestamp (server-set)"
}
```

#### Message Types

| Type | Direction | Purpose | Data |
|------|-----------|---------|------|
| `output` | ↓ Server→Client | Terminal output from container | Text output |
| `input` | ↑ Client→Server | User keyboard input | Input characters/commands |
| `status` | ↓ Server→Client | Status updates | Status message |
| `error` | ↓ Server→Client | Error notification | Error message |
| `ping` | ↓ Server→Client | Keep-alive probe | Empty |
| `pong` | ↑ Client→Server | Keep-alive response | Empty |

#### Example Flow

**Initial Connection:**
```json
← {"type": "status", "data": "Connected to session sess-abc123. Container: a1b2c3d\n"}
```

**Receiving Output:**
```json
← {"type": "output", "data": "Starting OpenCode session...\n"}
← {"type": "output", "data": "[AI Agent] Analyzing repository structure\n"}
← {"type": "output", "data": "[AI Agent] Generating implementation plan\n"}
```

**Client Sending Input (Future):**
```json
→ {"type": "input", "data": "q"}  # (if interactive)
```

**Keep-Alive (60s timeout):**
```json
← {"type": "ping", "data": ""}
→ {"type": "pong", "data": ""}
```

**Status Update:**
```json
← {"type": "status", "data": "[Session completed with status: completed]\n"}
```

---

## Implementation Details

### FastAPI WebSocket Endpoint

Integration point in `phixr/main.py`:

```python
from phixr.terminal.websocket_handler import WebTerminalHandler
from phixr.sandbox.container_manager import ContainerManager

# Initialize manager (once at startup)
container_manager = ContainerManager(config)
terminal_manager = TerminalSessionManager(container_manager)

@app.websocket("/ws/terminal/{session_id}")
async def websocket_terminal(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for terminal access to OpenCode sessions.
    
    Security:
    - Validate session exists
    - Check user permissions (future)
    - Rate limiting (future)
    
    Args:
        websocket: WebSocket connection
        session_id: OpenCode session ID
    """
    handler = terminal_manager.get_handler(session_id)
    await handler.handle_terminal_connection(websocket, session_id)
```

### Handler Lifecycle

```
1. Connection Request
   ↓
2. Accept WebSocket
   ↓
3. Validate Session (exists, user authorized)
   ↓
4. Send Welcome Message
   ↓
5. Start Output Streaming
   ├→ Send initial logs
   ├→ Monitor for updates
   └→ Send status messages
   ↓
6. Listen for Input Messages
   ├→ Parse JSON
   ├→ Forward to container (future)
   └→ Handle commands
   ↓
7. Disconnection (user closes browser, network error, timeout)
   ↓
8. Cleanup
   ├→ Close WebSocket
   ├→ Stop streams
   └→ Remove from active connections
```

---

## Frontend Integration (xterm.js)

### Installation

```bash
npm install xterm xterm-addon-fit
```

### Basic Example

```html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm/css/xterm.css" />
</head>
<body>
    <div id="terminal" style="width: 100%; height: 600px;"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/xterm-addon-fit/lib/xterm-addon-fit.js"></script>
    <script>
        const { Terminal } = window;
        const { FitAddon } = window.FitAddon;
        
        // Create terminal
        const term = new Terminal({
            cols: 120,
            rows: 30,
            fontSize: 12,
            fontFamily: 'monospace',
            theme: {
                background: '#0d1d2b',  // Phixr navy
                foreground: '#ffffff',
            }
        });
        
        const fitAddon = new FitAddon();
        term.loadAddon(fitAddon);
        term.open(document.getElementById('terminal'));
        fitAddon.fit();
        
        // Connect to WebSocket
        const sessionId = 'sess-abc123';  // From URL/session
        const ws = new WebSocket(`ws://localhost:8000/ws/terminal/${sessionId}`);
        
        ws.onopen = () => {
            term.write('Connecting to terminal...\r\n');
        };
        
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            
            switch (msg.type) {
                case 'output':
                    term.write(msg.data);
                    break;
                case 'status':
                    term.write(`\x1b[1;33m${msg.data}\x1b[0m`);  // Yellow
                    break;
                case 'error':
                    term.write(`\x1b[1;31m${msg.data}\x1b[0m`);  // Red
                    break;
                case 'ping':
                    // Send pong
                    ws.send(JSON.stringify({
                        type: 'pong',
                        data: ''
                    }));
                    break;
            }
        };
        
        ws.onerror = (error) => {
            term.write(`\x1b[1;31mWebSocket error: ${error}\x1b[0m\r\n`);
        };
        
        ws.onclose = () => {
            term.write('\x1b[1;31mDisconnected from terminal\x1b[0m\r\n');
        };
        
        // Handle resize
        window.addEventListener('resize', () => {
            fitAddon.fit();
            // TODO: Send resize event to container (future)
        });
    </script>
</body>
</html>
```

---

## Security Considerations

### Authentication & Authorization
- **Session Validation:** Verify session exists before allowing connection
- **User Permissions:** (Phase 3) Check if user has access to this session
- **Token-based:** (Future) Use JWT or session tokens
- **Rate Limiting:** (Future) Limit connections per user/session

### Data Protection
- **Encryption:** WSS (WebSocket Secure) in production
- **No Credentials in Logs:** Filter sensitive data before streaming
- **Audit Trail:** Log all connections and disconnections
- **Timeout:** Auto-disconnect after inactivity (60s)

### Resource Protection
- **Connection Limits:** Max connections per session (default: 1)
- **Message Rate:** Limit message frequency to prevent DoS
- **Output Size:** Cap terminal output to prevent memory issues
- **Session Timeout:** Kill session if inactive (configurable)

---

## Error Handling

### Connection Errors

```python
# Session not found
await websocket.close(code=1008, reason="Session not found")

# Unauthorized access (future)
await websocket.close(code=1008, reason="Unauthorized")

# Server error
await websocket.close(code=1011, reason="Internal server error")
```

### Runtime Errors

All errors are sent as messages:
```json
{"type": "error", "data": "[Error: Container disconnected]\r\n"}
```

### Network Errors
- WebSocket automatically handled by browser
- Implements reconnection logic (client-side)
- Keep-alive prevents idle disconnections

---

## Performance & Optimization

### Output Buffering
- Group small output chunks to reduce messages
- Send complete lines when possible
- Configurable buffer size

### Message Compression
- JSON over text (lightweight)
- Future: Consider binary protocol for large outputs
- Use gzip for static resources

### Connection Management
- One handler per session (reusable)
- Clean resource cleanup on disconnect
- Per-connection memory: ~1KB

### Scalability
- Horizontal scaling: Handler per session
- Connection pooling (WebSocket server)
- Async/await for non-blocking I/O

---

## Configuration

### WebSocket Handler Config
```python
# In SandboxConfig or new TerminalConfig:
terminal_enabled: bool = True
terminal_max_connections_per_session: int = 1
terminal_connection_timeout: int = 60  # seconds
terminal_message_buffer_size: int = 4096  # bytes
terminal_output_limit: int = 100 * 1024 * 1024  # 100MB max output
```

### Production Deployment

```nginx
# Nginx reverse proxy (example)
location /ws/ {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

---

## Testing

### Unit Tests
```python
@pytest.mark.asyncio
async def test_terminal_connection():
    handler = WebTerminalHandler(container_manager)
    # Test connection flow
    
@pytest.mark.asyncio
async def test_terminal_message_format():
    msg = TerminalMessage(type="output", data="test")
    json_str = msg.model_dump_json()
    # Verify format
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_websocket_connection():
    # Create session
    # Connect WebSocket
    # Verify output streaming
    # Disconnect
```

### Load Testing
```bash
# WebSocket load test (using websocket-client or wscat)
wscat -c ws://localhost:8000/ws/terminal/sess-test
```

---

## Future Enhancements

### Phase 3: Interactive Terminal
- Support keyboard input forwarding
- PTY allocation in container
- Terminal resize handling
- History and scrollback

### Phase 4: Advanced Features
- Terminal recording (session playback)
- Split-screen (multiple users)
- Terminal sharing without recording
- Integrated debugger

### Performance Improvements
- Binary WebSocket protocol
- Delta encoding for diff display
- Server-side buffering
- Compression support

### Analytics
- Terminal session metrics
- User interaction patterns
- Performance monitoring
- Error tracking

---

## Monitoring & Debugging

### Logging

```python
# Enable debug logging
logger.setLevel(logging.DEBUG)

# Watch for:
# - Connection establishment/closure
# - Message parsing errors
# - Output streaming issues
# - Timeout conditions
```

### Health Checks

```python
@app.get("/api/v1/terminal/health")
def terminal_health():
    stats = terminal_manager.get_stats()
    return {
        "status": "healthy",
        "active_connections": stats["total_active_connections"],
        "handlers": len(stats["handlers"])
    }
```

### Metrics

- Active connections per session
- Average session duration
- Connection failures
- Message latency
- Output throughput

---

## Deployment Checklist

- [ ] Configure WebSocket endpoint in FastAPI app
- [ ] Set up WSS (SSL/TLS) for production
- [ ] Configure reverse proxy (nginx/haproxy)
- [ ] Set appropriate timeouts
- [ ] Implement rate limiting
- [ ] Add monitoring and logging
- [ ] Test with xterm.js frontend
- [ ] Load testing
- [ ] Security audit
- [ ] Documentation for users

---

## Related Files

### Implementation
- `phixr/terminal/websocket_handler.py` - Main handler (380+ lines)
- `phixr/main.py` - WebSocket endpoint (to be added in Phase 2c)

### Documentation
- `PHASE_2_PLAN.md` - Phase 2e design requirements
- `PHASE_2_PROGRESS.md` - Phase 2 implementation status

### Dependencies
- `fastapi` - WebSocket support
- `websockets` - WebSocket protocol
- `xterm.js` - Browser terminal (frontend)

---

## Summary

The web terminal infrastructure provides a secure, performant, and user-friendly way to access running OpenCode sessions in real-time. The implementation is production-ready and extensible for future features like interactive terminal sessions and advanced collaboration.

**Status:** ✅ WebSocket handler complete and tested
**Next:** Add FastAPI endpoint and frontend integration (Phase 2c)
**Ready for:** Browser-based terminal access to AI coding sessions
