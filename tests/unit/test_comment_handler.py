"""Unit tests for the comment handler."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from phixr.handlers.comment_handler import CommentHandler, AssignmentHandler
from phixr.models.execution_models import SessionStatus


def _make_webhook(note: str, author: str = "alice", project_id: int = 1, issue_iid: int = 42):
    return {
        "object_kind": "note",
        "user": {"username": author},
        "project": {"id": project_id},
        "issue": {"iid": issue_iid},
        "object_attributes": {
            "id": 100,
            "note": note,
            "noteable_type": "Issue",
            "iid": issue_iid,
        },
    }


def _make_handler(integration=None):
    gitlab = MagicMock()
    assignment = MagicMock(spec=AssignmentHandler)
    assignment.is_bot_assigned.return_value = False
    handler = CommentHandler(gitlab, bot_user_id=3, assignment_handler=assignment)
    if integration:
        handler.set_opencode_integration(integration)
    return handler, gitlab


def _make_integration():
    integration = MagicMock()
    integration.get_active_session_for_issue.return_value = None
    integration.config = MagicMock()
    integration.config.opencode_server_url = "http://test:4096"
    integration.opencode_session_slugs = {}
    integration.get_opencode_session_url.return_value = "http://test:4096/Lw/session/ses_test123"

    async def fake_create(**kwargs):
        session = MagicMock()
        session.id = "sess-42-123"
        session.branch = "ai-work/issue-42"
        session.status = SessionStatus.RUNNING
        return session

    integration.create_session = AsyncMock(side_effect=fake_create)
    integration.send_followup = AsyncMock(return_value=True)
    integration.stop_session = AsyncMock(return_value=True)
    integration.monitor_session = AsyncMock()
    return integration


class TestSessionStart:
    @pytest.mark.asyncio
    async def test_session_command_creates_session(self):
        integration = _make_integration()
        handler, gitlab = _make_handler(integration)
        handler.context_extractor = MagicMock()
        ctx = MagicMock()
        ctx.title = "Test"
        ctx.url = "http://test"
        ctx.repo_url = "http://test.git"
        handler.context_extractor.extract_issue_context.return_value = ctx

        webhook = _make_webhook("@phixr-bot /session")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        integration.create_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_session_vibe_creates_session(self):
        integration = _make_integration()
        handler, gitlab = _make_handler(integration)
        handler.context_extractor = MagicMock()
        ctx = MagicMock()
        ctx.title = "Test"
        ctx.url = "http://test"
        ctx.repo_url = "http://test.git"
        handler.context_extractor.extract_issue_context.return_value = ctx

        webhook = _make_webhook("@phixr-bot /session --vibe")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        call_kwargs = integration.create_session.call_args[1]
        assert call_kwargs["vibe"] is True

    @pytest.mark.asyncio
    async def test_existing_session_notifies_user(self):
        integration = _make_integration()
        existing = MagicMock()
        existing.id = "sess-42-old"
        integration.get_active_session_for_issue.return_value = existing

        handler, gitlab = _make_handler(integration)
        webhook = _make_webhook("@phixr-bot /session")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        integration.create_session.assert_not_awaited()
        gitlab.add_issue_comment.assert_called()
        comment = gitlab.add_issue_comment.call_args[0][2]
        assert "already active" in comment

    @pytest.mark.asyncio
    async def test_no_integration_reports_error(self):
        handler, gitlab = _make_handler()
        webhook = _make_webhook("@phixr-bot /session")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        gitlab.add_issue_comment.assert_called()
        comment = gitlab.add_issue_comment.call_args[0][2]
        assert "not available" in comment


class TestMessageForwarding:
    @pytest.mark.asyncio
    async def test_forwards_message_to_active_session(self):
        integration = _make_integration()
        active = MagicMock()
        active.id = "sess-42-123"
        active.status = SessionStatus.RUNNING
        integration.get_active_session_for_issue.return_value = active

        handler, gitlab = _make_handler(integration)
        webhook = _make_webhook("@phixr-bot please add tests for the auth module")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        integration.send_followup.assert_awaited_once()
        args = integration.send_followup.call_args
        assert "add tests" in args[0][1]

    @pytest.mark.asyncio
    async def test_no_session_offers_to_start(self):
        integration = _make_integration()
        handler, gitlab = _make_handler(integration)

        webhook = _make_webhook("@phixr-bot please fix the login")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        gitlab.add_issue_comment.assert_called()
        comment = gitlab.add_issue_comment.call_args[0][2]
        assert "No active session" in comment

    @pytest.mark.asyncio
    async def test_bare_mention_no_session_acknowledges(self):
        integration = _make_integration()
        handler, gitlab = _make_handler(integration)

        webhook = _make_webhook("@phixr-bot")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        gitlab.add_issue_comment.assert_called()
        comment = gitlab.add_issue_comment.call_args[0][2]
        assert "ready" in comment.lower()


class TestSessionEnd:
    @pytest.mark.asyncio
    async def test_end_stops_active_session(self):
        integration = _make_integration()
        active = MagicMock()
        active.id = "sess-42-123"
        integration.get_active_session_for_issue.return_value = active

        handler, gitlab = _make_handler(integration)
        webhook = _make_webhook("@phixr-bot /end")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        integration.stop_session.assert_awaited_with("sess-42-123")
        gitlab.add_issue_comment.assert_called()
        comment = gitlab.add_issue_comment.call_args[0][2]
        assert "ended" in comment.lower()

    @pytest.mark.asyncio
    async def test_end_no_session_notifies(self):
        integration = _make_integration()
        handler, gitlab = _make_handler(integration)

        webhook = _make_webhook("@phixr-bot /end")
        result = await handler.handle_issue_comment(webhook)

        assert result is True
        gitlab.add_issue_comment.assert_called()
        comment = gitlab.add_issue_comment.call_args[0][2]
        assert "No active session" in comment


class TestIgnoresSelf:
    @pytest.mark.asyncio
    async def test_ignores_bot_comments(self):
        handler, gitlab = _make_handler()
        webhook = _make_webhook("@phixr-bot /session", author="phixr-bot")

        with patch("phixr.handlers.comment_handler.settings") as mock_settings:
            mock_settings.bot_username = "phixr-bot"
            result = await handler.handle_issue_comment(webhook)

        assert result is False


class TestNonPhixrComments:
    @pytest.mark.asyncio
    async def test_ignores_unrelated_comments(self):
        handler, gitlab = _make_handler()
        webhook = _make_webhook("just a regular comment")
        result = await handler.handle_issue_comment(webhook)
        assert result is False
