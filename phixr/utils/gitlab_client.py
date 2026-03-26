"""GitLab API client wrapper."""
import logging
from typing import Optional, List, Dict, Any
import gitlab

logger = logging.getLogger(__name__)


class GitLabClient:
    """Wrapper around python-gitlab client."""
    
    def __init__(self, gitlab_url: str, token: str):
        """Initialize GitLab client.
        
        Args:
            gitlab_url: URL of GitLab instance
            token: Personal access token
        """
        self.gitlab_url = gitlab_url
        self.token = token
        self.gl = gitlab.Gitlab(gitlab_url, private_token=token)
        
    def validate_connection(self) -> bool:
        """Validate GitLab connection."""
        try:
            # Get current user info directly via API
            user_data = self.gl.http_get("/user")
            username = user_data.get('username', 'unknown')
            logger.info(f"Connected to GitLab as user: {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to GitLab: {e}")
            return False
    
    def create_user(self, username: str, email: str, password: str, 
                    is_admin: bool = False) -> Optional[Dict[str, Any]]:
        """Create a new user.
        
        Args:
            username: Username for new user
            email: Email for new user
            password: Password for new user
            is_admin: Whether user should be admin
            
        Returns:
            User data if successful, None otherwise
        """
        try:
            user = self.gl.users.create({
                'username': username,
                'email': email,
                'password': password,
                'admin': is_admin
            })
            logger.info(f"Created user: {username} (id: {user.id})")
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email
            }
        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            return None
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username.
        
        Args:
            username: Username to retrieve
            
        Returns:
            User data if found, None otherwise
        """
        try:
            # Use direct API call to ensure we get full user data
            users_data = self.gl.http_get("/users", query_data={"username": username})
            if isinstance(users_data, list) and users_data:
                user = users_data[0]
                return {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user.get('email', '')
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get user {username}: {e}")
        return None
    
    def create_personal_access_token(self, user_id: int, token_name: str,
                                    scopes: List[str]) -> Optional[str]:
        """Create a personal access token for a user.
        
        Args:
            user_id: ID of user
            token_name: Name for the token
            scopes: List of scopes (e.g., ['api', 'read_api'])
            
        Returns:
            Token string if successful, None otherwise
        """
        try:
            user = self.gl.users.get(user_id)
            token = user.personalAccessTokens.create({
                'name': token_name,
                'scopes': scopes,
                'expires_at': None
            })
            logger.info(f"Created PAT for user {user_id}: {token_name}")
            return token.token
        except Exception as e:
            logger.error(f"Failed to create PAT for user {user_id}: {e}")
            return None
    
    def get_issue(self, project_id: int, issue_id: int) -> Optional[Dict[str, Any]]:
        """Get issue details.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            
        Returns:
            Issue data if found, None otherwise
        """
        try:
            project = self.gl.projects.get(project_id)
            issue = project.issues.get(issue_id)
            return {
                'id': issue.iid,
                'project_id': project_id,
                'title': issue.title,
                'description': issue.description,
                'url': issue.web_url,
                'assignees': [a['username'] for a in issue.assignees] if issue.assignees else [],
                'labels': issue.labels,
                'milestone': issue.milestone['title'] if issue.milestone else None,
                'author': issue.author['username'],
                'created_at': issue.created_at,
                'updated_at': issue.updated_at,
                'state': issue.state
            }
        except Exception as e:
            logger.error(f"Failed to get issue {project_id}/{issue_id}: {e}")
            return None
    
    def get_issue_notes(self, project_id: int, issue_id: int) -> List[Dict[str, Any]]:
        """Get all comments/notes for an issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            
        Returns:
            List of comment data
        """
        try:
            project = self.gl.projects.get(project_id)
            issue = project.issues.get(issue_id)
            notes = issue.notes.list(all=True)
            return [
                {
                    'id': note.id,
                    'body': note.body,
                    'author': note.author['username'],
                    'created_at': note.created_at,
                    'updated_at': note.updated_at,
                    'system': note.system
                }
                for note in notes
            ]
        except Exception as e:
            logger.error(f"Failed to get notes for issue {project_id}/{issue_id}: {e}")
            return []
    
    def add_issue_comment(self, project_id: int, issue_id: int, 
                         comment_text: str) -> Optional[Dict[str, Any]]:
        """Add a comment to an issue.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            comment_text: Text of the comment
            
        Returns:
            Comment data if successful, None otherwise
        """
        logger.info(f"Attempting to add comment to issue {project_id}/{issue_id}")
        logger.debug(f"GitLab URL: {self.gitlab_url}")
        logger.debug(f"Comment text preview: {comment_text[:100]}...")
        
        try:
            logger.debug(f"Getting project {project_id}...")
            project = self.gl.projects.get(project_id)
            logger.debug(f"Getting issue {issue_id}...")
            issue = project.issues.get(issue_id)
            logger.debug(f"Creating note...")
            note = issue.notes.create({'body': comment_text})
            logger.info(f"Successfully added comment to issue {project_id}/{issue_id} (note_id={note.id})")
            return {
                'id': note.id,
                'body': note.body,
                'created_at': note.created_at
            }
        except Exception as e:
            logger.error(f"Failed to add comment to issue {project_id}/{issue_id}: {e}", exc_info=True)
            return None
    
    def assign_issue(self, project_id: int, issue_id: int, 
                    assignee_ids: List[int]) -> bool:
        """Assign issue to users.
        
        Args:
            project_id: GitLab project ID
            issue_id: GitLab issue ID
            assignee_ids: List of user IDs to assign
            
        Returns:
            True if successful, False otherwise
        """
        try:
            project = self.gl.projects.get(project_id)
            issue = project.issues.get(issue_id)
            issue.assignee_ids = assignee_ids
            issue.save()
            logger.info(f"Assigned issue {project_id}/{issue_id} to users {assignee_ids}")
            return True
        except Exception as e:
            logger.error(f"Failed to assign issue {project_id}/{issue_id}: {e}")
            return False
    
    def get_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get project details.
        
        Args:
            project_id: GitLab project ID
            
        Returns:
            Project data if found, None otherwise
        """
        try:
            project = self.gl.projects.get(project_id)
            return {
                'id': project.id,
                'name': project.name,
                'path': project.path,
                'path_with_namespace': project.path_with_namespace,
                'http_url_to_repo': project.http_url_to_repo,
                'ssh_url_to_repo': project.ssh_url_to_repo,
                'web_url': project.web_url,
                'default_branch': project.default_branch,
            }
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            return None
