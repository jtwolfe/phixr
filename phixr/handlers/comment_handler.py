"""Webhook event handlers."""
import logging
from typing import Optional, TYPE_CHECKING
from phixr.config import settings
from phixr.utils import GitLabClient
from phixr.commands import CommandParser
from phixr.context import ContextExtractor

if TYPE_CHECKING:
    from phixr.bridge.opencode_bridge import OpenCodeBridge

logger = logging.getLogger(__name__)


class AssignmentHandler:
    """Handles issue assignment tracking."""
    
    def __init__(self, bot_user_id: int):
        """Initialize assignment handler.
        
        Args:
            bot_user_id: ID of the bot user
        """
        self.bot_user_id = bot_user_id
        # In a real implementation, this would be backed by Redis/DB
        self.assigned_issues = set()
    
    def track_assignment(self, project_id: int, issue_id: int, assignee_ids: list):
        """Track if the bot is assigned to an issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            assignee_ids: List of user IDs assigned to the issue
        """
        issue_key = f"{project_id}:{issue_id}"
        
        if self.bot_user_id in assignee_ids:
            self.assigned_issues.add(issue_key)
            logger.info(f"Bot assigned to issue {issue_key}")
        else:
            self.assigned_issues.discard(issue_key)
            logger.info(f"Bot unassigned from issue {issue_key}")
    
    def is_bot_assigned(self, project_id: int, issue_id: int) -> bool:
        """Check if bot is assigned to an issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            
        Returns:
            True if bot is assigned, False otherwise
        """
        issue_key = f"{project_id}:{issue_id}"
        return issue_key in self.assigned_issues
    
    def get_assigned_issues(self) -> set:
        """Get all issues the bot is assigned to.
        
        Returns:
            Set of issue keys (format: "project_id:issue_id")
        """
        return self.assigned_issues.copy()


class CommentHandler:
    """Handles issue comment events from webhooks."""
    
    def __init__(self, gitlab_client: GitLabClient, bot_user_id: int,
                 assignment_handler: AssignmentHandler,
                 opencode_bridge: Optional['OpenCodeBridge'] = None):
        """Initialize comment handler.
        
        Args:
            gitlab_client: GitLab API client
            bot_user_id: ID of the bot user
            assignment_handler: Assignment tracking handler
            opencode_bridge: Optional OpenCode bridge for Phase 2 features
        """
        self.gitlab_client = gitlab_client
        self.bot_user_id = bot_user_id
        self.assignment_handler = assignment_handler
        self.context_extractor = ContextExtractor(gitlab_client)
        self.command_parser = CommandParser()
        self.opencode_bridge = opencode_bridge
    
    def set_opencode_bridge(self, bridge: 'OpenCodeBridge'):
        """Set the OpenCode bridge for Phase 2 features."""
        self.opencode_bridge = bridge
    
    def handle_issue_comment(self, webhook_data: dict) -> bool:
        """Handle an issue comment webhook event.
        
        Bot responds when:
        - @phixr-bot is mentioned in the comment, OR
        - Comment author is assigned to an issue where phixr-bot is also assigned
        
        Args:
            webhook_data: Webhook payload from GitLab
            
        Returns:
            True if handled successfully, False otherwise
        """
        try:
            project_id = webhook_data['project']['id']
            # For note events, issue iid is in 'issue.iid', not 'object_attributes.iid'
            issue_id = webhook_data.get('issue', {}).get('iid') or webhook_data.get('object_attributes', {}).get('iid')
            comment_author = webhook_data['user']['username']
            comment_id = webhook_data['object_attributes']['id']
            comment_body = webhook_data['object_attributes']['note'] or ''
            
            if issue_id is None:
                logger.warning(f"Could not extract issue iid from webhook payload")
                logger.warning(f"Webhook payload keys: {webhook_data.keys()}")
                return False
            
            # Ignore comments from the bot itself
            if comment_author == settings.bot_username:
                logger.info(f"Ignoring comment from bot user ({comment_author})")
                return False
            
            logger.info(f"Received comment on issue {project_id}/{issue_id} from {comment_author}")
            logger.info(f"Bot username from settings: {settings.bot_username}")
            logger.info(f"Comment body: {comment_body[:200]}...")
            
            # Check if @phixr-bot is mentioned
            bot_mentioned = '@phixr-bot' in comment_body.lower()
            logger.info(f"Bot mentioned check: {bot_mentioned}")
            
            # Check if user is assigned to this issue (we'll check via API)
            # For now, respond if bot is mentioned OR if bot is assigned
            should_respond = bot_mentioned or self.assignment_handler.is_bot_assigned(project_id, issue_id)
            
            if not should_respond:
                logger.debug(f"No mention of @phixr-bot and bot not assigned to issue {project_id}/{issue_id}, ignoring")
                return False
            
            # Parse commands from comment
            commands = self.command_parser.extract_commands(comment_body)
            logger.info(f"Commands found: {commands}")
            
            if not commands:
                logger.debug(f"No commands found in comment")
                if bot_mentioned:
                    # Acknowledge the mention even without a command
                    self._handle_acknowledge_command(project_id, issue_id)
                    return True
                return False
            
            # Process each command
            for command_name, args in commands:
                logger.info(f"Processing command: {command_name} with args {args}")
                self._process_command(command_name, args, project_id, issue_id,
                                    comment_author, comment_id, comment_body)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling comment event: {e}", exc_info=True)
            return False
    
    def _process_command(self, command_name: str, args: list,
                        project_id: int, issue_id: int, comment_author: str,
                        comment_id: int, comment_body: str):
        """Process a single command.
        
        Args:
            command_name: Name of the command
            args: Command arguments
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            comment_author: Author of the comment
            comment_id: ID of the comment
            comment_body: Full comment text
        """
        if command_name == 'ai-status':
            self._handle_status_command(project_id, issue_id)
        elif command_name == 'ai-help':
            self._handle_help_command(project_id, issue_id)
        elif command_name == 'ai-acknowledge':
            self._handle_acknowledge_command(project_id, issue_id)
        elif command_name == 'ai-plan':
            self._handle_plan_command(project_id, issue_id, comment_author)
        elif command_name == 'ai-implement':
            self._handle_implement_command(project_id, issue_id, args)
        elif command_name == 'ai-review-mr':
            self._handle_review_mr_command(project_id, issue_id, args)
        elif command_name == 'ai-fix-tests':
            self._handle_fix_tests_command(project_id, issue_id, args)
        else:
            self._handle_future_command(command_name, project_id, issue_id)
    
    def _extract_issue_context(self, project_id: int, issue_id: int):
        """Extract issue context for OpenCode.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            
        Returns:
            IssueContext or None if extraction fails
        """
        return self.context_extractor.extract_issue_context(project_id, issue_id)
    
    def _handle_status_command(self, project_id: int, issue_id: int):
        """Handle /ai-status command."""
        context = self.context_extractor.extract_issue_context(project_id, issue_id)
        
        if not context:
            response = "❌ Could not extract issue context"
        else:
            response = f"""
✅ Bot Status: Ready

**Issue Context:**
- Title: {context.title}
- Author: {context.author}
- Assignees: {', '.join(context.assignees) or 'None'}
- Labels: {', '.join(context.labels) or 'None'}
- Comments: {len(context.comments)}

Use `/ai-help` to see available commands.
            """.strip()
        
        logger.info(f"Posting status response to issue {project_id}/{issue_id}")
        result = self.gitlab_client.add_issue_comment(project_id, issue_id, response)
        if result:
            logger.info(f"✅ Status response posted successfully")
        else:
            logger.error(f"❌ Status response posting failed")
    
    def _handle_help_command(self, project_id: int, issue_id: int):
        """Handle /ai-help command."""
        available_commands = self.command_parser.get_supported_commands()
        
        response = "📚 **Available Commands:**\n\n"
        
        # Phase 1 commands
        phase_1 = self.command_parser.get_phase_1_commands()
        response += "**Phase 1 (Available Now):**\n"
        for cmd, desc in phase_1.items():
            response += f"- `/{cmd}` - {desc}\n"
        
        # Future commands
        future_cmds = {k: v for k, v in available_commands.items() if k not in phase_1}
        if future_cmds:
            response += "\n**Coming Soon:**\n"
            for cmd, desc in future_cmds.items():
                response += f"- `/{cmd}` - {desc}\n"
        
        logger.info(f"Posting help response to issue {project_id}/{issue_id}")
        result = self.gitlab_client.add_issue_comment(project_id, issue_id, response)
        if result:
            logger.info(f"✅ Help response posted successfully")
        else:
            logger.error(f"❌ Help response posting failed")
    
    def _handle_acknowledge_command(self, project_id: int, issue_id: int):
        """Handle /ai-acknowledge command."""
        response = "👋 **Phixr Bot:** I'm ready to assist with this issue! Use `/ai-help` for available commands."
        logger.info(f"Posting acknowledge response to issue {project_id}/{issue_id}")
        result = self.gitlab_client.add_issue_comment(project_id, issue_id, response)
        if result:
            logger.info(f"✅ Acknowledge response posted successfully")
        else:
            logger.error(f"❌ Acknowledge response posting failed")
    
    def _handle_plan_command(self, project_id: int, issue_id: int, comment_author: str):
        """Handle /ai-plan command - generates implementation plan using OpenCode.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            comment_author: Author of the comment (for context)
        """
        if not self.opencode_bridge:
            response = "❌ **OpenCode not available.** Phase 2 sandbox is not configured."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        context = self._extract_issue_context(project_id, issue_id)
        if not context:
            response = "❌ Could not extract issue context. Make sure the issue exists and is accessible."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        if not context.repo_url:
            response = "❌ No repository URL found in issue context. Ensure the project has a repository configured."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        try:
            # Post initial acknowledgment
            ack_response = f"""
🤖 **Phixr Bot - Planning Phase**

I'm analyzing the issue and generating an implementation plan...

**Issue:** [{context.title}]({context.url})

This may take a moment. I'll post the plan here when ready.
            """.strip()
            self.gitlab_client.add_issue_comment(project_id, issue_id, ack_response)
            
            # Build prompt for planning
            plan_prompt = self._build_plan_prompt(context, comment_author)
            
            # Start OpenCode session for planning
            from phixr.models.execution_models import ExecutionMode
            session = self.opencode_bridge.start_opencode_session(
                context=context,
                mode=ExecutionMode.PLAN,
                initial_prompt=plan_prompt,
                timeout_minutes=15,  # Shorter timeout for planning
            )
            
            logger.info(f"Plan session started: {session.id} for issue {project_id}/{issue_id}")
            
            # Post session info for user
            response = f"""
📋 **Implementation Plan Session Started**

**Session ID:** `{session.id}`
**Issue:** [{context.title}]({context.url})

The AI is analyzing the codebase and will generate a detailed implementation plan.

To execute this plan, respond to this comment with:
`@phixr-bot /ai-implement`

To abort, use:
`@phixr-bot /ai-abort`
            """.strip()
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            
        except Exception as e:
            logger.error(f"Failed to start plan session: {e}")
            response = f"❌ **Failed to start planning session:** {str(e)}"
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _handle_review_mr_command(self, project_id: int, issue_id: int, args: list):
        """Handle /ai-review-mr command - reviews a merge request.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            args: Command arguments (should contain MR URL or IID)
        """
        if not self.opencode_bridge:
            response = "❌ **OpenCode not available.** Phase 2 sandbox is not configured."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        # Get MR info from args or extract from issue context
        mr_reference = args[0] if args else None
        
        if not mr_reference:
            response = """❌ **Missing MR reference**

Usage: `/ai-review-mr <mr-url-or-iid>`

Example:
- `/ai-review-mr !123`
- `/ai-review-mr https://gitlab.example.com/project/-/merge_requests/123`
            """.strip()
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        context = self._extract_issue_context(project_id, issue_id)
        if not context:
            response = "❌ Could not extract issue context."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        try:
            # Post initial acknowledgment
            ack_response = f"""
🔍 **Phixr Bot - MR Review**

I'm reviewing merge request: **{mr_reference}**

This may take a moment. I'll post the review here when ready.
            """.strip()
            self.gitlab_client.add_issue_comment(project_id, issue_id, ack_response)
            
            # Build prompt for MR review
            review_prompt = self._build_review_prompt(context, mr_reference)
            
            # Start OpenCode session for review
            from phixr.models.execution_models import ExecutionMode
            session = self.opencode_bridge.start_opencode_session(
                context=context,
                mode=ExecutionMode.REVIEW,
                initial_prompt=review_prompt,
                timeout_minutes=20,
            )
            
            response = f"""
🔍 **MR Review Session Started**

**Session ID:** `{session.id}`
**MR:** `{mr_reference}`

The AI is reviewing the merge request. Check back for the review results.
            """.strip()
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            
        except Exception as e:
            logger.error(f"Failed to start MR review session: {e}")
            response = f"❌ **Failed to start MR review:** {str(e)}"
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _handle_fix_tests_command(self, project_id: int, issue_id: int, args: list):
        """Handle /ai-fix-tests command - fixes failing tests.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            args: Command arguments (optional test pattern or MR reference)
        """
        if not self.opencode_bridge:
            response = "❌ **OpenCode not available.** Phase 2 sandbox is not configured."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        context = self._extract_issue_context(project_id, issue_id)
        if not context:
            response = "❌ Could not extract issue context."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        if not context.repo_url:
            response = "❌ No repository URL found in issue context."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        try:
            # Optional test pattern from args
            test_pattern = args[0] if args else None
            
            # Post initial acknowledgment
            ack_response = f"""
🧪 **Phixr Bot - Fixing Tests**

I'm analyzing the failing tests and will attempt to fix them...

{f'**Pattern:** `{test_pattern}`' if test_pattern else ''}

This may take a moment. I'll post the results here when ready.
            """.strip()
            self.gitlab_client.add_issue_comment(project_id, issue_id, ack_response)
            
            # Build prompt for test fixing
            fix_prompt = self._build_fix_tests_prompt(context, test_pattern)
            
            # Start OpenCode session for test fixing
            from phixr.models.execution_models import ExecutionMode
            session = self.opencode_bridge.start_opencode_session(
                context=context,
                mode=ExecutionMode.BUILD,
                initial_prompt=fix_prompt,
                timeout_minutes=30,
            )
            
            response = f"""
🧪 **Test Fix Session Started**

**Session ID:** `{session.id}`
**Issue:** [{context.title}]({context.url})

The AI is fixing the failing tests. Check back for results.
            """.strip()
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            
        except Exception as e:
            logger.error(f"Failed to start test fix session: {e}")
            response = f"❌ **Failed to start test fix session:** {str(e)}"
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _handle_implement_command(self, project_id: int, issue_id: int, args: list):
        """Handle /ai-implement command - starts OpenCode session for the issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            args: Command arguments (optional mode, etc.)
        """
        if not self.opencode_bridge:
            response = "❌ **OpenCode not available.** Phase 2 sandbox is not configured."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        context = self._extract_issue_context(project_id, issue_id)
        if not context:
            response = "❌ Could not extract issue context. Make sure the issue exists and is accessible."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        if not context.repo_url:
            response = "❌ No repository URL found in issue context. Ensure the project has a repository configured."
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            return
        
        try:
            initial_prompt = args[0] if args else None
            
            session = self.opencode_bridge.start_opencode_session(
                context=context,
                initial_prompt=initial_prompt,
            )
            
            response = f"""
🤖 **OpenCode Session Started**

**Session ID:** `{session.id}`
**Issue:** [{context.title}]({context.url})
**Branch:** `{session.branch}`

The AI is now working on this issue. You can:
- Check status: `/ai-status`
- View logs: Monitor the session via the API

**Note:** This is a Phase 2 feature. Real-time terminal streaming is available via WebSocket.
            """.strip()
            
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
            logger.info(f"Started OpenCode session {session.id} for issue {project_id}/{issue_id}")
            
        except Exception as e:
            logger.error(f"Failed to start OpenCode session: {e}")
            response = f"❌ **Failed to start OpenCode session:** {str(e)}"
            self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _handle_future_command(self, command_name: str, project_id: int, issue_id: int):
        """Handle commands that are implemented in future phases."""
        response = f"⏳ Command `/{command_name}` is coming in a future phase. Stay tuned!"
        self.gitlab_client.add_issue_comment(project_id, issue_id, response)
    
    def _build_plan_prompt(self, context, comment_author: str) -> str:
        """Build prompt for generating implementation plan.
        
        Args:
            context: IssueContext with issue details
            comment_author: Author of the comment
            
        Returns:
            Prompt string for OpenCode
        """
        # Format comments for context
        comments_text = ""
        if context.comments:
            comments_text = "\n\n**Issue Comments:**\n"
            for c in context.comments[-10:]:  # Last 10 comments
                comments_text += f"- **{c.get('author', 'unknown')}**: {c.get('body', '')[:500]}\n"
        
        prompt = f"""You are Phixr, an AI coding assistant. Generate a detailed implementation plan for the following GitLab issue.

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
        return prompt
    
    def _build_review_prompt(self, context, mr_reference: str) -> str:
        """Build prompt for reviewing a merge request.
        
        Args:
            context: IssueContext with issue details
            mr_reference: MR URL or IID
            
        Returns:
            Prompt string for OpenCode
        """
        prompt = f"""You are Phixr, an AI coding assistant. Review the following merge request for the project.

## Issue Context
- **Title:** {context.title}
- **URL:** {context.url}
- **Description:** {context.description or 'No description'}

## Merge Request to Review
**Reference:** {mr_reference}

## Your Task
1. Fetch the merge request details
2. Review the code changes:
   - Check for bugs or potential issues
   - Evaluate code quality and style
   - Look for security concerns
   - Assess test coverage
3. Provide a comprehensive review with:
   - Summary of changes
   - Strengths
   - Issues to address (if any)
   - Suggestions for improvement
   - Overall recommendation

Clone the repository at {context.repo_url} and perform a thorough code review.

Format your response as a markdown review.
"""
        return prompt
    
    def _build_fix_tests_prompt(self, context, test_pattern: str = None) -> str:
        """Build prompt for fixing failing tests.
        
        Args:
            context: IssueContext with issue details
            test_pattern: Optional pattern to match specific tests
            
        Returns:
            Prompt string for OpenCode
        """
        pattern_text = f" matching pattern: `{test_pattern}`" if test_pattern else ""
        
        prompt = f"""You are Phixr, an AI coding assistant. Fix the failing tests in the project.

## Issue Context
- **Title:** {context.title}
- **URL:** {context.url}
- **Description:** {context.description or 'No description'}

## Test Fixing Task
Fix any failing tests{pattern_text}.

## Your Task
1. Clone the repository at {context.repo_url}
2. Run the test suite to identify failing tests
3. Analyze the test failures
4. Fix the tests by:
   - Correcting the test code if it's wrong
   - Fixing the implementation if the tests are correct
   - Ensuring all tests pass after fixes
5. Run the test suite again to verify fixes

Clone the repository, run tests, fix the issues, and verify all tests pass.

Format your response as a markdown summary of what was fixed.
"""
        return prompt
