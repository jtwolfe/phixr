# 🚀 Next Steps: Getting Phase 1 Running

## Quick Start (5-10 minutes)

### Step 1: Create Root PAT Token

First, you need to generate a root personal access token:

1. **Open GitLab**: http://localhost:8080
2. **Login as root**:
   - Username: `root`
   - Password: `43hStVb9hSc1EWuIXdISinHFtE9gGemF9P0QFzm5gEI=`
3. **Generate PAT**:
   - Click your profile icon (top-right) → "Edit profile"
   - Go to "Access tokens" section (or visit `/-/profile/personal_access_tokens`)
   - Click "Add new token"
   - Name: `phixr-root-token`
   - Scopes: Check all boxes (or at least: `api`, `read_api`, `write_repository`, `admin`)
   - Expiration: Leave empty (never expire)
   - Click "Create personal access token"
   - **Copy the token** (you'll only see it once!)

### Step 2: Generate Bot User and Token (Automated)

Now run the setup script with your root PAT token:

```bash
cd /var/home/jim/workspace/phixr
source venv/bin/activate
python scripts/setup_bot_user.py --gitlab-url http://localhost:8080
```

When prompted, paste the root PAT token you just created. The script will:
- ✅ Verify your root token works
- ✅ Create the `phixr-bot` user
- ✅ Generate a personal access token for the bot
- ✅ Output the bot token to use

**Alternative: Manual Setup**

If you prefer, you can manually create the bot user and token through GitLab's web UI - see `docs/GITLAB_MANUAL_SETUP.md` for detailed steps.

### Step 2: Configure Environment

```bash
cd /var/home/jim/workspace/phixr
cp .env.example .env.local
```

Edit `.env.local` and add your bot token:
```
GITLAB_BOT_TOKEN=<paste-your-bot-token-here>
```

### Step 3: Run the Bot

```bash
cd /var/home/jim/workspace/phixr
source venv/bin/activate
python -m phixr.main
```

You should see:
```
2026-03-26 ... INFO     Phixr: Initializing Phixr...
2026-03-26 ... INFO     Phixr: Connected to GitLab as user: phixr-bot
2026-03-26 ... INFO     Phixr: Bot user ID: 2
2026-03-26 ... INFO     Phixr: ✅ Phixr initialized successfully
```

### Step 4: Test the Bot

1. **Create a test issue** in GitLab
2. **Assign phixr-bot** to the issue
3. **Comment**: `/ai-help`
4. **Bot should reply** with list of commands!

---

## What's Working Right Now

✅ Bot can be assigned to issues  
✅ Bot responds to slash commands  
✅ `/ai-help` - Lists available commands  
✅ `/ai-status` - Shows issue context  
✅ `/ai-acknowledge` - Bot confirms readiness  
✅ Full issue context is captured  
✅ Comments are tracked and organized  

---

## Troubleshooting

### Bot doesn't start
- Check `.env.local` has correct `GITLAB_BOT_TOKEN`
- Verify token has proper scopes (`api`, `read_api`)
- Try regenerating token in GitLab

### Bot doesn't respond to commands
- Confirm bot is assigned to the issue
- Check bot is responding (run with `LOG_LEVEL=DEBUG` to see logs)
- Verify GitLab webhook is configured (optional, but helps)

### Error: "Bot user not found"
- Make sure you created the `phixr-bot` user in GitLab
- Check username is exactly `phixr-bot` (case-sensitive)

---

## Next: Set Up Webhook (Optional but Recommended)

For better integration, configure GitLab to send webhook events:

1. Create a test project
2. Go to Settings > Webhooks
3. Add webhook:
   - URL: `http://localhost:8000/webhooks/gitlab`
   - Secret: `phixr-webhook-secret`
   - Trigger events: Issues, Comments
4. Click "Add webhook"

The bot will now get real-time notifications!

---

## Files You Might Need

- **Quick Start**: `docs/QUICKSTART.md`
- **Manual Setup**: `docs/GITLAB_MANUAL_SETUP.md`
- **Phase 1 Plan**: `PHASE_1_PLAN.md`
- **Implementation Summary**: `PHASE_1_SUMMARY.md`
- **Main App**: `phixr/main.py`
- **Configuration**: `.env.local` (create from .env.example)

---

## Architecture Overview

```
GitLab Instance (localhost:8080)
       ↓
   Bot assigned to issue
       ↓
   User comments: /ai-help
       ↓
GitLab sends webhook to:
       ↓
Phixr WebSocket Receiver (localhost:8000/webhooks/gitlab)
       ↓
Command Parser extracts /ai-*
       ↓
Context Extractor gathers issue details
       ↓
Handler processes command (/ai-help, /ai-status, etc.)
       ↓
Bot posts response to GitLab issue
       ↓
User sees response in issue comments
```

---

## What's Next (Phase 2)

- Containerize modified OpenCode
- Pass issue context to OpenCode container
- Execute code modifications in sandbox
- Generate MR/PR with changes
- Show results in bot comment

**Estimated timeline**: Ready after Phase 1 testing complete

---

**Questions?** Check the docs folder or review `phixr/main.py` for implementation details.
