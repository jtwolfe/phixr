#!/usr/bin/env python3
"""
Create the Phixr bot user in GitLab using a root/admin personal access token.

Reads GITLAB_URL from .env.local if available. Prompts for the root token interactively.

Usage:
    python scripts/setup_bot_user.py
    python scripts/setup_bot_user.py --gitlab-url http://gitlab.example.com:8080
"""
import os
import secrets
import time
from pathlib import Path

import click
import httpx as requests


def _load_env_local():
    """Load values from .env.local into environment (without overwriting)."""
    for path in [Path(".env.local"), Path("/app/.env.local")]:
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        if key and value:
                            os.environ.setdefault(key.strip(), value.strip())
            break


_load_env_local()


@click.command()
@click.option('--gitlab-url',
              default=lambda: os.environ.get('GITLAB_URL', 'http://localhost:8080'),
              help='GitLab instance URL (reads from .env.local if set)')
@click.option('--root-token',
              default=lambda: os.environ.get('GITLAB_ROOT_TOKEN', ''),
              prompt='GitLab root/admin personal access token',
              hide_input=True,
              help='Root PAT token from GitLab')
@click.option('--bot-username', default='phixr', help='Bot username')
@click.option('--bot-email', default='phixr@localhost', help='Bot email')
def setup_bot(gitlab_url: str, root_token: str, bot_username: str, bot_email: str):
    """Create the Phixr bot user in GitLab.

    Requires a root/admin personal access token. To create one:

    \b
    1. Log into GitLab as admin
    2. Go to /-/profile/personal_access_tokens
    3. Name: "phixr-setup", Scopes: api + admin
    4. Create and copy the token
    """
    gitlab_url = gitlab_url.rstrip("/")

    click.echo(f"\nPhixr Bot Setup")
    click.echo(f"===============")
    click.echo(f"GitLab:   {gitlab_url}")
    click.echo(f"Bot user: {bot_username}\n")

    # Step 1: Verify root token
    click.echo("Verifying admin token...")
    try:
        resp = requests.get(
            f"{gitlab_url}/api/v4/user",
            headers={"PRIVATE-TOKEN": root_token},
            timeout=10
        )
        if resp.status_code != 200:
            click.echo(f"Error: token verification failed ({resp.status_code})")
            click.echo("Make sure you're using a root/admin personal access token.")
            return
        user = resp.json()
        click.echo(f"  Authenticated as: {user['username']} (ID: {user['id']})")
    except requests.ConnectError:
        click.echo(f"Error: cannot connect to {gitlab_url}")
        return
    except Exception as e:
        click.echo(f"Error: {e}")
        return

    # Step 2: Create or find bot user
    click.echo(f"\nCreating bot user '{bot_username}'...")
    try:
        resp = requests.get(
            f"{gitlab_url}/api/v4/users",
            headers={"PRIVATE-TOKEN": root_token},
            params={"username": bot_username},
            timeout=10
        )
        if resp.status_code == 200 and resp.json():
            bot_user_id = resp.json()[0]['id']
            click.echo(f"  User already exists (ID: {bot_user_id})")
        else:
            resp = requests.post(
                f"{gitlab_url}/api/v4/users",
                headers={"PRIVATE-TOKEN": root_token},
                json={
                    'username': bot_username,
                    'email': bot_email,
                    'name': 'Phixr',
                    'password': secrets.token_urlsafe(32),
                },
                timeout=10
            )
            if resp.status_code == 201:
                bot_user_id = resp.json()['id']
                click.echo(f"  Created user (ID: {bot_user_id})")
            else:
                click.echo(f"  Error creating user: {resp.status_code}")
                click.echo(f"  {resp.text[:300]}")
                return

        # Step 3: Create bot PAT
        click.echo(f"\nCreating personal access token...")
        time.sleep(1)

        resp = requests.post(
            f"{gitlab_url}/api/v4/users/{bot_user_id}/personal_access_tokens",
            headers={"PRIVATE-TOKEN": root_token},
            json={
                'name': 'phixr-token',
                'scopes': ['api', 'read_api', 'write_repository'],
                'expires_at': None,
            },
            timeout=10
        )
        if resp.status_code == 201:
            bot_token = resp.json()['token']
            click.echo(f"  Token created")
        else:
            click.echo(f"  Error creating token: {resp.status_code}")
            click.echo(f"  {resp.text[:300]}")
            return

        # Done
        click.echo(f"\n{'=' * 50}")
        click.echo(f"Bot setup complete!")
        click.echo(f"{'=' * 50}")
        click.echo(f"\nAdd to your .env.local:")
        click.echo(f"  GITLAB_BOT_TOKEN={bot_token}")
        click.echo(f"  PHIXR_SANDBOX_GIT_PROVIDER_TOKEN={bot_token}")
        click.echo(f"\nThen start Phixr:")
        click.echo(f"  python -m phixr.main")
        click.echo()

    except requests.HTTPError as e:
        click.echo(f"API error: {e}")


if __name__ == '__main__':
    setup_bot()
