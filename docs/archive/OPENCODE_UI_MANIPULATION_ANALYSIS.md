# OpenCode UI Manipulation & Multi-User Architecture Analysis

**Date**: March 26, 2026  
**Status**: Architectural Analysis for Future Implementation  
**Context**: Single-user vibe coding MVP completed, planning for multi-user expansion

---

## Executive Summary

This document analyzes the architectural implications of embedding and manipulating the OpenCode web UI for multi-user collaborative coding. It explores the trade-offs between iframe embedding (current approach) and custom UI implementations, with specific recommendations for constraining user actions in multi-user scenarios.

---

## Current State Analysis

### OpenCode's Web Architecture

**OpenCode Web UI** (`opencode serve --hostname 0.0.0.0 --port 4096`):
- **Full-featured web IDE**: Monaco editor, terminal, file browser
- **Session-based**: Each session is isolated with its own project directory
- **API-driven**: All functionality accessible via HTTP endpoints
- **Direct browser access**: Users can interact with `http://localhost:4096` directly

### Current Phixr Integration

**Iframe Embedding** (Implemented):
```html
<iframe src="http://localhost:4096" width="100%" height="100%"></iframe>
```

**Session Management**:
- Phixr creates OpenCode sessions via API
- Passes session ID to iframe (future implementation)
- Vibe room provides wrapper UI with controls

---

## Multi-User Constraints Analysis

### Problem Statement

For multi-user vibe coding, we need to prevent users from:
1. Creating new sessions/projects outside the current issue
2. Accessing other users' sessions
3. Modifying project structure inappropriately
4. Exiting the collaborative context

### Current Constraints (Iframe Approach)

**What We CAN Control**:
- ✅ **URL Parameters**: Pass session tokens, user context
- ✅ **Wrapper UI**: Add custom controls around iframe
- ✅ **API Proxying**: Route certain requests through Phixr
- ✅ **Session Isolation**: Each vibe room gets dedicated OpenCode session

**What We CANNOT Control** (Same-Origin Policy):
- ❌ **Direct DOM Manipulation**: Cannot modify iframe content
- ❌ **UI Element Hiding**: Cannot hide OpenCode's native controls
- ❌ **Action Interception**: Cannot prevent all user actions in iframe
- ❌ **Context Switching**: Users can navigate away within iframe

---

## Architectural Options for Multi-User

### Option 1: Enhanced Iframe (Recommended for MVP)

**Implementation Strategy**:
```html
<div class="vibe-room">
  <div class="phixr-controls">
    <!-- Custom controls: participants, chat, issue context -->
  </div>
  <iframe src="http://localhost:4096/session/{session_id}?token={user_token}&constraints=multi-user"
          class="opencode-iframe">
  </iframe>
</div>
```

**Pros**:
- ✅ Leverages OpenCode's full UI/UX
- ✅ Minimal development effort
- ✅ Maintains all OpenCode features
- ✅ Easy to implement incrementally

**Cons**:
- ⚠️ Limited control over user actions
- ⚠️ Users can potentially break out of constraints
- ⚠️ UI inconsistencies between Phixr and OpenCode

**Mitigation Strategies**:
1. **URL-based Constraints**: Pass constraint parameters
2. **Session Tokens**: Validate all actions through Phixr
3. **Overlay Controls**: Add Phixr controls that override/conflict with OpenCode
4. **Proxy API Calls**: Route OpenCode API through Phixr for validation

### Option 2: API-Driven Custom UI (Full Control)

**Implementation Strategy**:
```typescript
// Custom React/Vue component that uses OpenCode API
class VibeCodeEditor extends React.Component {
  render() {
    return (
      <div>
        <MonacoEditor />  // Custom implementation
        <WebTerminal />   // Custom terminal
        <FileBrowser />   // Controlled file access
      </div>
    );
  }
}
```

**Pros**:
- ✅ Complete control over UI/UX
- ✅ Can enforce all constraints programmatically
- ✅ Consistent design with Phixr
- ✅ Can add collaboration features natively

**Cons**:
- ❌ Massive development effort (rebuild OpenCode UI)
- ❌ Feature parity challenges
- ❌ Maintenance burden
- ❌ Potential performance issues

**Implementation Complexity**: High (3-6 months for feature parity)

### Option 3: Hybrid Approach (Balanced)

**Implementation Strategy**:
```html
<div class="vibe-room">
  <!-- Phixr-controlled sections -->
  <div class="phixr-header">Issue Context & Participants</div>
  <div class="phixr-sidebar">File Browser & Chat</div>
  
  <!-- Constrained OpenCode iframe -->
  <iframe src="/proxy/opencode/session/{id}" class="constrained-iframe">
  </iframe>
  
  <!-- Phixr overlay controls -->
  <div class="phixr-overlay">
    <button>Save Changes</button>
    <button>Request Review</button>
  </div>
</div>
```

**Proxy Implementation**:
```python
@app.get("/proxy/opencode/session/{session_id}")
async def proxy_opencode_session(session_id: str, request: Request):
    # Validate user permissions
    # Add constraint headers
    # Proxy to OpenCode with modifications
    pass
```

**Pros**:
- ✅ Balances control with development effort
- ✅ Can override specific OpenCode behaviors
- ✅ Maintains OpenCode's core functionality
- ✅ Extensible for future features

**Cons**:
- ⚠️ Complex proxy implementation
- ⚠️ Potential performance overhead
- ⚠️ Requires deep OpenCode API knowledge

---

## Recommended Implementation Strategy

### Phase 1: Enhanced Iframe (Immediate - 1-2 weeks)

**Focus**: Improve current iframe implementation with better constraints

**Implementation**:
1. **URL Parameter Constraints**:
   ```javascript
   // In iframe src
   `http://localhost:4096/session/${sessionId}?phixr=true&user=${userId}&room=${roomId}`
   ```

2. **OpenCode UI Modifications** (if possible):
   - Check for `phixr=true` parameter
   - Hide/disable session creation controls
   - Show Phixr-specific branding
   - Restrict navigation

3. **Phixr Overlay Controls**:
   - Session management buttons
   - Participant list
   - Issue context display
   - Save/submit actions

### Phase 2: Proxy Layer (Medium-term - 2-4 weeks)

**Focus**: Add API proxying for enhanced control

**Implementation**:
1. **API Proxy Routes**:
   ```python
   @app.api_route("/proxy/opencode/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
   async def proxy_opencode_request(path: str, request: Request):
       # Validate user permissions
       # Modify request/response as needed
       # Add constraint headers
       response = await proxy_to_opencode(path, request)
       return response
   ```

2. **Constraint Enforcement**:
   - Block session creation requests
   - Validate file access permissions
   - Add audit logging
   - Enforce read-only modes for certain users

### Phase 3: Custom Components (Long-term - 3-6 months)

**Focus**: Replace iframe with custom components where needed

**Implementation**:
1. **Terminal Component**: Custom web terminal with OpenCode backend
2. **File Browser**: Controlled file access with permissions
3. **Editor Integration**: Monaco editor with collaborative features
4. **Gradual Migration**: Replace iframe sections incrementally

---

## Technical Deep Dive: OpenCode UI Manipulation

### URL Parameter Approach

**OpenCode's Current URL Structure**:
```
http://localhost:4096/session/{session_id}
```

**Proposed Phixr Parameters**:
```
http://localhost:4096/session/{session_id}?phixr=true&user_id={user}&room_id={room}&permissions=edit
```

**OpenCode Modifications Needed**:
```javascript
// In OpenCode's web UI
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('phixr') === 'true') {
    // Hide session management UI
    document.querySelector('.new-session-button').style.display = 'none';
    
    // Add Phixr branding
    document.title = `Phixr Vibe Coding - ${session.title}`;
    
    // Restrict certain actions
    if (urlParams.get('permissions') === 'read-only') {
        disableEditing();
    }
}
```

### API Proxying Strategy

**Request Interception**:
```python
async def proxy_opencode_request(path: str, request: Request, user_id: str, room_id: str):
    # Validate user has access to room
    room = await get_vibe_room(room_id)
    if user_id not in room.participants:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Block certain operations
    if path.startswith('/session') and request.method == 'POST':
        # Block new session creation
        raise HTTPException(status_code=403, detail="Session creation not allowed")
    
    # Add user context headers
    headers = dict(request.headers)
    headers['X-Phixr-User'] = user_id
    headers['X-Phixr-Room'] = room_id
    
    # Proxy the request
    return await forward_to_opencode(path, request, headers)
```

### Session Isolation Strategy

**Per-User Sessions** (Recommended):
```
User A in Vibe Room 123:
- OpenCode Session: ses_abc123_userA
- Project: /tmp/phixr/room_123/user_A

User B in Vibe Room 123:
- OpenCode Session: ses_abc123_userB  
- Project: /tmp/phixr/room_123/user_B
```

**Shared Session** (Alternative):
```
Both users in same OpenCode session:
- OpenCode Session: ses_abc123
- Phixr manages permissions
- More complex conflict resolution
```

---

## Security Considerations

### Authentication & Authorization
- **Session Tokens**: Validate all OpenCode API calls
- **User Context**: Pass user identity to OpenCode
- **Permission Levels**: Read-only vs edit vs admin modes

### Data Isolation
- **Project Separation**: Each user gets isolated workspace
- **File Access Control**: Prevent access to other users' files
- **Session Cleanup**: Automatic cleanup when users leave

### Network Security
- **HTTPS Only**: Require encrypted connections
- **CORS Policies**: Restrict cross-origin access
- **Request Validation**: Validate all proxied requests

---

## Performance Considerations

### Iframe Approach
- **Pros**: Native OpenCode performance
- **Cons**: Potential layout thrashing, iframe overhead

### Proxy Approach  
- **Pros**: Can optimize requests, add caching
- **Cons**: Additional latency, complexity

### Custom UI Approach
- **Pros**: Optimized for collaboration features
- **Cons**: Potential performance gaps vs native OpenCode

---

## Migration Strategy

### From Single-User to Multi-User

1. **Phase 1**: Add user identification to iframe URLs
2. **Phase 2**: Implement basic permission checks
3. **Phase 3**: Add proxy layer for API control
4. **Phase 4**: Replace iframe sections with custom components

### Backward Compatibility

- **Single-user sessions**: Continue to work unchanged
- **Existing vibe rooms**: Migrate to multi-user format
- **API compatibility**: Maintain OpenCode API compatibility

---

## Implementation Plan Summary

### Immediate (Next 1-2 weeks)
- ✅ Fix `/ai-plan` command (COMPLETED)
- ✅ Add URL parameters for basic constraints
- ✅ Implement Phixr overlay controls

### Short-term (1-2 months)  
- ✅ Add API proxying for request validation
- ✅ Implement session token authentication
- ✅ Add participant management UI

### Medium-term (3-6 months)
- ✅ Custom terminal component
- ✅ Collaborative file browser
- ✅ Real-time cursor sharing

### Long-term (6+ months)
- ✅ Full custom editor with collaboration features
- ✅ Advanced conflict resolution
- ✅ Integration with external collaboration tools

---

## Conclusion

**Recommended Approach**: Start with **Enhanced Iframe** (Option 1) for immediate multi-user support, then evolve to **Hybrid Approach** (Option 3) for advanced features.

**Key Benefits**:
- **Incremental Development**: Can start simple and add complexity
- **User Experience**: Maintains familiar OpenCode interface
- **Flexibility**: Can enhance constraints over time
- **Risk Mitigation**: Lower risk than full custom UI rebuild

**Success Metrics**:
- Users cannot accidentally create new sessions
- All file operations are logged and auditable  
- Session isolation prevents data leakage
- Performance remains comparable to native OpenCode

This architecture provides a solid foundation for scaling from single-user vibe coding to full multi-user collaborative development.