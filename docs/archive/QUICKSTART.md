# Phase 1 Quick Start Guide

## Prerequisites

- Python 3.11+
- Docker and Docker Compose (for running with PostgreSQL/Redis)
- GitLab instance running on localhost:8080 with root access
- pip

## Step 1: Set Up Python Environment

```bash
cd /var/home/jim/workspace/phixr

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r scripts/requirements_scripts.txt
```

## Step 2: Create Bot User in GitLab

```bash
# Run the bot setup script
python scripts/setup_bot_user.py

# You'll be prompted for:
# - GitLab root token (the password you have)
# - It will auto-configure the bot user

# The script will output your bot token - save this!
```

## Step 3: Configure Environment

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Edit `.env.local` and add:
- `GITLAB_BOT_TOKEN=<token from step 2>`
- `GITLAB_URL=http://localhost:8080`

## Step 4: Run Phixr Bot Locally (Development)

```bash
# Option A: With Docker Compose (includes PostgreSQL + Redis)
docker-compose up

# Option B: Direct Python (requires PostgreSQL + Redis running separately)
python -m phixr.main
```

The bot will start on `http://localhost:8000`

## Step 5: Test the Bot

1. In your GitLab instance, create a test issue
2. Assign the `phixr-bot` user to the issue
3. Add a comment: `/ai-help`
4. The bot should reply with available commands

## Verify Setup

Check the bot is running:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/info
```

## Next: Set Up Webhook

In GitLab project settings:
1. Go to Settings > Webhooks
2. Add webhook with URL: `http://localhost:8000/webhooks/gitlab` (or your public URL)
3. Set secret: `phixr-webhook-secret`
4. Select events: Issues, Comments
5. Save and test

## Troubleshooting

**Bot not responding to commands:**
- Check bot is assigned to the issue
- Verify webhook is being received (check logs)
- Ensure webhook secret matches

**GitLab connection error:**
- Verify `GITLAB_BOT_TOKEN` is set correctly
- Check GitLab URL is accessible
- Run setup script again

**Docker Compose issues:**
- Remove old containers: `docker-compose down -v`
- Rebuild: `docker-compose up --build`
