"""Collaboration features for Phixr.

Multi-user support, vibe rooms, and shared sessions.
"""

from phixr.collaboration.vibe_room_manager import (
    VibeRoomManager,
    get_vibe_room_manager
)

__all__ = [
    "VibeRoomManager",
    "get_vibe_room_manager",
]
