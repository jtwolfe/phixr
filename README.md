<div align="center">
  <img src="assets/phixr.jpg" alt="Phixr Logo" width="300" />
</div>

# Phixr

**Hybrid Git-Integrated AI Coding Platform**

Phixr bridges **GitLab's familiar workflow** with **OpenCode's excellent web UI**. Users interact with AI through natural language comments (`@phixr make a plan...`) while leveraging OpenCode's clean, fast interface for actual coding.

**Two Modes:**
- **Independent Mode**: Comment-driven automation (AI works like a professional colleague)
- **Vibe Mode**: Shared web interface for collaborative viewing

See [docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md) for complete project vision and requirements.

---

## 🚀 Key Features

- **Natural Language GitLab Integration** - `@phixr` commands in issues and comments
- **OpenCode WebUI Preservation** - Uses OpenCode's clean, fast interface
- **Two Operating Modes** - Independent (automated) and Vibe (collaborative)
- **Smart Git Operations** - Automatic branch creation, commits, and MRs
- **GitLab Web IDE Experience** - Branch-specific development environments
- **Enterprise Ready** - Designed for external model management

---

## 📋 Current Status

**✅ Core Infrastructure Complete:**
- Webhook handling and natural language command parsing
- OpenCode session management with robust error handling
- Vibe room framework for shared visibility
- Git operations and branch management

**Current Focus:** Implementing the two-mode architecture (Independent + Vibe) as defined in [docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md).

**Documentation:** All project documentation has been consolidated in the `docs/` directory for cleanliness. Only `README.md` remains in the project root.

---

## 🎯 Quick Start

### Prerequisites
- GitLab instance (localhost:8080 or your server)
- Python 3.11+
- Docker (optional, for containerized deployment)

### Quick Setup
1. **Clone and install**
   ```bash
   cd phixr
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure and start**
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local with your GitLab credentials
   python -m phixr.main
   ```

3. **Test it**
   - Create an issue in GitLab
   - Comment: `@phixr help` or `/ai-help`
   - Bot should respond with available commands

For detailed setup and configuration, see [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

---

## 📚 Documentation

**All documentation is in the `docs/` directory:**

### Core Documentation
- **[docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md)** - Current project vision and requirements
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Technical architecture
- **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** - Installation and setup
- **[docs/README.md](docs/README.md)** - Documentation index

### Supporting Documentation
- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - Quick start guide
- **[docs/GITLAB_MANUAL_SETUP.md](docs/GITLAB_MANUAL_SETUP.md)** - GitLab setup
- **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** - Testing procedures

**Historical documents** are archived in `docs/archive/` to maintain a clean repository structure.

---

## 🏗️ Project Status

**What's Working:**
- ✅ GitLab webhook handling and command parsing
- ✅ OpenCode session creation and management
- ✅ Vibe room framework
- ✅ Basic Git operations and branch management
- ✅ Documentation reorganization and cleanup

**Current Development Focus:**
- Two-mode system implementation (Independent + Vibe)
- Reliable OpenCode integration (addressing API limitations)
- Natural language command processing improvements
- Professional Git workflow automation

**See [docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md) for detailed requirements and success criteria.**

---

## 🤝 Contributing

1. Review [docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md) to understand the vision
2. Check [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical approach
3. See [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for development practices
4. All documentation changes should maintain the clean structure (only README.md in root)

---

<div align="center">
  <strong>Built with ❤️ for collaborative coding</strong>
  <br />
  <a href="https://opencode.ai">OpenCode</a> • GitLab Integration • AI Agents
</div>
⚠️ **NOTE**: These features are defined but the OpenCode integration layer needs fixes before they work.

**Intended Features** (when integration is fixed):
- `/ai-plan` - Generate implementation plan
- `/ai-implement` - AI implements the solution
- `/ai-review-mr` - AI reviews your merge request
- `/ai-fix-tests` - AI fixes failing tests
- Vibe room - Browser-based collaborative environment
- Web terminal - Access OpenCode via browser

**See**: [docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md) for current requirements and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical design

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

## 📚 Documentation

**All project documentation is now consolidated in the `docs/` directory:**

### Core Documentation
- **[docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md)** - Current project vision and requirements (primary reference)
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Technical architecture and implementation details
- **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** - Installation and setup guide

### Supporting Documentation
- **[docs/QUICKSTART.md](docs/QUICKSTART.md)** - Quick start guide
- **[docs/GITLAB_MANUAL_SETUP.md](docs/GITLAB_MANUAL_SETUP.md)** - GitLab environment setup
- **[docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)** - Testing procedures and guidelines
- **[docs/README.md](docs/README.md)** - Documentation index and navigation

**Historical documents** have been archived in `docs/archive/` to maintain a clean repository structure. See [docs/archive/README.md](docs/archive/README.md) for details on archived content.

---

## 📝 License

MIT License - see LICENSE file for details.

---

## 🙋 Questions?

- 📖 Check the documentation above
- 🤖 Review [docs/PROJECT_GOALS.md](docs/PROJECT_GOALS.md) for current direction
- 🛠️ See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical details

---

<div align="center">
  <strong>Built with ❤️ for collaborative coding</strong>
  <br />
  <a href="https://opencode.ai">OpenCode</a> • GitLab Integration • AI Agents
</div>
