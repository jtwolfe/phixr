"""Unit tests for OpenCode HTTP + SSE client."""

import pytest
import httpx
import respx
from unittest.mock import AsyncMock, patch

from phixr.bridge.opencode_client import OpenCodeServerClient, OpenCodeServerError


SERVER_URL = "http://test-opencode:4096"


@pytest.fixture
def client():
    c = OpenCodeServerClient(server_url=SERVER_URL)
    yield c


class TestHealthCheck:
    @respx.mock
    @pytest.mark.asyncio
    async def test_healthy(self, client):
        respx.get(f"{SERVER_URL}/global/health").mock(
            return_value=httpx.Response(200, json={"healthy": True, "version": "1.3.3"})
        )
        assert await client.health_check() is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_unhealthy(self, client):
        respx.get(f"{SERVER_URL}/global/health").mock(
            return_value=httpx.Response(500, text="error")
        )
        assert await client.health_check() is False

    @respx.mock
    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        respx.get(f"{SERVER_URL}/global/health").mock(
            side_effect=httpx.ConnectError("refused")
        )
        assert await client.health_check() is False


class TestSessionCRUD:
    @respx.mock
    @pytest.mark.asyncio
    async def test_create_session(self, client):
        session_data = {"id": "ses_abc123", "slug": "test", "title": "Test"}
        respx.post(f"{SERVER_URL}/session").mock(
            return_value=httpx.Response(200, json=session_data)
        )
        result = await client.create_session(title="Test")
        assert result["id"] == "ses_abc123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_create_session_error(self, client):
        respx.post(f"{SERVER_URL}/session").mock(
            return_value=httpx.Response(500, text="error")
        )
        with pytest.raises(OpenCodeServerError):
            await client.create_session()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_session(self, client):
        session_data = {"id": "ses_abc123", "title": "Test"}
        respx.get(f"{SERVER_URL}/session/ses_abc123").mock(
            return_value=httpx.Response(200, json=session_data)
        )
        result = await client.get_session("ses_abc123")
        assert result["id"] == "ses_abc123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client):
        respx.get(f"{SERVER_URL}/session/missing").mock(
            return_value=httpx.Response(404, text="not found")
        )
        result = await client.get_session("missing")
        assert result is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        sessions = [{"id": "ses_1"}, {"id": "ses_2"}]
        respx.get(f"{SERVER_URL}/session").mock(
            return_value=httpx.Response(200, json=sessions)
        )
        result = await client.list_sessions()
        assert len(result) == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_session_status(self, client):
        status = {"ses_abc": {"type": "busy"}}
        respx.get(f"{SERVER_URL}/session/status").mock(
            return_value=httpx.Response(200, json=status)
        )
        result = await client.get_session_status()
        assert result["ses_abc"]["type"] == "busy"

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_session_status_empty_when_idle(self, client):
        respx.get(f"{SERVER_URL}/session/status").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await client.get_session_status()
        assert result == {}

    @respx.mock
    @pytest.mark.asyncio
    async def test_abort_session(self, client):
        respx.post(f"{SERVER_URL}/session/ses_abc/abort").mock(
            return_value=httpx.Response(200, json=True)
        )
        result = await client.abort_session("ses_abc")
        assert result is True

    @respx.mock
    @pytest.mark.asyncio
    async def test_delete_session(self, client):
        respx.delete(f"{SERVER_URL}/session/ses_abc").mock(
            return_value=httpx.Response(200, json=True)
        )
        result = await client.delete_session("ses_abc")
        assert result is True


class TestPromptAndMessages:
    @respx.mock
    @pytest.mark.asyncio
    async def test_send_prompt_basic(self, client):
        route = respx.post(f"{SERVER_URL}/session/ses_abc/prompt_async").mock(
            return_value=httpx.Response(204)
        )
        await client.send_prompt("ses_abc", "Hello")
        request = route.calls[0].request
        body = request.read()
        import json
        payload = json.loads(body)
        assert payload["parts"] == [{"type": "text", "text": "Hello"}]
        assert "agent" not in payload
        assert "system" not in payload

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_prompt_with_options(self, client):
        route = respx.post(f"{SERVER_URL}/session/ses_abc/prompt_async").mock(
            return_value=httpx.Response(204)
        )
        await client.send_prompt(
            "ses_abc", "Fix the bug",
            agent="build",
            system="You are Phixr.",
            provider_id="anthropic",
            model_id="claude-sonnet-4-20250514",
        )
        import json
        payload = json.loads(route.calls[0].request.read())
        assert payload["agent"] == "build"
        assert payload["system"] == "You are Phixr."
        assert payload["model"] == {"providerID": "anthropic", "modelID": "claude-sonnet-4-20250514"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_prompt_error(self, client):
        respx.post(f"{SERVER_URL}/session/ses_abc/prompt_async").mock(
            return_value=httpx.Response(500, text="error")
        )
        with pytest.raises(OpenCodeServerError):
            await client.send_prompt("ses_abc", "Hello")

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_messages(self, client):
        messages = [
            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "Hi"}]},
            {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "Hello"}]},
        ]
        respx.get(f"{SERVER_URL}/session/ses_abc/message").mock(
            return_value=httpx.Response(200, json=messages)
        )
        result = await client.get_messages("ses_abc")
        assert len(result) == 2
        assert result[0]["info"]["role"] == "user"


class TestPermissions:
    @respx.mock
    @pytest.mark.asyncio
    async def test_list_permissions(self, client):
        perms = [{"id": "perm_1", "permission": "file_write"}]
        respx.get(f"{SERVER_URL}/permission").mock(
            return_value=httpx.Response(200, json=perms)
        )
        result = await client.list_permissions()
        assert len(result) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_reply_permission(self, client):
        route = respx.post(f"{SERVER_URL}/permission/perm_1/reply").mock(
            return_value=httpx.Response(200, json=True)
        )
        result = await client.reply_permission("perm_1", "always")
        assert result is True
        import json
        payload = json.loads(route.calls[0].request.read())
        assert payload["reply"] == "always"

    @respx.mock
    @pytest.mark.asyncio
    async def test_reply_permission_error(self, client):
        respx.post(f"{SERVER_URL}/permission/perm_1/reply").mock(
            return_value=httpx.Response(500, text="error")
        )
        result = await client.reply_permission("perm_1")
        assert result is False


class TestDiff:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_diff(self, client):
        diffs = [{"path": "src/main.py", "additions": 5, "deletions": 2}]
        respx.get(f"{SERVER_URL}/session/ses_abc/diff").mock(
            return_value=httpx.Response(200, json=diffs)
        )
        result = await client.get_diff("ses_abc", "msg_123")
        assert len(result) == 1
        assert result[0]["path"] == "src/main.py"


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_close(self, client):
        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        async with OpenCodeServerClient(SERVER_URL) as client:
            assert client.server_url == SERVER_URL
