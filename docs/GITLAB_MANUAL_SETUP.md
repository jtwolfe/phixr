# Manual GitLab Bot Setup Guide

Since the automated script requires proper GitLab authentication, here's a manual setup guide:

## Step 1: Access GitLab Web UI

1. Open browser and go to: http://localhost:8080
2. You'll be redirected to the login page
3. Log in as root user with password: `43hStVb9hSc1EWuIXdISinHFtE9gGemF9P0QFzm5gEI=`

## Step 2: Create Personal Access Token for Root

1. After logging in as root, go to: http://localhost:8080/-/profile/personal_access_tokens
2. Or: Click profile icon (top-right) > Edit Profile > Access Tokens
3. Create a new token with these settings:
   - Token name: `phixr-root-token`
   - Scopes: Select all (or at minimum: `api`, `read_api`, `write_repository`, `admin`)
   - Expiration: Leave empty (never expire) or set to future date
4. Click "Create personal access token"
5. **Save the token value** - it will only show once!

## Step 3: Create Bot User via Admin Panel

1. Go to: http://localhost:8080/-/admin/users (or Admin > Users & Permissions)
2. Click "New user"
3. Fill in:
   - Name: `Phixr Bot`
   - Username: `phixr-bot`
   - Email: `phixr-bot@localhost`
   - Password: Generate a strong password
4. Click "Create user"

## Step 4: Create Personal Access Token for Bot User

1. Go to the bot user's profile or admin panel
2. Click on the bot user from the users list
3. Go to Personal access tokens section
4. Create a new token:
   - Token name: `phixr-bot-token`
   - Scopes: `api`, `read_api`, `write_repository`
   - Expiration: Leave empty
5. **Save the token value**

## Step 5: Update .env.local

Edit `.env.local` with the tokens you created:

```
GITLAB_URL=http://localhost:8080
GITLAB_BOT_TOKEN=<bot-user-token-from-step-4>
BOT_USERNAME=phixr-bot
BOT_EMAIL=phixr-bot@localhost
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
WEBHOOK_SECRET=phixr-webhook-secret
LOG_LEVEL=INFO
```

## Step 6: Test the Bot

Run the Phixr bot application:

```bash
source venv/bin/activate
python -m phixr.main
```

Check health endpoint:
```bash
curl http://localhost:8000/health
```

You should see:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "gitlab_url": "http://localhost:8080"
}
```

## Step 7: Set Up a Webhook (Optional for local testing)

1. Create a test project in GitLab
2. Go to Settings > Webhooks
3. Add webhook:
   - URL: `http://localhost:8000/webhooks/gitlab` (or your public URL)
   - Secret: `phixr-webhook-secret` (match WEBHOOK_SECRET in .env.local)
   - Trigger: Issues, Comments
4. Click "Add webhook"

## Step 8: Test Bot in Issue

1. Create an issue in your test project
2. Assign the `phixr-bot` user to the issue
3. Add a comment: `/ai-help`
4. The bot should reply with available commands

---

## Troubleshooting

**"401 Unauthorized" when running bot:**
- Check GITLAB_BOT_TOKEN is correct in .env.local
- Verify the token hasn't expired
- Regenerate a new token and try again

**Bot doesn't respond to comments:**
- Ensure bot is assigned to the issue
- Check webhook is properly configured
- Look at bot logs for errors

**Can't create bot user:**
- Make sure you're logged in as root
- Check if user "phixr-bot" already exists (you may need to delete it first)
- Verify you have admin privileges

---

## Alternative: Use Automated Script (Once Tokens Are Set)

Once you have a valid root PAT token, you can use the automated script:

```bash
source venv/bin/activate
python -m scripts.setup_bot_user \
  --gitlab-url http://localhost:8080 \
  --root-token <your-root-pat-token>
```

This will:
1. Create the bot user automatically
2. Generate a bot PAT
3. Output the bot token to add to .env.local
