#!/usr/bin/env python3
"""Script to set up a Phixr bot user in GitLab."""
import click
import secrets
from phixr.utils import GitLabClient, setup_logger

logger = setup_logger(__name__)


@click.command()
@click.option('--gitlab-url', default='http://localhost:8080', 
              help='GitLab instance URL')
@click.option('--root-token', prompt=True, hide_input=True,
              help='GitLab root/admin personal access token')
@click.option('--bot-username', default='phixr-bot',
              help='Username for the bot')
@click.option('--bot-email', default='phixr-bot@localhost',
              help='Email for the bot')
def setup_bot(gitlab_url: str, root_token: str, bot_username: str, bot_email: str):
    """Set up a Phixr bot user in GitLab."""
    
    click.echo(f"\n🚀 Setting up Phixr bot in GitLab...")
    click.echo(f"GitLab URL: {gitlab_url}")
    click.echo(f"Bot username: {bot_username}\n")
    
    # Initialize GitLab client with root token
    gl_client = GitLabClient(gitlab_url, root_token)
    
    # Validate connection
    click.echo("✓ Validating GitLab connection...")
    if not gl_client.validate_connection():
        click.echo("✗ Failed to connect to GitLab")
        return
    
    # Check if bot user already exists
    click.echo(f"✓ Checking if {bot_username} already exists...")
    existing_user = gl_client.get_user(bot_username)
    
    if existing_user:
        click.echo(f"✓ User {bot_username} already exists (ID: {existing_user['id']})")
        bot_user_id = existing_user['id']
    else:
        # Generate a random password
        bot_password = secrets.token_urlsafe(32)
        
        # Create bot user
        click.echo(f"✓ Creating bot user {bot_username}...")
        user_data = gl_client.create_user(bot_username, bot_email, bot_password)
        
        if not user_data:
            click.echo("✗ Failed to create bot user")
            return
        
        bot_user_id = user_data['id']
        click.echo(f"✓ Bot user created with ID: {bot_user_id}")
    
    # Create personal access token
    click.echo("✓ Creating personal access token...")
    token_name = "phixr-bot-token"
    scopes = ['api', 'read_api', 'write_repository']
    
    bot_token = gl_client.create_personal_access_token(bot_user_id, token_name, scopes)
    
    if not bot_token:
        click.echo("✗ Failed to create personal access token")
        return
    
    click.echo(f"✓ Personal access token created")
    
    # Display results
    click.echo("\n" + "="*60)
    click.echo("✅ Phixr bot setup completed!")
    click.echo("="*60)
    click.echo(f"\nBot Configuration:")
    click.echo(f"  Username: {bot_username}")
    click.echo(f"  Email: {bot_email}")
    click.echo(f"  User ID: {bot_user_id}")
    click.echo(f"  Token: {bot_token}")
    click.echo(f"\nAdd to your .env.local file:")
    click.echo(f"  GITLAB_BOT_TOKEN={bot_token}")
    click.echo(f"  GITLAB_URL={gitlab_url}")
    click.echo("="*60 + "\n")


if __name__ == '__main__':
    setup_bot()
