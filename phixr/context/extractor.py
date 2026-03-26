"""Issue context extraction module."""
import logging
from datetime import datetime
from typing import Optional
from phixr.models import IssueContext
from phixr.utils import GitLabClient

logger = logging.getLogger(__name__)


class ContextExtractor:
    """Extracts and structures issue context."""
    
    def __init__(self, gitlab_client: GitLabClient):
        """Initialize context extractor.
        
        Args:
            gitlab_client: GitLab API client instance
        """
        self.gitlab_client = gitlab_client
    
    def extract_issue_context(self, project_id: int, issue_id: int) -> Optional[IssueContext]:
        """Extract full context from a GitLab issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            
        Returns:
            IssueContext object or None if issue not found
        """
        # Get issue details
        issue_data = self.gitlab_client.get_issue(project_id, issue_id)
        
        if not issue_data:
            logger.error(f"Failed to extract context for issue {project_id}/{issue_id}")
            return None
        
        # Get project details for repo_url
        project_data = self.gitlab_client.get_project(project_id)
        repo_url = ""
        repo_name = ""
        if project_data:
            repo_url = project_data.get('http_url_to_repo', '')
            repo_name = project_data.get('name', '')
        
        # Get issue notes/comments
        comments = self.gitlab_client.get_issue_notes(project_id, issue_id)
        
        # Convert comments to structured format
        formatted_comments = [
            {
                'id': c['id'],
                'author': c['author'],
                'body': c['body'],
                'created_at': c['created_at'],
                'system': c['system']
            }
            for c in comments
        ]
        
        # Create context object
        context = IssueContext(
            issue_id=issue_data['id'],
            project_id=project_id,
            title=issue_data['title'],
            description=issue_data['description'] or '',
            url=issue_data['url'],
            assignees=issue_data['assignees'],
            labels=issue_data['labels'],
            milestone=issue_data['milestone'],
            author=issue_data['author'],
            created_at=datetime.fromisoformat(str(issue_data['created_at']).replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(str(issue_data['updated_at']).replace('Z', '+00:00')),
            comments=formatted_comments,
            linked_issues=[],
            repo_url=repo_url,
            repo_name=repo_name
        )
        
        logger.info(f"Extracted context for issue {project_id}/{issue_id}: {context.title}")
        return context
    
    def serialize_context_for_env(self, context: IssueContext) -> dict:
        """Serialize context for passing via environment variables.
        
        Args:
            context: IssueContext to serialize
            
        Returns:
            Dictionary with environment-friendly serialization
        """
        import json
        
        return {
            'PHIXR_ISSUE_ID': str(context.issue_id),
            'PHIXR_PROJECT_ID': str(context.project_id),
            'PHIXR_ISSUE_TITLE': context.title,
            'PHIXR_ISSUE_DESCRIPTION': context.description,
            'PHIXR_ISSUE_URL': context.url,
            'PHIXR_ISSUE_ASSIGNEES': json.dumps(context.assignees),
            'PHIXR_ISSUE_LABELS': json.dumps(context.labels),
            'PHIXR_ISSUE_MILESTONE': context.milestone or '',
            'PHIXR_ISSUE_AUTHOR': context.author,
            'PHIXR_ISSUE_COMMENTS_JSON': json.dumps(
                [c for c in context.comments],
                default=str
            )
        }
    
    def serialize_context_for_api(self, context: IssueContext) -> dict:
        """Serialize context for passing via HTTP API.
        
        Args:
            context: IssueContext to serialize
            
        Returns:
            Dictionary with JSON-friendly serialization
        """
        return {
            'issue_id': context.issue_id,
            'project_id': context.project_id,
            'title': context.title,
            'description': context.description,
            'url': context.url,
            'assignees': context.assignees,
            'labels': context.labels,
            'milestone': context.milestone,
            'author': context.author,
            'created_at': context.created_at.isoformat(),
            'updated_at': context.updated_at.isoformat(),
            'comments': [
                {
                    'id': c['id'],
                    'author': c['author'],
                    'body': c['body'],
                    'created_at': c['created_at'],
                    'system': c['system']
                }
                for c in context.comments
            ],
            'linked_issues': context.linked_issues
        }
