#!/usr/bin/env python3
"""
Interactive script to help you manually generate a root PAT token,
then use it to create the bot user and bot token.
"""
import click
import requests
import secrets
import time

@click.command()
@click.option('--gitlab-url', default='http://localhost:8080', help='GitLab instance URL')
@click.option('--root-token', prompt='Paste your root personal access token here', 
              hide_input=True, help='Root PAT token from GitLab')
@click.option('--bot-username', default='phixr-bot', help='Bot username')
@click.option('--bot-email', default='phixr-bot@localhost', help='Bot email')
def setup_bot(gitlab_url: str, root_token: str, bot_username: str, bot_email: str):
    """
    Set up Phixr bot user using a root PAT token.
    
    To generate the root PAT token:
    1. Go to http://localhost:8080
    2. Login with username 'root' and your password
    3. Click your profile icon (top-right)
    4. Select "Edit profile"
    5. Go to "Access tokens" or visit /-/profile/personal_access_tokens
    6. Click "Add new token"
    7. Name: "phixr-root-token"
    8. Scopes: Check all (or at least: api, read_api, write_repository, admin)
    9. Expiration: Leave empty
    10. Click "Create personal access token"
    11. Copy the token and paste it when prompted
    """
    
    click.echo("\n" + "="*60)
    click.echo("🚀 Phixr Bot Setup (via Root PAT Token)")
    click.echo("="*60)
    click.echo(f"GitLab URL: {gitlab_url}")
    click.echo(f"Bot username: {bot_username}\n")
    
    # Step 1: Verify root token works
    click.echo("Step 1: Verifying root token...")
    try:
        response = requests.get(
            f"{gitlab_url}/api/v4/user",
            headers={"PRIVATE-TOKEN": root_token},
            timeout=5
        )
        
        if response.status_code == 200:
            user = response.json()
            click.echo(f"✓ Authenticated as: {user['username']} (ID: {user['id']})")
        else:
            click.echo(f"✗ Token verification failed: {response.status_code}")
            click.echo(f"  Response: {response.text[:200]}")
            click.echo("\n💡 Make sure you've created a root PAT token in GitLab")
            return
            
    except Exception as e:
        click.echo(f"✗ Error: {e}")
        return
    
    # Step 2: Create bot user
    click.echo("\nStep 2: Creating bot user...")
    
    try:
        # Check if user exists
        response = requests.get(
            f"{gitlab_url}/api/v4/users",
            headers={"PRIVATE-TOKEN": root_token},
            params={"username": bot_username},
            timeout=5
        )
        
        if response.status_code == 200 and response.json():
            click.echo(f"✓ User '{bot_username}' already exists")
            bot_user_id = response.json()[0]['id']
        else:
            # Create new user
            user_data = {
                'username': bot_username,
                'email': bot_email,
                'name': 'Phixr Bot',
                'password': secrets.token_urlsafe(32)
            }
            
            response = requests.post(
                f"{gitlab_url}/api/v4/users",
                headers={"PRIVATE-TOKEN": root_token},
                json=user_data,
                timeout=5
            )
            
            if response.status_code == 201:
                bot_user = response.json()
                bot_user_id = bot_user['id']
                click.echo(f"✓ Created bot user with ID: {bot_user_id}")
            else:
                click.echo(f"✗ Failed to create user: {response.status_code}")
                click.echo(f"  Response: {response.text[:300]}")
                return
        
        # Step 3: Create bot PAT
        click.echo(f"\nStep 3: Creating bot PAT token...")
        
        # Small delay to ensure user is ready
        time.sleep(1)
        
        bot_token_data = {
            'name': 'phixr-bot-token',
            'scopes': ['api', 'read_api', 'write_repository'],
            'expires_at': None
        }
        
        response = requests.post(
            f"{gitlab_url}/api/v4/users/{bot_user_id}/personal_access_tokens",
            headers={"PRIVATE-TOKEN": root_token},
            json=bot_token_data,
            timeout=5
        )
        
        if response.status_code == 201:
            bot_token_obj = response.json()
            bot_token = bot_token_obj['token']
            click.echo(f"✓ Created bot PAT token")
        else:
            click.echo(f"✗ Failed to create PAT: {response.status_code}")
            click.echo(f"  Response: {response.text[:300]}")
            return
        
        # Display results
        click.echo("\n" + "="*60)
        click.echo("✅ Phixr bot setup completed!")
        click.echo("="*60)
        click.echo(f"\nBot Configuration:")
        click.echo(f"  Username: {bot_username}")
        click.echo(f"  Email: {bot_email}")
        click.echo(f"  User ID: {bot_user_id}")
        click.echo(f"  Token: {bot_token}")
        click.echo(f"\n📝 Add to your .env.local file:")
        click.echo(f"  GITLAB_BOT_TOKEN={bot_token}")
        click.echo(f"  GITLAB_URL={gitlab_url}")
        click.echo("\n🚀 Next step: Run the bot")
        click.echo(f"  python -m phixr.main")
        click.echo("="*60 + "\n")
        
    except requests.exceptions.RequestException as e:
        click.echo(f"✗ API Error: {e}")

if __name__ == '__main__':
    setup_bot()
