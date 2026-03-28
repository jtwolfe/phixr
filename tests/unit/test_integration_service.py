"""Unit tests for OpenCode integration service."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from phixr.integration.opencode_integration_service import OpenCodeIntegrationService
from phixr.models.issue_context import IssueContext
from phixr.models.execution_models import SessionStatus


def _make_context(**overrides):
    defaults = dict(
        issue_id=42,
        project_id=1,
        title="Fix the login bug",
        description="Login crashes when password is empty.",
        url="http://gitlab.local/project/-/issues/42",
        author="alice",
        assignees=["phixr"],
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
    config.opencode_public_url = ""
    config.git_provider_token = ""
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


class TestIssueSessionMapping:
    @pytest.mark.asyncio
    async def test_no_active_session_initially(self):
        service = _make_service(_mock_client())
        assert service.get_active_session_for_issue(1, 42) is None

    @pytest.mark.asyncio
    async def test_active_session_after_create(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, project_id=1)
        active = service.get_active_session_for_issue(1, 42)
        assert active is not None
        assert active.id == session.id

    @pytest.mark.asyncio
    async def test_one_session_per_issue_enforced(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        await service.create_session(context=context, project_id=1)

        with pytest.raises(ValueError, match="already active"):
            await service.create_session(context=context, project_id=1)

    @pytest.mark.asyncio
    async def test_can_create_after_stop(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, project_id=1)
        await service.stop_session(session.id)

        # Should be able to create a new one now
        session2 = await service.create_session(context=context, project_id=1)
        assert session2.id != session.id


class TestCreateSession:
    @pytest.mark.asyncio
    async def test_creates_opencode_session_and_sends_prompt(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, project_id=1)

        # Session created on OpenCode
        client.create_session.assert_awaited_once()
        title_arg = client.create_session.call_args[1]["title"]
        assert "42" in title_arg

        # Prompt sent
        client.send_prompt.assert_awaited_once()
        call_kwargs = client.send_prompt.call_args[1]
        assert call_kwargs["session_id"] == "ses_test123"
        assert call_kwargs["system"] is not None

        # Phixr session tracked
        assert session.id.startswith("sess-42-")
        assert session.status == SessionStatus.RUNNING
        assert service.opencode_session_ids[session.id] == "ses_test123"

    @pytest.mark.asyncio
    async def test_creates_vibe_room(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, project_id=1, owner_id="alice")

        room = service.get_vibe_room_by_session(session.id)
        assert room is not None

    @pytest.mark.asyncio
    async def test_stores_session_slug(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, project_id=1)
        assert service.opencode_session_slugs[session.id] == "test-slug"


class TestSendFollowup:
    @pytest.mark.asyncio
    async def test_sends_message_to_active_session(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, project_id=1)
        client.send_prompt.reset_mock()

        result = await service.send_followup(session.id, "please also add tests", author="bob")

        assert result is True
        client.send_prompt.assert_awaited_once()
        call_kwargs = client.send_prompt.call_args[1]
        assert "bob" in call_kwargs["message"]
        assert "please also add tests" in call_kwargs["message"]

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_session(self):
        service = _make_service(_mock_client())
        result = await service.send_followup("nonexistent", "hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_stopped_session(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()

        session = await service.create_session(context=context, project_id=1)
        await service.stop_session(session.id)

        result = await service.send_followup(session.id, "hello")
        assert result is False


class TestMonitorSession:
    @pytest.mark.asyncio
    async def test_completes_when_idle(self):
        client = _mock_client()

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
        session = await service.create_session(context=context, project_id=1)

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        assert session.status == SessionStatus.COMPLETED
        assert session.ended_at is not None
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
        session = await service.create_session(context=context, project_id=1)

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
            context=context, project_id=1, timeout_minutes=0
        )
        session.timeout_minutes = 0
        service.sessions[session.id] = session

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        assert session.status == SessionStatus.TIMEOUT
        client.abort_session.assert_awaited()
        gitlab.add_issue_comment.assert_called()

    @pytest.mark.asyncio
    async def test_cleans_up_issue_mapping_on_complete(self):
        client = _mock_client()

        async def fake_events():
            yield {"type": "message.updated", "properties": {
                "sessionID": "ses_test123",
            }}

        client.subscribe_events = fake_events
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context, project_id=1)

        assert service.get_active_session_for_issue(1, 42) is not None

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        # Issue mapping should be cleaned up
        assert service.store.get_issue_session(1, 42) is None

    @pytest.mark.asyncio
    async def test_filters_events_by_session(self):
        client = _mock_client()
        approved_perms = []

        async def fake_events():
            yield {"type": "permission.asked", "properties": {
                "sessionID": "ses_OTHER",
                "id": "perm_other",
            }}
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
        session = await service.create_session(context=context, project_id=1)

        gitlab = MagicMock()
        await service.monitor_session(session.id, gitlab, 1, 42)

        assert "perm_other" not in approved_perms


class TestStopSession:
    @pytest.mark.asyncio
    async def test_stops_running_session(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context, project_id=1)

        result = await service.stop_session(session.id)
        assert result is True
        assert session.status == SessionStatus.STOPPED
        client.abort_session.assert_awaited_with("ses_test123")

    @pytest.mark.asyncio
    async def test_stop_unknown_session(self):
        service = _make_service(_mock_client())
        result = await service.stop_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_cleans_issue_mapping(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context, project_id=1)

        assert service.store.get_issue_session(1, 42) == session.id
        await service.stop_session(session.id)
        assert service.store.get_issue_session(1, 42) is None


class TestSessionQueries:
    @pytest.mark.asyncio
    async def test_get_session(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context, project_id=1)

        found = await service.get_session(session.id)
        assert found is not None
        assert found.id == session.id

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        await service.create_session(context=context, project_id=1)

        sessions = await service.list_sessions()
        assert len(sessions) == 1

    @pytest.mark.asyncio
    async def test_list_sessions_with_filter(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        await service.create_session(context=context, project_id=1)

        running = await service.list_sessions(status_filter=SessionStatus.RUNNING)
        assert len(running) == 1
        completed = await service.list_sessions(status_filter=SessionStatus.COMPLETED)
        assert len(completed) == 0


class TestPromptBuilding:
    def test_build_initial_prompt(self):
        context = _make_context()
        prompt = OpenCodeIntegrationService._build_initial_prompt(context)
        assert "42" in prompt
        assert "Fix the login bug" in prompt
        assert "Your Task" in prompt

    def test_build_system_instructions(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        system = service._build_system_instructions(context)
        assert "Phixr" in system
        assert "#42" in system
        assert "persistent session" in system

    def test_build_system_instructions_includes_clone(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context(repo_url="http://gitlab.local/project.git")
        system = service._build_system_instructions(context)
        assert "git clone" in system
        assert "/tmp/workspace" in system


class TestExtractAssistantText:
    def test_extracts_all_assistant_messages(self):
        messages = [
            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "Hello"}]},
            {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "First response"}]},
            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "Continue"}]},
            {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "Second response"}]},
        ]
        text = OpenCodeIntegrationService._extract_assistant_text(messages)
        assert "First response" in text
        assert "Second response" in text

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

    def test_multiple_text_parts_in_one_message(self):
        messages = [
            {"info": {"role": "assistant"}, "parts": [
                {"type": "text", "text": "Part 1"},
                {"type": "text", "text": "Part 2"},
            ]},
        ]
        text = OpenCodeIntegrationService._extract_assistant_text(messages)
        assert "Part 1" in text
        assert "Part 2" in text

    def test_single_assistant_message(self):
        messages = [
            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "Hi"}]},
            {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "World"}]},
        ]
        text = OpenCodeIntegrationService._extract_assistant_text(messages)
        assert text == "World"


class TestOpenCodeSessionUrl:
    @pytest.mark.asyncio
    async def test_builds_correct_url(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context, project_id=1)

        url = service.get_opencode_session_url(session.id)
        assert url is not None
        # Should be /{base64url("/")}/session/{oc_session_id}
        assert "/Lw/session/ses_test123" in url
        assert url.startswith("http://test:4096/")

    def test_returns_none_for_unknown_session(self):
        service = _make_service(_mock_client())
        url = service.get_opencode_session_url("nonexistent")
        assert url is None


class TestVibeRooms:
    @pytest.mark.asyncio
    async def test_vibe_room_url(self):
        client = _mock_client()
        service = _make_service(client)
        context = _make_context()
        session = await service.create_session(context=context, project_id=1, owner_id="alice")

        url = service.create_vibe_session_url(session.id)
        assert url is not None
        assert "/vibe/" in url

    @pytest.mark.asyncio
    async def test_no_vibe_room_for_unknown_session(self):
        service = _make_service(_mock_client())
        url = service.create_vibe_session_url("nonexistent")
        assert url is None
