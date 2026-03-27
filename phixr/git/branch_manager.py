"""Branch management for GitLab issues.

Handles detection of existing branches/MRs associated with issues
and creates new branches following a procedural naming scheme.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from phixr.utils.gitlab_client import GitLabClient
from phixr.models.issue_context import IssueContext

logger = logging.getLogger(__name__)


class BranchManager:
    """Manages Git branches for issues following the user's requirements."""

    def __init__(self, gitlab_client: GitLabClient):
        """Initialize branch manager.

        Args:
            gitlab_client: GitLab API client
        """
        self.gitlab_client = gitlab_client
        logger.info("BranchManager initialized")

    def get_or_create_branch_for_issue(self, project_id: int, issue_id: int) -> Tuple[str, bool]:
        """Get existing branch for issue or create a new one.

        Following user requirements:
        1. Check if there's a branch that if merged would close the issue
        2. If not, create a new branch with simple procedural name

        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID

        Returns:
            Tuple of (branch_name, was_newly_created)
        """
        logger.info(f"Finding branch for issue {project_id}/{issue_id}")

        # Step 1: Check for existing MRs that reference this issue
        mrs = self.gitlab_client.get_merge_requests_for_issue(project_id, issue_id)

        if mrs:
            # Use the branch from the first relevant MR
            mr = mrs[0]
            branch_name = mr['source_branch']
            logger.info(f"Found existing MR #{mr['iid']} with branch: {branch_name}")
            return branch_name, False

        # Step 2: Check if a branch with standard name already exists
        standard_branch = f"issue-{issue_id}"
        existing_branch = self.gitlab_client.get_branch(project_id, standard_branch)

        if existing_branch:
            logger.info(f"Found existing branch: {standard_branch}")
            return standard_branch, False

        # Step 3: Create new branch with simple procedural name
        new_branch = f"ai-work/issue-{issue_id}"
        created_branch = self.gitlab_client.create_branch(project_id, new_branch)

        if created_branch:
            logger.info(f"Created new branch: {new_branch}")
            return new_branch, True
        else:
            # Fallback to default branch
            logger.warning(f"Failed to create branch, using default")
            return "main", False

    def get_branch_for_session(self, context: IssueContext) -> str:
        """Get appropriate branch for a session based on context.

        Args:
            context: Issue context

        Returns:
            Branch name to use
        """
        branch_name, _ = self.get_or_create_branch_for_issue(
            context.project_id, context.issue_id
        )
        return branch_name

    def should_create_mr(self, project_id: int, issue_id: int) -> bool:
        """Check if we should create an MR for this issue.

        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID

        Returns:
            True if no MR exists for this issue
        """
        mrs = self.gitlab_client.get_merge_requests_for_issue(project_id, issue_id)
        return len(mrs) == 0


# Global instance
_branch_manager = None


def get_branch_manager(gitlab_client: GitLabClient) -> BranchManager:
    """Get or create branch manager instance.

    Args:
        gitlab_client: GitLab client to use

    Returns:
        BranchManager instance
    """
    global _branch_manager
    if _branch_manager is None:
        _branch_manager = BranchManager(gitlab_client)
    return _branch_manager