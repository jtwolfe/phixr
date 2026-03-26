"""Manager for multi-user collaborative vibe rooms.

This module provides the foundation for Phase 3+ multi-user collaboration features.
Vibe rooms allow multiple users to share and collaborate on OpenCode sessions with
proper access control and message attribution.
"""

import logging
import uuid
from typing import Dict, Optional, List
from datetime import datetime

from phixr.models.execution_models import (
    VibeRoom, SessionParticipant, SessionMessage, Session
)

logger = logging.getLogger(__name__)


class VibeRoomManager:
    """Manages collaborative vibe rooms for multi-user sessions.
    
    In Phase 2 (current), this is a foundation with minimal functionality.
    Phase 3+ will add:
    - Real-time WebSocket-based collaboration
    - Persistent vibe room storage (Redis/PostgreSQL)
    - Permission-based access control
    - Session sharing via tokens
    """
    
    def __init__(self):
        """Initialize vibe room manager."""
        self.rooms: Dict[str, VibeRoom] = {}
        logger.info("Vibe room manager initialized")
    
    def create_room(self, session: Session, owner_id: str, 
                   room_name: Optional[str] = None) -> VibeRoom:
        """Create a new vibe room for a session.
        
        In Phase 2, only the owner can use the room (single-user).
        Phase 3+ will enable adding other participants.
        
        Args:
            session: OpenCode session to associate with room
            owner_id: User ID of room owner
            room_name: Optional custom room name
            
        Returns:
            Created VibeRoom
        """
        room_id = f"vroom-{uuid.uuid4().hex[:8]}"
        room_name = room_name or f"Session {session.id}"
        
        room = VibeRoom(
            id=room_id,
            name=room_name,
            description=f"Collaborative session for issue {session.issue_id}",
            session_id=session.id,
            owner_id=owner_id,
            participants={
                owner_id: SessionParticipant(
                    user_id=owner_id,
                    username=f"user-{owner_id[:8]}",  # Placeholder
                    role="owner"
                )
            }
        )
        
        self.rooms[room_id] = room
        logger.info(f"Created vibe room: {room_id} (session: {session.id})")
        
        return room
    
    def get_room(self, room_id: str) -> Optional[VibeRoom]:
        """Get a vibe room by ID.
        
        Args:
            room_id: Room ID
            
        Returns:
            VibeRoom or None if not found
        """
        return self.rooms.get(room_id)
    
    def get_room_by_session(self, session_id: str) -> Optional[VibeRoom]:
        """Get vibe room associated with a session.
        
        Args:
            session_id: OpenCode session ID
            
        Returns:
            VibeRoom or None if not found
        """
        for room in self.rooms.values():
            if room.session_id == session_id:
                return room
        return None
    
    def add_participant(self, room_id: str, user_id: str, username: str,
                       role: str = "viewer") -> bool:
        """Add a participant to a vibe room.
        
        In Phase 2, this is a no-op (only owner can participate).
        Phase 3+ will implement full multi-user support.
        
        Args:
            room_id: Room ID
            user_id: User ID to add
            username: User's display name
            role: User role (owner, editor, viewer)
            
        Returns:
            True if participant was added, False otherwise
        """
        room = self.get_room(room_id)
        if not room:
            logger.warning(f"Room not found: {room_id}")
            return False
        
        if user_id in room.participants:
            logger.debug(f"User {user_id} already in room {room_id}")
            return True
        
        room.participants[user_id] = SessionParticipant(
            user_id=user_id,
            username=username,
            role=role,
            joined_at=datetime.utcnow()
        )
        
        room.updated_at = datetime.utcnow()
        logger.info(f"Added participant {user_id} to room {room_id} (role: {role})")
        
        return True
    
    def add_message(self, room_id: str, content: str, user_id: Optional[str] = None,
                   username: Optional[str] = None, is_ai: bool = False) -> Optional[SessionMessage]:
        """Add a message to a vibe room with user attribution.
        
        Args:
            room_id: Room ID
            content: Message content
            user_id: User ID (None for AI messages)
            username: User display name (None for AI)
            is_ai: Whether this is an AI-generated message
            
        Returns:
            Created SessionMessage or None if room not found
        """
        room = self.get_room(room_id)
        if not room:
            logger.warning(f"Room not found: {room_id}")
            return None
        
        # Get role from participant if exists
        participant_role = None
        if user_id and user_id in room.participants:
            participant_role = room.participants[user_id].role
        
        message = SessionMessage(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            username=username,
            role=participant_role,
            content=content,
            is_ai=is_ai
        )
        
        room.messages.append(message)
        room.updated_at = datetime.utcnow()
        
        # Update participant's last activity
        if user_id and user_id in room.participants:
            room.participants[user_id].last_activity = datetime.utcnow()
        
        return message
    
    def get_messages(self, room_id: str, limit: Optional[int] = None) -> List[SessionMessage]:
        """Get messages from a vibe room.
        
        Args:
            room_id: Room ID
            limit: Optional limit on number of messages to return
            
        Returns:
            List of messages
        """
        room = self.get_room(room_id)
        if not room:
            return []
        
        messages = room.messages
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def generate_sharing_token(self, room_id: str) -> Optional[str]:
        """Generate a sharing token for a vibe room.
        
        In Phase 3+, this token can be used to grant access to other users.
        Phase 2 does not use this feature.
        
        Args:
            room_id: Room ID
            
        Returns:
            Sharing token or None if room not found
        """
        room = self.get_room(room_id)
        if not room:
            return None
        
        room.sharing_token = f"token-{uuid.uuid4().hex[:16]}"
        room.updated_at = datetime.utcnow()
        
        logger.info(f"Generated sharing token for room {room_id}")
        return room.sharing_token
    
    def get_room_by_token(self, token: str) -> Optional[VibeRoom]:
        """Get vibe room by sharing token.
        
        Phase 3+ feature: Not implemented in Phase 2.
        
        Args:
            token: Sharing token
            
        Returns:
            VibeRoom or None if not found
        """
        for room in self.rooms.values():
            if room.sharing_token == token:
                return room
        return None
    
    def list_rooms(self, owner_id: Optional[str] = None,
                  archived: bool = False) -> List[VibeRoom]:
        """List vibe rooms, optionally filtered.
        
        Args:
            owner_id: Optional filter by owner
            archived: Include archived rooms
            
        Returns:
            List of VibeRoom objects
        """
        rooms = [r for r in self.rooms.values() if r.archived == archived]
        
        if owner_id:
            rooms = [r for r in rooms if r.owner_id == owner_id]
        
        return rooms
    
    def archive_room(self, room_id: str) -> bool:
        """Archive a vibe room (soft delete).
        
        Args:
            room_id: Room ID
            
        Returns:
            True if archived, False if room not found
        """
        room = self.get_room(room_id)
        if not room:
            return False
        
        room.archived = True
        room.updated_at = datetime.utcnow()
        logger.info(f"Archived vibe room: {room_id}")
        
        return True
    
    def delete_room(self, room_id: str) -> bool:
        """Delete a vibe room permanently.
        
        Args:
            room_id: Room ID
            
        Returns:
            True if deleted, False if room not found
        """
        if room_id not in self.rooms:
            return False
        
        del self.rooms[room_id]
        logger.info(f"Deleted vibe room: {room_id}")
        
        return True
    
    def get_stats(self) -> Dict:
        """Get vibe room statistics.
        
        Returns:
            Dictionary with stats
        """
        active_rooms = len([r for r in self.rooms.values() if not r.archived])
        total_messages = sum(len(r.messages) for r in self.rooms.values())
        
        return {
            "total_rooms": len(self.rooms),
            "active_rooms": active_rooms,
            "archived_rooms": len(self.rooms) - active_rooms,
            "total_messages": total_messages,
            "avg_participants": sum(len(r.participants) for r in self.rooms.values()) / len(self.rooms) if self.rooms else 0,
        }


# Global vibe room manager instance (will be moved to proper DI in Phase 3)
_vibe_room_manager: Optional[VibeRoomManager] = None


def get_vibe_room_manager() -> VibeRoomManager:
    """Get or create global vibe room manager."""
    global _vibe_room_manager
    if _vibe_room_manager is None:
        _vibe_room_manager = VibeRoomManager()
    return _vibe_room_manager
