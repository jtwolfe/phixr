# Phase 2 Developer Quick Reference

**⚠️ READ THIS FIRST**: Before working on Phase 2, read `PHASE_2_STATUS_HONEST.md` for full context.

## What's Working ✅

### 1. ContextInjector
```python
from phixr.bridge.context_injector import ContextInjector
from phixr.config.sandbox_config import SandboxConfig

config = SandboxConfig()
injector = ContextInjector(config)

# Build context message for OpenCode
message = injector.build_context_message(context, exec_config)
prompt = injector.build_system_prompt(exec_config)
```

**Status**: ✅ Production-ready, fully tested

### 2. VibeRoomManager  
```python
from phixr.collaboration.vibe_room_manager import VibeRoomManager
from phixr.models.execution_models import Session

manager = VibeRoomManager()
room = manager.create_room(session, owner_id)
manager.add_message(room.id, "Hello", user_id="123", username="Alice")
```

**Status**: ✅ Production-ready for MVP (in-memory), Phase 3 needs database

### 3. Models
```python
from phixr.models.execution_models import Session, VibeRoom, SessionParticipant
# All working and validated
```

**Status**: ✅ Production-ready

## What's NOT Working ❌

### OpenCodeBridge
```python
# ⚠️ BROKEN - Don't use directly with real OpenCode server
bridge = OpenCodeBridge(config)
session = bridge.start_opencode_session(context)  # Will fail!
```

**Problems**:
1. Async/sync mismatch - calls async methods synchronously
2. API signature mismatch - wrong parameters to `create_session()`
3. No real server testing

**Status**: ❌ Needs fixes before use

## What You Can Do Right Now

### ✅ Safe to Use
- ContextInjector (build context messages)
- VibeRoomManager (manage collaborative sessions)
- Execution models
- Configuration loading

### ❌ NOT Safe to Use
- OpenCodeBridge with real OpenCode server
- End-to-end `/ai-plan` command (will fail)
- Real session creation

## Quick Test Commands

### Run Working Tests
```bash
# VibeRoomManager tests (all pass)
pytest tests/unit/test_vibe_room_manager.py -v

# ContextInjector tests (all pass)  
pytest tests/integration/test_phase2_api_integration.py::TestContextInjectorAPI -v
```

### Test What's Broken
```bash
# This will fail with async error
python -c "
from phixr.bridge.opencode_bridge import OpenCodeBridge
from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import ExecutionMode

bridge = OpenCodeBridge()
context = IssueContext(...)  # You'll need to create this
session = bridge.start_opencode_session(context, ExecutionMode.PLAN)
"
```

## Fixing OpenCodeBridge (TODO)

To make OpenCodeBridge work, you need to:

### Option 1: Make Bridge Async (Recommended)
```python
# In opencode_bridge.py, change:
async def start_opencode_session(self, context, mode, ...):
    opencode_session = await self.client.create_session(...)  # Add await
    await self.client.send_message(...)  # Add await
```

### Option 2: Make Client Sync
```python
# In opencode_client.py, change:
def create_session(self, project_path, title, parent_id):  # Remove async
    response = self.client.post(...)  # Remove await
```

### Option 3: Add Sync Wrapper
```python
# Add sync methods to client that wrap async calls
def create_session_sync(self, *args, **kwargs):
    return asyncio.run(self.create_session(*args, **kwargs))
```

## File Locations

```
phixr/
├── bridge/
│   ├── opencode_bridge.py      # ⚠️ Broken (needs async fix)
│   ├── opencode_client.py      # ⚠️ Not validated
│   └── context_injector.py     # ✅ Working
├── collaboration/
│   └── vibe_room_manager.py    # ✅ Working
├── models/
│   └── execution_models.py     # ✅ Working
└── config/
    └── sandbox_config.py       # ✅ Working
```

## Configuration

### Environment Variables
```bash
# Optional - OpenCode server URL
export PHIXR_SANDBOX_OPENCODE_SERVER_URL=http://localhost:4096

# Required - GitLab
export GITLAB_URL=https://gitlab.example.com
export GITLAB_BOT_TOKEN=your-token
```

### Docker Compose
```bash
# Start OpenCode server (Phase 2 profile)
docker-compose up --profile phase-2

# This starts the server but bridge won't work yet
```

## Next Steps for Developer

1. **Read**: `PHASE_2_STATUS_HONEST.md` for full context
2. **Test**: Run the vibe room manager tests (they work)
3. **Experiment**: Use ContextInjector for message building
4. **Fix**: Implement async/sync fix for OpenCodeBridge (1-2 days)
5. **Test**: Add real integration tests with docker-compose
6. **Deploy**: Once bridge is fixed and tested

## Known Issues

| Issue | Impact | Fix Effort |
|-------|--------|------------|
| Async/sync mismatch | Can't create sessions | 1 day |
| API signature mismatch | Type errors | 1 hour |
| No real server tests | False confidence | 1 day |
| In-memory VibeRooms | Data lost on restart | Phase 3 |
| No monitoring | Hard to debug | 2-3 hours |

## Questions?

- **Architecture questions**? → See `PHASE_2_IMPLEMENTATION.md`
- **Status questions**? → See `PHASE_2_STATUS_HONEST.md`
- **How to fix**? → See "Fixing OpenCodeBridge" above
- **What works now**? → See "What's Working" above

## Summary

- ✅ Foundation is solid
- ✅ Can develop and test components in isolation
- ❌ Integration layer needs fixes
- ⚠️ Not production ready until bridge is fixed
- 💪 Fixing is straightforward (1-2 days)
