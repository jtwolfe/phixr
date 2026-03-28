"""Unit tests for the command parser."""

import pytest
from phixr.commands.parser import CommandParser, COMMAND_SESSION, COMMAND_END, MESSAGE


class TestParseSession:
    def test_session_command(self):
        result = CommandParser.parse("@phixr /session")
        assert result is not None
        action, payload = result
        assert action == COMMAND_SESSION
        assert payload["vibe"] is False

    def test_session_vibe(self):
        result = CommandParser.parse("@phixr /session --vibe")
        assert result is not None
        action, payload = result
        assert action == COMMAND_SESSION
        assert payload["vibe"] is True

    def test_session_case_insensitive(self):
        result = CommandParser.parse("@Phixr /session --vibe")
        assert result is not None
        assert result[0] == COMMAND_SESSION

    def test_session_with_surrounding_text(self):
        result = CommandParser.parse("Hey team, @phixr /session please")
        assert result is not None
        assert result[0] == COMMAND_SESSION

    def test_session_underscore_variant(self):
        result = CommandParser.parse("@phixr /session")
        assert result is not None
        assert result[0] == COMMAND_SESSION


class TestParseEnd:
    def test_end_command(self):
        result = CommandParser.parse("@phixr /end")
        assert result is not None
        action, payload = result
        assert action == COMMAND_END
        assert payload == {}

    def test_end_case_insensitive(self):
        result = CommandParser.parse("@PHIXR /end")
        assert result is not None
        assert result[0] == COMMAND_END


class TestParseMessage:
    def test_message_passthrough(self):
        result = CommandParser.parse("@phixr please add unit tests for the auth module")
        assert result is not None
        action, payload = result
        assert action == MESSAGE
        assert "please add unit tests" in payload["text"]

    def test_bare_mention(self):
        result = CommandParser.parse("@phixr")
        assert result is not None
        action, payload = result
        assert action == MESSAGE
        assert payload["text"] == ""

    def test_multiline_message(self):
        text = "@phixr here is what I need:\n1. Fix the login\n2. Add tests"
        result = CommandParser.parse(text)
        assert result is not None
        action, payload = result
        assert action == MESSAGE
        assert "Fix the login" in payload["text"]
        assert "Add tests" in payload["text"]


class TestParseNoMatch:
    def test_no_mention(self):
        assert CommandParser.parse("just a regular comment") is None

    def test_empty_string(self):
        assert CommandParser.parse("") is None

    def test_none_input(self):
        assert CommandParser.parse(None) is None

    def test_other_bot_mention(self):
        assert CommandParser.parse("@other-bot do something") is None


class TestGetSupportedCommands:
    def test_returns_commands(self):
        cmds = CommandParser.get_supported_commands()
        assert "session" in cmds
        assert "end" in cmds
