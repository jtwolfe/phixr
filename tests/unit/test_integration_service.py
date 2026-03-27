"""Unit tests for OpenCode integration service."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from phixr.integration.opencode_integration_service import OpenCodeIntegrationService
from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import ExecutionMode, SessionStatus


def _make_context(**overrides):
    defaults = dict(
        issue_id=42,
        project_id=1,
        title="Fix the login bug",
        description="Login crashes when password is empty.",
        url="http://gitlab.local/project/-/issues/42",
        author="alice",
        assignees=["phixr-bot"],
        labels=["bug"],
        repo_url="http://gitlab.local/project.git",
        repo_name="my/project",
        branch="main",
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    defaults.update(overrides)
    return IssueContext(**defaults)


def _make_service(mock_client=None):
    config = MagicMock()
    config.opencode_server_url = "http://test:4096"
    service = OpenCodeIntegrationService(config=config, base_url="http://phixr:8000")
    if mock_client:
        service.client = mock_client
    return service


def _mock_client():
    client = AsyncMock()
    client.health_check.return_value = True
    client.create_session.return_value = {
        "id": "ses_test123",
        "slug": "test-slug",
        "title": "test",
    }
    client.send_prompt.return_value = None
    client.get_messages.return_value = [
        {
            "info": {"role": "user", "id": "msg_u1", "sessionID": "ses_test123"},
            "parts": [{"type": "text", "text": "Fix the bug"}],
        },
        {
            "info": {"role": "assistant", "id": "msg_a1", "sessionID": "ses_test123"},
            "parts": [{"type": "text", "text": "Here is the plan:\n1. Find the bug\n2. Fix it"}],
        },
    ]
    client.get_session_status.return_value = {}
    client.abort_session.return_value = True
    client.delete_session.return_value = True
    client.list_permissions.return_value = []
    client.close.return_value = None
    return client


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_delegates_to_client(self):
        client = _mock_client()
        service = _make_service(client)
        assert await service.health_check() is True
        client.health_check.assert_awaited_once()


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_creates_opencode_session_and_sends_prompt(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(
            context=context,
            execution_mode=ExecutionMode.PLAN,
            timeout_minutes=15,
            owner_id="alice",
        )

        # Session created on OpenCode
        client.create_session.assert_awaited_once()
        title_arg = client.create_session.call_args[1]["title"]
        assert "42" in title_arg
        assert "plan" in title_arg.lower()

        # Prompt sent
        client.send_prompt.assert_awaited_once()
        call_kwargs = client.send_prompt.call_args[1]
        assert call_kwargs["session_id"] == "ses_test123"
        assert "plan" in call_kwargs["agent"]
        assert call_kwargs["system"] is not None

        # Phixr session tracked
        assert session.id.startswith("sess-42-")
        assert session.status == SessionStatus.RUNNING
        assert session.mode == ExecutionMode.PLAN
        assert service.opencode_session_ids[session.id] == "ses_test123"

    @pytest.mark.asyncio
    async def test_creates_vibe_room(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, owner_id="alice")

        room = service.get_vibe_room_by_session(session.id)
        assert room is not None

    @pytest.mark.asyncio
    async def test_build_mode_uses_build_agent(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        await service.create_session(
            context=context, execution_mode=ExecutionMode.BUILD
        )

        call_kwargs = client.send_prompt.call_args[1]
        assert call_kwargs["agent"] == "build"


class TestMonitorSession:
    @pytest.mark.asyncio
    async def test_completes_when_idle(self):
        client = _mock_client()

        # Simulate SSE events: message.updated then idle
        async def fake_events():
            yield {"type": "message.part.updated", "properties": {
                "sessionID": "ses_test123",
                "part": {"type": "text"},
            }}
            yield {"type": "message.updated", "properties": {
                "sessionID": "ses_test123",
            }}

        client.subscribe_events = fake_events
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context)

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        assert session.status == SessionStatus.COMPLETED
        assert session.ended_at is not None
        # Should post result to GitLab
        gitlab.add_issue_comment.assert_called()

    @pytest.mark.asyncio
    async def test_auto_approves_permissions(self):
        client = _mock_client()

        async def fake_events():
            yield {"type": "permission.asked", "properties": {
                "sessionID": "ses_test123",
                "id": "perm_99",
                "permission": "file_write",
            }}
            yield {"type": "message.updated", "properties": {
                "sessionID": "ses_test123",
            }}

        client.subscribe_events = fake_events
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context)

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        client.reply_permission.assert_awaited_with("perm_99", "always")

    @pytest.mark.asyncio
    async def test_timeout_aborts_session(self):
        client = _mock_client()

        async def slow_events():
            await asyncio.sleep(100)
            yield {"type": "never"}

        client.subscribe_events = slow_events
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(
            context=context, timeout_minutes=0  # immediate timeout
        )
        # Override timeout to 1 second for test
        session.timeout_minutes = 0
        service.sessions[session.id] = session

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        assert session.status == SessionStatus.TIMEOUT
        client.abort_session.assert_awaited()
        gitlab.add_issue_comment.assert_called()

    @pytest.mark.asyncio
    async def test_filters_events_by_session(self):
        client = _mock_client()
        approved_perms = []

        async def fake_events():
            # Event for a different session — should be ignored
            yield {"type": "permission.asked", "properties": {
                "sessionID": "ses_OTHER",
                "id": "perm_other",
            }}
            # Event for our session
            yield {"type": "message.updated", "properties": {
                "sessionID": "ses_test123",
            }}

        client.subscribe_events = fake_events
        original_reply = client.reply_permission
        async def track_reply(perm_id, reply):
            approved_perms.append(perm_id)
            return True
        client.reply_permission = AsyncMock(side_effect=track_reply)

        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context)

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        # Should NOT have approved the other session's permission
        assert "perm_other" not in approved_perms


class TestStopSession:
    @pytest.mark.asyncio
    async def test_stops_running_session(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context)

        result = await service.stop_session(session.id)
        assert result is True
        assert session.status == SessionStatus.STOPPED
        client.abort_session.assert_awaited_with("ses_test123")

    @pytest.mark.asyncio
    async def test_stop_unknown_session(self):
        service = _make_service(_mock_client())
        result = await service.stop_session("nonexistent")
        assert result is False


class TestSessionQueries:
    @pytest.mark.asyncio
    async def test_get_session(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context)

        found = await service.get_session(session.id)
        assert found is not None
        assert found.id == session.id

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        await service.create_session(context=context)

        sessions = await service.list_sessions()
        assert len(sessions) == 1

    @pytest.mark.asyncio
    async def test_list_sessions_with_filter(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        await service.create_session(context=context)

        running = await service.list_sessions(status_filter=SessionStatus.RUNNING)
        assert len(running) == 1
        completed = await service.list_sessions(status_filter=SessionStatus.COMPLETED)
        assert len(completed) == 0


class TestPromptBuilding:
    def test_build_prompt_plan_mode(self):
        context = _make_context()
        prompt = OpenCodeIntegrationService._build_prompt(context, ExecutionMode.PLAN)
        assert "42" in prompt
        assert "Fix the login bug" in prompt
        assert "plan" in prompt.lower()

    def test_build_prompt_build_mode(self):
        context = _make_context()
        prompt = OpenCodeIntegrationService._build_prompt(context, ExecutionMode.BUILD)
        assert "Implement" in prompt

    def test_build_prompt_review_mode(self):
        context = _make_context()
        prompt = OpenCodeIntegrationService._build_prompt(context, ExecutionMode.REVIEW)
        assert "Review" in prompt

    def test_build_system_instructions(self):
        context = _make_context()
        system = OpenCodeIntegrationService._build_system_instructions(
            context, ExecutionMode.PLAN
        )
        assert "Phixr" in system
        assert "PLAN" in system
        assert "#42" in system


class TestExtractAssistantText:
    def test_extracts_last_assistant_message(self):
        messages = [
            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "Hello"}]},
            {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "World"}]},
        ]
        text = OpenCodeIntegrationService._extract_assistant_text(messages)
        assert text == "World"

    def test_skips_tool_parts(self):
        messages = [
            {"info": {"role": "assistant"}, "parts": [
                {"type": "tool", "tool": "read_file"},
                {"type": "text", "text": "Result"},
            ]},
        ]
        text = OpenCodeIntegrationService._extract_assistant_text(messages)
        assert text == "Result"

    def test_no_assistant_message(self):
        messages = [
            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "Hello"}]},
        ]
        text = OpenCodeIntegrationService._extract_assistant_text(messages)
        assert "No text output" in text

    def test_multiple_text_parts(self):
        messages = [
            {"info": {"role": "assistant"}, "parts": [
                {"type": "text", "text": "Part 1"},
                {"type": "text", "text": "Part 2"},
            ]},
        ]
        text = OpenCodeIntegrationService._extract_assistant_text(messages)
        assert "Part 1" in text
        assert "Part 2" in text


class TestVibeRooms:
    @pytest.mark.asyncio
    async def test_vibe_room_url(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context, owner_id="alice")

        url = service.create_vibe_session_url(session.id)
        assert url is not None
        assert "/vibe/" in url

    @pytest.mark.asyncio
    async def test_no_vibe_room_for_unknown_session(self):
        service = _make_service(_mock_client())
        url = service.create_vibe_session_url("nonexistent")
        assert url is None
