"""Collaboration features for Phixr.

Multi-user support, vibe rooms, and shared sessions.
Phase 2: Foundation and models
Phase 3+: Full real-time collaboration
"""

from phixr.collaboration.vibe_room_manager import (
    VibeRoomManager,
    get_vibe_room_manager
)

__all__ = [
    "VibeRoomManager",
    "get_vibe_room_manager",
]
