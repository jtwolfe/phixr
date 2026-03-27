"""Webhook event handlers."""
import asyncio
import logging
from typing import Optional, TYPE_CHECKING
from phixr.config import settings
from phixr.utils import GitLabClient
from phixr.commands import CommandParser
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
        """Track if the bot is assigned to an issue."""
        issue_key = f"{project_id}:{issue_id}"

        if self.bot_user_id in assignee_ids:
            self.assigned_issues.add(issue_key)
            logger.info(f"Bot assigned to issue {issue_key}")
        else:
            self.assigned_issues.discard(issue_key)
            logger.info(f"Bot unassigned from issue {issue_key}")

    def is_bot_assigned(self, project_id: int, issue_id: int) -> bool:
        """Check if bot is assigned to an issue."""
        try:
            issue_key = f"{project_id}:{issue_id}"
            if issue_key in self.assigned_issues:
                return True

            issue = self.gitlab_client.get_issue(project_id, issue_id)
            if issue and 'assignees' in issue:
                assignee_ids = [assignee.get('id') for assignee in issue['assignees'] if assignee]
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
    """Handles issue comment events from webhooks."""

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
        """Set the OpenCode integration service."""
        self.opencode_integration = integration

    async def handle_issue_comment(self, webhook_data: dict) -> bool:
        """Handle an issue comment webhook event."""
        try:
            project_id = webhook_data['project']['id']
            issue_id = webhook_data.get('issue', {}).get('iid') or webhook_data.get('object_attributes', {}).get('iid')
            comment_author = webhook_data['user']['username']
            comment_id = webhook_data['object_attributes']['id']
            comment_body = webhook_data['object_attributes']['note'] or ''

            if issue_id is None:
                logger.warning(f"Could not extract issue iid from webhook payload")
                return False

            # Ignore comments from the bot itself
            if comment_author == settings.bot_username:
                return False

            logger.info(f"Received comment on issue {project_id}/{issue_id} from {comment_author}")

            # Check if @phixr-bot is mentioned
            bot_mentioned = '@phixr-bot' in comment_body.lower()
            should_respond = bot_mentioned or self.assignment_handler.is_bot_assigned(project_id, issue_id)

            if not should_respond:
                return False

            # Parse commands from comment
            commands = self.command_parser.extract_commands(comment_body)

            if not commands:
                if bot_mentioned:
                    await self._handle_acknowledge_command(project_id, issue_id)
                    return True
                return False

            # Process each command
            for command_name, args in commands:
                logger.info(f"Processing command: {command_name} with args {args}")
                await self._process_command(command_name, args, project_id, issue_id,
                                           comment_author, comment_id, comment_body)

            return True

        except Exception as e:
            logger.error(f"Error handling comment event: {e}", exc_info=True)
            return False

    async def _process_command(self, command_name: str, args: list,
                               project_id: int, issue_id: int, comment_author: str,
                               comment_id: int, comment_body: str):
        """Route command to handler."""
        if command_name == 'ai-status':
            await self._handle_status_command(project_id, issue_id)
        elif command_name == 'ai-help':
            await self._handle_help_command(project_id, issue_id)
        elif command_name == 'ai-acknowledge':
            await self._handle_acknowledge_command(project_id, issue_id)
        elif command_name == 'ai-plan':
            await self._handle_plan_command(project_id, issue_id, comment_author)
        elif command_name == 'ai-implement':
            await self._handle_implement_command(project_id, issue_id, args, comment_author)
        elif command_name == 'ai-review-mr':
            await self._handle_review_mr_command(project_id, issue_id, args, comment_author)
        elif command_name == 'ai-fix-tests':
            await self._handle_fix_tests_command(project_id, issue_id, args, comment_author)
        else:
            await self._handle_future_command(command_name, project_id, issue_id)

    def _extract_issue_context(self, project_id: int, issue_id: int):
        """Extract issue context for OpenCode."""
        return self.context_extractor.extract_issue_context(project_id, issue_id)

    # ── Simple Commands ──────────────────────────────────────────────────

    async def _handle_status_command(self, project_id: int, issue_id: int):
        """Handle /ai-status command."""
        context = self.context_extractor.extract_issue_context(project_id, issue_id)

        if not context:
            response = "❌ Could not extract issue context"
        else:
            response = f"""✅ Bot Status: Ready

**Issue Context:**
- Title: {context.title}
- Author: {context.author}
- Assignees: {', '.join(context.assignees) or 'None'}
- Labels: {', '.join(context.labels) or 'None'}
- Comments: {len(context.comments)}

Use `/ai-help` to see available commands."""

        self.gitlab_client.add_issue_comment(project_id, issue_id, response)

    async def _handle_help_command(self, project_id: int, issue_id: int):
        """Handle /ai-help command."""
        available_commands = self.command_parser.get_supported_commands()

        response = "📚 **Available Commands:**\n\n"

        phase_1 = self.command_parser.get_phase_1_commands()
        response += "**Phase 1 (Available Now):**\n"
        for cmd, desc in phase_1.items():
            response += f"- `/{cmd}` - {desc}\n"

        future_cmds = {k: v for k, v in available_commands.items() if k not in phase_1}
        if future_cmds:
            response += "\n**Coming Soon:**\n"
            for cmd, desc in future_cmds.items():
                response += f"- `/{cmd}` - {desc}\n"

        self.gitlab_client.add_issue_comment(project_id, issue_id, response)

    async def _handle_acknowledge_command(self, project_id: int, issue_id: int):
        """Handle /ai-acknowledge command."""
        response = "👋 **Phixr Bot:** I'm ready to assist with this issue! Use `/ai-help` for available commands."
        self.gitlab_client.add_issue_comment(project_id, issue_id, response)

    async def _handle_future_command(self, command_name: str, project_id: int, issue_id: int):
        """Handle commands that are not yet implemented."""
        response = f"⏳ Command `/{command_name}` is coming in a future phase. Stay tuned!"
        self.gitlab_client.add_issue_comment(project_id, issue_id, response)

    # ── OpenCode Session Commands ────────────────────────────────────────
    # All follow the same pattern:
    # 1. Check opencode_integration is available
    # 2. Extract issue context
    # 3. Post acknowledgment to GitLab
    # 4. Create OpenCode session
    # 5. Post session info to GitLab
    # 6. Start background monitoring task

    async def _start_opencode_session(
        self,
        project_id: int,
        issue_id: int,
        comment_author: str,
        mode: 'ExecutionMode',
        mode_label: str,
        mode_emoji: str,
        timeout_minutes: int = 30,
        extra_context: str = "",
    ) -> None:
        """Shared logic for starting an OpenCode session.

        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            comment_author: Who triggered the command
            mode: ExecutionMode (PLAN, BUILD, REVIEW)
            mode_label: Human label for messages (e.g. "Planning", "Implementation")
            mode_emoji: Emoji for messages
            timeout_minutes: Session timeout
            extra_context: Additional text appended to the issue description
        """
        if not self.opencode_integration:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "❌ **OpenCode not available.** Sandbox is not configured."
            )
            return

        context = self._extract_issue_context(project_id, issue_id)
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

        # Append extra context to the description if provided
        if extra_context:
            context.description = f"{context.description or ''}\n\n{extra_context}"

        try:
            # Post acknowledgment
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"{mode_emoji} **Phixr Bot — {mode_label} Phase**\n\n"
                f"Analyzing issue and starting {mode_label.lower()}...\n\n"
                f"**Issue:** [{context.title}]({context.url})\n\n"
                f"This may take a moment."
            )

            from phixr.models.execution_models import ExecutionMode
            session = await self.opencode_integration.create_session(
                context=context,
                execution_mode=mode,
                timeout_minutes=timeout_minutes,
                owner_id=comment_author,
            )

            logger.info(f"{mode_label} session started: {session.id} for issue {project_id}/{issue_id}")

            # Get vibe room URL
            vibe_room = self.opencode_integration.get_vibe_room_by_session(session.id)
            vibe_url = self.opencode_integration.create_vibe_session_url(session.id) if vibe_room else None

            vibe_line = f"\n**Vibe Room:** [Open in Browser]({vibe_url})" if vibe_url else ""
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"{mode_emoji} **AI {mode_label} Session Started**\n\n"
                f"**Session ID:** `{session.id}`\n"
                f"**Branch:** `{session.branch}`\n"
                f"**Mode:** {mode.value.upper()}"
                f"{vibe_line}\n\n"
                f"Results will be posted here when complete.\n\n"
                f"To abort: `@phixr-bot /ai-abort`"
            )

            # Start background monitoring
            asyncio.create_task(
                self.opencode_integration.monitor_session(
                    session.id, self.gitlab_client, project_id, issue_id
                )
            )

        except Exception as e:
            logger.error(f"Failed to start {mode_label.lower()} session: {e}", exc_info=True)
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                f"❌ **Failed to start {mode_label.lower()} session:** {str(e)}"
            )

    async def _handle_plan_command(self, project_id: int, issue_id: int, comment_author: str):
        """Handle /ai-plan command."""
        from phixr.models.execution_models import ExecutionMode
        await self._start_opencode_session(
            project_id, issue_id, comment_author,
            mode=ExecutionMode.PLAN,
            mode_label="Planning",
            mode_emoji="🤖",
            timeout_minutes=15,
        )

    async def _handle_implement_command(self, project_id: int, issue_id: int,
                                        args: list, comment_author: str):
        """Handle /ai-implement command."""
        from phixr.models.execution_models import ExecutionMode
        await self._start_opencode_session(
            project_id, issue_id, comment_author,
            mode=ExecutionMode.BUILD,
            mode_label="Implementation",
            mode_emoji="🚀",
            timeout_minutes=45,
        )

    async def _handle_review_mr_command(self, project_id: int, issue_id: int,
                                        args: list, comment_author: str):
        """Handle /ai-review-mr command."""
        mr_reference = args[0] if args else None

        if not mr_reference:
            self.gitlab_client.add_issue_comment(
                project_id, issue_id,
                "❌ **Missing MR reference**\n\n"
                "Usage: `/ai-review-mr <mr-url-or-iid>`\n\n"
                "Example: `/ai-review-mr !123`"
            )
            return

        from phixr.models.execution_models import ExecutionMode
        await self._start_opencode_session(
            project_id, issue_id, comment_author,
            mode=ExecutionMode.REVIEW,
            mode_label="MR Review",
            mode_emoji="🔍",
            timeout_minutes=20,
            extra_context=f"\n\n**Merge Request to Review:** {mr_reference}",
        )

    async def _handle_fix_tests_command(self, project_id: int, issue_id: int,
                                        args: list, comment_author: str):
        """Handle /ai-fix-tests command."""
        test_pattern = args[0] if args else None
        extra = f"\n\n**Test Pattern:** `{test_pattern}`" if test_pattern else ""
        extra += "\n\n**Task:** Run the test suite, identify failures, and fix them."

        from phixr.models.execution_models import ExecutionMode
        await self._start_opencode_session(
            project_id, issue_id, comment_author,
            mode=ExecutionMode.BUILD,
            mode_label="Test Fix",
            mode_emoji="🧪",
            timeout_minutes=30,
            extra_context=extra,
        )

    # ── Prompt Building (kept for reference, but now handled by integration service) ──

    def _build_plan_prompt(self, context, comment_author: str) -> str:
        """Build prompt for generating implementation plan."""
        comments_text = ""
        if context.comments:
            comments_text = "\n\n**Issue Comments:**\n"
            for c in context.comments[-10:]:
                comments_text += f"- **{c.get('author', 'unknown')}**: {c.get('body', '')[:500]}\n"

        return f"""You are Phixr, an AI coding assistant. Generate a detailed implementation plan for the following GitLab issue.

## Issue Details
- **Title:** {context.title}
- **URL:** {context.url}
- **Author:** {context.author}
- **Assignees:** {', '.join(context.assignees) or 'None'}
- **Labels:** {', '.join(context.labels) or 'None'}

## Description
{context.description or 'No description provided.'}
{comments_text}

## Your Task
1. Analyze the issue and understand what needs to be implemented
2. Review the codebase to understand the existing structure
3. Create a detailed implementation plan with:
   - Step-by-step tasks
   - Files that need to be modified/created
   - Technical considerations
   - Potential challenges and how to address them
4. Present the plan in a clear, structured format

Clone the repository at {context.repo_url}, explore the codebase, and provide your analysis.

Format your response as a markdown implementation plan.
"""

    def _build_review_prompt(self, context, mr_reference: str) -> str:
        """Build prompt for reviewing a merge request."""
        return f"""You are Phixr, an AI coding assistant. Review the following merge request.

## Issue Context
- **Title:** {context.title}
- **URL:** {context.url}
- **Description:** {context.description or 'No description'}

## Merge Request to Review
**Reference:** {mr_reference}

## Your Task
1. Fetch the merge request details
2. Review the code changes for bugs, quality, security, and test coverage
3. Provide a comprehensive review

Clone the repository at {context.repo_url} and perform a thorough code review.
"""

    def _build_fix_tests_prompt(self, context, test_pattern: str = None) -> str:
        """Build prompt for fixing failing tests."""
        pattern_text = f" matching pattern: `{test_pattern}`" if test_pattern else ""

        return f"""You are Phixr, an AI coding assistant. Fix the failing tests in the project.

## Issue Context
- **Title:** {context.title}
- **URL:** {context.url}
- **Description:** {context.description or 'No description'}

## Task
Fix any failing tests{pattern_text}.

1. Clone the repository at {context.repo_url}
2. Run the test suite to identify failures
3. Fix the tests
4. Verify all tests pass
"""
