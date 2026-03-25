<div align="center">
  <img src="assets/phixr.jpg" alt="Phixr Logo" width="300" />
</div>

# Phixr

**Hybrid Git-Integrated Collaborative AI Coding Platform**

Phixr is an **open-core, self-hosted hybrid AI coding agent** that bridges the structured world of GitLab / GitHub / Gitea issues/epics with real-time collaborative "vibe coding" sessions.

It lives natively inside your VCS web UI while offering a browser-based collaborative environment where you and an AI pair-program together, then ship polished merge requests with full session history preserved as Git artifacts.

---

## 🚀 Features

- **Zero-Friction Adoption** - Works directly from GitLab/GitHub issues you already use
- **Real-Time Collaboration** - Multi-user "vibe room" for mob programming with AI
- **Privacy First** - Fully self-hosted, local models, no data sent to third parties
- **Open-Core** - Free core features with optional paid org tier
- **Git-Native** - Full integration with your VCS (issues, MRs, epics, etc.)

---

## 📋 Current Status

**Phase 1: Bot Infrastructure ✅ COMPLETE**

The bot layer is fully operational:
- ✅ Bot user created and configured in GitLab
- ✅ Slash commands working (`/ai-help`, `/ai-status`, `/ai-acknowledge`)
- ✅ Issue context extraction functional
- ✅ Webhook receiver ready
- ✅ Full test coverage with working examples

**Phase 2: OpenCode Integration** 🔄 (Ready to begin)
- Containerize modified OpenCode
- Pass issue context to OpenCode
- Execute sandbox operations
- Auto-generate MR/PR with results

See [DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md) for current status and [PHASE_1_SUMMARY.md](./PHASE_1_SUMMARY.md) for Phase 1 details.

---

## 🎯 Quick Start

### Prerequisites
- GitLab instance (localhost:8080 or your server)
- Python 3.11+
- Docker (optional, for containerized deployment)

### Setup (5 minutes)

1. **Clone and install**
   ```bash
   cd phixr
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Generate bot credentials**
   ```bash
   python scripts/setup_bot_user.py --gitlab-url http://localhost:8080
   # Paste your root PAT token when prompted
   ```

3. **Start the bot**
   ```bash
   python -m phixr.main
   ```

4. **Test it**
   - Create an issue in GitLab
   - Assign `phixr-bot` user
   - Comment: `/ai-help`
   - Bot responds with available commands!

For detailed setup, see [GETTING_STARTED.md](./GETTING_STARTED.md).

---

## 📚 Documentation

- **[DESIGN.md](./DESIGN.md)** - Complete high-level design document
- **[GETTING_STARTED.md](./GETTING_STARTED.md)** - Setup instructions
- **[DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md)** - Current status and what's working
- **[PHASE_1_PLAN.md](./PHASE_1_PLAN.md)** - Detailed Phase 1 implementation plan
- **[PHASE_1_SUMMARY.md](./PHASE_1_SUMMARY.md)** - Phase 1 summary and architecture
- **[docs/QUICKSTART.md](./docs/QUICKSTART.md)** - Quick reference guide
- **[docs/GITLAB_MANUAL_SETUP.md](./docs/GITLAB_MANUAL_SETUP.md)** - Manual bot setup

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│      GitLab / GitHub / Gitea            │
│  (Issues, Comments, Events)             │
└──────────────┬──────────────────────────┘
               │ webhooks
               ▼
┌─────────────────────────────────────────┐
│      Phixr Bot Service                  │
│  ┌─────────────────────────────────────┐│
│  │ • Webhook Receiver                  ││
│  │ • Command Parser (/ai-*)            ││
│  │ • Context Extractor                 ││
│  │ • Assignment Tracker                ││
│  └─────────────────────────────────────┘│
└──────────────┬──────────────────────────┘
               │ API calls
       ┌───────┴────────┐
       ▼                ▼
    Redis          PostgreSQL
  (sessions)      (persistence)
```

---

## 🛠️ Project Structure

```
phixr/
├── assets/
│   └── phixr.jpg               # Logo
├── phixr/
│   ├── main.py                 # FastAPI application
│   ├── config/                 # Settings and configuration
│   ├── models/                 # Data models
│   ├── webhooks/               # GitLab webhook handlers
│   ├── handlers/               # Command handlers
│   ├── commands/               # Slash command parser
│   ├── context/                # Issue context extraction
│   ├── adapters/               # OpenCode integration (Phase 2)
│   ├── bridge/                 # Container lifecycle (Phase 2)
│   └── utils/                  # GitLab client, logging
├── scripts/
│   └── setup_bot_user.py       # Bot user creation script
├── docker/
│   └── Dockerfile              # Application container
├── docs/                       # Documentation
├── docker-compose.yml          # Local dev environment
├── requirements.txt            # Python dependencies
├── DESIGN.md                   # High-level design
├── PHASE_1_PLAN.md            # Phase 1 details
├── PHASE_1_SUMMARY.md         # Phase 1 summary
├── DEPLOYMENT_STATUS.md        # Current status
└── GETTING_STARTED.md         # Setup guide
```

---

## 🎮 Try the Bot

### What the Bot Can Do (Phase 1)

```
User:    /ai-help
Bot:     📚 **Available Commands:**
         - `/ai-status` - Show issue status and context
         - `/ai-help` - List available commands
         - `/ai-acknowledge` - Confirm bot is ready

User:    /ai-status
Bot:     ✅ **Bot Status:** Ready
         **Issue Context:**
         - Title: [issue title]
         - Author: [user]
         - Comments: [count]

User:    /ai-acknowledge
Bot:     👋 I'm ready to assist with this issue!
```

### What's Coming (Phase 2+)

- `/ai-plan` - Generate implementation plan
- `/ai-implement` - AI implements the solution
- `/ai-review-mr` - AI reviews your merge request
- `/ai-fix-tests` - AI fixes failing tests
- Vibe room - Browser-based collaborative environment
- Web terminal - Access OpenCode via browser

---

## 🔌 API Endpoints

- `GET /health` - Health check
- `GET /info` - Application info
- `POST /webhooks/gitlab` - GitLab webhook receiver (configured in GitLab UI)

---

## 🚢 Deployment

### Local Development
```bash
python -m phixr.main
# Runs on http://localhost:8000
```

### Docker Compose
```bash
docker-compose up
# Includes PostgreSQL, Redis, and Phixr bot
```

### Kubernetes
Ready for Kubernetes deployment - Helm charts coming in future phases.

---

## 🤝 Contributing

The project is structured for incremental development. Each phase has clear deliverables:

- **Phase 1** ✅ - Bot infrastructure & commands
- **Phase 2** 🔄 - OpenCode integration & sandbox
- **Phase 3** - Multi-user vibe room
- **Phase 4** - Analytics & team dashboard

Want to contribute? See [PHASE_1_PLAN.md](./PHASE_1_PLAN.md) for implementation details.

---

## 📝 License

Coming soon.

---

## 🙋 Questions?

- 📖 Check the [docs/](./docs/) folder
- 🤖 Review [DESIGN.md](./DESIGN.md) for architecture
- 🚀 See [GETTING_STARTED.md](./GETTING_STARTED.md) for setup
- 📊 Current status in [DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md)

---

<div align="center">
  <strong>Built with ❤️ for collaborative coding</strong>
  <br />
  <a href="https://github.com/anomalyco/opencode">OpenCode</a> • 
  <a href="https://github.com/sweep-ai/sweep">Sweep</a> • 
  <a href="https://github.com/paul-gauthier/aider">Aider</a>
</div>
