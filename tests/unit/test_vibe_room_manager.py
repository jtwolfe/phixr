"""Tests for vibe room manager and multi-user foundation."""

import pytest
from datetime import datetime

from phixr.collaboration.vibe_room_manager import VibeRoomManager, get_vibe_room_manager
from phixr.models.execution_models import (
    Session, VibeRoom, SessionMessage, SessionParticipant,
    ExecutionMode, SessionStatus
)


class TestVibeRoomManager:
    """Test vibe room manager functionality."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh vibe room manager."""
        return VibeRoomManager()
    
    @pytest.fixture
    def sample_session(self):
        """Create a sample session."""
        return Session(
            id="sess-abc123",
            issue_id=456,
            repo_url="https://github.com/example/repo.git",
            branch="ai-work/456",
            mode=ExecutionMode.PLAN,
            single_user=True
        )
    
    def test_create_room(self, manager, sample_session):
        """Test creating a vibe room."""
        room = manager.create_room(
            session=sample_session,
            owner_id="user-123",
            room_name="Test Collaboration Room"
        )
        
        assert room.id.startswith("vroom-")
        assert room.session_id == sample_session.id
        assert room.owner_id == "user-123"
        assert room.name == "Test Collaboration Room"
        assert len(room.participants) == 1
        assert "user-123" in room.participants
    
    def test_get_room(self, manager, sample_session):
        """Test retrieving a vibe room."""
        created_room = manager.create_room(sample_session, "user-123")
        
        retrieved_room = manager.get_room(created_room.id)
        
        assert retrieved_room is not None
        assert retrieved_room.id == created_room.id
        assert retrieved_room.owner_id == "user-123"
    
    def test_get_room_by_session(self, manager, sample_session):
        """Test finding vibe room by session ID."""
        room = manager.create_room(sample_session, "user-123")
        
        found_room = manager.get_room_by_session(sample_session.id)
        
        assert found_room is not None
        assert found_room.id == room.id
    
    def test_add_participant(self, manager, sample_session):
        """Test adding participants to a room."""
        room = manager.create_room(sample_session, "user-123")
        
        # Add another participant
        success = manager.add_participant(
            room.id,
            "user-456",
            "Alice Developer",
            role="editor"
        )
        
        assert success == True
        
        room = manager.get_room(room.id)
        assert len(room.participants) == 2
        assert "user-456" in room.participants
        assert room.participants["user-456"].role == "editor"
        assert room.participants["user-456"].username == "Alice Developer"
    
    def test_add_message_user(self, manager, sample_session):
        """Test adding user messages to a room."""
        room = manager.create_room(sample_session, "user-123")
        
        message = manager.add_message(
            room.id,
            "Let's start analyzing the code",
            user_id="user-123",
            username="Bob",
            is_ai=False
        )
        
        assert message is not None
        assert message.content == "Let's start analyzing the code"
        assert message.user_id == "user-123"
        assert message.username == "Bob"
        assert message.is_ai == False
        
        room = manager.get_room(room.id)
        assert len(room.messages) == 1
        assert room.messages[0].id == message.id
    
    def test_add_message_ai(self, manager, sample_session):
        """Test adding AI messages to a room."""
        room = manager.create_room(sample_session, "user-123")
        
        message = manager.add_message(
            room.id,
            "Here's my analysis of the code...",
            is_ai=True
        )
        
        assert message is not None
        assert message.is_ai == True
        assert message.user_id is None
        assert message.username is None
    
    def test_get_messages(self, manager, sample_session):
        """Test retrieving messages from a room."""
        room = manager.create_room(sample_session, "user-123")
        
        # Add multiple messages
        for i in range(5):
            manager.add_message(
                room.id,
                f"Message {i}",
                user_id="user-123",
                username="Bob"
            )
        
        messages = manager.get_messages(room.id)
        assert len(messages) == 5
        assert messages[0].content == "Message 0"
        assert messages[4].content == "Message 4"
        
        # Test with limit
        recent = manager.get_messages(room.id, limit=3)
        assert len(recent) == 3
        assert recent[0].content == "Message 2"  # Last 3 messages
    
    def test_generate_sharing_token(self, manager, sample_session):
        """Test generating a sharing token."""
        room = manager.create_room(sample_session, "user-123")
        
        token = manager.generate_sharing_token(room.id)
        
        assert token is not None
        assert token.startswith("token-")
        assert len(token) > 10
        
        # Verify token is stored
        room = manager.get_room(room.id)
        assert room.sharing_token == token
    
    def test_get_room_by_token(self, manager, sample_session):
        """Test finding room by sharing token."""
        room = manager.create_room(sample_session, "user-123")
        token = manager.generate_sharing_token(room.id)
        
        found_room = manager.get_room_by_token(token)
        
        assert found_room is not None
        assert found_room.id == room.id
    
    def test_list_rooms(self, manager):
        """Test listing rooms."""
        sessions = [
            Session(
                id=f"sess-{i}",
                issue_id=i,
                repo_url="https://github.com/example/repo.git",
                branch=f"ai-work/{i}"
            )
            for i in range(3)
        ]
        
        # Create rooms from different owners
        for i, session in enumerate(sessions):
            owner = "user-123" if i < 2 else "user-456"
            manager.create_room(session, owner)
        
        # List all rooms
        all_rooms = manager.list_rooms()
        assert len(all_rooms) == 3
        
        # Filter by owner
        user_123_rooms = manager.list_rooms(owner_id="user-123")
        assert len(user_123_rooms) == 2
        
        user_456_rooms = manager.list_rooms(owner_id="user-456")
        assert len(user_456_rooms) == 1
    
    def test_archive_room(self, manager, sample_session):
        """Test archiving a room."""
        room = manager.create_room(sample_session, "user-123")
        
        success = manager.archive_room(room.id)
        
        assert success == True
        
        # Verify room is archived
        room = manager.get_room(room.id)
        assert room.archived == True
        
        # Archived rooms should not appear in active list
        active = manager.list_rooms(archived=False)
        assert len(active) == 0
        
        archived = manager.list_rooms(archived=True)
        assert len(archived) == 1
    
    def test_delete_room(self, manager, sample_session):
        """Test deleting a room."""
        room = manager.create_room(sample_session, "user-123")
        room_id = room.id
        
        success = manager.delete_room(room_id)
        
        assert success == True
        
        # Verify room is deleted
        retrieved = manager.get_room(room_id)
        assert retrieved is None
    
    def test_get_stats(self, manager):
        """Test getting vibe room statistics."""
        sessions = [
            Session(
                id=f"sess-{i}",
                issue_id=i,
                repo_url="https://github.com/example/repo.git",
                branch=f"ai-work/{i}"
            )
            for i in range(3)
        ]
        
        # Create rooms and add messages
        for i, session in enumerate(sessions):
            room = manager.create_room(session, "user-123")
            
            # Add messages
            for j in range(i + 1):  # Room 0: 1 msg, Room 1: 2 msgs, Room 2: 3 msgs
                manager.add_message(room.id, f"Message {j}")
            
            # Archive the last room
            if i == 2:
                manager.archive_room(room.id)
        
        stats = manager.get_stats()
        
        assert stats["total_rooms"] == 3
        assert stats["active_rooms"] == 2
        assert stats["archived_rooms"] == 1
        assert stats["total_messages"] == 6  # 1 + 2 + 3
    
    def test_message_attribution(self, manager, sample_session):
        """Test that messages maintain proper user attribution."""
        room = manager.create_room(sample_session, "user-alice")
        manager.add_participant(room.id, "user-bob", "Bob")
        
        # Add messages from different users
        msg1 = manager.add_message(
            room.id,
            "Alice: Let's fix the bug",
            user_id="user-alice",
            username="Alice"
        )
        
        msg2 = manager.add_message(
            room.id,
            "Bob: I think I found the issue",
            user_id="user-bob",
            username="Bob"
        )
        
        msg3 = manager.add_message(
            room.id,
            "Here's my analysis...",
            is_ai=True
        )
        
        messages = manager.get_messages(room.id)
        
        # Verify attribution
        assert messages[0].user_id == "user-alice"
        assert messages[0].username == "Alice"
        assert messages[1].user_id == "user-bob"
        assert messages[1].username == "Bob"
        assert messages[2].is_ai == True
        assert messages[2].user_id is None
    
    def test_global_manager_singleton(self):
        """Test that global manager is a singleton."""
        manager1 = get_vibe_room_manager()
        manager2 = get_vibe_room_manager()
        
        # Should be the same instance
        assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
