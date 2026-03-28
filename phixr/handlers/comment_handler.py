"""Webhook event handlers."""
import asyncio
import logging
from typing import Optional, TYPE_CHECKING
from phixr.config import settings
from phixr.utils import GitLabClient
from phixr.commands import CommandParser
from phixr.commands.parser import COMMAND_SESSION, COMMAND_END, MESSAGE
from phixr.context import ContextExtractor

if TYPE_CHECKING:
    from phixr.integration.opencode_integration_service import OpenCodeIntegrationService

logger = logging.getLogger(__name__)


class AssignmentHandler:
    """Handles issue assignment tracking."""

    def __init__(self, bot_user_id: int, gitlab_client: GitLabClient):
        self.bot_user_id = bot_user_id
        self.gitlab_client = gitlab_client
        self.assigned_issues = set()

    def track_assignment(self, project_id: int, issue_id: int, assignee_ids: list):
        issue_key = f"{project_id}:{issue_id}"
        if self.bot_user_id in assignee_ids:
            self.assigned_issues.add(issue_key)
            logger.info(f"Bot assigned to issue {issue_key}")
        else:
            self.assigned_issues.discard(issue_key)
            logger.info(f"Bot unassigned from issue {issue_key}")

    def is_bot_assigned(self, project_id: int, issue_id: int) -> bool:
        try:
            issue_key = f"{project_id}:{issue_id}"
            if issue_key in self.assigned_issues:
                return True
            issue = self.gitlab_client.get_issue(project_id, issue_id)
            if issue and 'assignees' in issue:
                assignee_ids = [a.get('id') for a in issue['assignees'] if a]
                if self.bot_user_id in assignee_ids:
                    self.assigned_issues.add(issue_key)
                    return True
            return False
        except Exception as e:
            logger.warning(f"Failed to check bot assignment for issue {project_id}/{issue_id}: {e}")
            return False

    def get_assigned_issues(self) -> set:
        return self.assigned_issues.copy()


class CommentHandler:
    """Handles issue comment events from webhooks.

    Routes @phixr interactions to the appropriate handler:
    - /session [--vibe]  → start a persistent OpenCode session
    - /end               → close the active session
    - <message>          → forward to active session
    """

    def __init__(self, gitlab_client: GitLabClient, bot_user_id: int,
                 assignment_handler: AssignmentHandler,
                 opencode_integration: Optional['OpenCodeIntegrationService'] = None):
        self.gitlab_client = gitlab_client
        self.bot_user_id = bot_user_id
        self.assignment_handler = assignment_handler
        self.context_extractor = ContextExtractor(gitlab_client)
        self.command_parser = CommandParser()
        self.opencode_integration = opencode_integration

    def set_opencode_integration(self, integration: 'OpenCodeIntegrationService'):
        self.opencode_integration = integration

    async def handle_issue_comment(self, webhook_data: dict) -> bool:
        """Handle an issue comment webhook event."""
        try:
            project_id = webhook_data['project']['id']
            issue_id = (
                webhook_data.get('issue', {}).get('iid')
                or webhook_data.get('object_attributes', {}).get('iid')
            )
            comment_author = webhook_data['user']['username']
            comment_body = webhook_data['object_attributes']['note'] or ''

            if issue_id is None:
                logger.warning("Could not extract issue iid from webhook payload")
                return False

            # Ignore comments from the bot itself
            if comment_author == settings.bot_username:
                return False

            logger.info(f"Received comment on issue {project_id}/{issue_id} from {comment_author}")

            # Parse the comment for @phixr interactions
            parsed = self.command_parser.parse(comment_body)
            if not parsed:
                return False

            action, payload = parsed
            logger.info(f"Parsed action: {action}, payload: {payload}")

            if action == COMMAND_SESSION:
                await self._handle_session_start(
                    project_id, issue_id, comment_author,
                    vibe=payload.get("vibe", False),
                )
            elif action == COMMAND_END:
                await self._handle_session_end(project_id, issue_id, comment_author)
            elif action == MESSAGE:
                await self._handle_message(
                    project_id, issue_id, comment_author,
                    text=payload.get("text", ""),
                )

            return True

        except Exception as e:
            logger.error(f"Error handling comment event: {e}", exc_info=True)
            return False

    # ── Session Start ────────────────────────────────────────────────────

    async def _handle_session_start(
        self, project_id: int, issue_id: int, author: str, vibe: bool = False,
    ) -> None:
        """Handle @phixr /session [--vibe]."""
        if not self.opencode_integration:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "❌ **OpenCode not available.** Sandbox is not configured."
            )
            return

        # Check for existing session
        existing = self.opencode_integration.get_active_session_for_issue(
            project_id, issue_id
        )
        if existing:
            oc_url = self.opencode_integration.get_opencode_session_url(existing.id)
            vibe_line = ""
            if oc_url:
                vibe_line = f"\n**Live Session:** [Open in Browser]({oc_url})"

            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"ℹ️ **Session already active**\n\n"
                f"**Session ID:** `{existing.id}`{vibe_line}\n\n"
                f"Send messages with `@phixr-bot <your message>` or close with `@phixr-bot /end`."
            )
            return

        # Extract issue context
        context = self.context_extractor.extract_issue_context(project_id, issue_id)
        if not context:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "❌ Could not extract issue context. Make sure the issue exists and is accessible."
            )
            return

        if not context.repo_url:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "❌ No repository URL found. Ensure the project has a repository configured."
            )
            return

        try:
            # Post acknowledgment
            mode_label = "Vibe" if vibe else "Session"
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"🤖 **Phixr — Starting {mode_label}**\n\n"
                f"Analyzing issue and setting up workspace...\n\n"
                f"**Issue:** [{context.title}]({context.url})\n\n"
                f"This may take a moment."
            )

            session = await self.opencode_integration.create_session(
                context=context,
                project_id=project_id,
                timeout_minutes=30,
                owner_id=author,
                vibe=vibe,
            )

            logger.info(f"Session started: {session.id} for issue {project_id}/{issue_id}")

            # Build session info comment
            oc_url = self.opencode_integration.get_opencode_session_url(session.id)
            vibe_line = ""
            if oc_url:
                vibe_line = f"\n**Live Session:** [Open in Browser]({oc_url})"

            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"🤖 **AI Session Started**\n\n"
                f"**Session ID:** `{session.id}`\n"
                f"**Branch:** `{session.branch}`"
                f"{vibe_line}\n\n"
                f"Send messages with `@phixr-bot <your message>`.\n"
                f"Results will be posted here when complete.\n\n"
                f"To close: `@phixr-bot /end`"
            )

            # Start background monitoring
            asyncio.create_task(
                self.opencode_integration.monitor_session(
                    session.id, self.gitlab_client, project_id, issue_id
                )
            )

        except ValueError as e:
            # One-session-per-issue violation
            self.gitlab_client.add_issue_comment(
                project_id, issue_id, f"ℹ️ {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to start session: {e}", exc_info=True)
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"❌ **Failed to start session:** {str(e)}"
            )

    # ── Message Forwarding ───────────────────────────────────────────────

    async def _handle_message(
        self, project_id: int, issue_id: int, author: str, text: str,
    ) -> None:
        """Handle @phixr <message> — forward to active session."""
        if not self.opencode_integration:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "❌ **OpenCode not available.** Sandbox is not configured."
            )
            return

        session = self.opencode_integration.get_active_session_for_issue(
            project_id, issue_id
        )

        if not session:
            if not text:
                # Bare @phixr mention with no active session — acknowledge
                self.gitlab_client.add_issue_comment(
                    project_id, issue_id,
                    "👋 **Phixr Bot** is ready! Start a session with `@phixr-bot /session` "
                    "or `@phixr-bot /session --vibe` for a live coding UI."
                )
                return

            # Message but no active session — offer to start one
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "ℹ️ No active session for this issue.\n\n"
                "Start one with `@phixr-bot /session` and then send your message."
            )
            return

        if not text:
            # Bare @phixr mention with active session — post status
            oc_url = self.opencode_integration.get_opencode_session_url(session.id)
            vibe_line = ""
            if oc_url:
                vibe_line = f"\n**Live Session:** [Open in Browser]({oc_url})"
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"🤖 **Session Active:** `{session.id}`{vibe_line}\n\n"
                f"Send messages with `@phixr-bot <your message>` or close with `@phixr-bot /end`."
            )
            return

        # Forward the message to the active session
        sent = await self.opencode_integration.send_followup(
            session.id, text, author=author
        )
        if sent:
            logger.info(f"Forwarded message from {author} to session {session.id}")
        else:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "❌ Failed to forward message to the session. The session may have ended."
            )

    # ── Session End ──────────────────────────────────────────────────────

    async def _handle_session_end(
        self, project_id: int, issue_id: int, author: str,
    ) -> None:
        """Handle @phixr /end."""
        if not self.opencode_integration:
            return

        session = self.opencode_integration.get_active_session_for_issue(
            project_id, issue_id
        )
        if not session:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "ℹ️ No active session for this issue."
            )
            return

        success = await self.opencode_integration.stop_session(session.id)
        if success:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"✅ **Session ended** by @{author}.\n\n"
                f"**Session ID:** `{session.id}`"
            )
        else:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"❌ Failed to end session `{session.id}`."
            )
