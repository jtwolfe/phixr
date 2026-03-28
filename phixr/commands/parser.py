"""Command parser for @phixr interactions in issue comments.

Supports a minimal command set designed for seamless GitLab-OpenCode integration:
- /session          Start a persistent OpenCode session for this issue
- /session --vibe   Start a session and return a live OpenCode UI link
- /end              Close the active session
- @phixr <message>  Forward a message to the active session
"""

import re
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Result types returned by parse()
COMMAND_SESSION = "session"
COMMAND_END = "end"
MESSAGE = "message"


class CommandParser:
    """Parser for @phixr interactions in issue comments.

    Recognises three patterns:
    1. ``@phixr /session [--vibe]`` → start a session
    2. ``@phixr /end``              → close the active session
    3. ``@phixr <anything else>``   → forward text to session
    """

    # Pattern: @phixr /session [--vibe]
    _SESSION_RE = re.compile(
        r"@phixr\s+/session(?:\s+(--vibe))?",
        re.IGNORECASE,
    )
    # Pattern: @phixr /end
    _END_RE = re.compile(
        r"@phixr\s+/end",
        re.IGNORECASE,
    )
    # Pattern: @phixr <message> (must not start with a slash command we handle)
    # Also matches bare @phixr with no trailing text
    _MENTION_RE = re.compile(
        r"@phixr(?:\s+(.*))?",
        re.IGNORECASE | re.DOTALL,
    )

    COMMANDS = {
        "session": "Start a persistent AI session for this issue",
        "session --vibe": "Start a session and get a live OpenCode UI link",
        "end": "Close the active session and release resources",
    }

    @classmethod
    def parse(cls, text: str) -> Optional[Tuple[str, dict]]:
        """Parse an issue comment for @phixr interactions.

        Returns:
            Tuple of (action, payload) or None if the comment is not for us.

            action is one of: "session", "end", "message"
            payload keys depend on action:
              session: {"vibe": bool}
              end:     {}
              message: {"text": str}
        """
        if not text or "phixr" not in text.lower():
            return None

        # Check /session first
        m = cls._SESSION_RE.search(text)
        if m:
            vibe = m.group(1) is not None
            return COMMAND_SESSION, {"vibe": vibe}

        # Check /end
        m = cls._END_RE.search(text)
        if m:
            return COMMAND_END, {}

        # Check bare @phixr mention (message passthrough)
        m = cls._MENTION_RE.search(text)
        if m:
            message_text = (m.group(1) or "").strip()
            if message_text:
                return MESSAGE, {"text": message_text}
            # Bare @phixr with no text — treat as acknowledgment request
            return MESSAGE, {"text": ""}

        return None

    @classmethod
    def get_supported_commands(cls) -> dict:
        """Return command descriptions for /help-style responses."""
        return cls.COMMANDS
